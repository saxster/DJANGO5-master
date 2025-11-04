"""
Comprehensive Tests for Ticket Sentiment Analysis

Feature 2: NL/AI Platform Quick Win - Sentiment Analysis on Tickets

Test Coverage:
1. Sentiment score calculation accuracy
2. Emotion detection with keyword matching
3. Sentiment label classification
4. Auto-escalation logic for negative tickets
5. Signal handler triggering
6. Celery task execution
7. Edge cases and error handling

Following CLAUDE.md:
- Rule #11: Specific exception handling
- Pytest best practices
- Comprehensive fixtures
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.services.ticket_sentiment_analyzer import TicketSentimentAnalyzer
from apps.y_helpdesk.tasks.sentiment_analysis_tasks import (
    AnalyzeTicketSentimentTask,
    BulkAnalyzeTicketSentimentTask
)


@pytest.fixture
def mock_ticket(db):
    """Create a mock ticket for testing."""
    from apps.peoples.models import People
    from apps.onboarding.models import Bt
    from apps.tenants.models import Tenant

    # Create tenant
    tenant = Tenant.objects.create(
        name="Test Tenant",
        subdomain="test"
    )

    # Create business unit
    bu = Bt.objects.create(
        buname="Test BU",
        bucode="TST",
        tenant=tenant
    )

    # Create ticket
    ticket = Ticket.objects.create(
        ticketdesc="Test ticket description",
        ticketno="TST#001",
        status="NEW",
        priority="MEDIUM",
        bu=bu,
        tenant=tenant
    )

    return ticket


@pytest.fixture
def negative_ticket(db):
    """Create a ticket with negative sentiment text."""
    from apps.onboarding.models import Bt
    from apps.tenants.models import Tenant

    tenant = Tenant.objects.create(name="Test Tenant", subdomain="test")
    bu = Bt.objects.create(buname="Test BU", bucode="TST", tenant=tenant)

    ticket = Ticket.objects.create(
        ticketdesc=(
            "This is the third time I am reporting this issue. "
            "The system is still not working and it's unbearable. "
            "I am extremely frustrated and angry that nothing has been fixed."
        ),
        ticketno="TST#002",
        status="NEW",
        priority="LOW",
        bu=bu,
        tenant=tenant
    )

    return ticket


@pytest.fixture
def positive_ticket(db):
    """Create a ticket with positive sentiment text."""
    from apps.onboarding.models import Bt
    from apps.tenants.models import Tenant

    tenant = Tenant.objects.create(name="Test Tenant", subdomain="test")
    bu = Bt.objects.create(buname="Test BU", bucode="TST", tenant=tenant)

    ticket = Ticket.objects.create(
        ticketdesc=(
            "Thank you so much for the excellent support! "
            "The issue was resolved quickly and the team was very helpful. "
            "Great service, I really appreciate it."
        ),
        ticketno="TST#003",
        status="RESOLVED",
        priority="LOW",
        bu=bu,
        tenant=tenant
    )

    return ticket


# =============================================================================
# SENTIMENT CALCULATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestSentimentCalculation:
    """Test sentiment score calculation accuracy."""

    def test_calculate_sentiment_very_negative(self, negative_ticket):
        """Test very negative sentiment detection."""
        text = negative_ticket.ticketdesc
        score = TicketSentimentAnalyzer._calculate_sentiment_score(text)

        assert score < 4.0, f"Expected very negative score < 4.0, got {score}"
        assert score >= 0.0, f"Score should be >= 0, got {score}"

    def test_calculate_sentiment_positive(self, positive_ticket):
        """Test positive sentiment detection."""
        text = positive_ticket.ticketdesc
        score = TicketSentimentAnalyzer._calculate_sentiment_score(text)

        assert score > 6.0, f"Expected positive score > 6.0, got {score}"
        assert score <= 10.0, f"Score should be <= 10, got {score}"

    def test_calculate_sentiment_neutral(self, mock_ticket):
        """Test neutral sentiment detection."""
        neutral_text = "The system is not responding. Please check the logs."
        score = TicketSentimentAnalyzer._calculate_sentiment_score(neutral_text)

        assert 4.0 <= score <= 6.0, f"Expected neutral score 4-6, got {score}"

    def test_sentiment_score_range(self):
        """Test sentiment scores are within 0-10 range."""
        test_texts = [
            "terrible awful horrible worst",
            "great excellent wonderful perfect",
            "okay fine normal standard"
        ]

        for text in test_texts:
            score = TicketSentimentAnalyzer._calculate_sentiment_score(text)
            assert 0.0 <= score <= 10.0, f"Score {score} out of range for: {text}"


# =============================================================================
# EMOTION DETECTION TESTS
# =============================================================================

@pytest.mark.django_db
class TestEmotionDetection:
    """Test emotion detection with keyword matching."""

    def test_detect_frustration(self):
        """Test frustration keyword detection."""
        text = "This is the third time I am reporting this. Still not fixed. Frustrated."
        emotions = TicketSentimentAnalyzer._detect_emotions(text)

        assert 'frustration' in emotions, "Should detect frustration"
        assert emotions['frustration'] > 0, "Frustration score should be positive"

    def test_detect_urgency(self):
        """Test urgency keyword detection."""
        text = "This is urgent! Need immediate attention ASAP. Critical emergency."
        emotions = TicketSentimentAnalyzer._detect_emotions(text)

        assert 'urgency' in emotions, "Should detect urgency"
        assert emotions['urgency'] > 0.5, "High urgency score expected"

    def test_detect_satisfaction(self):
        """Test satisfaction keyword detection."""
        text = "Thank you so much! Excellent service. I really appreciate the help."
        emotions = TicketSentimentAnalyzer._detect_emotions(text)

        assert 'satisfaction' in emotions, "Should detect satisfaction"
        assert emotions['satisfaction'] > 0, "Satisfaction score should be positive"

    def test_detect_multiple_emotions(self):
        """Test detecting multiple emotions in one text."""
        text = "Urgent! This is the third time. Still frustrated. Need help ASAP."
        emotions = TicketSentimentAnalyzer._detect_emotions(text)

        assert 'frustration' in emotions, "Should detect frustration"
        assert 'urgency' in emotions, "Should detect urgency"
        assert len(emotions) >= 2, "Should detect multiple emotions"

    def test_no_emotions_detected(self):
        """Test text with no strong emotions."""
        text = "Please review the configuration settings."
        emotions = TicketSentimentAnalyzer._detect_emotions(text)

        assert len(emotions) == 0, "Should not detect emotions in neutral text"


# =============================================================================
# SENTIMENT LABEL TESTS
# =============================================================================

@pytest.mark.django_db
class TestSentimentLabel:
    """Test sentiment label classification."""

    def test_label_very_negative(self):
        """Test very_negative label (score < 2.0)."""
        label = TicketSentimentAnalyzer._determine_sentiment_label(1.5)
        assert label == 'very_negative'

    def test_label_negative(self):
        """Test negative label (2.0 <= score < 4.0)."""
        label = TicketSentimentAnalyzer._determine_sentiment_label(3.0)
        assert label == 'negative'

    def test_label_neutral(self):
        """Test neutral label (4.0 <= score < 6.0)."""
        label = TicketSentimentAnalyzer._determine_sentiment_label(5.0)
        assert label == 'neutral'

    def test_label_positive(self):
        """Test positive label (6.0 <= score < 8.0)."""
        label = TicketSentimentAnalyzer._determine_sentiment_label(7.0)
        assert label == 'positive'

    def test_label_very_positive(self):
        """Test very_positive label (score >= 8.0)."""
        label = TicketSentimentAnalyzer._determine_sentiment_label(9.0)
        assert label == 'very_positive'

    def test_label_boundary_conditions(self):
        """Test boundary values for labels."""
        boundaries = [
            (2.0, 'negative'),
            (4.0, 'neutral'),
            (6.0, 'positive'),
            (8.0, 'very_positive')
        ]

        for score, expected_label in boundaries:
            label = TicketSentimentAnalyzer._determine_sentiment_label(score)
            assert label == expected_label, f"Score {score} should be {expected_label}"


# =============================================================================
# AUTO-ESCALATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestAutoEscalation:
    """Test auto-escalation logic for negative tickets."""

    def test_should_escalate_very_negative_new_ticket(self, negative_ticket):
        """Test escalation for very negative new ticket."""
        # Simulate very negative score
        should_escalate = TicketSentimentAnalyzer._should_escalate(1.5, negative_ticket)
        assert should_escalate is True, "Should escalate very negative new ticket"

    def test_should_not_escalate_neutral_ticket(self, mock_ticket):
        """Test no escalation for neutral ticket."""
        should_escalate = TicketSentimentAnalyzer._should_escalate(5.0, mock_ticket)
        assert should_escalate is False, "Should not escalate neutral ticket"

    def test_should_not_escalate_resolved_ticket(self, negative_ticket):
        """Test no escalation for resolved tickets."""
        negative_ticket.status = 'RESOLVED'
        negative_ticket.save()

        should_escalate = TicketSentimentAnalyzer._should_escalate(1.5, negative_ticket)
        assert should_escalate is False, "Should not escalate resolved ticket"

    def test_auto_escalate_sets_priority(self, negative_ticket):
        """Test auto-escalation sets priority to HIGH."""
        TicketSentimentAnalyzer._auto_escalate_negative_ticket(
            negative_ticket,
            sentiment_score=1.5,
            emotions={'frustration': 0.8}
        )

        negative_ticket.refresh_from_db()
        assert negative_ticket.priority == 'HIGH', "Priority should be set to HIGH"

    def test_auto_escalate_marks_as_escalated(self, negative_ticket):
        """Test auto-escalation marks ticket as escalated."""
        TicketSentimentAnalyzer._auto_escalate_negative_ticket(
            negative_ticket,
            sentiment_score=1.5,
            emotions={'frustration': 0.8}
        )

        assert negative_ticket.isescalated is True, "Ticket should be marked escalated"


# =============================================================================
# FULL ANALYSIS TESTS
# =============================================================================

@pytest.mark.django_db
class TestTicketAnalysis:
    """Test complete sentiment analysis workflow."""

    def test_analyze_negative_ticket_full_workflow(self, negative_ticket):
        """Test full analysis workflow for negative ticket."""
        result = TicketSentimentAnalyzer.analyze_ticket_sentiment(negative_ticket)

        assert 'sentiment_score' in result
        assert 'sentiment_label' in result
        assert 'emotions' in result
        assert 'escalated' in result

        # Verify ticket was updated
        negative_ticket.refresh_from_db()
        assert negative_ticket.sentiment_score is not None
        assert negative_ticket.sentiment_label is not None
        assert negative_ticket.sentiment_analyzed_at is not None

    def test_analyze_positive_ticket_full_workflow(self, positive_ticket):
        """Test full analysis workflow for positive ticket."""
        result = TicketSentimentAnalyzer.analyze_ticket_sentiment(positive_ticket)

        assert result['escalated'] is False, "Positive ticket should not escalate"
        assert result['sentiment_score'] > 6.0, "Should have positive score"

    def test_analyze_ticket_with_comments(self, mock_ticket):
        """Test analysis includes ticket comments."""
        mock_ticket.comments = "Very frustrated with the service"
        mock_ticket.save()

        text = TicketSentimentAnalyzer._extract_text_for_analysis(mock_ticket)
        assert "frustrated" in text.lower(), "Comments should be included in analysis"

    def test_analyze_invalid_ticket_raises_error(self):
        """Test analysis with invalid ticket raises ValueError."""
        with pytest.raises(ValueError):
            TicketSentimentAnalyzer.analyze_ticket_sentiment(None)


# =============================================================================
# SIGNAL HANDLER TESTS
# =============================================================================

@pytest.mark.django_db
class TestSignalHandlers:
    """Test signal handler triggering."""

    @patch('apps.y_helpdesk.tasks.sentiment_analysis_tasks.AnalyzeTicketSentimentTask.delay')
    def test_signal_triggers_on_ticket_creation(self, mock_delay, db):
        """Test signal triggers sentiment analysis on ticket creation."""
        from apps.onboarding.models import Bt
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(name="Test", subdomain="test")
        bu = Bt.objects.create(buname="Test BU", bucode="TST", tenant=tenant)

        # Create ticket - should trigger signal
        ticket = Ticket.objects.create(
            ticketdesc="Test ticket",
            ticketno="TST#100",
            status="NEW",
            bu=bu,
            tenant=tenant
        )

        # Verify task was queued
        mock_delay.assert_called_once_with(ticket.id)

    @patch('apps.y_helpdesk.tasks.sentiment_analysis_tasks.AnalyzeTicketSentimentTask.delay')
    def test_signal_not_triggered_on_update(self, mock_delay, mock_ticket):
        """Test signal does not trigger on ticket update."""
        mock_delay.reset_mock()

        # Update ticket - should NOT trigger signal
        mock_ticket.priority = 'HIGH'
        mock_ticket.save()

        # Verify task was NOT queued
        assert not mock_delay.called, "Signal should only trigger on creation"


# =============================================================================
# CELERY TASK TESTS
# =============================================================================

@pytest.mark.django_db
class TestCeleryTasks:
    """Test Celery task execution."""

    def test_analyze_ticket_task_success(self, mock_ticket):
        """Test successful task execution."""
        task = AnalyzeTicketSentimentTask()
        result = task.run(mock_ticket.id)

        assert result['success'] is True
        assert 'sentiment_score' in result
        assert result['ticket_id'] == mock_ticket.id

    def test_analyze_ticket_task_not_found(self):
        """Test task with non-existent ticket."""
        task = AnalyzeTicketSentimentTask()

        with pytest.raises(ObjectDoesNotExist):
            task.run(999999)

    @patch('apps.y_helpdesk.services.ticket_sentiment_analyzer.TicketSentimentAnalyzer.analyze_ticket_sentiment')
    def test_task_retries_on_database_error(self, mock_analyze, mock_ticket):
        """Test task retries on database errors."""
        from django.db import DatabaseError

        mock_analyze.side_effect = DatabaseError("Connection lost")
        task = AnalyzeTicketSentimentTask()

        with pytest.raises(Exception):  # Should raise retry exception
            task.run(mock_ticket.id)

    def test_bulk_analyze_task_processes_multiple_tickets(self, db):
        """Test bulk analysis task."""
        from apps.onboarding.models import Bt
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(name="Test", subdomain="test")
        bu = Bt.objects.create(buname="Test BU", bucode="TST", tenant=tenant)

        # Create multiple tickets
        tickets = [
            Ticket.objects.create(
                ticketdesc=f"Test ticket {i}",
                ticketno=f"TST#{i}",
                bu=bu,
                tenant=tenant
            )
            for i in range(5)
        ]

        ticket_ids = [t.id for t in tickets]

        # Run bulk task
        task = BulkAnalyzeTicketSentimentTask()
        result = task.run(ticket_ids=ticket_ids)

        assert result['success'] is True
        assert result['processed'] == 5
        assert result['failed'] == 0


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================

@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_ticket_description(self, db):
        """Test handling of empty ticket description."""
        from apps.onboarding.models import Bt
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(name="Test", subdomain="test")
        bu = Bt.objects.create(buname="Test BU", bucode="TST", tenant=tenant)

        ticket = Ticket.objects.create(
            ticketdesc="",
            ticketno="TST#999",
            bu=bu,
            tenant=tenant
        )

        with pytest.raises(ValueError):
            TicketSentimentAnalyzer.analyze_ticket_sentiment(ticket)

    def test_very_long_text(self, mock_ticket):
        """Test handling of very long ticket descriptions."""
        long_text = "This is a test. " * 1000  # 10000+ characters
        mock_ticket.ticketdesc = long_text
        mock_ticket.save()

        result = TicketSentimentAnalyzer.analyze_ticket_sentiment(mock_ticket)
        assert result['sentiment_score'] is not None

    def test_special_characters_in_text(self, mock_ticket):
        """Test handling of special characters."""
        mock_ticket.ticketdesc = "Test!@#$%^&*(){}[]<>?/\\|~`"
        mock_ticket.save()

        result = TicketSentimentAnalyzer.analyze_ticket_sentiment(mock_ticket)
        assert result['sentiment_score'] is not None

    @patch('apps.y_helpdesk.services.ticket_sentiment_analyzer.TextBlob')
    def test_textblob_import_failure(self, mock_textblob, mock_ticket):
        """Test graceful handling when TextBlob is not available."""
        mock_textblob.side_effect = ImportError("TextBlob not installed")

        score = TicketSentimentAnalyzer._calculate_sentiment_score("test")
        assert score == 5.0, "Should return neutral score when TextBlob fails"
