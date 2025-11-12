"""
Quality Metrics Tracking Model

Tracks code quality metrics over time for trend analysis and alerting.
Enables historical analysis of:
- Code quality scores
- Test coverage percentages
- Cyclomatic complexity
- Security issue counts
- File size violations

Compliance:
- Rule #7: Model < 150 lines
- Enterprise metrics standards
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class QualityMetric(models.Model):
    """
    Periodic snapshot of code quality metrics.

    Stores weekly or daily snapshots of quality measurements for trend analysis.
    Automatically tracks metrics across the entire codebase.
    """

    # Timestamp
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When this metric was recorded"
    )

    # Code Quality Score (0-100)
    code_quality_score = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall code quality score (0-100)"
    )

    # Test Coverage (0-100%)
    test_coverage = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Test code coverage percentage"
    )

    # Complexity Score
    complexity_score = models.FloatField(
        default=0,
        help_text="Average cyclomatic complexity"
    )

    # Security Issues
    security_issues = models.IntegerField(
        default=0,
        help_text="Total number of security issues found"
    )

    security_critical = models.IntegerField(
        default=0,
        help_text="Count of critical severity security issues"
    )

    security_high = models.IntegerField(
        default=0,
        help_text="Count of high severity security issues"
    )

    # File Compliance
    file_violations = models.IntegerField(
        default=0,
        help_text="Number of file size compliance violations"
    )

    # Overall Assessment
    overall_grade = models.CharField(
        max_length=1,
        choices=[
            ('A', 'Excellent'),
            ('B', 'Good'),
            ('C', 'Acceptable'),
            ('D', 'Poor'),
            ('F', 'Failing'),
        ],
        default='C',
        help_text="Overall quality grade (A-F)"
    )

    overall_score = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall quality score (0-100)"
    )

    # Report
    report_json = models.JSONField(
        default=dict,
        help_text="Full report data as JSON"
    )

    # Metadata
    is_weekly = models.BooleanField(
        default=False,
        help_text="Whether this is a weekly (vs daily) snapshot"
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['-timestamp']),
            models.Index(fields=['is_weekly', '-timestamp']),
        ]
        verbose_name_plural = "Quality Metrics"

    def __str__(self):
        return f"{self.overall_grade} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @property
    def is_passing(self) -> bool:
        """Check if all metrics meet thresholds"""
        return (
            self.code_quality_score >= 90 and
            self.test_coverage >= 85 and
            self.complexity_score <= 6.5 and
            self.security_critical == 0 and
            self.file_violations == 0
        )

    @classmethod
    def get_latest(cls):
        """Get the latest metric snapshot"""
        return cls.objects.order_by('-timestamp').first()

    @classmethod
    def get_weekly_average(cls, weeks: int = 4):
        """
        Get average metrics for the last N weeks.
        Useful for trend analysis.
        """
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(weeks=weeks)
        metrics = cls.objects.filter(
            timestamp__gte=cutoff,
            is_weekly=True
        ).order_by('-timestamp')

        if not metrics.exists():
            return None

        avg_code_quality = sum(m.code_quality_score for m in metrics) / len(metrics)
        avg_coverage = sum(m.test_coverage for m in metrics) / len(metrics)
        avg_complexity = sum(m.complexity_score for m in metrics) / len(metrics)
        total_security = sum(m.security_issues for m in metrics)
        total_violations = sum(m.file_violations for m in metrics)

        return {
            'avg_code_quality': avg_code_quality,
            'avg_coverage': avg_coverage,
            'avg_complexity': avg_complexity,
            'total_security_issues': total_security,
            'total_violations': total_violations,
            'period_weeks': weeks,
            'metric_count': len(metrics),
        }
