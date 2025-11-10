"""
Audit Logging Signal Handlers

Automatically captures audit events for all workflow models using Django signals.

Features:
- Automatic audit trail for CRUD operations
- State transition tracking
- PII redaction integration
- Correlation ID support
- Tenant-aware audit logging

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #15: PII redaction in audit logs
- Rule #17: Transaction management

Usage:
    # In your app's apps.py:
    def ready(self):
        from apps.core.signals import audit_signals
"""

import logging
from typing import Optional, Dict, Any
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver, Signal
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, IntegrityError
import uuid

from apps.core.services.unified_audit_service import EntityAuditService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, CACHE_EXCEPTIONS

logger = logging.getLogger(__name__)

# Custom signal for state transitions
state_transition_signal = Signal()


# Models to audit (extend this list as needed)
AUDITED_MODELS = [
    'work_order_management.Wom',
    'work_order_management.WomDetails',
    'activity.Job',
    'activity.Jobneed',
    'attendance.PeopleEventlog',
    'y_helpdesk.Ticket',
]


def is_audited_model(instance) -> bool:
    """Check if model instance should be audited."""
    model_label = f"{instance._meta.app_label}.{instance._meta.model_name}"
    return any(model_label.lower() == audited.lower() for audited in AUDITED_MODELS)


def get_correlation_id(instance) -> uuid.UUID:
    """Get or generate correlation ID for audit event."""
    # Check if request context has correlation ID
    if hasattr(instance, '_audit_correlation_id'):
        return instance._audit_correlation_id

    # Generate new correlation ID
    return uuid.uuid4()


def get_actor_from_context(instance):
    """Extract actor (user) from instance or request context."""
    # Check if instance has current user attached
    if hasattr(instance, '_current_user'):
        return instance._current_user

    # Check if instance has created_by/updated_by field
    if hasattr(instance, 'updated_by') and instance.updated_by:
        return instance.updated_by
    elif hasattr(instance, 'created_by') and instance.created_by:
        return instance.created_by

    # No user available - system action
    return None


def get_model_snapshot(instance) -> Dict[str, Any]:
    """Get dictionary snapshot of model instance for audit."""
    snapshot = {}

    for field in instance._meta.fields:
        field_name = field.name
        try:
            field_value = getattr(instance, field_name)

            # Convert complex types to JSON-serializable format
            if hasattr(field_value, 'isoformat'):  # datetime
                snapshot[field_name] = field_value.isoformat()
            elif hasattr(field_value, 'pk'):  # ForeignKey
                snapshot[field_name] = str(field_value.pk)
            else:
                snapshot[field_name] = str(field_value)
        except (AttributeError, ValueError, TypeError) as e:
            logger.debug(f"Could not serialize field {field_name}: {e}")
            snapshot[field_name] = '<unable to serialize>'

    return snapshot


# Store previous state for update tracking
_instance_cache = {}


@receiver(pre_save)
def cache_previous_state(sender, instance, **kwargs):
    """Cache previous state before save for change tracking."""
    if not is_audited_model(instance):
        return

    if instance.pk:  # Only for updates, not creation
        try:
            previous_instance = sender.objects.get(pk=instance.pk)
            cache_key = f"{sender._meta.label}:{instance.pk}"
            _instance_cache[cache_key] = get_model_snapshot(previous_instance)
        except sender.DoesNotExist:
            pass
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to cache previous state: {e}", exc_info=True)


@receiver(post_save)
def log_entity_save(sender, instance, created, **kwargs):
    """Log entity creation or update to audit trail."""
    if not is_audited_model(instance):
        return

    try:
        actor = get_actor_from_context(instance)
        correlation_id = get_correlation_id(instance)

        # Skip audit if explicitly disabled for this instance
        if hasattr(instance, '_skip_audit') and instance._skip_audit:
            return

        audit_service = EntityAuditService(
            user=actor,
            correlation_id=str(correlation_id)
        )

        if created:
            # Entity creation
            audit_service.log_entity_created(
                entity=instance,
                action=f"{sender._meta.label} created",
                metadata={'correlation_id': str(correlation_id)}
            )
            logger.info(
                f"Audit logged: Created {sender._meta.label} ID={instance.pk}",
                extra={'correlation_id': str(correlation_id)}
            )
        else:
            # Entity update
            cache_key = f"{sender._meta.label}:{instance.pk}"
            old_data = _instance_cache.pop(cache_key, {})
            new_data = get_model_snapshot(instance)

            audit_service.log_entity_updated(
                entity=instance,
                action=f"{sender._meta.label} updated",
                changes={'before': old_data, 'after': new_data},
                metadata={'correlation_id': str(correlation_id)}
            )
            logger.info(
                f"Audit logged: Updated {sender._meta.label} ID={instance.pk}",
                extra={'correlation_id': str(correlation_id)}
            )

    except DATABASE_EXCEPTIONS as e:
        # Don't let audit failures break the main operation
        logger.error(
            f"Failed to log audit for {sender._meta.label} save: {e}",
            exc_info=True,
            extra={
                'model': sender._meta.label,
                'instance_pk': instance.pk,
                'created': created,
            }
        )
    except CACHE_EXCEPTIONS as e:
        # Catch any other unexpected errors
        logger.error(
            f"Unexpected error in audit logging: {e}",
            exc_info=True,
            extra={
                'model': sender._meta.label,
                'instance_pk': instance.pk,
            }
        )


