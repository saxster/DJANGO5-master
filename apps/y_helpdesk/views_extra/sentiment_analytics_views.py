"""
Sentiment Analytics Views

Feature 2: NL/AI Platform Quick Win - Dashboard and Analytics

Provides API endpoints for:
- Sentiment distribution heatmaps
- Negative ticket alerts
- Sentiment trends over time
- Emotion analysis aggregations

Following CLAUDE.md:
- Rule #11: Specific exception handling
- Rule #13: Type hints
- Rule #14: Comprehensive logging
"""

from typing import Dict, List, Optional
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from apps.y_helpdesk.models import Ticket
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS
import logging

logger = logging.getLogger('y_helpdesk.sentiment_analytics')


class SentimentAnalyticsView(LoginRequiredMixin, View):
    """
    API endpoint for sentiment analytics and dashboard data.

    Query Parameters:
    - action: Type of analytics (distribution, trends, alerts, emotions)
    - from: Start date for date range
    - to: End date for date range
    - bu_id: Filter by business unit
    """

    def get(self, request, *args, **kwargs):
        """Handle GET requests for sentiment analytics."""
        action = request.GET.get('action')

        try:
            if action == 'distribution':
                return self._get_sentiment_distribution(request)
            elif action == 'trends':
                return self._get_sentiment_trends(request)
            elif action == 'alerts':
                return self._get_negative_alerts(request)
            elif action == 'emotions':
                return self._get_emotion_analysis(request)
            elif action == 'statistics':
                return self._get_sentiment_statistics(request)
            else:
                return JsonResponse(
                    {'error': 'Invalid action parameter'},
                    status=400
                )

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error in sentiment analytics: {e}",
                extra={
                    'action': action,
                    'user': request.user.id
                },
                exc_info=True
            )
            return JsonResponse(
                {'error': 'Database error occurred'},
                status=500
            )
        except (AttributeError, TypeError, ValueError, KeyError) as e:
            logger.error(
                f"Data validation error in sentiment analytics: {e}",
                extra={
                    'action': action,
                    'user': request.user.id
                },
                exc_info=True
            )
            return JsonResponse(
                {'error': 'Invalid request data'},
                status=400
            )

    def _get_sentiment_distribution(self, request) -> JsonResponse:
        """
        Get sentiment label distribution.

        Returns count and percentage for each sentiment label.
        """
        # Base queryset with tenant/site filtering
        tickets = self._get_filtered_queryset(request)

        # Group by sentiment label
        distribution = tickets.values('sentiment_label').annotate(
            count=Count('id')
        ).order_by('sentiment_label')

        total = tickets.count()

        # Calculate percentages
        result = []
        for item in distribution:
            label = item['sentiment_label'] or 'not_analyzed'
            count = item['count']
            percentage = (count / total * 100) if total > 0 else 0

            result.append({
                'label': label,
                'count': count,
                'percentage': round(percentage, 2)
            })

        logger.info(
            f"Sentiment distribution calculated: {len(result)} labels, {total} total tickets",
            extra={
                'user': request.user.id,
                'total_tickets': total
            }
        )

        return JsonResponse({
            'distribution': result,
            'total_tickets': total
        })

    def _get_sentiment_trends(self, request) -> JsonResponse:
        """
        Get sentiment trends over time.

        Returns average sentiment score per day for the date range.
        """
        tickets = self._get_filtered_queryset(request)

        # Group by date and calculate average sentiment
        from django.db.models.functions import TruncDate

        trends = tickets.annotate(
            date=TruncDate('cdtz')
        ).values('date').annotate(
            avg_sentiment=Avg('sentiment_score'),
            ticket_count=Count('id')
        ).order_by('date')

        result = [
            {
                'date': item['date'].isoformat(),
                'avg_sentiment': round(item['avg_sentiment'], 2) if item['avg_sentiment'] else None,
                'ticket_count': item['ticket_count']
            }
            for item in trends
        ]

        logger.info(
            f"Sentiment trends calculated: {len(result)} data points",
            extra={'user': request.user.id}
        )

        return JsonResponse({'trends': result})

    def _get_negative_alerts(self, request) -> JsonResponse:
        """
        Get alerts for very negative tickets.

        Returns tickets with very_negative sentiment that need attention.
        """
        tickets = self._get_filtered_queryset(request)

        # Filter for very negative tickets that are still open
        negative_tickets = tickets.filter(
            sentiment_label='very_negative',
            status__in=['NEW', 'OPEN']
        ).select_related(
            'bu', 'assignedtopeople', 'ticketcategory'
        ).order_by('sentiment_score', 'cdtz')[:20]  # Top 20 most negative

        result = []
        for ticket in negative_tickets:
            result.append({
                'id': ticket.id,
                'ticketno': ticket.ticketno,
                'ticketdesc': ticket.ticketdesc[:100],  # First 100 chars
                'sentiment_score': ticket.sentiment_score,
                'sentiment_label': ticket.sentiment_label,
                'emotions': ticket.emotion_detected,
                'status': ticket.status,
                'priority': ticket.priority,
                'bu': ticket.bu.buname if ticket.bu else None,
                'assigned_to': ticket.assignedtopeople.peoplename if ticket.assignedtopeople else None,
                'created_at': ticket.cdtz.isoformat(),
                'is_escalated': ticket.isescalated
            })

        logger.warning(
            f"Found {len(result)} negative tickets requiring attention",
            extra={
                'user': request.user.id,
                'count': len(result)
            }
        )

        return JsonResponse({
            'alerts': result,
            'count': len(result)
        })

    def _get_emotion_analysis(self, request) -> JsonResponse:
        """
        Get emotion analysis aggregation.

        Returns counts and trends for detected emotions.
        """
        tickets = self._get_filtered_queryset(request)

        # Analyze emotion frequencies
        emotion_counts = {}
        total_analyzed = 0

        for ticket in tickets:
            if ticket.emotion_detected:
                total_analyzed += 1
                for emotion, score in ticket.emotion_detected.items():
                    if emotion not in emotion_counts:
                        emotion_counts[emotion] = {
                            'count': 0,
                            'total_score': 0.0,
                            'max_score': 0.0
                        }
                    emotion_counts[emotion]['count'] += 1
                    emotion_counts[emotion]['total_score'] += score
                    emotion_counts[emotion]['max_score'] = max(
                        emotion_counts[emotion]['max_score'],
                        score
                    )

        # Calculate averages
        result = []
        for emotion, data in emotion_counts.items():
            result.append({
                'emotion': emotion,
                'count': data['count'],
                'avg_score': round(data['total_score'] / data['count'], 3),
                'max_score': round(data['max_score'], 3),
                'percentage': round(data['count'] / total_analyzed * 100, 2) if total_analyzed > 0 else 0
            })

        # Sort by count descending
        result.sort(key=lambda x: x['count'], reverse=True)

        logger.info(
            f"Emotion analysis completed: {len(result)} emotions detected",
            extra={
                'user': request.user.id,
                'total_analyzed': total_analyzed
            }
        )

        return JsonResponse({
            'emotions': result,
            'total_analyzed': total_analyzed
        })

    def _get_sentiment_statistics(self, request) -> JsonResponse:
        """
        Get overall sentiment statistics.

        Returns:
        - Average sentiment score
        - Total tickets analyzed
        - Escalation rate
        - Distribution by priority
        """
        tickets = self._get_filtered_queryset(request)

        # Overall statistics
        total_count = tickets.count()
        analyzed_count = tickets.filter(sentiment_score__isnull=False).count()

        stats = tickets.aggregate(
            avg_sentiment=Avg('sentiment_score')
        )

        # Escalation rate for negative tickets
        negative_tickets = tickets.filter(sentiment_label__in=['very_negative', 'negative'])
        negative_count = negative_tickets.count()
        escalated_count = negative_tickets.filter(isescalated=True).count()
        escalation_rate = (escalated_count / negative_count * 100) if negative_count > 0 else 0

        # Priority distribution for negative tickets
        priority_dist = negative_tickets.values('priority').annotate(
            count=Count('id')
        )

        result = {
            'total_tickets': total_count,
            'analyzed_tickets': analyzed_count,
            'analysis_rate': round(analyzed_count / total_count * 100, 2) if total_count > 0 else 0,
            'avg_sentiment': round(stats['avg_sentiment'], 2) if stats['avg_sentiment'] else None,
            'negative_tickets': negative_count,
            'escalated_tickets': escalated_count,
            'escalation_rate': round(escalation_rate, 2),
            'priority_distribution': list(priority_dist)
        }

        logger.info(
            f"Sentiment statistics calculated: {total_count} tickets, {analyzed_count} analyzed",
            extra={'user': request.user.id}
        )

        return JsonResponse(result)

    def _get_filtered_queryset(self, request):
        """
        Get base queryset with standard filtering.

        Applies:
        - Tenant/client filtering
        - Site filtering
        - Date range filtering
        - Business unit filtering
        """
        from_date = request.GET.get('from')
        to_date = request.GET.get('to')
        bu_id = request.GET.get('bu_id')

        # Base queryset with tenant/site filtering
        queryset = Ticket.objects.filter(
            client_id=request.session.get('client_id'),
            bu_id__in=request.session.get('assignedsites', [])
        )

        # Date range filtering
        if from_date:
            queryset = queryset.filter(cdtz__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(cdtz__date__lte=to_date)

        # Business unit filtering
        if bu_id:
            queryset = queryset.filter(bu_id=bu_id)

        return queryset


class SentimentReanalysisView(LoginRequiredMixin, View):
    """
    API endpoint to trigger sentiment reanalysis.

    Allows administrators to:
    - Reanalyze specific tickets
    - Bulk reanalyze date ranges
    - Analyze unanalyzed tickets
    """

    def post(self, request, *args, **kwargs):
        """Trigger sentiment reanalysis."""
        from apps.y_helpdesk.tasks.sentiment_analysis_tasks import (
            AnalyzeTicketSentimentTask,
            BulkAnalyzeTicketSentimentTask
        )

        action = request.POST.get('action')

        try:
            if action == 'single':
                # Reanalyze single ticket
                ticket_id = request.POST.get('ticket_id')
                if not ticket_id:
                    return JsonResponse({'error': 'ticket_id required'}, status=400)

                # Queue task
                AnalyzeTicketSentimentTask.delay(int(ticket_id))

                return JsonResponse({
                    'success': True,
                    'message': f'Sentiment analysis queued for ticket {ticket_id}'
                })

            elif action == 'bulk':
                # Bulk reanalysis
                status_filter = request.POST.get('status')
                limit = int(request.POST.get('limit', 100))

                # Queue bulk task
                BulkAnalyzeTicketSentimentTask.delay(
                    status_filter=status_filter,
                    limit=limit
                )

                return JsonResponse({
                    'success': True,
                    'message': f'Bulk sentiment analysis queued for up to {limit} tickets'
                })

            else:
                return JsonResponse({'error': 'Invalid action'}, status=400)

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error queueing sentiment analysis: {e}",
                extra={'action': action, 'user': request.user.id},
                exc_info=True
            )
            return JsonResponse(
                {'error': 'Database error occurred'},
                status=500
            )
        except (AttributeError, TypeError, ValueError, KeyError) as e:
            logger.error(
                f"Validation error queueing sentiment analysis: {e}",
                extra={'action': action, 'user': request.user.id},
                exc_info=True
            )
            return JsonResponse({'error': str(e)}, status=500)
