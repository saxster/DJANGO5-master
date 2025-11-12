"""
Fraud Intelligence REST API Views.

Provides unified access to fraud detection scores and ML model performance
for real-time security intelligence dashboards.

Endpoints:
- GET /api/v2/noc/security/fraud-scores/live/ - High-risk persons (score >0.5)
- GET /api/v2/noc/security/fraud-scores/history/<person_id>/ - 30-day trend
- GET /api/v2/noc/security/fraud-scores/heatmap/ - Site-level aggregation
- GET /api/v2/noc/security/ml-models/performance/ - Current model metrics

Follows .claude/rules.md Rule #8: Methods < 50 lines.
"""

import logging
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max, Q
from django.db import models

from apps.peoples.models import People
from apps.client_onboarding.models import Bt
from apps.noc.security_intelligence.models import (
    FraudPredictionLog,
    FraudDetectionModel,
)
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS
from apps.core.decorators import require_capability

logger = logging.getLogger('noc.fraud_api')

# Cache TTL (5 minutes as specified)
FRAUD_CACHE_TTL = 300  # seconds


@require_http_methods(["GET"])
@login_required
@require_capability('security:fraud:view')
def fraud_scores_live_view(request):
    """
    Get high-risk persons with fraud score >0.5.

    Returns real-time fraud predictions for persons with elevated risk levels.
    Useful for security dashboard "watch list".

    Query parameters:
        - min_score (optional): Minimum fraud score (default 0.5)
        - site_id (optional): Filter by site
        - limit (optional): Max results (default 100)

    Returns:
        JsonResponse with high-risk predictions
    """
    try:
        # Parse query parameters
        min_score = float(request.GET.get('min_score', 0.5))
        site_id = request.GET.get('site_id')
        limit = int(request.GET.get('limit', 100))

        # Build cache key
        cache_key = f'fraud:live:{request.user.tenant.id}:{min_score}:{site_id}:{limit}'
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for live fraud scores")
            return JsonResponse({
                'status': 'success',
                'data': cached_data,
                'cached': True
            })

        # Query high-risk predictions (last 24 hours)
        cutoff_time = timezone.now() - timedelta(hours=24)
        query = FraudPredictionLog.objects.filter(
            tenant=request.user.tenant,
            predicted_at__gte=cutoff_time,
            fraud_probability__gte=min_score
        ).select_related('person', 'site').order_by('-fraud_probability')

        if site_id:
            query = query.filter(site_id=site_id)

        predictions = query[:limit]

        # Serialize predictions
        predictions_data = []
        for pred in predictions:
            predictions_data.append({
                'prediction_id': pred.id,
                'person_id': pred.person.id,
                'person_name': pred.person.peoplename,
                'site_id': pred.site.id if pred.site else None,
                'site_name': pred.site.name if pred.site else None,
                'fraud_probability': round(pred.fraud_probability, 4),
                'risk_level': pred.risk_level,
                'prediction_type': pred.prediction_type,
                'predicted_at': pred.predicted_at.isoformat(),
                'model_confidence': round(pred.model_confidence, 4),
                'baseline_deviation': round(pred.baseline_deviation, 4),
                'anomaly_indicators': pred.anomaly_indicators
            })

        response_data = {
            'total_count': len(predictions_data),
            'filters': {
                'min_score': min_score,
                'site_id': site_id,
                'limit': limit
            },
            'collected_at': timezone.now().isoformat(),
            'predictions': predictions_data
        }

        # Cache for 5 minutes
        cache.set(cache_key, response_data, FRAUD_CACHE_TTL)

        return JsonResponse({
            'status': 'success',
            'data': response_data,
            'cached': False
        })

    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid parameter: {e}'
        }, status=400)
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Error fetching live fraud scores: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)


@require_http_methods(["GET"])
@login_required
@require_capability('security:fraud:view')
def fraud_scores_history_view(request, person_id):
    """
    Get 30-day fraud score trend for a person.

    Returns daily aggregated fraud scores showing risk pattern over time.
    Enables trend analysis and behavioral change detection.

    Args:
        request: HTTP request
        person_id: Person ID

    Query parameters:
        - days (optional): Lookback period (default 30)

    Returns:
        JsonResponse with fraud score history
    """
    try:
        # Check cache first
        days = int(request.GET.get('days', 30))
        cache_key = f'fraud:history:{person_id}:{days}'
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for fraud history: {person_id}")
            return JsonResponse({
                'status': 'success',
                'data': cached_data,
                'cached': True
            })

        # Get person
        person = People.objects.select_related(
            'peopleorganizational'
        ).get(id=person_id, tenant=request.user.tenant)

        # Query predictions for last N days
        cutoff_time = timezone.now() - timedelta(days=days)
        predictions = FraudPredictionLog.objects.filter(
            tenant=request.user.tenant,
            person=person,
            predicted_at__gte=cutoff_time
        ).order_by('predicted_at')

        # Group by day and aggregate
        from django.db.models.functions import TruncDate
        daily_scores = predictions.annotate(
            date=TruncDate('predicted_at')
        ).values('date').annotate(
            avg_score=Avg('fraud_probability'),
            max_score=Max('fraud_probability'),
            prediction_count=Count('id'),
            high_risk_count=Count('id', filter=Q(risk_level__in=['HIGH', 'CRITICAL']))
        ).order_by('date')

        # Serialize history
        history_data = []
        for entry in daily_scores:
            history_data.append({
                'date': entry['date'].isoformat(),
                'avg_fraud_score': round(entry['avg_score'], 4),
                'max_fraud_score': round(entry['max_score'], 4),
                'prediction_count': entry['prediction_count'],
                'high_risk_count': entry['high_risk_count']
            })

        response_data = {
            'person_id': person_id,
            'person_name': person.peoplename,
            'days': days,
            'total_predictions': predictions.count(),
            'collected_at': timezone.now().isoformat(),
            'history': history_data
        }

        # Cache for 5 minutes
        cache.set(cache_key, response_data, FRAUD_CACHE_TTL)

        return JsonResponse({
            'status': 'success',
            'data': response_data,
            'cached': False
        })

    except People.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': f'Person {person_id} not found'
        }, status=404)
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Error fetching fraud history: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)


