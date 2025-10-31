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
from apps.ontology.decorators import ontology
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import logging

logger = logging.getLogger(__name__)


@ontology(
    domain="onboarding",
    purpose="REST API for onboarding system health monitoring, feature flags, cache health, logging health, and preflight validation",
    api_endpoint=True,
    http_methods=["GET", "POST"],
    authentication_required=True,
    permissions=["IsAuthenticated", "IsStaff (for admin endpoints)"],
    rate_limit="50/minute",
    response_schema="FeatureStatusResponse|HealthCheckResponse|PreflightValidationResponse",
    error_codes=[400, 401, 403, 412, 500, 503],
    criticality="medium",
    tags=["api", "rest", "health", "monitoring", "onboarding", "analytics", "system-status"],
    security_notes="Admin endpoints require is_staff. Health checks return 503 on critical failures. Preflight validation ensures tenant readiness",
    endpoints={
        "feature_status": "GET /api/v1/onboarding/feature-status/ - Get feature flags and configuration",
        "cache_health": "GET /api/v1/onboarding/cache-health/ - Check cache backend health",
        "logging_health": "GET /api/v1/onboarding/logging-health/ - Check logging configuration",
        "preflight": "GET|POST /api/v1/onboarding/preflight/ - Comprehensive tenant validation",
        "preflight_quick": "GET /api/v1/onboarding/preflight/quick/ - Quick readiness check",
        "reset_degradations": "POST /api/v1/onboarding/health/reset-degradations/ - Reset auto-degradations (admin)",
        "degradation_status": "GET /api/v1/onboarding/health/degradations/ - Get degradation status",
        "system_health": "GET /api/v1/onboarding/health/system/ - System health monitoring (admin)"
    },
    examples=[
        "curl -X GET https://api.example.com/api/v1/onboarding/feature-status/ -H 'Authorization: Bearer <token>'",
        "curl -X POST https://api.example.com/api/v1/onboarding/preflight/ -H 'Authorization: Bearer <token>' -d '{\"client_id\":123}'"
    ]
)
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
    """
    Preflight validation endpoint for conversational onboarding readiness

    GET /api/v1/onboarding/preflight/
    POST /api/v1/onboarding/preflight/

    This endpoint performs comprehensive validation to ensure the tenant and user
    are properly configured before enabling conversational onboarding features.

    Returns detailed validation results with actionable recommendations.

    Migrated from: apps/onboarding_api/views.py (lines 1623-1715)
    Date: 2025-10-11 (complete version with helper function)
    """
    try:
        from ..utils.preflight import run_preflight_validation
        from django.core.exceptions import ObjectDoesNotExist, ValidationError
        from django.db import DatabaseError, IntegrityError

        # Import exception classes for proper exception handling
        try:
            from ..services.llm import LLMServiceException
        except ImportError:
            class LLMServiceException(Exception):
                pass

        try:
            from ..integration.mapper import IntegrationException
        except ImportError:
            class IntegrationException(Exception):
                pass

        # Get client from user or request parameters
        client = request.user.client if hasattr(request.user, 'client') and request.user.client else None

        # For POST requests, allow specifying different client (staff only)
        if request.method == 'POST' and request.user.is_staff:
            data = request.data if hasattr(request, 'data') else {}
            client_id = data.get('client_id')
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
                'error': 'User must be associated with a client for preflight validation',
                'user_id': request.user.id,
                'user_email': request.user.email
            }, status=status.HTTP_400_BAD_REQUEST)

        # Run comprehensive preflight validation
        validation_results = run_preflight_validation(client=client, user=request.user)

        # Determine HTTP status based on validation results
        if validation_results['overall_status'] == 'critical':
            http_status = status.HTTP_412_PRECONDITION_FAILED  # Cannot proceed
        elif validation_results['overall_status'] == 'warning':
            http_status = status.HTTP_200_OK  # Can proceed with cautions
        else:
            http_status = status.HTTP_200_OK  # Ready to go

        # Add context information
        response_data = {
            'preflight_validation': validation_results,
            'client_info': {
                'id': client.id,
                'name': getattr(client, 'buname', 'Unknown'),
                'code': getattr(client, 'bucode', 'Unknown'),
                'is_active': getattr(client, 'is_active', False)
            },
            'user_info': {
                'id': request.user.id,
                'email': request.user.email,
                'capabilities': request.user.get_all_capabilities() if hasattr(request.user, 'get_all_capabilities') else {}
            },
            'next_steps': _get_next_steps_recommendations(validation_results),
            'validation_timestamp': timezone.now().isoformat()
        }

        # Log validation for monitoring
        logger.info(
            f"Preflight validation completed for client {client.id}: {validation_results['overall_status']}",
            extra={
                'client_id': client.id,
                'user_id': request.user.id,
                'validation_status': validation_results['overall_status'],
                'is_ready': validation_results['is_ready'],
                'critical_issues_count': len(validation_results['critical_issues']),
                'warnings_count': len(validation_results['warnings'])
            }
        )

        return Response(response_data, status=http_status)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Preflight validation error: {str(e)}")
        return Response({
            'error': 'Preflight validation failed',
            'details': str(e),
            'validation_status': 'error',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_next_steps_recommendations(validation_results: dict) -> list:
    """
    Generate actionable next steps based on validation results

    Helper function for preflight_validation.

    Args:
        validation_results: Results from preflight validation

    Returns:
        List of recommended next steps

    Migrated from: apps/onboarding_api/views.py (lines 1718-1767)
    Date: 2025-10-11
    """
    next_steps = []

    if validation_results['overall_status'] == 'critical':
        next_steps.append({
            'priority': 'critical',
            'action': 'resolve_critical_issues',
            'title': 'Resolve Critical Issues',
            'description': 'Fix all critical issues before enabling conversational onboarding',
            'issues': validation_results['critical_issues']
        })

    if validation_results['warnings']:
        next_steps.append({
            'priority': 'warning',
            'action': 'review_warnings',
            'title': 'Review Warnings',
            'description': 'Address warnings to improve onboarding experience',
            'warnings': validation_results['warnings']
        })

    if validation_results['recommendations']:
        next_steps.append({
            'priority': 'recommendation',
            'action': 'implement_recommendations',
            'title': 'Implement Recommendations',
            'description': 'Follow recommendations for optimal configuration',
            'recommendations': validation_results['recommendations']
        })

    if validation_results['is_ready']:
        next_steps.append({
            'priority': 'info',
            'action': 'enable_onboarding',
            'title': 'Enable Conversational Onboarding',
            'description': 'System is ready - you can now enable conversational onboarding features',
            'endpoint': '/api/v1/onboarding/conversation/start/',
            'admin_url': '/admin/onboarding_api/peopleonboardingproxy/'
        })

    return next_steps


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def preflight_quick_check(request):
    """
    Quick preflight check for basic readiness

    GET /api/v1/onboarding/preflight/quick/

    Performs essential validation checks only for faster response.
    Use full preflight validation for comprehensive assessment.

    Migrated from: apps/onboarding_api/views.py (lines 1770-1819)
    Date: 2025-10-11
    """
    try:
        from django.core.exceptions import ObjectDoesNotExist, ValidationError
        from django.db import DatabaseError, IntegrityError

        # Import exception classes
        try:
            from ..services.llm import LLMServiceException
        except ImportError:
            class LLMServiceException(Exception):
                pass

        try:
            from ..integration.mapper import IntegrationException
        except ImportError:
            class IntegrationException(Exception):
                pass

        client = request.user.client if hasattr(request.user, 'client') and request.user.client else None

        if not client:
            return Response({
                'ready': False,
                'reason': 'No client associated with user',
                'next_action': 'contact_administrator'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Quick checks only
        quick_checks = {
            'client_active': getattr(client, 'is_active', False),
            'user_active': request.user.is_active,
            'feature_enabled': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False),
            'user_has_capability': request.user.get_capability('can_use_conversational_onboarding') if hasattr(request.user, 'get_capability') else False
        }

        all_passed = all(quick_checks.values())

        response_data = {
            'ready': all_passed,
            'quick_checks': quick_checks,
            'timestamp': timezone.now().isoformat()
        }

        if not all_passed:
            response_data['next_action'] = 'run_full_preflight_validation'
            response_data['full_validation_url'] = '/api/v1/onboarding/preflight/'

        return Response(response_data, status=status.HTTP_200_OK)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Quick preflight check error: {str(e)}")
        return Response({
            'ready': False,
            'error': str(e),
            'next_action': 'contact_support'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def logging_documentation(request):
    """
    Get logging setup documentation
    GET /api/v1/onboarding/documentation/logging/

    Returns comprehensive documentation for configuring and maintaining
    the logging system for the onboarding API.

    Migrated from: apps/onboarding_api/views.py (lines 1587-1620)
    Date: 2025-10-11
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from django.core.exceptions import ObjectDoesNotExist, ValidationError
        from django.db import DatabaseError, IntegrityError
        from ..utils.logging_validation import create_logger_setup_documentation

        # Import exception classes
        try:
            from ..services.llm import LLMServiceException
        except ImportError:
            class LLMServiceException(Exception):
                pass

        try:
            from ..integration.mapper import IntegrationException
        except ImportError:
            class IntegrationException(Exception):
                pass

        documentation = create_logger_setup_documentation()

        return Response({
            'documentation': documentation,
            'format': 'markdown',
            'generated_at': timezone.now().isoformat(),
            'version': '1.0'
        }, status=status.HTTP_200_OK)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error generating logging documentation: {str(e)}")
        return Response({
            'error': 'Documentation generation failed',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_degradations(request):
    """
    Reset system degradations (admin only)
    POST /api/v1/onboarding/health/reset-degradations/

    Allows administrators to reset auto-applied degradations.

    Migrated from: apps/onboarding_api/views.py (lines 1876-1920)
    Date: 2025-10-11
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from django.core.exceptions import ObjectDoesNotExist, ValidationError
        from django.db import DatabaseError, IntegrityError
        from ..utils.monitoring import reset_system_degradations

        # Import exception classes
        try:
            from ..services.llm import LLMServiceException
        except ImportError:
            class LLMServiceException(Exception):
                pass

        try:
            from ..integration.mapper import IntegrationException
        except ImportError:
            class IntegrationException(Exception):
                pass

        level = request.data.get('level') if hasattr(request, 'data') else None
        reset_result = reset_system_degradations(level)

        logger.info(
            f"System degradations reset by {request.user.email}: {reset_result}",
            extra={
                'user_id': request.user.id,
                'user_email': request.user.email,
                'reset_level': level,
                'reset_details': reset_result
            }
        )

        return Response({
            'success': True,
            'reset_result': reset_result,
            'message': "Degradations reset successfully",
            'reset_by': request.user.email,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Degradation reset error: {str(e)}")
        return Response({
            'error': 'Failed to reset degradations',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def degradation_status(request):
    """
    Get current degradation status
    GET /api/v1/onboarding/health/degradations/

    Returns current auto-degradation status for monitoring.

    Migrated from: apps/onboarding_api/views.py (lines 1923-1947)
    Date: 2025-10-11
    """
    try:
        from django.core.exceptions import ObjectDoesNotExist, ValidationError
        from django.db import DatabaseError, IntegrityError
        from ..utils.monitoring import get_degradation_status

        # Import exception classes
        try:
            from ..services.llm import LLMServiceException
        except ImportError:
            class LLMServiceException(Exception):
                pass

        try:
            from ..integration.mapper import IntegrationException
        except ImportError:
            class IntegrationException(Exception):
                pass

        status_info = get_degradation_status()

        return Response({
            'degradation_status': status_info,
            'checked_at': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Degradation status check error: {str(e)}")
        return Response({
            'error': 'Failed to check degradation status',
            'details': str(e)
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
