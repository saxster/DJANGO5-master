"""
Rate Limiting Monitoring Dashboard Views

Provides real-time visibility into:
- Active rate limit violations
- Blocked IPs and auto-blocking events
- Top violating IPs and users
- Endpoint-specific metrics
- Violation trends and patterns

Complies with Rule #8 - View Method Size Limits (< 30 lines per method)
"""

import json
from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView

from apps.core.models.rate_limiting import (
    RateLimitBlockedIP,
    RateLimitTrustedIP,
    RateLimitViolationLog
)


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff access for rate limit monitoring."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff


@method_decorator(staff_member_required, name='dispatch')
class RateLimitDashboardView(StaffRequiredMixin, View):
    """
    Main rate limiting monitoring dashboard.

    Displays:
    - Real-time violation metrics
    - Currently blocked IPs
    - Recent violations
    - Endpoint protection status
    """
    template_name = 'core/rate_limit_dashboard.html'

    def get(self, request):
        """Render the rate limiting dashboard."""
        context = {
            'total_blocked_ips': RateLimitBlockedIP.objects.filter(
                is_active=True,
                blocked_until__gt=timezone.now()
            ).count(),
            'total_violations_24h': self._get_violations_count(hours=24),
            'total_violations_1h': self._get_violations_count(hours=1),
            'recent_blocks': RateLimitBlockedIP.objects.filter(
                is_active=True
            ).order_by('-blocked_at')[:10],
            'recent_violations': RateLimitViolationLog.objects.select_related(
                'user'
            ).order_by('-timestamp')[:20],
            'trusted_ips_count': RateLimitTrustedIP.objects.filter(
                is_active=True
            ).count(),
        }

        return render(request, self.template_name, context)

    def _get_violations_count(self, hours: int) -> int:
        """Get violation count for specified time window."""
        cutoff = timezone.now() - timedelta(hours=hours)
        return RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff
        ).count()


@method_decorator(staff_member_required, name='dispatch')
class RateLimitMetricsAPIView(StaffRequiredMixin, View):
    """
    API endpoint for real-time rate limiting metrics.

    Returns JSON data for dashboard charts and monitoring.
    """

    def get(self, request):
        """Return rate limiting metrics as JSON."""
        hours = int(request.GET.get('hours', 24))

        metrics = {
            'summary': self._get_summary_metrics(hours),
            'top_violating_ips': self._get_top_violating_ips(hours),
            'endpoint_metrics': self._get_endpoint_metrics(hours),
            'violation_timeline': self._get_violation_timeline(hours),
            'blocked_ips': self._get_blocked_ips_data(),
        }

        return JsonResponse(metrics)

    def _get_summary_metrics(self, hours: int) -> dict:
        """Get summary metrics for specified time window."""
        cutoff = timezone.now() - timedelta(hours=hours)

        return {
            'total_violations': RateLimitViolationLog.objects.filter(
                timestamp__gte=cutoff
            ).count(),
            'unique_ips': RateLimitViolationLog.objects.filter(
                timestamp__gte=cutoff
            ).values('client_ip').distinct().count(),
            'blocked_ips': RateLimitBlockedIP.objects.filter(
                is_active=True,
                blocked_until__gt=timezone.now()
            ).count(),
            'trusted_ips': RateLimitTrustedIP.objects.filter(
                is_active=True
            ).count(),
        }

    def _get_top_violating_ips(self, hours: int, limit: int = 10) -> list:
        """Get top violating IP addresses."""
        cutoff = timezone.now() - timedelta(hours=hours)

        violations = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff
        ).values('client_ip').annotate(
            violation_count=Count('id')
        ).order_by('-violation_count')[:limit]

        return list(violations)

    def _get_endpoint_metrics(self, hours: int) -> list:
        """Get metrics grouped by endpoint type."""
        cutoff = timezone.now() - timedelta(hours=hours)

        metrics = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff
        ).values('endpoint_type').annotate(
            violation_count=Count('id')
        ).order_by('-violation_count')

        return list(metrics)

    def _get_violation_timeline(self, hours: int) -> list:
        """Get violation timeline data for charting."""
        cutoff = timezone.now() - timedelta(hours=hours)

        violations = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff
        ).extra(
            select={'hour': "date_trunc('hour', timestamp)"}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')

        return [
            {
                'timestamp': v['hour'].isoformat(),
                'count': v['count']
            }
            for v in violations
        ]

    def _get_blocked_ips_data(self) -> list:
        """Get currently blocked IPs with details."""
        blocked = RateLimitBlockedIP.objects.filter(
            is_active=True,
            blocked_until__gt=timezone.now()
        ).order_by('-violation_count')

        return [
            {
                'ip_address': b.ip_address,
                'blocked_at': b.blocked_at.isoformat(),
                'blocked_until': b.blocked_until.isoformat(),
                'violation_count': b.violation_count,
                'endpoint_type': b.endpoint_type,
                'reason': b.reason
            }
            for b in blocked
        ]


@method_decorator(staff_member_required, name='dispatch')
class RateLimitBlockedIPListView(StaffRequiredMixin, ListView):
    """List view for managing blocked IPs."""
    model = RateLimitBlockedIP
    template_name = 'core/rate_limit_blocked_ips.html'
    context_object_name = 'blocked_ips'
    paginate_by = 50

    def get_queryset(self):
        """Get blocked IPs with filtering."""
        queryset = RateLimitBlockedIP.objects.filter(is_active=True)

        ip_filter = self.request.GET.get('ip')
        if ip_filter:
            queryset = queryset.filter(ip_address__icontains=ip_filter)

        endpoint_filter = self.request.GET.get('endpoint')
        if endpoint_filter:
            queryset = queryset.filter(endpoint_type=endpoint_filter)

        return queryset.order_by('-blocked_at')


@method_decorator(staff_member_required, name='dispatch')
class RateLimitTrustedIPListView(StaffRequiredMixin, ListView):
    """List view for managing trusted IPs."""
    model = RateLimitTrustedIP
    template_name = 'core/rate_limit_trusted_ips.html'
    context_object_name = 'trusted_ips'
    paginate_by = 50

    def get_queryset(self):
        """Get trusted IPs with filtering."""
        queryset = RateLimitTrustedIP.objects.filter(is_active=True)

        ip_filter = self.request.GET.get('ip')
        if ip_filter:
            queryset = queryset.filter(ip_address__icontains=ip_filter)

        return queryset.order_by('-added_at')


@method_decorator(staff_member_required, name='dispatch')
class RateLimitUnblockIPView(StaffRequiredMixin, View):
    """Manually unblock an IP address."""

    def post(self, request, ip_address):
        """Unblock the specified IP address."""
        try:
            blocked_ip = RateLimitBlockedIP.objects.get(
                ip_address=ip_address,
                is_active=True
            )

            blocked_ip.is_active = False
            blocked_ip.notes = f"{blocked_ip.notes}\nUnblocked by {request.user.loginid} at {timezone.now()}"
            blocked_ip.save()

            cache_key = f"blocked_ip:{ip_address}"
            cache.delete(cache_key)

            return JsonResponse({
                'success': True,
                'message': f'IP {ip_address} has been unblocked'
            })

        except RateLimitBlockedIP.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'IP not found in blocked list'
            }, status=404)


