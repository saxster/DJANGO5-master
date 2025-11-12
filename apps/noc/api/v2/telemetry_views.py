"""
Telemetry REST API Views.

Provides unified access to activity signals for real-time operational intelligence.

Endpoints:
- GET /api/v2/telemetry/signals/<person_id>/ - Real-time signals for person
- GET /api/v2/telemetry/signals/site/<site_id>/ - Aggregated site signals
- GET /api/v2/telemetry/correlations/ - Recent correlated incidents

Follows .claude/rules.md Rule #8: Methods < 50 lines.
"""

import logging
from typing import Dict, Any
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

from apps.peoples.models import People
from apps.client_onboarding.models import Bt
from apps.noc.models import CorrelatedIncident
from apps.noc.security_intelligence.services.activity_signal_collector import ActivitySignalCollector
from apps.core.decorators import require_capability

logger = logging.getLogger('noc.telemetry_api')

# Cache TTL
TELEMETRY_CACHE_TTL = 60  # seconds


@require_http_methods(["GET"])
@login_required
@require_capability('noc:view')
def person_signals_view(request, person_id):
    """
    Get real-time activity signals for a person.

    Returns telemetry data including phone events, location updates,
    movement distance, tasks completed, and tour checkpoints scanned.

    Args:
        request: HTTP request
        person_id: Person ID

    Returns:
        JsonResponse with signal data
    """
    try:
        # Check cache first
        cache_key = f'telemetry:person:{person_id}'
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for person signals: {person_id}")
            return JsonResponse({
                'status': 'success',
                'data': cached_data,
                'cached': True
            })

        # Get person
        person = People.objects.select_related(
            'peopleorganizational'
        ).get(id=person_id, tenant=request.user.tenant)

        # Get site from organizational data
        if not hasattr(person, 'peopleorganizational') or not person.peopleorganizational.bu:
            return JsonResponse({
                'status': 'error',
                'message': 'Person has no assigned site'
            }, status=400)

        site = person.peopleorganizational.bu

        # Collect signals (default 120min window)
        window_minutes = int(request.GET.get('window_minutes', 120))
        signals = ActivitySignalCollector.collect_all_signals(
            person=person,
            site=site,
            window_minutes=window_minutes
        )

        # Add metadata
        response_data = {
            'person_id': person_id,
            'person_name': person.peoplename,
            'site_id': site.id,
            'site_name': site.name,
            'window_minutes': window_minutes,
            'collected_at': timezone.now().isoformat(),
            'signals': signals
        }

        # Cache for 60 seconds
        cache.set(cache_key, response_data, TELEMETRY_CACHE_TTL)

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
    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error fetching person signals: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)


@require_http_methods(["GET"])
@login_required
@require_capability('noc:view')
def site_signals_view(request, site_id):
    """
    Get aggregated activity signals for a site.

    Aggregates signals from all active people at the site.

    Args:
        request: HTTP request
        site_id: Site (Bt) ID

    Returns:
        JsonResponse with aggregated signal data
    """
    try:
        # Check cache first
        cache_key = f'telemetry:site:{site_id}'
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for site signals: {site_id}")
            return JsonResponse({
                'status': 'success',
                'data': cached_data,
                'cached': True
            })

        # Get site
        site = Bt.objects.get(id=site_id, tenant=request.user.tenant)

        # Get all active people at site
        active_people = People.objects.filter(
            peopleorganizational__bu=site,
            isactive=True,
            tenant=request.user.tenant
        ).select_related('peopleorganizational')

        if not active_people.exists():
            return JsonResponse({
                'status': 'success',
                'data': {
                    'site_id': site_id,
                    'site_name': site.name,
                    'active_people_count': 0,
                    'aggregated_signals': {}
                }
            })

        # Aggregate signals
        window_minutes = int(request.GET.get('window_minutes', 120))
        aggregated_signals = {
            'phone_events_count': 0,
            'location_updates_count': 0,
            'movement_distance_meters': 0,
            'tasks_completed_count': 0,
            'tour_checkpoints_scanned': 0
        }

        for person in active_people:
            signals = ActivitySignalCollector.collect_all_signals(
                person=person,
                site=site,
                window_minutes=window_minutes
            )
            for key in aggregated_signals.keys():
                aggregated_signals[key] += signals.get(key, 0)

        response_data = {
            'site_id': site_id,
            'site_name': site.name,
            'active_people_count': active_people.count(),
            'window_minutes': window_minutes,
            'collected_at': timezone.now().isoformat(),
            'aggregated_signals': aggregated_signals
        }

        # Cache for 60 seconds
        cache.set(cache_key, response_data, TELEMETRY_CACHE_TTL)

        return JsonResponse({
            'status': 'success',
            'data': response_data,
            'cached': False
        })

    except Bt.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': f'Site {site_id} not found'
        }, status=404)
    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error fetching site signals: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)


@require_http_methods(["GET"])
@login_required
@require_capability('noc:view')
def correlations_view(request):
    """
    Get recent correlated incidents.

    Returns incidents where signals have been correlated with alerts.

    Query parameters:
        - site_id (optional): Filter by site
        - min_severity (optional): Minimum severity (MEDIUM, HIGH, CRITICAL)
        - hours (optional): Time window in hours (default 24)

    Returns:
        JsonResponse with correlated incidents
    """
    try:
        # Parse query parameters
        site_id = request.GET.get('site_id')
        min_severity = request.GET.get('min_severity', 'MEDIUM')
        hours = int(request.GET.get('hours', 24))

        # Build cache key
        cache_key = f'telemetry:correlations:{site_id}:{min_severity}:{hours}'
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for correlations")
            return JsonResponse({
                'status': 'success',
                'data': cached_data,
                'cached': True
            })

        # Query incidents
        cutoff_time = timezone.now() - timedelta(hours=hours)
        severity_order = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        min_severity_index = severity_order.index(min_severity)
        qualifying_severities = severity_order[min_severity_index:]

        query = CorrelatedIncident.objects.filter(
            tenant=request.user.tenant,
            detected_at__gte=cutoff_time,
            combined_severity__in=qualifying_severities
        ).select_related('person', 'site')

        if site_id:
            query = query.filter(site_id=site_id)

        incidents = query.order_by('-combined_severity', '-detected_at')[:100]

        # Serialize incidents
        incidents_data = []
        for incident in incidents:
            incidents_data.append({
                'incident_id': str(incident.incident_id),
                'person_id': incident.person.id,
                'person_name': incident.person.peoplename,
                'site_id': incident.site.id,
                'site_name': incident.site.name,
                'combined_severity': incident.combined_severity,
                'correlation_score': incident.correlation_score,
                'signals': incident.signals,
                'related_alerts_count': incident.related_alerts.count(),
                'detected_at': incident.detected_at.isoformat(),
                'investigated': incident.investigated
            })

        response_data = {
            'total_count': len(incidents_data),
            'filters': {
                'site_id': site_id,
                'min_severity': min_severity,
                'hours': hours
            },
            'incidents': incidents_data
        }

        # Cache for 60 seconds
        cache.set(cache_key, response_data, TELEMETRY_CACHE_TTL)

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
    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error fetching correlations: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)
