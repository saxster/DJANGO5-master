"""
File Upload Security Dashboard Views

Real-time monitoring and analytics for file upload security.
Provides visibility into upload patterns, security incidents, and compliance metrics.

Features:
- Real-time upload monitoring
- Security incident dashboard
- Failed upload analytics
- Path traversal attempt detection
- File type distribution charts
- User upload behavior analysis
- Quarantined files management
- Compliance reporting
"""

import json
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.db.models import Count, Sum, Q
from apps.core.services.file_upload_audit_service import FileUploadAuditLog, FileUploadAuditService


class FileUploadSecurityDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Main security dashboard for file upload monitoring."""

    template_name = 'core/file_upload_security_dashboard.html'

    def test_func(self):
        """Only admins can access security dashboard."""
        return self.request.user.isadmin

    def get_context_data(self, **kwargs):
        """Prepare dashboard data."""
        context = super().get_context_data(**kwargs)

        hours = int(self.request.GET.get('hours', 24))

        context['dashboard_data'] = {
            'upload_stats': FileUploadAuditService.get_upload_statistics(days=7),
            'recent_incidents': FileUploadAuditService.get_security_incidents(hours=hours),
            'hours_displayed': hours
        }

        return context


class FileUploadStatsAPIView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """API endpoint for real-time upload statistics."""

    def test_func(self):
        return self.request.user.isadmin

    def get(self, request, *args, **kwargs):
        """Get real-time upload statistics."""
        days = int(request.GET.get('days', 7))

        stats = FileUploadAuditService.get_upload_statistics(days=days)

        return JsonResponse(stats if stats else {'error': 'Failed to generate statistics'})


class SecurityIncidentsAPIView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """API endpoint for security incidents."""

    def test_func(self):
        return self.request.user.isadmin

    def get(self, request, *args, **kwargs):
        """Get recent security incidents."""
        hours = int(request.GET.get('hours', 24))

        incidents = FileUploadAuditService.get_security_incidents(hours=hours)

        return JsonResponse({
            'incidents': incidents,
            'count': len(incidents),
            'hours': hours
        })


class QuarantinedFilesView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """View and manage quarantined files."""

    template_name = 'core/quarantined_files.html'

    def test_func(self):
        return self.request.user.isadmin

    def get_context_data(self, **kwargs):
        """Get list of quarantined files."""
        context = super().get_context_data(**kwargs)

        quarantined = FileUploadAuditLog.objects.filter(
            event_type__in=['QUARANTINED', 'MALWARE_DETECTED']
        ).select_related('user').order_by('-timestamp')[:100]

        context['quarantined_files'] = quarantined

        return context


class UserUploadPatternsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Analyze user upload patterns for anomaly detection."""

    def test_func(self):
        return self.request.user.isadmin

    def get(self, request, *args, **kwargs):
        """Get user upload patterns."""
        user_id = request.GET.get('user_id')

        if not user_id:
            return JsonResponse({'error': 'user_id required'}, status=400)

        days = int(request.GET.get('days', 30))

        patterns = FileUploadAuditService.get_user_upload_patterns(user_id, days=days)

        return JsonResponse(patterns if patterns else {'error': 'Failed to analyze patterns'})


class ComplianceReportView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Generate compliance reports for auditors."""

    template_name = 'core/compliance_report.html'

    def test_func(self):
        return self.request.user.isadmin

    def get_context_data(self, **kwargs):
        """Generate compliance report data."""
        context = super().get_context_data(**kwargs)

        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        if self.request.GET.get('start_date'):
            from dateutil import parser
            start_date = parser.parse(self.request.GET['start_date'])

        if self.request.GET.get('end_date'):
            from dateutil import parser
            end_date = parser.parse(self.request.GET['end_date'])

        report = FileUploadAuditService.generate_compliance_report(start_date, end_date)

        context['compliance_report'] = report
        context['start_date'] = start_date
        context['end_date'] = end_date

        return context


class FileUploadAlertsAPIView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Real-time alerts for security events."""

    def test_func(self):
        return self.request.user.isadmin

    def get(self, request, *args, **kwargs):
        """Get recent security alerts."""
        minutes = int(request.GET.get('minutes', 60))
        cutoff_time = timezone.now() - timedelta(minutes=minutes)

        alerts = FileUploadAuditLog.objects.filter(
            timestamp__gte=cutoff_time,
            severity__in=['ERROR', 'CRITICAL']
        ).select_related('user').values(
            'id',
            'correlation_id',
            'timestamp',
            'event_type',
            'severity',
            'user__peoplename',
            'ip_address',
            'filename',
            'error_message'
        ).order_by('-timestamp')

        return JsonResponse({
            'alerts': list(alerts),
            'count': len(alerts),
            'period_minutes': minutes,
            'last_updated': timezone.now().isoformat()
        })