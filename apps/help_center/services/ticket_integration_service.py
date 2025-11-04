"""
Ticket Integration Service - Help-ticket correlation tracking.

Correlates help usage with ticket creation for effectiveness analysis.

Signals:
- post_save(Ticket) - Analyze help usage before ticket
- post_save(Ticket, status=RESOLVED) - Calculate resolution time

Following CLAUDE.md:
- Rule #7: Methods <50 lines
- Rule #11: Specific exception handling
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from apps.help_center.models import HelpTicketCorrelation, HelpArticleInteraction, HelpSearchHistory
from apps.help_center.services.search_service import SearchService

logger = logging.getLogger(__name__)


class TicketIntegrationService:
    """Correlate help usage with ticket creation."""

    @classmethod
    def analyze_ticket_help_usage(cls, ticket):
        """
        Check if user viewed help before creating ticket.

        Looks back 30 minutes for:
        - Article views
        - Searches
        - AI chat sessions
        """
        lookback_window = timezone.now() - timedelta(minutes=30)

        recent_views = HelpArticleInteraction.objects.filter(
            user=ticket.created_by,
            timestamp__gte=lookback_window,
            interaction_type=HelpArticleInteraction.InteractionType.VIEW
        ).select_related('article')

        recent_searches = HelpSearchHistory.objects.filter(
            user=ticket.created_by,
            timestamp__gte=lookback_window
        )

        help_activity = {
            'help_attempted': recent_views.exists() or recent_searches.exists(),
            'session_id': recent_views.first().session_id if recent_views.exists() else None,
            'articles_viewed': [view.article.id for view in recent_views],
            'search_queries': list(recent_searches.values_list('query', flat=True))
        }

        correlation = HelpTicketCorrelation.create_from_ticket(
            ticket=ticket,
            user_help_activity=help_activity
        )

        suggested_article = cls._find_relevant_article(ticket)
        if suggested_article:
            correlation.suggested_article = suggested_article
            correlation.relevant_article_exists = True
        else:
            correlation.content_gap = True

        correlation.save()

        logger.info(
            "ticket_help_correlation_created",
            extra={
                'ticket_id': ticket.id,
                'help_attempted': help_activity['help_attempted'],
                'content_gap': correlation.content_gap
            }
        )

        return correlation

    @classmethod
    def _find_relevant_article(cls, ticket):
        """Search for article matching ticket topic."""
        search_results = SearchService.hybrid_search(
            tenant=ticket.tenant,
            user=ticket.created_by,
            query=ticket.title,
            limit=1,
            role_filter=False
        )

        if search_results['total'] > 0:
            from apps.help_center.models import HelpArticle
            article_id = search_results['results'][0]['id']
            return HelpArticle.objects.get(id=article_id)

        return None

    @classmethod
    def update_resolution_time(cls, ticket):
        """Calculate resolution time when ticket is closed."""
        try:
            correlation = HelpTicketCorrelation.objects.get(ticket=ticket)

            resolution_time = ticket.resolved_at - ticket.created_at
            correlation.resolution_time_minutes = int(resolution_time.total_seconds() / 60)
            correlation.save(update_fields=['resolution_time_minutes'])

            logger.info(
                "ticket_resolution_time_updated",
                extra={'ticket_id': ticket.id, 'resolution_time_minutes': correlation.resolution_time_minutes}
            )

        except HelpTicketCorrelation.DoesNotExist:
            logger.warning(f"No correlation found for ticket {ticket.id}")


# Signal handlers
@receiver(post_save, sender='y_helpdesk.Ticket')
def on_ticket_created(sender, instance, created, **kwargs):
    """Trigger help correlation analysis when ticket is created."""
    if created:
        TicketIntegrationService.analyze_ticket_help_usage(instance)


@receiver(post_save, sender='y_helpdesk.Ticket')
def on_ticket_resolved(sender, instance, **kwargs):
    """Update resolution time when ticket is resolved."""
    if hasattr(instance, 'resolved_at') and instance.resolved_at:
        TicketIntegrationService.update_resolution_time(instance)
