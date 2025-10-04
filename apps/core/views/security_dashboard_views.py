"""
Security Dashboard Views

Provides web-based security monitoring dashboard for:
- File upload security events and metrics
- Real-time threat monitoring
- Security alert management
- Performance metrics visualization

Complements the file upload security fixes for CVSS 8.1 vulnerability monitoring.
"""

import json
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.utils import timezone
from apps.core.services.security_monitoring_service import SecurityMonitoringService
import logging

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class SecurityDashboardView(TemplateView):
    """
    Main security monitoring dashboard view.

    Provides comprehensive security metrics and real-time monitoring
    for file upload security, rate limiting, and threat detection.
    """
    template_name = 'core/security_dashboard.html'

    def get_context_data(self, **kwargs):
        """Get dashboard context data."""
        context = super().get_context_data(**kwargs)

        try:
            monitoring_service = SecurityMonitoringService()

            # Get time window from request or default to 24 hours
            time_window = int(self.request.GET.get('time_window', 24))

            # Get comprehensive dashboard data
            dashboard_data = monitoring_service.get_security_dashboard_data(time_window)

            context.update({
                'dashboard_data': dashboard_data,
                'time_window': time_window,
                'refresh_interval': 30,  # Auto-refresh every 30 seconds
                'page_title': 'Security Monitoring Dashboard',
                'breadcrumbs': [
                    {'name': 'Home', 'url': '/'},
                    {'name': 'Security', 'url': '/security/'},
                    {'name': 'Dashboard', 'url': '#'}
                ]
            })

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error loading security dashboard: {e}", exc_info=True)
            context.update({
                'error': 'Unable to load security dashboard data',
                'dashboard_data': None
            })

        return context


@method_decorator(staff_member_required, name='dispatch')
class SecurityMetricsApiView(View):
    """
    API endpoint for security metrics data.

    Provides JSON data for AJAX dashboard updates and external integrations.
    """

    def get(self, request, *args, **kwargs):
        """Get security metrics as JSON."""
        try:
            monitoring_service = SecurityMonitoringService()

            # Get parameters from request
            time_window = int(request.GET.get('time_window', 24))
            metric_type = request.GET.get('metric_type', 'all')

            # Get dashboard data
            dashboard_data = monitoring_service.get_security_dashboard_data(time_window)

            # Filter data based on requested metric type
            if metric_type == 'alerts':
                response_data = {
                    'active_alerts': dashboard_data['active_alerts'],
                    'alert_summary': dashboard_data['alert_summary']
                }
            elif metric_type == 'metrics':
                response_data = {
                    'security_metrics': dashboard_data['security_metrics']
                }
            elif metric_type == 'trends':
                response_data = {
                    'trending_data': dashboard_data['trending_data']
                }
            else:
                response_data = dashboard_data

            # Add metadata
            response_data['success'] = True
            response_data['timestamp'] = timezone.now().isoformat()

            return JsonResponse(response_data)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error in security metrics API: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Unable to fetch security metrics',
                'timestamp': timezone.now().isoformat()
            }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class SecurityAlertsView(TemplateView):
    """
    Security alerts management view.

    Displays active alerts, alert history, and alert configuration.
    """
    template_name = 'core/security_alerts.html'

    def get_context_data(self, **kwargs):
        """Get alerts context data."""
        context = super().get_context_data(**kwargs)

        try:
            monitoring_service = SecurityMonitoringService()

            # Get current alerts
            active_alerts = monitoring_service.check_for_security_alerts()

            # Get alert history (last 7 days)
            alert_history = self._get_alert_history(days=7)

            context.update({
                'active_alerts': active_alerts,
                'alert_history': alert_history,
                'alert_statistics': self._calculate_alert_statistics(alert_history),
                'page_title': 'Security Alerts',
                'breadcrumbs': [
                    {'name': 'Home', 'url': '/'},
                    {'name': 'Security', 'url': '/security/'},
                    {'name': 'Alerts', 'url': '#'}
                ]
            })

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error loading security alerts: {e}", exc_info=True)
            context.update({
                'error': 'Unable to load security alerts',
                'active_alerts': [],
                'alert_history': []
            })

        return context

    def _get_alert_history(self, days: int = 7) -> list:
        """Get alert history for specified number of days."""
        # This would typically query from a database
        # For now, return simulated data
        end_time = timezone.now()
        start_time = end_time - timedelta(days=days)

        # Simulate alert history
        alerts = []
        for i in range(days * 24):  # Hourly data
            hour_time = start_time + timedelta(hours=i)

            # Simulate some alerts
            if i % 6 == 0:  # Every 6 hours
                alerts.append({
                    'timestamp': hour_time.isoformat(),
                    'type': 'RATE_LIMIT_VIOLATION',
                    'priority': 'MEDIUM',
                    'count': 5,
                    'resolved': True
                })

            if i % 12 == 0:  # Every 12 hours
                alerts.append({
                    'timestamp': hour_time.isoformat(),
                    'type': 'SUSPICIOUS_UPLOAD_PATTERN',
                    'priority': 'HIGH',
                    'count': 3,
                    'resolved': True
                })

        return alerts

    def _calculate_alert_statistics(self, alert_history: list) -> dict:
        """Calculate alert statistics from history."""
        total_alerts = len(alert_history)
        high_priority = len([a for a in alert_history if a['priority'] == 'HIGH'])
        medium_priority = len([a for a in alert_history if a['priority'] == 'MEDIUM'])
        resolved_alerts = len([a for a in alert_history if a.get('resolved', False)])

        return {
            'total_alerts': total_alerts,
            'high_priority': high_priority,
            'medium_priority': medium_priority,
            'resolved_alerts': resolved_alerts,
            'resolution_rate': round((resolved_alerts / max(total_alerts, 1)) * 100, 2)
        }


