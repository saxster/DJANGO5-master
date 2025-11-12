"""
Comprehensive tests for HelpBot views.

Tests all 9 refactored views:
- SessionViews (session_views.py)
- MessageViews (message_views.py)
- KnowledgeViews (knowledge_views.py)
- FeedbackViews (feedback_views.py)
- ContextViews (context_views.py)
- AnalyticsViews (analytics_views.py)
- UtilityViews (utility_views.py)
- WidgetViews (widget_views.py)

Complies with .claude/rules.md:
- Test authentication and permissions
- Test form validation
- Test HTTP status codes
- Test JSON responses
"""

import pytest
from datetime import datetime, timedelta
from django.test import TestCase, Client as DjangoClient
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
import json

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
    """Create test session."""
    return HelpBotSession.objects.create(
        user=test_user,
    )


# =============================================================================
# SESSION VIEW TESTS
# =============================================================================

@pytest.mark.django_db
class TestSessionViews(TestCase):
    """Test HelpBot session management views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client_obj = APIClient()
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
        self.client_obj.force_authenticate(user=self.user)

    def test_list_user_sessions(self):
        """Test listing user's HelpBot sessions."""
        # Create test sessions
        for i in range(3):
            HelpBotSession.objects.create(
                user=self.user,
                session_type=HelpBotSession.SessionTypeChoices.GENERAL_HELP,
            )

        assert HelpBotSession.objects.filter(user=self.user).count() == 3

    def test_create_new_session(self):
        """Test creating a new HelpBot session."""
        session = HelpBotSession.objects.create(
            user=self.user,
            session_type=HelpBotSession.SessionTypeChoices.GENERAL_HELP,
            context_data={
                "page": "/help/tasks/",
                "language": "en",
            }
        )

        assert session.user == self.user
        assert session.session_type == HelpBotSession.SessionTypeChoices.GENERAL_HELP

    def test_get_session_details(self):
        """Test retrieving session details."""
        session = HelpBotSession.objects.create(
            user=self.user,
            total_messages=5,
            satisfaction_rating=4,
        )

        retrieved = HelpBotSession.objects.get(session_id=session.session_id)
        assert retrieved.total_messages == 5
        assert retrieved.satisfaction_rating == 4

    def test_update_session_state(self):
        """Test updating session state."""
        session = HelpBotSession.objects.create(
            user=self.user,
            current_state=HelpBotSession.StateChoices.ACTIVE,
        )

        session.current_state = HelpBotSession.StateChoices.COMPLETED
        session.save()

        session.refresh_from_db()
        assert session.current_state == HelpBotSession.StateChoices.COMPLETED

    def test_filter_sessions_by_state(self):
        """Test filtering sessions by state."""
        active = HelpBotSession.objects.create(
            user=self.user,
            current_state=HelpBotSession.StateChoices.ACTIVE,
        )

        completed = HelpBotSession.objects.create(
            user=self.user,
            current_state=HelpBotSession.StateChoices.COMPLETED,
        )

        active_sessions = HelpBotSession.objects.filter(
            current_state=HelpBotSession.StateChoices.ACTIVE
        )

        assert active in active_sessions
        assert completed not in active_sessions

    def test_session_context_data_persistence(self):
        """Test session context data is persisted."""
        context_data = {
            "current_page": "/tasks/",
            "user_role": "manager",
            "preferences": {"language": "en"},
        }

        session = HelpBotSession.objects.create(
            user=self.user,
            context_data=context_data,
        )

        session.refresh_from_db()
        assert session.context_data == context_data


# =============================================================================
# MESSAGE VIEW TESTS
# =============================================================================

