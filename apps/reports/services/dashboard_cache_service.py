"""
Dashboard caching service for Reports app.

Caches expensive dashboard metrics and aggregations.

Created: 2025-11-07
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from django.core.cache import cache
from django.db.models import Count, Avg, Sum, Q
from apps.core.utils_new.cache_utils import cache_result, invalidate_pattern

logger = logging.getLogger(__name__)


class DashboardCacheService:
    """Service for caching dashboard metrics and data."""
    
    # Cache timeouts (in seconds)
    METRICS_TIMEOUT = 300  # 5 minutes
    CHART_DATA_TIMEOUT = 600  # 10 minutes
    SUMMARY_TIMEOUT = 900  # 15 minutes
    
    @classmethod
    @cache_result(timeout=METRICS_TIMEOUT, key_prefix='dashboard_metrics')
    def get_dashboard_metrics(cls, site_id: int, date_range: tuple) -> Dict[str, Any]:
        """
        Get cached dashboard metrics for a site.
        
        Args:
            site_id: Site ID
            date_range: Tuple of (start_date, end_date)
            
        Returns:
            Dictionary of metrics
        """
        from apps.activity.models.task_model import Task
        from apps.work_order_management.models import WorkOrder
        
        start_date, end_date = date_range
        
        # Task metrics
        tasks = Task.objects.filter(site_id=site_id, created_at__range=(start_date, end_date))
        task_metrics = {
            'total_tasks': tasks.count(),
            'completed_tasks': tasks.filter(status='completed').count(),
            'pending_tasks': tasks.filter(status='pending').count(),
            'overdue_tasks': tasks.filter(
                status__in=['pending', 'in_progress'],
                due_date__lt=datetime.now()
            ).count(),
        }
        
        # Work order metrics
        work_orders = WorkOrder.objects.filter(
            site_id=site_id,
            created_at__range=(start_date, end_date)
        )
        wo_metrics = {
            'total_work_orders': work_orders.count(),
            'completed_wo': work_orders.filter(status='completed').count(),
            'avg_completion_time': work_orders.filter(
                status='completed'
            ).aggregate(
                avg_time=Avg('completion_time')
            )['avg_time'] or 0,
        }
        
        # Calculate completion rate
        total_items = task_metrics['total_tasks'] + wo_metrics['total_work_orders']
        completed_items = task_metrics['completed_tasks'] + wo_metrics['completed_wo']
        completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0
        
        return {
            **task_metrics,
            **wo_metrics,
            'completion_rate': round(completion_rate, 2),
            'date_range': date_range,
            'cached_at': datetime.now().isoformat(),
        }
    
    @classmethod
    @cache_result(timeout=CHART_DATA_TIMEOUT, key_prefix='dashboard_chart')
    def get_chart_data(cls, site_id: int, chart_type: str, days: int = 30) -> Dict[str, Any]:
        """
        Get cached chart data for dashboard visualizations.
        
        Args:
            site_id: Site ID
            chart_type: Type of chart ('tasks', 'work_orders', 'attendance')
            days: Number of days to include
            
        Returns:
            Chart data dictionary
        """
        from apps.activity.models.task_model import Task
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        if chart_type == 'tasks':
            # Daily task completion trend
            tasks = Task.objects.filter(
                site_id=site_id,
                created_at__range=(start_date, end_date)
            ).extra(
                select={'day': 'DATE(created_at)'}
            ).values('day').annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(status='completed'))
            ).order_by('day')
            
            return {
                'labels': [item['day'].strftime('%Y-%m-%d') for item in tasks],
                'total': [item['total'] for item in tasks],
                'completed': [item['completed'] for item in tasks],
                'chart_type': chart_type,
            }
        
        # Add more chart types as needed
        return {}
    
    @classmethod
    @cache_result(timeout=SUMMARY_TIMEOUT, key_prefix='site_summary')
    def get_site_summary(cls, site_id: int) -> Dict[str, Any]:
        """
        Get cached site summary statistics.
        
        Args:
            site_id: Site ID
            
        Returns:
            Summary statistics dictionary
        """
        from apps.client_onboarding.models import Site
        from apps.activity.models.task_model import Task
        from apps.peoples.models import People
        
        try:
            site = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            return {}
        
        # Get active users at site
        active_users = People.objects.filter(
            organizational__site_id=site_id,
            isverified=True
        ).count()
        
        # Get total tasks
        total_tasks = Task.objects.filter(site_id=site_id).count()
        
        return {
            'site_name': site.sitename,
            'active_users': active_users,
            'total_tasks': total_tasks,
            'site_type': getattr(site, 'site_type', 'Unknown'),
        }
    
    @classmethod
    def invalidate_site_cache(cls, site_id: int) -> int:
        """
        Invalidate all cached data for a site.
        
        Args:
            site_id: Site ID
            
        Returns:
            Number of cache entries invalidated
        """
        patterns = [
            f'dashboard_metrics_*{site_id}*',
            f'dashboard_chart_*{site_id}*',
            f'site_summary_*{site_id}*',
        ]
        
        total_deleted = 0
        for pattern in patterns:
            deleted = invalidate_pattern(pattern)
            total_deleted += deleted
        
        logger.info(f"Invalidated {total_deleted} cache entries for site {site_id}")
        return total_deleted
    
    @classmethod
    def warm_site_cache(cls, site_id: int) -> None:
        """
        Pre-warm cache for a site with common queries.
        
        Args:
            site_id: Site ID
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Warm dashboard metrics
        cls.get_dashboard_metrics(site_id, (start_date, end_date))
        
        # Warm chart data
        cls.get_chart_data(site_id, 'tasks', days=30)
        
        # Warm summary
        cls.get_site_summary(site_id)
        
        logger.info(f"Cache warmed for site {site_id}")


__all__ = ['DashboardCacheService']