@require_http_methods(["GET"])
@login_required
@require_capability('security:fraud:view')
def fraud_scores_heatmap_view(request):
    """
    Get site-level fraud score aggregation (heatmap data).

    Returns aggregated fraud metrics per site for geographic visualization.
    Enables identification of high-risk locations.

    Query parameters:
        - hours (optional): Time window in hours (default 24)
        - min_predictions (optional): Min predictions per site to include (default 5)

    Returns:
        JsonResponse with site-level fraud aggregations
    """
    try:
        # Parse query parameters
        hours = int(request.GET.get('hours', 24))
        min_predictions = int(request.GET.get('min_predictions', 5))

        # Build cache key
        cache_key = f'fraud:heatmap:{request.user.tenant.id}:{hours}:{min_predictions}'
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for fraud heatmap")
            return JsonResponse({
                'status': 'success',
                'data': cached_data,
                'cached': True
            })

        # Query predictions
        cutoff_time = timezone.now() - timedelta(hours=hours)
        site_aggregates = FraudPredictionLog.objects.filter(
            tenant=request.user.tenant,
            predicted_at__gte=cutoff_time,
            site__isnull=False
        ).values('site_id', 'site__name').annotate(
            avg_fraud_score=Avg('fraud_probability'),
            max_fraud_score=Max('fraud_probability'),
            total_predictions=Count('id'),
            high_risk_count=Count('id', filter=Q(risk_level__in=['HIGH', 'CRITICAL'])),
            critical_risk_count=Count('id', filter=Q(risk_level='CRITICAL'))
        ).filter(
            total_predictions__gte=min_predictions
        ).order_by('-avg_fraud_score')

        # Serialize heatmap data
        heatmap_data = []
        for site_data in site_aggregates:
            heatmap_data.append({
                'site_id': site_data['site_id'],
                'site_name': site_data['site__name'],
                'avg_fraud_score': round(site_data['avg_fraud_score'], 4),
                'max_fraud_score': round(site_data['max_fraud_score'], 4),
                'total_predictions': site_data['total_predictions'],
                'high_risk_count': site_data['high_risk_count'],
                'critical_risk_count': site_data['critical_risk_count'],
                'risk_percentage': round(
                    (site_data['high_risk_count'] / site_data['total_predictions']) * 100, 2
                )
            })

        response_data = {
            'total_sites': len(heatmap_data),
            'filters': {
                'hours': hours,
                'min_predictions': min_predictions
            },
            'collected_at': timezone.now().isoformat(),
            'sites': heatmap_data
        }

        # Cache for 5 minutes
        cache.set(cache_key, response_data, FRAUD_CACHE_TTL)

        return JsonResponse({
            'status': 'success',
            'data': response_data,
            'cached': False
        })

    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid parameter: {e}'
        }, status=400)
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Error fetching fraud heatmap: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)


@require_http_methods(["GET"])
@login_required
@require_capability('security:fraud:view')
def ml_model_performance_view(request):
    """
    Get current ML model performance metrics.

    Returns active fraud detection model metrics including PR-AUC,
    precision/recall, training data stats, and feature importance.

    Returns:
        JsonResponse with model performance data
    """
    try:
        # Check cache first
        cache_key = f'fraud:model_perf:{request.user.tenant.id}'
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for model performance")
            return JsonResponse({
                'status': 'success',
                'data': cached_data,
                'cached': True
            })

        # Get active model
        active_model = FraudDetectionModel.get_active_model(request.user.tenant)

        if not active_model:
            return JsonResponse({
                'status': 'success',
                'data': {
                    'has_active_model': False,
                    'message': 'No active fraud detection model found for this tenant'
                }
            })

        # Get model performance summary
        performance_summary = active_model.get_performance_summary()

        # Get recent prediction accuracy stats (last 30 days)
        accuracy_stats = FraudPredictionLog.get_prediction_accuracy_stats(
            tenant=request.user.tenant,
            days=30
        )

        response_data = {
            'has_active_model': True,
            'model': performance_summary,
            'prediction_accuracy': accuracy_stats,
            'collected_at': timezone.now().isoformat()
        }

        # Cache for 5 minutes
        cache.set(cache_key, response_data, FRAUD_CACHE_TTL)

        return JsonResponse({
            'status': 'success',
            'data': response_data,
            'cached': False
        })

    except CACHE_EXCEPTIONS as e:
        logger.error(f"Error fetching model performance: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)
