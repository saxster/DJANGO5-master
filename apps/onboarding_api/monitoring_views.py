"""
Production monitoring API views for Conversational Onboarding

These views provide operational monitoring endpoints for:
- Health checks and system status
- Performance metrics and analytics
- Alert monitoring and notifications
- Resource utilization tracking
"""

import logging
from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .monitoring import monitor
from .permissions import CanViewConversationAudit

logger = logging.getLogger(__name__)


class SystemHealthView(APIView):
    """
    Comprehensive system health check endpoint

    GET /api/v1/onboarding/health/

    Returns detailed health status of all components
    """
    permission_classes = []  # Public endpoint for load balancers

    def get(self, request):
        """Get comprehensive system health status"""
        try:
            health_status = monitor.perform_health_check()

            # Determine HTTP status code based on overall health
            if health_status['overall_status'] == 'healthy':
                response_status = status.HTTP_200_OK
            elif health_status['overall_status'] == 'degraded':
                response_status = status.HTTP_200_OK  # Still operational
            else:
                response_status = status.HTTP_503_SERVICE_UNAVAILABLE

            return Response(health_status, status=response_status)

        except (ValueError, TypeError) as e:
            logger.error(f"Health check failed: {e}")
            return Response(
                {
                    'overall_status': 'unhealthy',
                    'error': 'Health check system failure',
                    'timestamp': timezone.now().isoformat()
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class QuickHealthView(APIView):
    """
    Quick health check for load balancers

    GET /api/v1/onboarding/health/quick/

    Returns basic health status without detailed component checks
    """
    permission_classes = []  # Public endpoint for load balancers

    def get(self, request):
        """Get quick health status"""
        try:
            # Quick database connectivity check
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            # Check if conversational onboarding is enabled
            if not getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False):
                return Response(
                    {
                        'status': 'healthy',
                        'message': 'Service available (feature disabled)',
                        'feature_enabled': False,
                        'timestamp': timezone.now().isoformat()
                    }
                )

            return Response(
                {
                    'status': 'healthy',
                    'message': 'All systems operational',
                    'feature_enabled': True,
                    'timestamp': timezone.now().isoformat()
                }
            )

        except (ValueError, TypeError) as e:
            logger.error(f"Quick health check failed: {e}")
            return Response(
                {
                    'status': 'unhealthy',
                    'error': 'Database connectivity issue',
                    'timestamp': timezone.now().isoformat()
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class PerformanceMetricsView(APIView):
    """
    System performance metrics endpoint

    GET /api/v1/onboarding/metrics/

    Requires authentication to access detailed metrics
    """
    permission_classes = [IsAuthenticated, CanViewConversationAudit]

    def get(self, request):
        """Get performance metrics"""
        try:
            metrics = monitor.get_performance_metrics()

            # Add request metadata
            metrics['requested_by'] = request.user.email
            metrics['requested_at'] = timezone.now().isoformat()

            return Response(metrics)

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return Response(
                {
                    'error': 'Failed to retrieve performance metrics',
                    'timestamp': timezone.now().isoformat()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SystemAlertsView(APIView):
    """
    System alerts and monitoring notifications

    GET /api/v1/onboarding/alerts/

    Returns current system alerts requiring attention
    """
    permission_classes = [IsAuthenticated, CanViewConversationAudit]

    def get(self, request):
        """Get current system alerts"""
        try:
            alerts = monitor.check_system_alerts()

            # Categorize alerts by severity
            critical_alerts = [alert for alert in alerts if alert.get('severity') == 'critical']
            warning_alerts = [alert for alert in alerts if alert.get('severity') == 'warning']
            info_alerts = [alert for alert in alerts if alert.get('severity') == 'info']

            return Response({
                'total_alerts': len(alerts),
                'critical_count': len(critical_alerts),
                'warning_count': len(warning_alerts),
                'info_count': len(info_alerts),
                'alerts': {
                    'critical': critical_alerts,
                    'warning': warning_alerts,
                    'info': info_alerts
                },
                'requested_by': request.user.email,
                'timestamp': timezone.now().isoformat()
            })

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to get system alerts: {e}")
            return Response(
                {
                    'error': 'Failed to retrieve system alerts',
                    'timestamp': timezone.now().isoformat()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewConversationAudit])
def get_resource_utilization(request):
    """
    Get current resource utilization statistics

    Returns database usage, cache usage, and other resource metrics
    """
    try:
        from apps.core_onboarding.models import ConversationSession, LLMRecommendation, AIChangeSet
        from django.db import connection

        # Database statistics
        with connection.cursor() as cursor:
            # Get table sizes (PostgreSQL specific)
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    attname,
                    n_distinct,
                    correlation
                FROM pg_stats
                WHERE schemaname = 'public'
                  AND tablename LIKE '%onboarding%'
                LIMIT 10
            """)
            table_stats = cursor.fetchall()

        # Model counts
        conversation_count = ConversationSession.objects.count()
        recommendation_count = LLMRecommendation.objects.count()
        changeset_count = AIChangeSet.objects.count()

        # Recent activity
        cutoff_time = timezone.now() - timedelta(hours=24)
        recent_conversations = ConversationSession.objects.filter(cdtz__gte=cutoff_time).count()
        recent_recommendations = LLMRecommendation.objects.filter(cdtz__gte=cutoff_time).count()

        return Response({
            'database': {
                'conversation_sessions': conversation_count,
                'llm_recommendations': recommendation_count,
                'ai_changesets': changeset_count,
                'recent_activity_24h': {
                    'conversations': recent_conversations,
                    'recommendations': recent_recommendations
                },
                'table_statistics': [
                    {
                        'schema': stat[0],
                        'table': stat[1],
                        'column': stat[2],
                        'distinct_values': stat[3],
                        'correlation': stat[4]
                    }
                    for stat in table_stats
                ]
            },
            'cache': {
                'backend': settings.CACHES['default']['BACKEND'],
                'status': 'available'  # Could add more detailed cache stats
            },
            'feature_flags': {
                'conversational_onboarding': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False),
                'onboarding_checker': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', False),
                'knowledge_base': getattr(settings, 'ENABLE_ONBOARDING_KB', False),
                'server_sent_events': getattr(settings, 'ENABLE_ONBOARDING_SSE', False)
            },
            'requested_by': request.user.email,
            'timestamp': timezone.now().isoformat()
        })

    except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
        logger.error(f"Failed to get resource utilization: {e}")
        return Response(
            {
                'error': 'Failed to retrieve resource utilization',
                'timestamp': timezone.now().isoformat()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanViewConversationAudit])
def trigger_maintenance_mode(request):
    """
    Enable/disable maintenance mode for conversational onboarding

    POST /api/v1/onboarding/maintenance/

    Body: {"enabled": true/false, "reason": "maintenance reason"}
    """
    try:
        enabled = request.data.get('enabled', False)
        reason = request.data.get('reason', 'Scheduled maintenance')

        # Store maintenance mode in cache
        from django.core.cache import cache

        if enabled:
            maintenance_data = {
                'enabled': True,
                'reason': reason,
                'enabled_by': request.user.email,
                'enabled_at': timezone.now().isoformat()
            }
            cache.set('conversational_onboarding_maintenance', maintenance_data, timeout=3600*24)  # 24 hours max

            logger.warning(f"Maintenance mode enabled by {request.user.email}: {reason}")

            return Response({
                'message': 'Maintenance mode enabled',
                'maintenance': maintenance_data
            })

        else:
            cache.delete('conversational_onboarding_maintenance')

            logger.info(f"Maintenance mode disabled by {request.user.email}")

            return Response({
                'message': 'Maintenance mode disabled',
                'disabled_by': request.user.email,
                'disabled_at': timezone.now().isoformat()
            })

    except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
        logger.error(f"Failed to toggle maintenance mode: {e}")
        return Response(
            {
                'error': 'Failed to update maintenance mode',
                'timestamp': timezone.now().isoformat()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([])  # Public for load balancer health checks
def maintenance_status(request):
    """
    Check current maintenance mode status

    GET /api/v1/onboarding/maintenance/status/
    """
    try:
        from django.core.cache import cache

        maintenance_data = cache.get('conversational_onboarding_maintenance')

        if maintenance_data:
            return Response({
                'in_maintenance': True,
                'maintenance': maintenance_data,
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            'in_maintenance': False,
            'timestamp': timezone.now().isoformat()
        })

    except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
        logger.error(f"Failed to check maintenance status: {e}")
        return Response(
            {
                'error': 'Failed to check maintenance status',
                'timestamp': timezone.now().isoformat()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ConfigurationStatusView(APIView):
    """
    Display current configuration status and settings

    GET /api/v1/onboarding/config/status/

    Shows current feature flags, thresholds, and operational parameters
    """
    permission_classes = [IsAuthenticated, CanViewConversationAudit]

    def get(self, request):
        """Get current configuration status"""
        try:
            config_status = {
                'feature_flags': {
                    'conversational_onboarding': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False),
                    'onboarding_checker': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', False),
                    'knowledge_base': getattr(settings, 'ENABLE_ONBOARDING_KB', False),
                    'server_sent_events': getattr(settings, 'ENABLE_ONBOARDING_SSE', False),
                    'translation_caching': getattr(settings, 'ENABLE_TRANSLATION_CACHING', True),
                    'rate_limiting': getattr(settings, 'ENABLE_RATE_LIMITING', True)
                },
                'thresholds': {
                    'approval_threshold': getattr(settings, 'ONBOARDING_APPROVE_THRESHOLD', 0.7),
                    'escalation_threshold': getattr(settings, 'ONBOARDING_ESCALATE_THRESHOLD', 0.4),
                    'rate_limit_window': getattr(settings, 'ONBOARDING_API_RATE_LIMIT_WINDOW', 60),
                    'max_requests': getattr(settings, 'ONBOARDING_API_MAX_REQUESTS', 30)
                },
                'providers': {
                    'translation_provider': getattr(settings, 'TRANSLATION_PROVIDER', 'noop'),
                    'llm_providers': getattr(settings, 'LLM_PROVIDER_CONFIG', {}),
                    'cache_backend': settings.CACHES['default']['BACKEND']
                },
                'security': {
                    'api_auth_enabled': getattr(settings, 'ENABLE_API_AUTH', True),
                    'api_require_signing': getattr(settings, 'API_REQUIRE_SIGNING', False),
                    'csrf_protection': settings.CSRF_COOKIE_SECURE if hasattr(settings, 'CSRF_COOKIE_SECURE') else False
                },
                'requested_by': request.user.email,
                'timestamp': timezone.now().isoformat()
            }

            return Response(config_status)

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            logger.error(f"Failed to get configuration status: {e}")
            return Response(
                {
                    'error': 'Failed to retrieve configuration status',
                    'timestamp': timezone.now().isoformat()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )