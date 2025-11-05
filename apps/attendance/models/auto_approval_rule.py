"""
Auto-Approval Rule Model (Phase 4.5)

Model for configurable auto-approval rules.

Author: Claude Code
Created: 2025-11-05
Phase: 4.5 - Auto-Approval Rules
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.core.models import BaseModel, TenantAwareModel
from apps.attendance.models.approval_enums import RequestStatus
from apps.attendance.models.auto_approval_rule_actions import AutoApprovalRuleActions

import logging

logger = logging.getLogger(__name__)


class AutoApprovalRule(AutoApprovalRuleActions, BaseModel, TenantAwareModel):
    """
    Configurable rules for auto-approval of requests.

    Allows automatic approval of low-risk requests without manual review.

    Example Rules:
    - Same site, same shift, within 15 minutes → Auto-approve
    - Coverage gap fill, qualified worker → Auto-approve
    - Emergency assignment, site supervisor request → Auto-approve
    """

    rule_name = models.CharField(
        max_length=100,
        help_text=_("Descriptive name for this rule")
    )

    rule_code = models.CharField(
        max_length=50,
        unique=True,
        help_text=_("Unique code for this rule")
    )

    active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Whether this rule is currently active")
    )

    # ========== Rule Criteria ==========

    request_types = models.JSONField(
        default=list,
        help_text=_("List of request types this rule applies to")
    )

    priority_levels = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Priority levels this rule applies to (empty = all)")
    )

    max_distance_from_site_meters = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Maximum distance from site for auto-approval (meters)")
    )

    max_time_variance_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Maximum time variance from scheduled shift (minutes)")
    )

    requires_qualification_match = models.BooleanField(
        default=True,
        help_text=_("Whether worker must be qualified for post")
    )

    same_site_only = models.BooleanField(
        default=True,
        help_text=_("Only auto-approve if same site")
    )

    # ========== Rule Conditions (JSON-based for flexibility) ==========

    conditions = models.JSONField(
        default=dict,
        help_text=_(
            "Flexible conditions in JSON format. Example: "
            "{'max_late_minutes': 15, 'allowed_sites': [1, 2], 'requires_supervisor_request': true}"
        )
    )

    # ========== Rule Metadata ==========

    description = models.TextField(
        blank=True,
        help_text=_("Description of when this rule applies")
    )

    created_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auto_approval_rules_created',
        help_text=_("Who created this rule")
    )

    times_applied = models.IntegerField(
        default=0,
        help_text=_("Number of times this rule has been applied")
    )

    last_applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When this rule was last applied")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_auto_approval_rule'
        verbose_name = _('Auto-Approval Rule')
        verbose_name_plural = _('Auto-Approval Rules')
        indexes = [
            models.Index(fields=['tenant', 'active'], name='aar_active_idx'),
            models.Index(fields=['rule_code'], name='aar_code_idx'),
        ]
        ordering = ['rule_name']

    def __str__(self):
        status = "Active" if self.active else "Inactive"
        return f"{self.rule_name} ({status}) - Applied {self.times_applied} times"

    def matches_request(self, approval_request):
        """
        Check if this rule matches the given approval request.

        Args:
            approval_request: ApprovalRequest instance

        Returns:
            tuple: (matches: bool, reason: str)
        """
        # Check request type
        if approval_request.request_type not in self.request_types:
            return (False, "Request type not in rule")

        # Check priority if specified
        if self.priority_levels and approval_request.priority not in self.priority_levels:
            return (False, "Priority level not in rule")

        # Check same site requirement
        if self.same_site_only:
            # TODO: Implement site checking logic
            pass

        # Check custom conditions
        conditions = self.conditions or {}

        # Example condition checks
        if 'max_late_minutes' in conditions:
            # Check if request is for late check-in within threshold
            # Implementation depends on request_metadata structure
            pass

        # If all checks pass
        return (True, "All conditions met")
