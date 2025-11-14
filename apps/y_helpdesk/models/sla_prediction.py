"""
SLA Prediction Model

Stores risk predictions for tickets to help prioritize work.
Part of Priority Alerts system - user-friendly deadline tracking.

User sees: "⚠️ This ticket might miss its deadline"
Not: "High SLA breach probability detected"

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes

Created: 2025-11-07
"""

import logging
from django.db import models
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel

logger = logging.getLogger(__name__)


class SLAPrediction(BaseModel, TenantAwareModel):
    """
    Priority alert predictions for tickets.
    
    Stores risk level and suggested actions to help teams
    prevent deadline misses.
    """

    # Override audit fields to prevent related_name collisions with core app
    cuser = models.ForeignKey(
        'peoples.People',
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name='helpdesk_sla_prediction_cusers',
        verbose_name="Created by",
        help_text="User who created this prediction"
    )
    muser = models.ForeignKey(
        'peoples.People',
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name='helpdesk_sla_prediction_musers',
        verbose_name="Modified by",
        help_text="User who last modified this prediction"
    )
    
    RISK_LEVEL_CHOICES = [
        ('low', '🟢 On Track'),
        ('medium', '🟠 Soon'),
        ('high', '🔴 Urgent'),
    ]
    
    # What are we tracking?
    item_type = models.CharField(
        max_length=50,
        default='Ticket',
        help_text="Type of item (Ticket, WorkOrder, etc.)"
    )
    
    item_id = models.IntegerField(
        help_text="ID of the ticket/item"
    )
    
    # Risk assessment
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default='low',
        help_text="Priority level: low/medium/high"
    )
    
    confidence = models.IntegerField(
        default=0,
        help_text="Risk score (0-100)"
    )
    
    risk_factors = models.JSONField(
        default=list,
        blank=True,
        help_text="Why this needs attention: [{icon, message, severity}, ...]"
    )
    
    suggested_actions = models.JSONField(
        default=list,
        blank=True,
        help_text="What to do: [{icon, text, action, priority}, ...]"
    )
    
    # User interaction
    is_acknowledged = models.BooleanField(
        default=False,
        help_text="User clicked 'I've got this'"
    )
    
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user acknowledged"
    )
    
    acknowledged_by = models.ForeignKey(
        'peoples.People',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='helpdesk_sla_predictions_acknowledged',
        help_text="Who acknowledged"
    )
    
    # Tracking
    last_checked = models.DateTimeField(
        auto_now=True,
        help_text="Last risk calculation"
    )
    
    alert_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When notification was sent"
    )
    
    class Meta:
        db_table = 'sla_prediction'
        indexes = [
            models.Index(fields=['item_type', 'item_id']),
            models.Index(fields=['risk_level', 'is_acknowledged']),
            models.Index(fields=['tenant', 'risk_level']),
            models.Index(fields=['last_checked']),
        ]
        unique_together = [['item_type', 'item_id']]
        verbose_name = "Priority Alert"
        verbose_name_plural = "Priority Alerts"
        ordering = ['-confidence', '-last_checked']
    
    def __str__(self):
        return f"{self.get_risk_level_display()} - {self.item_type} #{self.item_id}"
    
    def acknowledge(self, user):
        """Mark alert as acknowledged by user."""
        self.is_acknowledged = True
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        self.save(update_fields=['is_acknowledged', 'acknowledged_at', 'acknowledged_by'])
        logger.info(f"Alert acknowledged: {self} by {user.peoplename}")
    
    def get_ticket(self):
        """Get associated ticket (if item_type is Ticket)."""
        if self.item_type == 'Ticket':
            from apps.y_helpdesk.models import Ticket
            try:
                return Ticket.objects.get(id=self.item_id)
            except Ticket.DoesNotExist:
                logger.warning(f"Ticket {self.item_id} not found for prediction {self.id}")
                return None
        return None
    
    @property
    def badge(self):
        """Get friendly badge text."""
        return self.get_risk_level_display()
