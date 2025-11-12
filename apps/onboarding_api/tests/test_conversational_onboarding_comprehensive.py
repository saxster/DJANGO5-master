"""
Comprehensive test suite for Conversational Onboarding Module

This test suite provides complete coverage of all critical functionality,
security enhancements, and edge cases for the onboarding system.
"""
import uuid

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from apps.onboarding_api.utils.concurrency import advisory_lock, check_lock_status
from apps.onboarding_api.utils.monitoring import SystemMonitor, HealthStatus, DegradationLevel

User = get_user_model()


class ConversationalOnboardingBaseTestCase(APITestCase):
    """Base test case with common setup for onboarding tests"""

    def setUp(self):
        """Set up test data"""
        # Create test client/tenant
        self.client_model = Bt.objects.create(
            buname="Test Client",
            bucode="TESTCLIENT",
            is_active=True
        )

        # Create test user with capabilities
        self.user = User.objects.create_user(
            email='test@example.com',
            loginid='testuser',
            client=self.client_model,
            is_active=True,
            is_verified=True,
            capabilities={
                'can_use_conversational_onboarding': True,
                'can_approve_ai_recommendations': False,
                'can_manage_knowledge_base': False
            }
        )

        # Create admin user
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            loginid='adminuser',
            client=self.client_model,
            is_staff=True,
            is_active=True,
            is_verified=True,
            capabilities={
                'can_use_conversational_onboarding': True,
                'can_approve_ai_recommendations': True,
                'can_manage_knowledge_base': True,
                'can_access_admin_endpoints': True
            }
        )

        # Create approver user
        self.approver_user = User.objects.create_user(
            email='approver@example.com',
            loginid='approveruser',
            client=self.client_model,
            is_active=True,
            is_verified=True,
            capabilities={
                'can_use_conversational_onboarding': True,
                'can_approve_ai_recommendations': True
            }
        )

        self.client.force_authenticate(user=self.user)

        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()


class ConversationStartTestCase(ConversationalOnboardingBaseTestCase):
    """Test conversation start functionality"""

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True)
    def test_conversation_start_success(self):
        """Test successful conversation start"""
        url = reverse('onboarding_api:conversation-start')
        data = {
            'language': 'en',
            'client_context': {'setup_type': 'initial'},
            'conversation_type': 'initial_setup'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('conversation_id', response.data)
        self.assertIn('session_token', response.data)

        # Verify session was created
        session_id = response.data['conversation_id']
        session = ConversationSession.objects.get(session_id=session_id)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.client, self.client_model)

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=False)
    def test_conversation_start_disabled(self):
        """Test conversation start when feature is disabled"""
        url = reverse('onboarding_api:conversation-start')
        data = {'language': 'en'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('not enabled', response.data['error'])

    def test_conversation_start_concurrent_protection(self):
        """Test advisory locks prevent concurrent session creation"""
        url = reverse('onboarding_api:conversation-start')
        data = {'language': 'en'}

        # Create an active session first
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_model,
            current_state=ConversationSession.StateChoices.IN_PROGRESS,
            conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP
        )

        with override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True):
            response = self.client.post(url, data, format='json')

        # Should return conflict due to existing active session
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('active conversation session', response.data['error'])

    def test_conversation_start_no_client(self):
        """Test conversation start fails without client association"""
        # Remove client association
        self.user.client = None
        self.user.save()

        url = reverse('onboarding_api:conversation-start')
        data = {'language': 'en'}

        with override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True):
            response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('client', response.data['error'])


class ConcurrencyTestCase(ConversationalOnboardingBaseTestCase):
    """Test concurrency control mechanisms"""

    def test_advisory_lock_basic_functionality(self):
        """Test basic advisory lock functionality"""
        with advisory_lock(self.user, self.client_model.id, "test_operation") as acquired:
            self.assertTrue(acquired)

            # Check lock status
            lock_status = check_lock_status(self.user, self.client_model.id, "test_operation")
            self.assertTrue(lock_status['is_locked'])

        # Lock should be released after context
        lock_status = check_lock_status(self.user, self.client_model.id, "test_operation")
        self.assertFalse(lock_status['is_locked'])

    def test_advisory_lock_prevents_concurrent_access(self):
        """Test that advisory locks prevent concurrent access"""
        # First lock acquisition should succeed
        with advisory_lock(self.user, self.client_model.id, "test_operation") as first_acquired:
            self.assertTrue(first_acquired)

            # Second lock acquisition should fail
            with advisory_lock(self.user, self.client_model.id, "test_operation") as second_acquired:
                self.assertFalse(second_acquired)

    def test_advisory_lock_different_users(self):
        """Test advisory locks are user-specific"""
        with advisory_lock(self.user, self.client_model.id, "test_operation") as user_acquired:
            self.assertTrue(user_acquired)

            # Different user should be able to acquire different lock
            with advisory_lock(self.admin_user, self.client_model.id, "test_operation") as admin_acquired:
                self.assertTrue(admin_acquired)


