"""
Funnel Analytics API Views

REST API endpoints for onboarding funnel analytics and optimization.

Following .claude/rules.md:
- Rule #8: View methods < 30 lines (delegate to services)
- Rule #11: Specific exception handling
- Rule #15: Logging data sanitization

Author: Claude Code
Date: 2025-10-01
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from django.utils import timezone
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from apps.onboarding_api.services.funnel_analytics import (
    get_funnel_analytics_service,
    get_funnel_optimization_engine,
    get_funnel_metrics_for_dashboard
)
from apps.onboarding_api.services.llm import LLMServiceException

logger = logging.getLogger(__name__)


class FunnelMetricsView(APIView):
    """
    GET /api/v1/onboarding/analytics/funnel/

    Complete funnel metrics with stage breakdown and conversion rates.

    Query Parameters:
        - start_date: ISO format datetime (default: 7 days ago)
        - end_date: ISO format datetime (default: now)
        - client_id: Optional client filter
        - user_segment: Optional segment filter

    Response:
        {
            "period": {"start": "...", "end": "..."},
            "total_sessions": 150,
            "overall_conversion_rate": 0.45,
            "avg_completion_time_minutes": 18.5,
            "stages": [...],
            "top_drop_off_points": [...],
            "cohort_analysis": {...},
            "recommendations": [...]
        }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Get comprehensive funnel metrics for specified period"""
        try:
            # Parse query parameters
            end_date = self._parse_date(
                request.query_params.get('end_date'),
                default=timezone.now()
            )
            start_date = self._parse_date(
                request.query_params.get('start_date'),
                default=end_date - timedelta(days=7)
            )
            client_id = request.query_params.get('client_id')
            user_segment = request.query_params.get('user_segment')

            # Validate date range
            if start_date >= end_date:
                return Response(
                    {'error': 'start_date must be before end_date'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate funnel metrics
            service = get_funnel_analytics_service()
            analytics = service.calculate_funnel_metrics(
                start_date=start_date,
                end_date=end_date,
                client_id=int(client_id) if client_id else None,
                user_segment=user_segment
            )

            # Format response
            return Response({
                'period': {
                    'start': analytics.period_start.isoformat(),
                    'end': analytics.period_end.isoformat()
                },
                'total_sessions': analytics.total_sessions,
                'overall_conversion_rate': round(analytics.overall_conversion_rate, 4),
                'avg_completion_time_minutes': round(analytics.avg_completion_time_minutes, 2),
                'stages': [
                    {
                        'name': stage.name,
                        'description': stage.description,
                        'count': stage.count,
                        'conversion_rate': round(stage.conversion_rate, 4),
                        'drop_off_rate': round(stage.drop_off_rate or 0, 4),
                        'avg_time_to_next_minutes': round(stage.avg_time_to_next or 0, 2)
                    }
                    for stage in analytics.stages
                ],
                'top_drop_off_points': analytics.top_drop_off_points,
                'cohort_analysis': analytics.cohort_analysis,
                'recommendations': analytics.recommendations
            })

        except (ValueError, ValidationError) as e:
            logger.warning(f"Invalid funnel metrics request: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid request parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in funnel metrics: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except (LLMServiceException, ConnectionError, TimeoutError) as e:
            logger.error(f"Service error in funnel metrics: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Service temporarily unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    def _parse_date(self, date_string: Optional[str], default: datetime) -> datetime:
        """Parse date string to datetime with validation"""
        if not date_string:
            return default

        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValidationError(f"Invalid date format: {date_string}")


class DropOffHeatmapView(APIView):
    """
    GET /api/v1/onboarding/analytics/drop-off-heatmap/

    Drop-off heatmap data for visualization.

    Query Parameters:
        - start_date: ISO format datetime (default: 7 days ago)
        - end_date: ISO format datetime (default: now)
        - client_id: Optional client filter

    Response:
        {
            "heatmap_data": [
                {
                    "from_stage": "started",
                    "to_stage": "engaged",
                    "drop_off_count": 45,
                    "drop_off_rate": 0.30,
                    "impact_severity": "high"
                },
                ...
            ],
            "total_incomplete": 150,
            "common_reasons": [...]
        }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Get drop-off heatmap data"""
        try:
            # Parse query parameters
            end_date = self._parse_date(
                request.query_params.get('end_date'),
                default=timezone.now()
            )
            start_date = self._parse_date(
                request.query_params.get('start_date'),
                default=end_date - timedelta(days=7)
            )
            client_id = request.query_params.get('client_id')

            # Get drop-off analysis
            service = get_funnel_analytics_service()
            drop_off_data = service.get_drop_off_analysis(
                start_date=start_date,
                end_date=end_date,
                client_id=int(client_id) if client_id else None
            )

            return Response({
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'total_incomplete': drop_off_data['total_incomplete'],
                'final_states': drop_off_data['final_states'],
                'error_patterns': drop_off_data['error_patterns'],
                'time_analysis': drop_off_data['time_analysis'],
                'common_reasons': drop_off_data['common_drop_off_reasons'],
                'recommendations': drop_off_data['recommendations']
            })

        except (ValueError, ValidationError) as e:
            logger.warning(f"Invalid drop-off heatmap request: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid request parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in drop-off heatmap: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _parse_date(self, date_string: Optional[str], default: datetime) -> datetime:
        """Parse date string to datetime with validation"""
        if not date_string:
            return default

        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValidationError(f"Invalid date format: {date_string}")


class CohortComparisonView(APIView):
    """
    GET /api/v1/onboarding/analytics/cohort-comparison/

    Compare conversion rates across user cohorts.

    Query Parameters:
        - start_date: ISO format datetime (default: 30 days ago)
        - end_date: ISO format datetime (default: now)
        - client_id: Optional client filter

    Response:
        {
            "segments": {
                "first_time_users": {...},
                "returning_users": {...},
                "admin_users": {...},
                "mobile_users": {...}
            },
            "segment_performance": {...},
            "insights": [...]
        }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Get cohort comparison analysis"""
        try:
            # Parse query parameters
            end_date = self._parse_date(
                request.query_params.get('end_date'),
                default=timezone.now()
            )
            start_date = self._parse_date(
                request.query_params.get('start_date'),
                default=end_date - timedelta(days=30)
            )
            client_id = request.query_params.get('client_id')

            # Get segment analysis
            service = get_funnel_analytics_service()
            segment_data = service.get_user_segment_analysis(
                start_date=start_date,
                end_date=end_date,
                client_id=int(client_id) if client_id else None
            )

            return Response({
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'segments': segment_data['segments'],
                'segment_performance': segment_data['segment_performance'],
                'insights': segment_data['insights']
            })

        except (ValueError, ValidationError) as e:
            logger.warning(f"Invalid cohort comparison request: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid request parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in cohort comparison: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _parse_date(self, date_string: Optional[str], default: datetime) -> datetime:
        """Parse date string to datetime with validation"""
        if not date_string:
            return default

        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValidationError(f"Invalid date format: {date_string}")


class OptimizationRecommendationsView(APIView):
    """
    GET /api/v1/onboarding/analytics/recommendations/

    AI-generated optimization recommendations based on funnel data.

    Query Parameters:
        - start_date: ISO format datetime (default: 7 days ago)
        - end_date: ISO format datetime (default: now)
        - client_id: Optional client filter
        - priority: Optional filter by priority (high, medium, low)

    Response:
        {
            "recommendations": [
                {
                    "type": "conversion_optimization",
                    "priority": "high",
                    "title": "Improve Overall Conversion Rate",
                    "description": "...",
                    "suggested_actions": [...],
                    "estimated_impact": "..."
                },
                ...
            ],
            "total_count": 8,
            "high_priority_count": 3
        }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Get optimization recommendations"""
        try:
            # Parse query parameters
            end_date = self._parse_date(
                request.query_params.get('end_date'),
                default=timezone.now()
            )
            start_date = self._parse_date(
                request.query_params.get('start_date'),
                default=end_date - timedelta(days=7)
            )
            client_id = request.query_params.get('client_id')
            priority_filter = request.query_params.get('priority')

            # Calculate funnel metrics
            service = get_funnel_analytics_service()
            analytics = service.calculate_funnel_metrics(
                start_date=start_date,
                end_date=end_date,
                client_id=int(client_id) if client_id else None
            )

            # Generate optimization recommendations
            engine = get_funnel_optimization_engine()
            recommendations = engine.generate_optimization_recommendations(analytics)

            # Filter by priority if specified
            if priority_filter:
                recommendations = [
                    rec for rec in recommendations
                    if rec['priority'] == priority_filter.lower()
                ]

            # Count by priority
            priority_counts = {
                'high': sum(1 for rec in recommendations if rec['priority'] == 'high'),
                'medium': sum(1 for rec in recommendations if rec['priority'] == 'medium'),
                'low': sum(1 for rec in recommendations if rec['priority'] == 'low')
            }

            return Response({
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'recommendations': recommendations,
                'total_count': len(recommendations),
                'priority_counts': priority_counts,
                'current_metrics': {
                    'total_sessions': analytics.total_sessions,
                    'conversion_rate': round(analytics.overall_conversion_rate, 4),
                    'avg_completion_time_minutes': round(analytics.avg_completion_time_minutes, 2)
                }
            })

        except (ValueError, ValidationError) as e:
            logger.warning(f"Invalid recommendations request: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid request parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in recommendations: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except (LLMServiceException, ConnectionError, TimeoutError) as e:
            logger.error(f"Service error in recommendations: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Service temporarily unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    def _parse_date(self, date_string: Optional[str], default: datetime) -> datetime:
        """Parse date string to datetime with validation"""
        if not date_string:
            return default

        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValidationError(f"Invalid date format: {date_string}")


class RealtimeFunnelDashboardView(APIView):
    """
    GET /api/v1/onboarding/analytics/realtime/

    Real-time funnel metrics for live dashboards (last 24 hours).

    Query Parameters:
        - client_id: Optional client filter

    Response:
        {
            "real_time": {
                "last_updated": "...",
                "period": "24 hours",
                "total_sessions": 85,
                "active_sessions": 12,
                "completion_rate": 0.42
            },
            "weekly_summary": {...},
            "stage_breakdown": [...],
            "recommendations": [...]
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get real-time dashboard metrics"""
        try:
            client_id = request.query_params.get('client_id')

            # Get dashboard metrics (cached for performance)
            dashboard_data = get_funnel_metrics_for_dashboard(
                client_id=int(client_id) if client_id else None
            )

            return Response(dashboard_data)

        except (ValueError, ValidationError) as e:
            logger.warning(f"Invalid realtime dashboard request: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid request parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in realtime dashboard: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FunnelComparisonView(APIView):
    """
    GET /api/v1/onboarding/analytics/comparison/

    Compare funnel performance between two time periods.

    Query Parameters:
        - period1_start, period1_end: First period dates
        - period2_start, period2_end: Second period dates
        - client_id: Optional client filter

    Response:
        {
            "period1": {...},
            "period2": {...},
            "changes": {
                "total_sessions_change": 25,
                "conversion_rate_change": 0.05,
                "trend": "improving"
            },
            "stage_comparisons": [...],
            "improvement_opportunities": [...]
        }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Get funnel comparison between two periods"""
        try:
            # Parse period 1
            period1_end = self._parse_date(
                request.query_params.get('period1_end'),
                default=timezone.now()
            )
            period1_start = self._parse_date(
                request.query_params.get('period1_start'),
                default=period1_end - timedelta(days=7)
            )

            # Parse period 2
            period2_end = self._parse_date(
                request.query_params.get('period2_end'),
                default=period1_start
            )
            period2_start = self._parse_date(
                request.query_params.get('period2_start'),
                default=period2_end - timedelta(days=7)
            )

            client_id = request.query_params.get('client_id')

            # Get comparison data
            service = get_funnel_analytics_service()
            comparison = service.get_funnel_comparison(
                period1_start=period1_start,
                period1_end=period1_end,
                period2_start=period2_start,
                period2_end=period2_end,
                client_id=int(client_id) if client_id else None
            )

            return Response(comparison)

        except (ValueError, ValidationError) as e:
            logger.warning(f"Invalid funnel comparison request: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid request parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in funnel comparison: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _parse_date(self, date_string: Optional[str], default: datetime) -> datetime:
        """Parse date string to datetime with validation"""
        if not date_string:
            return default

        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValidationError(f"Invalid date format: {date_string}")


__all__ = [
    'FunnelMetricsView',
    'DropOffHeatmapView',
    'CohortComparisonView',
    'OptimizationRecommendationsView',
    'RealtimeFunnelDashboardView',
    'FunnelComparisonView',
]
