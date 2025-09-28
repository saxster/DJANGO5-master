"""
Test configuration and fixtures for Conversational Onboarding API tests.

Provides reusable test fixtures, mock data, and configuration
for comprehensive testing of all onboarding functionality.
"""
import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from apps.onboarding.models import Bt, ConversationSession, AuthoritativeKnowledge


User = get_user_model()


# Test settings overrides for controlled testing environment
TEST_SETTINGS_OVERRIDES = {
    'ENABLE_CONVERSATIONAL_ONBOARDING': True,
    'ENABLE_PRODUCTION_EMBEDDINGS': False,  # Use dummy for tests unless specifically testing real embeddings
    'ENABLE_WEBHOOK_NOTIFICATIONS': False,  # Disabled by default for tests
    'ONBOARDING_LLM_PROVIDER': 'dummy',
    'ONBOARDING_VECTOR_BACKEND': 'postgres_array',
    'CACHES': {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    },
    'CELERY_TASK_ALWAYS_EAGER': True,  # Run tasks synchronously in tests
    'CELERY_TASK_EAGER_PROPAGATES': True,
}


@pytest.fixture
def test_client():
    """Create a test client (business unit)"""
    return Bt.objects.create(
        buname='Test Corporation',
        bucode='TEST001',
        enable=True,
        bupreferences={
            'siteopentime': '08:00',
            'siteclosetime': '18:00',
            'maxadmins': 5,
            'billingtype': 'monthly'
        }
    )


@pytest.fixture
def test_user(test_client):
    """Create a test user associated with test client"""
    user = User.objects.create_user(
        email='testuser@testcorp.com',
        password='securepass123',
        is_active=True
    )
    user.client = test_client
    user.capabilities = {
        'can_use_conversational_onboarding': True,
        'can_approve_ai_recommendations': True
    }
    user.save()
    return user


@pytest.fixture
def admin_user():
    """Create an admin user for admin-only tests"""
    return User.objects.create_user(
        email='admin@testcorp.com',
        password='adminpass123',
        is_active=True,
        is_staff=True,
        is_superuser=True
    )


@pytest.fixture
def test_conversation(test_user, test_client):
    """Create a test conversation session"""
    return ConversationSession.objects.create(
        user=test_user,
        client=test_client,
        language='en',
        conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
        current_state=ConversationSession.StateChoices.IN_PROGRESS,
        context_data={'test': True}
    )


@pytest.fixture
def test_knowledge():
    """Create test authoritative knowledge"""
    return AuthoritativeKnowledge.objects.create(
        source_organization='Test Standards Org',
        document_title='Test Security Guidelines',
        authority_level='high',
        content_summary='This is a test document containing security guidelines for facility management.',
        publication_date='2024-01-01',
        is_current=True
    )


@pytest.fixture
def api_client_authenticated(test_user):
    """Get authenticated API client"""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=test_user)
    return client


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for controlled testing"""
    from unittest.mock import MagicMock

    mock_service = MagicMock()
    mock_service.generate_embedding.return_value = MagicMock(
        embedding=[0.1, 0.2, 0.3] * 128,  # 384-dimensional vector
        provider='test',
        model='test-model',
        cost_cents=0.0,
        token_count=10,
        latency_ms=100,
        cached=False
    )

    return mock_service


@pytest.fixture
def mock_notification_service():
    """Mock notification service for testing"""
    from unittest.mock import MagicMock

    mock_service = MagicMock()
    mock_service.send_notification.return_value = {
        'slack': MagicMock(success=True, provider='slack'),
        'email': MagicMock(success=True, provider='email')
    }

    return mock_service


class BaseOnboardingTestCase(TestCase):
    """Base test case with common setup for onboarding tests"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Apply test settings
        cls.settings_patcher = override_settings(**TEST_SETTINGS_OVERRIDES)
        cls.settings_patcher.enable()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.settings_patcher.disable()

    def setUp(self):
        """Set up common test data"""
        self.client_bt = Bt.objects.create(
            buname='Test Corporation',
            bucode='TEST001',
            enable=True
        )

        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_active=True
        )
        self.user.client = self.client_bt
        self.user.capabilities = {
            'can_use_conversational_onboarding': True,
            'can_approve_ai_recommendations': True
        }
        self.user.save()

        from rest_framework.test import APIClient
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def create_test_session(self):
        """Create a test conversation session"""
        return ConversationSession.objects.create(
            user=self.user,
            client=self.client_bt,
            language='en',
            conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
            current_state=ConversationSession.StateChoices.IN_PROGRESS
        )