@method_decorator(staff_member_required, name='dispatch')
class FileUploadSecurityView(TemplateView):
    """
    File upload security specific monitoring view.

    Focused on file upload security metrics, validation failures,
    and upload attack patterns.
    """
    template_name = 'core/file_upload_security.html'

    def get_context_data(self, **kwargs):
        """Get file upload security context data."""
        context = super().get_context_data(**kwargs)

        try:
            monitoring_service = SecurityMonitoringService()

            # Get time window from request
            time_window = int(self.request.GET.get('time_window', 24))

            # Get file upload specific metrics
            metrics = monitoring_service.get_file_upload_metrics(time_window)

            # Extract file upload specific data
            upload_security = metrics.get('upload_security', {})
            file_validation = metrics.get('file_validation', {})
            suspicious_activity = metrics.get('suspicious_activity', {})

            context.update({
                'upload_metrics': upload_security,
                'validation_metrics': file_validation,
                'suspicious_metrics': suspicious_activity,
                'time_window': time_window,
                'page_title': 'File Upload Security',
                'breadcrumbs': [
                    {'name': 'Home', 'url': '/'},
                    {'name': 'Security', 'url': '/security/'},
                    {'name': 'File Upload Security', 'url': '#'}
                ]
            })

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error loading file upload security data: {e}", exc_info=True)
            context.update({
                'error': 'Unable to load file upload security data',
                'upload_metrics': {},
                'validation_metrics': {},
                'suspicious_metrics': {}
            })

        return context


class SecurityHealthCheckView(View):
    """
    Security health check endpoint for monitoring systems.

    Provides health status and basic metrics for external monitoring.
    """

    def get(self, request, *args, **kwargs):
        """Get security health status."""
        try:
            monitoring_service = SecurityMonitoringService()

            # Get basic health metrics
            metrics = monitoring_service.get_file_upload_metrics(1)  # Last 1 hour

            # Calculate health status
            health_status = self._calculate_health_status(metrics)

            response_data = {
                'status': health_status['status'],
                'score': health_status['score'],
                'metrics': {
                    'upload_success_rate': metrics['upload_security']['upload_success_rate'],
                    'rate_limit_violations': metrics['rate_limiting']['rate_limit_violations'],
                    'suspicious_activity': metrics['suspicious_activity']['suspicious_activity_alerts']
                },
                'timestamp': timezone.now().isoformat()
            }

            # Set appropriate HTTP status based on health
            status_code = 200 if health_status['status'] == 'healthy' else 503

            return JsonResponse(response_data, status=status_code)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error in security health check: {e}", exc_info=True)
            return JsonResponse({
                'status': 'unhealthy',
                'error': 'Health check failed',
                'timestamp': timezone.now().isoformat()
            }, status=503)

    def _calculate_health_status(self, metrics: dict) -> dict:
        """Calculate overall security health status."""
        score = 100

        # Check upload success rate
        upload_success_rate = metrics['upload_security']['upload_success_rate']
        if upload_success_rate < 90:
            score -= 10

        # Check rate limiting violations
        rate_violations = metrics['rate_limiting']['rate_limit_violations']
        if rate_violations > 50:
            score -= 15

        # Check suspicious activity
        suspicious_alerts = metrics['suspicious_activity']['suspicious_activity_alerts']
        if suspicious_alerts > 10:
            score -= 20

        # Determine status
        if score >= 80:
            status = 'healthy'
        elif score >= 60:
            status = 'warning'
        else:
            status = 'critical'

        return {
            'status': status,
            'score': score
        }


