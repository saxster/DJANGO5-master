"""
Ontology Dashboard Views

Django views for serving the coverage metrics dashboard.
"""
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from .metrics_generator import CoverageMetricsGenerator


@staff_member_required
@require_GET
@cache_page(60 * 5)  # Cache for 5 minutes
def dashboard_view(request):
    """
    Render the ontology coverage dashboard.

    Requires staff permissions to access.
    """
    generator = CoverageMetricsGenerator()
    metrics = generator.generate_full_metrics()

    # Convert lists to JSON for template rendering
    context = {
        'metrics': metrics,
    }

    # Serialize lists for JavaScript
    context['metrics']['by_domain'] = json.dumps(metrics['by_domain'])
    context['metrics']['by_criticality'] = json.dumps(metrics['by_criticality'])
    context['metrics']['trend'] = json.dumps(metrics.get('trend', []))

    return render(request, 'ontology/dashboard.html', context)


@staff_member_required
@require_GET
def metrics_api_view(request):
    """
    API endpoint to fetch raw metrics data as JSON.

    Useful for programmatic access or external monitoring.
    """
    generator = CoverageMetricsGenerator()
    metrics = generator.generate_full_metrics()

    return JsonResponse(metrics, safe=False)


@staff_member_required
@require_GET
def coverage_summary_api_view(request):
    """
    API endpoint for quick coverage summary.

    Returns only high-level metrics for status checks.
    """
    generator = CoverageMetricsGenerator()
    summary = generator.get_summary_metrics()

    return JsonResponse(summary)
