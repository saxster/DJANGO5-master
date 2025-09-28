"""
Issue Tracker Knowledge Base Models
Anomaly detection, fix suggestions, and recurrence tracking
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class AnomalySignature(models.Model):
    """
    Unique fingerprint of an anomaly pattern for tracking recurrences
    """
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical')
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
        ('monitoring', 'Monitoring')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Unique signature hash
    signature_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 hash of anomaly signature"
    )

    # Anomaly classification
    anomaly_type = models.CharField(
        max_length=50,
        help_text="Type of anomaly (latency, error, schema, etc.)"
    )
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Pattern definition
    pattern = models.JSONField(
        help_text="Pattern definition for anomaly detection"
    )

    # Signature metadata
    endpoint_pattern = models.CharField(max_length=200)
    error_class = models.CharField(max_length=100, blank=True)
    schema_signature = models.TextField(blank=True)

    # Tracking metrics
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    occurrence_count = models.IntegerField(default=1)

    # Resolution tracking
    mttr_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Mean Time To Resolution in seconds"
    )
    mtbf_hours = models.FloatField(
        null=True,
        blank=True,
        help_text="Mean Time Between Failures in hours"
    )

    # Tags for categorization
    tags = models.JSONField(
        default=list,
        help_text="Tags for categorization and search"
    )

    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['signature_hash']),
            models.Index(fields=['anomaly_type', 'severity']),
            models.Index(fields=['status', 'last_seen']),
            models.Index(fields=['endpoint_pattern']),
        ]

    def __str__(self):
        return f"{self.anomaly_type} - {self.endpoint_pattern}"

    @property
    def is_recurring(self):
        """Check if this is a recurring issue"""
        return self.occurrence_count > 3

    @property
    def severity_score(self):
        """Get numeric severity score for prioritization"""
        scores = {'info': 1, 'warning': 2, 'error': 3, 'critical': 4}
        return scores.get(self.severity, 1)

    def update_occurrence(self):
        """Update occurrence tracking"""
        self.occurrence_count += 1
        self.last_seen = timezone.now()
        self.save()

    def calculate_mttr(self):
        """Calculate MTTR from resolved occurrences"""
        resolved_occurrences = self.occurrences.filter(
            status='resolved',
            resolved_at__isnull=False
        )

        if not resolved_occurrences.exists():
            return None

        total_resolution_time = 0
        count = 0

        for occurrence in resolved_occurrences:
            if occurrence.created_at and occurrence.resolved_at:
                resolution_time = (
                    occurrence.resolved_at - occurrence.created_at
                ).total_seconds()
                total_resolution_time += resolution_time
                count += 1

        if count > 0:
            self.mttr_seconds = int(total_resolution_time / count)
            self.save()

        return self.mttr_seconds


class AnomalyOccurrence(models.Model):
    """
    Individual occurrence of an anomaly
    """
    STATUS_CHOICES = [
        ('new', 'New'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive')
    ]

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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
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
        from django.utils import timezone
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


class FixSuggestion(models.Model):
    """
    AI/rule-based fix suggestions for anomaly signatures
    """
    FIX_TYPES = [
        ('index', 'Database Index'),
        ('serializer', 'Serializer Update'),
        ('rate_limit', 'Rate Limiting'),
        ('connection_pool', 'Connection Pool'),
        ('caching', 'Caching Strategy'),
        ('retry_policy', 'Retry Policy'),
        ('schema_update', 'Schema Update'),
        ('configuration', 'Configuration Change'),
        ('code_fix', 'Code Fix'),
        ('infrastructure', 'Infrastructure Change')
    ]

    STATUS_CHOICES = [
        ('suggested', 'Suggested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('applied', 'Applied'),
        ('verified', 'Verified')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signature = models.ForeignKey(
        AnomalySignature,
        on_delete=models.CASCADE,
        related_name='fix_suggestions'
    )

    # Suggestion metadata
    title = models.CharField(max_length=200)
    description = models.TextField()
    fix_type = models.CharField(max_length=30, choices=FIX_TYPES)

    # Confidence and priority
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score from 0.0 to 1.0"
    )
    priority_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Priority score from 1 (low) to 10 (high)"
    )

    # Implementation details
    patch_template = models.TextField(
        blank=True,
        help_text="Code or configuration patch template"
    )
    implementation_steps = models.JSONField(
        default=list,
        help_text="Step-by-step implementation guide"
    )

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='suggested')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(
        max_length=100,
        default='ai_assistant',
        help_text="Source of suggestion (ai_assistant, rule_engine, user)"
    )

    # Application tracking
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_fixes'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Auto-applicability
    auto_applicable = models.BooleanField(
        default=False,
        help_text="Can this fix be applied automatically?"
    )
    risk_level = models.CharField(
        max_length=20,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        default='medium'
    )

    class Meta:
        ordering = ['-priority_score', '-confidence', '-created_at']
        indexes = [
            models.Index(fields=['signature', 'status']),
            models.Index(fields=['fix_type', 'confidence']),
            models.Index(fields=['auto_applicable', 'risk_level']),
        ]

    def __str__(self):
        return f"{self.title} ({self.fix_type})"

    @property
    def effectiveness_score(self):
        """Calculate effectiveness score based on confidence and priority"""
        return (self.confidence * 0.7) + (self.priority_score / 10 * 0.3)

    def approve(self, user: User):
        """Approve fix suggestion"""
        self.status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()

    def reject(self, reason: str = ''):
        """Reject fix suggestion"""
        self.status = 'rejected'
        if reason:
            self.description += f"\n\nRejection reason: {reason}"
        self.save()


class FixAction(models.Model):
    """
    Track application of fix suggestions
    """
    ACTION_TYPES = [
        ('applied', 'Applied'),
        ('tested', 'Tested'),
        ('rolled_back', 'Rolled Back'),
        ('verified', 'Verified')
    ]

    RESULT_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.ForeignKey(
        AnomalyOccurrence,
        on_delete=models.CASCADE,
        related_name='fix_actions'
    )
    suggestion = models.ForeignKey(
        FixSuggestion,
        on_delete=models.CASCADE,
        related_name='actions'
    )

    # Action details
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.ForeignKey(User, on_delete=models.CASCADE)

    # Implementation details
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    # Code/infrastructure changes
    commit_sha = models.CharField(max_length=40, blank=True)
    pr_link = models.URLField(blank=True)
    deployment_id = models.CharField(max_length=100, blank=True)

    # Verification
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-applied_at']
        indexes = [
            models.Index(fields=['occurrence', 'action_type']),
            models.Index(fields=['suggestion', 'result']),
            models.Index(fields=['applied_at']),
        ]

    def __str__(self):
        return f"{self.action_type} - {self.suggestion.title}"

    def mark_verified(self, notes: str = ''):
        """Mark action as verified"""
        self.result = 'success'
        self.verified_at = timezone.now()
        self.verification_notes = notes
        self.save()

        # Update suggestion status
        if self.suggestion.status != 'verified':
            self.suggestion.status = 'verified'
            self.suggestion.save()


class RecurrenceTracker(models.Model):
    """
    Track issue recurrence patterns and resolution effectiveness
    """
    signature = models.OneToOneField(
        AnomalySignature,
        on_delete=models.CASCADE,
        related_name='recurrence_tracker'
    )

    # Recurrence patterns
    last_occurrence_at = models.DateTimeField(null=True, blank=True)
    recurrence_count = models.IntegerField(default=0)
    days_since_last_fix = models.IntegerField(null=True, blank=True)

    # Pattern analysis
    typical_interval_hours = models.FloatField(null=True, blank=True)
    severity_trend = models.CharField(
        max_length=20,
        choices=[
            ('improving', 'Improving'),
            ('stable', 'Stable'),
            ('worsening', 'Worsening')
        ],
        null=True,
        blank=True
    )

    # Fix effectiveness
    fixes_attempted = models.IntegerField(default=0)
    successful_fixes = models.IntegerField(default=0)
    fix_success_rate = models.FloatField(null=True, blank=True)

    # Alerting
    requires_attention = models.BooleanField(default=False)
    alert_threshold_exceeded = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['requires_attention']),
            models.Index(fields=['alert_threshold_exceeded']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"Recurrence tracking for {self.signature}"

    def update_recurrence(self):
        """Update recurrence tracking metrics"""
        occurrences = self.signature.occurrences.order_by('-created_at')

        if occurrences.count() > 1:
            # Calculate typical interval
            intervals = []
            for i in range(min(5, occurrences.count() - 1)):
                interval = (
                    occurrences[i].created_at - occurrences[i + 1].created_at
                ).total_seconds() / 3600  # Convert to hours
                intervals.append(interval)

            if intervals:
                self.typical_interval_hours = sum(intervals) / len(intervals)

        # Update recurrence count
        self.recurrence_count = occurrences.count()
        self.last_occurrence_at = occurrences.first().created_at if occurrences else None

        # Analyze severity trend
        recent_occurrences = occurrences[:5]  # Last 5 occurrences
        if len(recent_occurrences) >= 3:
            severity_scores = [
                self.signature.severity_score for _ in recent_occurrences
            ]
            if severity_scores[-1] > severity_scores[0]:
                self.severity_trend = 'worsening'
            elif severity_scores[-1] < severity_scores[0]:
                self.severity_trend = 'improving'
            else:
                self.severity_trend = 'stable'

        # Update fix effectiveness
        fix_actions = FixAction.objects.filter(
            occurrence__signature=self.signature
        )
        self.fixes_attempted = fix_actions.count()
        self.successful_fixes = fix_actions.filter(result='success').count()

        if self.fixes_attempted > 0:
            self.fix_success_rate = self.successful_fixes / self.fixes_attempted

        # Determine if requires attention
        self.requires_attention = (
            self.recurrence_count > 5 or
            self.severity_trend == 'worsening' or
            (self.fix_success_rate or 0) < 0.5
        )

        # Alert threshold
        self.alert_threshold_exceeded = (
            self.recurrence_count > 10 or
            self.signature.severity in ['critical', 'error']
        )

        self.save()