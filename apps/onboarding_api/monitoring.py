"""
Production monitoring and health checks for Conversational Onboarding

This module provides comprehensive monitoring capabilities including:
- Health checks for all critical components
- Performance metrics collection
- Error rate monitoring
- System alerts and notifications
- Circuit breaker patterns for external dependencies
"""

import logging
import time
from typing import Dict, Any, List
from django.core.cache import cache
from django.utils import timezone

from apps.core_onboarding.models import ConversationSession, LLMRecommendation, AIChangeSet
from apps.core_onboarding.services.llm import get_llm_service
from apps.core_onboarding.services.knowledge import get_knowledge_service

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """Structured health check result"""

    def __init__(self, service: str, status: str, details: Dict[str, Any] = None,
                 response_time_ms: float = 0, error: str = None):
        self.service = service
        self.status = status  # 'healthy', 'degraded', 'unhealthy'
        self.details = details or {}
        self.response_time_ms = response_time_ms
        self.error = error
        self.timestamp = timezone.now()

    def to_dict(self):
        return {
            'service': self.service,
            'status': self.status,
            'details': self.details,
            'response_time_ms': self.response_time_ms,
            'error': self.error,
            'timestamp': self.timestamp.isoformat(),
            'is_healthy': self.status == 'healthy'
        }


