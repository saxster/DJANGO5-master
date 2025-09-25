from django.db.models.signals import post_save
from apps.onboarding.models import Bt, TypeAssist, Shift, GeofenceMaster
from apps.onboarding.serializers import (
    GeofenceMasterSerializers,
    BtSerializers,
    ShiftSerializers,
    TypeAssistSerializers,
)
from django.dispatch import receiver
import json

from background_tasks.tasks import publish_mqtt

TOPIC = "redmine_to_noc"


def build_payload(instance, model_name, created):
    serializer_cls = {
        "Bt": BtSerializers,
        "TypeAssist": TypeAssistSerializers,
        "Shift": ShiftSerializers,
        "GeofenceMaster": GeofenceMasterSerializers,
    }[model_name]
    serializer = serializer_cls(instance)
    return json.dumps(
        {
            "operation": "CREATE" if created else "UPDATE",
            "app": "onboarding",
            "models": model_name,
            "payload": serializer.data,
        }
    )


@receiver(post_save, sender=Bt)
def bt_post_save(sender, instance, created, **kwargs):
    payload = build_payload(instance, "Bt", created)
    publish_mqtt.delay(TOPIC, payload)


@receiver(post_save, sender=TypeAssist)
def typeassist_post_save(sender, instance, created, **kwargs):
    payload = build_payload(instance, "TypeAssist", created)
    publish_mqtt.delay(TOPIC, payload)


@receiver(post_save, sender=Shift)
def shift_post_save(sender, instance, created, **kwargs):
    payload = build_payload(instance, "Shift", created)
    publish_mqtt.delay(TOPIC, payload)


@receiver(post_save, sender=GeofenceMaster)
def geofencemaster_post_save(sender, instance, created, **kwargs):
    payload = build_payload(instance, "GeofenceMaster", created)
    publish_mqtt.delay(TOPIC, payload)
    
    # Invalidate geofence cache when geofence is modified
    try:
        from apps.core.services.geofence_service import geofence_service
        geofence_service.invalidate_geofence_cache(
            client_id=instance.client_id, 
            bu_id=instance.bu_id
        )
        
        # Log the modification for audit trail
        if hasattr(instance, '_audit_user_id'):
            changes = {}
            if created:
                changes = {'action': 'created'}
            else:
                # In a more complete implementation, we'd track field changes
                changes = {'action': 'updated'}
            
            geofence_service.audit_trail.log_geofence_modification(
                geofence_id=instance.id,
                user_id=getattr(instance, '_audit_user_id', -1),
                action='CREATE' if created else 'UPDATE',
                changes=changes
            )
    except ImportError:
        # Service not available, skip cache invalidation
        pass
