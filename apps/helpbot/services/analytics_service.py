"""
HelpBot Analytics Service

Tracks usage patterns, performance metrics, and provides insights for continuous improvement.
Integrates with existing monitoring infrastructure.
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from collections import defaultdict

from django.conf import settings
from django.db import models, transaction
from django.db.models import Count, Avg, Max, Min, F, Q
from django.utils import timezone
from django.core.cache import cache

from apps.helpbot.models import (
    HelpBotSession, HelpBotMessage, HelpBotFeedback,
    HelpBotKnowledge, HelpBotAnalytics, HelpBotContext
)

logger = logging.getLogger(__name__)


class HelpBotAnalyticsService:
    """
    Comprehensive analytics service for HelpBot usage and performance tracking.
    """

    def __init__(self):
        self.cache_prefix = 'helpbot_analytics'
        self.cache_timeout = getattr(settings, 'HELPBOT_ANALYTICS_CACHE_TIMEOUT', 3600)
        self.batch_size = getattr(settings, 'HELPBOT_ANALYTICS_BATCH_SIZE', 100)

    def record_session_metrics(self, session: HelpBotSession) -> bool:
        """Record metrics for a completed session."""
        try:
            with transaction.atomic():
                session_date = session.cdtz.date()
                session_hour = session.cdtz.hour

                # Session count metric
                self._increment_metric(
                    metric_type=HelpBotAnalytics.MetricTypeChoices.SESSION_COUNT,
                    value=1.0,
                    date=session_date,
                    hour=session_hour,
                    dimension_data={
                        'session_type': session.session_type,
                        'language': session.language,
                        'voice_enabled': session.voice_enabled,
                    }
                )

                # Message count metric
                message_count = session.messages.count()
                self._increment_metric(
                    metric_type=HelpBotAnalytics.MetricTypeChoices.MESSAGE_COUNT,
                    value=float(message_count),
                    date=session_date,
                    hour=session_hour,
                    dimension_data={
                        'session_type': session.session_type,
                    }
                )

                # User satisfaction if available
                if session.satisfaction_rating:
                    self._record_metric(
                        metric_type=HelpBotAnalytics.MetricTypeChoices.USER_SATISFACTION,
                        value=float(session.satisfaction_rating),
                        date=session_date,
                        hour=session_hour,
                        dimension_data={
                            'session_type': session.session_type,
                        }
                    )

                logger.debug(f"Recorded session metrics for {session.session_id}")
                return True

        except Exception as e:
            logger.error(f"Error recording session metrics: {e}")
            return False

    def record_response_time(self, message: HelpBotMessage) -> bool:
        """Record response time metrics for a bot message."""
        try:
            if (message.message_type == HelpBotMessage.MessageTypeChoices.BOT_RESPONSE
                and message.processing_time_ms):

                message_date = message.cdtz.date()
                message_hour = message.cdtz.hour

                self._record_metric(
                    metric_type=HelpBotAnalytics.MetricTypeChoices.RESPONSE_TIME,
                    value=float(message.processing_time_ms),
                    date=message_date,
                    hour=message_hour,
                    dimension_data={
                        'session_type': message.session.session_type,
                        'confidence_score': message.confidence_score,
                        'has_knowledge_sources': len(message.knowledge_sources) > 0,
                    }
                )

                return True

        except Exception as e:
            logger.error(f"Error recording response time: {e}")
            return False

    def record_knowledge_usage(self, knowledge_id: str, context: Dict[str, Any] = None) -> bool:
        """Record knowledge base usage metrics."""
        try:
            today = timezone.now().date()
            hour = timezone.now().hour

            self._increment_metric(
                metric_type=HelpBotAnalytics.MetricTypeChoices.KNOWLEDGE_USAGE,
                value=1.0,
                date=today,
                hour=hour,
                dimension_data={
                    'knowledge_id': knowledge_id,
                    'context': context or {},
                }
            )

            return True

        except Exception as e:
            logger.error(f"Error recording knowledge usage: {e}")
            return False

    def record_error_rate(self, error_type: str, context: Dict[str, Any] = None) -> bool:
        """Record error metrics."""
        try:
            today = timezone.now().date()
            hour = timezone.now().hour

            self._increment_metric(
                metric_type=HelpBotAnalytics.MetricTypeChoices.ERROR_RATE,
                value=1.0,
                date=today,
                hour=hour,
                dimension_data={
                    'error_type': error_type,
                    'context': context or {},
                }
            )

            return True

        except Exception as e:
            logger.error(f"Error recording error rate: {e}")
            return False

    def _increment_metric(self, metric_type: str, value: float, date: date,
                         hour: int = None, dimension_data: Dict[str, Any] = None) -> bool:
        """Increment an existing metric or create new one."""
        try:
            analytics, created = HelpBotAnalytics.objects.get_or_create(
                metric_type=metric_type,
                date=date,
                hour=hour,
                defaults={
                    'value': value,
                    'dimension_data': dimension_data or {}
                }
            )

            if not created:
                # Increment existing metric
                analytics.value = F('value') + value
                analytics.save(update_fields=['value'])

            return True

        except Exception as e:
            logger.error(f"Error incrementing metric: {e}")
            return False

    def _record_metric(self, metric_type: str, value: float, date: date,
                      hour: int = None, dimension_data: Dict[str, Any] = None) -> bool:
        """Record a metric value (for averages, etc.)."""
        try:
            HelpBotAnalytics.objects.create(
                metric_type=metric_type,
                value=value,
                date=date,
                hour=hour,
                dimension_data=dimension_data or {}
            )

            return True

        except Exception as e:
            logger.error(f"Error recording metric: {e}")
            return False

    def get_dashboard_data(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive dashboard data for the specified period."""
        try:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)

            # Use cache for expensive queries
            cache_key = f"{self.cache_prefix}_dashboard_{days}_{end_date}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data

            dashboard_data = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'overview': self._get_overview_metrics(start_date, end_date),
                'usage_trends': self._get_usage_trends(start_date, end_date),
                'performance_metrics': self._get_performance_metrics(start_date, end_date),
                'knowledge_analytics': self._get_knowledge_analytics(start_date, end_date),
                'user_satisfaction': self._get_satisfaction_metrics(start_date, end_date),
                'error_analysis': self._get_error_analysis(start_date, end_date),
            }

            # Cache the results
            cache.set(cache_key, dashboard_data, self.cache_timeout)

            return dashboard_data

        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {'error': str(e)}

    def _get_overview_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get high-level overview metrics."""
        try:
            # Total sessions
            total_sessions = HelpBotSession.objects.filter(
                cdtz__date__range=[start_date, end_date]
            ).count()

            # Total messages
            total_messages = HelpBotMessage.objects.filter(
                cdtz__date__range=[start_date, end_date]
            ).count()

            # Unique users
            unique_users = HelpBotSession.objects.filter(
                cdtz__date__range=[start_date, end_date]
            ).values('user').distinct().count()

            # Average session length (in messages)
            avg_session_length = HelpBotMessage.objects.filter(
                cdtz__date__range=[start_date, end_date]
            ).values('session').annotate(
                message_count=Count('message_id')
            ).aggregate(
                avg=Avg('message_count')
            )['avg'] or 0

            # Completion rate
            completed_sessions = HelpBotSession.objects.filter(
                cdtz__date__range=[start_date, end_date],
                current_state=HelpBotSession.StateChoices.COMPLETED
            ).count()

            completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0

            return {
                'total_sessions': total_sessions,
                'total_messages': total_messages,
                'unique_users': unique_users,
                'avg_session_length': round(avg_session_length, 2),
                'completion_rate': round(completion_rate, 2),
            }

        except Exception as e:
            logger.error(f"Error getting overview metrics: {e}")
            return {}

    def _get_usage_trends(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get usage trends over time."""
        try:
            # Daily session counts
            daily_sessions = HelpBotSession.objects.filter(
                cdtz__date__range=[start_date, end_date]
            ).extra(
                select={'date': 'DATE(cdtz)'}
            ).values('date').annotate(
                sessions=Count('session_id')
            ).order_by('date')

            # Hourly distribution
            hourly_distribution = HelpBotSession.objects.filter(
                cdtz__date__range=[start_date, end_date]
            ).extra(
                select={'hour': 'EXTRACT(hour FROM cdtz)'}
            ).values('hour').annotate(
                sessions=Count('session_id')
            ).order_by('hour')

            # Session type distribution
            session_types = HelpBotSession.objects.filter(
                cdtz__date__range=[start_date, end_date]
            ).values('session_type').annotate(
                count=Count('session_id')
            ).order_by('-count')

            return {
                'daily_sessions': list(daily_sessions),
                'hourly_distribution': list(hourly_distribution),
                'session_types': list(session_types),
            }

        except Exception as e:
            logger.error(f"Error getting usage trends: {e}")
            return {}

    def _get_performance_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get performance metrics."""
        try:
            # Response time statistics
            response_times = HelpBotMessage.objects.filter(
                cdtz__date__range=[start_date, end_date],
                message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
                processing_time_ms__isnull=False
            ).aggregate(
                avg_response_time=Avg('processing_time_ms'),
                min_response_time=Min('processing_time_ms'),
                max_response_time=Max('processing_time_ms')
            )

            # Confidence score distribution
            confidence_scores = HelpBotMessage.objects.filter(
                cdtz__date__range=[start_date, end_date],
                message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
                confidence_score__isnull=False
            ).aggregate(
                avg_confidence=Avg('confidence_score'),
                min_confidence=Min('confidence_score'),
                max_confidence=Max('confidence_score')
            )

            # High confidence responses (>0.8)
            high_confidence_count = HelpBotMessage.objects.filter(
                cdtz__date__range=[start_date, end_date],
                message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE,
                confidence_score__gt=0.8
            ).count()

            total_bot_messages = HelpBotMessage.objects.filter(
                cdtz__date__range=[start_date, end_date],
                message_type=HelpBotMessage.MessageTypeChoices.BOT_RESPONSE
            ).count()

            high_confidence_rate = (high_confidence_count / total_bot_messages * 100) if total_bot_messages > 0 else 0

            return {
                'avg_response_time_ms': round(response_times['avg_response_time'] or 0, 2),
                'min_response_time_ms': response_times['min_response_time'] or 0,
                'max_response_time_ms': response_times['max_response_time'] or 0,
                'avg_confidence_score': round(confidence_scores['avg_confidence'] or 0, 3),
                'high_confidence_rate': round(high_confidence_rate, 2),
            }

        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}

    def _get_knowledge_analytics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get knowledge base usage analytics."""
        try:
            # Most used knowledge articles
            knowledge_usage = defaultdict(int)

            messages_with_knowledge = HelpBotMessage.objects.filter(
                cdtz__date__range=[start_date, end_date],
                knowledge_sources__isnull=False
            ).exclude(knowledge_sources=[])

            for message in messages_with_knowledge:
                for source in message.knowledge_sources:
                    if 'id' in source:
                        knowledge_usage[source['id']] += 1

            # Get top knowledge articles with details
            top_knowledge = []
            for knowledge_id, usage_count in sorted(knowledge_usage.items(),
                                                   key=lambda x: x[1], reverse=True)[:10]:
                try:
                    knowledge = HelpBotKnowledge.objects.get(knowledge_id=knowledge_id)
                    top_knowledge.append({
                        'id': knowledge_id,
                        'title': knowledge.title,
                        'category': knowledge.category,
                        'usage_count': usage_count,
                        'effectiveness_score': knowledge.effectiveness_score,
                    })
                except HelpBotKnowledge.DoesNotExist:
                    continue

            # Knowledge effectiveness distribution
            effectiveness_stats = HelpBotKnowledge.objects.filter(
                is_active=True
            ).aggregate(
                avg_effectiveness=Avg('effectiveness_score'),
                min_effectiveness=Min('effectiveness_score'),
                max_effectiveness=Max('effectiveness_score')
            )

            # Knowledge coverage by category
            category_coverage = HelpBotKnowledge.objects.filter(
                is_active=True
            ).values('category').annotate(
                count=Count('knowledge_id')
            ).order_by('-count')

            return {
                'total_active_articles': HelpBotKnowledge.objects.filter(is_active=True).count(),
                'top_knowledge_articles': top_knowledge,
                'avg_effectiveness_score': round(effectiveness_stats['avg_effectiveness'] or 0, 3),
                'category_coverage': list(category_coverage),
                'total_knowledge_references': sum(knowledge_usage.values()),
            }

        except Exception as e:
            logger.error(f"Error getting knowledge analytics: {e}")
            return {}

    def _get_satisfaction_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get user satisfaction metrics."""
        try:
            # Session satisfaction ratings
            satisfaction_ratings = HelpBotSession.objects.filter(
                cdtz__date__range=[start_date, end_date],
                satisfaction_rating__isnull=False
            ).aggregate(
                avg_rating=Avg('satisfaction_rating'),
                total_ratings=Count('satisfaction_rating')
            )

            # Feedback analysis
            feedback_counts = HelpBotFeedback.objects.filter(
                cdtz__date__range=[start_date, end_date]
            ).values('feedback_type').annotate(
                count=Count('feedback_id')
            ).order_by('-count')

            # Positive vs negative feedback
            positive_feedback = HelpBotFeedback.objects.filter(
                cdtz__date__range=[start_date, end_date],
                feedback_type__in=[
                    HelpBotFeedback.FeedbackTypeChoices.HELPFUL
                ]
            ).count()

            negative_feedback = HelpBotFeedback.objects.filter(
                cdtz__date__range=[start_date, end_date],
                feedback_type__in=[
                    HelpBotFeedback.FeedbackTypeChoices.NOT_HELPFUL,
                    HelpBotFeedback.FeedbackTypeChoices.INCORRECT
                ]
            ).count()

            total_feedback = positive_feedback + negative_feedback
            satisfaction_rate = (positive_feedback / total_feedback * 100) if total_feedback > 0 else 0

            return {
                'avg_session_rating': round(satisfaction_ratings['avg_rating'] or 0, 2),
                'total_session_ratings': satisfaction_ratings['total_ratings'] or 0,
                'feedback_breakdown': list(feedback_counts),
                'satisfaction_rate': round(satisfaction_rate, 2),
                'total_feedback': total_feedback,
            }

        except Exception as e:
            logger.error(f"Error getting satisfaction metrics: {e}")
            return {}

    def _get_error_analysis(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get error analysis data."""
        try:
            # Sessions with errors
            error_sessions = HelpBotSession.objects.filter(
                cdtz__date__range=[start_date, end_date],
                current_state=HelpBotSession.StateChoices.ERROR
            ).count()

            total_sessions = HelpBotSession.objects.filter(
                cdtz__date__range=[start_date, end_date]
            ).count()

            error_rate = (error_sessions / total_sessions * 100) if total_sessions > 0 else 0

            # Context errors
            contexts_with_errors = HelpBotContext.objects.filter(
                timestamp__date__range=[start_date, end_date]
            ).exclude(error_context={}).count()

            # Common error patterns (from context)
            error_patterns = defaultdict(int)
            error_contexts = HelpBotContext.objects.filter(
                timestamp__date__range=[start_date, end_date]
            ).exclude(error_context={})

            for context in error_contexts:
                error_data = context.error_context
                if 'error_type' in error_data:
                    error_patterns[error_data['error_type']] += 1
                elif 'http_status' in error_data:
                    error_patterns[f"HTTP_{error_data['http_status']}"] += 1

            return {
                'session_error_rate': round(error_rate, 2),
                'total_error_sessions': error_sessions,
                'contexts_with_errors': contexts_with_errors,
                'common_error_patterns': dict(error_patterns),
            }

        except Exception as e:
            logger.error(f"Error getting error analysis: {e}")
            return {}

    def generate_insights(self, days: int = 30) -> List[Dict[str, Any]]:
        """Generate actionable insights from analytics data."""
        try:
            dashboard_data = self.get_dashboard_data(days)
            insights = []

            # Performance insights
            performance = dashboard_data.get('performance_metrics', {})
            avg_response_time = performance.get('avg_response_time_ms', 0)

            if avg_response_time > 2000:  # > 2 seconds
                insights.append({
                    'type': 'performance',
                    'severity': 'warning',
                    'title': 'Slow Response Times',
                    'description': f'Average response time is {avg_response_time:.0f}ms, consider optimization.',
                    'recommendation': 'Review knowledge base indexing and LLM performance.'
                })

            # Satisfaction insights
            satisfaction = dashboard_data.get('user_satisfaction', {})
            satisfaction_rate = satisfaction.get('satisfaction_rate', 0)

            if satisfaction_rate < 70:  # < 70% satisfaction
                insights.append({
                    'type': 'satisfaction',
                    'severity': 'warning',
                    'title': 'Low User Satisfaction',
                    'description': f'User satisfaction rate is {satisfaction_rate:.1f}%.',
                    'recommendation': 'Review feedback and improve knowledge base content.'
                })

            # Usage insights
            overview = dashboard_data.get('overview', {})
            completion_rate = overview.get('completion_rate', 0)

            if completion_rate < 60:  # < 60% completion
                insights.append({
                    'type': 'usage',
                    'severity': 'info',
                    'title': 'Low Session Completion Rate',
                    'description': f'Only {completion_rate:.1f}% of sessions are completed.',
                    'recommendation': 'Analyze drop-off points and improve user experience.'
                })

            # Knowledge insights
            knowledge = dashboard_data.get('knowledge_analytics', {})
            avg_effectiveness = knowledge.get('avg_effectiveness_score', 0)

            if avg_effectiveness < 0.6:  # < 60% effectiveness
                insights.append({
                    'type': 'knowledge',
                    'severity': 'warning',
                    'title': 'Knowledge Base Effectiveness',
                    'description': f'Average knowledge effectiveness is {avg_effectiveness:.1f}.',
                    'recommendation': 'Update and improve low-performing knowledge articles.'
                })

            # Error insights
            error_analysis = dashboard_data.get('error_analysis', {})
            error_rate = error_analysis.get('session_error_rate', 0)

            if error_rate > 10:  # > 10% error rate
                insights.append({
                    'type': 'errors',
                    'severity': 'error',
                    'title': 'High Error Rate',
                    'description': f'Error rate is {error_rate:.1f}%.',
                    'recommendation': 'Investigate and fix common error patterns.'
                })

            return insights

        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return []

    def get_user_analytics(self, user, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a specific user."""
        try:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)

            user_sessions = HelpBotSession.objects.filter(
                user=user,
                cdtz__date__range=[start_date, end_date]
            )

            analytics = {
                'total_sessions': user_sessions.count(),
                'avg_session_length': user_sessions.annotate(
                    message_count=Count('messages')
                ).aggregate(
                    avg=Avg('message_count')
                )['avg'] or 0,
                'satisfaction_ratings': user_sessions.filter(
                    satisfaction_rating__isnull=False
                ).aggregate(
                    avg=Avg('satisfaction_rating'),
                    count=Count('satisfaction_rating')
                ),
                'most_used_session_types': user_sessions.values(
                    'session_type'
                ).annotate(
                    count=Count('session_id')
                ).order_by('-count')[:5],
                'feedback_given': HelpBotFeedback.objects.filter(
                    user=user,
                    cdtz__date__range=[start_date, end_date]
                ).values('feedback_type').annotate(
                    count=Count('feedback_id')
                ),
            }

            return analytics

        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {}

    def cleanup_old_analytics(self, days: int = 90) -> int:
        """Clean up old analytics records."""
        try:
            cutoff_date = timezone.now().date() - timedelta(days=days)

            deleted_count, _ = HelpBotAnalytics.objects.filter(
                date__lt=cutoff_date
            ).delete()

            logger.info(f"Cleaned up {deleted_count} old analytics records")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up analytics: {e}")
            return 0