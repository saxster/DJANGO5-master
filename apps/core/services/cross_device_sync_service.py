"""
Cross-Device Sync Coordinator

Coordinates sync across multiple user devices with priority-based conflict resolution.

Features:
- Device registry management
- Cross-device conflict detection
- Priority-based resolution
- Device-to-device notifications

Follows .claude/rules.md:
- Rule #7: Service methods < 50 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
from typing import Dict, Any, Optional
from django.db import transaction, DatabaseError
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.core.models.device_registry import UserDevice, DeviceSyncState
from apps.core.services.sync_push_service import sync_push_service
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger('sync.cross_device')


class CrossDeviceSyncService:
    """Coordinate sync across multiple user devices."""

    DEFAULT_PRIORITIES = {
        'desktop': 100,
        'laptop': 80,
        'tablet': 60,
        'phone': 40,
    }

    @classmethod
    def register_device(cls, user, device_id: str, device_type: str,
                       **metadata) -> UserDevice:
        """
        Register or update device in registry.

        Args:
            user: User instance
            device_id: Unique device identifier
            device_type: phone, tablet, laptop, desktop
            **metadata: Additional device metadata

        Returns:
            UserDevice instance
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                device, created = UserDevice.objects.update_or_create(
                    device_id=device_id,
                    defaults={
                        'user': user,
                        'device_type': device_type,
                        'priority': cls.DEFAULT_PRIORITIES.get(device_type, 50),
                        'device_name': metadata.get('device_name', ''),
                        'os_type': metadata.get('os_type', ''),
                        'os_version': metadata.get('os_version', ''),
                        'app_version': metadata.get('app_version', ''),
                        'is_active': True,
                    }
                )

                action = 'registered' if created else 'updated'
                logger.info(f"Device {action}: {device_id} ({device_type})")

                return device

        except (DatabaseError, ValueError) as e:
            logger.error(f"Failed to register device: {e}", exc_info=True)
            raise

    @classmethod
    def sync_across_devices(cls, user, device_id: str, domain: str,
                           entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync data and coordinate across user's devices.

        Args:
            user: User instance
            device_id: Source device
            domain: Data domain
            entity_id: Entity identifier
            data: Sync data with version

        Returns:
            Sync result with coordination info
        """
        try:
            device = UserDevice.objects.get(device_id=device_id, user=user)

            sync_states = DeviceSyncState.objects.filter(
                device__user=user,
                domain=domain,
                entity_id=entity_id
            ).select_related('device').order_by('-last_sync_version')

            latest_state = sync_states.first()

            if latest_state and latest_state.last_sync_version > data.get('version', 0):
                return cls._resolve_cross_device_conflict(
                    current_device=device,
                    latest_device=latest_state.device,
                    domain=domain,
                    entity_id=entity_id,
                    data=data
                )

            DeviceSyncState.objects.update_or_create(
                device=device,
                domain=domain,
                entity_id=entity_id,
                defaults={
                    'last_sync_version': data.get('version', 0),
                    'last_modified_at': timezone.now(),
                    'is_dirty': False,
                }
            )

            other_devices = UserDevice.objects.filter(
                user=user,
                is_active=True
            ).exclude(device_id=device_id)

            for other_device in other_devices:
                sync_push_service.push_to_user_sync(
                    user_id=user.id,
                    data={
                        'type': 'sync_from_device',
                        'device_id': device_id,
                        'domain': domain,
                        'entity_id': entity_id,
                        'action': 'refresh'
                    }
                )

            return {
                'status': 'synced',
                'notified_devices': other_devices.count(),
                'conflict': False
            }

        except (ObjectDoesNotExist, DatabaseError) as e:
            logger.error(f"Cross-device sync error: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @classmethod
    def _resolve_cross_device_conflict(cls, current_device: UserDevice,
                                       latest_device: UserDevice,
                                       domain: str, entity_id: str,
                                       data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve conflict using device priority.

        Args:
            current_device: Device attempting sync
            latest_device: Device with latest version
            domain: Data domain
            entity_id: Entity ID
            data: Sync data

        Returns:
            Resolution result
        """
        if current_device.priority > latest_device.priority:
            winning_device = current_device
            resolution = 'current_wins'
        elif latest_device.priority > current_device.priority:
            winning_device = latest_device
            resolution = 'latest_wins'
        else:
            if data.get('modified_at', '') > latest_device.last_seen.isoformat():
                winning_device = current_device
                resolution = 'most_recent_wins'
            else:
                winning_device = latest_device
                resolution = 'latest_wins'

        logger.info(
            f"Cross-device conflict: {domain}/{entity_id} - "
            f"{resolution} (winner: {winning_device.device_id})"
        )

        return {
            'status': 'conflict_resolved',
            'resolution': resolution,
            'winning_device': winning_device.device_id,
            'conflict': True
        }

    @classmethod
    def get_user_devices(cls, user) -> list:
        """Get all active devices for user."""
        return list(UserDevice.objects.filter(user=user, is_active=True))

    @classmethod
    def deactivate_device(cls, device_id: str) -> bool:
        """Deactivate device (lost/stolen)."""
        try:
            device = UserDevice.objects.get(device_id=device_id)
            device.is_active = False
            device.save()

            logger.info(f"Deactivated device: {device_id}")
            return True

        except ObjectDoesNotExist:
            return False


cross_device_sync_service = CrossDeviceSyncService()