@receiver(post_delete)
def log_entity_delete(sender, instance, **kwargs):
    """Log entity deletion to audit trail."""
    if not is_audited_model(instance):
        return

    try:
        actor = get_actor_from_context(instance)
        correlation_id = get_correlation_id(instance)

        # Skip audit if explicitly disabled
        if hasattr(instance, '_skip_audit') and instance._skip_audit:
            return

        audit_service = EntityAuditService(
            user=actor,
            correlation_id=str(correlation_id)
        )
        snapshot = get_model_snapshot(instance)

        audit_service.log_entity_deleted(
            entity=instance,
            action=f"{sender._meta.label} deleted",
            metadata={
                'snapshot': snapshot,
                'correlation_id': str(correlation_id),
            }
        )

        logger.info(
            f"Audit logged: Deleted {sender._meta.label} ID={instance.pk}",
            extra={'correlation_id': str(correlation_id)}
        )

    except DATABASE_EXCEPTIONS as e:
        # Don't let audit failures break the delete operation
        logger.error(
            f"Failed to log audit for {sender._meta.label} delete: {e}",
            exc_info=True,
            extra={
                'model': sender._meta.label,
                'instance_pk': instance.pk,
            }
        )
    except CACHE_EXCEPTIONS as e:
        logger.error(
            f"Unexpected error in delete audit logging: {e}",
            exc_info=True,
            extra={
                'model': sender._meta.label,
                'instance_pk': instance.pk,
            }
        )


@receiver(state_transition_signal)
def log_state_transition(sender, instance, from_state, to_state, comments, **kwargs):
    """Log state transition to audit trail."""
    try:
        actor = get_actor_from_context(instance)
        correlation_id = get_correlation_id(instance)

        audit_service = EntityAuditService(
            user=actor,
            correlation_id=str(correlation_id)
        )

        audit_service.log_state_transition(
            entity=instance,
            from_state=from_state,
            to_state=to_state,
            action=comments or f"{sender._meta.label} state transition",
            successful=kwargs.get('successful', True),
            failure_reason=kwargs.get('failure_reason'),
            metadata={
                **(kwargs.get('metadata') or {}),
                'correlation_id': str(correlation_id),
            }
        )

        logger.info(
            f"Audit logged: State transition {from_state} → {to_state} for {sender._meta.label} ID={instance.pk}",
            extra={'correlation_id': str(correlation_id)}
        )

    except DATABASE_EXCEPTIONS as e:
        logger.error(
            f"Failed to log state transition audit: {e}",
            exc_info=True,
            extra={
                'model': sender._meta.label,
                'instance_pk': instance.pk,
                'from_state': from_state,
                'to_state': to_state,
            }
        )
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"Unexpected error in state transition audit logging: {e}",
            exc_info=True
        )


# Helper functions for manual signal triggering


def attach_audit_context(instance, user=None, correlation_id=None):
    """
    Attach audit context to model instance before save.

    Usage:
        work_order = Wom.objects.get(pk=123)
        attach_audit_context(work_order, user=request.user)
        work_order.status = 'APPROVED'
        work_order.save()  # Audit automatically logged with user context
    """
    if user:
        instance._current_user = user
    if correlation_id:
        instance._audit_correlation_id = correlation_id
    return instance


def skip_audit_for_instance(instance):
    """
    Skip audit logging for this specific instance save.

    Usage:
        # For bulk operations where audit is handled separately
        for item in items:
            skip_audit_for_instance(item)
            item.save()
    """
    instance._skip_audit = True
    return instance


def trigger_state_transition_audit(instance, from_state, to_state, comments='', user=None):
    """
    Manually trigger state transition audit.

    Usage:
        from apps.core.signals.audit_signals import trigger_state_transition_audit

        trigger_state_transition_audit(
            instance=work_order,
            from_state='DRAFT',
            to_state='SUBMITTED',
            comments='Submitted for approval',
            user=request.user
        )
    """
    if user:
        attach_audit_context(instance, user=user)

    state_transition_signal.send(
        sender=instance.__class__,
        instance=instance,
        from_state=from_state,
        to_state=to_state,
        comments=comments
    )
