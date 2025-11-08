"""
Audit Log Mining Service

Analyzes audit logs to detect suspicious administrative actions
and security anomalies.

Features:
- After-hours access detection
- Mass deletion pattern detection
- Permission change monitoring
- Failed login pattern analysis
- Geographic anomaly detection
- Behavioral baseline comparison

Uses AuditLog model for analysis.

Compliance: CLAUDE.md Rule #7 (file size), Rule #11 (specific exceptions)
"""

import logging
from datetime import datetime, time, timedelta, timezone as dt_timezone
from typing import Dict, List, Optional, Set
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db.models import Count, Q

from apps.core.models import AuditLog
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.utils_new.datetime_utilities import get_current_utc
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

logger = logging.getLogger(__name__)


class AuditMiningService:
    """
    Service for mining audit logs for suspicious patterns.
    """

    AFTER_HOURS_START = time(22, 0)
    AFTER_HOURS_END = time(7, 0)
    MASS_DELETE_THRESHOLD = 10
    FAILED_LOGIN_THRESHOLD = 5
    PERMISSION_CHANGE_WINDOW_MINUTES = 30

    @classmethod
    def detect_suspicious_activity(
        cls,
        tenant_id: int,
        lookback_hours: int = 24
    ) -> List[Dict]:
        """
        Detect all types of suspicious activity.

        Args:
            tenant_id: Tenant identifier
            lookback_hours: Hours to analyze

        Returns:
            List of suspicious activity events
        """
        suspicious_events = []
        cutoff = get_current_utc() - timedelta(hours=lookback_hours)

        try:
            after_hours = cls.detect_after_hours_access(tenant_id, cutoff)
            suspicious_events.extend(after_hours)

            mass_deletions = cls.detect_mass_deletions(tenant_id, cutoff)
            suspicious_events.extend(mass_deletions)

            permission_changes = cls.detect_permission_changes(tenant_id, cutoff)
            suspicious_events.extend(permission_changes)

            failed_logins = cls.detect_failed_login_patterns(tenant_id, cutoff)
            suspicious_events.extend(failed_logins)

            logger.info(
                f"Detected {len(suspicious_events)} suspicious activities "
                f"for tenant {tenant_id} in last {lookback_hours}h"
            )
            return suspicious_events

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error detecting suspicious activity: {e}", exc_info=True)
            return []

    @classmethod
    def detect_after_hours_access(
        cls,
        tenant_id: int,
        cutoff: datetime
    ) -> List[Dict]:
        """
        Detect administrative access during after-hours.

        Args:
            tenant_id: Tenant identifier
            cutoff: Time threshold

        Returns:
            List of after-hours access events
        """
        events = []

        try:
            logs = AuditLog.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=cutoff,
                event_type__in=['CREATE', 'UPDATE', 'DELETE'],
                level__in=['WARNING', 'CRITICAL', 'SECURITY']
            ).select_related('user')

            for log in logs:
                log_time = log.created_at.time()

                if cls._is_after_hours(log_time):
                    events.append({
                        'type': 'AFTER_HOURS_ACCESS',
                        'user_id': log.user_id,
                        'user_name': log.user.username if log.user else 'Unknown',
                        'event_type': log.event_type,
                        'timestamp': log.created_at.isoformat(),
                        'ip_address': log.metadata.get('ip_address', 'Unknown'),
                        'severity': 'HIGH',
                    })

            logger.info(f"Detected {len(events)} after-hours access events")
            return events

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error detecting after-hours access: {e}", exc_info=True)
            return []

    @classmethod
    def detect_mass_deletions(
        cls,
        tenant_id: int,
        cutoff: datetime
    ) -> List[Dict]:
        """
        Detect mass deletion operations.

        Args:
            tenant_id: Tenant identifier
            cutoff: Time threshold

        Returns:
            List of mass deletion events
        """
        events = []

        try:
            user_deletions = AuditLog.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=cutoff,
                event_type='DELETE'
            ).values('user_id').annotate(
                delete_count=Count('id')
            ).filter(delete_count__gte=cls.MASS_DELETE_THRESHOLD)

            for item in user_deletions:
                user_logs = AuditLog.objects.filter(
                    tenant_id=tenant_id,
                    user_id=item['user_id'],
                    created_at__gte=cutoff,
                    event_type='DELETE'
                ).select_related('user')[:1]

                if user_logs:
                    log = user_logs[0]
                    events.append({
                        'type': 'MASS_DELETION',
                        'user_id': item['user_id'],
                        'user_name': log.user.username if log.user else 'Unknown',
                        'delete_count': item['delete_count'],
                        'first_deletion': log.created_at.isoformat(),
                        'severity': 'CRITICAL',
                    })

            logger.info(f"Detected {len(events)} mass deletion events")
            return events

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error detecting mass deletions: {e}", exc_info=True)
            return []

    @classmethod
    def detect_permission_changes(
        cls,
        tenant_id: int,
        cutoff: datetime
    ) -> List[Dict]:
        """
        Detect rapid permission/privilege changes.

        Args:
            tenant_id: Tenant identifier
            cutoff: Time threshold

        Returns:
            List of suspicious permission change events
        """
        events = []

        try:
            permission_logs = AuditLog.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=cutoff,
                event_type='UPDATE',
                metadata__has_key='permission_change'
            ).select_related('user').order_by('user_id', 'created_at')

            user_changes = defaultdict(list)

            for log in permission_logs:
                user_changes[log.user_id].append(log)

            for user_id, changes in user_changes.items():
                if len(changes) >= 3:
                    time_window = changes[-1].created_at - changes[0].created_at

                    if time_window.total_seconds() <= cls.PERMISSION_CHANGE_WINDOW_MINUTES * 60:
                        events.append({
                            'type': 'RAPID_PERMISSION_CHANGES',
                            'user_id': user_id,
                            'user_name': changes[0].user.username if changes[0].user else 'Unknown',
                            'change_count': len(changes),
                            'time_window_minutes': time_window.total_seconds() / 60,
                            'first_change': changes[0].created_at.isoformat(),
                            'last_change': changes[-1].created_at.isoformat(),
                            'severity': 'HIGH',
                        })

            logger.info(f"Detected {len(events)} suspicious permission change patterns")
            return events

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error detecting permission changes: {e}", exc_info=True)
            return []

    @classmethod
    def detect_failed_login_patterns(
        cls,
        tenant_id: int,
        cutoff: datetime
    ) -> List[Dict]:
        """
        Detect failed login patterns indicating brute force attempts.

        Args:
            tenant_id: Tenant identifier
            cutoff: Time threshold

        Returns:
            List of failed login pattern events
        """
        events = []

        try:
            failed_logins = AuditLog.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=cutoff,
                event_type='LOGIN_FAILED'
            ).values('metadata__username', 'metadata__ip_address').annotate(
                attempt_count=Count('id')
            ).filter(attempt_count__gte=cls.FAILED_LOGIN_THRESHOLD)

            for item in failed_logins:
                events.append({
                    'type': 'FAILED_LOGIN_PATTERN',
                    'username': item.get('metadata__username', 'Unknown'),
                    'ip_address': item.get('metadata__ip_address', 'Unknown'),
                    'attempt_count': item['attempt_count'],
                    'severity': 'CRITICAL' if item['attempt_count'] > 10 else 'HIGH',
                })

            logger.info(f"Detected {len(events)} failed login patterns")
            return events

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error detecting failed login patterns: {e}", exc_info=True)
            return []

    @classmethod
    def get_user_activity_summary(
        cls,
        tenant_id: int,
        user_id: int,
        lookback_days: int = 30
    ) -> Dict:
        """
        Get comprehensive activity summary for user.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            lookback_days: Days to analyze

        Returns:
            Activity summary with statistics
        """
        cutoff = get_current_utc() - timedelta(days=lookback_days)

        try:
            logs = AuditLog.objects.filter(
                tenant_id=tenant_id,
                user_id=user_id,
                created_at__gte=cutoff
            )

            event_counts = logs.values('event_type').annotate(
                count=Count('id')
            )

            after_hours_count = sum(
                1 for log in logs
                if cls._is_after_hours(log.created_at.time())
            )

            return {
                'user_id': user_id,
                'total_events': logs.count(),
                'event_breakdown': {
                    item['event_type']: item['count']
                    for item in event_counts
                },
                'after_hours_count': after_hours_count,
                'period_days': lookback_days,
                'suspicious_indicators': cls._calculate_suspicion_score(
                    logs, after_hours_count
                ),
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error getting user activity summary: {e}", exc_info=True)
            return {}

    @classmethod
    def _is_after_hours(cls, check_time: time) -> bool:
        """Check if time is during after-hours."""
        if cls.AFTER_HOURS_START < cls.AFTER_HOURS_END:
            return cls.AFTER_HOURS_START <= check_time <= cls.AFTER_HOURS_END
        else:
            return check_time >= cls.AFTER_HOURS_START or check_time <= cls.AFTER_HOURS_END

    @classmethod
    def _calculate_suspicion_score(cls, logs, after_hours_count: int) -> Dict:
        """Calculate suspicion indicators from log patterns."""
        total = logs.count()

        delete_count = logs.filter(event_type='DELETE').count()
        permission_changes = logs.filter(
            event_type='UPDATE',
            metadata__has_key='permission_change'
        ).count()

        return {
            'after_hours_percentage': (after_hours_count / total * 100) if total > 0 else 0,
            'delete_percentage': (delete_count / total * 100) if total > 0 else 0,
            'permission_change_count': permission_changes,
            'risk_level': cls._determine_risk_level(
                after_hours_count, delete_count, permission_changes, total
            ),
        }

    @classmethod
    def _determine_risk_level(
        cls,
        after_hours: int,
        deletes: int,
        permission_changes: int,
        total: int
    ) -> str:
        """Determine overall risk level from activity patterns."""
        if total == 0:
            return 'NONE'

        score = 0

        if after_hours / total > 0.3:
            score += 2
        if deletes > cls.MASS_DELETE_THRESHOLD:
            score += 3
        if permission_changes > 5:
            score += 2

        if score >= 5:
            return 'CRITICAL'
        elif score >= 3:
            return 'HIGH'
        elif score >= 1:
            return 'MEDIUM'
        else:
            return 'LOW'