class SecurityTestCase(ConversationalOnboardingBaseTestCase):
    """Test security enhancements"""

    def test_tenant_scope_validation_success(self):
        """Test successful tenant scope validation"""
        from apps.onboarding_api.utils.security import tenant_scope_validator

        validation = tenant_scope_validator.validate_tenant_scope(
            self.user, self.client_model, 'read'
        )

        self.assertTrue(validation['is_valid'])
        self.assertEqual(validation['tenant_id'], self.client_model.id)
        self.assertEqual(validation['user_id'], self.user.id)

    def test_tenant_scope_validation_wrong_client(self):
        """Test tenant scope validation fails for wrong client"""
        from apps.onboarding_api.utils.security import tenant_scope_validator

        # Create different client
        other_client = Bt.objects.create(
            buname="Other Client",
            bucode="OTHERCLIENT",
            is_active=True
        )

        validation = tenant_scope_validator.validate_tenant_scope(
            self.user, other_client, 'read'
        )

        self.assertFalse(validation['is_valid'])
        self.assertIn('does not belong', validation['violations'][0])

    def test_tenant_scope_validation_admin_operation(self):
        """Test admin operation requires proper privileges"""
        from apps.onboarding_api.utils.security import tenant_scope_validator

        # Regular user should fail admin operation
        validation = tenant_scope_validator.validate_tenant_scope(
            self.user, self.client_model, 'admin_manage'
        )
        self.assertFalse(validation['is_valid'])

        # Admin user should succeed
        validation = tenant_scope_validator.validate_tenant_scope(
            self.admin_user, self.client_model, 'admin_manage'
        )
        self.assertTrue(validation['is_valid'])
        self.assertEqual(validation['scope_level'], 'admin')

    def test_idempotency_manager(self):
        """Test idempotency protection"""
        from apps.onboarding_api.utils.security import idempotency_manager

        # Generate idempotency key
        key = idempotency_manager.generate_idempotency_key(
            self.user, 'test_operation', {'data': 'test'}
        )

        self.assertIsInstance(key, str)
        self.assertTrue(key.startswith('onboarding_idempotency:'))

        # First check should indicate no duplicate
        result = idempotency_manager.check_idempotency(key, {'result': 'success'})
        self.assertFalse(result['is_duplicate'])

        # Second check should indicate duplicate
        result = idempotency_manager.check_idempotency(key)
        self.assertTrue(result['is_duplicate'])
        self.assertEqual(result['cached_result']['result'], {'result': 'success'})

    def test_security_audit_logging(self):
        """Test security audit logging"""
        from apps.onboarding_api.utils.security import security_audit_logger

        with self.assertLogs('audit', level='INFO') as log:
            security_audit_logger.log_access_attempt(
                user=self.user,
                resource='/api/test',
                operation='read',
                granted=True,
                additional_context={'test': 'context'}
            )

        self.assertIn('access_granted', log.output[0])


class PreflightValidationTestCase(ConversationalOnboardingBaseTestCase):
    """Test preflight validation system"""

    def test_preflight_validation_success(self):
        """Test successful preflight validation"""
        validator = PreflightValidator(client=self.client_model, user=self.user)
        results = validator.run_full_validation()

        self.assertIn('overall_status', results)
        self.assertIn('is_ready', results)
        self.assertIn('checks', results)
        self.assertIsInstance(results['checks'], dict)

    def test_preflight_validation_no_client(self):
        """Test preflight validation with no client"""
        validator = PreflightValidator(client=None, user=self.user)
        results = validator.run_full_validation()

        self.assertFalse(results['is_ready'])
        self.assertIn('client_configuration', results['checks'])
        self.assertFalse(results['checks']['client_configuration']['passed'])

    def test_preflight_validation_inactive_client(self):
        """Test preflight validation with inactive client"""
        self.client_model.is_active = False
        self.client_model.save()

        validator = PreflightValidator(client=self.client_model, user=self.user)
        results = validator.run_full_validation()

        self.assertFalse(results['is_ready'])
        self.assertIn('Client is not active', results['critical_issues'])

    def test_preflight_validation_endpoint(self):
        """Test preflight validation API endpoint"""
        url = reverse('onboarding_api:preflight-validation')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('preflight_validation', response.data)
        self.assertIn('client_info', response.data)
        self.assertIn('next_steps', response.data)


