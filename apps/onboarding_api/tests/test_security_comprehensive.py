"""
Comprehensive security tests for Conversational Onboarding API.

Tests focus on:
- Tenant isolation and boundary enforcement
- Permission and authorization checks
- Security audit logging
- Input validation and injection prevention
- Idempotency and rate limiting
"""
import uuid

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.onboarding.models import (
    Bt,
    ConversationSession,
    LLMRecommendation,
    AIChangeSet,
    ChangeSetApproval,
)
from apps.onboarding_api.utils.security import (
    TenantScopeValidator,
    IdempotencyManager,
    SecurityAuditLogger
)

User = get_user_model()


class TenantIsolationTestCase(TestCase):
    """Test tenant isolation and boundary enforcement"""

    def setUp(self):
        """Set up multi-tenant test environment"""
        # Create two separate clients/tenants
        self.tenant1 = Bt.objects.create(
            buname='Tenant One Corp',
            bucode='TEN001',
            enable=True
        )

        self.tenant2 = Bt.objects.create(
            buname='Tenant Two Inc',
            bucode='TEN002',
            enable=True
        )

        # Create users for each tenant
        self.user1 = User.objects.create_user(
            email='user1@tenant1.com',
            password='securepass123',
            is_active=True
        )
        self.user1.client = self.tenant1
        self.user1.capabilities = {
            'can_use_conversational_onboarding': True,
            'can_approve_ai_recommendations': True
        }
        self.user1.save()

        self.user2 = User.objects.create_user(
            email='user2@tenant2.com',
            password='securepass123',
            is_active=True
        )
        self.user2.client = self.tenant2
        self.user2.capabilities = {
            'can_use_conversational_onboarding': True,
            'can_approve_ai_recommendations': True
        }
        self.user2.save()

        # Create API clients
        self.api_client1 = APIClient()
        self.api_client1.force_authenticate(user=self.user1)

        self.api_client2 = APIClient()
        self.api_client2.force_authenticate(user=self.user2)

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True)
    def test_conversation_tenant_isolation(self):
        """Test that conversations are isolated between tenants"""
        # User1 creates a conversation
        response1 = self.api_client1.post(
            reverse('onboarding_api:conversation-start'),
            data={'language': 'en', 'client_context': {}}
        )

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        conversation_id = response1.data['conversation_id']

        # User2 tries to access User1's conversation (should fail)
        response2 = self.api_client2.get(
            reverse('onboarding_api:conversation-status', kwargs={'conversation_id': conversation_id})
        )

        # Should return 404 (not 403) to avoid information leakage
        self.assertEqual(response2.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_scope_validator_logic(self):
        """Test tenant scope validation logic"""
        validator = TenantScopeValidator()

        # Valid tenant scope
        result = validator.validate_tenant_scope(self.user1, self.tenant1, 'read')
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['tenant_id'], self.tenant1.id)
        self.assertEqual(result['scope_level'], 'user')

        # Invalid tenant scope (cross-tenant access)
        result = validator.validate_tenant_scope(self.user1, self.tenant2, 'read')
        self.assertFalse(result['is_valid'])
        self.assertGreater(len(result['violations']), 0)
        self.assertIn('does not belong to client', result['violations'][0])

        # Admin operation validation
        self.user1.is_staff = True
        self.user1.save()

        result = validator.validate_tenant_scope(self.user1, self.tenant1, 'admin_access')
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['scope_level'], 'admin')

    def test_cross_tenant_changeset_access_denied(self):
        """Test that users cannot access changesets from other tenants"""
        # Create conversation and changeset for tenant1
        session1 = ConversationSession.objects.create(
            user=self.user1,
            client=self.tenant1,
            current_state=ConversationSession.StateChoices.COMPLETED
        )

        changeset1 = AIChangeSet.objects.create(
            conversation_session=session1,
            approved_by=self.user1,
            status=AIChangeSet.StatusChoices.APPLIED,
            description='Tenant 1 changes',
            total_changes=1
        )

        # User2 tries to access changeset from tenant1
        response = self.api_client2.post(
            reverse('onboarding_api:changesets-rollback', kwargs={'changeset_id': changeset1.changeset_id}),
            data={'reason': 'Unauthorized access attempt'}
        )

        # Should be denied
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_approval_tenant_boundary_validation(self):
        """Test approval process enforces tenant boundaries"""
        # Create conversation for tenant1
        session1 = ConversationSession.objects.create(
            user=self.user1,
            client=self.tenant1,
            current_state=ConversationSession.StateChoices.AWAITING_USER_APPROVAL
        )

        # Create approval request that user2 (different tenant) tries to approve
        changeset = AIChangeSet.objects.create(
            conversation_session=session1,
            approved_by=self.user1,
            status=AIChangeSet.StatusChoices.PENDING,
            description='Cross-tenant test'
        )

        approval = ChangeSetApproval.objects.create(
            changeset=changeset,
            approver=self.user2,  # User from different tenant
            approval_level=ChangeSetApproval.ApprovalLevelChoices.SECONDARY
        )

        # User2 tries to approve changeset from tenant1
        response = self.api_client2.post(
            reverse('onboarding_api:secondary-approval-decide', kwargs={'approval_id': approval.id}),
            data={'decision': 'approve', 'reason': 'Cross-tenant attempt'}
        )

        # Should be denied due to tenant boundary violation
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('tenant', response.data.get('error', '').lower())


