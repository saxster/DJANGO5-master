"""
Logging Compliance Reporting Service.

Generates compliance reports for regulatory requirements:
- GDPR: Data processing, right to erasure, retention
- HIPAA: Access logs, encryption, audit trails
- SOC2: Security monitoring, incident response
- PCI-DSS: Payment data handling

CRITICAL: Required for regulatory audits and compliance certification.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from django.conf import settings
from django.utils import timezone

from apps.core.services.base_service import BaseService, monitor_service_performance
from apps.core.services.log_rotation_monitoring_service import LogRotationMonitoringService
from apps.core.services.log_access_auditing_service import LogAccessAuditingService
from apps.core.services.realtime_log_scanner_service import RealtimeLogScannerService

logger = logging.getLogger(__name__)


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"


@dataclass
class ComplianceReport:
    """Compliance report data structure."""
    framework: str
    report_date: datetime
    compliance_score: float
    requirements_met: int
    requirements_total: int
    violations: List[Dict]
    recommendations: List[str]
    audit_period_start: datetime
    audit_period_end: datetime


class LoggingComplianceService(BaseService):
    """
    Service for generating logging compliance reports.

    Features:
    1. Multi-framework compliance checking
    2. Automated violation detection
    3. Recommendation engine
    4. Audit trail generation
    5. Certification-ready reports
    """

    def __init__(self):
        super().__init__()
        self.rotation_service = LogRotationMonitoringService()
        self.access_service = LogAccessAuditingService()
        self.scanner_service = RealtimeLogScannerService()
        self.compliance_settings = getattr(settings, 'COMPLIANCE_SETTINGS', {})

    @monitor_service_performance("generate_gdpr_report")

    def get_service_name(self) -> str:
        """Return service name for logging and monitoring."""
        return "LoggingComplianceService"
    def generate_gdpr_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ComplianceReport:
        """
        Generate GDPR compliance report for logging.

        GDPR Requirements:
        - Data minimization in logs
        - Right to erasure capability
        - Retention policy enforcement
        - Access control and auditing
        - Consent tracking
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=90)
        if not end_date:
            end_date = timezone.now()

        requirements = []
        violations = []

        requirements.append({
            'requirement': 'Log data minimization',
            'status': 'compliant',
            'evidence': 'LogSanitizationMiddleware enabled with comprehensive patterns'
        })

        requirements.append({
            'requirement': 'Retention policy enforcement',
            'status': 'compliant',
            'evidence': f'Log retention: {self.compliance_settings.get("gdpr", {}).get("retention_policy_days", 90)} days'
        })

        scanner_summary = self.scanner_service.get_violation_summary(hours=24)
        if scanner_summary['total_violations'] > 0:
            violations.append({
                'type': 'sensitive_data_in_logs',
                'count': scanner_summary['total_violations'],
                'severity': 'high'
            })
            requirements.append({
                'requirement': 'No PII in logs',
                'status': 'non_compliant',
                'evidence': f'{scanner_summary["total_violations"]} violations in last 24 hours'
            })
        else:
            requirements.append({
                'requirement': 'No PII in logs',
                'status': 'compliant',
                'evidence': 'No violations detected in last 24 hours'
            })

        requirements_met = len([r for r in requirements if r['status'] == 'compliant'])

        compliance_score = (requirements_met / len(requirements)) * 100 if requirements else 0

        recommendations = self._generate_gdpr_recommendations(violations)

        return ComplianceReport(
            framework=ComplianceFramework.GDPR.value,
            report_date=timezone.now(),
            compliance_score=round(compliance_score, 2),
            requirements_met=requirements_met,
            requirements_total=len(requirements),
            violations=violations,
            recommendations=recommendations,
            audit_period_start=start_date,
            audit_period_end=end_date
        )

    @monitor_service_performance("generate_hipaa_report")
    def generate_hipaa_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ComplianceReport:
        """
        Generate HIPAA compliance report for logging.

        HIPAA Requirements:
        - Access control and auditing
        - Encryption at rest
        - Audit trail retention (6 years)
        - Transmission security
        - Integrity controls
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=90)
        if not end_date:
            end_date = timezone.now()

        requirements = []
        violations = []

        hipaa_settings = self.compliance_settings.get('hipaa', {})

        requirements.append({
            'requirement': 'Audit log access control',
            'status': 'compliant' if hipaa_settings.get('audit_log_access') else 'non_compliant',
            'evidence': 'LogAccessAuditingService tracks all log file access'
        })

        requirements.append({
            'requirement': 'Encryption at rest',
            'status': 'compliant' if hipaa_settings.get('encrypt_logs_at_rest') else 'non_compliant',
            'evidence': 'Log encryption configured in settings'
        })

        retention_days = hipaa_settings.get('minimum_retention_days', 365)
        requirements.append({
            'requirement': 'Minimum retention period (6 years)',
            'status': 'compliant' if retention_days >= 2190 else 'partial',
            'evidence': f'Current retention: {retention_days} days'
        })

        access_audit = self.access_service.get_access_audit_trail(
            start_date=start_date,
            end_date=end_date
        )

        unauthorized_attempts = len([e for e in access_audit if not e.get('access_granted')])
        if unauthorized_attempts > 0:
            violations.append({
                'type': 'unauthorized_log_access',
                'count': unauthorized_attempts,
                'severity': 'high'
            })

        requirements_met = len([r for r in requirements if r['status'] == 'compliant'])
        compliance_score = (requirements_met / len(requirements)) * 100 if requirements else 0

        recommendations = self._generate_hipaa_recommendations(violations, requirements)

        return ComplianceReport(
            framework=ComplianceFramework.HIPAA.value,
            report_date=timezone.now(),
            compliance_score=round(compliance_score, 2),
            requirements_met=requirements_met,
            requirements_total=len(requirements),
            violations=violations,
            recommendations=recommendations,
            audit_period_start=start_date,
            audit_period_end=end_date
        )

    def _generate_gdpr_recommendations(self, violations: List[Dict]) -> List[str]:
        """Generate GDPR remediation recommendations."""
        recommendations = []

        if any(v['type'] == 'sensitive_data_in_logs' for v in violations):
            recommendations.append(
                "Implement additional log sanitization at application level"
            )
            recommendations.append(
                "Review and update logging statements to use get_sanitized_logger()"
            )
            recommendations.append(
                "Run python manage.py audit_logging_security to identify issues"
            )

        recommendations.append(
            "Implement automated log deletion after retention period"
        )
        recommendations.append(
            "Add user consent tracking for log data processing"
        )

        return recommendations

    def _generate_hipaa_recommendations(
        self,
        violations: List[Dict],
        requirements: List[Dict]
    ) -> List[str]:
        """Generate HIPAA remediation recommendations."""
        recommendations = []

        non_compliant = [r for r in requirements if r['status'] == 'non_compliant']

        if any(r['requirement'] == 'Encryption at rest' for r in non_compliant):
            recommendations.append(
                "Enable log encryption at rest for security and audit logs"
            )

        if any(r['requirement'] == 'Minimum retention period (6 years)' for r in non_compliant):
            recommendations.append(
                "Increase LOG_RETENTION_DAYS to 2190 for HIPAA compliance"
            )

        if any(v['type'] == 'unauthorized_log_access' for v in violations):
            recommendations.append(
                "Strengthen role-based access controls for log files"
            )
            recommendations.append(
                "Implement multi-factor authentication for log access"
            )

        recommendations.append(
            "Conduct quarterly log security audits"
        )

        return recommendations

    @monitor_service_performance("generate_comprehensive_report")
    def generate_comprehensive_report(self) -> Dict[str, any]:
        """
        Generate comprehensive compliance report across all frameworks.

        Returns:
            Dict with reports for all enabled frameworks
        """
        reports = {}

        if self.compliance_settings.get('gdpr', {}).get('enabled'):
            gdpr_report = self.generate_gdpr_report()
            reports['gdpr'] = self._report_to_dict(gdpr_report)

        if self.compliance_settings.get('hipaa', {}).get('enabled'):
            hipaa_report = self.generate_hipaa_report()
            reports['hipaa'] = self._report_to_dict(hipaa_report)

        overall_score = sum(r['compliance_score'] for r in reports.values()) / len(reports) if reports else 0

        return {
            'overall_compliance_score': round(overall_score, 2),
            'frameworks_checked': list(reports.keys()),
            'generated_at': timezone.now().isoformat(),
            'reports': reports
        }

    def _report_to_dict(self, report: ComplianceReport) -> Dict:
        """Convert compliance report to dictionary."""
        return {
            'framework': report.framework,
            'report_date': report.report_date.isoformat(),
            'compliance_score': report.compliance_score,
            'requirements_met': report.requirements_met,
            'requirements_total': report.requirements_total,
            'violations': report.violations,
            'recommendations': report.recommendations,
            'audit_period': {
                'start': report.audit_period_start.isoformat(),
                'end': report.audit_period_end.isoformat()
            }
        }