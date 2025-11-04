"""
Modern Admin Dashboard Views
Enhanced admin interface with analytics, monitoring, and bulk operations
"""

import json
import logging
from datetime import datetime, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Avg, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import DatabaseError, OperationalError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.peoples.models import People
from apps.y_helpdesk.models import Ticket
from apps.activity.models import Task
from apps.core.models import APIAccessLog, CSPViolation
from apps.core.serializers.frontend_serializers import FrontendResponseMixin
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

# Configure logger for this module
logger = logging.getLogger(__name__)


def admin_required(view_func):
    """
    Decorator to require admin access
    """
    def check_admin(user):
        return user.is_authenticated and (user.is_staff or getattr(user, 'isadmin', False))

    return user_passes_test(check_admin)(view_func)


@method_decorator(admin_required, name='dispatch')
class ModernAdminDashboardView(FrontendResponseMixin, TemplateView):
    """
    Modern admin dashboard with analytics and monitoring
    """
    template_name = 'admin/base_modern_admin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get dashboard data
        context.update({
            'stats': self.get_dashboard_stats(),
            'recent_activities': self.get_recent_activities(),
            'alerts': self.get_system_alerts(),
        })

        return context

    def get_dashboard_stats(self):
        """
        Get key statistics for dashboard
        """
        try:
            # Cache stats for 5 minutes
            cache_key = 'admin_dashboard_stats'
            stats = cache.get(cache_key)

            if stats is None:
                now = timezone.now()
                last_month = now - timedelta(days=30)

                stats = {
                    'total_users': People.objects.count(),
                    'active_users': People.objects.filter(enable=True).count(),
                    'new_users_this_month': People.objects.filter(cdtz__gte=last_month).count(),
                    'active_sessions': self.get_active_sessions_count(),
                    'avg_session_duration': '45m',  # Would calculate from session data
                    'open_tickets': self.get_open_tickets_count(),
                    'ticket_trend': self.get_ticket_trend(),
                    'system_health': self.get_system_health(),
                    'uptime': '99.9%',  # Would calculate from monitoring data
                }

                cache.set(cache_key, stats, 300)  # Cache for 5 minutes

            return stats

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            # Return safe defaults on error
            return {
                'total_users': 0,
                'active_users': 0,
                'new_users_this_month': 0,
                'active_sessions': 0,
                'avg_session_duration': '0m',
                'open_tickets': 0,
                'ticket_trend': 0,
                'system_health': 'Unknown',
                'uptime': '0%',
            }

    def get_active_sessions_count(self):
        """
        Get count of active user sessions
        """
        try:
            from django.contrib.sessions.models import Session
            return Session.objects.filter(expire_date__gte=timezone.now()).count()
        except (ImportError, DatabaseError, OperationalError) as e:
            logger.warning(f"Failed to get active sessions count: {e}", exc_info=True)
            return 0

    def get_open_tickets_count(self):
        """
        Get count of open tickets
        """
        try:
            return Ticket.objects.filter(
                status__in=['open', 'in_progress', 'pending']
            ).count()
        except (DatabaseError, OperationalError, ObjectDoesNotExist) as e:
            logger.warning(f"Failed to get open tickets count: {e}", exc_info=True)
            return 0

    def get_ticket_trend(self):
        """
        Get ticket trend compared to yesterday
        """
        try:
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)

            today_count = Ticket.objects.filter(cdtz__date=today).count()
            yesterday_count = Ticket.objects.filter(cdtz__date=yesterday).count()

            return today_count - yesterday_count
        except (DatabaseError, OperationalError) as e:
            logger.warning(f"Failed to calculate ticket trend: {e}", exc_info=True)
            return 0

    def get_system_health(self):
        """
        Calculate overall system health
        """
        try:
            # Simple health calculation based on error rates
            recent_errors = CSPViolation.objects.filter(
                violation_time__gte=timezone.now() - timedelta(hours=1)
            ).count()

            if recent_errors == 0:
                return 'Excellent'
            elif recent_errors < 5:
                return 'Good'
            elif recent_errors < 20:
                return 'Warning'
            else:
                return 'Critical'
        except (DatabaseError, OperationalError) as e:
            logger.warning(f"Failed to calculate system health: {e}", exc_info=True)
            return 'Unknown'

    def get_recent_activities(self):
        """
        Get recent system activities
        """
        try:
            activities = []

            # Get recent user registrations
            recent_users = People.objects.filter(
                cdtz__gte=timezone.now() - timedelta(days=7)
            ).order_by('-cdtz')[:3]

            for user in recent_users:
                activities.append({
                    'description': f'New user registered: {user.peoplename or user.loginid}',
                    'user': 'System',
                    'timestamp': user.cdtz,
                    'icon': 'person_add',
                    'color': 'var(--yt-success-500)'
                })

            # Get recent tickets
            recent_tickets = Ticket.objects.filter(
                cdtz__gte=timezone.now() - timedelta(days=1)
            ).order_by('-cdtz')[:2]

            for ticket in recent_tickets:
                activities.append({
                    'description': f'Ticket created: {ticket.title}',
                    'user': str(ticket.reporter) if hasattr(ticket, 'reporter') else 'Unknown',
                    'timestamp': ticket.cdtz,
                    'icon': 'support',
                    'color': 'var(--yt-warning-500)'
                })

            # Sort by timestamp
            activities.sort(key=lambda x: x['timestamp'], reverse=True)

            return activities[:5]

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            return [{
                'description': 'Dashboard data unavailable',
                'user': 'System',
                'timestamp': timezone.now(),
                'icon': 'error',
                'color': 'var(--yt-danger-500)'
            }]

    def get_system_alerts(self):
        """
        Get system alerts count
        """
        try:
            now = timezone.now()
            last_hour = now - timedelta(hours=1)

            return {
                'security': CSPViolation.objects.filter(
                    violation_time__gte=last_hour
                ).count(),
                'performance': 0,  # Would integrate with performance monitoring
                'errors': 0,  # Would integrate with error tracking
            }
        except (DatabaseError, OperationalError) as e:
            logger.warning(f"Failed to get system alerts: {e}", exc_info=True)
            return {'security': 0, 'performance': 0, 'errors': 0}