@method_decorator(staff_member_required, name='dispatch')
class RateLimitAddTrustedIPView(StaffRequiredMixin, View):
    """Add an IP to the trusted whitelist."""

    def post(self, request):
        """Add IP to trusted list."""
        data = json.loads(request.body)
        ip_address = data.get('ip_address')
        description = data.get('description', '')

        if not ip_address:
            return JsonResponse({
                'success': False,
                'error': 'IP address is required'
            }, status=400)

        try:
            trusted_ip, created = RateLimitTrustedIP.objects.get_or_create(
                ip_address=ip_address,
                defaults={
                    'description': description,
                    'added_by': request.user,
                    'is_active': True
                }
            )

            cache.delete('trusted_ips_set')

            return JsonResponse({
                'success': True,
                'created': created,
                'message': f'IP {ip_address} added to trusted list' if created else 'IP already in trusted list'
            })

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class RateLimitViolationAnalyticsView(StaffRequiredMixin, View):
    """Advanced analytics for rate limit violations."""

    def get(self, request):
        """Return advanced analytics data."""
        hours = int(request.GET.get('hours', 24))
        cutoff = timezone.now() - timedelta(hours=hours)

        analytics = {
            'attack_patterns': self._detect_attack_patterns(cutoff),
            'geographic_distribution': self._get_geographic_distribution(cutoff),
            'time_distribution': self._get_time_distribution(cutoff),
            'user_vs_anonymous': self._get_user_distribution(cutoff),
        }

        return JsonResponse(analytics)

    def _detect_attack_patterns(self, cutoff):
        """Detect coordinated attack patterns."""
        violations = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff
        ).values('client_ip', 'endpoint_type').annotate(
            count=Count('id')
        ).filter(count__gte=5)

        return list(violations)

    def _get_geographic_distribution(self, cutoff):
        """Get geographic distribution of violations."""
        return []

    def _get_time_distribution(self, cutoff):
        """Get hourly distribution of violations."""
        violations = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff
        ).extra(
            select={'hour': "EXTRACT(hour FROM timestamp)"}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')

        return list(violations)

    def _get_user_distribution(self, cutoff):
        """Get authenticated vs anonymous violation distribution."""
        total = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff
        ).count()

        authenticated = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff,
            user__isnull=False
        ).count()

        return {
            'total': total,
            'authenticated': authenticated,
            'anonymous': total - authenticated
        }