"""
Attendance Audit Service

Provides high-level interface for querying and analyzing audit logs.

Features:
- Query audit logs with filters
- Generate audit reports
- Detect suspicious patterns
- Export audit data for compliance
- Analytics and metrics

Used by:
- Admin dashboard
- Compliance reports
- Security investigations
- Performance monitoring
"""

from django.db.models import Q, Count, Avg, Max, Min, F
from django.utils import timezone
from datetime import timedelta, datetime
from typing import List, Dict, Any, Optional, Tuple
from apps.attendance.models.audit_log import AttendanceAccessLog, AuditLogRetentionPolicy
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
import logging

logger = logging.getLogger(__name__)


class AuditQueryService:
    """
    Service for querying audit logs with advanced filters.
    """

    @staticmethod
    def get_user_activity(user_id: int, days: int = 30) -> List[AttendanceAccessLog]:
        """
        Get all attendance access by a specific user.

        Args:
            user_id: User ID
            days: Number of days to look back (default: 30)

        Returns:
            List of audit log entries
        """
        since = timezone.now() - timedelta(days=days)
        return AttendanceAccessLog.objects.filter(
            user_id=user_id,
            timestamp__gte=since
        ).select_related('user', 'attendance_record').order_by('-timestamp')

    @staticmethod
    def get_record_access_history(attendance_record_id: int) -> List[AttendanceAccessLog]:
        """
        Get complete access history for a specific attendance record.

        Answers: "Who viewed employee X's attendance?"

        Args:
            attendance_record_id: Attendance record ID

        Returns:
            List of audit log entries showing all access
        """
        return AttendanceAccessLog.objects.filter(
            attendance_record_id=attendance_record_id
        ).select_related('user').order_by('-timestamp')

    @staticmethod
    def get_failed_access_attempts(hours: int = 24) -> List[AttendanceAccessLog]:
        """
        Get all failed access attempts in the specified time window.

        Args:
            hours: Number of hours to look back

        Returns:
            List of failed access attempts
        """
        since = timezone.now() - timedelta(hours=hours)
        return AttendanceAccessLog.objects.filter(
            timestamp__gte=since,
            status_code__gte=400
        ).select_related('user').order_by('-timestamp')

    @staticmethod
    def search_logs(
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        status_code: Optional[int] = None,
        is_suspicious: Optional[bool] = None,
        tenant: Optional[str] = None,
    ) -> List[AttendanceAccessLog]:
        """
        Search audit logs with multiple filters.

        Args:
            user_id: Filter by user
            action: Filter by action type
            start_date: Start of date range
            end_date: End of date range
            ip_address: Filter by IP address
            status_code: Filter by HTTP status code
            is_suspicious: Filter suspicious activity
            tenant: Filter by tenant

        Returns:
            Filtered audit logs
        """
        queryset = AttendanceAccessLog.objects.all()

        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if action:
            queryset = queryset.filter(action=action)
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        if status_code:
            queryset = queryset.filter(status_code=status_code)
        if is_suspicious is not None:
            queryset = queryset.filter(is_suspicious=is_suspicious)
        if tenant:
            queryset = queryset.filter(tenant=tenant)

        return queryset.select_related('user', 'attendance_record').order_by('-timestamp')


