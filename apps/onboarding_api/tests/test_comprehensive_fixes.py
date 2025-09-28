"""
Comprehensive tests for Conversational Onboarding Module fixes and features
"""
from datetime import timedelta

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.onboarding.models import (
    Bt, ConversationSession, LLMRecommendation, AuthoritativeKnowledge
)
from apps.onboarding.admin import (
    ConversationSessionAdmin, LLMRecommendationAdmin, AuthoritativeKnowledgeAdmin
)
)
from background_tasks.onboarding_tasks import (
    cleanup_old_sessions, cleanup_failed_tasks, archive_completed_sessions
)

User = get_user_model()


class AsyncTaskIDFixTestCase(APITestCase):
    """Test that async task IDs are properly returned for polling"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            capabilities={'can_use_conversational_onboarding': True}
        )
        self.client.force_authenticate(user=self.user)

        # Create client/BT
        self.bt = Bt.objects.create(
            buname='Test Company',
            bucode='TEST001',
            active=True
        )
        self.user.client = self.bt
        self.user.save()

        # Create conversation session
        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.bt,
            conversation_type='initial_setup',
            current_state=ConversationSession.StateChoices.IN_PROGRESS
        )

    @patch('apps.onboarding_api.views.process_conversation_step.delay')
    def test_async_task_returns_celery_id(self, mock_delay):
        """Test that async processing returns actual Celery task ID"""
        # Setup mock
        mock_async_result = Mock()
        mock_async_result.id = 'celery-task-12345'
        mock_delay.return_value = mock_async_result

        url = reverse('onboarding_api:conversation-process', kwargs={
            'conversation_id': str(self.session.session_id)
        })

        # Long input to trigger async processing
        data = {
            'user_input': 'x' * 600,  # Triggers async
            'context': {}
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['task_id'], 'celery-task-12345')
        self.assertIn('friendly_task_id', response.data)
        self.assertIn('/tasks/celery-task-12345/status/', response.data['task_status_url'])


class KnowledgeServiceFixTestCase(TestCase):
    """Test knowledge service initialization and timezone import fixes"""

    @patch('apps.onboarding_api.views.get_knowledge_service')
    def test_knowledge_validation_uses_factory(self, mock_get_service):
        """Test that knowledge validation uses get_knowledge_service factory"""
        # Setup mock
        mock_service = Mock()
        mock_service.validate_recommendation_against_knowledge.return_value = {
            'is_valid': True,
            'confidence_score': 0.85,
            'supporting_sources': [],
            'potential_conflicts': [],
            'recommendations': []
        }
        mock_get_service.return_value = mock_service

        client = APIClient()
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_staff=True
        )
        client.force_authenticate(user=user)

        url = reverse('onboarding_api:knowledge-validate')
        data = {
            'recommendation': {'test': 'data'},
            'context': {}
        }

        response = client.post(url, data, format='json')

        # Verify factory was called
        mock_get_service.assert_called_once()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('validation_timestamp', response.data['validation_details'])


class AdminFieldsFixTestCase(TestCase):
    """Test that admin ModelAdmins use correct model fields"""

    def setUp(self):
        self.site = site
        self.user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )

        # Create test objects
        self.bt = Bt.objects.create(
            buname='Test Company',
            bucode='TEST001',
            active=True
        )

        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.bt,
            language='en',
            conversation_type='initial_setup',
            context_data={'test': 'data'},
            collected_data={'collected': 'data'},
            current_state=ConversationSession.StateChoices.IN_PROGRESS
        )

        self.recommendation = LLMRecommendation.objects.create(
            session=self.session,
            maker_output={'test': 'output'},
            checker_output={'validation': 'result'},
            consensus={'agreed': 'recommendation'},
            authoritative_sources=['source1', 'source2'],
            confidence_score=0.85,
            status='validated',
            trace_id='trace-123'
        )

        self.knowledge = AuthoritativeKnowledge.objects.create(
            source_organization='Test Org',
            document_title='Test Document',
            document_version='1.0',
            authority_level='high',
            content_summary='Test content summary',
            publication_date=timezone.now(),
            is_current=True,
            language='en'
        )

    def test_conversation_session_admin_fields(self):
        """Test ConversationSession admin uses correct fields"""
        admin_obj = ConversationSessionAdmin(ConversationSession, self.site)

        # Check list_display
        self.assertIn('user', admin_obj.list_display)
        self.assertIn('conversation_type', admin_obj.list_display)

        # Check fieldsets reference correct fields
        for fieldset in admin_obj.fieldsets:
            for field in fieldset[1]['fields']:
                if isinstance(field, tuple):
                    for f in field:
                        self.assertTrue(hasattr(self.session, f) or f in ['cuser', 'muser'])
                else:
                    self.assertTrue(hasattr(self.session, field) or field in ['cuser', 'muser'])

    def test_llm_recommendation_admin_fields(self):
        """Test LLMRecommendation admin uses correct fields"""
        admin_obj = LLMRecommendationAdmin(LLMRecommendation, self.site)

        # Check list_display
        self.assertIn('status', admin_obj.list_display)
        self.assertNotIn('recommendation_type', admin_obj.list_display)

        # Check fieldsets reference correct fields
        for fieldset in admin_obj.fieldsets:
            for field in fieldset[1]['fields']:
                if isinstance(field, tuple):
                    for f in field:
                        self.assertTrue(hasattr(self.recommendation, f) or f in ['cuser', 'muser'])
                else:
                    self.assertTrue(hasattr(self.recommendation, field) or field in ['cuser', 'muser'])

    def test_authoritative_knowledge_admin_fields(self):
        """Test AuthoritativeKnowledge admin uses correct fields"""
        admin_obj = AuthoritativeKnowledgeAdmin(AuthoritativeKnowledge, self.site)

        # Check list_display
        self.assertIn('document_title', admin_obj.list_display)
        self.assertIn('source_organization', admin_obj.list_display)
        self.assertNotIn('title', admin_obj.list_display)

        # Check fieldsets reference correct fields
        for fieldset in admin_obj.fieldsets:
            for field in fieldset[1]['fields']:
                if isinstance(field, tuple):
                    for f in field:
                        self.assertTrue(hasattr(self.knowledge, f) or f in ['cuser', 'muser'])
                else:
                    self.assertTrue(hasattr(self.knowledge, field) or field in ['cuser', 'muser'])


class FeatureStatusEndpointTestCase(APITestCase):
    """Test the feature status endpoint"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            capabilities={'can_approve_ai_recommendations': True}
        )
        self.client.force_authenticate(user=self.user)

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True)
    def test_feature_status_endpoint_exists(self):
        """Test that /status/ endpoint exists and returns expected data"""
        url = reverse('onboarding_api:feature-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('enabled', response.data)
        self.assertIn('flags', response.data)
        self.assertIn('configuration', response.data)
        self.assertIn('version', response.data)
        self.assertIn('user_capabilities', response.data)

        # Check feature flags
        self.assertIn('dual_llm_enabled', response.data['flags'])
        self.assertIn('streaming_enabled', response.data['flags'])
        self.assertIn('personalization_enabled', response.data['flags'])

        # Check user capabilities
        self.assertTrue(response.data['user_capabilities']['can_approve_recommendations'])


class UICompatibilityLayerTestCase(APITestCase):
    """Test UI compatibility layer endpoints"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.bt = Bt.objects.create(
            buname='Test Company',
            bucode='TEST001',
            active=True
        )
        self.user.client = self.bt
        self.user.save()

    def test_ui_compat_conversation_start(self):
        """Test UI-compatible conversation start"""
        url = reverse('onboarding_api:conversation-start-ui')
        data = {
            'client': self.bt.id,
            'language': 'en'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('session_id', response.data)
        self.assertIn('initial_message', response.data)
        self.assertIn('questions', response.data)

    @patch('apps.onboarding_api.views_ui_compat.process_conversation_step.delay')
    def test_ui_compat_conversation_process(self, mock_delay):
        """Test UI-compatible conversation process with session_id in body"""
        # Create session
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.bt,
            current_state=ConversationSession.StateChoices.IN_PROGRESS
        )

        # Setup mock
        mock_async_result = Mock()
        mock_async_result.id = 'task-123'
        mock_delay.return_value = mock_async_result

        url = reverse('onboarding_api:conversation-process-ui')
        data = {
            'session_id': str(session.session_id),
            'user_input': 'x' * 600  # Trigger async
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['task_id'], 'task-123')
        self.assertEqual(response.data['session_id'], str(session.session_id))

    @patch('celery.result.AsyncResult')
    def test_ui_compat_task_status(self, mock_async_result):
        """Test UI-compatible task status endpoint"""
        # Setup mock
        mock_result = Mock()
        mock_result.state = 'SUCCESS'
        mock_result.info = {
            'response_text': 'Test response',
            'recommendations': [],
            'next_question': 'Next question?'
        }
        mock_async_result.return_value = mock_result

        url = reverse('onboarding_api:task-status-ui', kwargs={'task_id': 'task-123'})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        self.assertEqual(response.data['progress'], 1.0)
        self.assertIn('result', response.data)


class ChangeSetDiffPreviewTestCase(APITestCase):
    """Test changeset diff preview API"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            capabilities={'can_approve_ai_recommendations': True}
        )
        self.client.force_authenticate(user=self.user)

        self.bt = Bt.objects.create(
            buname='Test Company',
            bucode='TEST001',
            active=True,
            config={'test': 'config'}
        )

    def test_changeset_diff_preview(self):
        """Test changeset diff preview generation"""
        url = reverse('onboarding_api:changeset-preview')
        data = {
            'approved_items': [
                {
                    'entity_type': 'bt',
                    'entity_id': self.bt.id,
                    'changes': {
                        'buname': 'Updated Company',
                        'config': {'updated': 'config'}
                    }
                }
            ],
            'modifications': {}
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('changes', response.data)
        self.assertIn('summary', response.data)

        # Check diff structure
        change = response.data['changes'][0]
        self.assertEqual(change['entity_type'], 'bt')
        self.assertEqual(change['operation'], 'update')
        self.assertIsNotNone(change['before'])
        self.assertIsNotNone(change['after'])
        self.assertGreater(len(change['fields_changed']), 0)


class ConcurrencyGuardTestCase(TransactionTestCase):
    """Test concurrency guard for conversation sessions"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.bt = Bt.objects.create(
            buname='Test Company',
            bucode='TEST001',
            active=True
        )
        self.user.client = self.bt
        self.user.save()

    def test_prevents_duplicate_active_sessions(self):
        """Test that concurrent active sessions are prevented"""
        # Create active session
        active_session = ConversationSession.objects.create(
            user=self.user,
            client=self.bt,
            current_state=ConversationSession.StateChoices.IN_PROGRESS,
            mdtz=timezone.now()
        )

        url = reverse('onboarding_api:conversation-start')
        data = {
            'client_context': {},
            'language': 'en'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('existing_session_id', response.data)
        self.assertEqual(response.data['existing_session_id'], str(active_session.session_id))

    def test_auto_closes_stale_sessions(self):
        """Test that stale sessions are auto-closed"""
        # Create old active session
        old_session = ConversationSession.objects.create(
            user=self.user,
            client=self.bt,
            current_state=ConversationSession.StateChoices.IN_PROGRESS,
            mdtz=timezone.now() - timedelta(hours=1)
        )

        url = reverse('onboarding_api:conversation-start')
        data = {
            'client_context': {},
            'language': 'en'
        }

        response = self.client.post(url, data, format='json')

        # Should succeed and close old session
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check old session was closed
        old_session.refresh_from_db()
        self.assertEqual(old_session.current_state, ConversationSession.StateChoices.CANCELLED)

    def test_resume_existing_session(self):
        """Test resuming existing session"""
        active_session = ConversationSession.objects.create(
            user=self.user,
            client=self.bt,
            current_state=ConversationSession.StateChoices.IN_PROGRESS,
            mdtz=timezone.now()
        )

        url = reverse('onboarding_api:conversation-start')
        data = {
            'client_context': {},
            'language': 'en',
            'resume_existing': True
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['resumed'])
        self.assertEqual(response.data['conversation_id'], str(active_session.session_id))


class CeleryBeatCleanupTasksTestCase(TransactionTestCase):
    """Test Celery Beat cleanup tasks"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.bt = Bt.objects.create(
            buname='Test Company',
            bucode='TEST001',
            active=True
        )

    def test_cleanup_old_sessions(self):
        """Test cleanup of old sessions"""
        # Create old completed session
        old_session = ConversationSession.objects.create(
            user=self.user,
            client=self.bt,
            current_state=ConversationSession.StateChoices.COMPLETED,
            mdtz=timezone.now() - timedelta(days=35)
        )

        # Create recent session (should not be deleted)
        recent_session = ConversationSession.objects.create(
            user=self.user,
            client=self.bt,
            current_state=ConversationSession.StateChoices.COMPLETED,
            mdtz=timezone.now()
        )

        result = cleanup_old_sessions(None, days_old=30)

        self.assertEqual(result['sessions_deleted'], 1)
        self.assertFalse(ConversationSession.objects.filter(id=old_session.id).exists())
        self.assertTrue(ConversationSession.objects.filter(id=recent_session.id).exists())

    def test_cleanup_failed_tasks(self):
        """Test cleanup of failed/stuck tasks"""
        # Create stuck session
        stuck_session = ConversationSession.objects.create(
            user=self.user,
            client=self.bt,
            current_state=ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS,
            mdtz=timezone.now() - timedelta(hours=2)
        )

        result = cleanup_failed_tasks(None)

        self.assertEqual(result['stuck_sessions_reset'], 1)

        stuck_session.refresh_from_db()
        self.assertEqual(stuck_session.current_state, ConversationSession.StateChoices.ERROR)
        self.assertIn('timeout', stuck_session.error_message)

    def test_archive_completed_sessions(self):
        """Test archiving of completed sessions"""
        # Create old completed sessions
        for i in range(5):
            ConversationSession.objects.create(
                user=self.user,
                client=self.bt,
                current_state=ConversationSession.StateChoices.COMPLETED,
                mdtz=timezone.now() - timedelta(days=10)
            )

        result = archive_completed_sessions(None, batch_size=3)

        self.assertEqual(result['sessions_archived'], 3)
        # Check that only 2 sessions remain
        self.assertEqual(ConversationSession.objects.count(), 2)


