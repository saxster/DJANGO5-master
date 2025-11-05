"""
AI Testing REST API Views
Comprehensive REST API for external tool integration
"""

import csv
import json
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

from apps.ai_testing.models.test_coverage_gaps import TestCoverageGap, TestCoveragePattern
from apps.ai_testing.models.adaptive_thresholds import AdaptiveThreshold
from apps.ai_testing.models.regression_predictions import RegressionPrediction
from apps.ai_testing.dashboard_integration import get_ai_insights_summary
from .serializers import (
    TestCoverageGapSummarySerializer,
    TestCoverageGapSerializer,
    TestCoveragePatternSerializer,
    AdaptiveThresholdSerializer,
    RegressionPredictionSerializer,
    AIInsightsSummarySerializer,
    CoverageGapStatsSerializer,
    TestGenerationRequestSerializer,
    TestGenerationResponseSerializer,
    AnalysisRequestSerializer,
    ExportRequestSerializer,
    APIErrorSerializer
)
from django.http import HttpResponse, JsonResponse
from django.db import models, DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from io import StringIO

logger = logging.getLogger(__name__)


def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_staff or user.is_superuser


# Core API Endpoints

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_insights_api(request):
    """
    GET /api/ai-testing/insights/
    Get comprehensive AI insights summary
    """
    try:
        insights = get_ai_insights_summary()
        serializer = AIInsightsSummarySerializer(insights)

        return Response({
            'success': True,
            'data': serializer.data,
            'timestamp': timezone.now()
        })

    except (ValueError, TypeError) as e:
        logger.error(f"AI insights API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def coverage_gaps_api(request):
    """
    GET /api/ai-testing/coverage-gaps/
    List coverage gaps with filtering and pagination
    """
    try:
        # Query parameters
        page_size = min(int(request.GET.get('page_size', 20)), 100)
        page = int(request.GET.get('page', 1))
        priority_filter = request.GET.get('priority')
        status_filter = request.GET.get('status')
        coverage_type_filter = request.GET.get('coverage_type')
        summary_only = request.GET.get('summary') == 'true'

        # Build queryset with comprehensive optimization
        gaps = TestCoverageGap.objects.select_related(
            'anomaly_signature',
            'assigned_to',
            'assigned_to__profile'
        ).prefetch_related(
            'related_gaps',
            'test_file_references'
        )

        if priority_filter:
            gaps = gaps.filter(priority=priority_filter)

        if status_filter:
            gaps = gaps.filter(status=status_filter)

        if coverage_type_filter:
            gaps = gaps.filter(coverage_type=coverage_type_filter)

        # Order by priority and confidence
        gaps = gaps.order_by('-confidence_score', '-impact_score')

        # Pagination
        paginator = Paginator(gaps, page_size)
        page_obj = paginator.get_page(page)

        # Serialize data
        serializer_class = TestCoverageGapSummarySerializer if summary_only else TestCoverageGapSerializer
        serializer = serializer_class(page_obj, many=True)

        return Response({
            'success': True,
            'data': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            },
            'filters': {
                'priority': priority_filter,
                'status': status_filter,
                'coverage_type': coverage_type_filter
            },
            'timestamp': timezone.now()
        })

    except (ValueError, TypeError) as e:
        logger.error(f"Coverage gaps API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def coverage_gap_detail_api(request, gap_id):
    """
    GET /api/ai-testing/coverage-gaps/{gap_id}/
    Get detailed information about a specific coverage gap
    """
    try:
        gap = TestCoverageGap.objects.select_related(
            'anomaly_signature', 'assigned_to'
        ).get(id=gap_id)

        serializer = TestCoverageGapSerializer(gap)

        # Add similar gaps
        similar_gaps = TestCoverageGap.find_similar_gaps(gap, threshold=0.6)[:3]
        similar_serializer = TestCoverageGapSummarySerializer(
            [item['gap'] for item in similar_gaps],
            many=True
        )

        return Response({
            'success': True,
            'data': serializer.data,
            'similar_gaps': similar_serializer.data,
            'timestamp': timezone.now()
        })

    except TestCoverageGap.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Coverage gap not found',
            'timestamp': timezone.now()
        }, status=status.HTTP_404_NOT_FOUND)

    except (ValueError, TypeError) as e:
        logger.error(f"Coverage gap detail API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def regression_risk_api(request, version=None):
    """
    GET /api/ai-testing/regression-risk/{version}/
    Get regression risk score for a specific version
    """
    try:
        queryset = RegressionPrediction.objects.select_related(
            'created_by'
        ).prefetch_related(
            'affected_tests'
        ).order_by('-created_at')

        if version:
            prediction = queryset.filter(
                version_identifier=version
            ).first()
        else:
            prediction = queryset.first()

        if not prediction:
            return Response({
                'success': True,
                'data': {
                    'risk_score': 0.0,
                    'confidence': 0.0,
                    'version': version,
                    'message': 'No regression prediction available'
                },
                'timestamp': timezone.now()
            })

        serializer = RegressionPredictionSerializer(prediction)

        return Response({
            'success': True,
            'data': serializer.data,
            'timestamp': timezone.now()
        })

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Regression risk API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def adaptive_thresholds_api(request):
    """
    GET /api/ai-testing/thresholds/
    Get current adaptive thresholds
    """
    try:
        thresholds = AdaptiveThreshold.objects.select_related(
            'created_by'
        ).order_by('metric_name')
        serializer = AdaptiveThresholdSerializer(thresholds, many=True)

        return Response({
            'success': True,
            'data': serializer.data,
            'count': thresholds.count(),
            'timestamp': timezone.now()
        })

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Adaptive thresholds API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patterns_api(request):
    """
    GET /api/ai-testing/patterns/
    Get detected coverage patterns
    """
    try:
        patterns = TestCoveragePattern.objects.select_related(
            'created_by'
        ).filter(
            is_active=True
        ).order_by('-occurrence_count', '-confidence_score')

        limit = min(int(request.GET.get('limit', 50)), 100)
        patterns = patterns[:limit]

        serializer = TestCoveragePatternSerializer(patterns, many=True)

        return Response({
            'success': True,
            'data': serializer.data,
            'count': len(serializer.data),
            'timestamp': timezone.now()
        })

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Patterns API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def coverage_gaps_stats_api(request):
    """
    GET /api/ai-testing/coverage-gaps/stats/
    Get coverage gaps statistics
    """
    try:
        # Calculate statistics
        total_gaps = TestCoverageGap.objects.count()

        # Priority breakdown
        by_priority = dict(
            TestCoverageGap.objects.values('priority').annotate(
                count=models.Count('id')
            ).values_list('priority', 'count')
        )

        # Type breakdown
        by_type = dict(
            TestCoverageGap.objects.values('coverage_type').annotate(
                count=models.Count('id')
            ).values_list('coverage_type', 'count')
        )

        # Status breakdown
        by_status = dict(
            TestCoverageGap.objects.values('status').annotate(
                count=models.Count('id')
            ).values_list('status', 'count')
        )

        # Recent gaps (last 7 days)
        recent_7d = TestCoverageGap.objects.filter(
            identified_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()

        # Implementation rate
        implemented_count = TestCoverageGap.objects.filter(
            status__in=['test_implemented', 'test_verified']
        ).count()
        implementation_rate = (implemented_count / total_gaps * 100) if total_gaps > 0 else 0

        stats_data = {
            'total': total_gaps,
            'by_priority': by_priority,
            'by_type': by_type,
            'by_status': by_status,
            'recent_7d': recent_7d,
            'implementation_rate': round(implementation_rate, 1)
        }

        serializer = CoverageGapStatsSerializer(stats_data)

        return Response({
            'success': True,
            'data': serializer.data,
            'timestamp': timezone.now()
        })

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Coverage gaps stats API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Test Generation API

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_test_api(request):
    """
    POST /api/ai-testing/generate-test/
    Generate test code for a coverage gap
    """
    try:
        serializer = TestGenerationRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'timestamp': timezone.now()
            }, status=status.HTTP_400_BAD_REQUEST)

        gap_id = serializer.validated_data['gap_id']
        framework = serializer.validated_data['framework']

        # Get coverage gap
        gap = TestCoverageGap.objects.get(id=gap_id)

        # Generate test code
        test_code = gap.generate_test_code(framework)

        if test_code:
            # Prepare response data
            file_extension = '.kt' if framework in ['espresso', 'junit', 'robolectric'] else '.swift'
            file_name = f"test_{gap.coverage_type}_{gap.title.replace(' ', '_').lower()}{file_extension}"

            response_data = {
                'success': True,
                'test_code': test_code,
                'file_name': file_name,
                'framework': framework,
                'file_size': len(test_code.encode('utf-8')),
                'line_count': len(test_code.split('\n')),
                'generated_at': timezone.now()
            }

            response_serializer = TestGenerationResponseSerializer(response_data)

            return Response({
                'success': True,
                'data': response_serializer.data,
                'timestamp': timezone.now()
            })

        else:
            return Response({
                'success': False,
                'error': 'Failed to generate test code',
                'timestamp': timezone.now()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except TestCoverageGap.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Coverage gap not found',
            'timestamp': timezone.now()
        }, status=status.HTTP_404_NOT_FOUND)

    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Generate test API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Analysis API

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_analysis_api(request):
    """
    POST /api/ai-testing/trigger-analysis/
    Trigger pattern analysis via API
    """
    try:
        serializer = AnalysisRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'timestamp': timezone.now()
            }, status=status.HTTP_400_BAD_REQUEST)

        # Trigger background analysis task
        from apps.ai_testing.tasks import ai_daily_pattern_analysis

        task_result = ai_daily_pattern_analysis.apply_async()

        return Response({
            'success': True,
            'data': {
                'analysis_id': task_result.id,
                'status': 'initiated',
                'message': 'Pattern analysis started in background',
                'parameters': serializer.validated_data
            },
            'timestamp': timezone.now()
        })

    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Trigger analysis API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Export API

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_coverage_gaps_csv(request):
    """
    GET /api/ai-testing/export/coverage-gaps.csv
    Export coverage gaps as CSV
    """
    try:
        # Query parameters
        priority_filter = request.GET.get('priority')
        status_filter = request.GET.get('status')
        days = int(request.GET.get('days', 30))

        # Build queryset
        gaps = TestCoverageGap.objects.select_related('anomaly_signature')

        if priority_filter:
            gaps = gaps.filter(priority=priority_filter)

        if status_filter:
            gaps = gaps.filter(status=status_filter)

        # Date filter
        since_date = timezone.now() - timezone.timedelta(days=days)
        gaps = gaps.filter(identified_at__gte=since_date)

        gaps = gaps.order_by('-confidence_score', '-impact_score')

        # Generate CSV
        output = StringIO()
        writer = csv.writer(output)

        # Headers
        writer.writerow([
            'ID', 'Title', 'Coverage Type', 'Priority', 'Status',
            'Confidence Score', 'Impact Score', 'Affected Platforms',
            'Affected Endpoints', 'Recommended Framework',
            'Estimated Time (hours)', 'Identified At', 'Updated At'
        ])

        # Data rows
        for gap in gaps:
            writer.writerow([
                str(gap.id),
                gap.title,
                gap.get_coverage_type_display(),
                gap.get_priority_display(),
                gap.get_status_display(),
                f"{gap.confidence_score:.3f}",
                f"{gap.impact_score:.1f}",
                ', '.join(gap.affected_platforms) if gap.affected_platforms else '',
                ', '.join(gap.affected_endpoints) if gap.affected_endpoints else '',
                gap.get_recommended_framework_display() if gap.recommended_framework else '',
                gap.estimated_implementation_time,
                gap.identified_at.isoformat(),
                gap.updated_at.isoformat()
            ])

        # Create response
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="coverage_gaps_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        return response

    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Export CSV API error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_coverage_gaps_json(request):
    """
    GET /api/ai-testing/export/coverage-gaps.json
    Export coverage gaps as JSON
    """
    try:
        # Query parameters
        priority_filter = request.GET.get('priority')
        status_filter = request.GET.get('status')
        days = int(request.GET.get('days', 30))
        include_details = request.GET.get('details') == 'true'

        # Build queryset
        gaps = TestCoverageGap.objects.select_related('anomaly_signature')

        if priority_filter:
            gaps = gaps.filter(priority=priority_filter)

        if status_filter:
            gaps = gaps.filter(status=status_filter)

        # Date filter
        since_date = timezone.now() - timezone.timedelta(days=days)
        gaps = gaps.filter(identified_at__gte=since_date)

        gaps = gaps.order_by('-confidence_score', '-impact_score')

        # Serialize data
        serializer_class = TestCoverageGapSerializer if include_details else TestCoverageGapSummarySerializer
        serializer = serializer_class(gaps, many=True)

        export_data = {
            'export_info': {
                'generated_at': timezone.now().isoformat(),
                'total_count': gaps.count(),
                'filters_applied': {
                    'priority': priority_filter,
                    'status': status_filter,
                    'days': days
                },
                'include_details': include_details
            },
            'coverage_gaps': serializer.data
        }

        # Create response
        response = HttpResponse(
            json.dumps(export_data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="coverage_gaps_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'

        return response

    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Export JSON API error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_ai_insights_json(request):
    """
    GET /api/ai-testing/export/insights.json
    Export comprehensive AI insights as JSON
    """
    try:
        insights = get_ai_insights_summary()

        # Add additional export metadata
        export_data = {
            'export_info': {
                'generated_at': timezone.now().isoformat(),
                'export_type': 'ai_insights_summary',
                'version': '1.0'
            },
            'ai_insights': insights
        }

        # Create response
        response = HttpResponse(
            json.dumps(export_data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="ai_insights_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'

        return response

    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Export AI insights JSON error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


# Health and Status API

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_api(request):
    """
    GET /api/ai-testing/health/
    Get AI system health status
    """
    try:
        insights = get_ai_insights_summary()
        health_score = insights['health_score']

        # Determine health status
        if health_score >= 80:
            health_status = 'healthy'
        elif health_score >= 60:
            health_status = 'warning'
        else:
            health_status = 'critical'

        return Response({
            'success': True,
            'data': {
                'health_score': health_score,
                'health_status': health_status,
                'critical_gaps': insights['coverage_gaps']['critical_count'],
                'regression_risk': insights['regression_risk']['risk_score'],
                'last_updated': insights['last_updated']
            },
            'timestamp': timezone.now()
        })

    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Health API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)