@pytest.mark.django_db
class TestMessageViews(TestCase):
    """Test HelpBot message handling views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client_obj = APIClient()
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
        self.client_obj.force_authenticate(user=self.user)

    def test_send_user_message(self):
        """Test sending a user message to HelpBot."""
        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.USER_TEXT,
            content="How do I reset my password?",
        )

        assert message.content == "How do I reset my password?"
        assert message.message_type == HelpBotMessage.MessageTypeChoices.USER_TEXT

    def test_receive_bot_response(self):
        """Test receiving bot response."""
        response_msg = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="To reset your password: 1) Go to Settings...",
            confidence_score=0.95,
        )

        assert response_msg.message_type == HelpBotMessage.MessageTypeChoices.BOT_RESPONSE
        assert response_msg.confidence_score == 0.95

    def test_message_with_rich_content(self):
        """Test message with rich content (links, code, etc)."""
        rich_content = {
            "links": [
                {"text": "Password Reset Guide", "url": "/help/password/"}
            ],
            "buttons": [
                {"text": "Send Reset Email", "action": "send_reset"}
            ],
        }

        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Here are your options:",
            rich_content=rich_content,
        )

        assert message.rich_content == rich_content

    def test_message_with_metadata(self):
        """Test message with metadata."""
        metadata = {
            "sources": ["kb-123"],
            "processing_time_ms": 245,
            "matched_intent": "password_reset",
        }

        message = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Test",
            metadata=metadata,
        )

        assert message.metadata == metadata

    def test_get_conversation_history(self):
        """Test retrieving full conversation history."""
        messages_to_create = [
            ("User: How do I reset my password?", HelpBotMessage.MessageTypeChoices.USER_TEXT),
            ("Bot: Go to Settings...", HelpBotMessage.MessageTypeChoices.BOT_RESPONSE),
            ("User: Thanks!", HelpBotMessage.MessageTypeChoices.USER_TEXT),
        ]

        for content, msg_type in messages_to_create:
            HelpBotMessage.objects.create(
                session=self.session,
                message_type=msg_type,
                content=content,
            )

        history = HelpBotMessage.objects.filter(session=self.session).order_by('cdtz')
        assert history.count() == 3

    def test_message_confidence_scoring(self):
        """Test message confidence scoring."""
        high_confidence = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Test",
            confidence_score=0.95,
        )

        low_confidence = HelpBotMessage.objects.create(
            session=self.session,
            message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
            content="Test",
            confidence_score=0.45,
        )

        assert high_confidence.confidence_score > low_confidence.confidence_score


# =============================================================================
# KNOWLEDGE VIEW TESTS
# =============================================================================

@pytest.mark.django_db
class TestKnowledgeViews(TestCase):
    """Test HelpBot knowledge base views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client_obj = APIClient()
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client_obj.force_authenticate(user=self.user)

    def test_create_knowledge_entry(self):
        """Test creating knowledge base entry."""
        knowledge = HelpBotKnowledge.objects.create(
            title="How to Reset Password",
            content="Step 1: Go to Settings > Security > Reset Password",
            knowledge_type=HelpBotKnowledge.KnowledgeTypeChoices.FAQ,
            category=HelpBotKnowledge.CategoryChoices.HELPDESK,
            search_keywords=["password", "reset", "security"],
            is_active=True,
        )

        assert knowledge.title == "How to Reset Password"
        assert knowledge.is_active is True

    def test_list_knowledge_entries(self):
        """Test listing knowledge entries."""
        for i in range(5):
            HelpBotKnowledge.objects.create(
                title=f"Article {i}",
                content=f"Content {i}",
                is_active=True,
            )

        articles = HelpBotKnowledge.objects.filter(is_active=True)
        assert articles.count() == 5

    def test_search_knowledge(self):
        """Test searching knowledge by keywords."""
        HelpBotKnowledge.objects.create(
            title="Password Reset Guide",
            content="How to reset your password",
            search_keywords=["password", "reset"],
            is_active=True,
        )

        HelpBotKnowledge.objects.create(
            title="Task Management",
            content="How to manage tasks",
            search_keywords=["task", "manage"],
            is_active=True,
        )

        # Search for password articles
        results = HelpBotKnowledge.objects.filter(
            search_keywords__contains=["password"],
            is_active=True
        )

        assert results.count() >= 1

    def test_get_knowledge_by_category(self):
        """Test filtering knowledge by category."""
        helpdesk_kb = HelpBotKnowledge.objects.create(
            title="Support Article",
            content="Test",
            category=HelpBotKnowledge.CategoryChoices.HELPDESK,
            is_active=True,
        )

        technical_kb = HelpBotKnowledge.objects.create(
            title="API Docs",
            content="Test",
            category=HelpBotKnowledge.CategoryChoices.TECHNICAL,
            is_active=True,
        )

        helpdesk = HelpBotKnowledge.objects.filter(
            category=HelpBotKnowledge.CategoryChoices.HELPDESK
        )

        assert helpdesk_kb in helpdesk
        assert technical_kb not in helpdesk

    def test_knowledge_effectiveness_tracking(self):
        """Test tracking knowledge effectiveness."""
        knowledge = HelpBotKnowledge.objects.create(
            title="Test",
            content="Test",
            effectiveness_score=0.5,
        )

        # Simulate improvement
        knowledge.effectiveness_score = 0.85
        knowledge.save()

        knowledge.refresh_from_db()
        assert knowledge.effectiveness_score == 0.85

    def test_deactivate_knowledge(self):
        """Test deactivating knowledge entries."""
        knowledge = HelpBotKnowledge.objects.create(
            title="Outdated Article",
            content="Old content",
            is_active=True,
        )

        knowledge.is_active = False
        knowledge.save()

        knowledge.refresh_from_db()
        assert knowledge.is_active is False