# Additional utility views for security operations

@staff_member_required
def security_export_view(request):
    """Export security data for analysis."""
    try:
        monitoring_service = SecurityMonitoringService()

        # Get parameters
        time_window = int(request.GET.get('time_window', 24))
        export_format = request.GET.get('format', 'json')

        # Get data
        dashboard_data = monitoring_service.get_security_dashboard_data(time_window)

        if export_format == 'json':
            response = JsonResponse(dashboard_data)
            response['Content-Disposition'] = f'attachment; filename="security_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response

        else:
            return JsonResponse({'error': 'Unsupported export format'}, status=400)

    except (DatabaseError, IntegrityError) as e:
        logger.error(f"Error exporting security data: {e}", exc_info=True)
        return JsonResponse({'error': 'Export failed'}, status=500)


@staff_member_required
def security_test_alerts_view(request):
    """Test alert system for validation."""
    try:
        monitoring_service = SecurityMonitoringService()

        # Create test alert
        test_alert = {
            'type': 'TEST_ALERT',
            'priority': 'LOW',
            'message': 'This is a test alert for system validation',
            'timestamp': timezone.now().isoformat(),
            'recommended_action': 'No action required - this is a test'
        }

        # Process test alert
        result = monitoring_service.create_security_incident(test_alert)

        return JsonResponse({
            'success': True,
            'message': 'Test alert processed successfully',
            'alert': test_alert
        })

    except (DatabaseError, IntegrityError) as e:
        logger.error(f"Error testing alert system: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Alert test failed'
        }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class SessionMonitoringView(TemplateView):
    """
    Session monitoring dashboard view.

    Implements Rule #10: Session Security Standards monitoring.

    Features:
    - Real-time active session count
    - Session activity timeline
    - Suspicious session detection
    - Privilege escalation tracking
    - Geographic anomaly detection
    """
    template_name = 'core/session_monitoring.html'

    def get_context_data(self, **kwargs):
        """Get session monitoring context data."""
        context = super().get_context_data(**kwargs)

        try:
            from apps.core.models import SessionForensics
            from django.contrib.sessions.models import Session

            time_window_hours = int(self.request.GET.get('hours', 24))
            cutoff = timezone.now() - timedelta(hours=time_window_hours)

            active_sessions_count = Session.objects.filter(
                expire_date__gt=timezone.now()
            ).count()

            timeout_events = cache.get(
                'session_activity:timeout_events',
                0
            )

            suspicious_activity = SessionForensics.get_suspicious_activity(
                hours=time_window_hours
            )

            recent_rotations = SessionForensics.objects.filter(
                event_type='rotated',
                timestamp__gte=cutoff
            ).select_related('user')[:50]

            privilege_escalations = SessionForensics.objects.filter(
                event_type='privilege_change',
                timestamp__gte=cutoff
            ).select_related('user')[:50]

            context.update({
                'active_sessions': active_sessions_count,
                'timeout_events': timeout_events,
                'suspicious_activity_count': suspicious_activity.count(),
                'suspicious_activities': suspicious_activity[:20],
                'recent_rotations': recent_rotations,
                'privilege_escalations': privilege_escalations,
                'time_window_hours': time_window_hours,
                'session_config': {
                    'cookie_age': settings.SESSION_COOKIE_AGE,
                    'save_every_request': settings.SESSION_SAVE_EVERY_REQUEST,
                    'expire_at_browser_close': settings.SESSION_EXPIRE_AT_BROWSER_CLOSE,
                    'activity_timeout': getattr(settings, 'SESSION_ACTIVITY_TIMEOUT', 1800),
                    'max_concurrent_sessions': getattr(settings, 'MAX_CONCURRENT_SESSIONS', 3)
                },
                'page_title': 'Session Security Monitoring',
                'breadcrumbs': [
                    {'name': 'Home', 'url': '/'},
                    {'name': 'Security', 'url': '/security/'},
                    {'name': 'Sessions', 'url': '#'}
                ]
            })

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error loading session monitoring dashboard: {e}", exc_info=True)
            context.update({
                'error': 'Unable to load session monitoring data'
            })

        return context


