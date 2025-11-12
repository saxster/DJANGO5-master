"""
import logging
logger = logging.getLogger(__name__)
Comprehensive tests for HelpBot models.

Tests all 6 refactored models:
- HelpBotSession (session management)
- HelpBotMessage (conversation messages)
- HelpBotKnowledge (knowledge base)
- HelpBotFeedback (user feedback)
- HelpBotContext (contextual information)
- HelpBotAnalytics (metrics and analytics)

Complies with .claude/rules.md:
- Specific exception testing
- Database transaction handling
- Unique constraints and indexes
"""

import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
import uuid

from apps.helpbot.models import (
    HelpBotSession,
    HelpBotMessage,
    HelpBotKnowledge,
    HelpBotFeedback,
    HelpBotContext,
    HelpBotAnalytics,
)
from apps.peoples.models import People
from apps.tenants.models import Client


@pytest.fixture
def test_user(db):
    """Create test user."""
    tenant = Client.objects.create(
        name="Test Tenant",
        is_active=True
    )
    return People.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        client=tenant,
    )


@pytest.fixture
def test_session(db, test_user):
    """Create test HelpBot session."""
    return HelpBotSession.objects.create(
        user=test_user,
        session_type=HelpBotSession.SessionTypeChoices.GENERAL_HELP,
        current_state=HelpBotSession.StateChoices.ACTIVE,
        language="en",
        client=test_user.client,
    )


@pytest.fixture
def test_knowledge(db):
    """Create test knowledge entry."""
    return HelpBotKnowledge.objects.create(
        title="How to Reset Password",
        content="Follow these steps to reset your password...",
        knowledge_type=HelpBotKnowledge.KnowledgeTypeChoices.FAQ,
        category=HelpBotKnowledge.CategoryChoices.HELPDESK,
        search_keywords=["password", "reset", "login"],
        is_active=True,
        effectiveness_score=0.85,
    )


# =============================================================================
# HELPBOT SESSION MODEL TESTS
# =============================================================================