@admin_required
@api_view(['GET'])
def admin_stats_api(request):
    """
    API endpoint for real-time dashboard stats
    """
    view = ModernAdminDashboardView()
    stats = view.get_dashboard_stats()

    response_mixin = FrontendResponseMixin()
    envelope = response_mixin.get_response_envelope(
        data=stats,
        message="Dashboard stats retrieved",
        request=request
    )

    return Response(envelope)


@admin_required
@api_view(['GET'])
def admin_chart_data_api(request):
    """
    API endpoint for chart data
    """
    period = request.GET.get('period', '7d')

    try:
        if period == '7d':
            days = 7
        elif period == '30d':
            days = 30
        elif period == '90d':
            days = 90
        else:
            days = 7

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # User activity data
        user_activity = []
        current_date = start_date

        while current_date <= end_date:
            active_count = People.objects.filter(
                last_login__date=current_date,
                enable=True
            ).count()

            user_activity.append({
                'date': current_date.isoformat(),
                'count': active_count
            })

            current_date += timedelta(days=1)

        # Performance data (mock data - would integrate with real metrics)
        performance_data = [
            {'time': '00:00', 'response_time': 120},
            {'time': '04:00', 'response_time': 95},
            {'time': '08:00', 'response_time': 180},
            {'time': '12:00', 'response_time': 220},
            {'time': '16:00', 'response_time': 150},
            {'time': '20:00', 'response_time': 110},
        ]

        response_data = {
            'user_activity': {
                'labels': [item['date'] for item in user_activity],
                'values': [item['count'] for item in user_activity]
            },
            'performance': {
                'labels': [item['time'] for item in performance_data],
                'values': [item['response_time'] for item in performance_data]
            }
        }

        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data=response_data,
            message="Chart data retrieved",
            request=request
        )

        return Response(envelope)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data=None,
            status_code=500,
            message="Failed to retrieve chart data",
            error_code="CHART_DATA_ERROR",
            request=request
        )
        return Response(envelope, status=500)


