"""
Analytics Service - Generate wellness engagement analytics and insights

Responsible for:
- Generating comprehensive wellness analytics
- Calculating engagement summaries
- Analyzing content effectiveness by category
- Tracking user preferences and trends
- Providing recommendations for engagement improvement
"""

from datetime import timedelta

from django.db.models import (
    Avg,
    Case,
    Count,
    IntegerField,
    Max,
    Q,
    Value,
)
from django.db.models.functions import ExtractHour
from django.utils import timezone

from apps.wellness.logging import get_wellness_logger
from apps.wellness.models import WellnessContentInteraction

logger = get_wellness_logger(__name__)


class AnalyticsService:
    """Service for generating wellness engagement analytics"""

    @staticmethod
    def generate_wellness_analytics(user, days=30):
        """
        Generate comprehensive wellness analytics

        Args:
            user: User object
            days: Number of days to analyze

        Returns:
            dict: Comprehensive analytics with engagement, effectiveness, preferences, trends
        """
        analysis_window_end = timezone.now()
        since_date = analysis_window_end - timedelta(days=days)

        interactions = WellnessContentInteraction.objects.filter(
            user=user,
            interaction_date__gte=since_date
        )

        total_interactions = interactions.count()
        unique_content = interactions.values('content').distinct().count()

        base_score = Case(
            When(interaction_type='viewed', then=Value(1)),
            When(interaction_type='completed', then=Value(3)),
            When(interaction_type='bookmarked', then=Value(2)),
            When(interaction_type='shared', then=Value(4)),
            When(interaction_type='rated', then=Value(2)),
            When(interaction_type='acted_upon', then=Value(5)),
            When(interaction_type='requested_more', then=Value(3)),
            When(interaction_type='dismissed', then=Value(-1)),
            default=Value(0),
            output_field=IntegerField()
        )
        rating_bonus = Case(
            When(user_rating__gte=4, then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )
        completion_bonus = Case(
            When(completion_percentage__gte=80, then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )

        annotated_interactions = interactions.annotate(
            engagement_score=base_score + rating_bonus + completion_bonus
        )
        avg_engagement = annotated_interactions.aggregate(
            avg=Avg('engagement_score')
        )['avg'] or 0.0

        category_stats_raw = annotated_interactions.values('content__category').annotate(
            interaction_count=Count('id'),
            avg_rating=Avg('user_rating'),
            completed_count=Count('id', filter=Q(interaction_type='completed')),
            avg_completion=Avg('completion_percentage'),
            avg_engagement=Avg('engagement_score'),
        )
        category_stats = []
        for row in category_stats_raw:
            total = row['interaction_count'] or 0
            completion_rate = (
                (row['completed_count'] / total) * 100 if total else 0
            )
            category_stats.append({
                'category': row['content__category'] or 'uncategorized',
                'interaction_count': total,
                'avg_rating': round(row['avg_rating'], 2) if row['avg_rating'] is not None else None,
                'avg_completion_percentage': round(row['avg_completion'], 2) if row['avg_completion'] is not None else None,
                'avg_engagement_score': round(row['avg_engagement'] or 0, 2),
                'completion_rate': round(completion_rate, 2),
            })

        top_content_raw = annotated_interactions.values(
            'content_id',
            'content__title',
            'content__category'
        ).annotate(
            interaction_count=Count('id'),
            avg_engagement=Avg('engagement_score'),
            avg_rating=Avg('user_rating'),
            avg_completion=Avg('completion_percentage'),
            last_interaction=Max('interaction_date')
        ).order_by('-avg_engagement', '-interaction_count')[:5]
        top_performing_content = [
            {
                'content_id': row['content_id'],
                'title': row['content__title'],
                'category': row['content__category'],
                'interaction_count': row['interaction_count'],
                'avg_engagement_score': round(row['avg_engagement'] or 0, 2),
                'avg_completion_percentage': round(row['avg_completion'], 2) if row['avg_completion'] is not None else None,
                'avg_rating': round(row['avg_rating'], 2) if row['avg_rating'] is not None else None,
                'last_interaction': row['last_interaction'].isoformat() if row['last_interaction'] else None,
            }
            for row in top_content_raw
        ]

        preferred_categories_raw = annotated_interactions.values('content__category').annotate(
            avg_engagement=Avg('engagement_score'),
            interaction_count=Count('id')
        ).order_by('-avg_engagement', '-interaction_count')[:3]
        preferred_categories = [
            {
                'category': row['content__category'],
                'avg_engagement_score': round(row['avg_engagement'] or 0, 2),
                'interaction_count': row['interaction_count']
            }
            for row in preferred_categories_raw
        ]

        optimal_delivery_time = None
        interaction_hours = annotated_interactions.annotate(
            hour=ExtractHour('interaction_date')
        ).values('hour').annotate(count=Count('id')).order_by('-count')

        if interaction_hours:
            peak_hour = interaction_hours[0]['hour']
            if peak_hour is not None:
                optimal_delivery_time = f"{int(peak_hour):02d}:00"

        midpoint = since_date + timedelta(days=days / 2)
        first_half = annotated_interactions.filter(interaction_date__lt=midpoint)
        second_half = annotated_interactions.filter(interaction_date__gte=midpoint)
        first_count = first_half.count()
        second_count = second_half.count()

        engagement_trend = 'stable'
        if first_count == 0 and second_count > 0:
            engagement_trend = 'increasing'
        elif second_count == 0 and first_count > 0:
            engagement_trend = 'decreasing'
        elif first_count:
            change_ratio = (second_count - first_count) / first_count
            if change_ratio > 0.1:
                engagement_trend = 'increasing'
            elif change_ratio < -0.1:
                engagement_trend = 'decreasing'

        def _category_distribution(qs):
            distribution = qs.values('content__category').annotate(total=Count('id'))
            total = sum(item['total'] for item in distribution) or 1
            return {
                (item['content__category'] or 'uncategorized'): item['total'] / total
                for item in distribution
            }

        category_shifts = []
        if total_interactions:
            first_dist = _category_distribution(first_half)
            second_dist = _category_distribution(second_half)
            for category in set(first_dist) | set(second_dist):
                delta = round(
                    (second_dist.get(category, 0) - first_dist.get(category, 0)) * 100,
                    2
                )
                if abs(delta) >= 5:
                    category_shifts.append({
                        'category': category,
                        'delta_percentage': delta
                    })

        recommendations = []
        if total_interactions < 5:
            recommendations.append({
                'type': 'engagement',
                'message': 'Encourage more wellness interactions to build a personalization baseline.'
            })
        if preferred_categories:
            recommendations.append({
                'type': 'personalization',
                'message': f"Highlight additional content in {preferred_categories[0]['category']} to reinforce engagement."
            })
        if engagement_trend == 'decreasing':
            recommendations.append({
                'type': 'retention',
                'message': 'Engagement is trending down; send a check-in nudging new wellness activities.'
            })

        if not recommendations:
            recommendations.append({
                'type': 'status',
                'message': 'Engagement metrics look healthy for this period.'
            })

        trend_status = engagement_trend if total_interactions else 'no_data'

        return {
            'engagement_summary': {
                'total_interactions': total_interactions,
                'unique_content_viewed': unique_content,
                'avg_engagement_score': round(avg_engagement, 2),
                'analysis_period_days': days
            },
            'content_effectiveness': {
                'category_stats': category_stats,
                'top_performing_content': top_performing_content
            },
            'user_preferences': {
                'preferred_categories': preferred_categories,
                'optimal_delivery_time': optimal_delivery_time
            },
            'trend_analysis': {
                'engagement_trend': trend_status,
                'category_shifts': category_shifts
            },
            'recommendations': recommendations,
            'analysis_metadata': {
                'generated_at': analysis_window_end.isoformat(),
                'algorithm_version': '1.1.0'
            }
        }
