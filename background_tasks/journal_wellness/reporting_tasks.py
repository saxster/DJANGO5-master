"""
Reporting Tasks for Journal & Wellness System

Handles comprehensive analytics reporting and data generation including:
- Weekly wellness summary generation
- Tenant-wide wellness analytics
- Content effectiveness reporting
- Search index maintenance

All tasks use existing PostgreSQL Task Queue infrastructure with reports priority queue.
"""

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.db import DatabaseError, IntegrityError, ConnectionError
from django.contrib.auth import get_user_model
from django.db.models import Count, Avg
from datetime import timedelta
import logging

from apps.journal.models import JournalEntry
from apps.wellness.models import WellnessContent, WellnessUserProgress, WellnessContentInteraction

User = get_user_model()
logger = logging.getLogger('background_tasks')


@shared_task(
    soft_time_limit=3600,  # 1 hour - comprehensive analytics
    time_limit=4800         # 80 minutes hard limit
)
def generate_wellness_analytics_reports():
    """
    Generate comprehensive wellness analytics reports

    Runs weekly to:
    - Generate tenant-wide wellness reports
    - Calculate content effectiveness trends
    - Identify wellness program ROI metrics
    - Generate compliance and usage reports
    """

    logger.info("Generating wellness analytics reports")

    try:
        reports_generated = []

        # Generate reports for each tenant
        # Performance: Prefetch tenant users to avoid N+1 queries in generate_tenant_wellness_report
        from apps.tenants.models import Tenant
        tenants = Tenant.objects.prefetch_related('people_set').all()
        for tenant in tenants:
            try:
                report = generate_tenant_wellness_report(tenant)
                reports_generated.append(report)

            except (ValueError, TypeError) as e:
                logger.error(f"Failed to generate report for tenant {tenant.id}: {e}")

        # Generate system-wide effectiveness report
        effectiveness_report = generate_content_effectiveness_report()
        reports_generated.append(effectiveness_report)

        logger.info(f"Generated {len(reports_generated)} wellness analytics reports")

        return {
            'success': True,
            'reports_generated': len(reports_generated),
            'report_details': reports_generated,
            'generated_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Wellness analytics report generation failed: {e}")
        raise


@shared_task(
    soft_time_limit=600,  # 10 minutes - search indexing
    time_limit=900         # 15 minutes hard limit
)
def maintain_journal_search_index():
    """Maintain Elasticsearch search indexes"""
    logger.info("Maintaining journal search indexes")

    try:
        from .search import JournalElasticsearchService
        es_service = JournalElasticsearchService()

        # Reindex entries with outdated search data
        outdated_entries = JournalEntry.objects.filter(
            updated_at__gte=timezone.now() - timedelta(hours=24),
            is_deleted=False
        )

        reindexed_count = 0
        for entry in outdated_entries:
            if es_service.index_journal_entry(entry):
                reindexed_count += 1

        return {
            'success': True,
            'reindexed_count': reindexed_count,
            'maintained_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Search index maintenance failed: {e}")
        raise


@shared_task(
    soft_time_limit=1800,  # 30 minutes - weekly summaries
    time_limit=2400         # 40 minutes hard limit
)
def weekly_wellness_summary():
    """Generate weekly wellness summary for all users"""
    logger.info("Generating weekly wellness summaries")

    try:
        # This would generate personalized weekly summaries for users
        # showing their wellness trends, achievements, and recommendations

        users_with_progress = WellnessUserProgress.objects.filter(
            total_content_viewed__gt=0
        ).select_related('user')

        summaries_generated = 0

        for progress in users_with_progress:
            try:
                # Generate weekly summary
                summary = generate_user_weekly_summary(progress.user)

                # TODO: Send summary via email or notification
                # send_weekly_summary_notification.delay(progress.user.id, summary)

                summaries_generated += 1

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Failed to generate weekly summary for user {progress.user.id}: {e}")

        return {
            'success': True,
            'summaries_generated': summaries_generated,
            'users_processed': users_with_progress.count()
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Weekly summary generation failed: {e}")
        raise


# Helper functions

def generate_tenant_wellness_report(tenant):
    """Generate wellness report for specific tenant"""
    logger.info(f"Generating wellness report for tenant {tenant.tenantname}")

    # Get tenant users
    tenant_users = User.objects.filter(tenant=tenant)

    # Get wellness metrics
    total_users = tenant_users.count()
    users_with_progress = WellnessUserProgress.objects.filter(user__in=tenant_users).count()

    # Get recent wellness interactions
    recent_interactions = WellnessContentInteraction.objects.filter(
        user__in=tenant_users,
        interaction_date__gte=timezone.now() - timedelta(days=30)
    )

    # Calculate engagement metrics
    active_users = recent_interactions.values('user').distinct().count()
    total_interactions = recent_interactions.count()
    avg_engagement = recent_interactions.aggregate(avg=Avg('engagement_score'))['avg'] or 0

    # Content category analysis
    category_stats = recent_interactions.values('content__category').annotate(
        count=Count('id'),
        avg_rating=Avg('user_rating')
    )

    report = {
        'tenant_name': tenant.tenantname,
        'reporting_period': '30_days',
        'user_metrics': {
            'total_users': total_users,
            'users_with_wellness_progress': users_with_progress,
            'active_users_last_30_days': active_users,
            'engagement_rate': round(active_users / total_users, 3) if total_users > 0 else 0
        },
        'interaction_metrics': {
            'total_interactions': total_interactions,
            'avg_engagement_score': round(avg_engagement, 2),
            'interactions_per_active_user': round(total_interactions / active_users, 1) if active_users > 0 else 0
        },
        'category_performance': list(category_stats),
        'generated_at': timezone.now().isoformat()
    }

    return report


def generate_content_effectiveness_report():
    """Generate system-wide content effectiveness report"""
    logger.info("Generating content effectiveness report")

    # Get all active content with interactions
    content_with_interactions = WellnessContent.objects.filter(
        is_active=True,
        interactions__isnull=False
    ).distinct()

    effectiveness_data = []

    for content in content_with_interactions:
        interactions = content.interactions.all()
        total = interactions.count()

        if total > 0:
            completed = interactions.filter(interaction_type='completed').count()
            positive = interactions.filter(
                interaction_type__in=['completed', 'bookmarked', 'acted_upon']
            ).count()

            effectiveness_data.append({
                'content_id': str(content.id),
                'title': content.title,
                'category': content.category,
                'evidence_level': content.evidence_level,
                'total_interactions': total,
                'completion_rate': round(completed / total, 3),
                'effectiveness_rate': round(positive / total, 3),
                'priority_score': content.priority_score
            })

    # Sort by effectiveness
    effectiveness_data.sort(key=lambda x: x['effectiveness_rate'], reverse=True)

    return {
        'report_type': 'content_effectiveness',
        'top_performing_content': effectiveness_data[:10],
        'underperforming_content': [c for c in effectiveness_data if c['effectiveness_rate'] < 0.3],
        'total_content_analyzed': len(effectiveness_data),
        'generated_at': timezone.now().isoformat()
    }


def generate_user_weekly_summary(user):
    """Generate weekly wellness summary for individual user"""
    # Get user's entries from past week
    week_entries = JournalEntry.objects.filter(
        user=user,
        timestamp__gte=timezone.now() - timedelta(days=7),
        is_deleted=False
    )

    # Get wellness interactions from past week
    week_interactions = WellnessContentInteraction.objects.filter(
        user=user,
        interaction_date__gte=timezone.now() - timedelta(days=7)
    )

    summary = {
        'user_name': user.peoplename,
        'week_ending': timezone.now().date().isoformat(),
        'journal_activity': {
            'entries_created': week_entries.count(),
            'wellbeing_entries': week_entries.filter(
                entry_type__in=['MOOD_CHECK_IN', 'STRESS_LOG', 'GRATITUDE']
            ).count()
        },
        'wellness_engagement': {
            'content_viewed': week_interactions.count(),
            'content_completed': week_interactions.filter(interaction_type='completed').count()
        },
        'key_insights': [],  # Would be populated with actual insights
        'recommendations': []  # Would be populated with weekly recommendations
    }

    return summary


# Task scheduling configuration for Django admin
JOURNAL_WELLNESS_PERIODIC_TASKS = {
    'daily_wellness_content_scheduling': {
        'task': 'background_tasks.journal_wellness_tasks.daily_wellness_content_scheduling',
        'schedule': 'cron(hour=8, minute=0)',  # 8 AM daily
        'description': 'Schedule daily wellness content for all users'
    },
    'update_all_user_streaks': {
        'task': 'background_tasks.journal_wellness_tasks.update_all_user_streaks',
        'schedule': 'cron(hour=23, minute=30)',  # 11:30 PM daily
        'description': 'Update wellness engagement streaks'
    },
    'enforce_data_retention_policies': {
        'task': 'background_tasks.journal_wellness_tasks.enforce_data_retention_policies',
        'schedule': 'cron(hour=2, minute=0)',  # 2 AM daily
        'description': 'Enforce data retention and auto-deletion policies'
    },
    'cleanup_old_wellness_interactions': {
        'task': 'background_tasks.journal_wellness_tasks.cleanup_old_wellness_interactions',
        'schedule': 'cron(hour=3, minute=0, day_of_week=0)',  # Sunday 3 AM weekly
        'description': 'Clean up old wellness interaction records'
    },
    'generate_wellness_analytics_reports': {
        'task': 'background_tasks.journal_wellness_tasks.generate_wellness_analytics_reports',
        'schedule': 'cron(hour=6, minute=0, day_of_week=1)',  # Monday 6 AM weekly
        'description': 'Generate comprehensive wellness analytics reports'
    },
    'maintain_journal_search_index': {
        'task': 'background_tasks.journal_wellness_tasks.maintain_journal_search_index',
        'schedule': 'cron(hour=4, minute=0)',  # 4 AM daily
        'description': 'Maintain Elasticsearch search indexes'
    },
    'weekly_wellness_summary': {
        'task': 'background_tasks.journal_wellness_tasks.weekly_wellness_summary',
        'schedule': 'cron(hour=7, minute=0, day_of_week=0)',  # Sunday 7 AM weekly
        'description': 'Generate weekly wellness summaries for users'
    }
}
