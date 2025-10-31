"""
Query Execution Plan Monitoring Models

Models for capturing, storing, and analyzing PostgreSQL query execution plans.
Enables detection of performance regressions and optimization opportunities.

Features:
- Execution plan storage and versioning
- Plan comparison and regression detection
- Performance metrics extraction
- Optimization recommendations
- Historical plan tracking

Compliance:
- Rule #7: Model < 150 lines (split into focused models)
- Rule #12: Query optimization awareness
- Enterprise performance monitoring standards
"""

import json
import hashlib
import re
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


class QueryExecutionPlan(models.Model):
    """
    Stores PostgreSQL query execution plans with performance metrics.

    Captures EXPLAIN ANALYZE output for performance analysis and
    regression detection over time.
    """

    # Query identification
    query_hash = models.BigIntegerField(
        db_index=True,
        help_text="PostgreSQL query hash (queryid from pg_stat_statements)"
    )

    plan_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Hash of the execution plan structure"
    )

    query_text = models.TextField(
        help_text="Full query text (truncated if necessary)"
    )

    # Execution plan data
    execution_plan = models.JSONField(
        help_text="Full EXPLAIN ANALYZE output as JSON"
    )

    plan_summary = models.TextField(
        help_text="Human-readable plan summary"
    )

    # Performance metrics
    execution_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Actual execution time in milliseconds"
    )

    planning_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Query planning time in milliseconds"
    )

    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="PostgreSQL cost estimate"
    )

    rows_returned = models.BigIntegerField(
        default=0,
        help_text="Number of rows returned"
    )

    # Resource usage
    shared_hit_blocks = models.BigIntegerField(
        default=0,
        help_text="Shared buffer blocks hit"
    )

    shared_read_blocks = models.BigIntegerField(
        default=0,
        help_text="Shared buffer blocks read"
    )

    temp_read_blocks = models.BigIntegerField(
        default=0,
        help_text="Temporary blocks read"
    )

    temp_written_blocks = models.BigIntegerField(
        default=0,
        help_text="Temporary blocks written"
    )

    # Plan metadata
    captured_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When this plan was captured"
    )

    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who captured this plan (if manual)"
    )

    capture_method = models.CharField(
        max_length=20,
        choices=[
            ('automatic', 'Automatic (slow query detection)'),
            ('manual', 'Manual capture'),
            ('scheduled', 'Scheduled analysis'),
        ],
        default='automatic',
        help_text="How this plan was captured"
    )

    # Analysis results
    optimization_opportunities = models.JSONField(
        default=list,
        blank=True,
        help_text="List of identified optimization opportunities"
    )

    regression_detected = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this plan represents a performance regression"
    )

    class Meta:
        db_table = 'query_execution_plans'
        ordering = ['-captured_at']
        indexes = [
            models.Index(fields=['query_hash', 'captured_at']),
            models.Index(fields=['plan_hash']),
            models.Index(fields=['execution_time']),
            models.Index(fields=['regression_detected', 'captured_at']),
        ]
        verbose_name = 'Query Execution Plan'
        verbose_name_plural = 'Query Execution Plans'

    def __str__(self):
        return f"Plan {self.plan_hash[:8]} for query {self.query_hash} ({self.execution_time}ms)"

    def save(self, *args, **kwargs):
        """Override save to generate plan hash and summary."""
        if self.execution_plan:
            self.plan_hash = self.generate_plan_hash()
            self.plan_summary = self.generate_plan_summary()

        super().save(*args, **kwargs)

    def generate_plan_hash(self) -> str:
        """
        Generate a hash of the execution plan structure.

        Creates a hash based on the plan structure while ignoring
        actual values and costs that may vary between executions.
        """
        try:
            # Extract just the plan structure, ignoring costs and actual values
            normalized_plan = self._normalize_plan_structure(self.execution_plan)
            plan_string = json.dumps(normalized_plan, sort_keys=True)
            return hashlib.sha256(plan_string.encode()).hexdigest()
        except Exception:
            # Fallback to simple hash if normalization fails
            plan_string = json.dumps(self.execution_plan, sort_keys=True)
            return hashlib.sha256(plan_string.encode()).hexdigest()

    def _normalize_plan_structure(self, plan_node):
        """Normalize plan structure for hashing."""
        if isinstance(plan_node, dict):
            normalized = {}
            for key, value in plan_node.items():
                # Skip cost and timing related fields for structure hashing
                if key not in ['Total Cost', 'Startup Cost', 'Actual Total Time',
                              'Actual Startup Time', 'Actual Rows', 'Actual Loops']:
                    if key == 'Plans':
                        normalized[key] = [self._normalize_plan_structure(child) for child in value]
                    elif isinstance(value, (dict, list)):
                        normalized[key] = self._normalize_plan_structure(value)
                    else:
                        normalized[key] = value
            return normalized
        elif isinstance(plan_node, list):
            return [self._normalize_plan_structure(item) for item in plan_node]
        else:
            return plan_node

    def generate_plan_summary(self) -> str:
        """Generate human-readable plan summary."""
        try:
            if not self.execution_plan:
                return "No plan data available"

            # Extract top-level plan information
            plan = self.execution_plan[0]['Plan'] if isinstance(self.execution_plan, list) else self.execution_plan.get('Plan', {})

            node_type = plan.get('Node Type', 'Unknown')
            total_cost = plan.get('Total Cost', 0)
            actual_time = plan.get('Actual Total Time', 0)

            summary_parts = [f"{node_type} (Cost: {total_cost}, Time: {actual_time}ms)"]

            # Add key operation details
            if 'Relation Name' in plan:
                summary_parts.append(f"Table: {plan['Relation Name']}")

            if 'Index Name' in plan:
                summary_parts.append(f"Index: {plan['Index Name']}")

            if 'Sort Key' in plan:
                summary_parts.append(f"Sort: {', '.join(plan['Sort Key'])}")

            if 'Hash Cond' in plan:
                summary_parts.append(f"Hash Condition: {plan['Hash Cond']}")

            if 'Filter' in plan:
                summary_parts.append(f"Filter: {plan['Filter']}")

            return " | ".join(summary_parts)

        except Exception as e:
            return f"Error generating summary: {str(e)}"

    @property
    def cache_hit_ratio(self) -> float:
        """Calculate cache hit ratio percentage."""
        total_blocks = self.shared_hit_blocks + self.shared_read_blocks
        if total_blocks > 0:
            return (self.shared_hit_blocks / total_blocks) * 100
        return 0

    @property
    def uses_temp_storage(self) -> bool:
        """Check if query uses temporary storage."""
        return self.temp_read_blocks > 0 or self.temp_written_blocks > 0

    @classmethod
    def get_plan_history(cls, query_hash: int, days: int = 30):
        """Get execution plan history for a specific query."""
        since = timezone.now() - timezone.timedelta(days=days)
        return cls.objects.filter(
            query_hash=query_hash,
            captured_at__gte=since
        ).order_by('-captured_at')

    def find_similar_plans(self, limit: int = 10):
        """Find plans with similar structure but different performance."""
        return QueryExecutionPlan.objects.filter(
            plan_hash=self.plan_hash
        ).exclude(
            id=self.id
        ).order_by('-captured_at')[:limit]


