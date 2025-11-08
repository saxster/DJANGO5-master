"""
Geofence Audit Service

Handles audit trail for geofence modifications and violations.
Separated from query/validation logic for single responsibility principle.

Following .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #11: Specific exception handling
- Rule #13: Use constants instead of magic numbers
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from apps.core.constants.spatial_constants import SECONDS_IN_DAY
from apps.core.exceptions.patterns import TEMPLATE_EXCEPTIONS


logger = logging.getLogger(__name__)
error_logger = logging.getLogger("error_logger")


class GeofenceAuditService:
    """
    Service for geofence audit trail and violation tracking.

    Responsibilities:
    - Log geofence modifications
    - Log geofence violations
    - Retrieve audit history
    """

    # Cache keys
    AUDIT_KEY_TEMPLATE = "geofence_audit:{geofence_id}:{date}"
    VIOLATIONS_KEY_TEMPLATE = "geofence_violations:{date}"

    # Limits
    MAX_VIOLATIONS_PER_DAY = 1000
    MAX_VIOLATIONS_RETURNED = 100

    def log_geofence_modification(
        self,
        geofence_id: int,
        user_id: int,
        action: str,
        changes: Dict[str, Any],
        ip_address: Optional[str] = None
    ):
        """
        Log geofence modifications for audit trail.

        Args:
            geofence_id: ID of the geofence
            user_id: ID of the user making changes
            action: Type of action (CREATE, UPDATE, DELETE, ENABLE, DISABLE)
            changes: Dictionary of field changes
            ip_address: Optional IP address of user

        Example:
            >>> service = GeofenceAuditService()
            >>> service.log_geofence_modification(
            ...     geofence_id=123,
            ...     user_id=456,
            ...     action='UPDATE',
            ...     changes={'gfname': ('Old Name', 'New Name')}
            ... )
        """
        try:
            audit_entry = {
                'timestamp': datetime.now().isoformat(),
                'geofence_id': geofence_id,
                'user_id': user_id,
                'action': action,
                'changes': changes,
                'ip_address': ip_address
            }

            # Store in cache for recent access
            date_str = datetime.now().strftime('%Y%m%d')
            audit_key = self.AUDIT_KEY_TEMPLATE.format(
                geofence_id=geofence_id,
                date=date_str
            )

            cached_audits = cache.get(audit_key, [])
            cached_audits.append(audit_entry)
            cache.set(audit_key, cached_audits, SECONDS_IN_DAY)

            logger.info(
                f"Geofence audit logged: {action} on geofence {geofence_id} "
                f"by user {user_id}"
            )

        except (DatabaseError, IntegrityError) as e:
            error_logger.error(
                f"Database error logging geofence audit: {str(e)}"
            )
        except TEMPLATE_EXCEPTIONS as e:
            error_logger.error(
                f"Unexpected error logging geofence audit: {str(e)}",
                exc_info=True
            )

    def log_geofence_violation(
        self,
        people_id: int,
        geofence_id: int,
        violation_type: str,
        location: Tuple[float, float],
        additional_data: Optional[Dict] = None
    ):
        """
        Log geofence violations for monitoring and alerting.

        Args:
            people_id: ID of the person
            geofence_id: ID of the geofence
            violation_type: Type of violation (ENTRY, EXIT, BREACH)
            location: (lat, lon) tuple of violation location
            additional_data: Optional additional context data

        Example:
            >>> service = GeofenceAuditService()
            >>> service.log_geofence_violation(
            ...     people_id=789,
            ...     geofence_id=123,
            ...     violation_type='ENTRY',
            ...     location=(40.7128, -74.0060),
            ...     additional_data={'alert_sent': True}
            ... )
        """
        try:
            violation_entry = {
                'timestamp': datetime.now().isoformat(),
                'people_id': people_id,
                'geofence_id': geofence_id,
                'violation_type': violation_type,
                'location': {'lat': location[0], 'lon': location[1]},
                'additional_data': additional_data or {}
            }

            # Store in cache for recent violations
            date_str = datetime.now().strftime('%Y%m%d')
            violation_key = self.VIOLATIONS_KEY_TEMPLATE.format(date=date_str)

            cached_violations = cache.get(violation_key, [])
            cached_violations.append(violation_entry)

            # Keep only last N violations per day to prevent memory issues
            if len(cached_violations) > self.MAX_VIOLATIONS_PER_DAY:
                cached_violations = cached_violations[-self.MAX_VIOLATIONS_PER_DAY:]

            cache.set(violation_key, cached_violations, SECONDS_IN_DAY)

            logger.warning(
                f"Geofence violation logged: {violation_type} by person {people_id} "
                f"at geofence {geofence_id}"
            )

        except (DatabaseError, IntegrityError) as e:
            error_logger.error(
                f"Database error logging geofence violation: {str(e)}"
            )
        except TEMPLATE_EXCEPTIONS as e:
            error_logger.error(
                f"Unexpected error logging geofence violation: {str(e)}",
                exc_info=True
            )

    def get_recent_violations(self, days: int = 7) -> List[Dict]:
        """
        Get recent geofence violations from cache.

        Args:
            days: Number of days to look back (default: 7)

        Returns:
            List of violation entries, sorted by timestamp (newest first)

        Example:
            >>> service = GeofenceAuditService()
            >>> violations = service.get_recent_violations(days=7)
            >>> len(violations)
            42
            >>> violations[0]['violation_type']
            'ENTRY'
        """
        violations = []

        try:
            for i in range(days):
                date_key = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                violation_key = self.VIOLATIONS_KEY_TEMPLATE.format(date=date_key)
                daily_violations = cache.get(violation_key, [])
                violations.extend(daily_violations)

            # Sort by timestamp (newest first)
            violations.sort(key=lambda x: x['timestamp'], reverse=True)

            # Return only the most recent violations
            return violations[:self.MAX_VIOLATIONS_RETURNED]

        except TEMPLATE_EXCEPTIONS as e:
            error_logger.error(
                f"Error retrieving recent violations: {str(e)}",
                exc_info=True
            )
            return []

    def get_audit_history(
        self,
        geofence_id: int,
        days: int = 30
    ) -> List[Dict]:
        """
        Get audit history for a specific geofence.

        Args:
            geofence_id: Geofence ID
            days: Number of days to look back (default: 30)

        Returns:
            List of audit entries, sorted by timestamp (newest first)

        Example:
            >>> service = GeofenceAuditService()
            >>> audits = service.get_audit_history(geofence_id=123, days=30)
            >>> audits[0]['action']
            'UPDATE'
        """
        audit_entries = []

        try:
            for i in range(days):
                date_key = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                audit_key = self.AUDIT_KEY_TEMPLATE.format(
                    geofence_id=geofence_id,
                    date=date_key
                )
                daily_audits = cache.get(audit_key, [])
                audit_entries.extend(daily_audits)

            # Sort by timestamp (newest first)
            audit_entries.sort(key=lambda x: x['timestamp'], reverse=True)

            return audit_entries

        except TEMPLATE_EXCEPTIONS as e:
            error_logger.error(
                f"Error retrieving audit history for geofence {geofence_id}: {str(e)}",
                exc_info=True
            )
            return []


# Singleton instance
geofence_audit_service = GeofenceAuditService()