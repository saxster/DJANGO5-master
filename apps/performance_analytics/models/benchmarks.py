"""
Cohort Benchmark Model

Statistical benchmarks per cohort for fair comparison.
Updated weekly from WorkerDailyMetrics.

Compliance:
- Rule #6: Model < 150 lines
"""

from django.db import models
from apps.core.models import TenantAwareModel, BaseModel


class CohortBenchmark(TenantAwareModel, BaseModel):
    """
    Statistical benchmarks per cohort.
    
    Cohort = workers with same site, role, shift, tenure band, month
    Used for fair peer comparison and percentile calculation.
    
    Updated weekly via Celery task.
    """
    
    cohort_key = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Format: site_id|role|shift_type|tenure_band|month"
    )
    metric_name = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Metric being benchmarked (e.g., 'bpi', 'on_time_rate')"
    )
    period_start = models.DateField(help_text="Benchmark period start")
    period_end = models.DateField(help_text="Benchmark period end")
    
    # Sample Statistics
    sample_size = models.IntegerField(
        default=0,
        help_text="Number of worker-days in cohort"
    )
    worker_count = models.IntegerField(
        default=0,
        help_text="Number of unique workers"
    )
    
    # Distribution Statistics
    mean = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    median = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    std_dev = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    min_value = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    max_value = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    
    # Percentiles
    p10 = models.DecimalField(max_digits=8, decimal_places=3, default=0, help_text="10th percentile")
    p25 = models.DecimalField(max_digits=8, decimal_places=3, default=0, help_text="25th percentile (Q1)")
    p50 = models.DecimalField(max_digits=8, decimal_places=3, default=0, help_text="50th percentile (median)")
    p75 = models.DecimalField(max_digits=8, decimal_places=3, default=0, help_text="75th percentile (Q3)")
    p90 = models.DecimalField(max_digits=8, decimal_places=3, default=0, help_text="90th percentile")
    
    # Control Limits (for anomaly detection)
    lower_control_limit = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=0,
        help_text="Mean - 2*std_dev"
    )
    upper_control_limit = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=0,
        help_text="Mean + 2*std_dev"
    )
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'perf_cohort_benchmarks'
        verbose_name = 'Cohort Benchmark'
        verbose_name_plural = 'Cohort Benchmarks'
        unique_together = [['tenant', 'cohort_key', 'metric_name', 'period_start']]
        indexes = [
            models.Index(fields=['tenant', 'cohort_key', 'metric_name']),
            models.Index(fields=['tenant', 'period_start', 'period_end']),
        ]
        ordering = ['-period_end', 'cohort_key', 'metric_name']
    
    def __str__(self):
        return f"{self.cohort_key} - {self.metric_name} ({self.period_start} to {self.period_end})"
    
    def is_sufficient_sample(self, min_workers=5, min_days=7):
        """Check if cohort has sufficient sample size for valid benchmarks."""
        return self.worker_count >= min_workers and self.sample_size >= min_days
    
    def get_percentile_band(self, value):
        """
        Determine which percentile band a value falls into.
        
        Returns: 'bottom_10', 'bottom_25', 'middle_50', 'top_25', 'top_10'
        """
        if value >= self.p90:
            return 'top_10'
        elif value >= self.p75:
            return 'top_25'
        elif value >= self.p25:
            return 'middle_50'
        elif value >= self.p10:
            return 'bottom_25'
        else:
            return 'bottom_10'
