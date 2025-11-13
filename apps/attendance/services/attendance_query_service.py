"""
Attendance Query Service

Optimized query service for attendance records with caching support.

Provides high-performance queries for:
- Date range queries
- User-specific attendance records
- Dashboard summaries
- Report generation

Follows .claude/rules.md:
- Functions < 50 lines
- Specific exception handling
- Uses Redis caching
"""

import logging
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from django.db import DatabaseError
from django.core.cache import cache
from django.db.models import Q, Count, Sum, Avg

from apps.attendance.models import PeopleEventlog
from apps.core.decorators.caching import cache_query

logger = logging.getLogger(__name__)


class AttendanceQueryService:
    """Service for optimized attendance queries with caching."""

    @staticmethod
    def get_attendance_by_date_range(
        user_id: int,
        start_date: date,
        end_date: date,
        tenant_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get attendance records for a date range (with caching).

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            tenant_id: Optional tenant ID for filtering

        Returns:
            List of attendance records

        Raises:
            DatabaseError: Database errors
        """
        # Generate cache key
        cache_key = (
            f'attendance:range:{user_id}:'
            f'{start_date.isoformat()}:{end_date.isoformat()}:'
            f'tenant:{tenant_id or "all"}'
        )

        # Try cache first
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return cached_results

        logger.debug(f"Cache MISS: {cache_key}")

        # Build query
        queryset = PeopleEventlog.objects.filter(
            people_id=user_id,
            datefor__gte=start_date,
            datefor__lte=end_date
        )

        # Apply tenant filtering
        if tenant_id:
            queryset = queryset.filter(client_id=tenant_id)

        # Optimize with select_related
        queryset = queryset.select_related(
            'people',
            'shift',
            'peventtype',
            'bu',
            'client'
        ).order_by('-datefor', '-punchintime')

        # Serialize results
        results = [
            {
                'id': record.id,
                'date': record.datefor.isoformat() if record.datefor else None,
                'punch_in': record.punchintime.isoformat() if record.punchintime else None,
                'punch_out': record.punchouttime.isoformat() if record.punchouttime else None,
                'duration': record.duration,
                'event_type': record.peventtype.tacode if record.peventtype else None,
                'shift_id': record.shift_id,
            }
            for record in queryset
        ]

        # Cache for 1 hour (3600 seconds)
        cache.set(cache_key, results, 3600)
        logger.info(f"Cached attendance range query: {cache_key} (TTL: 3600s)")

        return results

    @staticmethod
    def get_attendance_summary(
        user_id: int,
        month: int,
        year: int,
        tenant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get monthly attendance summary (with caching).

        Args:
            user_id: User ID
            month: Month (1-12)
            year: Year
            tenant_id: Optional tenant ID for filtering

        Returns:
            Summary dict with total days, present days, absent days, etc.

        Raises:
            ValueError: Invalid month/year
            DatabaseError: Database errors
        """
        if not (1 <= month <= 12):
            raise ValueError(f"Invalid month: {month}. Must be 1-12.")

        # Generate cache key
        cache_key = (
            f'attendance:summary:{user_id}:{year}:{month:02d}:'
            f'tenant:{tenant_id or "all"}'
        )

        # Try cache first
        cached_summary = cache.get(cache_key)
        if cached_summary is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return cached_summary

        logger.debug(f"Cache MISS: {cache_key}")

        # Calculate date range
        from calendar import monthrange
        _, last_day = monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        # Build query
        queryset = PeopleEventlog.objects.filter(
            people_id=user_id,
            datefor__gte=start_date,
            datefor__lte=end_date
        )

        if tenant_id:
            queryset = queryset.filter(client_id=tenant_id)

        # Aggregate summary
        total_records = queryset.count()
        present_count = queryset.filter(peventtype__tacode='PRESENT').count()
        absent_count = queryset.filter(peventtype__tacode='ABSENT').count()
        halfday_count = queryset.filter(peventtype__tacode='HALFDAY').count()

        # Calculate total duration (in hours)
        total_duration = queryset.aggregate(
            total_hours=Sum('duration')
        )['total_hours'] or 0

        summary = {
            'user_id': user_id,
            'month': month,
            'year': year,
            'total_records': total_records,
            'present_days': present_count,
            'absent_days': absent_count,
            'halfday_days': halfday_count,
            'total_hours': round(total_duration, 2),
        }

        # Cache for 1 hour (3600 seconds)
        cache.set(cache_key, summary, 3600)
        logger.info(f"Cached attendance summary: {cache_key} (TTL: 3600s)")

        return summary

    @staticmethod
    def get_recent_attendance(
        user_id: int,
        days: int = 7,
        tenant_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent attendance records (with caching).

        Args:
            user_id: User ID
            days: Number of recent days (default: 7)
            tenant_id: Optional tenant ID for filtering

        Returns:
            List of recent attendance records

        Raises:
            DatabaseError: Database errors
        """
        from datetime import datetime
        from django.utils import timezone

        # Calculate date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Use date range query (which has caching)
        return AttendanceQueryService.get_attendance_by_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            tenant_id=tenant_id
        )


__all__ = ['AttendanceQueryService']
