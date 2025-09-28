"""
Signal handlers for peoples app.

This module contains signal handlers for People model operations including:
- MQTT message publishing for real-time updates
- Automatic creation of related models (PeopleProfile, PeopleOrganizational)
- Session rotation on privilege changes (Rule #10: Session Security)
"""

import json
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver, Signal
from django.db import DatabaseError, IntegrityError
from apps.peoples.models import People
from apps.peoples.serializers import PeopleSerializer

logger = logging.getLogger("peoples.signals")

TOPIC = "redmine_to_noc"


def build_payload(instance, model_name, created):
    """Build MQTT payload for People model changes."""
    serializer_cls = {"People": PeopleSerializer}[model_name]
    serializer = serializer_cls(instance)
    return json.dumps(
        {
            "operation": "CREATE" if created else "UPDATE",
            "app": "Peoples",
            "models": model_name,
            "payload": serializer.data,
        }
    )


@receiver(post_save, sender=People)
def people_post_save(sender, instance, created, **kwargs):
    """Publish MQTT message when People instance is saved."""
    payload = build_payload(instance, "People", created)
    # publish_mqtt.delay(TOPIC, payload)  # Temporarily disabled - RabbitMQ not running


@receiver(post_save, sender=People)
def create_people_profile(sender, instance, created, **kwargs):
    """
    Automatically create PeopleProfile when a People instance is created.

    TRANSACTION BEHAVIOR:
    - This signal fires WITHIN the parent transaction if the caller uses transaction.atomic
    - If the parent transaction rolls back, this PeopleProfile will also be rolled back
    - DO NOT add transaction.atomic here - it would create unnecessary savepoints

    Complies with: .claude/rules.md - Transaction Management Requirements

    Args:
        sender: The model class (People)
        instance: The actual instance being saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    if created:
        try:
            from apps.peoples.models.profile_model import PeopleProfile
            from datetime import date

            dateofbirth = getattr(instance, '_temp_dateofbirth', date(1990, 1, 1))
            dateofjoin = getattr(instance, '_temp_dateofjoin', None)
            gender = getattr(instance, '_temp_gender', None)
            peopleimg = getattr(instance, '_temp_peopleimg', None)

            PeopleProfile.objects.create(
                people=instance,
                dateofbirth=dateofbirth,
                dateofjoin=dateofjoin,
                gender=gender,
                peopleimg=peopleimg
            )

            logger.info(
                f"Created PeopleProfile for user",
                extra={
                    'user_id': instance.id,
                    'peoplename': instance.peoplename
                }
            )

        except IntegrityError as e:
            logger.warning(
                f"PeopleProfile already exists for user",
                extra={
                    'user_id': instance.id,
                    'error': str(e)
                }
            )
        except DatabaseError as e:
            logger.error(
                f"Database error creating PeopleProfile",
                extra={
                    'user_id': instance.id,
                    'error': str(e)
                }
            )


@receiver(post_save, sender=People)
def create_people_organizational(sender, instance, created, **kwargs):
    """
    Automatically create PeopleOrganizational when a People instance is created.

    TRANSACTION BEHAVIOR:
    - This signal fires WITHIN the parent transaction if the caller uses transaction.atomic
    - If the parent transaction rolls back, this PeopleOrganizational will also be rolled back
    - DO NOT add transaction.atomic here - it would create unnecessary savepoints

    Complies with: .claude/rules.md - Transaction Management Requirements

    Args:
        sender: The model class (People)
        instance: The actual instance being saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    if created:
        try:
            from apps.peoples.models.organizational_model import PeopleOrganizational

            location = getattr(instance, '_temp_location', None)
            department = getattr(instance, '_temp_department', None)
            designation = getattr(instance, '_temp_designation', None)
            peopletype = getattr(instance, '_temp_peopletype', None)
            worktype = getattr(instance, '_temp_worktype', None)
            client = getattr(instance, '_temp_client', None)
            bu = getattr(instance, '_temp_bu', None)
            reportto = getattr(instance, '_temp_reportto', None)

            PeopleOrganizational.objects.create(
                people=instance,
                location=location,
                department=department,
                designation=designation,
                peopletype=peopletype,
                worktype=worktype,
                client=client,
                bu=bu,
                reportto=reportto
            )

            logger.info(
                f"Created PeopleOrganizational for user",
                extra={
                    'user_id': instance.id,
                    'peoplename': instance.peoplename
                }
            )

        except IntegrityError as e:
            logger.warning(
                f"PeopleOrganizational already exists for user",
                extra={
                    'user_id': instance.id,
                    'error': str(e)
                }
            )
        except DatabaseError as e:
            logger.error(
                f"Database error creating PeopleOrganizational",
                extra={
                    'user_id': instance.id,
                    'error': str(e)
                }
            )


privilege_changed = Signal()


@receiver(pre_save, sender=People)
def track_privilege_changes(sender, instance, **kwargs):
    """
    Track privilege changes before save to enable session rotation.

    Implements Rule #10: Session Security Standards.
    When privileges are elevated, the user's session should be rotated
    to prevent session fixation attacks.

    Args:
        sender: The model class (People)
        instance: The instance being saved
        **kwargs: Additional keyword arguments
    """
    if instance.pk:
        try:
            old_instance = People.objects.get(pk=instance.pk)

            old_privileges = {
                'is_superuser': old_instance.is_superuser,
                'is_staff': old_instance.is_staff,
                'isadmin': old_instance.isadmin
            }

            new_privileges = {
                'is_superuser': instance.is_superuser,
                'is_staff': instance.is_staff,
                'isadmin': instance.isadmin
            }

            privilege_escalated = False
            for key in ['is_superuser', 'is_staff', 'isadmin']:
                if not old_privileges[key] and new_privileges[key]:
                    privilege_escalated = True
                    break

            if privilege_escalated:
                instance._privilege_changed = True
                instance._old_privileges = old_privileges
                instance._new_privileges = new_privileges

                logger.warning(
                    f"Privilege escalation detected for user {instance.peoplecode}",
                    extra={
                        'user_id': instance.id,
                        'peoplecode': instance.peoplecode,
                        'old_privileges': old_privileges,
                        'new_privileges': new_privileges
                    }
                )

        except People.DoesNotExist:
            pass
        except DatabaseError as e:
            logger.error(f"Error tracking privilege changes: {str(e)}")


@receiver(post_save, sender=People)
def handle_privilege_change(sender, instance, created, **kwargs):
    """
    Handle privilege changes by triggering session rotation.

    Implements Rule #10: Session Security Standards.

    Args:
        sender: The model class (People)
        instance: The saved instance
        created: Boolean; True if new record
        **kwargs: Additional keyword arguments
    """
    if not created and getattr(instance, '_privilege_changed', False):
        try:
            privilege_changed.send(
                sender=sender,
                instance=instance,
                old_privileges=getattr(instance, '_old_privileges', {}),
                new_privileges=getattr(instance, '_new_privileges', {})
            )

            logger.info(
                f"Privilege change signal sent for user {instance.peoplecode}",
                extra={
                    'user_id': instance.id,
                    'old_privileges': getattr(instance, '_old_privileges', {}),
                    'new_privileges': getattr(instance, '_new_privileges', {})
                }
            )

            delattr(instance, '_privilege_changed')
            if hasattr(instance, '_old_privileges'):
                delattr(instance, '_old_privileges')
            if hasattr(instance, '_new_privileges'):
                delattr(instance, '_new_privileges')

        except (AttributeError, ValueError) as e:
            logger.error(f"Error handling privilege change: {str(e)}")