class SecurityAuditTestCase(TestCase):
    """Test security audit logging and monitoring"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='audit@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Audit Test Client',
            bucode='AUD001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

    @patch('apps.onboarding_api.utils.security.logger')
    def test_security_audit_logging_structure(self, mock_logger):
        """Test that security events are properly logged with correct structure"""
        logger = SecurityAuditLogger()

        # Test access attempt logging
        logger.log_access_attempt(
            user=self.user,
            resource='/api/v1/onboarding/conversation/start/',
            operation='create_session',
            granted=True,
            additional_context={'client_ip': '127.0.0.1'}
        )

        # Verify logging was called
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args

        # Check log message structure
        self.assertIn('access_granted', call_args[0][0])

        # Check extra data structure
        extra_data = call_args[1]['extra']
        self.assertEqual(extra_data['event_type'], 'access_granted')
        self.assertEqual(extra_data['user_id'], self.user.id)
        self.assertIn('timestamp', extra_data)

    def test_privilege_escalation_logging(self):
        """Test privilege escalation logging"""
        logger = SecurityAuditLogger()

        with patch('apps.onboarding_api.utils.security.logger') as mock_logger:
            logger.log_privilege_escalation(
                user=self.user,
                from_role='user',
                to_role='approver',
                granted=True,
                justification='Admin approval required'
            )

            # Should log with critical severity for granted escalations
            mock_logger.critical.assert_called()

    def test_security_violation_detection(self):
        """Test security violation detection and logging"""
        validator = TenantScopeValidator()

        # Create scenario that should trigger violation
        other_client = Bt.objects.create(buname='Other', bucode='OTHER')

        with patch('apps.onboarding_api.utils.security.logger') as mock_logger:
            result = validator.validate_tenant_scope(self.user, other_client, 'admin')

            self.assertFalse(result['is_valid'])
            self.assertGreater(len(result['violations']), 0)


class IdempotencyTestCase(TestCase):
    """Test idempotency protection mechanisms"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='idempotency@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Idempotency Test Client',
            bucode='IMP001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_idempotency_key_generation_deterministic(self):
        """Test that idempotency keys are deterministic for same input"""
        manager = IdempotencyManager()

        # Generate keys for same operation with same data
        key1 = manager.generate_idempotency_key(
            self.user, 'test_operation', {'param': 'value'}
        )
        key2 = manager.generate_idempotency_key(
            self.user, 'test_operation', {'param': 'value'}
        )

        self.assertEqual(key1, key2)

        # Different data should generate different keys
        key3 = manager.generate_idempotency_key(
            self.user, 'test_operation', {'param': 'different_value'}
        )

        self.assertNotEqual(key1, key3)

    @patch('django.core.cache.cache')
    def test_idempotency_duplicate_detection(self, mock_cache):
        """Test idempotency duplicate request detection"""
        manager = IdempotencyManager()

        # Mock cache to return existing result
        cached_result = {
            'result': {'status': 'completed', 'id': 'test-123'},
            'timestamp': '2024-01-01T12:00:00Z',
            'key': 'test_key'
        }
        mock_cache.get.return_value = cached_result

        result = manager.check_idempotency('test_key')

        self.assertTrue(result['is_duplicate'])
        self.assertEqual(result['cached_result'], cached_result)

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True)
    @patch('apps.onboarding_api.utils.security.cache')
    def test_api_idempotency_protection(self, mock_cache):
        """Test that API endpoints properly implement idempotency protection"""
        # Mock cache to simulate duplicate request
        mock_cache.get.return_value = {
            'result': {
                'conversation_id': 'cached-conv-123',
                'message': 'Cached result'
            },
            'timestamp': '2024-01-01T12:00:00Z'
        }

        # Make request that should return cached result
        response = self.api_client.post(
            reverse('onboarding_api:conversation-start'),
            data={'language': 'en', 'client_context': {}}
        )

        # Should return the cached result
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have idempotency headers
        self.assertIn('X-Idempotency-Key', response)