@method_decorator(staff_member_required, name='dispatch')
class SessionMonitoringApiView(View):
    """
    API endpoint for session monitoring data.

    Provides real-time session metrics for AJAX updates.
    """

    def get(self, request, *args, **kwargs):
        """Get session monitoring metrics as JSON."""
        try:
            from apps.core.models import SessionForensics
            from django.contrib.sessions.models import Session

            time_window = int(request.GET.get('hours', 1))
            cutoff = timezone.now() - timedelta(hours=time_window)

            active_sessions = Session.objects.filter(
                expire_date__gt=timezone.now()
            ).count()

            timeout_events = cache.get('session_activity:timeout_events', 0)

            recent_events = SessionForensics.objects.filter(
                timestamp__gte=cutoff
            ).values('event_type').annotate(
                count=models.Count('id')
            )

            suspicious_count = SessionForensics.objects.filter(
                timestamp__gte=cutoff,
                is_suspicious=True
            ).count()

            event_breakdown = {
                item['event_type']: item['count']
                for item in recent_events
            }

            return JsonResponse({
                'success': True,
                'timestamp': timezone.now().isoformat(),
                'metrics': {
                    'active_sessions': active_sessions,
                    'timeout_events': timeout_events,
                    'suspicious_events': suspicious_count,
                    'event_breakdown': event_breakdown
                },
                'config': {
                    'session_timeout': settings.SESSION_COOKIE_AGE,
                    'activity_timeout': getattr(settings, 'SESSION_ACTIVITY_TIMEOUT', 1800),
                    'max_concurrent': getattr(settings, 'MAX_CONCURRENT_SESSIONS', 3)
                }
            })

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error in session monitoring API: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to retrieve session metrics'
            }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class UserSessionManagementView(View):
    """
    User session management API endpoint.

    Allows users to:
    - View their active sessions
    - Invalidate specific sessions
    - Invalidate all other sessions (keep current)
    """

    def get(self, request, *args, **kwargs):
        """Get user's active sessions."""
        try:
            from apps.core.middleware.concurrent_session_limiting import SessionManagerAPI

            user_sessions = SessionManagerAPI.get_user_active_sessions(
                request.user.id
            )

            return JsonResponse({
                'success': True,
                'sessions': user_sessions,
                'total_sessions': len(user_sessions),
                'max_allowed': getattr(settings, 'MAX_CONCURRENT_SESSIONS', 3)
            })

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error retrieving user sessions: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to retrieve sessions'
            }, status=500)

    def post(self, request, *args, **kwargs):
        """Manage user sessions (invalidate specific or all others)."""
        try:
            from apps.core.middleware.concurrent_session_limiting import SessionManagerAPI

            action = request.POST.get('action')
            session_key = request.POST.get('session_key')

            if action == 'invalidate_session' and session_key:
                result = SessionManagerAPI.invalidate_session(
                    request.user.id,
                    session_key
                )

                return JsonResponse({
                    'success': result,
                    'message': 'Session invalidated' if result else 'Failed to invalidate session'
                })

            elif action == 'invalidate_all_others':
                count = SessionManagerAPI.invalidate_all_other_sessions(
                    request.user.id,
                    request.session.session_key
                )

                return JsonResponse({
                    'success': True,
                    'message': f'Invalidated {count} other sessions',
                    'invalidated_count': count
                })

            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action or missing parameters'
                }, status=400)

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error managing user sessions: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to manage sessions'
            }, status=500)