"""
Sentiment Analysis Celery Tasks

Feature 2: NL/AI Platform Quick Win - Asynchronous Sentiment Analysis

Tasks:
- AnalyzeTicketSentimentTask: Analyze ticket sentiment after creation
- BulkAnalyzeTicketSentimentTask: Batch analyze existing tickets

Following CLAUDE.md:
- Rule #11: Specific exception handling (DATABASE_EXCEPTIONS)
- Rule #14: Comprehensive logging with correlation IDs
- Celery best practices: IdempotentTask base, retry policies
"""

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from apps.core.tasks.base import IdempotentTask
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.y_helpdesk.exceptions import SENTIMENT_ANALYSIS_EXCEPTIONS
import logging

logger = logging.getLogger('y_helpdesk.tasks')


@shared_task(base=IdempotentTask, bind=True)
class AnalyzeTicketSentimentTask(IdempotentTask):
    """
    Analyze sentiment for a single ticket asynchronously.

    This task is triggered by post_save signal on ticket creation.
    Uses IdempotentTask to prevent duplicate analysis.

    Configuration:
    - max_retries: 3 (from BaseTask)
    - idempotency_ttl: 300 (5 minutes)
    - retry_backoff: True (exponential backoff)
    """

    name = 'helpdesk.sentiment.analyze_ticket'
    idempotency_ttl = 300  # 5 minutes - short TTL for quick re-analysis if needed
    max_retries = 3
    default_retry_delay = 30  # 30 seconds between retries

    def run(self, ticket_id: int) -> dict:
        """
        Execute sentiment analysis for the specified ticket.

        Args:
            ticket_id: ID of ticket to analyze

        Returns:
            dict: Analysis results

        Raises:
            ObjectDoesNotExist: If ticket not found
            ValueError: If ticket data is invalid
            DatabaseError: If save fails
        """
        from apps.y_helpdesk.models import Ticket
        from apps.y_helpdesk.services.ticket_sentiment_analyzer import TicketSentimentAnalyzer

        logger.info(
            f"Starting sentiment analysis for ticket {ticket_id}",
            extra={
                'ticket_id': ticket_id,
                'task_id': self.request.id,
                'task_name': self.name
            }
        )

        try:
            # Fetch ticket
            ticket = Ticket.objects.get(id=ticket_id)

            logger.debug(
                f"Fetched ticket: {ticket.ticketno}",
                extra={
                    'ticket_id': ticket_id,
                    'ticket_no': ticket.ticketno,
                    'status': ticket.status
                }
            )

            # Run sentiment analysis
            result = TicketSentimentAnalyzer.analyze_ticket_sentiment(ticket)

            logger.info(
                f"Sentiment analysis completed for ticket {ticket_id}: "
                f"{result['sentiment_label']} ({result['sentiment_score']:.2f})",
                extra={
                    'ticket_id': ticket_id,
                    'sentiment_score': result['sentiment_score'],
                    'sentiment_label': result['sentiment_label'],
                    'escalated': result['escalated']
                }
            )

            return {
                'success': True,
                'ticket_id': ticket_id,
                'sentiment_score': result['sentiment_score'],
                'sentiment_label': result['sentiment_label'],
                'emotions': result['emotions'],
                'escalated': result['escalated']
            }

        except ObjectDoesNotExist:
            logger.error(
                f"Ticket {ticket_id} not found for sentiment analysis",
                extra={
                    'ticket_id': ticket_id,
                    'task_id': self.request.id
                }
            )
            raise

        except ValueError as e:
            logger.error(
                f"Invalid ticket data for sentiment analysis: {e}",
                extra={
                    'ticket_id': ticket_id,
                    'error': str(e)
                },
                exc_info=True
            )
            # Don't retry for validation errors
            raise

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error during sentiment analysis: {e}",
                extra={
                    'ticket_id': ticket_id,
                    'error': str(e),
                    'retry_count': self.request.retries
                },
                exc_info=True
            )
            # Retry database errors with exponential backoff
            raise self.retry(exc=e, countdown=self.default_retry_delay)

        except SENTIMENT_ANALYSIS_EXCEPTIONS as e:
            logger.error(
                f"Unexpected error during sentiment analysis: {e}",
                extra={
                    'ticket_id': ticket_id,
                    'error': str(e),
                    'error_type': e.__class__.__name__
                },
                exc_info=True
            )
            # Retry unexpected errors
            raise self.retry(exc=e, countdown=self.default_retry_delay)


@shared_task(base=IdempotentTask, bind=True)
class BulkAnalyzeTicketSentimentTask(IdempotentTask):
    """
    Bulk analyze sentiment for multiple tickets.

    Useful for:
    - Initial migration of existing tickets
    - Re-analysis after algorithm updates
    - Batch processing for reports

    Configuration:
    - max_retries: 2
    - idempotency_ttl: 3600 (1 hour)
    - Batch size: 100 tickets
    """

    name = 'helpdesk.sentiment.bulk_analyze'
    idempotency_ttl = 3600  # 1 hour
    max_retries = 2
    soft_time_limit = 1800  # 30 minutes
    time_limit = 3600       # 1 hour

    def run(self, ticket_ids: list = None, status_filter: str = None, limit: int = 100) -> dict:
        """
        Bulk analyze sentiment for tickets.

        Args:
            ticket_ids: List of specific ticket IDs (optional)
            status_filter: Filter by status (e.g., 'NEW', 'OPEN')
            limit: Maximum number of tickets to process

        Returns:
            dict: Processing results with counts
        """
        from apps.y_helpdesk.models import Ticket
        from apps.y_helpdesk.services.ticket_sentiment_analyzer import TicketSentimentAnalyzer

        logger.info(
            f"Starting bulk sentiment analysis",
            extra={
                'ticket_ids': ticket_ids,
                'status_filter': status_filter,
                'limit': limit,
                'task_id': self.request.id
            }
        )

        # Build queryset
        if ticket_ids:
            tickets = Ticket.objects.filter(id__in=ticket_ids)
        else:
            tickets = Ticket.objects.filter(sentiment_score__isnull=True)
            if status_filter:
                tickets = tickets.filter(status=status_filter)

        tickets = tickets[:limit]
        total_count = tickets.count()

        logger.info(f"Processing {total_count} tickets for sentiment analysis")

        # Process tickets
        processed = 0
        failed = 0
        escalated = 0

        for ticket in tickets:
            try:
                result = TicketSentimentAnalyzer.analyze_ticket_sentiment(ticket)
                processed += 1
                if result['escalated']:
                    escalated += 1

                # Log progress every 10 tickets
                if processed % 10 == 0:
                    logger.info(
                        f"Bulk analysis progress: {processed}/{total_count} tickets processed"
                    )

            except SENTIMENT_ANALYSIS_EXCEPTIONS as e:
                failed += 1
                logger.error(
                    f"Failed to analyze ticket {ticket.id}: {e}",
                    extra={
                        'ticket_id': ticket.id,
                        'error': str(e)
                    }
                )

        logger.info(
            f"Bulk sentiment analysis completed: "
            f"{processed} processed, {failed} failed, {escalated} escalated",
            extra={
                'total_count': total_count,
                'processed': processed,
                'failed': failed,
                'escalated': escalated
            }
        )

        return {
            'success': True,
            'total_count': total_count,
            'processed': processed,
            'failed': failed,
            'escalated': escalated
        }
