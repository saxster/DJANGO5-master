"""
Team Daily Metrics Model

Stores team/site-level aggregated metrics.
Rolled up from WorkerDailyMetrics.

Compliance:
- Rule #6: Model < 150 lines
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import TenantAwareModel, BaseModel


class TeamDailyMetrics(TenantAwareModel, BaseModel):
    """
    Team/site-level daily metrics.
    
    Aggregated from WorkerDailyMetrics for:
    - Site-level reporting
    - Shift comparison
    - Multi-site benchmarking
    """
    
    # Dimensions
    date = models.DateField(db_index=True)
    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='team_metrics'
    )
    shift_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="Shift type (day, night, evening) or null for all shifts"
    )
    
    # Team Size
    active_workers = models.IntegerField(default=0)
    scheduled_workers = models.IntegerField(default=0)
    
    # Hours
    total_worked_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_scheduled_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_overtime_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Team BPI
    team_bpi_avg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    team_bpi_median = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    team_bpi_std_dev = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    
    # Performance Distribution
    workers_exceptional = models.IntegerField(default=0, help_text="BPI 90+")
    workers_strong = models.IntegerField(default=0, help_text="BPI 75-89")
    workers_solid = models.IntegerField(default=0, help_text="BPI 60-74")
    workers_developing = models.IntegerField(default=0, help_text="BPI 40-59")
    workers_needs_support = models.IntegerField(default=0, help_text="BPI <40")
    
    # Key Metrics (Averages)
    on_time_rate_avg = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sla_hit_rate_avg = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    patrol_coverage_avg = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    task_completion_rate_avg = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quality_score_avg = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Operational KPIs
    coverage_gap_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="Unfilled shift hours"
    )
    total_ncns_incidents = models.IntegerField(default=0)
    total_late_incidents = models.IntegerField(default=0)
    total_geofence_violations = models.IntegerField(default=0)
    
    # Task/Work Metrics
    total_tasks_completed = models.IntegerField(default=0)
    total_tours_completed = models.IntegerField(default=0)
    total_work_orders_completed = models.IntegerField(default=0)
    
    # Incidents
    incident_rate_per_100h = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0,
        help_text="Safety incidents per 100 worked hours"
    )
    incidents_total = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'perf_team_daily_metrics'
        verbose_name = 'Team Daily Metrics'
        verbose_name_plural = 'Team Daily Metrics'
        unique_together = [['tenant', 'date', 'site', 'shift_type']]
        indexes = [
            models.Index(fields=['tenant', 'date', 'site']),
            models.Index(fields=['tenant', 'date', 'shift_type']),
            models.Index(fields=['tenant', 'team_bpi_avg']),
        ]
        ordering = ['-date', 'site']
    
    def __str__(self):
        shift_desc = f" ({self.shift_type})" if self.shift_type else ""
        return f"{self.site.abbr} - {self.date}{shift_desc} - Team BPI: {self.team_bpi_avg}"
    
    def get_performance_distribution(self):
        """Get performance band distribution as percentages."""
        total = self.active_workers
        if total == 0:
            return {}
        
        return {
            'exceptional': round((self.workers_exceptional / total) * 100, 1),
            'strong': round((self.workers_strong / total) * 100, 1),
            'solid': round((self.workers_solid / total) * 100, 1),
            'developing': round((self.workers_developing / total) * 100, 1),
            'needs_support': round((self.workers_needs_support / total) * 100, 1),
        }
