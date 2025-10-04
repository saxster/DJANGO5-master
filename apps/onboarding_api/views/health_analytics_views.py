"""
Health Check and Analytics Views

System health monitoring, analytics, and feature status endpoints.

Migrated from: apps/onboarding_api/views.py (lines 1185-1948)
Date: 2025-09-30
"""
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import logging

logger = logging.getLogger(__name__)


class FeatureStatusView(APIView):
    """Check feature status and configuration"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return feature status and configuration"""
        response_data = {
            'enabled': settings.ENABLE_CONVERSATIONAL_ONBOARDING,
            'flags': {
                'dual_llm_enabled': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', False),
                'streaming_enabled': getattr(settings, 'ENABLE_ONBOARDING_SSE', False),
                'personalization_enabled': getattr(settings, 'ENABLE_ONBOARDING_PERSONALIZATION', False),
                'knowledge_base_enabled': getattr(settings, 'ENABLE_ONBOARDING_KB', True),
                'ai_experiments_enabled': getattr(settings, 'ENABLE_ONBOARDING_EXPERIMENTS', False),
            },
            'configuration': {
                'max_session_duration_minutes': getattr(settings, 'ONBOARDING_SESSION_DURATION', 30),
                'max_recommendations_per_session': getattr(settings, 'ONBOARDING_MAX_RECOMMENDATIONS', 5),
                'languages_supported': getattr(settings, 'ONBOARDING_LANGUAGES', ['en']),
                'llm_provider': getattr(settings, 'ONBOARDING_LLM_PROVIDER', 'dummy'),
            },
            'version': '1.0.0'
        }

        if hasattr(request.user, 'capabilities') and request.user.capabilities:
            response_data['user_capabilities'] = {
                'can_approve_recommendations': request.user.capabilities.get('can_approve_ai_recommendations', False),
                'can_access_admin_dashboard': request.user.capabilities.get('can_access_ai_admin_dashboard', False),
                'can_override_ai_decisions': request.user.capabilities.get('can_override_ai_decisions', False),
            }
        else:
            response_data['user_capabilities'] = {
                'can_approve_recommendations': False,
                'can_access_admin_dashboard': False,
                'can_override_ai_decisions': False,
            }

        return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cache_health_check(request):
    """Check cache backend health"""
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from ..middleware import OnboardingAPIMiddleware

        cache_status = OnboardingAPIMiddleware.get_cache_health_status()
        http_status = status.HTTP_200_OK if cache_status['is_valid'] else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response({
            'cache_health': cache_status,
            'system_status': 'healthy' if cache_status['is_valid'] else 'degraded',
            'checked_at': timezone.now().isoformat(),
            'recommendations': cache_status.get('recommendations', [])
        }, status=http_status)

    except Exception as e:
        logger.error(f"Cache health check error: {str(e)}")
        return Response({
            'error': 'Cache health check failed',
            'details': str(e),
            'system_status': 'unknown',
            'checked_at': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def logging_health_check(request):
    """Check logging configuration health"""
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from ..utils.logging_validation import get_logging_health_status

        logging_health = get_logging_health_status()

        if logging_health['overall_health'] == 'critical':
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            http_status = status.HTTP_200_OK

        return Response({
            'logging_health': logging_health,
            'system_status': logging_health['overall_health'],
            'checked_at': timezone.now().isoformat(),
            'recommendations': logging_health.get('recommendations', []),
            'critical_issues': logging_health.get('critical_issues', [])
        }, status=http_status)

    except Exception as e:
        logger.error(f"Logging health check error: {str(e)}")
        return Response({
            'error': 'Logging health check failed',
            'details': str(e),
            'system_status': 'unknown',
            'checked_at': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def preflight_validation(request):
    """Preflight validation for onboarding readiness"""
    try:
        from ..utils.preflight import run_preflight_validation

        client = request.user.client if hasattr(request.user, 'client') and request.user.client else None

        if request.method == 'POST' and request.user.is_staff:
            client_id = request.data.get('client_id')
            if client_id:
                try:
                    from apps.onboarding.models import Bt
                    client = Bt.objects.get(id=client_id)
                except Bt.DoesNotExist:
                    return Response({
                        'error': 'Specified client not found',
                        'client_id': client_id
                    }, status=status.HTTP_400_BAD_REQUEST)

        if not client:
            return Response({
                'error': 'User must be associated with a client',
                'user_id': request.user.id,
                'user_email': request.user.email
            }, status=status.HTTP_400_BAD_REQUEST)

        validation_results = run_preflight_validation(client=client, user=request.user)

        if validation_results['overall_status'] == 'critical':
            http_status = status.HTTP_412_PRECONDITION_FAILED
        else:
            http_status = status.HTTP_200_OK

        return Response({
            'preflight_validation': validation_results,
            'client_info': {
                'id': client.id,
                'name': getattr(client, 'buname', 'Unknown'),
                'code': getattr(client, 'bucode', 'Unknown'),
                'is_active': getattr(client, 'is_active', False)
            },
            'user_info': {
                'id': request.user.id,
                'email': request.user.email
            },
            'validation_timestamp': timezone.now().isoformat()
        }, status=http_status)

    except Exception as e:
        logger.error(f"Preflight validation error: {str(e)}")
        return Response({
            'error': 'Preflight validation failed',
            'details': str(e),
            'validation_status': 'error',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health_monitoring(request):
    """System health monitoring endpoint"""
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from ..utils.monitoring import get_system_health, get_degradation_status

        health_report = get_system_health()
        degradation_status = get_degradation_status()

        response_data = {
            'system_health': health_report,
            'degradation_status': degradation_status,
            'monitoring_metadata': {
                'endpoint': '/api/v1/onboarding/health/system/',
                'version': '1.0',
                'checked_at': timezone.now().isoformat()
            }
        }

        if health_report['overall_status'].value == 'critical':
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            http_status = status.HTTP_200_OK

        return Response(response_data, status=http_status)

    except Exception as e:
        logger.error(f"System health monitoring error: {str(e)}")
        return Response({
            'error': 'System health monitoring failed',
            'details': str(e),
            'system_status': 'unknown',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
