"""
Logging Compliance Dashboard Views.

Provides web interface for:
- GDPR compliance monitoring
- HIPAA audit trail viewing
- Real-time security violation alerts
- Log access auditing
- Compliance reporting

CRITICAL: Required for regulatory compliance and security auditing.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.core.exceptions import PermissionDenied

from apps.core.services.logging_compliance_service import LoggingComplianceService
from apps.core.services.log_rotation_monitoring_service import LogRotationMonitoringService
from apps.core.services.log_access_auditing_service import LogAccessAuditingService, LogAccessOperation
from apps.core.services.realtime_log_scanner_service import RealtimeLogScannerService
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


def is_compliance_officer(user):
    """Check if user has compliance officer permissions."""
    return user.is_superuser or (
        hasattr(user, 'groups') and
        user.groups.filter(name__in=['compliance_officer', 'security_admin']).exists()
    )


@login_required
@user_passes_test(is_compliance_officer)
@require_http_methods(["GET"])
def compliance_dashboard(request):
    """Main compliance dashboard view."""
    try:
        compliance_service = LoggingComplianceService()
        rotation_service = LogRotationMonitoringService()
        scanner_service = RealtimeLogScannerService()

        comprehensive_report = compliance_service.generate_comprehensive_report()
        rotation_status = rotation_service.check_log_rotation_status()
        scanner_summary = scanner_service.get_violation_summary(hours=24)

        context = {
            'compliance_report': comprehensive_report,
            'rotation_status': rotation_status,
            'scanner_summary': scanner_summary,
            'last_updated': timezone.now(),
        }

        return render(request, 'core/logging_compliance_dashboard.html', context)

    except (ValueError, TypeError) as e:
        correlation_id = getattr(request, 'correlation_id', None)
        ErrorHandler.handle_exception(
            e,
            context={'view': 'compliance_dashboard'},
            correlation_id=correlation_id
        )
        raise


@login_required
@user_passes_test(is_compliance_officer)
@require_http_methods(["GET"])
def gdpr_compliance_report(request):
    """GDPR-specific compliance report."""
    try:
        compliance_service = LoggingComplianceService()

        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.fromisoformat(start_date)
        if end_date:
            end_date = datetime.fromisoformat(end_date)

        report = compliance_service.generate_gdpr_report(start_date, end_date)

        return JsonResponse({
            'status': 'success',
            'report': {
                'framework': report.framework,
                'compliance_score': report.compliance_score,
                'requirements_met': report.requirements_met,
                'requirements_total': report.requirements_total,
                'violations': report.violations,
                'recommendations': report.recommendations,
                'audit_period': {
                    'start': report.audit_period_start.isoformat(),
                    'end': report.audit_period_end.isoformat()
                },
                'report_date': report.report_date.isoformat()
            }
        })

    except (ValueError, TypeError) as e:
        correlation_id = getattr(request, 'correlation_id', None)
        ErrorHandler.handle_exception(
            e,
            context={'view': 'gdpr_compliance_report'},
            correlation_id=correlation_id
        )
        return JsonResponse({
            'status': 'error',
            'error': 'Failed to generate GDPR report',
            'correlation_id': correlation_id
        }, status=500)


@login_required
@user_passes_test(is_compliance_officer)
@require_http_methods(["GET"])
def hipaa_compliance_report(request):
    """HIPAA-specific compliance report."""
    try:
        compliance_service = LoggingComplianceService()

        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.fromisoformat(start_date)
        if end_date:
            end_date = datetime.fromisoformat(end_date)

        report = compliance_service.generate_hipaa_report(start_date, end_date)

        return JsonResponse({
            'status': 'success',
            'report': {
                'framework': report.framework,
                'compliance_score': report.compliance_score,
                'requirements_met': report.requirements_met,
                'requirements_total': report.requirements_total,
                'violations': report.violations,
                'recommendations': report.recommendations,
                'audit_period': {
                    'start': report.audit_period_start.isoformat(),
                    'end': report.audit_period_end.isoformat()
                },
                'report_date': report.report_date.isoformat()
            }
        })

    except (ValueError, TypeError) as e:
        correlation_id = getattr(request, 'correlation_id', None)
        ErrorHandler.handle_exception(
            e,
            context={'view': 'hipaa_compliance_report'},
            correlation_id=correlation_id
        )
        return JsonResponse({
            'status': 'error',
            'error': 'Failed to generate HIPAA report',
            'correlation_id': correlation_id
        }, status=500)


@login_required
@user_passes_test(is_compliance_officer)
@require_http_methods(["GET"])
def log_access_audit_trail(request):
    """View log access audit trail."""
    try:
        access_service = LogAccessAuditingService()

        user_id = request.GET.get('user_id')
        log_file_type = request.GET.get('log_file_type')
        days = int(request.GET.get('days', 30))

        start_date = timezone.now() - timedelta(days=days)

        audit_trail = access_service.get_access_audit_trail(
            user_id=int(user_id) if user_id else None,
            log_file_type=log_file_type,
            start_date=start_date,
            end_date=timezone.now()
        )

        return JsonResponse({
            'status': 'success',
            'audit_trail': audit_trail,
            'total_accesses': len(audit_trail),
            'unauthorized_attempts': len([e for e in audit_trail if not e.get('access_granted')]),
            'time_period_days': days
        })

    except (ValueError, TypeError) as e:
        correlation_id = getattr(request, 'correlation_id', None)
        ErrorHandler.handle_exception(
            e,
            context={'view': 'log_access_audit_trail'},
            correlation_id=correlation_id
        )
        return JsonResponse({
            'status': 'error',
            'error': 'Failed to retrieve audit trail',
            'correlation_id': correlation_id
        }, status=500)


@login_required
@user_passes_test(is_compliance_officer)
@require_http_methods(["GET"])
def security_violations_report(request):
    """View recent security violations from log scanner."""
    try:
        scanner_service = RealtimeLogScannerService()

        hours = int(request.GET.get('hours', 24))

        summary = scanner_service.get_violation_summary(hours=hours)

        return JsonResponse({
            'status': 'success',
            'summary': summary
        })

    except (ValueError, TypeError) as e:
        correlation_id = getattr(request, 'correlation_id', None)
        ErrorHandler.handle_exception(
            e,
            context={'view': 'security_violations_report'},
            correlation_id=correlation_id
        )
        return JsonResponse({
            'status': 'error',
            'error': 'Failed to generate security violations report',
            'correlation_id': correlation_id
        }, status=500)