"""
Ticket Sentiment Analysis Service

Feature 2: NL/AI Platform Quick Win - Sentiment Analysis on Tickets

Analyzes ticket descriptions and comments to:
1. Calculate sentiment score (0-10 scale)
2. Classify sentiment (very_negative to very_positive)
3. Detect emotions (frustration, anger, satisfaction)
4. Auto-escalate highly negative tickets

Leverages patterns from apps/journal/ml/analytics_engine.py
Uses TextBlob for sentiment analysis (already in requirements)

Following CLAUDE.md:
- Rule #7: <150 lines per class
- Rule #11: Specific exception handling
- Rule #13: Type hints
- Rule #14: Comprehensive logging
"""

from typing import Dict, Optional, List, Tuple
from django.utils import timezone
from django.db import DatabaseError
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.y_helpdesk.exceptions import (
    SENTIMENT_ANALYSIS_EXCEPTIONS,
    SentimentAnalysisError
)
import logging

logger = logging.getLogger('y_helpdesk.sentiment')


class TicketSentimentAnalyzer:
    """
    Analyze sentiment from ticket descriptions and comments.

    Sentiment Score Scale:
    - 0-2: Very Negative (requires immediate attention)
    - 2-4: Negative (priority boost)
    - 4-6: Neutral (standard handling)
    - 6-8: Positive (satisfied customer)
    - 8-10: Very Positive (excellent experience)
    """

    # Frustration keywords for emotion detection
    FRUSTRATION_KEYWORDS = [
        'third time', 'still not fixed', 'not working', 'unbearable',
        'frustrated', 'angry', 'disappointed', 'terrible', 'worst',
        'broken', 'useless', 'never works', 'always fails', 'fed up',
        'ridiculous', 'unacceptable', 'urgent', 'critical', 'emergency'
    ]

    URGENCY_KEYWORDS = [
        'urgent', 'asap', 'immediately', 'critical', 'emergency',
        'right now', 'as soon as possible', 'time sensitive'
    ]

    SATISFACTION_KEYWORDS = [
        'thank', 'thanks', 'appreciate', 'excellent', 'great',
        'perfect', 'wonderful', 'helpful', 'resolved', 'fixed'
    ]

    @classmethod
    def analyze_ticket_sentiment(cls, ticket) -> Dict[str, any]:
        """
        Main analysis method - analyzes ticket description and comments.

        Args:
            ticket: Ticket instance to analyze

        Returns:
            dict: Analysis results with sentiment_score, label, emotions

        Raises:
            ValueError: If ticket is invalid
            DatabaseError: If save fails
        """
        if not ticket or not ticket.ticketdesc:
            logger.warning(
                "Cannot analyze sentiment: invalid ticket",
                extra={'ticket_id': getattr(ticket, 'id', None)}
            )
            raise ValueError("Ticket must have a description")

        logger.info(
            f"Analyzing sentiment for ticket {ticket.id}",
            extra={
                'ticket_id': ticket.id,
                'ticket_no': ticket.ticketno,
                'status': ticket.status
            }
        )

        # Extract all text for analysis
        text = cls._extract_text_for_analysis(ticket)

        # Calculate sentiment score
        sentiment_score = cls._calculate_sentiment_score(text)

        # Detect emotions
        emotions = cls._detect_emotions(text)

        # Determine label from score
        sentiment_label = cls._determine_sentiment_label(sentiment_score)

        # Update ticket with sentiment data
        try:
            ticket.sentiment_score = sentiment_score
            ticket.sentiment_label = sentiment_label
            ticket.emotion_detected = emotions
            ticket.sentiment_analyzed_at = timezone.now()
            ticket.save(update_fields=[
                'sentiment_score',
                'sentiment_label',
                'emotion_detected',
                'sentiment_analyzed_at'
            ])

            logger.info(
                f"Sentiment analysis complete: {sentiment_label} ({sentiment_score:.2f})",
                extra={
                    'ticket_id': ticket.id,
                    'sentiment_score': sentiment_score,
                    'sentiment_label': sentiment_label,
                    'emotions': list(emotions.keys())
                }
            )
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Failed to save sentiment analysis: {e}",
                extra={'ticket_id': ticket.id},
                exc_info=True
            )
            raise

        # Auto-escalate if very negative
        if cls._should_escalate(sentiment_score, ticket):
            cls._auto_escalate_negative_ticket(ticket, sentiment_score, emotions)

        return {
            'sentiment_score': sentiment_score,
            'sentiment_label': sentiment_label,
            'emotions': emotions,
            'escalated': cls._should_escalate(sentiment_score, ticket)
        }

    @classmethod
    def _extract_text_for_analysis(cls, ticket) -> str:
        """
        Extract all text from ticket description and comments.

        Args:
            ticket: Ticket instance

        Returns:
            str: Combined text for analysis
        """
        text = f"{ticket.ticketdesc} "

        # Add comments if available
        if ticket.comments:
            text += f"{ticket.comments} "

        # Add workflow history comments if available
        try:
            ticket_log = ticket.ticketlog
            if ticket_log and 'ticket_history' in ticket_log:
                for entry in ticket_log['ticket_history']:
                    if 'comments' in entry:
                        text += f"{entry['comments']} "
        except (KeyError, TypeError, AttributeError) as e:
            logger.debug(f"Could not extract workflow history: {e}")

        return text.strip()

    @classmethod
    def _calculate_sentiment_score(cls, text: str) -> float:
        """
        Calculate sentiment score using TextBlob.

        TextBlob polarity ranges from -1 (negative) to +1 (positive).
        We convert to 0-10 scale.

        Args:
            text: Text to analyze

        Returns:
            float: Sentiment score (0-10)
        """
        try:
            from textblob import TextBlob

            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 to 1

            # Convert to 0-10 scale
            # polarity -1 -> 0, polarity 0 -> 5, polarity 1 -> 10
            sentiment_score = (polarity + 1) * 5

            logger.debug(
                f"Sentiment calculation: polarity={polarity:.3f}, score={sentiment_score:.2f}"
            )

            return round(sentiment_score, 2)

        except ImportError:
            logger.error("TextBlob not installed - cannot calculate sentiment")
            return 5.0  # Default to neutral
        except SENTIMENT_ANALYSIS_EXCEPTIONS as e:
            logger.error(f"Error calculating sentiment: {e}", exc_info=True)
            return 5.0

    @classmethod
    def _detect_emotions(cls, text: str) -> Dict[str, float]:
        """
        Detect emotions based on keyword analysis.

        Args:
            text: Text to analyze

        Returns:
            dict: Emotion scores {emotion: score}
        """
        text_lower = text.lower()
        emotions = {}

        # Detect frustration
        frustration_count = sum(
            1 for keyword in cls.FRUSTRATION_KEYWORDS
            if keyword in text_lower
        )
        if frustration_count > 0:
            # Score increases with more keywords, capped at 1.0
            emotions['frustration'] = min(1.0, frustration_count * 0.2)

        # Detect urgency
        urgency_count = sum(
            1 for keyword in cls.URGENCY_KEYWORDS
            if keyword in text_lower
        )
        if urgency_count > 0:
            emotions['urgency'] = min(1.0, urgency_count * 0.3)

        # Detect satisfaction
        satisfaction_count = sum(
            1 for keyword in cls.SATISFACTION_KEYWORDS
            if keyword in text_lower
        )
        if satisfaction_count > 0:
            emotions['satisfaction'] = min(1.0, satisfaction_count * 0.25)

        logger.debug(f"Detected emotions: {emotions}")

        return emotions

    @classmethod
    def _determine_sentiment_label(cls, score: float) -> str:
        """
        Convert numerical score to human-readable label.

        Args:
            score: Sentiment score (0-10)

        Returns:
            str: Sentiment label
        """
        if score < 2.0:
            return 'very_negative'
        elif score < 4.0:
            return 'negative'
        elif score < 6.0:
            return 'neutral'
        elif score < 8.0:
            return 'positive'
        else:
            return 'very_positive'

    @classmethod
    def _should_escalate(cls, sentiment_score: float, ticket) -> bool:
        """
        Determine if ticket should be auto-escalated based on sentiment.

        Escalation criteria:
        - Sentiment score < 2.0 (very negative)
        - Status is NEW or OPEN (not already resolved/closed)
        - Not already escalated

        Args:
            sentiment_score: Calculated sentiment score
            ticket: Ticket instance

        Returns:
            bool: True if should escalate
        """
        should_escalate = (
            sentiment_score < 2.0 and
            ticket.status in ['NEW', 'OPEN'] and
            not ticket.isescalated
        )

        if should_escalate:
            logger.info(
                f"Ticket {ticket.id} meets escalation criteria",
                extra={
                    'ticket_id': ticket.id,
                    'sentiment_score': sentiment_score,
                    'status': ticket.status
                }
            )

        return should_escalate

    @classmethod
    def _auto_escalate_negative_ticket(
        cls,
        ticket,
        sentiment_score: float,
        emotions: Dict[str, float]
    ) -> None:
        """
        Auto-escalate ticket with very negative sentiment.

        Actions:
        1. Set priority to HIGH if not already
        2. Mark as escalated
        3. Add escalation note to workflow history
        4. Log escalation event

        Args:
            ticket: Ticket to escalate
            sentiment_score: Sentiment score that triggered escalation
            emotions: Detected emotions
        """
        logger.warning(
            f"Auto-escalating ticket {ticket.id} due to negative sentiment",
            extra={
                'ticket_id': ticket.id,
                'sentiment_score': sentiment_score,
                'emotions': emotions
            }
        )

        # Boost priority if not already high
        if ticket.priority != 'HIGH':
            ticket.priority = 'HIGH'

        # Mark as escalated
        ticket.isescalated = True

        # Add escalation note to history
        escalation_note = (
            f"Auto-escalated due to very negative sentiment "
            f"(score: {sentiment_score:.2f}). "
            f"Detected emotions: {', '.join(emotions.keys())}"
        )

        try:
            # Add to workflow history
            workflow = ticket.get_or_create_workflow()
            if not workflow.workflow_data:
                workflow.workflow_data = {}
            if 'workflow_history' not in workflow.workflow_data:
                workflow.workflow_data['workflow_history'] = []

            workflow.workflow_data['workflow_history'].append({
                'when': timezone.now().isoformat(),
                'who': 'SYSTEM',
                'action': 'AUTO_ESCALATED',
                'details': escalation_note,
                'sentiment_score': sentiment_score,
                'emotions': emotions
            })
            workflow.save(update_fields=['workflow_data'])

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Failed to add escalation note: {e}",
                extra={'ticket_id': ticket.id},
                exc_info=True
            )

        # Save priority and escalation status
        try:
            ticket.save(update_fields=['priority'])
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Failed to escalate ticket: {e}",
                extra={'ticket_id': ticket.id},
                exc_info=True
            )
            raise
