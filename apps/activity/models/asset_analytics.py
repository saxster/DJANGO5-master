"""
Asset Analytics Models (Sprint 4.5)

Models for tracking asset utilization, performance, and maintenance metrics:
- AssetUtilizationMetric: Daily utilization tracking
- MaintenanceCostTracking: Maintenance cost history
- AssetHealthScore: Calculated health scores

Enables analytics dashboard and predictive maintenance.

Author: Development Team
Date: October 2025
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class AssetUtilizationMetric(BaseModel, TenantAwareModel):
    """
    Daily asset utilization metrics.

    Tracks asset uptime, downtime, and utilization percentage.
    """

    asset = models.ForeignKey(
        'activity.Asset',
        verbose_name=_("Asset"),
        on_delete=models.CASCADE,
        related_name='utilization_metrics'
    )

    date = models.DateField(
        _("Date"),
        help_text="Date of measurement"
    )

    utilization_percentage = models.DecimalField(
        _("Utilization %"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of time asset was in use (0-100%)"
    )

    uptime_hours = models.DecimalField(
        _("Uptime Hours"),
        max_digits=6,
        decimal_places=2,
        default=0.0,
        help_text="Total operational hours"
    )

    downtime_hours = models.DecimalField(
        _("Downtime Hours"),
        max_digits=6,
        decimal_places=2,
        default=0.0,
        help_text="Total downtime hours (maintenance, repairs, etc.)"
    )

    idle_hours = models.DecimalField(
        _("Idle Hours"),
        max_digits=6,
        decimal_places=2,
        default=0.0,
        help_text="Hours asset was available but not in use"
    )

    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text="Additional utilization metadata"
    )

    class Meta:
        db_table = 'activity_asset_utilization'
        verbose_name = _("Asset Utilization Metric")
        verbose_name_plural = _("Asset Utilization Metrics")
        unique_together = [('tenant', 'asset', 'date')]
        indexes = [
            models.Index(fields=['tenant', 'asset', 'date']),
            models.Index(fields=['tenant', 'date']),
            models.Index(fields=['utilization_percentage']),
        ]
        ordering = ['-date']

    def __str__(self):
        return f"{self.asset.assetcode} - {self.date}: {self.utilization_percentage}%"


class MaintenanceCostTracking(BaseModel, TenantAwareModel):
    """
    Maintenance cost tracking for assets.

    Records all maintenance costs with categorization for analytics.
    """

    class CostType(models.TextChoices):
        """Types of maintenance costs."""
        REPAIR = ("REPAIR", "Repair")
        INSPECTION = ("INSPECTION", "Inspection")
        REPLACEMENT = ("REPLACEMENT", "Replacement")
        PREVENTIVE = ("PREVENTIVE", "Preventive Maintenance")
        EMERGENCY = ("EMERGENCY", "Emergency Repair")

    asset = models.ForeignKey(
        'activity.Asset',
        verbose_name=_("Asset"),
        on_delete=models.CASCADE,
        related_name='maintenance_costs'
    )

    maintenance_date = models.DateField(
        _("Maintenance Date"),
        help_text="Date maintenance was performed"
    )

    cost = models.DecimalField(
        _("Cost"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Maintenance cost in local currency"
    )

    cost_type = models.CharField(
        _("Cost Type"),
        max_length=20,
        choices=CostType.choices
    )

    description = models.TextField(
        _("Description"),
        help_text="Description of maintenance work performed"
    )

    performed_by = models.ForeignKey(
        'peoples.People',
        verbose_name=_("Performed By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_work'
    )

    vendor_name = models.CharField(
        _("Vendor Name"),
        max_length=200,
        blank=True,
        help_text="External vendor if applicable"
    )

    invoice_number = models.CharField(
        _("Invoice Number"),
        max_length=100,
        blank=True
    )

    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text="Additional cost metadata (parts used, labor hours, etc.)"
    )

    class Meta:
        db_table = 'activity_maintenance_cost'
        verbose_name = _("Maintenance Cost")
        verbose_name_plural = _("Maintenance Costs")
        indexes = [
            models.Index(fields=['tenant', 'asset', 'maintenance_date']),
            models.Index(fields=['tenant', 'cost_type', 'maintenance_date']),
            models.Index(fields=['maintenance_date']),
        ]
        ordering = ['-maintenance_date']

    def __str__(self):
        return f"{self.asset.assetcode} - {self.cost_type}: {self.cost}"


class AssetHealthScore(BaseModel, TenantAwareModel):
    """
    Asset health score tracking.

    Calculated health scores based on utilization, maintenance, age, and failures.
    """

    asset = models.ForeignKey(
        'activity.Asset',
        verbose_name=_("Asset"),
        on_delete=models.CASCADE,
        related_name='health_scores'
    )

    calculated_date = models.DateField(
        _("Calculated Date"),
        help_text="Date score was calculated"
    )

    health_score = models.DecimalField(
        _("Health Score"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall health score (0-100, higher is better)"
    )

    risk_level = models.CharField(
        _("Risk Level"),
        max_length=20,
        choices=[
            ('LOW', 'Low Risk'),
            ('MEDIUM', 'Medium Risk'),
            ('HIGH', 'High Risk'),
            ('CRITICAL', 'Critical Risk')
        ],
        help_text="Risk level based on health score"
    )

    predicted_failure_date = models.DateField(
        _("Predicted Failure Date"),
        null=True,
        blank=True,
        help_text="ML-predicted next failure date"
    )

    recommended_maintenance_date = models.DateField(
        _("Recommended Maintenance Date"),
        null=True,
        blank=True,
        help_text="Recommended next maintenance date"
    )

    factors = models.JSONField(
        _("Health Factors"),
        default=dict,
        help_text="Contributing factors to health score"
    )

    class Meta:
        db_table = 'activity_asset_health_score'
        verbose_name = _("Asset Health Score")
        verbose_name_plural = _("Asset Health Scores")
        unique_together = [('tenant', 'asset', 'calculated_date')]
        indexes = [
            models.Index(fields=['tenant', 'asset', 'calculated_date']),
            models.Index(fields=['tenant', 'risk_level']),
            models.Index(fields=['health_score']),
        ]
        ordering = ['-calculated_date']

    def __str__(self):
        return f"{self.asset.assetcode} - {self.calculated_date}: {self.health_score} ({self.risk_level})"
