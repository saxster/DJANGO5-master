"""
Help Center Ticket Correlation Model

Correlate help usage with ticket creation for effectiveness analysis.

Key questions:
- Did user try help before creating ticket?
- Which articles did they view?
- Was relevant content available?
- How long did it take to resolve with/without help?

Created: 2025-11-04 (Split from god file)
"""

from django.db import models
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager


class HelpTicketCorrelation(TenantAwareModel):
    """
    Correlate help usage with ticket creation for effectiveness analysis.

    Key questions (110 lines - under 150 limit):
    - Did user try help before creating ticket?
    - Which articles did they view?
    - Was relevant content available?
    - How long did it take to resolve with/without help?
    """

    ticket = models.OneToOneField(
        'y_helpdesk.Ticket',
        on_delete=models.CASCADE,
        related_name='help_correlation'
    )

    help_attempted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Did user view any help articles before creating ticket?"
    )

    help_session_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Link to help session if help was attempted"
    )

    articles_viewed = models.ManyToManyField(
        'help_center.HelpArticle',
        blank=True,
        related_name='ticket_correlations'
    )

    search_queries = models.JSONField(
        default=list,
        help_text="List of search queries attempted before ticket creation"
    )

    relevant_article_exists = models.BooleanField(
        null=True,
        blank=True,
        help_text="Based on ticket analysis, does relevant help content exist?"
    )

    content_gap = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Should content team create new article for this topic?"
    )

    suggested_article = models.ForeignKey(
        'help_center.HelpArticle',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='suggested_for_tickets',
        help_text="Article to show in ticket view"
    )

    resolution_time_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time from ticket creation to resolution (minutes)"
    )

    analyzed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When correlation analysis was performed"
    )

    objects = TenantAwareManager()

    class Meta:
        db_table = 'help_center_ticket_correlation'
        indexes = [
            models.Index(fields=['help_attempted', 'content_gap'], name='help_ticket_gap_idx'),
            models.Index(fields=['ticket'], name='help_ticket_correlation_idx'),
        ]

    @classmethod
    def create_from_ticket(cls, ticket, user_help_activity=None):
        """
        Create correlation record when ticket is created.

        Args:
            ticket: Ticket instance
            user_help_activity: Dict with {
                'help_attempted': bool,
                'session_id': UUID,
                'articles_viewed': [article_ids],
                'search_queries': [queries]
            }
        """
        correlation = cls.objects.create(
            ticket=ticket,
            tenant=ticket.tenant,
            help_attempted=False,
            content_gap=False,
            analyzed_at=timezone.now()
        )

        if user_help_activity:
            correlation.help_attempted = user_help_activity.get('help_attempted', False)
            correlation.help_session_id = user_help_activity.get('session_id')
            correlation.search_queries = user_help_activity.get('search_queries', [])

            article_ids = user_help_activity.get('articles_viewed', [])
            if article_ids:
                correlation.articles_viewed.set(article_ids)

            correlation.save()

        return correlation

    def __str__(self):
        status = "with help" if self.help_attempted else "without help"
        return f"Ticket #{self.ticket.id} ({status})"
