"""
SOS Incident Review Report Generation Service

Generates comprehensive post-incident review reports for SOS alerts
including timeline, response actions, location tracking, evidence, and lessons learned.

Features:
- Timeline reconstruction from audit logs
- Response action tracking
- Guard location history
- Photo/evidence attachment
- PDF generation with professional formatting
- Lessons learned documentation

Report Structure:
- Executive Summary
- Incident Timeline
- Response Actions Taken
- Location Tracking Map
- Evidence Gallery
- Lessons Learned
- Recommendations

Compliance: CLAUDE.md Rule #7 (file size), Rule #11 (specific exceptions)
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Dict, List, Optional
from io import BytesIO

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.template.loader import render_to_string
from django.conf import settings

from apps.attendance.models import SOSAlert, Attendance
from apps.mqtt.models import LocationUpdate
from apps.core.models import AuditLog
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, FILE_EXCEPTIONS
from apps.core.utils_new.datetime_utilities import get_current_utc, format_time_delta

logger = logging.getLogger(__name__)


class SOSReviewService:
    """
    Service for generating SOS incident review reports.
    """

    SEVERITY_LEVELS = {
        'CRITICAL': 'Critical - Immediate threat to life/safety',
        'HIGH': 'High - Serious incident requiring immediate response',
        'MEDIUM': 'Medium - Incident requiring prompt attention',
        'LOW': 'Low - Minor incident, documented for record',
    }

    @classmethod
    def generate_review_report(
        cls,
        sos_alert_id: int,
        tenant_id: int,
        include_evidence: bool = True
    ) -> Dict:
        """
        Generate comprehensive SOS incident review report.

        Args:
            sos_alert_id: SOS alert identifier
            tenant_id: Tenant identifier
            include_evidence: Whether to include photo evidence

        Returns:
            Report data dictionary for PDF generation

        Raises:
            ValidationError: If SOS alert not found or invalid
        """
        try:
            sos_alert = SOSAlert.objects.select_related(
                'guard', 'responder', 'site'
            ).get(id=sos_alert_id, tenant_id=tenant_id)

            report = {
                'metadata': cls._build_metadata(sos_alert),
                'executive_summary': cls._build_executive_summary(sos_alert),
                'timeline': cls._build_timeline(sos_alert),
                'response_actions': cls._build_response_actions(sos_alert),
                'location_tracking': cls._build_location_tracking(sos_alert),
                'lessons_learned': cls._extract_lessons_learned(sos_alert),
                'recommendations': cls._generate_recommendations(sos_alert),
            }

            if include_evidence:
                report['evidence'] = cls._gather_evidence(sos_alert)

            logger.info(f"Generated SOS review report for alert {sos_alert_id}")
            return report

        except ObjectDoesNotExist:
            raise ValidationError(f"SOS alert {sos_alert_id} not found")
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error generating SOS report: {e}", exc_info=True)
            raise ValidationError("Failed to generate review report")

    @classmethod
    def generate_pdf(cls, report_data: Dict) -> bytes:
        """
        Generate PDF from report data.

        Args:
            report_data: Report dictionary from generate_review_report

        Returns:
            PDF file as bytes

        Raises:
            ValidationError: If PDF generation fails
        """
        try:
            from weasyprint import HTML

            html_content = render_to_string(
                'attendance/sos_review_report.html',
                report_data
            )

            pdf_file = HTML(string=html_content).write_pdf()

            logger.info("Generated PDF for SOS review report")
            return pdf_file

        except ImportError:
            logger.error("WeasyPrint not installed for PDF generation")
            raise ValidationError("PDF generation library not available")
        except (ValueError, TypeError) as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            raise ValidationError(f"Failed to generate PDF: {e}")

    @classmethod
    def _build_metadata(cls, sos_alert) -> Dict:
        """Build report metadata section."""
        return {
            'report_id': f"SOS-{sos_alert.id}-{get_current_utc().strftime('%Y%m%d')}",
            'generated_at': get_current_utc().isoformat(),
            'incident_id': sos_alert.id,
            'site_name': sos_alert.site.name if sos_alert.site else 'Unknown',
            'tenant_id': sos_alert.tenant_id,
            'classification': sos_alert.severity or 'UNCLASSIFIED',
        }

    @classmethod
    def _build_executive_summary(cls, sos_alert) -> Dict:
        """Build executive summary section."""
        response_time = None
        if sos_alert.acknowledged_at and sos_alert.triggered_at:
            delta = sos_alert.acknowledged_at - sos_alert.triggered_at
            response_time = format_time_delta(delta)

        resolution_time = None
        if sos_alert.resolved_at and sos_alert.triggered_at:
            delta = sos_alert.resolved_at - sos_alert.triggered_at
            resolution_time = format_time_delta(delta)

        return {
            'guard_name': sos_alert.guard.username if sos_alert.guard else 'Unknown',
            'guard_id': sos_alert.guard_id,
            'incident_time': sos_alert.triggered_at.isoformat() if sos_alert.triggered_at else None,
            'location': sos_alert.location_description or 'Not specified',
            'severity': sos_alert.severity or 'MEDIUM',
            'severity_description': cls.SEVERITY_LEVELS.get(
                sos_alert.severity or 'MEDIUM',
                'Standard incident'
            ),
            'response_time': response_time,
            'resolution_time': resolution_time,
            'responder_name': sos_alert.responder.username if sos_alert.responder else 'None',
            'status': sos_alert.status,
            'injuries_reported': sos_alert.metadata.get('injuries', False),
            'police_contacted': sos_alert.metadata.get('police_contacted', False),
        }

    @classmethod
    def _build_timeline(cls, sos_alert) -> List[Dict]:
        """Build incident timeline from audit logs and SOS data."""
        timeline = []

        if sos_alert.triggered_at:
            timeline.append({
                'timestamp': sos_alert.triggered_at.isoformat(),
                'event': 'SOS Alert Triggered',
                'actor': sos_alert.guard.username if sos_alert.guard else 'System',
                'details': f"Location: {sos_alert.location_description or 'Unknown'}",
            })

        if sos_alert.acknowledged_at:
            timeline.append({
                'timestamp': sos_alert.acknowledged_at.isoformat(),
                'event': 'Alert Acknowledged',
                'actor': sos_alert.responder.username if sos_alert.responder else 'Unknown',
                'details': 'Responder dispatched',
            })

        audit_logs = AuditLog.objects.filter(
            tenant_id=sos_alert.tenant_id,
            object_id=str(sos_alert.id),
            created_at__gte=sos_alert.triggered_at
        ).order_by('created_at')

        for log in audit_logs:
            timeline.append({
                'timestamp': log.created_at.isoformat(),
                'event': log.event_type,
                'actor': log.user.username if log.user else 'System',
                'details': log.message or '',
            })

        if sos_alert.resolved_at:
            timeline.append({
                'timestamp': sos_alert.resolved_at.isoformat(),
                'event': 'Incident Resolved',
                'actor': sos_alert.responder.username if sos_alert.responder else 'System',
                'details': sos_alert.resolution_notes or 'Incident closed',
            })

        timeline.sort(key=lambda x: x['timestamp'])
        return timeline

    @classmethod
    def _build_response_actions(cls, sos_alert) -> List[Dict]:
        """Build list of response actions taken."""
        actions = []

        if sos_alert.metadata.get('actions_taken'):
            for action in sos_alert.metadata['actions_taken']:
                actions.append({
                    'action': action.get('description', ''),
                    'timestamp': action.get('timestamp', ''),
                    'performed_by': action.get('actor', 'Unknown'),
                    'outcome': action.get('outcome', 'Completed'),
                })

        if not actions and sos_alert.resolution_notes:
            actions.append({
                'action': 'Incident Resolution',
                'timestamp': sos_alert.resolved_at.isoformat() if sos_alert.resolved_at else '',
                'performed_by': sos_alert.responder.username if sos_alert.responder else 'Unknown',
                'outcome': sos_alert.resolution_notes,
            })

        return actions

    @classmethod
    def _build_location_tracking(cls, sos_alert) -> Dict:
        """Build guard location tracking data."""
        if not sos_alert.guard_id or not sos_alert.triggered_at:
            return {'available': False}

        try:
            start_time = sos_alert.triggered_at - timedelta(minutes=30)
            end_time = sos_alert.resolved_at or get_current_utc()

            locations = LocationUpdate.objects.filter(
                guard_id=sos_alert.guard_id,
                timestamp__gte=start_time,
                timestamp__lte=end_time
            ).order_by('timestamp')

            tracking_points = [
                {
                    'latitude': loc.latitude,
                    'longitude': loc.longitude,
                    'timestamp': loc.timestamp.isoformat(),
                    'in_geofence': loc.in_geofence,
                }
                for loc in locations
            ]

            return {
                'available': True,
                'tracking_points': tracking_points,
                'total_points': len(tracking_points),
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error fetching location tracking: {e}")
            return {'available': False, 'error': str(e)}

    @classmethod
    def _gather_evidence(cls, sos_alert) -> List[Dict]:
        """Gather photo and document evidence."""
        evidence = []

        if sos_alert.metadata.get('attachments'):
            for attachment in sos_alert.metadata['attachments']:
                evidence.append({
                    'type': attachment.get('type', 'photo'),
                    'filename': attachment.get('filename', 'Unknown'),
                    'url': attachment.get('url', ''),
                    'timestamp': attachment.get('timestamp', ''),
                    'description': attachment.get('description', ''),
                })

        return evidence

    @classmethod
    def _extract_lessons_learned(cls, sos_alert) -> List[str]:
        """Extract lessons learned from incident."""
        lessons = []

        if sos_alert.metadata.get('lessons_learned'):
            lessons = sos_alert.metadata['lessons_learned']
        elif sos_alert.post_incident_notes:
            lessons.append(sos_alert.post_incident_notes)

        return lessons

    @classmethod
    def _generate_recommendations(cls, sos_alert) -> List[Dict]:
        """Generate recommendations based on incident analysis."""
        recommendations = []

        if sos_alert.acknowledged_at and sos_alert.triggered_at:
            response_seconds = (sos_alert.acknowledged_at - sos_alert.triggered_at).total_seconds()
            if response_seconds > 300:
                recommendations.append({
                    'category': 'Response Time',
                    'priority': 'HIGH',
                    'recommendation': 'Review responder notification process - response time exceeded 5 minutes',
                })

        if not sos_alert.metadata.get('police_contacted') and sos_alert.severity == 'CRITICAL':
            recommendations.append({
                'category': 'External Coordination',
                'priority': 'MEDIUM',
                'recommendation': 'Consider police notification protocol for critical severity incidents',
            })

        if sos_alert.metadata.get('actions_taken') is None:
            recommendations.append({
                'category': 'Documentation',
                'priority': 'MEDIUM',
                'recommendation': 'Implement structured action logging for better incident reconstruction',
            })

        return recommendations