class MonitoringTestCase(ConversationalOnboardingBaseTestCase):
    """Test health monitoring and auto-degradation"""

    def test_system_monitor_initialization(self):
        """Test system monitor initialization"""
        monitor = SystemMonitor()

        self.assertEqual(monitor.degradation_state, DegradationLevel.NONE)
        self.assertIsInstance(monitor.thresholds, dict)

    @patch('apps.onboarding_api.utils.monitoring.cache')
    def test_system_health_check(self, mock_cache):
        """Test system health check"""
        # Mock cache to return healthy metrics
        mock_cache.get.return_value = {
            'avg_latency_ms': 1000,
            'error_rate_percent': 2.0,
            'daily_tokens_used': 1000
        }

        monitor = SystemMonitor()
        health_report = monitor.check_system_health()

        self.assertIn('overall_status', health_report)
        self.assertIn('component_status', health_report)
        self.assertIsInstance(health_report['component_status'], dict)

    @patch('apps.onboarding_api.utils.monitoring.cache')
    def test_auto_degradation_trigger(self, mock_cache):
        """Test auto-degradation triggers"""
        # Mock cache to return unhealthy metrics
        mock_cache.get.return_value = {
            'avg_latency_ms': 50000,  # Very high latency
            'error_rate_percent': 15.0,  # High error rate
            'daily_tokens_used': 1000
        }
        mock_cache.set.return_value = True

        monitor = SystemMonitor()
        health_report = monitor.check_system_health()

        # Should have applied degradations
        self.assertEqual(health_report['overall_status'], HealthStatus.CRITICAL)
        self.assertGreater(len(health_report['degradations_applied']), 0)

    def test_health_monitoring_endpoint(self):
        """Test health monitoring API endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('onboarding_api:system-health-monitoring')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('system_health', response.data)
        self.assertIn('degradation_status', response.data)

    def test_health_monitoring_non_staff(self):
        """Test health monitoring endpoint requires staff permission"""
        url = reverse('onboarding_api:system-health-monitoring')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class EscalationTestCase(ConversationalOnboardingBaseTestCase):
    """Test escalation functionality"""

    def setUp(self):
        super().setUp()
        # Create a test session and changeset for escalation tests
        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_model,
            current_state=ConversationSession.StateChoices.AWAITING_USER_APPROVAL,
            conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP
        )

        self.changeset = AIChangeSet.objects.create(
            session=self.session,
            recommendations_summary="Test recommendations",
            status=AIChangeSet.StatusChoices.PENDING,
            total_changes=1,
            successful_changes=0,
            failed_changes=0
        )

        self.approval = ChangeSetApproval.objects.create(
            changeset=self.changeset,
            approval_level=ChangeSetApproval.ApprovalLevelChoices.SECONDARY,
            required=True,
            status=ChangeSetApproval.StatusChoices.PENDING
        )

    @patch('apps.y_helpdesk.models.Ticket.objects.create')
    def test_secondary_approval_escalation(self, mock_ticket_create):
        """Test secondary approval escalation creates helpdesk ticket"""
        # Mock ticket creation
        mock_ticket = Mock()
        mock_ticket.ticketno = 'APPR-ESC-20241201-12345678'
        mock_ticket.uuid = uuid.uuid4()
        mock_ticket_create.return_value = mock_ticket

        self.client.force_authenticate(user=self.approver_user)
        url = reverse('onboarding_api:secondary-approval-decide', kwargs={'approval_id': self.approval.id})

        data = {
            'decision': 'escalate',
            'reason': 'Need senior management review'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['decision'], 'escalated')
        self.assertIn('escalation_details', response.data)
        self.assertIn('ticket_number', response.data['escalation_details'])

        # Verify ticket creation was called
        mock_ticket_create.assert_called_once()


class RateLimitingTestCase(ConversationalOnboardingBaseTestCase):
    """Test rate limiting functionality"""

    @patch('django.core.cache.cache.get')
    @patch('django.core.cache.cache.set')
    def test_rate_limiting_middleware(self, mock_cache_set, mock_cache_get):
        """Test rate limiting middleware"""
        # Mock cache to simulate rate limit not exceeded
        mock_cache_get.return_value = 5  # Under the limit

        middleware = OnboardingAPIMiddleware(lambda r: Mock())

        # Create mock request
        request = Mock()
        request.path = '/api/v1/onboarding/conversation/start/'
        request.user = self.user
        request.META = {'REMOTE_ADDR': '127.0.0.1'}

        result = middleware.process_request(request)

        # Should not be rate limited
        self.assertIsNone(result)

    def test_cache_health_check_endpoint(self):
        """Test cache health check endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('onboarding_api:cache-health-check')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cache_health', response.data)
        self.assertIn('system_status', response.data)


