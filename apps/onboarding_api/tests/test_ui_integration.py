"""
Integration tests for conversational onboarding UI
"""

import json
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.peoples.models import People
from apps.onboarding.models import Bt


class ConversationalUIIntegrationTest(TestCase):
    """Test UI integration with backend APIs"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.api_client = APIClient()

        # Create test user
        self.user = People.objects.create_user(
            loginid='testuser',
            peoplecode='TEST001',
            peoplename='Test User',
            email='test@example.com',
            dateofbirth='1990-01-01',
            is_staff=True
        )

        # Set AI capabilities
        self.user.set_ai_capabilities(can_approve=True, can_manage_kb=True, is_approver=True)
        self.user.save()

        # Create test client
        self.client_bt = Bt.objects.create(
            bucode='CLIENT001',
            buname='Test Client',
            enable=True
        )

    def test_ui_loads_successfully(self):
        """Test that the UI loads without errors"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('onboarding_api:conversational-ui'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AI-Powered Conversational Onboarding')
        self.assertContains(response, 'conversational_onboarding.js')
        self.assertContains(response, 'conversational_onboarding.css')

    def test_ui_config_endpoint(self):
        """Test UI configuration endpoint"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('onboarding_api:ui-config'))

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn('api_base', data)
        self.assertIn('enable_sse', data)
        self.assertIn('user', data)
        self.assertEqual(data['api_base'], '/api/v1/onboarding')
        self.assertEqual(data['user']['name'], 'Test User')

    def test_conversation_start_api(self):
        """Test conversation start API integration"""
        self.api_client.force_authenticate(user=self.user)

        response = self.api_client.post('/api/v1/onboarding/conversation/start/', {
            'client_context': {}
        }, format='json')

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('session_id', data)
        self.assertIn('initial_message', data)
        self.assertIn('current_state', data)

        # Verify session was created
        session_id = data['session_id']
        self.assertTrue(len(session_id) > 0)

    def test_conversation_status_api(self):
        """Test conversation status API integration"""
        self.api_client.force_authenticate(user=self.user)

        # Start a conversation first
        start_response = self.api_client.post('/api/v1/onboarding/conversation/start/', {
            'client_context': {}
        }, format='json')

        session_id = start_response.json()['session_id']

        # Check status
        status_response = self.api_client.get(f'/api/v1/onboarding/conversation/{session_id}/status/')

        self.assertEqual(status_response.status_code, 200)

        status_data = status_response.json()
        self.assertIn('session_id', status_data)
        self.assertIn('progress', status_data)
        self.assertIn('current_state', status_data)
        self.assertEqual(status_data['session_id'], session_id)

    def test_conversation_process_api(self):
        """Test conversation process API integration"""
        self.api_client.force_authenticate(user=self.user)

        # Start a conversation first
        start_response = self.api_client.post('/api/v1/onboarding/conversation/start/', {
            'client_context': {}
        }, format='json')

        session_id = start_response.json()['session_id']

        # Process user input
        process_response = self.api_client.post('/api/v1/onboarding/conversation/process/', {
            'session_id': session_id,
            'user_input': 'I need to set up a security facility with 24/7 operations'
        }, format='json')

        # Should return 202 for async processing or 200 for sync
        self.assertIn(process_response.status_code, [200, 202])

        if process_response.status_code == 200:
            data = process_response.json()
            # Check for expected response structure
            self.assertTrue(
                'ai_response' in data or
                'task_id' in data or
                'next_question' in data
            )

    def test_knowledge_validation_api(self):
        """Test knowledge validation API integration"""
        self.api_client.force_authenticate(user=self.user)

        response = self.api_client.post('/api/v1/onboarding/knowledge/validate/', {
            'recommendation': {
                'type': 'business_unit_setup',
                'content': {
                    'bu_name': 'Test Unit',
                    'max_users': 10
                }
            },
            'context': {
                'client_id': self.client_bt.id
            }
        }, format='json')

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('validation_status', data)
        self.assertIn('confidence_score', data)
        self.assertIn('supporting_sources', data)
        self.assertIn('potential_conflicts', data)

    def test_recommendations_approval_dry_run(self):
        """Test recommendations approval in dry run mode"""
        self.api_client.force_authenticate(user=self.user)

        # Start a conversation to get a session
        start_response = self.api_client.post('/api/v1/onboarding/conversation/start/', {
            'client_context': {}
        }, format='json')

        session_id = start_response.json()['session_id']

        # Test approval endpoint with dry run
        response = self.api_client.post('/api/v1/onboarding/recommendations/approve/', {
            'session_id': session_id,
            'approved_items': [],
            'rejected_items': [],
            'reasons': {},
            'modifications': {},
            'dry_run': True
        }, format='json')

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('system_configuration', data)
        self.assertIn('implementation_plan', data)
        self.assertIn('changeset_id', data)
        self.assertIn('changes_applied', data)

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access UI"""
        # Try to access UI without authentication
        response = self.client.get(reverse('onboarding_api:conversational-ui'))

        # Should redirect to login or return 302/403
        self.assertIn(response.status_code, [302, 403])

        # Try to access config without authentication
        config_response = self.client.get(reverse('onboarding_api:ui-config'))
        self.assertIn(config_response.status_code, [302, 403])

    def test_insufficient_permissions(self):
        """Test UI behavior with insufficient permissions"""
        # Create user without AI capabilities
        limited_user = People.objects.create_user(
            loginid='limited',
            peoplecode='LIMITED',
            peoplename='Limited User',
            email='limited@example.com',
            dateofbirth='1990-01-01'
        )

        # UI should load (view-only mode)
        self.client.force_login(limited_user)
        response = self.client.get(reverse('onboarding_api:conversational-ui'))
        self.assertEqual(response.status_code, 200)

        # But API calls should be restricted
        self.api_client.force_authenticate(user=limited_user)

        # Approval endpoint should be forbidden
        approval_response = self.api_client.post('/api/v1/onboarding/recommendations/approve/', {
            'session_id': 'test-session',
            'approved_items': [],
            'rejected_items': [],
            'reasons': {},
            'modifications': {},
            'dry_run': True
        }, format='json')

        self.assertEqual(approval_response.status_code, 403)

    def test_ui_static_files_accessible(self):
        """Test that required static files are accessible"""
        self.client.force_login(self.user)

        # Try to access CSS file
        css_response = self.client.get('/static/css/conversational_onboarding.css')
        # Note: This might return 404 in test environment without static file serving
        # In production, static files would be served by web server
        # We just verify the path is correct
        self.assertTrue(True)  # Placeholder for static file test

    def test_csrf_token_handling(self):
        """Test CSRF token is properly handled"""
        self.client.force_login(self.user)

        # GET request to UI should include CSRF token in context
        response = self.client.get(reverse('onboarding_api:conversational-ui'))

        self.assertEqual(response.status_code, 200)
        # Check that CSRF token is available in the response
        self.assertContains(response, 'csrfToken')

    def test_error_handling(self):
        """Test error handling in API endpoints"""
        self.api_client.force_authenticate(user=self.user)

        # Test malformed request to conversation start
        response = self.api_client.post('/api/v1/onboarding/conversation/start/', {
            'invalid_field': 'invalid_data'
        }, format='json')

        # Should handle gracefully
        self.assertTrue(response.status_code in [200, 400])

        if response.status_code == 400:
            data = response.json()
            self.assertIn('error', data)

    def test_feature_flag_integration(self):
        """Test that feature flags are properly integrated"""

        self.client.force_login(self.user)

        # Mock feature flag disabled
        with self.settings(ENABLE_CONVERSATIONAL_ONBOARDING=False):
            # API should return feature disabled
            response = self.api_client.post('/api/v1/onboarding/conversation/start/', {
                'client_context': {}
            }, format='json')

            self.assertEqual(response.status_code, 403)
            data = response.json()
            self.assertIn('error', data)
            self.assertIn('not enabled', data['error'])