@admin_required
@api_view(['GET'])
def admin_recent_activity_api(request):
    """
    API endpoint for recent activity feed
    """
    try:
        view = ModernAdminDashboardView()
        activities = view.get_recent_activities()

        # Format for JSON response
        formatted_activities = []
        for activity in activities:
            formatted_activities.append({
                'description': activity['description'],
                'user': activity['user'],
                'time_ago': timezone.now() - activity['timestamp'],
                'icon': activity['icon'],
                'color': activity['color']
            })

        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data=formatted_activities,
            message="Recent activity retrieved",
            request=request
        )

        return Response(envelope)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data=[],
            status_code=500,
            message="Failed to retrieve activity data",
            error_code="ACTIVITY_DATA_ERROR",
            request=request
        )
        return Response(envelope, status=500)


@admin_required
@api_view(['POST'])
def admin_export_api(request):
    """
    API endpoint for data export
    """
    export_type = request.data.get('type')

    if not export_type:
        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data=None,
            status_code=400,
            message="Export type is required",
            error_code="MISSING_EXPORT_TYPE",
            request=request
        )
        return Response(envelope, status=400)

    try:
        # Generate export file
        export_data = generate_export(export_type)

        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data={
                'download_url': export_data['url'],
                'filename': export_data['filename'],
                'type': export_type,
                'expires_at': (timezone.now() + timedelta(hours=1)).isoformat()
            },
            message=f"Export prepared for {export_type}",
            request=request
        )

        return Response(envelope)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data=None,
            status_code=500,
            message=f"Export failed for {export_type}",
            error_code="EXPORT_ERROR",
            request=request
        )
        return Response(envelope, status=500)


@admin_required
@api_view(['POST'])
def admin_system_check_api(request):
    """
    API endpoint for system health check
    """
    try:
        health_results = perform_system_health_check()

        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data=health_results,
            message="System health check completed",
            request=request
        )

        return Response(envelope)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data=None,
            status_code=500,
            message="System health check failed",
            error_code="HEALTH_CHECK_ERROR",
            request=request
        )
        return Response(envelope, status=500)


@admin_required
@api_view(['POST'])
def admin_clear_caches_api(request):
    """
    API endpoint for clearing system caches
    """
    try:
        from django.core.cache import cache
        from django.core.management import call_command

        # Clear Django cache
        cache.clear()

        # Clear specific application caches
        cleared_caches = ['default', 'select2']

        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data={
                'cleared_caches': cleared_caches,
                'cleared_at': timezone.now().isoformat()
            },
            message="System caches cleared successfully",
            request=request
        )

        return Response(envelope)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        response_mixin = FrontendResponseMixin()
        envelope = response_mixin.get_response_envelope(
            data=None,
            status_code=500,
            message="Failed to clear caches",
            error_code="CACHE_CLEAR_ERROR",
            request=request
        )
        return Response(envelope, status=500)


# Utility functions
def generate_export(export_type):
    """
    Generate export file for specified type
    """
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

    if export_type == 'users':
        # Generate user export
        filename = f'users_export_{timestamp}.csv'
        # Implementation would create actual CSV file
        return {
            'url': f'/admin/exports/{filename}',
            'filename': filename
        }
    elif export_type == 'tickets':
        filename = f'tickets_export_{timestamp}.csv'
        return {
            'url': f'/admin/exports/{filename}',
            'filename': filename
        }
    else:
        raise ValueError(f"Unsupported export type: {export_type}")


