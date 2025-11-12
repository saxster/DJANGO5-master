"""
Worker Daily Metrics Model

Stores daily performance snapshot per worker.
Aggregated nightly from attendance, tasks, tours, work orders.

Compliance:
- Rule #6: Model < 150 lines
- Rule #11: Specific exception handling
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import TenantAwareModel, BaseModel


class WorkerDailyMetrics(TenantAwareModel, BaseModel):
    """
    Daily performance snapshot per worker.
    
    Aggregated nightly at 2 AM from:
    - Attendance (punch times, geofence, hours)
    - Tasks (completion, SLA, quality)
    - Tours (coverage, checkpoints, timing)
    - Work Orders (resolution, quality)
    - Compliance (certs, safety, documentation)
    
    Used for:
    - Worker performance dashboards
    - Supervisor coaching queues
    - Executive reporting
    - Cohort benchmarking
    """
    
    # Dimensions
    date = models.DateField(db_index=True, help_text="Metric date")
    worker = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='daily_metrics',
        help_text="Worker being measured"
    )
    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='worker_metrics',
        help_text="Primary work site for this day"
    )
    role = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Worker role (security_guard, supervisor, technician)"
    )
    shift_type = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Shift type (day, night, evening, weekend)"
    )
    
    # Exposure (denominators for rate calculations)
    scheduled_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Hours scheduled to work"
    )
    worked_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Hours actually worked"
    )
    scheduled_shifts = models.IntegerField(
        default=0,
        help_text="Number of shifts scheduled"
    )
    
    # Attendance Metrics
    on_time_punches = models.IntegerField(default=0)
    late_punches = models.IntegerField(default=0)
    total_late_minutes = models.IntegerField(default=0)
    early_departures = models.IntegerField(default=0)
    geofence_violations = models.IntegerField(default=0)
    ncns_incidents = models.IntegerField(default=0)
    
    # Task Metrics
    tasks_assigned = models.IntegerField(default=0)
    tasks_completed = models.IntegerField(default=0)
    tasks_within_sla = models.IntegerField(default=0)
    tasks_rework = models.IntegerField(default=0)
    task_quality_avg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Patrol Metrics
    tours_assigned = models.IntegerField(default=0)
    tours_completed = models.IntegerField(default=0)
    checkpoints_expected = models.IntegerField(default=0)
    checkpoints_scanned = models.IntegerField(default=0)
    checkpoints_missed = models.IntegerField(default=0)
    checkpoints_late = models.IntegerField(default=0)
    incidents_detected = models.IntegerField(default=0)
    
    # Work Order Metrics
    work_orders_assigned = models.IntegerField(default=0)
    work_orders_completed = models.IntegerField(default=0)
    work_orders_within_sla = models.IntegerField(default=0)
    work_order_quality_avg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Quality & Compliance
    incidents_reported = models.IntegerField(default=0)
    near_misses_reported = models.IntegerField(default=0)
    daily_reports_submitted = models.IntegerField(default=0)
    daily_reports_expected = models.IntegerField(default=0)
    evidence_photos_uploaded = models.IntegerField(default=0)
    evidence_photos_expected = models.IntegerField(default=0)
    certifications_current = models.IntegerField(default=0)
    certifications_total = models.IntegerField(default=0)
    
    # Computed Scores (0-100)
    attendance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Attendance & reliability score (0-100)"
    )
    task_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Task performance score (0-100)"
    )
    patrol_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Patrol quality score (0-100)"
    )
    work_order_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Work order performance score (0-100)"
    )
    compliance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Compliance & safety score (0-100)"
    )
    
    # Balanced Performance Index
    balanced_performance_index = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_index=True,
        help_text="Overall BPI score (0-100), weighted average"
    )
    
    # Cohort Comparison
    cohort_key = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Cohort identifier: site|role|shift|tenure_band|month"
    )
    bpi_percentile = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentile within cohort (0-100)"
    )
    performance_band = models.CharField(
        max_length=20,
        choices=[
            ('exceptional', 'Exceptional (90-100)'),
            ('strong', 'Strong (75-89)'),
            ('solid', 'Solid (60-74)'),
            ('developing', 'Developing (40-59)'),
            ('needs_support', 'Needs Support (<40)'),
        ],
        default='solid',
        help_text="Performance classification"
    )
    
    class Meta:
        db_table = 'perf_worker_daily_metrics'
        verbose_name = 'Worker Daily Metrics'
        verbose_name_plural = 'Worker Daily Metrics'
        unique_together = [['tenant', 'date', 'worker']]
        indexes = [
            models.Index(fields=['tenant', 'date', 'worker']),
            models.Index(fields=['tenant', 'date', 'site']),
            models.Index(fields=['tenant', 'cohort_key', 'date']),
            models.Index(fields=['tenant', 'balanced_performance_index']),
            models.Index(fields=['tenant', 'performance_band']),
        ]
        ordering = ['-date', 'worker']
    
    def __str__(self):
        return f"{self.worker.loginid} - {self.date} - BPI: {self.balanced_performance_index}"
    
    def get_performance_band_display_verbose(self):
        """Get verbose performance band description."""
        bands = {
            'exceptional': 'Exceptional Performance',
            'strong': 'Strong Performance',
            'solid': 'Solid Performance',
            'developing': 'Developing',
            'needs_support': 'Needs Support'
        }
        return bands.get(self.performance_band, 'Unknown')
