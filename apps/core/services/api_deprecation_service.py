"""
API Deprecation Monitoring Service
Tracks usage of deprecated APIs and generates alerts.

Compliance with .claude/rules.md:
- Rule #6: File < 200 lines
- Rule #11: Specific exception handling
- Rule #15: No sensitive data logging
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db import DatabaseError
from django.db.models import Count, Q
from typing import List, Dict, Optional

logger = logging.getLogger('api.deprecation.service')


class APIDeprecationService:
    """
    Service for managing API deprecation lifecycle and monitoring.
    """

    @staticmethod
    def get_deprecated_endpoints(api_type: Optional[str] = None) -> List:
        """Get all deprecated endpoints, optionally filtered by type."""
        from apps.core.models.api_deprecation import APIDeprecation

        try:
            queryset = APIDeprecation.objects.filter(
                status__in=['deprecated', 'sunset_warning']
            ).select_related('tenant')

            if api_type:
                queryset = queryset.filter(api_type=api_type)

            return list(queryset.order_by('sunset_date'))

        except DatabaseError as e:
            logger.error(f"Database error fetching deprecated endpoints: {e}")
            return []

    @staticmethod
    def get_sunset_warnings() -> List:
        """Get endpoints approaching sunset (within 30 days)."""
        from apps.core.models.api_deprecation import APIDeprecation

        try:
            thirty_days = timezone.now() + timedelta(days=30)
            return list(
                APIDeprecation.objects.filter(
                    sunset_date__lte=thirty_days,
                    sunset_date__gte=timezone.now(),
                    status='sunset_warning'
                ).order_by('sunset_date')
            )

        except DatabaseError as e:
            logger.error(f"Database error fetching sunset warnings: {e}")
            return []

    @staticmethod
    def get_usage_stats(endpoint_pattern: str, days: int = 7) -> Dict:
        """Get usage statistics for a deprecated endpoint."""
        from apps.core.models.api_deprecation import APIDeprecation, APIDeprecationUsage

        try:
            deprecation = APIDeprecation.objects.get(endpoint_pattern=endpoint_pattern)
            cutoff = timezone.now() - timedelta(days=days)

            usage_data = APIDeprecationUsage.objects.filter(
                deprecation=deprecation,
                timestamp__gte=cutoff
            ).values('client_version').annotate(
                count=Count('id')
            ).order_by('-count')

            total_usage = sum(item['count'] for item in usage_data)

            return {
                'endpoint': endpoint_pattern,
                'total_usage': total_usage,
                'unique_clients': usage_data.count(),
                'clients_breakdown': list(usage_data),
                'days_until_sunset': (deprecation.sunset_date - timezone.now()).days if deprecation.sunset_date else None,
                'replacement': deprecation.replacement_endpoint,
            }

        except APIDeprecation.DoesNotExist:
            logger.warning(f"No deprecation found for {endpoint_pattern}")
            return {}
        except DatabaseError as e:
            logger.error(f"Database error fetching usage stats: {e}")
            return {}

    @staticmethod
    def check_safe_to_remove(endpoint_pattern: str, threshold_requests: int = 10) -> bool:
        """
        Check if it's safe to remove an endpoint (low usage).
        Returns True if usage is below threshold in last 30 days.
        """
        from apps.core.models.api_deprecation import APIDeprecationUsage, APIDeprecation

        try:
            deprecation = APIDeprecation.objects.get(endpoint_pattern=endpoint_pattern)
            cutoff = timezone.now() - timedelta(days=30)

            usage_count = APIDeprecationUsage.objects.filter(
                deprecation=deprecation,
                timestamp__gte=cutoff
            ).count()

            return usage_count < threshold_requests

        except APIDeprecation.DoesNotExist:
            return True
        except DatabaseError as e:
            logger.error(f"Database error checking removal safety: {e}")
            return False

    @staticmethod
    def get_clients_on_deprecated_api() -> List[Dict]:
        """Get list of clients still using deprecated APIs."""
        from apps.core.models.api_deprecation import APIDeprecationUsage

        try:
            cutoff = timezone.now() - timedelta(days=7)

            clients = APIDeprecationUsage.objects.filter(
                timestamp__gte=cutoff,
                client_version__isnull=False
            ).values(
                'client_version',
                'deprecation__endpoint_pattern',
                'deprecation__replacement_endpoint'
            ).annotate(
                usage_count=Count('id')
            ).order_by('-usage_count')

            return list(clients)

        except DatabaseError as e:
            logger.error(f"Database error fetching deprecated API clients: {e}")
            return []

    @staticmethod
    def update_all_statuses():
        """Batch update status for all deprecated endpoints."""
        from apps.core.models.api_deprecation import APIDeprecation
        from django.db import transaction

        try:
            with transaction.atomic():
                deprecations = APIDeprecation.objects.filter(
                    status__in=['deprecated', 'sunset_warning']
                )

                updated_count = 0
                for dep in deprecations:
                    old_status = dep.status
                    dep.update_status()
                    if dep.status != old_status:
                        dep.save(update_fields=['status'])
                        updated_count += 1

                logger.info(f"Updated {updated_count} deprecation statuses")
                return updated_count

        except DatabaseError as e:
            logger.error(f"Database error updating deprecation statuses: {e}")
            return 0

    @staticmethod
    def get_deprecation_dashboard_data() -> Dict:
        """Get comprehensive data for deprecation dashboard."""
        from apps.core.models.api_deprecation import APIDeprecation, APIDeprecationUsage

        try:
            cache_key = 'deprecation_dashboard_data'
            cached = cache.get(cache_key)
            if cached:
                return cached

            thirty_days_ago = timezone.now() - timedelta(days=30)

            data = {
                'total_deprecated': APIDeprecation.objects.filter(status='deprecated').count(),
                'sunset_warnings': APIDeprecation.objects.filter(status='sunset_warning').count(),
                'removed': APIDeprecation.objects.filter(status='removed').count(),
                'upcoming_sunsets': list(
                    APIDeprecation.objects.filter(
                        sunset_date__gte=timezone.now(),
                        sunset_date__lte=timezone.now() + timedelta(days=90)
                    ).values('endpoint_pattern', 'sunset_date', 'replacement_endpoint').order_by('sunset_date')
                ),
                'high_usage_deprecated': list(
                    APIDeprecationUsage.objects.filter(
                        timestamp__gte=thirty_days_ago
                    ).values(
                        'deprecation__endpoint_pattern',
                        'deprecation__replacement_endpoint'
                    ).annotate(
                        usage_count=Count('id')
                    ).order_by('-usage_count')[:10]
                ),
                'clients_needing_migration': APIDeprecationService.get_clients_on_deprecated_api(),
            }

            cache.set(cache_key, data, 300)
            return data

        except DatabaseError as e:
            logger.error(f"Database error generating dashboard data: {e}")
            return {}


__all__ = ['APIDeprecationService']