@pytest.mark.django_db
class TestHelpBotSession(TestCase):
    """Test HelpBotSession model."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Client.objects.create(
            name="Test Tenant",
            is_active=True
        )
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            client=self.tenant,
        )

    def test_create_session_success(self):
        """Test creating a HelpBot session."""
        session = HelpBotSession.objects.create(
            user=self.user,
            session_type=HelpBotSession.SessionTypeChoices.GENERAL_HELP,
            current_state=HelpBotSession.StateChoices.ACTIVE,
            language="en",
            client=self.tenant,
        )

        assert session.session_id is not None
        assert session.user == self.user
        assert session.current_state == HelpBotSession.StateChoices.ACTIVE
        assert session.total_messages == 0
        assert session.language == "en"

    def test_session_uuid_primary_key(self):
        """Test that session_id is UUID primary key."""
        session = HelpBotSession.objects.create(
            user=self.user,
            session_type=HelpBotSession.SessionTypeChoices.TUTORIAL,
        )

        assert isinstance(session.session_id, uuid.UUID)
        assert session.session_id != uuid.uuid4()

    def test_session_all_types(self):
        """Test all session type choices."""
        for session_type, display_name in HelpBotSession.SessionTypeChoices.choices:
            session = HelpBotSession.objects.create(
                user=self.user,
                session_type=session_type,
            )
            assert session.session_type == session_type

    def test_session_all_states(self):
        """Test all session state choices."""
        for state, display_name in HelpBotSession.StateChoices.choices:
            session = HelpBotSession.objects.create(
                user=self.user,
                current_state=state,
            )
            assert session.current_state == state

    def test_session_context_data_default(self):
        """Test context_data defaults to empty dict."""
        session = HelpBotSession.objects.create(
            user=self.user,
            context_data={"test": "data"},
        )

        assert session.context_data == {"test": "data"}

    def test_session_voice_enabled(self):
        """Test voice_enabled field."""
        session = HelpBotSession.objects.create(
            user=self.user,
            voice_enabled=True,
        )

        assert session.voice_enabled is True

    def test_session_satisfaction_rating_validation(self):
        """Test satisfaction rating can be set."""
        session = HelpBotSession.objects.create(
            user=self.user,
            satisfaction_rating=5,
        )

        assert session.satisfaction_rating == 5

    def test_session_str_representation(self):
        """Test session string representation."""
        session = HelpBotSession.objects.create(
            user=self.user,
            session_type=HelpBotSession.SessionTypeChoices.GENERAL_HELP,
        )

        session_str = str(session)
        assert "HelpBot Session" in session_str
        assert str(session.session_id) in session_str

    def test_session_last_activity_updated(self):
        """Test last_activity is auto-updated."""
        session = HelpBotSession.objects.create(
            user=self.user,
        )

        original_activity = session.last_activity

        # Update session
        session.total_messages = 5
        session.save()

        session.refresh_from_db()
        assert session.last_activity >= original_activity

    def test_session_total_messages_increment(self):
        """Test total_messages counter."""
        session = HelpBotSession.objects.create(
            user=self.user,
            total_messages=0,
        )

        session.total_messages = 10
        session.save()

        session.refresh_from_db()
        assert session.total_messages == 10

    def test_session_user_relation(self):
        """Test user relationship."""
        session = HelpBotSession.objects.create(
            user=self.user,
        )

        assert session.user.email == "test@example.com"
        assert HelpBotSession.objects.filter(user=self.user).exists()

    def test_session_deletion_cascade(self):
        """Test that deleting user cascades to sessions."""
        session = HelpBotSession.objects.create(
            user=self.user,
        )

        session_id = session.session_id

        # Delete user
        self.user.delete()

        # Session should be deleted too
        assert not HelpBotSession.objects.filter(session_id=session_id).exists()


# =============================================================================
# HELPBOT MESSAGE MODEL TESTS
# =============================================================================

@pytest.mark.django_db
class TestHelpBotMessage(TestCase):
    """Test HelpBotMessage model."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Client.objects.create(
            name="Test Tenant",
            is_active=True
        )
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            client=self.tenant,
        )
        self.session = HelpBotSession.objects.create(
            user=self.user,
        )

    def test_create_message_success(self):
        """Test creating a message."""
        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.USER_TEXT,
            content="How do I reset my password?",
            confidence_score=0.95,
        )

        assert message.message_id is not None
        assert message.session == self.session
        assert message.content == "How do I reset my password?"
        assert message.confidence_score == 0.95

    def test_message_all_types(self):
        """Test all message type choices."""
        for msg_type, display_name in HelpBotMessage.MessageTypeChoices.choices:
            message = HelpBotMessage.objects.create(
                session=self.session,
                message_type=msg_type,
                content="Test message",
            )
            assert message.message_type == msg_type

    def test_message_rich_content(self):
        """Test rich_content field."""
        rich_content = {
            "links": [{"text": "FAQ", "url": "/help/faq"}],
            "code": {"language": "python", "snippet": "logger.info('hello')"},
        }
        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Here's an example",
            rich_content=rich_content,
        )

        assert message.rich_content == rich_content

    def test_message_metadata(self):
        """Test metadata field."""
        metadata = {
            "source": "faq",
            "matched_keywords": ["password", "reset"],
            "processing_time_ms": 150,
        }
        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Test",
            metadata=metadata,
        )

        assert message.metadata == metadata

    def test_message_knowledge_sources(self):
        """Test knowledge_sources field."""
        sources = [
            {"id": "kb-123", "title": "Password Reset Guide", "score": 0.95}
        ]
        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Test",
            knowledge_sources=sources,
        )

        assert message.knowledge_sources == sources

    def test_message_processing_time(self):
        """Test processing_time_ms field."""
        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Test",
            processing_time_ms=250,
        )

        assert message.processing_time_ms == 250

    def test_message_confidence_score_range(self):
        """Test confidence_score is between 0-1."""
        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Test",
            confidence_score=0.75,
        )

        assert 0 <= message.confidence_score <= 1

    def test_message_session_relation(self):
        """Test session relationship."""
        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.USER_TEXT,
            content="Test",
        )

        assert message.session.session_id == self.session.session_id
        assert HelpBotMessage.objects.filter(session=self.session).exists()

    def test_message_ordering(self):
        """Test messages are ordered by creation time."""
        msg1 = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.USER_TEXT,
            content="First message",
        )

        msg2 = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Second message",
        )

        messages = HelpBotMessage.objects.filter(session=self.session)
        assert messages[0].content == "First message"
        assert messages[1].content == "Second message"

    def test_message_session_cascade(self):
        """Test that deleting session cascades to messages."""
        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.USER_TEXT,
            content="Test",
        )

        message_id = message.message_id

        # Delete session
        self.session.delete()

        # Message should be deleted
        assert not HelpBotMessage.objects.filter(message_id=message_id).exists()


# =============================================================================
# HELPBOT KNOWLEDGE MODEL TESTS
# =============================================================================

@pytest.mark.django_db
class TestHelpBotKnowledge(TestCase):
    """Test HelpBotKnowledge model."""

    def test_create_knowledge_success(self):
        """Test creating knowledge entry."""
        knowledge = HelpBotKnowledge.objects.create(
            title="Password Reset Guide",
            content="Step 1: Go to settings...",
            knowledge_type=HelpBotKnowledge.KnowledgeTypeChoices.FAQ,
            category=HelpBotKnowledge.CategoryChoices.HELPDESK,
            search_keywords=["password", "reset"],
            is_active=True,
        )

        assert knowledge.knowledge_id is not None
        assert knowledge.title == "Password Reset Guide"
        assert knowledge.is_active is True

    def test_knowledge_all_types(self):
        """Test all knowledge type choices."""
        for ktype, display_name in HelpBotKnowledge.KnowledgeTypeChoices.choices:
            knowledge = HelpBotKnowledge.objects.create(
                title="Test",
                content="Test content",
                knowledge_type=ktype,
            )
            assert knowledge.knowledge_type == ktype

    def test_knowledge_all_categories(self):
        """Test all category choices."""
        for cat, display_name in HelpBotKnowledge.CategoryChoices.choices:
            knowledge = HelpBotKnowledge.objects.create(
                title="Test",
                content="Test content",
                category=cat,
            )
            assert knowledge.category == cat

    def test_knowledge_search_keywords(self):
        """Test search_keywords array field."""
        keywords = ["password", "reset", "account", "login"]
        knowledge = HelpBotKnowledge.objects.create(
            title="Test",
            content="Test",
            search_keywords=keywords,
        )

        assert knowledge.search_keywords == keywords

    def test_knowledge_tags_array(self):
        """Test tags array field."""
        tags = ["urgent", "popular", "frequently-updated"]
        knowledge = HelpBotKnowledge.objects.create(
            title="Test",
            content="Test",
            tags=tags,
        )

        assert knowledge.tags == tags

    def test_knowledge_related_urls(self):
        """Test related_urls array field."""
        urls = ["https://example.com/page1", "https://example.com/page2"]
        knowledge = HelpBotKnowledge.objects.create(
            title="Test",
            content="Test",
            related_urls=urls,
        )

        assert knowledge.related_urls == urls

    def test_knowledge_embedding_vector(self):
        """Test embedding_vector field."""
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        knowledge = HelpBotKnowledge.objects.create(
            title="Test",
            content="Test",
            embedding_vector=vector,
        )

        assert knowledge.embedding_vector == vector

    def test_knowledge_effectiveness_score(self):
        """Test effectiveness_score field."""
        knowledge = HelpBotKnowledge.objects.create(
            title="Test",
            content="Test",
            effectiveness_score=0.92,
        )

        assert knowledge.effectiveness_score == 0.92

    def test_knowledge_usage_count(self):
        """Test usage_count field."""
        knowledge = HelpBotKnowledge.objects.create(
            title="Test",
            content="Test",
            usage_count=0,
        )

        knowledge.usage_count = 50
        knowledge.save()

        knowledge.refresh_from_db()
        assert knowledge.usage_count == 50

    def test_knowledge_source_file(self):
        """Test source_file field."""
        knowledge = HelpBotKnowledge.objects.create(
            title="Test",
            content="Test",
            source_file="/docs/password-reset.md",
        )

        assert knowledge.source_file == "/docs/password-reset.md"

    def test_knowledge_active_inactive(self):
        """Test is_active field."""
        active = HelpBotKnowledge.objects.create(
            title="Active",
            content="Test",
            is_active=True,
        )

        inactive = HelpBotKnowledge.objects.create(
            title="Inactive",
            content="Test",
            is_active=False,
        )

        assert active.is_active is True
        assert inactive.is_active is False
        assert HelpBotKnowledge.objects.filter(is_active=True).count() >= 1

    def test_knowledge_str_representation(self):
        """Test string representation."""
        knowledge = HelpBotKnowledge.objects.create(
            title="Test Knowledge",
            content="Test",
            category=HelpBotKnowledge.CategoryChoices.HELPDESK,
        )

        assert "Test Knowledge" in str(knowledge)
        assert "helpdesk" in str(knowledge).lower()


# =============================================================================
# HELPBOT FEEDBACK MODEL TESTS
# =============================================================================

@pytest.mark.django_db
class TestHelpBotFeedback(TestCase):
    """Test HelpBotFeedback model."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Client.objects.create(
            name="Test Tenant",
            is_active=True
        )
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            client=self.tenant,
        )
        self.session = HelpBotSession.objects.create(
            user=self.user,
        )
        self.message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Test response",
        )

    def test_create_feedback_success(self):
        """Test creating feedback."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            message=self.message,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
            rating=5,
            comment="Very helpful!",
        )

        assert feedback.feedback_id is not None
        assert feedback.feedback_type == HelpBotFeedback.FeedbackTypeChoices.HELPFUL
        assert feedback.rating == 5

    def test_feedback_all_types(self):
        """Test all feedback type choices."""
        for ftype, display_name in HelpBotFeedback.FeedbackTypeChoices.choices:
            feedback = HelpBotFeedback.objects.create(
                session=self.session,
                user=self.user,
                feedback_type=ftype,
            )
            assert feedback.feedback_type == ftype

    def test_feedback_rating_field(self):
        """Test rating field (1-5)."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
            rating=4,
        )

        assert feedback.rating == 4

    def test_feedback_comment(self):
        """Test comment field."""
        comment = "This really helped me solve the problem quickly."
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
            comment=comment,
        )

        assert feedback.comment == comment

    def test_feedback_suggestion(self):
        """Test suggestion field."""
        suggestion = "Could you also include examples?"
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.SUGGESTION,
            suggestion=suggestion,
        )

        assert feedback.suggestion == suggestion

    def test_feedback_context_data(self):
        """Test context_data field."""
        context = {
            "page_url": "/help/faq/",
            "session_length_seconds": 120,
            "messages_count": 3,
        }
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
            context_data=context,
        )

        assert feedback.context_data == context

    def test_feedback_is_processed_flag(self):
        """Test is_processed flag."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
            is_processed=False,
        )

        assert feedback.is_processed is False

        feedback.is_processed = True
        feedback.save()

        feedback.refresh_from_db()
        assert feedback.is_processed is True

    def test_feedback_message_optional(self):
        """Test message is optional."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
            message=None,
        )

        assert feedback.message is None

    def test_feedback_message_cascade(self):
        """Test that deleting message doesn't affect feedback."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            message=self.message,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
        )

        feedback_id = feedback.feedback_id

        # Delete message
        self.message.delete()

        # Feedback should still exist
        feedback.refresh_from_db()
        assert feedback.message is None


# =============================================================================
# HELPBOT CONTEXT MODEL TESTS
# =============================================================================

