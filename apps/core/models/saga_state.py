"""
Saga State Model - Distributed Transaction State Persistence

Enables safe rollbacks for distributed operations (scheduling, tours, complex workflows).

Saga Pattern:
1. Create saga with unique ID
2. Execute steps sequentially
3. Persist context after each step
4. On failure, rollback using persisted context
5. Auto-cleanup completed sagas (>7 days)

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #12: Query optimization with indexes
- Rule #17: Transaction management

Sprint 3: Saga State Persistence
"""

import logging
import uuid
from datetime import timedelta
from typing import Dict, Any
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class SagaState(models.Model):
    """
    Distributed transaction saga state persistence.

    Stores intermediate state for multi-step operations to enable rollback.
    """

    STATUS_CHOICES = [
        ('created', 'Created'),
        ('in_progress', 'In Progress'),
        ('committed', 'Committed'),
        ('rolled_back', 'Rolled Back'),
        ('failed', 'Failed'),
    ]

    # Identification
    saga_id = models.CharField(
        max_length=255,
        primary_key=True,
        help_text="Unique saga identifier (format: operation_YYYYMMDD_HHMMSS)"
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='created',
        help_text="Current saga status"
    )

    # Operation metadata
    operation_type = models.CharField(
        max_length=100,
        help_text="Type of operation (e.g., 'guard_tour', 'schedule_creation')"
    )

    steps_completed = models.IntegerField(
        default=0,
        help_text="Number of steps successfully completed"
    )

    total_steps = models.IntegerField(
        default=0,
        help_text="Total number of steps in saga"
    )

    # Context data (stores intermediate results)
    context_data = models.JSONField(
        default=dict,
        help_text="Saga context: step results, created objects, rollback data"
    )

    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text="Error message if saga failed"
    )

    error_step = models.CharField(
        max_length=100,
        blank=True,
        help_text="Step where error occurred"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When saga was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    committed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When saga was committed"
    )

    rolled_back_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When saga was rolled back"
    )

    class Meta:
        db_table = 'saga_state'
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['operation_type', 'status']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = "Saga State"
        verbose_name_plural = "Saga States"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.operation_type} - {self.saga_id} ({self.status})"

    def record_step_completion(self, step_name: str, step_result: Any):
        """
        Record successful step completion.

        Args:
            step_name: Name of completed step
            step_result: Result data from step
        """
        self.steps_completed += 1
        self.context_data[step_name] = {
            'result': step_result,
            'completed_at': timezone.now().isoformat()
        }
        self.status = 'in_progress'
        self.save()

        logger.info(f"Saga {self.saga_id}: Step '{step_name}' completed ({self.steps_completed}/{self.total_steps})")

    def commit(self):
        """Mark saga as successfully committed."""
        self.status = 'committed'
        self.committed_at = timezone.now()
        self.save()

        logger.info(f"Saga {self.saga_id} committed successfully")

    def rollback(self, error_step: str, error_message: str):
        """
        Mark saga as rolled back due to error.

        Args:
            error_step: Step where error occurred
            error_message: Error description
        """
        self.status = 'rolled_back'
        self.error_step = error_step
        self.error_message = error_message
        self.rolled_back_at = timezone.now()
        self.save()

        logger.warning(f"Saga {self.saga_id} rolled back at step '{error_step}': {error_message}")

    def is_stale(self, threshold_days: int = 7) -> bool:
        """
        Check if saga is stale (completed long ago).

        Args:
            threshold_days: Days before saga considered stale

        Returns:
            bool: True if stale and can be cleaned up
        """
        if self.status not in ['committed', 'rolled_back']:
            return False  # Still active

        completion_time = self.committed_at or self.rolled_back_at
        if not completion_time:
            return False

        age = timezone.now() - completion_time
        return age > timedelta(days=threshold_days)
