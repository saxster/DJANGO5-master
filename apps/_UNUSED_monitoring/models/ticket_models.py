"""
Automated Ticketing System Models

Handles automated ticket creation, routing, and resolution tracking.
Follows .claude/rules.md Rule #7: Model < 150 lines per class.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
import uuid


class TicketCategory(BaseModel, TenantAwareModel):
    """
    Categories for automated tickets with routing and SLA definitions.

    Defines how different types of operational issues are handled.
    """

    PRIORITY_LEVELS = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('URGENT', 'Urgent'),
        ('EMERGENCY', 'Emergency'),
    ]

    category_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique identifier for this category"
    )

    name = models.CharField(
        max_length=100,
        help_text="Category name"
    )

    description = models.TextField(
        help_text="Detailed category description"
    )

    default_priority = models.CharField(
        max_length=20,
        choices=PRIORITY_LEVELS,
        default='MEDIUM',
        help_text="Default priority for tickets in this category"
    )

    # Routing configuration
    default_assignee_role = models.CharField(
        max_length=50,
        blank=True,
        help_text="Default role to assign tickets to"
    )

    escalation_roles = models.JSONField(
        default=list,
        help_text="List of roles for escalation chain"
    )

    requires_immediate_response = models.BooleanField(
        default=False,
        help_text="Whether tickets require immediate response"
    )

    # SLA definitions
    response_time_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Required response time in minutes"
    )

    resolution_time_hours = models.PositiveIntegerField(
        default=24,
        help_text="Required resolution time in hours"
    )

    # Automation settings
    auto_assign = models.BooleanField(
        default=True,
        help_text="Whether to automatically assign tickets"
    )

    auto_escalate = models.BooleanField(
        default=True,
        help_text="Whether to automatically escalate overdue tickets"
    )

    notification_channels = models.JSONField(
        default=list,
        help_text="Notification channels (email, sms, webhook)"
    )

    # Templates
    title_template = models.CharField(
        max_length=200,
        help_text="Template for ticket titles"
    )

    description_template = models.TextField(
        help_text="Template for ticket descriptions"
    )

    resolution_steps = models.JSONField(
        default=list,
        help_text="Standard resolution steps"
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this category is active"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_ticket_category'
        verbose_name = 'Ticket Category'
        verbose_name_plural = 'Ticket Categories'
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['default_priority']),
        ]

    def __str__(self):
        return f"{self.name} ({self.default_priority})"


class OperationalTicket(BaseModel, TenantAwareModel):
    """
    Automated operational tickets for device and system issues.

    Created automatically from alerts and monitoring data.
    """

    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('PENDING_USER', 'Pending User Response'),
        ('PENDING_VENDOR', 'Pending Vendor'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    ]

    RESOLUTION_TYPES = [
        ('AUTOMATIC', 'Automatically Resolved'),
        ('MANUAL', 'Manually Resolved'),
        ('ESCALATED', 'Escalated to Higher Level'),
        ('WORKAROUND', 'Workaround Applied'),
        ('NO_ACTION', 'No Action Required'),
        ('DUPLICATE', 'Duplicate of Another Ticket'),
    ]

    ticket_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique identifier for this ticket"
    )

    ticket_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Human-readable ticket number"
    )

    category = models.ForeignKey(
        TicketCategory,
        on_delete=models.CASCADE,
        related_name='tickets',
        help_text="Ticket category"
    )

    # Related objects
    alert = models.ForeignKey(
        'monitoring.Alert',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tickets',
        help_text="Alert that triggered this ticket"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='operational_tickets',
        help_text="User this ticket is about"
    )

    device_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Device involved in the issue"
    )

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='operational_tickets',
        help_text="Site where issue occurred"
    )

    # Ticket content
    title = models.CharField(
        max_length=200,
        help_text="Ticket title"
    )

    description = models.TextField(
        help_text="Detailed ticket description"
    )

    priority = models.CharField(
        max_length=20,
        choices=TicketCategory.PRIORITY_LEVELS,
        db_index=True,
        help_text="Ticket priority"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OPEN',
        db_index=True,
        help_text="Current ticket status"
    )

    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        help_text="User assigned to handle this ticket"
    )

    assigned_role = models.CharField(
        max_length=50,
        blank=True,
        help_text="Role assigned to handle this ticket"
    )

    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ticket was assigned"
    )

    # Timing
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When ticket was created"
    )

    first_response_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When first response was provided"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ticket was resolved"
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ticket was closed"
    )

    # SLA tracking
    response_due_at = models.DateTimeField(
        db_index=True,
        help_text="When response is due"
    )

    resolution_due_at = models.DateTimeField(
        db_index=True,
        help_text="When resolution is due"
    )

    is_overdue = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether ticket is overdue"
    )

    # Resolution
    resolution_type = models.CharField(
        max_length=20,
        choices=RESOLUTION_TYPES,
        blank=True,
        help_text="How the ticket was resolved"
    )

    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes about the resolution"
    )

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_tickets',
        help_text="User who resolved the ticket"
    )

    # Metadata
    automation_data = models.JSONField(
        default=dict,
        help_text="Data from automated systems"
    )

    escalation_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times ticket has been escalated"
    )

    customer_satisfaction = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Customer satisfaction rating (1-5)"
    )

    # Communication tracking
    last_update_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time ticket was updated"
    )

    update_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of updates to this ticket"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_operational_ticket'
        verbose_name = 'Operational Ticket'
        verbose_name_plural = 'Operational Tickets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status', 'priority']),
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['response_due_at']),
            models.Index(fields=['resolution_due_at']),
            models.Index(fields=['is_overdue']),
        ]

    def __str__(self):
        return f"{self.ticket_number}: {self.title} ({self.status})"

    def save(self, *args, **kwargs):
        # Generate ticket number if not set
        if not self.ticket_number:
            self.ticket_number = self._generate_ticket_number()

        # Set due dates if not set
        if not self.response_due_at:
            self.response_due_at = self.created_at + timezone.timedelta(
                minutes=self.category.response_time_minutes
            )

        if not self.resolution_due_at:
            self.resolution_due_at = self.created_at + timezone.timedelta(
                hours=self.category.resolution_time_hours
            )

        # Update overdue status
        self.is_overdue = self._check_overdue()

        super().save(*args, **kwargs)

    def _generate_ticket_number(self):
        """Generate unique ticket number"""
        from django.utils.crypto import get_random_string
        prefix = f"OT{timezone.now().strftime('%Y%m')}"
        suffix = get_random_string(6, '0123456789')
        return f"{prefix}-{suffix}"

    def _check_overdue(self):
        """Check if ticket is overdue"""
        now = timezone.now()

        if self.status in ['RESOLVED', 'CLOSED', 'CANCELLED']:
            return False

        # Check response SLA
        if not self.first_response_at and now > self.response_due_at:
            return True

        # Check resolution SLA
        if self.status not in ['RESOLVED'] and now > self.resolution_due_at:
            return True

        return False

    def assign_to_user(self, user, notes=""):
        """Assign ticket to a specific user"""
        self.assigned_to = user
        self.assigned_role = getattr(user, 'role', '')
        self.assigned_at = timezone.now()
        self.status = 'ASSIGNED'
        self.save()

    def mark_in_progress(self, user, notes=""):
        """Mark ticket as in progress"""
        if not self.first_response_at:
            self.first_response_at = timezone.now()
        self.status = 'IN_PROGRESS'
        self.save()

    def resolve(self, user, resolution_type, notes=""):
        """Resolve the ticket"""
        self.status = 'RESOLVED'
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_type = resolution_type
        self.resolution_notes = notes
        self.is_overdue = False
        self.save()


class AutomatedAction(BaseModel, TenantAwareModel):
    """
    Automated actions that can be triggered by alerts or tickets.

    Defines automated responses to operational issues.
    """

    ACTION_TYPES = [
        ('NOTIFICATION', 'Send Notification'),
        ('DEVICE_COMMAND', 'Device Command'),
        ('TICKET_CREATE', 'Create Ticket'),
        ('ESCALATION', 'Escalate to Higher Level'),
        ('RESOURCE_ALLOCATION', 'Allocate Backup Resource'),
        ('MAINTENANCE_SCHEDULE', 'Schedule Maintenance'),
        ('SYSTEM_ADJUSTMENT', 'Adjust System Settings'),
        ('DATA_COLLECTION', 'Collect Additional Data'),
    ]

    TRIGGER_CONDITIONS = [
        ('ALERT_CREATED', 'Alert Created'),
        ('ALERT_ESCALATED', 'Alert Escalated'),
        ('TICKET_OVERDUE', 'Ticket Overdue'),
        ('DEVICE_OFFLINE', 'Device Offline'),
        ('BATTERY_CRITICAL', 'Battery Critical'),
        ('SECURITY_BREACH', 'Security Breach'),
        ('PERFORMANCE_DEGRADED', 'Performance Degraded'),
    ]

    action_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique identifier for this action"
    )

    name = models.CharField(
        max_length=100,
        help_text="Action name"
    )

    description = models.TextField(
        help_text="Detailed action description"
    )

    action_type = models.CharField(
        max_length=30,
        choices=ACTION_TYPES,
        db_index=True,
        help_text="Type of action to perform"
    )

    trigger_condition = models.CharField(
        max_length=30,
        choices=TRIGGER_CONDITIONS,
        db_index=True,
        help_text="Condition that triggers this action"
    )

    # Conditions
    trigger_criteria = models.JSONField(
        help_text="Specific criteria for triggering this action"
    )

    priority_filter = models.JSONField(
        default=list,
        help_text="Alert/ticket priorities this applies to"
    )

    site_filter = models.ManyToManyField(
        'onboarding.Bt',
        blank=True,
        help_text="Sites this action applies to"
    )

    # Action configuration
    action_config = models.JSONField(
        help_text="Configuration parameters for the action"
    )

    max_executions_per_hour = models.PositiveIntegerField(
        default=10,
        help_text="Maximum executions per hour (rate limiting)"
    )

    cooldown_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Cooldown period between executions"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this action is active"
    )

    success_rate = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Success rate of this action (0-1)"
    )

    total_executions = models.PositiveIntegerField(
        default=0,
        help_text="Total number of executions"
    )

    last_executed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last execution timestamp"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_automated_action'
        verbose_name = 'Automated Action'
        verbose_name_plural = 'Automated Actions'
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['trigger_condition', 'is_active']),
            models.Index(fields=['action_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.action_type})"

    def can_execute(self):
        """Check if action can be executed (rate limiting, cooldown)"""
        if not self.is_active:
            return False

        # Check cooldown
        if self.last_executed_at:
            cooldown_until = self.last_executed_at + timezone.timedelta(
                minutes=self.cooldown_minutes
            )
            if timezone.now() < cooldown_until:
                return False

        # Check rate limiting (simplified - would need more sophisticated tracking)
        return True


class TicketEscalation(BaseModel):
    """
    Ticket escalation tracking and automation.

    Tracks escalations and manages escalation workflows.
    """

    ticket = models.ForeignKey(
        OperationalTicket,
        on_delete=models.CASCADE,
        related_name='escalations',
        help_text="Ticket that was escalated"
    )

    escalated_from = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalations_from',
        help_text="User who escalated the ticket"
    )

    escalated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalations_to',
        help_text="User ticket was escalated to"
    )

    escalated_to_role = models.CharField(
        max_length=50,
        help_text="Role ticket was escalated to"
    )

    escalation_level = models.PositiveIntegerField(
        help_text="Escalation level (1, 2, 3, etc.)"
    )

    reason = models.TextField(
        help_text="Reason for escalation"
    )

    escalated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When escalation occurred"
    )

    is_automatic = models.BooleanField(
        default=False,
        help_text="Whether escalation was automatic"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_ticket_escalation'
        verbose_name = 'Ticket Escalation'
        verbose_name_plural = 'Ticket Escalations'
        indexes = [
            models.Index(fields=['ticket', 'escalated_at']),
            models.Index(fields=['escalated_to', 'escalated_at']),
        ]

    def __str__(self):
        return f"Escalation: {self.ticket.ticket_number} to Level {self.escalation_level}"


class TicketResolution(BaseModel):
    """
    Detailed ticket resolution tracking and knowledge base.

    Stores resolution details for future reference and automation.
    """

    ticket = models.OneToOneField(
        OperationalTicket,
        on_delete=models.CASCADE,
        related_name='detailed_resolution',
        help_text="Ticket that was resolved"
    )

    resolution_category = models.CharField(
        max_length=50,
        help_text="Category of resolution"
    )

    root_cause = models.TextField(
        help_text="Identified root cause of the issue"
    )

    resolution_steps = models.JSONField(
        help_text="Steps taken to resolve the issue"
    )

    time_to_resolution_minutes = models.PositiveIntegerField(
        help_text="Total time to resolution in minutes"
    )

    resources_used = models.JSONField(
        default=list,
        help_text="Resources used for resolution"
    )

    # Knowledge base
    is_permanent_fix = models.BooleanField(
        help_text="Whether this is a permanent fix"
    )

    prevention_measures = models.TextField(
        blank=True,
        help_text="Measures to prevent recurrence"
    )

    similar_tickets = models.ManyToManyField(
        OperationalTicket,
        blank=True,
        help_text="Related/similar tickets"
    )

    # Effectiveness tracking
    customer_satisfaction = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Customer satisfaction rating (1-5)"
    )

    recurrence_within_30_days = models.BooleanField(
        default=False,
        help_text="Whether issue recurred within 30 days"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_ticket_resolution'
        verbose_name = 'Ticket Resolution'
        verbose_name_plural = 'Ticket Resolutions'
        indexes = [
            models.Index(fields=['resolution_category']),
            models.Index(fields=['is_permanent_fix']),
            models.Index(fields=['customer_satisfaction']),
        ]

    def __str__(self):
        return f"Resolution: {self.ticket.ticket_number} ({self.resolution_category})"