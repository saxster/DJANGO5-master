"""
Notification Preferences Service

Per-user/role notification channel and timing preferences.
Supports SMS, email, push notifications with quiet hours and priority routing.

Features:
- Channel-specific preferences (SMS, email, push)
- Quiet hours enforcement (e.g., 10PM-7AM)
- Priority-based routing (SOS alerts bypass quiet hours)
- On-call rotation support
- Role-based defaults

Stores preferences in People.other_data with structure:
{
    "notification_preferences": {
        "channels": {
            "sms": {"enabled": true, "priorities": ["CRITICAL", "SOS"]},
            "email": {"enabled": true, "priorities": ["ALL"]},
            "push": {"enabled": true, "priorities": ["CRITICAL", "HIGH"]}
        },
        "quiet_hours": {"enabled": true, "start": "22:00", "end": "07:00"},
        "on_call": {"enabled": false, "bypass_quiet_hours": true},
        "timezone_offset": 0
    }
}

Compliance: CLAUDE.md Rule #7 (file size), Rule #11 (specific exceptions)
"""

import logging
from datetime import datetime, time, timezone as dt_timezone
from typing import Dict, List, Optional

from django.core.exceptions import ValidationError, ObjectDoesNotExist

from apps.peoples.models import People
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, JSON_EXCEPTIONS
from apps.core.utils_new.datetime_utilities import get_current_utc

logger = logging.getLogger(__name__)


class NotificationPreferencesService:
    """
    Service for managing user notification preferences.
    """

    CHANNELS = ['sms', 'email', 'push', 'webhook']
    PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'SOS']

    DEFAULT_PREFERENCES = {
        'channels': {
            'sms': {'enabled': False, 'priorities': ['SOS']},
            'email': {'enabled': True, 'priorities': ['ALL']},
            'push': {'enabled': True, 'priorities': ['HIGH', 'CRITICAL', 'SOS']},
        },
        'quiet_hours': {'enabled': True, 'start': '22:00', 'end': '07:00'},
        'on_call': {'enabled': False, 'bypass_quiet_hours': False},
        'timezone_offset': 0,
    }

    @classmethod
    def should_notify(
        cls,
        user_id: int,
        channel: str,
        priority: str = 'MEDIUM'
    ) -> bool:
        """
        Check if user should receive notification on given channel.

        Args:
            user_id: User identifier
            channel: Notification channel (sms, email, push)
            priority: Message priority level

        Returns:
            True if notification should be sent
        """
        if channel not in cls.CHANNELS:
            logger.warning(f"Invalid notification channel: {channel}")
            return False

        try:
            preferences = cls.get_preferences(user_id)

            if not cls._is_channel_enabled(preferences, channel, priority):
                return False

            if priority in ['SOS', 'CRITICAL']:
                return True

            if preferences.get('on_call', {}).get('enabled', False):
                if preferences['on_call'].get('bypass_quiet_hours', False):
                    return True

            if cls._is_quiet_hours(preferences):
                logger.info(
                    f"Suppressing {priority} notification to user {user_id} "
                    f"during quiet hours"
                )
                return False

            return True

        except (ValueError, TypeError) as e:
            logger.error(f"Error checking notification preferences: {e}")
            return True

    @classmethod
    def get_preferences(cls, user_id: int) -> Dict:
        """
        Get notification preferences for user.

        Args:
            user_id: User identifier

        Returns:
            Preferences dictionary (returns defaults if not configured)
        """
        try:
            user = People.objects.get(id=user_id)
            stored_prefs = user.other_data.get('notification_preferences', {})

            prefs = cls.DEFAULT_PREFERENCES.copy()
            cls._deep_merge(prefs, stored_prefs)

            return prefs

        except ObjectDoesNotExist:
            logger.warning(f"User {user_id} not found, using defaults")
            return cls.DEFAULT_PREFERENCES.copy()
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error fetching preferences: {e}")
            return cls.DEFAULT_PREFERENCES.copy()

    @classmethod
    def set_preferences(cls, user_id: int, preferences: Dict) -> bool:
        """
        Update notification preferences for user.

        Args:
            user_id: User identifier
            preferences: New preferences dictionary

        Returns:
            True if saved successfully

        Raises:
            ValidationError: If preferences invalid
        """
        cls._validate_preferences(preferences)

        try:
            user = People.objects.get(id=user_id)
            current = user.other_data.get('notification_preferences', {})

            cls._deep_merge(current, preferences)
            user.other_data['notification_preferences'] = current
            user.save()

            logger.info(f"Updated notification preferences for user {user_id}")
            return True

        except ObjectDoesNotExist:
            raise ValidationError(f"User {user_id} not found")
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error saving preferences: {e}", exc_info=True)
            raise ValidationError("Failed to save notification preferences")

    @classmethod
    def enable_on_call(cls, user_id: int, bypass_quiet_hours: bool = True) -> bool:
        """
        Enable on-call mode for user.

        Args:
            user_id: User identifier
            bypass_quiet_hours: Whether to receive all notifications during quiet hours

        Returns:
            True if updated
        """
        return cls.set_preferences(user_id, {
            'on_call': {
                'enabled': True,
                'bypass_quiet_hours': bypass_quiet_hours,
                'enabled_at': get_current_utc().isoformat(),
            }
        })

    @classmethod
    def disable_on_call(cls, user_id: int) -> bool:
        """Disable on-call mode for user."""
        return cls.set_preferences(user_id, {
            'on_call': {'enabled': False}
        })

    @classmethod
    def _is_channel_enabled(cls, preferences: Dict, channel: str, priority: str) -> bool:
        """Check if channel is enabled for priority level."""
        channel_config = preferences.get('channels', {}).get(channel, {})

        if not channel_config.get('enabled', False):
            return False

        allowed_priorities = channel_config.get('priorities', [])

        if 'ALL' in allowed_priorities:
            return True

        return priority in allowed_priorities

    @classmethod
    def _is_quiet_hours(cls, preferences: Dict) -> bool:
        """Check if current time is within quiet hours."""
        quiet_config = preferences.get('quiet_hours', {})

        if not quiet_config.get('enabled', False):
            return False

        try:
            current_time = get_current_utc().time()
            start_time = datetime.strptime(quiet_config['start'], '%H:%M').time()
            end_time = datetime.strptime(quiet_config['end'], '%H:%M').time()

            if start_time < end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time

        except (KeyError, ValueError) as e:
            logger.error(f"Invalid quiet hours configuration: {e}")
            return False

    @classmethod
    def _validate_preferences(cls, preferences: Dict):
        """Validate preferences structure."""
        if 'channels' in preferences:
            for channel, config in preferences['channels'].items():
                if channel not in cls.CHANNELS:
                    raise ValidationError(f"Invalid channel: {channel}")

                if 'priorities' in config:
                    for priority in config['priorities']:
                        if priority not in cls.PRIORITIES and priority != 'ALL':
                            raise ValidationError(f"Invalid priority: {priority}")

    @classmethod
    def _deep_merge(cls, base: Dict, updates: Dict):
        """Deep merge updates into base dictionary."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                cls._deep_merge(base[key], value)
            else:
                base[key] = value