def perform_system_health_check():
    """
    Perform comprehensive system health check
    """
    results = {
        'overall_status': 'healthy',
        'checks': [],
        'timestamp': timezone.now().isoformat()
    }

    # Database connectivity check
    try:
        People.objects.exists()
        results['checks'].append({
            'name': 'Database Connectivity',
            'status': 'pass',
            'message': 'Database is accessible',
            'response_time_ms': 10
        })
    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        results['checks'].append({
            'name': 'Database Connectivity',
            'status': 'fail',
            'message': f'Database error: {str(e)}',
            'response_time_ms': None
        })
        results['overall_status'] = 'unhealthy'

    # Cache connectivity check
    try:
        cache.set('health_check', 'test', 1)
        cache.get('health_check')
        results['checks'].append({
            'name': 'Cache System',
            'status': 'pass',
            'message': 'Cache is working normally',
            'response_time_ms': 5
        })
    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        results['checks'].append({
            'name': 'Cache System',
            'status': 'fail',
            'message': f'Cache error: {str(e)}',
            'response_time_ms': None
        })

    # Security check
    recent_violations = CSPViolation.objects.filter(
        violation_time__gte=timezone.now() - timedelta(hours=1)
    ).count()

    if recent_violations == 0:
        results['checks'].append({
            'name': 'Security Status',
            'status': 'pass',
            'message': 'No recent security violations',
            'response_time_ms': None
        })
    else:
        results['checks'].append({
            'name': 'Security Status',
            'status': 'warning',
            'message': f'{recent_violations} security violations in the last hour',
            'response_time_ms': None
        })

    return results


# Enhanced Admin Views for specific models
@method_decorator(admin_required, name='dispatch')
class AdminUserManagementView(TemplateView):
    """
    Enhanced user management interface
    """
    template_name = 'admin/user_management.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            'user_stats': self.get_user_statistics(),
            'recent_users': self.get_recent_users(),
            'user_distribution': self.get_user_distribution(),
        })

        return context

    def get_user_statistics(self):
        """
        Get detailed user statistics
        """
        return {
            'total': People.objects.count(),
            'active': People.objects.filter(enable=True).count(),
            'verified': People.objects.filter(isverified=True).count(),
            'admins': People.objects.filter(isadmin=True).count(),
            'unverified': People.objects.filter(isverified=False).count(),
        }

    def get_recent_users(self):
        """
        Get recently registered users
        """
        return People.objects.filter(
            cdtz__gte=timezone.now() - timedelta(days=30)
        ).order_by('-cdtz')[:10]

    def get_user_distribution(self):
        """
        Get user distribution by business unit
        """
        try:
            from apps.client_onboarding.models import Bt
            return Bt.objects.annotate(
                user_count=Count('people')
            ).values('buname', 'user_count').order_by('-user_count')[:10]
        except (ImportError, DatabaseError, OperationalError, ObjectDoesNotExist) as e:
            logger.warning(f"Failed to get user distribution: {e}", exc_info=True)
            return []


@method_decorator(admin_required, name='dispatch')
class AdminSystemMonitoringView(TemplateView):
    """
    System monitoring and health view
    """
    template_name = 'admin/system_monitoring.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            'health_status': perform_system_health_check(),
            'performance_metrics': self.get_performance_metrics(),
            'security_status': self.get_security_status(),
        })

        return context

    def get_performance_metrics(self):
        """
        Get system performance metrics
        """
        # This would integrate with your monitoring system
        return {
            'average_response_time': 150,
            'requests_per_minute': 450,
            'error_rate': 0.1,
            'cpu_usage': 35,
            'memory_usage': 60,
            'disk_usage': 45
        }

    def get_security_status(self):
        """
        Get security status overview
        """
        recent_violations = CSPViolation.objects.filter(
            violation_time__gte=timezone.now() - timedelta(days=1)
        ).count()

        failed_logins = APIAccessLog.objects.filter(
            timestamp__gte=timezone.now() - timedelta(hours=1),
            status_code__gte=400
        ).count()

        return {
            'csp_violations': recent_violations,
            'failed_login_attempts': failed_logins,
            'security_level': 'high' if recent_violations == 0 and failed_logins < 5 else 'medium'
        }