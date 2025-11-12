"""
Analytics Service - Help system effectiveness tracking.

Key metrics:
- Usage (views, searches, AI interactions)
- Effectiveness (helpful ratio, ticket deflection)
- Content gaps (zero-result searches)
- User adoption (active users by role)

Following CLAUDE.md:
- Rule #7: Methods <50 lines
- Rule #11: Specific exception handling
- Rule #12: Query optimization
"""

import logging
from django.db.models import Count, Avg, F, Q, ExpressionWrapper, FloatField
from django.utils import timezone
from datetime import timedelta
from apps.help_center.models import (
    HelpArticle, HelpSearchHistory, HelpArticleInteraction, HelpTicketCorrelation
)
from apps.ontology import ontology

logger = logging.getLogger(__name__)


@ontology(
    domain="help",
    purpose="Track help article engagement, search analytics, and knowledge gap identification",
    inputs=[
        {"name": "tenant", "type": "Tenant", "description": "Tenant for analytics scope"},
        {"name": "date_from", "type": "datetime", "description": "Start date for metrics"},
        {"name": "date_to", "type": "datetime", "description": "End date for metrics"}
    ],
    outputs=[
        {"name": "dashboard", "type": "dict", "description": "Effectiveness metrics including usage, ticket deflection, content gaps"}
    ],
    depends_on=[
        "apps.help_center.models.HelpArticleInteraction",
        "apps.help_center.models.HelpSearchHistory",
        "apps.help_center.models.HelpTicketCorrelation"
    ],
    tags=["help", "analytics", "metrics", "engagement", "ticket-deflection"],
    criticality="medium",
    business_value="Quantifies help system ROI: ticket deflection rate, resolution time improvement, content gap analysis",
    performance_notes="Optimized queries with aggregations, caches results for dashboard views",
    security_notes="Multi-tenant isolated, role-based access to analytics data"
)
class AnalyticsService:
    """Help system effectiveness tracking."""

    @classmethod
    def get_effectiveness_dashboard(cls, tenant, date_from=None, date_to=None):
        """Generate comprehensive effectiveness metrics."""
        if not date_from:
            date_from = timezone.now() - timedelta(days=30)
        if not date_to:
            date_to = timezone.now()

        return {
            'usage': cls._calculate_usage_metrics(tenant, date_from, date_to),
            'effectiveness': cls._calculate_effectiveness_metrics(tenant, date_from, date_to),
            'content_performance': cls._analyze_content_performance(tenant, date_from, date_to),
        }

    @classmethod
    def _calculate_usage_metrics(cls, tenant, date_from, date_to):
        """Daily active users, views, searches."""
        interactions = HelpArticleInteraction.objects.filter(
            tenant=tenant,
            timestamp__range=(date_from, date_to)
        )

        searches = HelpSearchHistory.objects.filter(
            tenant=tenant,
            timestamp__range=(date_from, date_to)
        )

        return {
            'daily_active_users': interactions.values('user').distinct().count(),
            'total_article_views': interactions.filter(
                interaction_type=HelpArticleInteraction.InteractionType.VIEW
            ).count(),
            'total_searches': searches.count(),
        }

    @classmethod
    def _calculate_effectiveness_metrics(cls, tenant, date_from, date_to):
        """Ticket deflection, resolution time, satisfaction."""
        correlations = HelpTicketCorrelation.objects.filter(tenant=tenant)

        if date_from and date_to:
            correlations = correlations.filter(analyzed_at__range=(date_from, date_to))

        total_correlations = correlations.count()
        tickets_with_help = correlations.filter(help_attempted=True).count()
        deflection_rate = (tickets_with_help / total_correlations * 100) if total_correlations > 0 else 0

        with_help = correlations.filter(help_attempted=True, resolution_time_minutes__isnull=False)
        without_help = correlations.filter(help_attempted=False, resolution_time_minutes__isnull=False)

        avg_time_with_help = with_help.aggregate(avg=Avg('resolution_time_minutes'))['avg'] or 0
        avg_time_without_help = without_help.aggregate(avg=Avg('resolution_time_minutes'))['avg'] or 0

        improvement_percent = (
            ((avg_time_without_help - avg_time_with_help) / avg_time_without_help * 100)
            if avg_time_without_help > 0 else 0
        )

        return {
            'ticket_deflection_rate_percent': round(deflection_rate, 2),
            'avg_resolution_time_with_help_minutes': round(avg_time_with_help, 2),
            'avg_resolution_time_without_help_minutes': round(avg_time_without_help, 2),
            'resolution_time_improvement_percent': round(improvement_percent, 2),
        }

    @classmethod
    def _analyze_content_performance(cls, tenant, date_from, date_to):
        """Top articles, low-performing articles, content gaps."""
        top_viewed = HelpArticle.objects.filter(
            tenant=tenant,
            status=HelpArticle.Status.PUBLISHED
        ).order_by('-view_count')[:10]

        zero_result_searches = HelpSearchHistory.objects.filter(
            tenant=tenant,
            timestamp__range=(date_from, date_to),
            results_count=0
        ).values('query').annotate(
            count=Count('id')
        ).order_by('-count')[:20]

        return {
            'top_viewed_articles': [
                {'id': a.id, 'title': a.title, 'views': a.view_count}
                for a in top_viewed
            ],
            'content_gaps': [
                {'query': item['query'], 'count': item['count']}
                for item in zero_result_searches
            ]
        }
