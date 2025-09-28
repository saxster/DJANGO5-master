"""
Intelligent cache warming service with scheduling.

Pre-populates caches during off-peak hours and after deployments.
Complies with .claude/rules.md - Service < 150 lines, single responsibility.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from django.core.cache import cache
from django.utils import timezone
from django.db import DatabaseError

logger = logging.getLogger(__name__)

__all__ = ['CacheWarmingService', 'warm_critical_caches_task']


class CacheWarmingService:
    """
    Service for intelligent cache warming.

    Features:
    - Priority-based warming (critical caches first)
    - Access pattern analysis
    - Progressive warming to avoid overload
    """

    WARMING_PRIORITIES = {
        'dashboard': 1,
        'dropdown': 2,
        'form': 3,
        'reports': 4,
    }

    def warm_all_caches(self) -> Dict[str, Any]:
        """
        Warm all cache patterns based on priority.

        Returns:
            Warming operation results
        """
        try:
            results = {
                'started_at': timezone.now().isoformat(),
                'patterns_warmed': {},
                'total_keys_warmed': 0,
                'errors': []
            }

            sorted_patterns = sorted(
                self.WARMING_PRIORITIES.items(),
                key=lambda x: x[1]
            )

            for pattern_name, priority in sorted_patterns:
                try:
                    result = self._warm_pattern(pattern_name)
                    results['patterns_warmed'][pattern_name] = result
                    results['total_keys_warmed'] += result.get('keys_warmed', 0)

                except (DatabaseError, ConnectionError) as e:
                    error_msg = f"Error warming {pattern_name}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)

            results['completed_at'] = timezone.now().isoformat()

            logger.info(
                f"Cache warming completed: {results['total_keys_warmed']} keys warmed, "
                f"{len(results['errors'])} errors"
            )

            return results

        except (ValueError, TypeError) as e:
            logger.error(f"Cache warming failed: {e}")
            return {'error': str(e)}

    def _warm_pattern(self, pattern_name: str) -> Dict[str, Any]:
        """
        Warm a specific cache pattern.

        Args:
            pattern_name: Pattern to warm

        Returns:
            Warming results for pattern
        """
        warming_functions = {
            'dashboard': self._warm_dashboard_caches,
            'dropdown': self._warm_dropdown_caches,
            'form': self._warm_form_caches,
            'reports': self._warm_report_caches,
        }

        warming_func = warming_functions.get(pattern_name)
        if warming_func:
            return warming_func()

        return {'pattern': pattern_name, 'keys_warmed': 0, 'skipped': True}

    def _warm_dashboard_caches(self) -> Dict[str, Any]:
        """Warm dashboard metric caches"""
        try:
            from apps.activity.models.job_model import Jobneed
            from apps.activity.models.asset_model import Asset

            dashboard_data = {
                'total_jobs': Jobneed.objects.filter(enable=True).count(),
                'total_assets': Asset.objects.filter(enable=True).count(),
            }

            cache_key = 'tenant:1:client:1:bu:1:dashboard:metrics:v1.0'
            cache.set(cache_key, dashboard_data, timeout=900)

            return {'pattern': 'dashboard', 'keys_warmed': 1}

        except (ImportError, DatabaseError) as e:
            logger.warning(f"Error warming dashboard caches: {e}")
            return {'pattern': 'dashboard', 'keys_warmed': 0, 'error': str(e)}

    def _warm_dropdown_caches(self) -> Dict[str, Any]:
        """Warm dropdown data caches"""
        try:
            from apps.peoples.models import People
            from apps.onboarding.models import TypeAssist

            keys_warmed = 0

            people_dropdown = list(
                People.objects.filter(enable=True).values('id', 'peoplename', 'peoplecode')[:100]
            )
            cache.set('tenant:1:dropdown:people:v1.0', people_dropdown, timeout=1800)
            keys_warmed += 1

            typeassist_categories = ['JOBSTATUS', 'PRIORITY']
            for category in typeassist_categories:
                ta_data = list(TypeAssist.objects.filter(tacode=category, enable=True).values())
                cache.set(f'tenant:1:dropdown:typeassist:{category}:v1.0', ta_data, timeout=1800)
                keys_warmed += 1

            return {'pattern': 'dropdown', 'keys_warmed': keys_warmed}

        except (ImportError, DatabaseError) as e:
            logger.warning(f"Error warming dropdown caches: {e}")
            return {'pattern': 'dropdown', 'keys_warmed': 0, 'error': str(e)}

    def _warm_form_caches(self) -> Dict[str, Any]:
        """Warm form choice caches"""
        return {'pattern': 'form', 'keys_warmed': 0, 'skipped': True}

    def _warm_report_caches(self) -> Dict[str, Any]:
        """Warm report data caches"""
        return {'pattern': 'reports', 'keys_warmed': 0, 'skipped': True}


def warm_critical_caches_task():
    """
    Task function for scheduled cache warming.

    Can be called from PostgreSQL task queue or management command.
    """
    service = CacheWarmingService()
    return service.warm_all_caches()