class AuditAnalyticsService:
    """
    Service for analyzing audit logs and generating insights.
    """

    @staticmethod
    def get_access_statistics(days: int = 30) -> Dict[str, Any]:
        """
        Get access statistics for the specified period.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with statistics
        """
        since = timezone.now() - timedelta(days=days)
        logs = AttendanceAccessLog.objects.filter(timestamp__gte=since)

        return {
            'total_accesses': logs.count(),
            'unique_users': logs.values('user').distinct().count(),
            'by_action': dict(logs.values('action').annotate(count=Count('id')).values_list('action', 'count')),
            'failed_accesses': logs.filter(status_code__gte=400).count(),
            'suspicious_accesses': logs.filter(is_suspicious=True).count(),
            'avg_duration_ms': logs.aggregate(avg=Avg('duration_ms'))['avg'],
            'peak_access_time': AuditAnalyticsService._get_peak_hour(logs),
        }

    @staticmethod
    def _get_peak_hour(queryset) -> Optional[int]:
        """Get hour of day with most accesses"""
        from django.db.models.functions import ExtractHour

        result = (
            queryset
            .annotate(hour=ExtractHour('timestamp'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('-count')
            .first()
        )
        return result['hour'] if result else None

    @staticmethod
    def detect_anomalies(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        Detect anomalous access patterns for a user.

        Detects:
        - Access at unusual times
        - Access from unusual locations (IPs)
        - Unusual volume of accesses
        - Unusual actions

        Args:
            user_id: User ID to analyze
            days: Number of days to analyze

        Returns:
            List of detected anomalies
        """
        since = timezone.now() - timedelta(days=days)
        logs = AttendanceAccessLog.objects.filter(
            user_id=user_id,
            timestamp__gte=since
        )

        anomalies = []

        # Detect unusual time access (outside 6 AM - 10 PM)
        night_accesses = logs.filter(
            Q(timestamp__hour__lt=6) | Q(timestamp__hour__gt=22)
        ).count()
        if night_accesses > 0:
            anomalies.append({
                'type': 'unusual_time',
                'count': night_accesses,
                'severity': 'medium' if night_accesses < 10 else 'high',
                'description': f'{night_accesses} accesses outside normal hours (6 AM - 10 PM)',
            })

        # Detect access from multiple IPs
        unique_ips = logs.values('ip_address').distinct().count()
        if unique_ips > 5:
            anomalies.append({
                'type': 'multiple_locations',
                'count': unique_ips,
                'severity': 'low' if unique_ips < 10 else 'medium',
                'description': f'Access from {unique_ips} different IP addresses',
            })

        # Detect high volume
        avg_per_day = logs.count() / days
        if avg_per_day > 100:
            anomalies.append({
                'type': 'high_volume',
                'count': logs.count(),
                'severity': 'medium',
                'description': f'High access volume: {avg_per_day:.0f} accesses per day',
            })

        # Detect bulk exports
        export_count = logs.filter(action=AttendanceAccessLog.Action.EXPORT).count()
        if export_count > 10:
            anomalies.append({
                'type': 'bulk_export',
                'count': export_count,
                'severity': 'high',
                'description': f'{export_count} data export operations',
            })

        return anomalies

    @staticmethod
    def get_most_accessed_records(days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most frequently accessed attendance records.

        Args:
            days: Number of days to analyze
            limit: Number of records to return

        Returns:
            List of most accessed records with access counts
        """
        since = timezone.now() - timedelta(days=days)

        most_accessed = (
            AttendanceAccessLog.objects
            .filter(
                timestamp__gte=since,
                attendance_record__isnull=False
            )
            .values('attendance_record_id', 'attendance_record__people__username')
            .annotate(access_count=Count('id'))
            .order_by('-access_count')[:limit]
        )

        return list(most_accessed)

    @staticmethod
    def get_user_access_patterns(user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Analyze access patterns for a specific user.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dictionary with access pattern analysis
        """
        since = timezone.now() - timedelta(days=days)
        logs = AttendanceAccessLog.objects.filter(
            user_id=user_id,
            timestamp__gte=since
        )

        from django.db.models.functions import ExtractHour, ExtractWeekDay

        # Access by hour of day
        by_hour = dict(
            logs
            .annotate(hour=ExtractHour('timestamp'))
            .values('hour')
            .annotate(count=Count('id'))
            .values_list('hour', 'count')
        )

        # Access by day of week
        by_weekday = dict(
            logs
            .annotate(weekday=ExtractWeekDay('timestamp'))
            .values('weekday')
            .annotate(count=Count('id'))
            .values_list('weekday', 'count')
        )

        # Most common IPs
        common_ips = list(
            logs
            .values('ip_address')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        # Most common actions
        common_actions = dict(
            logs
            .values('action')
            .annotate(count=Count('id'))
            .values_list('action', 'count')
        )

        return {
            'total_accesses': logs.count(),
            'by_hour': by_hour,
            'by_weekday': by_weekday,
            'common_ips': common_ips,
            'common_actions': common_actions,
            'first_access': logs.aggregate(first=Min('timestamp'))['first'],
            'last_access': logs.aggregate(last=Max('timestamp'))['last'],
            'avg_duration_ms': logs.aggregate(avg=Avg('duration_ms'))['avg'],
        }


class AuditReportService:
    """
    Service for generating compliance audit reports.
    """

    @staticmethod
    def generate_compliance_report(
        start_date: datetime,
        end_date: datetime,
        tenant: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive compliance audit report.

        For SOC 2 / ISO 27001 audits.

        Args:
            start_date: Report start date
            end_date: Report end date
            tenant: Optional tenant filter

        Returns:
            Compliance report with all required metrics
        """
        queryset = AttendanceAccessLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date
        )

        if tenant:
            queryset = queryset.filter(tenant=tenant)

        report = {
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days,
            },
            'access_summary': {
                'total_accesses': queryset.count(),
                'unique_users': queryset.values('user').distinct().count(),
                'unique_records': queryset.filter(attendance_record__isnull=False).values('attendance_record').distinct().count(),
            },
            'by_action': dict(
                queryset.values('action').annotate(count=Count('id')).values_list('action', 'count')
            ),
            'by_resource_type': dict(
                queryset.values('resource_type').annotate(count=Count('id')).values_list('resource_type', 'count')
            ),
            'security_events': {
                'failed_accesses': queryset.filter(status_code__gte=400).count(),
                'unauthorized_attempts': queryset.filter(status_code__in=[401, 403]).count(),
                'suspicious_activity': queryset.filter(is_suspicious=True).count(),
                'high_risk_accesses': queryset.filter(risk_score__gte=70).count(),
            },
            'performance_metrics': {
                'avg_response_time_ms': queryset.aggregate(avg=Avg('duration_ms'))['avg'],
                'max_response_time_ms': queryset.aggregate(max=Max('duration_ms'))['max'],
                'slow_operations': queryset.filter(duration_ms__gte=1000).count(),
            },
            'audit_coverage': {
                'logged_operations': queryset.count(),
                'audit_log_retention_days': AuditReportService._get_retention_days(),
                'data_completeness': AuditReportService._check_data_completeness(queryset),
            },
        }

        return report

    @staticmethod
    def _get_retention_days() -> int:
        """Get configured audit log retention period"""
        try:
            policy = AuditLogRetentionPolicy.objects.filter(is_active=True).first()
            return policy.retention_days if policy else 2190  # Default: 6 years
        except DATABASE_EXCEPTIONS:
            return 2190

    @staticmethod
    def _check_data_completeness(queryset) -> Dict[str, Any]:
        """Check for missing or incomplete audit data"""
        total = queryset.count()

        return {
            'total_records': total,
            'missing_user': queryset.filter(user__isnull=True).count(),
            'missing_ip': queryset.filter(ip_address__isnull=True).count(),
            'missing_duration': queryset.filter(duration_ms__isnull=True).count(),
            'completeness_percentage': (
                (total - queryset.filter(
                    Q(user__isnull=True) |
                    Q(ip_address__isnull=True)
                ).count()) / total * 100 if total > 0 else 0
            ),
        }

    @staticmethod
    def export_to_csv(queryset, filename: str) -> str:
        """
        Export audit logs to CSV format.

        Args:
            queryset: Audit logs queryset
            filename: Output filename

        Returns:
            Path to generated CSV file
        """
        import csv
        from django.utils.timezone import localtime

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow([
                'Timestamp',
                'User',
                'Action',
                'Resource Type',
                'Record ID',
                'IP Address',
                'Status Code',
                'Duration (ms)',
                'Suspicious',
                'Risk Score',
            ])

            # Data rows
            for log in queryset.iterator(chunk_size=1000):
                writer.writerow([
                    localtime(log.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                    log.user.username if log.user else 'Anonymous',
                    log.get_action_display(),
                    log.get_resource_type_display(),
                    log.attendance_record_id or '',
                    log.ip_address or '',
                    log.status_code or '',
                    log.duration_ms or '',
                    'Yes' if log.is_suspicious else 'No',
                    log.risk_score,
                ])

        logger.info(f"Exported {queryset.count()} audit logs to {filename}")
        return filename


class AuditInvestigationService:
    """
    Service for security investigations and incident response.
    """

    @staticmethod
    def investigate_user(user_id: int, days: int = 90) -> Dict[str, Any]:
        """
        Comprehensive investigation of a user's access.

        Used for security incidents or compliance audits.

        Args:
            user_id: User ID to investigate
            days: Number of days to investigate

        Returns:
            Complete investigation report
        """
        since = timezone.now() - timedelta(days=days)
        logs = AttendanceAccessLog.objects.filter(
            user_id=user_id,
            timestamp__gte=since
        )

        return {
            'user_id': user_id,
            'investigation_period': {
                'start': since.isoformat(),
                'end': timezone.now().isoformat(),
                'days': days,
            },
            'activity_summary': {
                'total_accesses': logs.count(),
                'first_access': logs.aggregate(first=Min('timestamp'))['first'],
                'last_access': logs.aggregate(last=Max('timestamp'))['last'],
                'unique_records_accessed': logs.filter(attendance_record__isnull=False).values('attendance_record').distinct().count(),
            },
            'actions_performed': dict(
                logs.values('action').annotate(count=Count('id')).values_list('action', 'count')
            ),
            'access_locations': list(
                logs.values('ip_address').annotate(count=Count('id')).order_by('-count')
            ),
            'failed_attempts': logs.filter(status_code__gte=400).count(),
            'suspicious_activity': logs.filter(is_suspicious=True).count(),
            'anomalies': AuditAnalyticsService.detect_anomalies(user_id, days),
            'access_patterns': AuditAnalyticsService.get_user_access_patterns(user_id, days),
            'risk_assessment': AuditInvestigationService._assess_risk(logs),
        }

    @staticmethod
    def _assess_risk(queryset) -> Dict[str, Any]:
        """Assess risk level based on access patterns"""
        total = queryset.count()
        suspicious = queryset.filter(is_suspicious=True).count()
        failed = queryset.filter(status_code__gte=400).count()
        exports = queryset.filter(action=AttendanceAccessLog.Action.EXPORT).count()

        # Calculate risk score
        risk_score = 0
        risk_factors = []

        if suspicious > 0:
            risk_score += min(suspicious * 5, 40)
            risk_factors.append(f'{suspicious} suspicious activities')

        if failed > total * 0.1:  # >10% failure rate
            risk_score += 20
            risk_factors.append(f'High failure rate ({failed}/{total})')

        if exports > 10:
            risk_score += 30
            risk_factors.append(f'{exports} data exports')

        # Determine risk level
        if risk_score >= 70:
            risk_level = 'HIGH'
        elif risk_score >= 40:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'

        return {
            'risk_score': min(risk_score, 100),
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'recommendation': AuditInvestigationService._get_recommendation(risk_level),
        }

    @staticmethod
    def _get_recommendation(risk_level: str) -> str:
        """Get investigation recommendation based on risk level"""
        recommendations = {
            'HIGH': 'Immediate investigation recommended. Review all access logs and consider account suspension.',
            'MEDIUM': 'Further monitoring recommended. Review suspicious activities and verify legitimacy.',
            'LOW': 'Normal activity. Continue routine monitoring.',
        }
        return recommendations.get(risk_level, 'No recommendation available')

    @staticmethod
    def trace_data_access(attendance_record_id: int) -> Dict[str, Any]:
        """
        Trace all access to a specific attendance record.

        Answers: "Who accessed this record and when?"

        Args:
            attendance_record_id: Attendance record ID

        Returns:
            Complete access history and analysis
        """
        logs = AttendanceAccessLog.objects.filter(
            attendance_record_id=attendance_record_id
        ).select_related('user')

        return {
            'record_id': attendance_record_id,
            'total_accesses': logs.count(),
            'unique_users': logs.values('user').distinct().count(),
            'first_access': logs.aggregate(first=Min('timestamp'))['first'],
            'last_access': logs.aggregate(last=Max('timestamp'))['last'],
            'access_timeline': list(
                logs.values(
                    'timestamp', 'user__username', 'action',
                    'ip_address', 'status_code'
                ).order_by('timestamp')
            ),
            'by_action': dict(
                logs.values('action').annotate(count=Count('id')).values_list('action', 'count')
            ),
            'by_user': list(
                logs.values('user__username').annotate(count=Count('id')).order_by('-count')
            ),
            'modifications': list(
                logs.filter(action__in=[
                    AttendanceAccessLog.Action.UPDATE,
                    AttendanceAccessLog.Action.DELETE,
                    AttendanceAccessLog.Action.APPROVE,
                    AttendanceAccessLog.Action.REJECT,
                ]).values(
                    'timestamp', 'user__username', 'action',
                    'old_values', 'new_values'
                ).order_by('timestamp')
            ),
        }
