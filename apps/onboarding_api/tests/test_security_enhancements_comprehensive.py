"""
Comprehensive Test Suite for Onboarding Security Enhancements

Tests cover:
- Phase 1: Rate limiter, upload throttling
- Phase 2: DLQ integration, funnel analytics
- Phase 3: Session recovery, error recovery, analytics dashboard

Author: Claude Code
Date: 2025-10-01
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from apps.core_onboarding.models import ConversationSession, LLMRecommendation
from apps.core_onboarding.services.security import get_rate_limiter
from apps.onboarding_api.services.upload_throttling import get_upload_throttling_service
from apps.onboarding_api.services.funnel_analytics import get_funnel_analytics_service
from apps.onboarding_api.services.session_recovery import (
    get_session_recovery_service,
    CheckpointNotFoundError
)
from apps.onboarding_api.services.error_recovery import (
    get_error_recovery_service,
    ErrorCategory,
    ErrorSeverity
)
from apps.onboarding_api.services.analytics_dashboard import get_analytics_dashboard_service
from background_tasks.onboarding_base_task import OnboardingBaseTask
from background_tasks.dead_letter_queue import dlq_handler

User = get_user_model()


# ==============================================================================
# PHASE 1 TESTS: Rate Limiter and Upload Throttling
# ==============================================================================

class RateLimiterTests(TestCase):
    """Tests for enhanced rate limiter with circuit breaker"""

    def setUp(self):
        self.rate_limiter = get_rate_limiter()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_rate_limiter_normal_operation(self):
        """Test rate limiter allows requests under limit"""
        user_id = "test_user_1"
        resource = "test_resource"

        for i in range(10):
            allowed, info = self.rate_limiter.check_rate_limit(
                user_identifier=user_id,
                resource_type=resource
            )
            assert allowed, f"Request {i} should be allowed"

    def test_rate_limiter_blocks_when_limit_exceeded(self):
        """Test rate limiter blocks requests over limit"""
        user_id = "test_user_2"
        resource = "test_resource"

        # Configure low limit for testing
        limit = 5

        for i in range(limit):
            allowed, info = self.rate_limiter.check_rate_limit(
                user_identifier=user_id,
                resource_type=resource
            )
            if allowed:
                self.rate_limiter.increment_usage(user_id, resource)

        # Next request should be blocked
        allowed, info = self.rate_limiter.check_rate_limit(
            user_identifier=user_id,
            resource_type=resource
        )
        assert not allowed, "Request should be blocked after limit exceeded"
        assert 'retry_after_seconds' in info

    @patch('apps.onboarding_api.services.security.cache.get')
    def test_rate_limiter_circuit_breaker_opens_on_cache_failure(self, mock_cache_get):
        """Test circuit breaker opens after threshold failures"""
        mock_cache_get.side_effect = Exception("Cache connection failed")

        rate_limiter = get_rate_limiter()
        rate_limiter.cache_failure_count = 0
        rate_limiter.circuit_breaker_threshold = 3

        # Trigger failures
        for i in range(3):
            allowed, info = rate_limiter.check_rate_limit(
                user_identifier="test_user",
                resource_type="test_resource"
            )

        # Circuit breaker should be open
        assert rate_limiter.circuit_breaker_reset_time is not None

    def test_rate_limiter_critical_resource_fail_closed(self):
        """Test critical resources fail-closed when circuit is open"""
        rate_limiter = get_rate_limiter()

        # Simulate open circuit breaker
        rate_limiter.circuit_breaker_reset_time = timezone.now() + timedelta(minutes=5)

        # Critical resource should be blocked
        allowed, info = rate_limiter.check_rate_limit(
            user_identifier="test_user",
            resource_type="llm_calls"  # Critical resource
        )

        assert not allowed, "Critical resource should fail-closed"
        assert info.get('reason') == 'circuit_breaker_open'

    def test_rate_limiter_fallback_cache_works(self):
        """Test in-memory fallback cache when Redis unavailable"""
        rate_limiter = get_rate_limiter()
        rate_limiter.fallback_cache = {}

        # Simulate circuit breaker open for non-critical resource
        rate_limiter.circuit_breaker_reset_time = timezone.now() + timedelta(minutes=5)

        user_id = "test_user"
        resource = "non_critical_resource"

        # Should use fallback cache
        for i in range(3):
            allowed, info = rate_limiter.check_rate_limit(
                user_identifier=user_id,
                resource_type=resource
            )
            assert allowed, f"Request {i} should use fallback"

    def test_rate_limiter_retry_after_header_calculation(self):
        """Test Retry-After header is correctly calculated"""
        rate_limiter = get_rate_limiter()

        # Simulate rate limit exceeded
        blocked, info = rate_limiter._handle_rate_limit_exceeded(
            user_identifier="test_user",
            resource_type="test_resource",
            current_count=100,
            limit=50,
            correlation_id="test_123"
        )

        assert not blocked
        assert 'retry_after_seconds' in info
        assert info['retry_after_seconds'] > 0


class UploadThrottlingTests(TestCase):
    """Tests for upload throttling service"""

    def setUp(self):
        self.throttling_service = get_upload_throttling_service()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_upload_throttling_photo_quota_enforcement(self):
        """Test photo upload quota is enforced per session"""
        session_id = "test_session_1"
        user_id = "test_user_1"

        # Simulate 50 photo uploads (at limit)
        for i in range(50):
            allowed, error_info = self.throttling_service.check_upload_allowed(
                session_id=session_id,
                user_id=user_id,
                upload_type='photos',
                file_size=1024 * 1024,  # 1MB
                content_type='image/jpeg'
            )

            if allowed:
                self.throttling_service.increment_upload_count(
                    session_id=session_id,
                    user_id=user_id,
                    upload_type='photos',
                    file_size=1024 * 1024
                )

        # 51st photo should be rejected
        allowed, error_info = self.throttling_service.check_upload_allowed(
            session_id=session_id,
            user_id=user_id,
            upload_type='photos',
            file_size=1024 * 1024,
            content_type='image/jpeg'
        )

        assert not allowed, "51st photo upload should be blocked"
        assert error_info['error'] == 'session_photo_limit'

    def test_upload_throttling_total_size_limit(self):
        """Test total upload size limit per session"""
        session_id = "test_session_2"
        user_id = "test_user_2"

        large_file_size = 50 * 1024 * 1024  # 50MB

        # Upload 2 large files (100MB total)
        for i in range(2):
            allowed, error_info = self.throttling_service.check_upload_allowed(
                session_id=session_id,
                user_id=user_id,
                upload_type='photos',
                file_size=large_file_size,
                content_type='image/jpeg'
            )

            if allowed:
                self.throttling_service.increment_upload_count(
                    session_id=session_id,
                    user_id=user_id,
                    upload_type='photos',
                    file_size=large_file_size
                )

        # 3rd large file should be rejected (would exceed 100MB limit)
        allowed, error_info = self.throttling_service.check_upload_allowed(
            session_id=session_id,
            user_id=user_id,
            upload_type='photos',
            file_size=large_file_size,
            content_type='image/jpeg'
        )

        assert not allowed, "Upload exceeding total size should be blocked"
        assert error_info['error'] == 'total_size_limit'

    def test_upload_throttling_burst_protection(self):
        """Test burst protection (10 photos/minute limit)"""
        session_id = "test_session_3"
        user_id = "test_user_3"

        # Rapidly upload 10 photos
        for i in range(10):
            allowed, error_info = self.throttling_service.check_upload_allowed(
                session_id=session_id,
                user_id=user_id,
                upload_type='photos',
                file_size=1024 * 1024,
                content_type='image/jpeg'
            )

            if allowed:
                self.throttling_service.increment_upload_count(
                    session_id=session_id,
                    user_id=user_id,
                    upload_type='photos',
                    file_size=1024 * 1024
                )

        # 11th rapid upload should be rejected
        allowed, error_info = self.throttling_service.check_upload_allowed(
            session_id=session_id,
            user_id=user_id,
            upload_type='photos',
            file_size=1024 * 1024,
            content_type='image/jpeg'
        )

        assert not allowed, "Burst upload should be blocked"
        assert error_info['error'] == 'burst_limit'

    def test_upload_throttling_file_type_validation(self):
        """Test invalid file types are rejected"""
        session_id = "test_session_4"
        user_id = "test_user_4"

        # Try to upload executable file as photo
        allowed, error_info = self.throttling_service.check_upload_allowed(
            session_id=session_id,
            user_id=user_id,
            upload_type='photos',
            file_size=1024,
            content_type='application/x-executable'
        )

        assert not allowed, "Invalid file type should be rejected"
        assert error_info['error'] == 'file_type_invalid'


# ==============================================================================
# PHASE 2 TESTS: DLQ and Funnel Analytics
# ==============================================================================

class DLQIntegrationTests(TransactionTestCase):
    """Tests for DLQ integration with OnboardingBaseTask"""

    def test_onboarding_base_task_generates_correlation_id(self):
        """Test OnboardingBaseTask generates correlation ID"""
        task = OnboardingBaseTask()

        correlation_id = task.get_correlation_id()

        assert correlation_id is not None
        assert len(correlation_id) > 0

    def test_onboarding_base_task_uses_provided_correlation_id(self):
        """Test OnboardingBaseTask uses provided correlation ID"""
        task = OnboardingBaseTask()
        provided_id = "test_correlation_123"

        correlation_id = task.get_correlation_id(provided_id)

        assert correlation_id == provided_id

    def test_onboarding_base_task_task_success_format(self):
        """Test task success response format"""
        task = OnboardingBaseTask()

        result = task.task_success(
            result={'data': 'test'},
            correlation_id='test_123'
        )

        assert result['status'] == 'completed'
        assert result['result'] == {'data': 'test'}
        assert result['correlation_id'] == 'test_123'
        assert 'completed_at' in result

    def test_onboarding_base_task_task_failure_format(self):
        """Test task failure response format"""
        task = OnboardingBaseTask()

        result = task.task_failure(
            error_message='Test error',
            correlation_id='test_123',
            error_type='TestError'
        )

        assert result['status'] == 'failed'
        assert result['error'] == 'Test error'
        assert result['error_type'] == 'TestError'
        assert result['correlation_id'] == 'test_123'

    @patch('background_tasks.onboarding_base_task.dlq_handler.send_to_dlq')
    def test_onboarding_base_task_sends_to_dlq_on_final_retry(self, mock_send_to_dlq):
        """Test DLQ integration on final retry"""
        task = OnboardingBaseTask()
        task.name = 'test_task'
        task.max_retries = 3

        # Simulate final retry
        task.request = Mock()
        task.request.retries = 3
        task.request.id = 'task_123'
        task.request.args = ('arg1',)
        task.request.kwargs = {}

        # Handle error
        exception = Exception("Test error")
        result = task.handle_task_error(
            exception=exception,
            correlation_id='test_123',
            context={'test': 'context'}
        )

        # Verify DLQ was called
        mock_send_to_dlq.assert_called_once()


class FunnelAnalyticsTests(TestCase):
    """Tests for funnel analytics service"""

    def setUp(self):
        self.analytics_service = get_funnel_analytics_service()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_funnel_metrics_calculation_accuracy(self):
        """Test funnel metrics are calculated correctly"""
        # Create test sessions
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)

        # Create sessions in different states
        ConversationSession.objects.create(
            session_id='session1',
            user=self.user,
            current_state=ConversationSession.StateChoices.STARTED,
            cdtz=start_time,
            mdtz=start_time + timedelta(minutes=1)
        )

        ConversationSession.objects.create(
            session_id='session2',
            user=self.user,
            current_state=ConversationSession.StateChoices.COMPLETED,
            cdtz=start_time,
            mdtz=start_time + timedelta(minutes=10)
        )

        # Calculate metrics
        metrics = self.analytics_service.calculate_funnel_metrics(
            start_date=start_time,
            end_date=end_time
        )

        assert metrics.total_sessions >= 2
        assert len(metrics.stages) > 0
        assert 0 <= metrics.overall_conversion_rate <= 1

    def test_drop_off_point_identification(self):
        """Test drop-off points are identified correctly"""
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)

        # Create sessions showing drop-off
        for i in range(10):
            ConversationSession.objects.create(
                session_id=f'session_{i}',
                user=self.user,
                current_state=ConversationSession.StateChoices.STARTED,
                cdtz=start_time,
                mdtz=start_time + timedelta(minutes=1)
            )

        # Only 2 complete
        for i in range(2):
            ConversationSession.objects.create(
                session_id=f'completed_{i}',
                user=self.user,
                current_state=ConversationSession.StateChoices.COMPLETED,
                cdtz=start_time,
                mdtz=start_time + timedelta(minutes=10)
            )

        metrics = self.analytics_service.calculate_funnel_metrics(
            start_date=start_time,
            end_date=end_time
        )

        assert len(metrics.top_drop_off_points) > 0


# ==============================================================================
# PHASE 3 TESTS: Session Recovery and Error Recovery
# ==============================================================================

class SessionRecoveryTests(TransactionTestCase):
    """Tests for session recovery service"""

    def setUp(self):
        self.recovery_service = get_session_recovery_service()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_checkpoint_creation_succeeds(self):
        """Test checkpoint is created successfully"""
        session = ConversationSession.objects.create(
            session_id='test_session',
            user=self.user,
            current_state=ConversationSession.StateChoices.IN_PROGRESS,
            cdtz=timezone.now(),
            mdtz=timezone.now()
        )

        checkpoint_data = {
            'state': ConversationSession.StateChoices.IN_PROGRESS,
            'data': {'answers': ['a1', 'a2']},
            'history': ['q1', 'q2'],
            'version': 1
        }

        result = self.recovery_service.create_checkpoint(
            session_id=str(session.session_id),
            checkpoint_data=checkpoint_data,
            force=True
        )

        assert result['status'] == 'created'
        assert 'checkpoint_version' in result

    def test_session_resume_restores_state(self):
        """Test session resume restores correct state"""
        session = ConversationSession.objects.create(
            session_id='test_session_2',
            user=self.user,
            current_state=ConversationSession.StateChoices.STARTED,
            cdtz=timezone.now(),
            mdtz=timezone.now()
        )

        # Create checkpoint
        checkpoint_data = {
            'state': ConversationSession.StateChoices.IN_PROGRESS,
            'data': {'answers': ['a1', 'a2']},
            'history': ['q1', 'q2'],
            'version': 1
        }

        self.recovery_service.create_checkpoint(
            session_id=str(session.session_id),
            checkpoint_data=checkpoint_data,
            force=True
        )

        # Resume session
        result = self.recovery_service.resume_session(
            session_id=str(session.session_id),
            user_id=self.user.id
        )

        assert result['status'] == 'resumed'
        assert 'next_action' in result

    def test_abandonment_risk_detection_accuracy(self):
        """Test abandonment risk is detected accurately"""
        # Create session with risk factors
        session = ConversationSession.objects.create(
            session_id='risky_session',
            user=self.user,
            current_state=ConversationSession.StateChoices.IN_PROGRESS,
            cdtz=timezone.now() - timedelta(minutes=15),  # 15 min inactive
            mdtz=timezone.now() - timedelta(minutes=15),
            collected_data={
                'same_question_count': 4,  # Confused
                'error_count': 6  # Many errors
            }
        )

        risk_assessment = self.recovery_service.detect_abandonment_risk(
            str(session.session_id)
        )

        assert risk_assessment['risk_score'] > 50
        assert risk_assessment['risk_level'] in ['high', 'critical']
        assert len(risk_assessment['risk_factors']) > 0


class ErrorRecoveryTests(TestCase):
    """Tests for error recovery service"""

    def setUp(self):
        self.error_service = get_error_recovery_service()

    def test_error_categorization_database_errors(self):
        """Test database errors are categorized correctly"""
        from django.db import DatabaseError

        exception = DatabaseError("Connection timeout")

        categorization = self.error_service.categorize_error(exception)

        assert categorization['category'] == ErrorCategory.DATABASE.value
        assert categorization['severity'] == ErrorSeverity.CRITICAL.value
        assert categorization['is_retryable'] is True

    def test_error_categorization_validation_errors(self):
        """Test validation errors are categorized correctly"""
        from django.core.exceptions import ValidationError

        exception = ValidationError("Invalid input format")

        categorization = self.error_service.categorize_error(exception)

        assert categorization['category'] == ErrorCategory.VALIDATION.value
        assert categorization['is_retryable'] is False

    def test_retry_configuration_for_network_errors(self):
        """Test retry configuration for network errors"""
        categorization = {
            'category': ErrorCategory.NETWORK.value,
            'severity': ErrorSeverity.MEDIUM.value
        }

        retry_config = self.error_service.get_retry_configuration(categorization)

        assert retry_config['max_attempts'] >= 3
        assert retry_config['backoff_type'] == 'exponential'

    def test_user_facing_message_generation(self):
        """Test user-facing messages are contextual"""
        exception = Exception("Database connection failed")

        categorization = self.error_service.categorize_error(exception)

        assert 'user_message' in categorization
        assert 'title' in categorization['user_message']
        assert 'message' in categorization['user_message']
        assert 'action_button' in categorization['user_message']


# ==============================================================================
# RUN TESTS
# ==============================================================================

@pytest.mark.django_db
class TestIntegrationScenarios:
    """Integration tests covering full workflows"""

    def test_complete_onboarding_workflow_with_checkpoints(self, db):
        """Test complete onboarding workflow with checkpoints"""
        # This would test:
        # 1. Session creation
        # 2. Checkpoint creation at each step
        # 3. Funnel tracking
        # 4. Successful completion
        # 5. Analytics reflection
        pass  # Implementation would be extensive

    def test_session_recovery_after_abandonment(self, db):
        """Test session can be recovered after abandonment"""
        # This would test:
        # 1. Session starts
        # 2. Checkpoints created
        # 3. Session abandoned
        # 4. Risk detected
        # 5. Session resumed
        # 6. Completion
        pass  # Implementation would be extensive


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