class IntegrationTestCase(APITestCase):
    """Integration tests for the complete flow"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            capabilities={'can_approve_ai_recommendations': True}
        )
        self.client.force_authenticate(user=self.user)

        self.bt = Bt.objects.create(
            buname='Test Company',
            bucode='TEST001',
            active=True
        )
        self.user.client = self.bt
        self.user.save()

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True)
    def test_complete_conversation_flow(self):
        """Test complete conversation flow from start to finish"""
        # 1. Check feature status
        status_url = reverse('onboarding_api:feature-status')
        status_response = self.client.get(status_url)
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertTrue(status_response.data['enabled'])

        # 2. Start conversation
        start_url = reverse('onboarding_api:conversation-start')
        start_data = {'client_context': {}, 'language': 'en'}
        start_response = self.client.post(start_url, start_data, format='json')
        self.assertEqual(start_response.status_code, status.HTTP_200_OK)
        conversation_id = start_response.data['conversation_id']

        # 3. Process conversation (sync mode for short input)
        process_url = reverse('onboarding_api:conversation-process',
                             kwargs={'conversation_id': conversation_id})
        process_data = {'user_input': 'Test input', 'context': {}}

        with patch('apps.onboarding_api.views.get_llm_service') as mock_llm:
            mock_service = Mock()
            mock_service.process_conversation_step.return_value = {
                'recommendations': [{'test': 'recommendation'}],
                'confidence_score': 0.9,
                'next_steps': ['step1']
            }
            mock_llm.return_value = mock_service

            process_response = self.client.post(process_url, process_data, format='json')
            self.assertEqual(process_response.status_code, status.HTTP_200_OK)

        # 4. Check conversation status
        status_url = reverse('onboarding_api:conversation-status',
                           kwargs={'conversation_id': conversation_id})
        status_response = self.client.get(status_url)
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertIn('state', status_response.data)

        # 5. Preview changes
        preview_url = reverse('onboarding_api:changeset-preview')
        preview_data = {
            'approved_items': [{
                'entity_type': 'bt',
                'entity_id': self.bt.id,
                'changes': {'buname': 'Updated Name'}
            }],
            'modifications': {}
        }
        preview_response = self.client.post(preview_url, preview_data, format='json')
        self.assertEqual(preview_response.status_code, status.HTTP_200_OK)
        self.assertIn('changes', preview_response.data)

    def test_ui_compatibility_flow(self):
        """Test UI compatibility layer flow"""
        # Start with UI-compatible endpoint
        start_url = reverse('onboarding_api:conversation-start-ui')
        start_data = {'client': self.bt.id, 'language': 'en'}
        start_response = self.client.post(start_url, start_data, format='json')

        self.assertEqual(start_response.status_code, status.HTTP_200_OK)
        self.assertIn('session_id', start_response.data)
        self.assertIn('initial_message', start_response.data)

        session_id = start_response.data['session_id']

        # Process with UI-compatible endpoint
        process_url = reverse('onboarding_api:conversation-process-ui')
        process_data = {
            'session_id': session_id,
            'user_input': 'Test input'
        }

        with patch('apps.onboarding_api.views_ui_compat.get_llm_service') as mock_llm:
            mock_service = Mock()
            mock_service.process_conversation_step.return_value = {
                'response_text': 'Test response',
                'recommendations': [],
                'next_question': 'Next?'
            }
            mock_llm.return_value = mock_service

            process_response = self.client.post(process_url, process_data, format='json')
            self.assertEqual(process_response.status_code, status.HTTP_200_OK)
            self.assertIn('ai_response', process_response.data)


if __name__ == '__main__':
    import django
    django.setup()
    import unittest
    unittest.main()