class ConversationalOnboardingMonitor:
    """
    Comprehensive monitoring system for conversational onboarding

    Features:
    - Component health checks
    - Performance metrics collection
    - Error rate monitoring
    - Capacity monitoring
    - External dependency monitoring
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check of all components

        Returns:
            Dict containing overall health status and component details
        """
        start_time = time.time()
        health_results = {}
        overall_status = 'healthy'

        # Core component health checks
        health_checks = [
            self._check_database_health,
            self._check_cache_health,
            self._check_llm_service_health,
            self._check_knowledge_service_health,
            self._check_conversation_processing_health,
            self._check_integration_adapter_health,
            self._check_background_task_health,
            self._check_storage_health,
        ]

        for health_check in health_checks:
            try:
                result = health_check()
                health_results[result.service] = result.to_dict()

                # Determine overall status
                if result.status == 'unhealthy':
                    overall_status = 'unhealthy'
                elif result.status == 'degraded' and overall_status == 'healthy':
                    overall_status = 'degraded'

            except (ConnectionError, LLMServiceException, TimeoutError) as e:
                self.logger.error(f"Health check failed for {health_check.__name__}: {e}")
                service_name = health_check.__name__.replace('_check_', '').replace('_health', '')
                health_results[service_name] = {
                    'service': service_name,
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': timezone.now().isoformat(),
                    'is_healthy': False
                }
                overall_status = 'unhealthy'

        total_time = (time.time() - start_time) * 1000

        return {
            'overall_status': overall_status,
            'total_check_time_ms': round(total_time, 2),
            'timestamp': timezone.now().isoformat(),
            'components': health_results,
            'summary': self._generate_health_summary(health_results)
        }

    def _check_database_health(self) -> HealthCheckResult:
        """Check database connectivity and performance"""
        start_time = time.time()

        try:
            # Test database connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            # Test onboarding models
            conversation_count = ConversationSession.objects.count()
            recommendation_count = LLMRecommendation.objects.count()
            changeset_count = AIChangeSet.objects.count()

            response_time = (time.time() - start_time) * 1000

            # Check for concerning metrics
            status = 'healthy'
            details = {
                'conversation_sessions': conversation_count,
                'llm_recommendations': recommendation_count,
                'changesets': changeset_count,
                'database_engine': connection.settings_dict['ENGINE']
            }

            # Check for potential issues
            if response_time > 1000:  # Slow database response
                status = 'degraded'
                details['warning'] = 'Database response time is slow'

            return HealthCheckResult(
                service='database',
                status=status,
                details=details,
                response_time_ms=round(response_time, 2)
            )

        except (ConnectionError, LLMServiceException, TimeoutError) as e:
            return HealthCheckResult(
                service='database',
                status='unhealthy',
                error=str(e),
                response_time_ms=(time.time() - start_time) * 1000
            )

    def _check_cache_health(self) -> HealthCheckResult:
        """Check cache system health"""
        start_time = time.time()

        try:
            test_key = f"health_check_{int(time.time())}"
            test_value = "test_value"

            # Test cache write/read
            cache.set(test_key, test_value, timeout=60)
            retrieved_value = cache.get(test_key)

            if retrieved_value != test_value:
                raise Exception("Cache write/read test failed")

            # Clean up
            cache.delete(test_key)

            response_time = (time.time() - start_time) * 1000

            return HealthCheckResult(
                service='cache',
                status='healthy',
                details={
                    'cache_backend': settings.CACHES['default']['BACKEND'],
                    'write_read_test': 'passed'
                },
                response_time_ms=round(response_time, 2)
            )

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            return HealthCheckResult(
                service='cache',
                status='unhealthy',
                error=str(e),
                response_time_ms=(time.time() - start_time) * 1000
            )

    def _check_llm_service_health(self) -> HealthCheckResult:
        """Check LLM service availability and performance"""
        start_time = time.time()

        try:
            if not getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False):
                return HealthCheckResult(
                    service='llm_service',
                    status='healthy',
                    details={'status': 'disabled', 'reason': 'conversational_onboarding_disabled'},
                    response_time_ms=0
                )

            llm_service = get_llm_service()

            # Test basic connectivity (if service supports it)
            if hasattr(llm_service, 'health_check'):
                health_status = llm_service.health_check()
            else:
                # Fallback: test with minimal request
                try:
                    test_response = llm_service.generate_response(
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=5
                    )
                    health_status = {'status': 'available', 'test_response': True}
                except (ValueError, TypeError, AttributeError) as e:
                    health_status = {'status': 'degraded', 'test_response': False}

            response_time = (time.time() - start_time) * 1000

            status = 'healthy' if health_status.get('status') == 'available' else 'degraded'

            return HealthCheckResult(
                service='llm_service',
                status=status,
                details={
                    'provider': llm_service.__class__.__name__,
                    'health_status': health_status,
                    'feature_enabled': True
                },
                response_time_ms=round(response_time, 2)
            )

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            return HealthCheckResult(
                service='llm_service',
                status='unhealthy',
                error=str(e),
                response_time_ms=(time.time() - start_time) * 1000
            )

    def _check_knowledge_service_health(self) -> HealthCheckResult:
        """Check knowledge service health"""
        start_time = time.time()

        try:
            if not getattr(settings, 'ENABLE_ONBOARDING_KB', False):
                return HealthCheckResult(
                    service='knowledge_service',
                    status='healthy',
                    details={'status': 'disabled', 'reason': 'knowledge_base_disabled'},
                    response_time_ms=0
                )

            knowledge_service = get_knowledge_service()

            # Test basic functionality
            if hasattr(knowledge_service, 'health_check'):
                health_status = knowledge_service.health_check()
            else:
                # Test search functionality
                try:
                    search_results = knowledge_service.search_knowledge("test", limit=1)
                    health_status = {'status': 'available', 'search_test': True}
                except (ValueError, TypeError, AttributeError) as e:
                    health_status = {'status': 'degraded', 'search_test': False}

            response_time = (time.time() - start_time) * 1000

            status = 'healthy' if health_status.get('status') == 'available' else 'degraded'

            return HealthCheckResult(
                service='knowledge_service',
                status=status,
                details={
                    'service': knowledge_service.__class__.__name__,
                    'health_status': health_status,
                    'feature_enabled': True
                },
                response_time_ms=round(response_time, 2)
            )

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            return HealthCheckResult(
                service='knowledge_service',
                status='unhealthy',
                error=str(e),
                response_time_ms=(time.time() - start_time) * 1000
            )

    def _check_conversation_processing_health(self) -> HealthCheckResult:
        """Check conversation processing pipeline health"""
        start_time = time.time()

        try:
            # Check recent conversation processing metrics
            cutoff_time = timezone.now() - timedelta(hours=1)

            recent_conversations = ConversationSession.objects.filter(
                cdtz__gte=cutoff_time
            )

            # Check error rates
            error_conversations = recent_conversations.filter(
                current_state=ConversationSession.StateChoices.ERROR
            ).count()

            total_conversations = recent_conversations.count()
            error_rate = (error_conversations / total_conversations) if total_conversations > 0 else 0

            # Check processing times (approximation)
            stuck_conversations = ConversationSession.objects.filter(
                current_state=ConversationSession.StateChoices.IN_PROGRESS,
                mdtz__lt=timezone.now() - timedelta(hours=2)
            ).count()

            response_time = (time.time() - start_time) * 1000

            # Determine status
            status = 'healthy'
            warnings = []

            if error_rate > 0.1:  # More than 10% error rate
                status = 'degraded'
                warnings.append(f'High error rate: {error_rate:.1%}')

            if stuck_conversations > 0:
                status = 'degraded' if status == 'healthy' else status
                warnings.append(f'{stuck_conversations} conversations appear stuck')

            return HealthCheckResult(
                service='conversation_processing',
                status=status,
                details={
                    'recent_conversations': total_conversations,
                    'error_conversations': error_conversations,
                    'error_rate': round(error_rate, 3),
                    'stuck_conversations': stuck_conversations,
                    'warnings': warnings
                },
                response_time_ms=round(response_time, 2)
            )

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            return HealthCheckResult(
                service='conversation_processing',
                status='unhealthy',
                error=str(e),
                response_time_ms=(time.time() - start_time) * 1000
            )

    def _check_integration_adapter_health(self) -> HealthCheckResult:
        """Check integration adapter health"""
        start_time = time.time()

        try:
            from apps.onboarding_api.integration.mapper import IntegrationAdapter

            adapter = IntegrationAdapter()

            # Check recent changeset operations
            cutoff_time = timezone.now() - timedelta(hours=24)
            recent_changesets = AIChangeSet.objects.filter(cdtz__gte=cutoff_time)

            total_changesets = recent_changesets.count()
            failed_changesets = recent_changesets.filter(
                status=AIChangeSet.StatusChoices.FAILED
            ).count()

            failure_rate = (failed_changesets / total_changesets) if total_changesets > 0 else 0

            response_time = (time.time() - start_time) * 1000

            # Determine status
            status = 'healthy'
            if failure_rate > 0.05:  # More than 5% failure rate
                status = 'degraded'

            return HealthCheckResult(
                service='integration_adapter',
                status=status,
                details={
                    'recent_changesets': total_changesets,
                    'failed_changesets': failed_changesets,
                    'failure_rate': round(failure_rate, 3),
                    'supported_types': adapter.supported_types
                },
                response_time_ms=round(response_time, 2)
            )

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            return HealthCheckResult(
                service='integration_adapter',
                status='unhealthy',
                error=str(e),
                response_time_ms=(time.time() - start_time) * 1000
            )

    def _check_background_task_health(self) -> HealthCheckResult:
        """Check background task system health"""
        start_time = time.time()

        try:
            # Note: This is a basic check. In production, you'd check actual task queue health
            # For now, we'll check if the task system is configured

            task_backend_configured = hasattr(settings, 'CELERY_BROKER_URL') or hasattr(settings, 'CELERY_RESULT_BACKEND')

            response_time = (time.time() - start_time) * 1000

            status = 'healthy' if task_backend_configured else 'degraded'

            return HealthCheckResult(
                service='background_tasks',
                status=status,
                details={
                    'task_backend_configured': task_backend_configured,
                    'note': 'Basic configuration check only'
                },
                response_time_ms=round(response_time, 2)
            )

        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            return HealthCheckResult(
                service='background_tasks',
                status='unhealthy',
                error=str(e),
                response_time_ms=(time.time() - start_time) * 1000
            )

    def _check_storage_health(self) -> HealthCheckResult:
        """Check storage system health"""
        start_time = time.time()

        try:
            import os
            import tempfile

            # Test temporary directory access
            with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
                tmp_file.write(b'health check test')
                tmp_file.flush()

            # Check media directory if configured
            media_root = getattr(settings, 'MEDIA_ROOT', None)
            media_accessible = False
            if media_root and os.path.exists(media_root):
                media_accessible = os.access(media_root, os.W_OK)

            response_time = (time.time() - start_time) * 1000

            status = 'healthy'
            details = {
                'temp_directory_writable': True,
                'media_root_configured': media_root is not None,
                'media_root_accessible': media_accessible
            }

            if media_root and not media_accessible:
                status = 'degraded'
                details['warning'] = 'Media directory not accessible'

            return HealthCheckResult(
                service='storage',
                status=status,
                details=details,
                response_time_ms=round(response_time, 2)
            )

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, LLMServiceException, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, ValueError) as e:
            return HealthCheckResult(
                service='storage',
                status='unhealthy',
                error=str(e),
                response_time_ms=(time.time() - start_time) * 1000
            )

    def _generate_health_summary(self, health_results: Dict) -> Dict[str, Any]:
        """Generate summary of health check results"""
        healthy_services = []
        degraded_services = []
        unhealthy_services = []

        for service_name, result in health_results.items():
            if result['status'] == 'healthy':
                healthy_services.append(service_name)
            elif result['status'] == 'degraded':
                degraded_services.append(service_name)
            else:
                unhealthy_services.append(service_name)

        return {
            'total_services': len(health_results),
            'healthy_services': len(healthy_services),
            'degraded_services': len(degraded_services),
            'unhealthy_services': len(unhealthy_services),
            'healthy_service_names': healthy_services,
            'degraded_service_names': degraded_services,
            'unhealthy_service_names': unhealthy_services,
            'availability_percentage': round(
                (len(healthy_services) + len(degraded_services)) / len(health_results) * 100, 2
            ) if health_results else 100
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the last 24 hours"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=24)

            # Conversation metrics
            total_conversations = ConversationSession.objects.filter(cdtz__gte=cutoff_time).count()
            completed_conversations = ConversationSession.objects.filter(
                cdtz__gte=cutoff_time,
                current_state=ConversationSession.StateChoices.COMPLETED
            ).count()

            # Recommendation metrics
            total_recommendations = LLMRecommendation.objects.filter(cdtz__gte=cutoff_time).count()
            approved_recommendations = LLMRecommendation.objects.filter(
                cdtz__gte=cutoff_time,
                status=LLMRecommendation.StatusChoices.APPROVED
            ).count()

            # Changeset metrics
            total_changesets = AIChangeSet.objects.filter(cdtz__gte=cutoff_time).count()
            successful_changesets = AIChangeSet.objects.filter(
                cdtz__gte=cutoff_time,
                status=AIChangeSet.StatusChoices.APPLIED
            ).count()

            return {
                'time_period': '24_hours',
                'timestamp': timezone.now().isoformat(),
                'conversations': {
                    'total': total_conversations,
                    'completed': completed_conversations,
                    'completion_rate': round(completed_conversations / total_conversations, 3) if total_conversations > 0 else 0
                },
                'recommendations': {
                    'total': total_recommendations,
                    'approved': approved_recommendations,
                    'approval_rate': round(approved_recommendations / total_recommendations, 3) if total_recommendations > 0 else 0
                },
                'changesets': {
                    'total': total_changesets,
                    'successful': successful_changesets,
                    'success_rate': round(successful_changesets / total_changesets, 3) if total_changesets > 0 else 0
                }
            }

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, LLMServiceException, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, ValueError) as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }

    def check_system_alerts(self) -> List[Dict[str, Any]]:
        """Check for system alerts and issues that require attention"""
        alerts = []

        try:
            # Check for stuck conversations
            stuck_conversations = ConversationSession.objects.filter(
                current_state=ConversationSession.StateChoices.IN_PROGRESS,
                mdtz__lt=timezone.now() - timedelta(hours=4)
            ).count()

            if stuck_conversations > 0:
                alerts.append({
                    'severity': 'warning',
                    'type': 'stuck_conversations',
                    'message': f'{stuck_conversations} conversations have been in progress for over 4 hours',
                    'count': stuck_conversations,
                    'timestamp': timezone.now().isoformat()
                })

            # Check for high error rates
            recent_conversations = ConversationSession.objects.filter(
                cdtz__gte=timezone.now() - timedelta(hours=1)
            ).count()

            if recent_conversations > 0:
                error_conversations = ConversationSession.objects.filter(
                    cdtz__gte=timezone.now() - timedelta(hours=1),
                    current_state=ConversationSession.StateChoices.ERROR
                ).count()

                error_rate = error_conversations / recent_conversations

                if error_rate > 0.15:  # More than 15% error rate
                    alerts.append({
                        'severity': 'critical',
                        'type': 'high_error_rate',
                        'message': f'High conversation error rate: {error_rate:.1%}',
                        'error_rate': error_rate,
                        'timestamp': timezone.now().isoformat()
                    })

            # Check for failed changesets
            failed_changesets = AIChangeSet.objects.filter(
                cdtz__gte=timezone.now() - timedelta(hours=6),
                status=AIChangeSet.StatusChoices.FAILED
            ).count()

            if failed_changesets > 0:
                alerts.append({
                    'severity': 'warning',
                    'type': 'failed_changesets',
                    'message': f'{failed_changesets} changesets failed in the last 6 hours',
                    'count': failed_changesets,
                    'timestamp': timezone.now().isoformat()
                })

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, LLMServiceException, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, ValueError) as e:
            alerts.append({
                'severity': 'critical',
                'type': 'monitoring_error',
                'message': f'Failed to check system alerts: {str(e)}',
                'timestamp': timezone.now().isoformat()
            })

        return alerts


# Singleton instance
monitor = ConversationalOnboardingMonitor()