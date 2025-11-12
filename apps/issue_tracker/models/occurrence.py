"""
AnomalyOccurrence Model
Individual occurrence of an anomaly with client version tracking
"""

import uuid
from django.db import models
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.utils import timezone

from .enums import OCCURRENCE_STATUS_CHOICES
from .signature import AnomalySignature

User = get_user_model()


class AnomalyOccurrence(models.Model):
    """
    Individual occurrence of an anomaly
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signature = models.ForeignKey(
        AnomalySignature,
        on_delete=models.CASCADE,
        related_name='occurrences'
    )

    # Reference to stream event
    test_run_id = models.UUIDField(null=True, blank=True)
    event_ref = models.UUIDField(null=True, blank=True)

    # Occurrence details
    created_at = models.DateTimeField(auto_now_add=True)
    endpoint = models.CharField(max_length=200)
    error_message = models.TextField(blank=True)
    exception_class = models.CharField(max_length=100, blank=True)
    stack_hash = models.CharField(max_length=64, blank=True)

    # Context information
    http_status_code = models.IntegerField(null=True, blank=True)
    latency_ms = models.FloatField(null=True, blank=True)
    payload_sanitized = models.JSONField(
        null=True,
        blank=True,
        help_text="Sanitized payload data"
    )

    # Resolution tracking
    status = models.CharField(
        max_length=20,
        choices=OCCURRENCE_STATUS_CHOICES,
        default='new'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_anomalies'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_anomalies'
    )
    resolution_notes = models.TextField(blank=True)

    # Additional metadata
    environment = models.CharField(max_length=50, default='production')
    correlation_id = models.UUIDField(null=True, blank=True)

    # Client version tracking for trend analysis
    client_app_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Client application version (e.g., 1.2.3)"
    )
    client_os_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Client OS version (e.g., Android 13, iOS 16.1)"
    )
    client_device_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Client device model (e.g., iPhone 14, Samsung Galaxy S23)"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['signature', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['correlation_id']),
            # Client version tracking indexes for trend analysis
            models.Index(fields=['client_app_version', 'created_at']),
            models.Index(fields=['client_os_version', 'created_at']),
            models.Index(fields=['signature', 'client_app_version']),
        ]

    def __str__(self):
        return f"Occurrence {self.id} - {self.signature.anomaly_type}"

    def mark_resolved(self, user: User, notes: str = ''):
        """Mark occurrence as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.resolution_notes = notes
        self.save()

        # Update signature MTTR
        self.signature.calculate_mttr()

    @property
    def resolution_time_seconds(self):
        """Get resolution time in seconds"""
        if self.resolved_at and self.created_at:
            return (self.resolved_at - self.created_at).total_seconds()
        return None

    @property
    def client_version_info(self):
        """Get structured client version information"""
        return {
            'app_version': self.client_app_version or 'unknown',
            'os_version': self.client_os_version or 'unknown',
            'device_model': self.client_device_model or 'unknown'
        }

    @classmethod
    def version_trend_analysis(cls, signature_id=None, days=30):
        """
        Analyze anomaly trends by client version

        Args:
            signature_id: Optional signature to filter by
            days: Number of days to analyze (default 30)

        Returns:
            Dict with trend analysis by app version, OS version, and device
        """
        from datetime import timedelta

        since_date = timezone.now() - timedelta(days=days)
        queryset = cls.objects.filter(created_at__gte=since_date)

        if signature_id:
            queryset = queryset.filter(signature_id=signature_id)

        # Analyze by app version
        app_version_trends = dict(
            queryset.exclude(client_app_version='')
            .values('client_app_version')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values_list('client_app_version', 'count')
        )

        # Analyze by OS version
        os_version_trends = dict(
            queryset.exclude(client_os_version='')
            .values('client_os_version')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values_list('client_os_version', 'count')
        )

        # Analyze by device model
        device_trends = dict(
            queryset.exclude(client_device_model='')
            .values('client_device_model')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]  # Top 10 devices
            .values_list('client_device_model', 'count')
        )

        # Version regression analysis
        version_regression = []
        for app_version, count in app_version_trends.items():
            # Compare with previous period
            previous_period = timezone.now() - timedelta(days=days*2)
            previous_count = cls.objects.filter(
                created_at__gte=previous_period,
                created_at__lt=since_date,
                client_app_version=app_version
            ).count()

            change = count - previous_count
            change_pct = (change / previous_count * 100) if previous_count > 0 else 100

            version_regression.append({
                'version': app_version,
                'current_count': count,
                'previous_count': previous_count,
                'change': change,
                'change_percent': round(change_pct, 1)
            })

        return {
            'app_version_trends': app_version_trends,
            'os_version_trends': os_version_trends,
            'device_trends': device_trends,
            'version_regression_analysis': sorted(
                version_regression,
                key=lambda x: x['change_percent'],
                reverse=True
            )
        }
