"""
AI Testing Views
Coverage Gap Management, Test Generation, and AI Insights
"""

import unicodedata
import re

from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from apps.core.decorators import csrf_protect_htmx, rate_limit

from apps.ai_testing.dashboard_integration import get_ai_insights_summary
from .services.test_synthesizer import TestSynthesizer
from .models import TestCoverageGap


def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_staff or user.is_superuser


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize filename for Content-Disposition header to prevent header injection.

    Security measures:
    - Removes CRLF characters (\\r\\n) to prevent HTTP header injection
    - Removes control characters (ASCII 0-31)
    - Removes non-ASCII characters (prevent encoding attacks)
    - Removes quotes and backslashes (prevent quote escaping)
    - Limits length to prevent buffer overflows

    Args:
        filename: Untrusted filename from user input or database
        max_length: Maximum allowed filename length (default 200)

    Returns:
        Safe filename suitable for Content-Disposition header

    Security:
        Prevents CVE-2023-XXXX class HTTP header injection vulnerabilities

    References:
        - OWASP: HTTP Response Splitting
        - CWE-113: Improper Neutralization of CRLF Sequences in HTTP Headers
    """
    if not filename:
        return "download.txt"

    # Remove CRLF and all control characters (ASCII 0-31)
    sanitized = ''.join(c for c in filename if c not in '\r\n\t\x00' and ord(c) >= 32)

    # Remove quotes, backslashes that could break header syntax
    sanitized = sanitized.replace('"', '').replace('\\', '').replace("'", '')

    # Normalize Unicode and convert to ASCII (removes non-ASCII)
    sanitized = unicodedata.normalize('NFKD', sanitized).encode('ascii', 'ignore').decode('ascii')

    # Remove any remaining dangerous characters (keep only alphanumeric, spaces, hyphens, underscores, dots)
    sanitized = re.sub(r'[^\w\s\-_.]', '', sanitized)

    # Remove path traversal sequences
    sanitized = sanitized.replace('..', '').replace('/.', '').replace('\\.', '')

    # Limit length
    sanitized = sanitized[:max_length]

    # Fallback if everything was removed
    if not sanitized or sanitized.isspace():
        return "download.txt"

    return sanitized.strip()


# Coverage Gap Management Views

@user_passes_test(is_staff_or_superuser)
def coverage_gaps_list(request):
    """List all coverage gaps with filtering and sorting"""
    # Base queryset with comprehensive optimization
    gaps = TestCoverageGap.objects.select_related(
        'anomaly_signature',
        'assigned_to',
        'assigned_to__profile'
    ).prefetch_related(
        'related_gaps'
    )

    # Filtering
    coverage_type = request.GET.get('coverage_type')
    if coverage_type:
        gaps = gaps.filter(coverage_type=coverage_type)

    priority = request.GET.get('priority')
    if priority:
        gaps = gaps.filter(priority=priority)

    status = request.GET.get('status')
    if status:
        gaps = gaps.filter(status=status)
    else:
        # Default to active gaps only
        gaps = gaps.filter(status__in=['identified', 'test_generated', 'test_implemented'])

    # Search
    search = request.GET.get('search')
    if search:
        gaps = gaps.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(affected_endpoints__icontains=search)
        )

    # Sorting
    sort_by = request.GET.get('sort', '-confidence_score')
    valid_sorts = [
        'priority', '-priority',
        'confidence_score', '-confidence_score',
        'impact_score', '-impact_score',
        'identified_at', '-identified_at',
        'coverage_type', '-coverage_type'
    ]
    if sort_by in valid_sorts:
        gaps = gaps.order_by(sort_by)

    # Pagination
    paginator = Paginator(gaps, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    stats = {
        'total': gaps.count(),
        'critical': gaps.filter(priority='critical').count(),
        'high': gaps.filter(priority='high').count(),
        'implemented': gaps.filter(status='test_verified').count(),
        'coverage_types': dict(gaps.values('coverage_type').annotate(count=Count('id')).values_list('coverage_type', 'count')),
    }

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'current_filters': {
            'coverage_type': coverage_type,
            'priority': priority,
            'status': status,
            'search': search,
            'sort': sort_by
        },
        'coverage_type_choices': TestCoverageGap.COVERAGE_TYPES,
        'priority_choices': TestCoverageGap.PRIORITY_LEVELS,
        'status_choices': TestCoverageGap.GAP_STATUS,
    }

    return render(request, 'ai_testing/coverage_gaps_list.html', context)


@user_passes_test(is_staff_or_superuser)
def coverage_gap_detail(request, gap_id):
    """Detailed view of a specific coverage gap"""
    gap = get_object_or_404(TestCoverageGap, id=gap_id)

    # Get similar gaps for pattern analysis
    similar_gaps = TestCoverageGap.find_similar_gaps(gap, threshold=0.6)[:5]

    # Get related patterns
    patterns = gap.patterns.all()

    # Get implementation timeline
    timeline = [
        {'event': 'Gap Identified', 'timestamp': gap.identified_at, 'status': 'identified'},
    ]

    if gap.status in ['test_generated', 'test_implemented', 'test_verified']:
        timeline.append({
            'event': 'Test Generated',
            'timestamp': gap.updated_at,
            'status': 'test_generated'
        })

    if gap.implemented_at:
        timeline.append({
            'event': 'Test Implemented',
            'timestamp': gap.implemented_at,
            'status': 'test_implemented'
        })

    if gap.verified_at:
        timeline.append({
            'event': 'Test Verified',
            'timestamp': gap.verified_at,
            'status': 'test_verified'
        })

    context = {
        'gap': gap,
        'similar_gaps': similar_gaps,
        'patterns': patterns,
        'timeline': timeline,
        'framework_choices': TestCoverageGap.TEST_FRAMEWORKS,
        'estimated_time': gap.estimated_implementation_time,
    }

    return render(request, 'ai_testing/coverage_gap_detail.html', context)


@user_passes_test(is_staff_or_superuser)
@require_http_methods(["POST"])
@csrf_protect_htmx
@rate_limit(max_requests=50, window_seconds=300)
def update_gap_status(request, gap_id):
    """Update coverage gap status via HTMX"""
    gap = get_object_or_404(TestCoverageGap, id=gap_id)

    try:
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')

        if new_status not in dict(TestCoverageGap.GAP_STATUS):
            return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)

        if new_status == 'dismissed':
            gap.dismiss_gap(reason=notes, user=request.user)
        elif new_status == 'test_implemented':
            test_file_path = request.POST.get('test_file_path', '')
            commit_sha = request.POST.get('commit_sha', '')
            gap.mark_implemented(test_file_path, commit_sha, request.user)
        elif new_status == 'test_verified':
            gap.mark_verified(notes=notes, user=request.user)
        else:
            gap.status = new_status
            gap.assigned_to = request.user
            gap.save()

        return JsonResponse({
            'success': True,
            'message': f'Gap status updated to {new_status}',
            'new_status': new_status
        })

    except (DatabaseError, IntegrityError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# Test Generation Views

@user_passes_test(is_staff_or_superuser)
def generate_test(request, gap_id):
    """Generate test code for a coverage gap"""
    gap = get_object_or_404(TestCoverageGap, id=gap_id)

    if request.method == 'POST':
        try:
            framework = request.POST.get('framework', gap.recommended_framework)

            if not framework:
                return JsonResponse({
                    'success': False,
                    'error': 'No test framework specified'
                }, status=400)

            # Generate test code using AI
            test_code = gap.generate_test_code(framework)

            if test_code:
                return JsonResponse({
                    'success': True,
                    'message': 'Test code generated successfully',
                    'test_code': test_code,
                    'framework': framework,
                    'file_name': f"test_{gap.coverage_type}_{gap.id}.kt" if framework in ['espresso', 'junit'] else f"test_{gap.coverage_type}_{gap.id}.swift"
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to generate test code'
                }, status=500)

        except (DatabaseError, IntegrityError) as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    # GET request - show generation form
    context = {
        'gap': gap,
        'framework_choices': TestCoverageGap.TEST_FRAMEWORKS,
    }

    return render(request, 'ai_testing/generate_test.html', context)


@user_passes_test(is_staff_or_superuser)
def test_generation_dashboard(request):
    """Dashboard for test generation management"""
    # Optimized: Single queryset fetch with annotations to avoid N+1 queries
    from django.db.models import Q, Case, When, Value, IntegerField

    # Base queryset with optimization
    base_qs = TestCoverageGap.objects.select_related(
        'anomaly_signature',
        'assigned_to',
        'assigned_to__profile'
    ).filter(auto_generated_test_code__isnull=False)

    # Recent test generations
    recent_generations = base_qs.filter(
        status__in=['test_generated', 'test_implemented', 'test_verified']
    ).order_by('-updated_at')[:10]

    # Generation statistics (annotate in single query to avoid separate counts)
    all_generated = base_qs.annotate(
        is_pending=Case(When(status='test_generated', then=Value(1)), default=Value(0), output_field=IntegerField()),
        is_implemented=Case(When(status__in=['test_implemented', 'test_verified'], then=Value(1)), default=Value(0), output_field=IntegerField())
    ).values('recommended_framework').annotate(count=Count('id')).values_list('recommended_framework', 'count')

    stats = {
        'total_generated': base_qs.count(),
        'pending_implementation': TestCoverageGap.objects.filter(status='test_generated', auto_generated_test_code__isnull=False).count(),
        'implemented': TestCoverageGap.objects.filter(status__in=['test_implemented', 'test_verified'], auto_generated_test_code__isnull=False).count(),
        'framework_distribution': dict(all_generated)
    }

    context = {
        'recent_generations': recent_generations,
        'stats': stats,
    }

    return render(request, 'ai_testing/test_generation_dashboard.html', context)


@user_passes_test(is_staff_or_superuser)
def preview_generated_test(request):
    """Preview generated test code"""
    gap_id = request.GET.get('gap_id')
    framework = request.GET.get('framework')

    if not gap_id or not framework:
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        gap = TestCoverageGap.objects.get(id=gap_id)

        # Generate preview code
        synthesizer = TestSynthesizer()
        test_code = synthesizer.generate_test_for_gap(gap, framework)

        if test_code:
            file_extension = '.kt' if framework in ['espresso', 'junit', 'robolectric'] else '.swift'
            raw_filename = f"test_{gap.coverage_type}_{gap.title.replace(' ', '_').lower()}{file_extension}"
            # Sanitize filename for client-side download safety
            file_name = sanitize_filename(raw_filename)

            return JsonResponse({
                'success': True,
                'test_code': test_code,
                'file_name': file_name,
                'framework': framework,
                'coverage_type': gap.coverage_type,
                'description': gap.description
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Could not generate test code'
            }, status=500)

    except TestCoverageGap.DoesNotExist:
        return JsonResponse({'error': 'Coverage gap not found'}, status=404)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        return JsonResponse({'error': str(e)}, status=500)


@user_passes_test(is_staff_or_superuser)
def download_generated_test(request):
    """Download generated test file"""
    gap_id = request.GET.get('gap_id')
    framework = request.GET.get('framework')

    if not gap_id:
        raise Http404("Gap ID required")

    try:
        gap = TestCoverageGap.objects.get(id=gap_id)

        # Use existing code or generate new
        test_code = gap.auto_generated_test_code
        if not test_code and framework:
            test_code = gap.generate_test_code(framework)

        if not test_code:
            raise Http404("No test code available")

        # Determine file name and content type
        file_extension = '.kt' if framework in ['espresso', 'junit', 'robolectric'] else '.swift'
        raw_filename = f"test_{gap.coverage_type}_{gap.title.replace(' ', '_').lower()}{file_extension}"
        # Sanitize filename to prevent CRLF injection and header injection attacks
        file_name = sanitize_filename(raw_filename)

        response = HttpResponse(test_code, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'

        # Mark as downloaded
        gap.status = 'test_generated'
        gap.save()

        return response

    except TestCoverageGap.DoesNotExist:
        raise Http404("Coverage gap not found")


# API Views

@user_passes_test(is_staff_or_superuser)
def ai_insights_api(request):
    """REST API endpoint for AI insights data"""
    try:
        insights = get_ai_insights_summary()
        return JsonResponse({
            'success': True,
            'data': insights
        })
    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@user_passes_test(is_staff_or_superuser)
def coverage_gaps_api(request):
    """REST API endpoint for coverage gaps data"""
    try:
        # Query parameters
        limit = min(int(request.GET.get('limit', 50)), 100)
        status_filter = request.GET.get('status')
        priority_filter = request.GET.get('priority')

        # Build queryset
        gaps = TestCoverageGap.objects.all()

        if status_filter:
            gaps = gaps.filter(status=status_filter)

        if priority_filter:
            gaps = gaps.filter(priority=priority_filter)

        gaps = gaps.order_by('-confidence_score', '-impact_score')[:limit]

        # Serialize data
        gaps_data = []
        for gap in gaps:
            gaps_data.append({
                'id': str(gap.id),
                'title': gap.title,
                'coverage_type': gap.coverage_type,
                'priority': gap.priority,
                'status': gap.status,
                'confidence_score': gap.confidence_score,
                'impact_score': gap.impact_score,
                'affected_platforms': gap.affected_platforms,
                'affected_endpoints': gap.affected_endpoints,
                'identified_at': gap.identified_at.isoformat(),
                'estimated_time_hours': gap.estimated_implementation_time,
            })

        return JsonResponse({
            'success': True,
            'count': len(gaps_data),
            'data': gaps_data
        })

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# HTMX Partial Views

@user_passes_test(is_staff_or_superuser)
def gap_card_partial(request, gap_id):
    """HTMX partial for individual gap card updates"""
    gap = get_object_or_404(TestCoverageGap, id=gap_id)

    return render(request, 'ai_testing/partials/gap_card.html', {
        'gap': gap
    })


@user_passes_test(is_staff_or_superuser)
def test_preview_partial(request):
    """HTMX partial for test code preview"""
    gap_id = request.GET.get('gap_id')
    framework = request.GET.get('framework')

    if not gap_id or not framework:
        return render(request, 'ai_testing/partials/test_preview_error.html', {
            'error': 'Missing parameters'
        })

    try:
        gap = TestCoverageGap.objects.get(id=gap_id)

        # Use existing code or generate preview
        test_code = gap.auto_generated_test_code
        if not test_code:
            synthesizer = TestSynthesizer()
            test_code = synthesizer.generate_test_for_gap(gap, framework)

        if test_code:
            context = {
                'gap': gap,
                'test_code': test_code,
                'framework': framework,
                'file_extension': '.kt' if framework in ['espresso', 'junit', 'robolectric'] else '.swift'
            }
            return render(request, 'ai_testing/partials/test_preview.html', context)
        else:
            return render(request, 'ai_testing/partials/test_preview_error.html', {
                'error': 'Could not generate test code'
            })

    except TestCoverageGap.DoesNotExist:
        return render(request, 'ai_testing/partials/test_preview_error.html', {
            'error': 'Coverage gap not found'
        })
    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        return render(request, 'ai_testing/partials/test_preview_error.html', {
            'error': str(e)
        })