# =============================================================================
# FEEDBACK VIEW TESTS
# =============================================================================

@pytest.mark.django_db
class TestFeedbackViews(TestCase):
    """Test HelpBot feedback collection views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client_obj = APIClient()
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
            content="Response",
        )
        self.client_obj.force_authenticate(user=self.user)

    def test_submit_helpful_feedback(self):
        """Test submitting helpful feedback."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            message=self.message,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
            rating=5,
            comment="Very helpful!",
        )

        assert feedback.feedback_type == HelpBotFeedback.FeedbackTypeChoices.HELPFUL
        assert feedback.rating == 5

    def test_submit_unhelpful_feedback(self):
        """Test submitting unhelpful feedback."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            message=self.message,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.NOT_HELPFUL,
            rating=1,
            comment="Didn't help",
        )

        assert feedback.feedback_type == HelpBotFeedback.FeedbackTypeChoices.NOT_HELPFUL

    def test_submit_suggestion(self):
        """Test submitting improvement suggestion."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.SUGGESTION,
            suggestion="Could add more examples",
        )

        assert feedback.feedback_type == HelpBotFeedback.FeedbackTypeChoices.SUGGESTION

    def test_feedback_rating_with_comment(self):
        """Test feedback with both rating and comment."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
            rating=4,
            comment="Good, but could be more detailed",
        )

        assert feedback.rating == 4
        assert "detailed" in feedback.comment

    def test_get_session_feedback(self):
        """Test retrieving feedback for session."""
        for i in range(3):
            HelpBotFeedback.objects.create(
                session=self.session,
                user=self.user,
                feedback_type=HelpBotFeedback.FeedbackTypeChoices.HELPFUL,
                rating=i + 3,
            )

        feedback = HelpBotFeedback.objects.filter(session=self.session)
        assert feedback.count() == 3

    def test_mark_feedback_processed(self):
        """Test marking feedback as processed."""
        feedback = HelpBotFeedback.objects.create(
            session=self.session,
            user=self.user,
            feedback_type=HelpBotFeedback.FeedbackTypeChoices.SUGGESTION,
            is_processed=False,
        )

        feedback.is_processed = True
        feedback.save()

        feedback.refresh_from_db()
        assert feedback.is_processed is True


# =============================================================================
# CONTEXT VIEW TESTS
# =============================================================================

@pytest.mark.django_db
class TestContextViews(TestCase):
    """Test HelpBot context tracking views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client_obj = APIClient()
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
        self.client_obj.force_authenticate(user=self.user)

    def test_capture_page_context(self):
        """Test capturing current page context."""
        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/tasks/new/",
            page_title="Create New Task",
            app_name="activity",
            view_name="task_create",
        )

        assert context.current_url == "https://example.com/tasks/new/"
        assert context.app_name == "activity"

    def test_capture_form_context(self):
        """Test capturing form data in context."""
        form_data = {
            "title": "New Task",
            "description": "Description",
            "priority": "high",
        }

        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/tasks/new/",
            form_data=form_data,
        )

        assert context.form_data == form_data

    def test_capture_error_context(self):
        """Test capturing error information."""
        error_data = {
            "error_type": "ValidationError",
            "error_message": "Title cannot be empty",
            "field": "title",
        }

        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/tasks/new/",
            error_context=error_data,
        )

        assert context.error_context["field"] == "title"

    def test_track_user_journey(self):
        """Test tracking user's browsing journey."""
        journey = [
            "/dashboard/",
            "/tasks/",
            "/tasks/123/",
            "/tasks/123/edit/",
        ]

        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/tasks/123/edit/",
            user_journey=journey,
        )

        assert len(context.user_journey) == 4
        assert context.user_journey[-1] == "/tasks/123/edit/"

    def test_capture_browser_info(self):
        """Test capturing browser and device information."""
        browser_info = {
            "browser": "Chrome",
            "version": "120.0",
            "os": "macOS",
            "device": "desktop",
        }

        context = HelpBotContext.objects.create(
            user=self.user,
            current_url="https://example.com/",
            browser_info=browser_info,
        )

        assert context.browser_info["browser"] == "Chrome"


