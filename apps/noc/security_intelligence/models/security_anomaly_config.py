"""
Security Anomaly Configuration Model.

Stores configurable thresholds and settings for security anomaly detection.
Allows per-tenant and per-site customization of detection sensitivity.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class SecurityAnomalyConfig(BaseModel, TenantAwareModel):
    """
    Configuration for security anomaly detection thresholds.

    Allows fine-tuning of detection sensitivity per tenant or site.
    """

    SCOPE_CHOICES = [
        ('TENANT', 'Tenant-wide'),
        ('CLIENT', 'Client-specific'),
        ('SITE', 'Site-specific'),
    ]

    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default='TENANT',
        help_text="Scope of this configuration"
    )

    client = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='security_configs_as_client',
        help_text="Client for CLIENT/SITE scope"
    )

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='security_configs_as_site',
        help_text="Site for SITE scope"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this configuration is active"
    )

    # Attendance Anomaly Thresholds
    max_continuous_work_hours = models.IntegerField(
        default=16,
        validators=[MinValueValidator(8), MaxValueValidator(24)],
        help_text="Maximum continuous work hours before overtime alert"
    )

    min_travel_time_minutes = models.IntegerField(
        default=30,
        validators=[MinValueValidator(5)],
        help_text="Minimum travel time between distant sites (minutes)"
    )

    max_travel_speed_kmh = models.IntegerField(
        default=150,
        validators=[MinValueValidator(50), MaxValueValidator(300)],
        help_text="Maximum believable travel speed (km/h)"
    )

    unauthorized_access_severity = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
            ('CRITICAL', 'Critical'),
        ],
        default='CRITICAL',
        help_text="Severity for unauthorized site access"
    )

    # Activity Monitoring Thresholds
    inactivity_detection_enabled = models.BooleanField(
        default=True,
        help_text="Enable night shift inactivity detection"
    )

    inactivity_window_minutes = models.IntegerField(
        default=120,
        validators=[MinValueValidator(30), MaxValueValidator(360)],
        help_text="Time window for inactivity detection (minutes)"
    )

    inactivity_score_threshold = models.FloatField(
        default=0.8,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Inactivity score threshold (0-1)"
    )

    deep_night_hours_start = models.IntegerField(
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Deep night hours start (hour of day)"
    )

    deep_night_hours_end = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Deep night hours end (hour of day)"
    )

    # Fraud Detection Thresholds
    biometric_confidence_min = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Minimum biometric confidence score"
    )

    gps_accuracy_max_meters = models.IntegerField(
        default=100,
        validators=[MinValueValidator(10), MaxValueValidator(1000)],
        help_text="Maximum acceptable GPS accuracy (meters)"
    )

    geofence_violation_threshold_meters = models.IntegerField(
        default=200,
        validators=[MinValueValidator(50), MaxValueValidator(1000)],
        help_text="Distance outside geofence before alert (meters)"
    )

    concurrent_biometric_window_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="Time window for detecting concurrent biometric use"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_security_anomaly_config'
        verbose_name = 'Security Anomaly Config'
        verbose_name_plural = 'Security Anomaly Configs'
        indexes = [
            models.Index(fields=['tenant', 'scope', 'is_active']),
            models.Index(fields=['client', 'is_active']),
            models.Index(fields=['site', 'is_active']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(scope='TENANT') | models.Q(client__isnull=False),
                name='client_required_for_client_scope'
            ),
            models.CheckConstraint(
                check=models.Q(scope__in=['TENANT', 'CLIENT']) | models.Q(site__isnull=False),
                name='site_required_for_site_scope'
            ),
        ]

    def __str__(self):
        return f"{self.get_scope_display()} Config ({self.tenant.name})"

    @classmethod
    def get_config_for_site(cls, tenant, site):
        """
        Get effective configuration for a site (site > client > tenant).

        Args:
            tenant: Tenant instance
            site: Site (Bt) instance

        Returns:
            SecurityAnomalyConfig instance
        """
        config = cls.objects.filter(
            tenant=tenant,
            site=site,
            scope='SITE',
            is_active=True
        ).first()

        if not config and site:
            client = site.get_client_parent()
            if client:
                config = cls.objects.filter(
                    tenant=tenant,
                    client=client,
                    scope='CLIENT',
                    is_active=True
                ).first()

        if not config:
            config = cls.objects.filter(
                tenant=tenant,
                scope='TENANT',
                is_active=True
            ).first()

        return config