"""
Cache analytics models for storing time-series cache metrics.

Tracks cache performance over time for analysis and optimization.
Complies with .claude/rules.md - Model < 150 lines, single responsibility.
"""

import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

__all__ = ['CacheMetrics', 'CacheAnomalyLog']


class CacheMetrics(models.Model):
    """
    Time-series storage for cache performance metrics.

    Tracks hit ratios, memory usage, and access patterns per cache pattern.
    """

    pattern_name = models.CharField(max_length=100, db_index=True)
    pattern_key = models.CharField(max_length=200)

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    interval = models.CharField(
        max_length=20,
        choices=[
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly')
        ],
        default='hourly',
        db_index=True
    )

    total_hits = models.BigIntegerField(default=0)
    total_misses = models.BigIntegerField(default=0)
    hit_ratio = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    avg_ttl_at_hit = models.IntegerField(default=0, help_text='Average TTL remaining when cache hit occurs')
    configured_ttl = models.IntegerField(default=0)

    memory_bytes = models.BigIntegerField(default=0, help_text='Estimated memory usage for pattern')
    key_count = models.IntegerField(default=0, help_text='Number of active keys for pattern')

    class Meta:
        db_table = 'core_cache_metrics'
        verbose_name = 'Cache Metric'
        verbose_name_plural = 'Cache Metrics'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['pattern_name', '-timestamp'], name='idx_cache_pattern_time'),
            models.Index(fields=['interval', '-timestamp'], name='idx_cache_interval_time'),
            models.Index(fields=['-hit_ratio'], name='idx_cache_hit_ratio'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(hit_ratio__gte=0) & models.Q(hit_ratio__lte=1),
                name='cache_hit_ratio_bounds'
            ),
            models.CheckConstraint(
                check=models.Q(total_hits__gte=0) & models.Q(total_misses__gte=0),
                name='cache_counts_positive'
            )
        ]

    def __str__(self):
        return f"{self.pattern_name} - {self.timestamp} ({self.hit_ratio * 100:.1f}%)"

    def save(self, *args, **kwargs):
        """Calculate hit ratio before saving"""
        try:
            total = self.total_hits + self.total_misses
            if total > 0:
                self.hit_ratio = self.total_hits / total
            else:
                self.hit_ratio = 0
            super().save(*args, **kwargs)
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.error(f"Error saving cache metrics: {e}")
            raise


class CacheAnomalyLog(models.Model):
    """
    Log of detected cache anomalies for investigation.

    Tracks unusual cache behavior that may indicate issues.
    """

    pattern_name = models.CharField(max_length=100, db_index=True)
    anomaly_type = models.CharField(
        max_length=50,
        choices=[
            ('low_hit_ratio', 'Low Hit Ratio'),
            ('high_miss_rate', 'High Miss Rate'),
            ('memory_spike', 'Memory Usage Spike'),
            ('ttl_mismatch', 'TTL Configuration Mismatch'),
            ('key_explosion', 'Excessive Key Count'),
        ],
        db_index=True
    )

    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    severity = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ],
        default='medium'
    )

    hit_ratio_at_detection = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    description = models.TextField()
    recommendation = models.TextField(blank=True)

    resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        db_table = 'core_cache_anomaly_log'
        verbose_name = 'Cache Anomaly'
        verbose_name_plural = 'Cache Anomalies'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['pattern_name', '-detected_at'], name='idx_anomaly_pattern_time'),
            models.Index(fields=['resolved', '-detected_at'], name='idx_anomaly_resolved'),
            models.Index(fields=['severity', '-detected_at'], name='idx_anomaly_severity'),
        ]

    def __str__(self):
        return f"{self.pattern_name} - {self.anomaly_type} ({self.severity})"