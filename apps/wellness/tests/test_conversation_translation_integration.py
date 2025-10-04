"""
Integration Tests for Conversation Translation Feature

Comprehensive tests to verify the complete translation functionality works correctly,
including service layer, database caching, API endpoints, and UI integration.
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.tenants.models import Tenant
from apps.wellness.models.wisdom_conversations import WisdomConversation, ConversationThread
from apps.wellness.models.conversation_translation import WisdomConversationTranslation, TranslationQualityFeedback
from apps.wellness.services.conversation_translation_service import ConversationTranslationService
from apps.wellness.tasks import translate_conversation_async

User = get_user_model()


class ConversationTranslationIntegrationTest(TestCase):
    """Integration tests for the complete translation feature"""

    def setUp(self):
        """Set up test data"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            domain="test.com"
        )

        # Create test user with preferred language
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplename="Test User",
            peoplecode="TEST001",
            email="test@test.com",
            preferred_language="hi",
            tenant=self.tenant
        )

        # Create conversation thread
        self.thread = ConversationThread.objects.create(
            user=self.user,
            thread_type="gratitude_practice",
            tenant=self.tenant
        )

        # Create sample conversation
        self.conversation = WisdomConversation.objects.create(
            user=self.user,
            thread=self.thread,
            conversation_text="I'm grateful for the support from my team today. It made a challenging project much easier to handle.",
            conversation_tone="warm",
            source_type="user_input",
            tenant=self.tenant
        )

    def test_translation_service_basic_functionality(self):
        """Test basic translation service functionality"""
        service = ConversationTranslationService()

        # Mock translation backend response
        mock_response = {
            'success': True,
            'translated_text': 'मैं आज अपनी टीम के समर्थन के लिए आभारी हूं। इसने एक चुनौतीपूर्ण परियोजना को संभालना बहुत आसान बना दिया।',
            'backend_used': 'google',
            'confidence': 0.95,
            'warning': '⚠️ यह बातचीत अंग्रेजी से अनुवादित की गई है। अनुवाद में त्रुटियां हो सकती हैं।',
            'translation_date': timezone.now().isoformat()
        }

        with patch.object(service, '_perform_translation', return_value=mock_response):
            result = service.translate_conversation(
                conversation=self.conversation,
                target_language='hi',
                user=self.user
            )

            self.assertTrue(result['success'])
            self.assertEqual(result['language'], 'hi')
            self.assertIn('warning', result)
            self.assertEqual(result['backend_used'], 'google')

    def test_database_caching_functionality(self):
        """Test that translations are properly cached in database"""
        service = ConversationTranslationService()

        # Mock successful translation
        mock_response = {
            'success': True,
            'translated_text': 'Texto traducido de prueba',
            'backend_used': 'google',
            'confidence': 0.88,
            'warning': '⚠️ Esta conversación fue traducida del inglés.',
            'translation_date': timezone.now().isoformat()
        }

        with patch.object(service, '_perform_translation', return_value=mock_response):
            # First translation should create database entry
            result1 = service.translate_conversation(
                conversation=self.conversation,
                target_language='es',
                user=self.user
            )

            # Check database entry was created
            translation = WisdomConversationTranslation.objects.filter(
                original_conversation=self.conversation,
                target_language='es'
            ).first()

            self.assertIsNotNone(translation)
            self.assertEqual(translation.status, 'completed')
            self.assertEqual(translation.translated_text, 'Texto traducido de prueba')
            self.assertEqual(translation.confidence_score, 0.88)

            # Second call should use database cache
            result2 = service.translate_conversation(
                conversation=self.conversation,
                target_language='es',
                user=self.user
            )

            self.assertTrue(result2['database_cached'])
            self.assertEqual(result2['translated_text'], 'Texto traducido de prueba')

    def test_translation_api_endpoints(self):
        """Test translation API endpoints"""
        self.client.force_login(self.user)

        # Test translate conversation endpoint
        translate_url = reverse('wellness:translate_conversation')
        data = {
            'conversation_id': str(self.conversation.id),
            'target_language': 'hi'
        }

        # Mock translation service
        with patch('apps.wellness.views.translation_api_views.ConversationTranslationService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.translate_conversation.return_value = {
                'success': True,
                'original_text': self.conversation.conversation_text,
                'translated_text': 'हिंदी में अनुवादित पाठ',
                'language': 'hi',
                'warning': 'Translation warning',
                'backend_used': 'google',
                'confidence': 0.9,
                'cached': False,
                'translation_date': timezone.now().isoformat()
            }

            response = self.client.post(
                translate_url,
                data=json.dumps(data),
                content_type='application/json'
            )

            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertTrue(response_data['success'])
            self.assertEqual(response_data['data']['target_language'], 'hi')

        # Test supported languages endpoint
        languages_url = reverse('wellness:supported_languages')
        response = self.client.get(languages_url)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('supported_languages', response_data['data'])

    def test_translation_quality_feedback(self):
        """Test translation quality feedback functionality"""
        # Create a translation
        translation = WisdomConversationTranslation.objects.create(
            original_conversation=self.conversation,
            target_language='hi',
            translated_text='हिंदी में अनुवादित पाठ',
            warning_message='Translation warning',
            translation_backend='google',
            quality_level='unverified',
            status='completed',
            confidence_score=0.85,
            tenant=self.tenant
        )

        # Test creating feedback
        feedback = TranslationQualityFeedback.objects.create(
            translation=translation,
            user=self.user,
            feedback_type='rating',
            quality_rating=4,
            feedback_text='Good translation but could be improved',
            tenant=self.tenant
        )

        self.assertEqual(feedback.quality_rating, 4)
        self.assertEqual(feedback.feedback_type, 'rating')

        # Test feedback API endpoint
        self.client.force_login(self.user)
        feedback_url = reverse('wellness:translation_feedback')

        data = {
            'translation_id': str(translation.id),
            'feedback_type': 'rating',
            'quality_rating': 5,
            'feedback_text': 'Excellent translation!'
        }

        response = self.client.post(
            feedback_url,
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])

    def test_automatic_translation_signal(self):
        """Test automatic translation when new conversation is created"""
        # Create user with non-English preference
        hindi_user = User.objects.create_user(
            loginid="hindiuser",
            peoplename="Hindi User",
            peoplecode="HINDI001",
            email="hindi@test.com",
            preferred_language="hi",
            tenant=self.tenant
        )

        # Mock Celery task
        with patch('apps.wellness.signals.conversation_translation_signals.translate_conversation_async') as mock_task:
            mock_task.delay = MagicMock()

            # Create new conversation - should trigger auto-translation
            new_conversation = WisdomConversation.objects.create(
                user=hindi_user,
                thread=self.thread,
                conversation_text="This is a new conversation that should be auto-translated.",
                conversation_tone="encouraging",
                source_type="system_generated",
                tenant=self.tenant
            )

            # Verify translation task was queued
            mock_task.delay.assert_called_once()
            call_args = mock_task.delay.call_args[1]
            self.assertEqual(call_args['conversation_id'], new_conversation.id)
            self.assertEqual(call_args['target_language'], 'hi')
            self.assertEqual(call_args['priority'], 'auto')

    def test_translation_cache_expiry(self):
        """Test translation cache expiry functionality"""
        # Create expired translation
        expired_translation = WisdomConversationTranslation.objects.create(
            original_conversation=self.conversation,
            target_language='te',
            translated_text='Telugu translation',
            warning_message='Translation warning',
            translation_backend='google',
            quality_level='unverified',
            status='completed',
            expires_at=timezone.now() - timedelta(days=1),  # Expired
            tenant=self.tenant
        )

        self.assertTrue(expired_translation.is_expired)

        # Service should not use expired translation
        service = ConversationTranslationService()
        cached_result = service._get_cached_translation_from_db(
            conversation=self.conversation,
            target_language='te'
        )

        self.assertIsNone(cached_result)

    def test_translation_performance_tracking(self):
        """Test translation performance and metrics tracking"""
        translation = WisdomConversationTranslation.objects.create(
            original_conversation=self.conversation,
            target_language='fr',
            translated_text='Texte traduit en français',
            translation_backend='azure',
            confidence_score=0.92,
            word_count_original=15,
            word_count_translated=18,
            translation_time_ms=1200,
            cache_hit_count=5,
            tenant=self.tenant
        )

        # Test performance metrics
        metrics = translation.calculate_performance_metrics()
        self.assertEqual(metrics['translation_speed'], 1200)
        self.assertEqual(metrics['cache_efficiency'], 5)
        self.assertEqual(metrics['backend_used'], 'azure')

        # Test access tracking
        initial_hits = translation.cache_hit_count
        translation.mark_accessed()
        translation.refresh_from_db()
        self.assertEqual(translation.cache_hit_count, initial_hits + 1)
        self.assertIsNotNone(translation.last_accessed)

    def test_batch_translation_management_command(self):
        """Test batch translation management command functionality"""
        from django.core.management import call_command
        from io import StringIO

        # Create additional test conversations
        conversations = []
        for i in range(3):
            conv = WisdomConversation.objects.create(
                user=self.user,
                thread=self.thread,
                conversation_text=f"Test conversation {i+1} for batch translation.",
                conversation_tone="neutral",
                source_type="user_input",
                tenant=self.tenant
            )
            conversations.append(conv)

        # Test dry run
        out = StringIO()
        call_command(
            'translate_conversations',
            '--language', 'hi',
            '--max-translations', '3',
            '--dry-run',
            stdout=out
        )

        output = out.getvalue()
        self.assertIn('Dry run complete', output)
        self.assertIn('No translations were processed', output)

    def test_translation_ui_integration(self):
        """Test translation UI components integration"""
        self.client.force_login(self.user)

        # Test conversations with wisdom page
        url = reverse('wellness:conversations_with_wisdom')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'languageSelect')  # Language selector
        self.assertContains(response, 'translateToggle')  # Translation toggle
        self.assertContains(response, 'translationWarning')  # Warning div
        self.assertContains(response, 'translationQuality')  # Quality info div

    def test_user_language_preference_form(self):
        """Test user language preference in profile forms"""
        self.client.force_login(self.user)

        # Test that preferred_language field is available in user forms
        from apps.peoples.forms import PeopleForm

        form = PeopleForm(instance=self.user)
        self.assertIn('preferred_language', form.fields)
        self.assertEqual(form.fields['preferred_language'].label, 'Preferred Language')

        # Test form submission with language preference
        form_data = {
            'peoplename': 'Updated User',
            'peoplecode': 'TEST001',
            'loginid': 'testuser',
            'email': 'test@test.com',
            'preferred_language': 'te',
            'enable': True,
            'gender': 'M',
            'dateofbirth': '1990-01-01',
        }

        form = PeopleForm(data=form_data, instance=self.user)
        if form.is_valid():
            updated_user = form.save()
            self.assertEqual(updated_user.preferred_language, 'te')

    def test_translation_admin_interface(self):
        """Test translation management in admin interface"""
        # Create admin user
        admin_user = User.objects.create_superuser(
            loginid="admin",
            peoplename="Admin User",
            peoplecode="ADMIN001",
            email="admin@test.com",
            tenant=self.tenant
        )

        self.client.force_login(admin_user)

        # Create translation for admin testing
        translation = WisdomConversationTranslation.objects.create(
            original_conversation=self.conversation,
            target_language='hi',
            translated_text='Admin test translation',
            translation_backend='google',
            quality_level='unverified',
            status='completed',
            tenant=self.tenant
        )

        # Test admin list view
        admin_url = '/admin/wellness/wisdomconversationtranslation/'
        response = self.client.get(admin_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin test translation')

        # Test admin change view
        change_url = f'/admin/wellness/wisdomconversationtranslation/{translation.id}/change/'
        response = self.client.get(change_url)
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        """Clean up test data"""
        # Clean up will be handled by Django's TestCase automatically
        pass


class ConversationTranslationCeleryTest(TransactionTestCase):
    """Test Celery task integration for translations"""

    def setUp(self):
        """Set up test data for Celery tests"""
        self.tenant = Tenant.objects.create(
            name="Celery Test Tenant",
            domain="celery.test.com"
        )

        self.user = User.objects.create_user(
            loginid="celeryuser",
            peoplename="Celery Test User",
            peoplecode="CEL001",
            email="celery@test.com",
            preferred_language="es",
            tenant=self.tenant
        )

        self.thread = ConversationThread.objects.create(
            user=self.user,
            thread_type="daily_reflection",
            tenant=self.tenant
        )

        self.conversation = WisdomConversation.objects.create(
            user=self.user,
            thread=self.thread,
            conversation_text="Today was productive and I learned something new.",
            conversation_tone="positive",
            source_type="user_input",
            tenant=self.tenant
        )

    @patch('apps.wellness.tasks.ConversationTranslationService')
    def test_celery_translation_task(self, mock_service):
        """Test Celery translation task execution"""
        # Mock service response
        mock_instance = mock_service.return_value
        mock_instance.translate_conversation.return_value = {
            'success': True,
            'translated_text': 'Hoy fue productivo y aprendí algo nuevo.',
            'backend_used': 'azure',
            'confidence': 0.89,
            'cached': False
        }

        # Execute task synchronously for testing
        result = translate_conversation_async(
            conversation_id=self.conversation.id,
            target_language='es',
            priority='manual'
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['target_language'], 'es')
        self.assertEqual(result['backend_used'], 'azure')

        # Verify service was called correctly
        mock_instance.translate_conversation.assert_called_once()


# Sample data for testing
class SampleDataMixin:
    """Mixin providing sample conversation data for testing"""

    SAMPLE_CONVERSATIONS = [
        {
            'text': 'I am grateful for my family and friends who support me every day.',
            'tone': 'warm',
            'type': 'gratitude_practice'
        },
        {
            'text': 'Today I faced a challenge but I handled it well by staying calm.',
            'tone': 'encouraging',
            'type': 'resilience_building'
        },
        {
            'text': 'I notice I feel stressed when I have too many tasks. I can break them into smaller steps.',
            'tone': 'reflective',
            'type': 'self_awareness'
        },
        {
            'text': 'Taking a short walk during lunch helped me feel more energized for the afternoon.',
            'tone': 'positive',
            'type': 'wellness_practice'
        }
    ]

    EXPECTED_TRANSLATIONS = {
        'hi': [
            'मैं अपने परिवार और दोस्तों के लिए आभारी हूं जो हर दिन मेरा समर्थन करते हैं।',
            'आज मैंने एक चुनौती का सामना किया लेकिन मैंने शांत रहकर इसे अच्छी तरह संभाला।',
        ],
        'es': [
            'Estoy agradecido por mi familia y amigos que me apoyan todos los días.',
            'Hoy enfrenté un desafío pero lo manejé bien manteniéndome tranquilo.',
        ]
    }

    def create_sample_conversations(self, user, thread, tenant):
        """Create sample conversations for testing"""
        conversations = []
        for sample in self.SAMPLE_CONVERSATIONS:
            conv = WisdomConversation.objects.create(
                user=user,
                thread=thread,
                conversation_text=sample['text'],
                conversation_tone=sample['tone'],
                source_type='user_input',
                tenant=tenant
            )
            conversations.append(conv)
        return conversations


if __name__ == '__main__':
    # Run tests if this file is executed directly
    import django
    from django.test.utils import get_runner
    from django.conf import settings

    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['apps.wellness.tests.test_conversation_translation_integration'])
    if failures:
        exit(1)