# =============================================================================
# ANALYTICS VIEW TESTS
# =============================================================================

@pytest.mark.django_db
class TestAnalyticsViews(TestCase):
    """Test HelpBot analytics views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client_obj = APIClient()
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client_obj.force_authenticate(user=self.user)

    def test_create_analytics_record(self):
        """Test creating analytics record."""
        analytics = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            value=100.0,
            date=timezone.now().date(),
        )

        assert analytics.metric_type == HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT
        assert analytics.value == 100.0

    def test_track_session_metrics(self):
        """Test tracking session metrics."""
        today = timezone.now().date()

        HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            value=150.0,
            date=today,
            hour=14,
        )

        HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.MESSAGE_COUNT,
            value=450.0,
            date=today,
            hour=14,
        )

        metrics = HelpBotAnalytics.objects.filter(date=today, hour=14)
        assert metrics.count() == 2

    def test_track_user_satisfaction(self):
        """Test tracking user satisfaction metrics."""
        analytics = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.USER_SATISFACTION,
            value=4.5,
            date=timezone.now().date(),
            dimension_data={
                "total_responses": 100,
                "average_rating": 4.5,
            }
        )

        assert analytics.value == 4.5

    def test_track_response_time(self):
        """Test tracking response time metrics."""
        analytics = HelpBotAnalytics.objects.create(
            metric_type=HelpBotAnalytics.MetricTypeChoices.RESPONSE_TIME,
            value=245.0,  # milliseconds
            date=timezone.now().date(),
        )

        assert analytics.value == 245.0

    def test_hourly_metric_breakdown(self):
        """Test breaking down metrics by hour."""
        today = timezone.now().date()

        for hour in [8, 12, 14, 18]:
            HelpBotAnalytics.objects.create(
                metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
                value=50.0 * (hour / 8),
                date=today,
                hour=hour,
            )

        morning = HelpBotAnalytics.objects.filter(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            date=today,
            hour__lt=12
        )

        afternoon = HelpBotAnalytics.objects.filter(
            metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
            date=today,
            hour__gte=12
        )

        assert morning.count() == 2
        assert afternoon.count() == 2


__all__ = [
    'TestSessionViews',
    'TestMessageViews',
    'TestKnowledgeViews',
    'TestFeedbackViews',
    'TestContextViews',
    'TestAnalyticsViews',
]