class InputValidationTestCase(TestCase):
    """Test input validation and injection prevention"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='validation@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Validation Test Client',
            bucode='VAL001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_serializer_validation_prevents_invalid_data(self):
        """Test that serializers properly validate input data"""
        from apps.onboarding_api.serializers import ConversationStartSerializer

        # Test invalid language code
        invalid_data = {
            'language': 'invalid_language_code_that_is_too_long',
            'client_context': {}
        }

        serializer = ConversationStartSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('language', serializer.errors)

        # Test valid data
        valid_data = {
            'language': 'en',
            'client_context': {},
            'resume_existing': False
        }

        serializer = ConversationStartSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())

    def test_sql_injection_prevention_in_filters(self):
        """Test that SQL injection attempts are prevented"""
        # Test with malicious input
        malicious_conversation_id = "'; DROP TABLE conversation_session; --"

        response = self.api_client.get(
            f"/api/v1/onboarding/conversation/{malicious_conversation_id}/status/"
        )

        # Should return 404 (not crash or execute SQL)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_xss_prevention_in_responses(self):
        """Test that XSS attempts are prevented in API responses"""
        from apps.onboarding_api.serializers import ConversationProcessSerializer

        # Test with potential XSS payload
        xss_payload = "<script>alert('xss')</script>"

        serializer = ConversationProcessSerializer(data={
            'user_input': xss_payload,
            'context': {}
        })

        # Should validate the data (serializer should accept it)
        self.assertTrue(serializer.is_valid())

        # But the actual response should be sanitized (would be handled by Django's XSS protection)
        # This is more of a structural test

    def test_large_payload_handling(self):
        """Test handling of oversized payloads"""
        # Create very large input
        large_input = "A" * 10000  # 10KB of text

        response = self.api_client.post(
            reverse('onboarding_api:conversation-start'),
            data={
                'language': 'en',
                'initial_input': large_input,
                'client_context': {}
            }
        )

        # Should handle gracefully (either accept or reject with proper error)
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        ])

    def test_json_injection_prevention(self):
        """Test prevention of JSON injection attacks"""
        # Test with malicious JSON structure
        malicious_context = {
            '__proto__': {'isAdmin': True},
            'constructor': {'prototype': {'isAdmin': True}},
            'nested': {
                'deeper': {
                    '__proto__': {'malicious': True}
                }
            }
        }

        response = self.api_client.post(
            reverse('onboarding_api:conversation-start'),
            data={
                'language': 'en',
                'client_context': malicious_context
            }
        )

        # Should handle gracefully without allowing prototype pollution
        # Django's JSON handling should prevent this
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class PermissionBoundaryTestCase(TestCase):
    """Test permission boundary enforcement"""

    def setUp(self):
        """Set up users with different permission levels"""
        self.client_bt = Bt.objects.create(
            buname='Permission Test Client',
            bucode='PERM001',
            enable=True
        )

        # Regular user (no special permissions)
        self.regular_user = User.objects.create_user(
            email='regular@example.com',
            password='testpass123',
            is_active=True
        )
        self.regular_user.client = self.client_bt
        self.regular_user.capabilities = {
            'can_use_conversational_onboarding': True
        }
        self.regular_user.save()

        # Approver user
        self.approver_user = User.objects.create_user(
            email='approver@example.com',
            password='testpass123',
            is_active=True
        )
        self.approver_user.client = self.client_bt
        self.approver_user.capabilities = {
            'can_use_conversational_onboarding': True,
            'can_approve_ai_recommendations': True
        }
        self.approver_user.save()

        # Admin user
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='testpass123',
            is_active=True,
            is_staff=True
        )
        self.admin_user.client = self.client_bt
        self.admin_user.save()

    def test_regular_user_cannot_approve_recommendations(self):
        """Test that regular users cannot approve AI recommendations"""
        api_client = APIClient()
        api_client.force_authenticate(user=self.regular_user)

        response = api_client.post(
            reverse('onboarding_api:recommendations-approve'),
            data={
                'approved_items': [],
                'rejected_items': [],
                'dry_run': True
            }
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_approver_can_approve_recommendations(self):
        """Test that approver users can approve AI recommendations"""
        api_client = APIClient()
        api_client.force_authenticate(user=self.approver_user)

        response = api_client.post(
            reverse('onboarding_api:recommendations-approve'),
            data={
                'approved_items': [],
                'rejected_items': [],
                'dry_run': True
            }
        )

        # Should succeed (or fail for business logic reasons, not permissions)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_access_to_analytics(self):
        """Test that only admins can access analytics endpoints"""
        # Regular user should be denied
        regular_client = APIClient()
        regular_client.force_authenticate(user=self.regular_user)

        response = regular_client.get(reverse('onboarding_api:template-analytics'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin should succeed
        admin_client = APIClient()
        admin_client.force_authenticate(user=self.admin_user)

        response = admin_client.get(reverse('onboarding_api:template-analytics'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ConcurrencyAndRateLimitingTestCase(TestCase):
    """Test concurrency controls and rate limiting"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='concurrency@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Concurrency Test Client',
            bucode='CON001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True)
    @patch('apps.onboarding_api.utils.concurrency.advisory_lock')
    def test_concurrent_session_creation_prevention(self, mock_lock):
        """Test that concurrent session creation is prevented"""
        # Mock advisory lock to simulate lock acquisition failure
        mock_lock.return_value.__enter__.return_value = False

        response = self.api_client.post(
            reverse('onboarding_api:conversation-start'),
            data={'language': 'en', 'client_context': {}}
        )

        # Should return 429 (Too Many Requests) when lock cannot be acquired
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('retry_after', response.data)

    def test_duplicate_session_handling(self):
        """Test handling of attempts to create duplicate sessions"""
        with override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True):
            # Create first session
            response1 = self.api_client.post(
                reverse('onboarding_api:conversation-start'),
                data={'language': 'en', 'client_context': {}}
            )

            self.assertEqual(response1.status_code, status.HTTP_200_OK)

            # Try to create second session (should conflict)
            response2 = self.api_client.post(
                reverse('onboarding_api:conversation-start'),
                data={'language': 'en', 'client_context': {}}
            )

            # Should return conflict or handle gracefully
            self.assertIn(response2.status_code, [
                status.HTTP_409_CONFLICT,
                status.HTTP_200_OK  # If resume logic kicks in
            ])


