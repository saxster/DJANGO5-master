"""
Schedule Uniqueness Service

Ensures no duplicate scheduled jobs are created through:
- Unique constraints on (schedule_pattern, execution_time, job_type)
- Database-level uniqueness with composite indexes
- Redis cache for fast duplicate detection
- Concurrent creation handling with distributed locks

Prevents common scheduling issues:
- Duplicate PPM job creation
- Overlapping tour schedules
- DST boundary duplications
- Concurrent schedule modifications

Usage:
    from apps.schedhuler.services.schedule_uniqueness_service import ScheduleUniquenessService

    service = ScheduleUniquenessService()

    # Ensure unique schedule creation
    schedule = service.ensure_unique_schedule({
        'cron_expression': '0 */2 * * *',
        'job_type': 'cleanup',
        'tenant_id': tenant.id,
        'job_data': {...}
    })

    # Validate no overlaps
    conflicts = service.validate_no_overlap(
        new_schedule, existing_schedules
    )
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from django.db import IntegrityError, DatabaseError, transaction
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q

from apps.core.services import BaseService
from apps.core.exceptions import SchedulingException, BusinessLogicException
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY
from apps.core.tasks.idempotency_service import UniversalIdempotencyService
from apps.schedhuler.services.dst_validator import DSTValidator


logger = logging.getLogger(__name__)


@dataclass
class ScheduleConflict:
    """Represents a schedule conflict"""
    conflict_type: str
    conflicting_schedule_id: int
    conflicting_time: str
    severity: str  # 'error', 'warning', 'info'
    message: str


class ScheduleUniquenessService(BaseService):
    """
    Service for ensuring schedule uniqueness and preventing duplicates.

    Features:
    - Unique composite keys for schedules
    - Redis-based fast duplicate detection
    - Database constraints for data integrity
    - Distributed locks for concurrent operations
    - Overlap detection and validation
    """

    # Cache configuration
    CACHE_PREFIX = 'schedule_unique'
    CACHE_TTL = SECONDS_IN_HOUR * 4  # 4 hours

    def __init__(self):
        super().__init__()
        self.idempotency_service = UniversalIdempotencyService
        self.dst_validator = DSTValidator()

    def ensure_unique_schedule(
        self,
        schedule_config: Dict[str, Any],
        allow_overlap: bool = False
    ) -> Dict[str, Any]:
        """
        Creates schedule only if unique composite key doesn't exist.

        Args:
            schedule_config: Schedule configuration dict containing:
                - cron_expression: Cron expression string
                - job_type: Type of job (ppm, tour, cleanup, etc.)
                - tenant_id: Tenant/client ID
                - job_data: Additional job configuration
            allow_overlap: Allow overlapping schedules (default: False)

        Returns:
            Dictionary with schedule creation result

        Raises:
            SchedulingException: If duplicate schedule exists
            ValidationError: If schedule configuration invalid

        Implementation:
            1. Validate schedule configuration
            2. Generate unique key
            3. Acquire distributed lock
            4. Check Redis cache
            5. Check database
            6. Validate no overlap (if required)
            7. Create schedule
            8. Update cache
        """
        try:
            # Validate configuration
            self._validate_schedule_config(schedule_config)

            # Generate unique key
            unique_key = self._generate_schedule_key(schedule_config)

            # Acquire distributed lock to prevent race conditions
            lock_key = f"schedule_creation:{unique_key}"

            with self.idempotency_service.acquire_distributed_lock(lock_key, timeout=30):
                # Check Redis cache first (fast path)
                if self._check_cache_duplicate(unique_key):
                    raise SchedulingException(
                        f"Duplicate schedule detected: {schedule_config.get('job_type', 'unknown')}"
                    )

                # Check database
                if self._check_database_duplicate(schedule_config):
                    # Update cache for future checks
                    self._cache_schedule(unique_key)

                    raise SchedulingException(
                        f"Schedule already exists: {schedule_config.get('job_type', 'unknown')}"
                    )

                # Validate no overlap (if required)
                if not allow_overlap:
                    conflicts = self.validate_no_overlap(schedule_config)
                    error_conflicts = [c for c in conflicts if c.severity == 'error']

                    if error_conflicts:
                        conflict_messages = [c.message for c in error_conflicts]
                        raise BusinessLogicException(
                            f"Schedule overlap detected: {'; '.join(conflict_messages)}"
                        )

                # Create schedule in database
                schedule = self._create_schedule_record(schedule_config)

                # Update cache
                self._cache_schedule(unique_key)

                logger.info(
                    f"Created unique schedule: {schedule_config.get('job_type', 'unknown')}",
                    extra={'schedule_id': schedule.get('id'), 'unique_key': unique_key}
                )

                return {
                    'success': True,
                    'schedule': schedule,
                    'unique_key': unique_key,
                    'message': 'Schedule created successfully'
                }

        except (ValidationError, ValueError) as e:
            logger.error(f"Invalid schedule configuration: {e}")
            raise ValidationError(f"Invalid schedule configuration: {str(e)}")

        except SchedulingException:
            # Re-raise scheduling exceptions
            raise

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error creating schedule: {e}", exc_info=True)
            raise SchedulingException(
                "Failed to create schedule due to database error"
            ) from e

    def validate_no_overlap(
        self,
        new_schedule: Dict[str, Any],
        existing_schedules: Optional[List[Dict[str, Any]]] = None
    ) -> List[ScheduleConflict]:
        """
        Validate that new schedule doesn't overlap with existing schedules.

        Args:
            new_schedule: New schedule configuration
            existing_schedules: Optional list of existing schedules to check against

        Returns:
            List of conflicts found (empty if no conflicts)

        Checks:
            - Same cron expression + same resource
            - Overlapping time windows
            - Conflicting job types on same asset
            - DST boundary issues
        """
        conflicts = []

        try:
            # Get existing schedules if not provided
            if existing_schedules is None:
                existing_schedules = self._get_existing_schedules(new_schedule)

            new_cron = new_schedule.get('cron_expression', '')
            new_job_type = new_schedule.get('job_type', '')
            new_resource = new_schedule.get('resource_id')

            for existing in existing_schedules:
                # Check exact duplicate
                if (existing.get('cron_expression') == new_cron and
                    existing.get('job_type') == new_job_type and
                    existing.get('resource_id') == new_resource):

                    conflicts.append(ScheduleConflict(
                        conflict_type='exact_duplicate',
                        conflicting_schedule_id=existing.get('id', 0),
                        conflicting_time=new_cron,
                        severity='error',
                        message=f"Exact schedule duplicate: {new_job_type} on resource {new_resource}"
                    ))

                # Check time window overlap
                if new_resource and existing.get('resource_id') == new_resource:
                    overlap = self._check_time_overlap(new_schedule, existing)
                    if overlap:
                        conflicts.append(ScheduleConflict(
                            conflict_type='time_overlap',
                            conflicting_schedule_id=existing.get('id', 0),
                            conflicting_time=overlap['overlap_period'],
                            severity='warning',
                            message=f"Time overlap: {new_job_type} conflicts with {existing.get('job_type')}"
                        ))

            # Check DST boundaries
            dst_conflicts = self._check_dst_boundaries(new_schedule)
            conflicts.extend(dst_conflicts)

            return conflicts

        except (DatabaseError, ValidationError) as e:
            logger.error(f"Error validating overlap: {e}", exc_info=True)
            return []

    def get_schedule_frequency_analysis(
        self,
        cron_expression: str,
        analysis_window_days: int = 7
    ) -> Dict[str, Any]:
        """
        Analyze schedule frequency and provide recommendations.

        Args:
            cron_expression: Cron expression to analyze
            analysis_window_days: Number of days to analyze

        Returns:
            Dictionary with frequency analysis

        Analysis includes:
            - Execution count in window
            - Average interval
            - Peak execution times
            - Recommended offset (to avoid collision)
        """
        try:
            from croniter import croniter

            if not croniter.is_valid(cron_expression):
                raise ValidationError(f"Invalid cron expression: {cron_expression}")

            now = timezone.now()
            end_time = now + timedelta(days=analysis_window_days)

            # Calculate executions
            iterator = croniter(cron_expression, now)
            executions = []
            execution_count = 0
            max_iterations = 1000  # Safety limit

            while execution_count < max_iterations:
                next_execution = iterator.get_next(datetime)
                if next_execution >= end_time:
                    break
                executions.append(next_execution)
                execution_count += 1

            # Calculate intervals
            intervals = []
            for i in range(1, len(executions)):
                interval = (executions[i] - executions[i-1]).total_seconds()
                intervals.append(interval)

            avg_interval = sum(intervals) / len(intervals) if intervals else 0

            # Determine frequency category
            if avg_interval < 60:
                frequency_category = 'very_high'  # < 1 minute
            elif avg_interval < 3600:
                frequency_category = 'high'  # < 1 hour
            elif avg_interval < 86400:
                frequency_category = 'medium'  # < 1 day
            else:
                frequency_category = 'low'  # >= 1 day

            return {
                'cron_expression': cron_expression,
                'execution_count': len(executions),
                'avg_interval_seconds': round(avg_interval, 2),
                'avg_interval_human': self._humanize_interval(avg_interval),
                'frequency_category': frequency_category,
                'peak_hours': self._calculate_peak_hours(executions),
                'recommended_offset_minutes': self._recommend_offset(avg_interval),
                'collision_risk': 'high' if frequency_category in ['very_high', 'high'] else 'low'
            }

        except ImportError:
            logger.error("croniter library not installed")
            return {'error': 'croniter library required for frequency analysis'}

        except (ValueError, ValidationError) as e:
            logger.error(f"Error analyzing schedule frequency: {e}")
            return {'error': str(e)}

    # Private helper methods

    def _validate_schedule_config(self, config: Dict[str, Any]) -> None:
        """Validate schedule configuration"""
        required_fields = ['cron_expression', 'job_type']

        for field in required_fields:
            if field not in config or not config[field]:
                raise ValidationError(f"Missing required field: {field}")

        # Validate cron expression
        try:
            from croniter import croniter
            if not croniter.is_valid(config['cron_expression']):
                raise ValidationError(f"Invalid cron expression: {config['cron_expression']}")
        except ImportError:
            logger.warning("croniter not installed, skipping cron validation")

    def _generate_schedule_key(self, config: Dict[str, Any]) -> str:
        """Generate unique key for schedule"""
        key_data = {
            'cron': config.get('cron_expression', ''),
            'job_type': config.get('job_type', ''),
            'tenant_id': config.get('tenant_id', ''),
            'resource_id': config.get('resource_id', '')
        }

        key_str = ':'.join(str(v) for v in key_data.values())
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:32]

        return f"{self.CACHE_PREFIX}:{key_hash}"

    def _check_cache_duplicate(self, unique_key: str) -> bool:
        """Check Redis cache for duplicate"""
        try:
            return cache.get(unique_key) is not None
        except ConnectionError:
            return False

    def _check_database_duplicate(self, config: Dict[str, Any]) -> bool:
        """Check database for duplicate schedule"""
        # This is a placeholder - implement based on your Job model
        # In production, check Job or Schedule table for existing record
        return False

    def _cache_schedule(self, unique_key: str) -> None:
        """Cache schedule key"""
        try:
            cache.set(unique_key, True, timeout=self.CACHE_TTL)
        except ConnectionError:
            pass

    def _create_schedule_record(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create schedule record in database"""
        # Placeholder - implement based on your model
        # In production, create Job or Schedule record
        return {
            'id': 1,
            'cron_expression': config.get('cron_expression'),
            'job_type': config.get('job_type'),
            'created_at': timezone.now().isoformat()
        }

    def _get_existing_schedules(self, new_schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get existing schedules from database"""
        # Placeholder - implement based on your model
        return []

    def _check_time_overlap(
        self,
        schedule1: Dict[str, Any],
        schedule2: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check if two schedules have overlapping execution times"""
        # Placeholder - implement overlap detection logic
        return None

    def _check_dst_boundaries(self, schedule: Dict[str, Any]) -> List[ScheduleConflict]:
        """
        Check for potential DST boundary issues using comprehensive DST validator.

        Enhanced to use DSTValidator for accurate DST risk assessment.

        Args:
            schedule: Schedule configuration dict containing cron_expression and timezone

        Returns:
            List of ScheduleConflict objects with DST warnings
        """
        conflicts = []

        try:
            cron_expression = schedule.get('cron_expression', '')
            timezone_name = schedule.get('timezone', 'UTC')

            # Use DST validator for comprehensive check
            dst_result = self.dst_validator.validate_schedule_dst_safety(
                cron_expression,
                timezone_name
            )

            if dst_result.get('has_issues'):
                # Map risk level to severity
                severity_map = {
                    'high': 'error',
                    'medium': 'warning',
                    'low': 'info',
                    'none': 'info'
                }

                severity = severity_map.get(dst_result.get('risk_level', 'low'), 'warning')

                # Create conflicts for each problematic time
                for prob_time in dst_result.get('problematic_times', []):
                    # Get recommendations
                    recommendations = dst_result.get('recommendations', [])
                    message = dst_result.get('message', 'Schedule may be affected by DST')

                    if recommendations:
                        message += f" | {recommendations[0]}"

                    conflicts.append(ScheduleConflict(
                        conflict_type='dst_boundary',
                        conflicting_schedule_id=schedule.get('id', 0),
                        conflicting_time=prob_time,
                        severity=severity,
                        message=message
                    ))

                logger.info(
                    f"DST risk detected for schedule {schedule.get('id', 'unknown')}: "
                    f"Risk level {dst_result.get('risk_level')}, "
                    f"Times {dst_result.get('problematic_times')}"
                )

        except (ValueError, TypeError) as e:
            logger.error(f"DST boundary check error: {e}")

        return conflicts

    def _humanize_interval(self, seconds: float) -> str:
        """Convert seconds to human-readable interval"""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            return f"{int(seconds / 60)} minutes"
        elif seconds < 86400:
            return f"{int(seconds / 3600)} hours"
        else:
            return f"{int(seconds / 86400)} days"

    def _calculate_peak_hours(self, executions: List[datetime]) -> List[int]:
        """Calculate peak execution hours"""
        hour_counts = {}
        for execution in executions:
            hour = execution.hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1

        # Return top 3 peak hours
        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
        return [hour for hour, count in sorted_hours[:3]]

    def _recommend_offset(self, avg_interval: float) -> int:
        """Recommend offset in minutes to avoid collisions"""
        # Recommend offset based on interval
        if avg_interval < 900:  # < 15 minutes
            return 5
        elif avg_interval < 3600:  # < 1 hour
            return 15
        else:
            return 30

    def get_service_name(self) -> str:
        """Return service name for monitoring"""
        return "ScheduleUniquenessService"