class MockDataFactory:
    """Factory for creating mock test data"""

    @staticmethod
    def create_mock_llm_response():
        """Create mock LLM response data"""
        return {
            'recommendations': [
                {
                    'entity_type': 'bt',
                    'entity_id': 1,
                    'changes': {
                        'buname': 'Updated Business Unit',
                        'enable': True
                    },
                    'confidence': 0.85,
                    'reasoning': 'Based on provided context'
                }
            ],
            'confidence_score': 0.85,
            'next_steps': ['Review configuration', 'Test system']
        }

    @staticmethod
    def create_mock_embedding_vector(dimension=384):
        """Create mock embedding vector"""
        import random
        return [random.uniform(-1, 1) for _ in range(dimension)]

    @staticmethod
    def create_mock_notification_event():
        """Create mock notification event"""
        from apps.onboarding_api.services.notifications import NotificationEvent
        from django.utils import timezone

        return NotificationEvent(
            event_type='approval_pending',
            event_id='test-event-123',
            title='Test Notification',
            message='This is a test notification',
            priority='medium',
            metadata={'test': True},
            timestamp=timezone.now()
        )


# Custom test decorators
def requires_real_embeddings(test_func):
    """Decorator for tests that require real embedding providers"""
    def wrapper(*args, **kwargs):
        with override_settings(ENABLE_PRODUCTION_EMBEDDINGS=True):
            return test_func(*args, **kwargs)
    wrapper.__name__ = test_func.__name__
    return wrapper


def requires_webhooks(test_func):
    """Decorator for tests that require webhook notifications"""
    def wrapper(*args, **kwargs):
        with override_settings(ENABLE_WEBHOOK_NOTIFICATIONS=True):
            return test_func(*args, **kwargs)
    wrapper.__name__ = test_func.__name__
    return wrapper


def with_test_data(clients=1, users_per_client=1, conversations_per_user=0):
    """Decorator to automatically create test data"""
    def decorator(test_func):
        def wrapper(self, *args, **kwargs):
            # Create test data based on parameters
            test_clients = []
            test_users = []
            test_conversations = []

            for i in range(clients):
                client = Bt.objects.create(
                    buname=f'Test Client {i+1}',
                    bucode=f'TC{i+1:03d}',
                    enable=True
                )
                test_clients.append(client)

                for j in range(users_per_client):
                    user = User.objects.create_user(
                        email=f'user{j+1}@client{i+1}.com',
                        password='testpass123',
                        is_active=True
                    )
                    user.client = client
                    user.save()
                    test_users.append(user)

                    for k in range(conversations_per_user):
                        conversation = ConversationSession.objects.create(
                            user=user,
                            client=client,
                            current_state=ConversationSession.StateChoices.IN_PROGRESS
                        )
                        test_conversations.append(conversation)

            # Add test data to instance
            self.test_clients = test_clients
            self.test_users = test_users
            self.test_conversations = test_conversations

            return test_func(self, *args, **kwargs)

        wrapper.__name__ = test_func.__name__
        return wrapper
    return decorator


# Test data templates
SAMPLE_TEMPLATE_CONFIG = {
    "business_units": [
        {
            "buname": "Sample Office",
            "bucode": "SAMPLE001",
            "bupreferences": {
                "siteopentime": "09:00",
                "siteclosetime": "17:00",
                "guardstrenth": 2,
                "maxadmins": 3
            },
            "enable": True
        }
    ],
    "shifts": [
        {
            "shiftname": "Day Shift",
            "starttime": "09:00:00",
            "endtime": "17:00:00",
            "peoplecount": 2,
            "enable": True
        }
    ],
    "type_assists": [
        {
            "tacode": "STAFF",
            "taname": "Staff Member",
            "enable": True
        }
    ]
}


SAMPLE_SITE_INFO = {
    'industry': 'office',
    'size': 'medium',
    'operating_hours': 'business_hours',
    'security_level': 'medium',
    'staff_count': 25
}


# Test validation utilities
class TestValidationMixin:
    """Mixin providing validation utilities for tests"""

    def assert_response_structure(self, response_data, expected_keys):
        """Assert that response has expected structure"""
        for key in expected_keys:
            self.assertIn(key, response_data, f"Response missing key: {key}")

    def assert_valid_uuid(self, uuid_string):
        """Assert that string is a valid UUID"""
        try:
            uuid.UUID(uuid_string)
        except ValueError:
            self.fail(f"Invalid UUID: {uuid_string}")

    def assert_security_headers_present(self, response):
        """Assert that security headers are present in response"""
        security_headers = ['X-Idempotency-Key']
        for header in security_headers:
            if header in response:
                self.assertIsNotNone(response[header])


# Performance benchmarks
PERFORMANCE_BENCHMARKS = {
    'template_loading_max_time': 1.0,  # seconds
    'embedding_generation_max_time': 5.0,  # seconds for batch of 10
    'notification_sending_max_time': 2.0,  # seconds
    'api_response_max_time': 2.0,  # seconds for standard API calls
    'database_query_max_time': 0.5,  # seconds for complex queries
}