class PlanRegressionAlert(models.Model):
    """
    Alerts for detected execution plan regressions.

    Automatically created when a query's execution plan
    shows significant performance degradation.
    """

    SEVERITY_CHOICES = [
        ('info', 'Informational'),
        ('warning', 'Warning - Performance Degraded'),
        ('critical', 'Critical - Severe Regression'),
    ]

    STATUS_CHOICES = [
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
    ]

    # Alert identification
    query_hash = models.BigIntegerField(
        db_index=True,
        help_text="Query hash that experienced regression"
    )

    current_plan = models.ForeignKey(
        QueryExecutionPlan,
        on_delete=models.CASCADE,
        related_name='regression_alerts_current',
        help_text="Current (regressed) execution plan"
    )

    baseline_plan = models.ForeignKey(
        QueryExecutionPlan,
        on_delete=models.CASCADE,
        related_name='regression_alerts_baseline',
        help_text="Previous (baseline) execution plan"
    )

    # Regression details
    performance_degradation = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Performance degradation percentage"
    )

    regression_type = models.CharField(
        max_length=50,
        choices=[
            ('execution_time', 'Execution Time Regression'),
            ('plan_change', 'Plan Structure Change'),
            ('index_not_used', 'Index No Longer Used'),
            ('sequential_scan', 'Sequential Scan Introduced'),
            ('temp_storage', 'Temporary Storage Usage'),
        ],
        help_text="Type of regression detected"
    )

    # Alert management
    detected_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the regression was detected"
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='warning',
        db_index=True,
        help_text="Regression severity level"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        db_index=True,
        help_text="Current alert status"
    )

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_plan_regressions',
        help_text="User who acknowledged this alert"
    )

    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this alert was acknowledged"
    )

    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes about investigation and resolution"
    )

    class Meta:
        db_table = 'plan_regression_alerts'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['query_hash', 'detected_at']),
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['regression_type', 'status']),
        ]
        verbose_name = 'Plan Regression Alert'
        verbose_name_plural = 'Plan Regression Alerts'

    def __str__(self):
        return f"{self.regression_type} - Query {self.query_hash} ({self.performance_degradation}% slower)"

    def acknowledge(self, user, notes=""):
        """Acknowledge the regression alert."""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        if notes:
            self.resolution_notes = f"{self.resolution_notes}\n[{timezone.now()}] Acknowledged: {notes}"
        self.save()

    def resolve(self, notes=""):
        """Mark regression as resolved."""
        self.status = 'resolved'
        if notes:
            self.resolution_notes = f"{self.resolution_notes}\n[{timezone.now()}] Resolved: {notes}"
        self.save()

    @classmethod
    def create_regression_alert(cls, current_plan, baseline_plan, regression_data):
        """Create a new regression alert."""
        degradation = regression_data.get('performance_degradation', 0)
        regression_type = regression_data.get('type', 'execution_time')

        # Determine severity based on degradation
        if degradation > 200:  # 200% slower
            severity = 'critical'
        elif degradation > 50:  # 50% slower
            severity = 'warning'
        else:
            severity = 'info'

        return cls.objects.create(
            query_hash=current_plan.query_hash,
            current_plan=current_plan,
            baseline_plan=baseline_plan,
            performance_degradation=degradation,
            regression_type=regression_type,
            severity=severity
        )