class BackgroundTaskTestCase(ConversationalOnboardingBaseTestCase):
    """Test background task functionality"""

    def test_cleanup_old_sessions_task(self):
        """Test cleanup of old sessions"""
        # Create old session
        old_session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_model,
            current_state=ConversationSession.StateChoices.COMPLETED,
            conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP
        )

        # Make it old by setting the date manually
        old_date = timezone.now() - timedelta(days=35)
        old_session.mdtz = old_date
        old_session.save()

        from background_tasks.onboarding_tasks import cleanup_old_sessions

        # Create mock self for the task
        mock_self = Mock()

        result = cleanup_old_sessions(mock_self, days_old=30)

        self.assertEqual(result['status'], 'completed')
        self.assertGreaterEqual(result['sessions_deleted'], 1)

        # Verify session was deleted
        with self.assertRaises(ConversationSession.DoesNotExist):
            ConversationSession.objects.get(id=old_session.id)


class AdminInterfaceTestCase(ConversationalOnboardingBaseTestCase):
    """Test admin interface functionality"""

    def test_people_capability_management(self):
        """Test people capability management in admin"""
        from apps.onboarding_api.admin import PeopleConversationalOnboardingAdmin

        admin_instance = PeopleConversationalOnboardingAdmin(
            model=User,
            admin_site=Mock()
        )

        # Test capability display methods
        onboarding_status = admin_instance.onboarding_enabled(self.user)
        self.assertIn('Enabled', str(onboarding_status))

        approver_status = admin_instance.approver_status(self.user)
        self.assertIn('—', str(approver_status))  # Should show no approver capability

        # Test with approver user
        approver_status = admin_instance.approver_status(self.approver_user)
        self.assertIn('Approver', str(approver_status))


class IntegrationTestCase(ConversationalOnboardingBaseTestCase):
    """Integration tests for complete workflows"""

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True)
    def test_complete_onboarding_workflow(self):
        """Test complete onboarding workflow from start to approval"""
        # 1. Start conversation
        start_url = reverse('onboarding_api:conversation-start')
        start_data = {'language': 'en'}

        start_response = self.client.post(start_url, start_data, format='json')
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)

        conversation_id = start_response.data['conversation_id']

        # 2. Check status
        status_url = reverse('onboarding_api:conversation-status', kwargs={'conversation_id': conversation_id})
        status_response = self.client.get(status_url)
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)

        # 3. Verify session exists
        session = ConversationSession.objects.get(session_id=conversation_id)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.client, self.client_model)

    def test_error_handling_and_logging(self):
        """Test error handling and security logging"""
        # Test with invalid data
        url = reverse('onboarding_api:conversation-start')
        invalid_data = {'invalid_field': 'invalid_value'}

        with self.assertLogs('django', level='ERROR'):
            response = self.client.post(url, invalid_data, format='json')

        # Should handle error gracefully
        self.assertIn(response.status_code, [400, 403, 500])


class PerformanceTestCase(ConversationalOnboardingBaseTestCase):
    """Performance and load testing"""

    def test_concurrent_session_creation_performance(self):
        """Test performance under concurrent load"""
        from threading import Thread
        import time

        results = []

        def create_session():
            start_time = time.time()
            try:
                url = reverse('onboarding_api:conversation-start')
                data = {'language': 'en'}

                with override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True):
                    response = self.client.post(url, data, format='json')

                results.append({
                    'status_code': response.status_code,
                    'duration': time.time() - start_time,
                    'success': response.status_code in [201, 409]  # 409 is expected for concurrent requests
                })
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                results.append({
                    'error': str(e),
                    'duration': time.time() - start_time,
                    'success': False
                })

        # Create multiple threads to test concurrency
        threads = []
        for _ in range(5):
            thread = Thread(target=create_session)
            threads.append(thread)

        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        total_duration = time.time() - start_time

        # Verify results
        self.assertEqual(len(results), 5)
        successful_results = [r for r in results if r['success']]
        self.assertGreaterEqual(len(successful_results), 1)  # At least one should succeed

        # Performance assertion - should complete within reasonable time
        self.assertLess(total_duration, 10.0)  # 10 seconds max for 5 concurrent requests


# Test configuration for different environments
class TestConfiguration:
    """Test configuration for different environments"""

    @staticmethod
    def get_test_settings():
        """Get test-specific Django settings"""
        return {
            'ENABLE_CONVERSATIONAL_ONBOARDING': True,
            'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER': False,  # Disable LLM for tests
            'ENABLE_ONBOARDING_KB': False,  # Disable KB for tests
            'CACHE_TIMEOUT': 1,  # Short timeout for tests
            'DATABASES': {
                'default': {
                    'ENGINE': 'django.contrib.gis.db.backends.postgis',
                    'NAME': ':memory:',
                }
            }
        }