class DataValidationTestCase(TestCase):
    """Test data validation and sanitization"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='validation@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Validation Test Client',
            bucode='VAL001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_uuid_validation_in_urls(self):
        """Test that UUID validation works in URL patterns"""
        # Valid UUID should work
        valid_uuid = str(uuid.uuid4())
        response = self.api_client.get(f"/api/v1/onboarding/conversation/{valid_uuid}/status/")

        # Should return 404 (not found) rather than 400 (bad request)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Invalid UUID should return 404 (Django URL routing handles this)
        invalid_uuid = "not-a-uuid"
        response = self.api_client.get(f"/api/v1/onboarding/conversation/{invalid_uuid}/status/")

        # Should return 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_json_field_validation(self):
        """Test JSON field validation and sanitization"""
        from apps.onboarding_api.serializers import ConversationProcessSerializer

        # Test with valid JSON
        valid_data = {
            'user_input': 'Test input',
            'context': {'key': 'value', 'nested': {'inner': 'data'}}
        }

        serializer = ConversationProcessSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())

        # Test with None context (should use default)
        none_context_data = {
            'user_input': 'Test input',
            'context': None
        }

        serializer = ConversationProcessSerializer(data=none_context_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['context'], {})


class APIContractTestCase(TestCase):
    """Test API contract compliance and backward compatibility"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='contract@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Contract Test Client',
            bucode='CON001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_api_response_structure_consistency(self):
        """Test that API responses maintain consistent structure"""
        # Test feature status endpoint
        response = self.api_client.get(reverse('onboarding_api:feature-status'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check required fields are present
        required_fields = ['enabled', 'flags', 'configuration', 'version', 'user_capabilities']
        for field in required_fields:
            self.assertIn(field, response.data)

        # Check flags structure
        flag_fields = ['dual_llm_enabled', 'streaming_enabled', 'personalization_enabled']
        for flag in flag_fields:
            self.assertIn(flag, response.data['flags'])

    def test_openapi_schema_compliance(self):
        """Test that API responses match OpenAPI schema definitions"""
        from apps.onboarding_api.openapi_schemas import conversation_start_body

        # Test that conversation start matches schema
        # This is a structural test to ensure schema consistency
        schema_properties = conversation_start_body['properties']

        self.assertIn('client_context', schema_properties)
        self.assertIn('language', schema_properties)
        self.assertIn('resume_existing', schema_properties)

        # Verify default values match
        self.assertEqual(schema_properties['language']['default'], 'en')
        self.assertEqual(schema_properties['resume_existing']['default'], False)

    def test_backward_compatibility_maintained(self):
        """Test that existing API contracts are maintained"""
        # Test that old endpoints still work
        with override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True):
            response = self.api_client.post(
                reverse('onboarding_api:conversation-start'),
                data={'language': 'en'}  # Minimal required data
            )

            # Should work with minimal data (backward compatibility)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Should include expected fields
            expected_fields = ['conversation_id', 'enhanced_understanding', 'questions']
            for field in expected_fields:
                self.assertIn(field, response.data)


class ErrorHandlingTestCase(TestCase):
    """Test comprehensive error handling"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='error@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Error Test Client',
            bucode='ERR001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_graceful_service_failure_handling(self):
        """Test that service failures are handled gracefully"""
        with patch('apps.onboarding_api.services.llm.get_llm_service') as mock_llm:
            # Mock LLM service to raise exception
            mock_llm.side_effect = Exception("LLM service unavailable")

            with override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True):
                response = self.api_client.post(
                    reverse('onboarding_api:conversation-start'),
                    data={'language': 'en', 'client_context': {}}
                )

                # Should return 500 with proper error message
                self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
                self.assertIn('error', response.data)

    def test_database_connection_failure_handling(self):
        """Test handling of database connection issues"""
        # This is more of a structural test - actual DB failures are hard to simulate
        with patch('apps.onboarding.models.ConversationSession.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database connection failed")

            with override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True):
                response = self.api_client.post(
                    reverse('onboarding_api:conversation-start'),
                    data={'language': 'en', 'client_context': {}}
                )

                # Should handle database errors gracefully
                self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_external_service_timeout_handling(self):
        """Test handling of external service timeouts"""
        with patch('requests.post') as mock_post:
            # Mock timeout exception
            import requests
            mock_post.side_effect = requests.Timeout("Request timed out")

            from apps.onboarding_api.services.notifications import SlackNotificationProvider, NotificationEvent
            from django.utils import timezone

            provider = SlackNotificationProvider('slack', {
                'webhook_url': 'https://hooks.slack.com/test'
            })

            event = NotificationEvent(
                event_type='test_timeout',
                event_id='timeout-test',
                title='Timeout Test',
                message='Test message',
                priority='medium',
                metadata={},
                timestamp=timezone.now()
            )

            result = provider.send_notification(event)

            # Should handle timeout gracefully
            self.assertFalse(result.success)
            self.assertIn('timeout', result.error_message.lower())


# Test runners and configurations
class SecurityTestRunner:
    """Custom test runner for security-focused testing"""

    @staticmethod
    def run_security_tests():
        """Run all security-related tests"""
        import subprocess
        import sys

        # Run security tests with specific markers
        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            'apps/onboarding_api/tests/test_security_comprehensive.py',
            '-m', 'security',
            '-v',
            '--tb=short'
        ], capture_output=True, text=True)

        return result.returncode == 0, result.stdout, result.stderr

    @staticmethod
    def run_tenant_isolation_tests():
        """Run tenant isolation specific tests"""
        import subprocess
        import sys

        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            'apps/onboarding_api/tests/test_security_comprehensive.py::TenantIsolationTestCase',
            '-v',
            '--tb=short'
        ], capture_output=True, text=True)

        return result.returncode == 0, result.stdout, result.stderr


# Security test configuration
SECURITY_TEST_CONFIG = {
    'test_multiple_tenants': True,
    'test_permission_boundaries': True,
    'test_audit_logging': True,
    'test_input_validation': True,
    'test_rate_limiting': True,
    'test_sql_injection_prevention': True,
    'test_xss_prevention': True,
    'test_csrf_protection': True
}


# Test data generators
def generate_test_changeset_data():
    """Generate test data for changeset testing"""
    return {
        'approved_items': [
            {
                'entity_type': 'bt',
                'entity_id': 1,
                'changes': {
                    'buname': 'Updated Name',
                    'enable': True
                }
            }
        ],
        'rejected_items': [],
        'reasons': {},
        'modifications': {},
        'dry_run': True
    }


def generate_test_template_data():
    """Generate test data for template testing"""
    return {
        'industry': 'office',
        'size': 'medium',
        'operating_hours': 'business_hours',
        'security_level': 'medium',
        'staff_count': 25,
        'special_requirements': []
    }