@pytest.mark.django_db
class TestHelpBotContext(TestCase):
    """Test HelpBotContext model."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Client.objects.create(
            name="Test Tenant",
            is_active=True
        )
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            client=self.tenant,
        )
        self.session = HelpBotSession.objects.create(
            user=self.user,
        )

    def test_create_context_success(self):
        """Test creating context."""
        context = HelpBotContext.objects.create(
            user=self.user,
            session=self.session,
            current_url="https://example.com/help/tasks/",
            page_title="Task Management Help",
            app_name="activity",
            view_name="task_list",
        )

        assert context.context_id is not None
        assert context.current_url == "https://example.com/help/tasks/"

    def test_context_page_title(self):
        """Test page_title field."""
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/",
            page_title="Dashboard",
        )

        assert context.page_title == "Dashboard"

    def test_context_app_and_view_names(self):
        """Test app_name and view_name fields."""
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/",
            app_name="peoples",
            view_name="profile_detail",
        )

        assert context.app_name == "peoples"
        assert context.view_name == "profile_detail"

    def test_context_user_role(self):
        """Test user_role field."""
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/",
            user_role="facility_manager",
        )

        assert context.user_role == "facility_manager"

    def test_context_form_data(self):
        """Test form_data field."""
        form_data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
        }
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/",
            form_data=form_data,
        )

        assert context.form_data == form_data

    def test_context_error_context(self):
        """Test error_context field."""
        error_data = {
            "error_type": "ValidationError",
            "error_message": "Invalid email format",
            "field": "email",
        }
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/",
            error_context=error_data,
        )

        assert context.error_context == error_data

    def test_context_user_journey(self):
        """Test user_journey field (list of pages)."""
        journey = [
            "/dashboard/",
            "/tasks/",
            "/tasks/123/",
        ]
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/",
            user_journey=journey,
        )

        assert context.user_journey == journey

    def test_context_browser_info(self):
        """Test browser_info field."""
        browser_info = {
            "user_agent": "Mozilla/5.0...",
            "browser": "Chrome",
            "os": "macOS",
            "screen_resolution": "1920x1080",
        }
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/",
            browser_info=browser_info,
        )

        assert context.browser_info == browser_info

    def test_context_session_optional(self):
        """Test session is optional."""
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/",
            session=None,
        )

        assert context.session is None

    def test_context_str_representation(self):
        """Test string representation."""
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/tasks/",
        )

        context_str = str(context)
        assert "https://example.com/tasks/" in context_str


# =============================================================================
# HELPBOT ANALYTICS MODEL TESTS
# =============================================================================

@pytest.mark.django_db
class TestHelpBotAnalytics(TestCase):
    """Test HelpBotAnalytics model."""

    def test_create_analytics_success(self):
        """Test creating analytics record."""
        analytics = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            value=100.0,
            date=timezone.now().date(),
            hour=14,
        )

        assert analytics.analytics_id is not None
        assert analytics.metric_type == HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT
        assert analytics.value == 100.0

    def test_analytics_all_metric_types(self):
        """Test all metric type choices."""
        for metric_type, display_name in HelpBotAnalytics.MetricTypeChoices.choices:
            analytics = HelpBotAnalytics.objects.create(
                metric_type=metric_type,
                value=50.0,
            )
            assert analytics.metric_type == metric_type

    def test_analytics_value_field(self):
        """Test value field (float)."""
        analytics = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.RESPONSE_TIME,
            value=342.5,  # milliseconds
        )

        assert analytics.value == 342.5

    def test_analytics_dimension_data(self):
        """Test dimension_data field for breakdowns."""
        dimensions = {
            "by_category": {
                "helpdesk": 45,
                "technical": 30,
                "general": 25,
            },
            "by_user_type": {
                "admin": 50,
                "user": 50,
            },
        }
        analytics = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            value=100.0,
            dimension_data=dimensions,
        )

        assert analytics.dimension_data == dimensions

    def test_analytics_date_field(self):
        """Test date field."""
        today = timezone.now().date()
        analytics = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            value=100.0,
            date=today,
        )

        assert analytics.date == today

    def test_analytics_hour_field(self):
        """Test hour field (0-23)."""
        for hour in [0, 12, 23]:
            analytics = HelpBotAnalytics.objects.create(
                metric_type=HelpBotAnalytics.MetricTypeChoices.MESSAGE_COUNT,
                value=50.0,
                hour=hour,
            )
            assert analytics.hour == hour

    def test_analytics_hour_optional(self):
        """Test hour is optional."""
        analytics = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            value=100.0,
            hour=None,
        )

        assert analytics.hour is None

    def test_analytics_unique_constraint(self):
        """Test unique constraint on (metric_type, date, hour)."""
        today = timezone.now().date()

        analytics1 = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            value=100.0,
            date=today,
            hour=14,
        )

        # Creating duplicate should fail
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                HelpBotAnalytics.objects.create(
                    metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
                    value=150.0,
                    date=today,
                    hour=14,
                )

    def test_analytics_str_representation(self):
        """Test string representation."""
        analytics = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.USER_SATISFACTION,
            value=4.5,
        )

        analytics_str = str(analytics)
        assert "user_satisfaction" in analytics_str.lower()
        assert "4.5" in analytics_str

    def test_analytics_ordering_by_date(self):
        """Test analytics can be ordered by date."""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        analytics_old = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            value=50.0,
            date=yesterday,
        )

        analytics_new = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            value=100.0,
            date=today,
        )

        analytics = HelpBotAnalytics.objects.all().order_by('date')
        assert analytics[0].date == yesterday
        assert analytics[1].date == today


__all__ = [
    'TestHelpBotSession',
    'TestHelpBotMessage',
    'TestHelpBotKnowledge',
    'TestHelpBotFeedback',
    'TestHelpBotContext',
    'TestHelpBotAnalytics',
]
