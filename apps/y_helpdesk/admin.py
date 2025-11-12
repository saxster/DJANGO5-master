"""
Y-Helpdesk Django Admin Configuration

Provides operational visibility and management interface for tickets,
escalation rules, and SLA policies.

Following .claude/rules.md:
- Admin < 100 lines per ModelAdmin
- Security-conscious (read-only sensitive fields)
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.core.exceptions import ObjectDoesNotExist

from apps.y_helpdesk.models import Ticket, EscalationMatrix
from apps.y_helpdesk.models.sla_policy import SLAPolicy
from apps.y_helpdesk.models.ticket_workflow import TicketWorkflow
from apps.y_helpdesk.models.ticket_attachment import TicketAttachment
from apps.y_helpdesk.models.audit_log import TicketAuditLog
from apps.y_helpdesk.models.sla_prediction import SLAPrediction
from apps.y_helpdesk.services.priority_alert_service import PriorityAlertService
from apps.core.services.smart_assignment_service import SmartAssignmentService
from apps.peoples.models import AgentSkill


class PriorityAlertFilter(admin.SimpleListFilter):
    """Filter tickets by priority alert level."""
    title = 'Priority Level'
    parameter_name = 'alert'
    
    def lookups(self, request, model_admin):
        return [
            ('urgent', '🔴 Urgent (need attention now)'),
            ('soon', '🟠 Soon (check on these)'),
            ('ok', '🟢 On Track'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'urgent':
            return queryset.filter(
                id__in=SLAPrediction.objects.filter(
                    item_type='Ticket',
                    risk_level='high'
                ).values_list('item_id', flat=True)
            )
        elif self.value() == 'soon':
            return queryset.filter(
                id__in=SLAPrediction.objects.filter(
                    item_type='Ticket',
                    risk_level='medium'
                ).values_list('item_id', flat=True)
            )
        elif self.value() == 'ok':
            return queryset.filter(
                id__in=SLAPrediction.objects.filter(
                    item_type='Ticket',
                    risk_level='low'
                ).values_list('item_id', flat=True)
            )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """
    Admin interface for ticket management with visual indicators.

    Features:
    - Color-coded status and priority badges
    - Sentiment indicators
    - SLA overdue warnings
    - Quick filters for triage
    
    N+1 Query Optimization:
    - select_related: assignedtopeople, bu, createdbypeople, ticketcategory, ticketsubcategory
    - prefetch_related: workflow_history, attachments
    """

    list_display = (
        'ticketno',
        'priority_alert_badge',
        'status_badge',
        'priority_badge',
        'sentiment_indicator',
        'assignedtopeople',
        'bu',
        'created_display',
        'sla_indicator'
    )
    
    # N+1 query optimization
    list_select_related = [
        'assignedtopeople', 'bu', 'createdbypeople', 
        'ticketcategory', 'ticketsubcategory'
    ]
    list_prefetch_related = ['workflow_history', 'attachments']

    list_filter = (
        'status',
        'priority',
        PriorityAlertFilter,
        'ticketsource',
        'sentiment_label',
        'ticketcategory',
        'bu',
    )

    search_fields = (
        'ticketno',
        'ticketdesc',
        'comments',
        'assignedtopeople__peoplename',
    )

    readonly_fields = (
        'uuid',
        'version',
        'sentiment_score',
        'sentiment_label',
        'sentiment_analyzed_at',
        'emotion_detected',
        'ticketno',
        'cdtz',
        'mdtz',
        'cuser',
        'muser',
    )

    fieldsets = (
        ('Basic Information', {
            'fields': ('ticketno', 'uuid', 'ticketdesc', 'comments')
        }),
        ('Classification', {
            'fields': ('status', 'priority', 'ticketcategory', 'ticketsource')
        }),
        ('Assignment', {
            'fields': ('assignedtopeople', 'assignedtogroup', 'bu', 'client')
        }),
        ('Location & Assets', {
            'fields': ('location', 'asset'),
            'classes': ('collapse',)
        }),
        ('Sentiment Analysis', {
            'fields': ('sentiment_score', 'sentiment_label', 'emotion_detected', 'sentiment_analyzed_at'),
            'classes': ('collapse',)
        }),
        ('Multilingual', {
            'fields': ('original_language',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('version', 'cdtz', 'mdtz', 'cuser', 'muser'),
            'classes': ('collapse',)
        }),
    )

    list_per_page = 50
    date_hierarchy = 'cdtz'

    def status_badge(self, obj):
        """Colored status badge."""
        colors = {
            'NEW': '#ffc107',
            'OPEN': '#007bff',
            'ONHOLD': '#6c757d',
            'RESOLVED': '#28a745',
            'CLOSED': '#6c757d',
            'CANCELLED': '#dc3545'
        }
        return format_html(
            '<span style="background: {}; padding: 3px 8px; border-radius: 3px; '
            'color: white; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def priority_badge(self, obj):
        """Colored priority badge."""
        colors = {
            'LOW': '#28a745',
            'MEDIUM': '#ffc107',
            'HIGH': '#dc3545',
        }
        return format_html(
            '<span style="background: {}; padding: 3px 8px; border-radius: 3px; '
            'color: white; font-weight: bold;">{}</span>',
            colors.get(obj.priority, '#6c757d'),
            obj.priority
        )
    priority_badge.short_description = 'Priority'
    priority_badge.admin_order_field = 'priority'

    def sentiment_indicator(self, obj):
        """Visual sentiment indicator with score."""
        if obj.sentiment_score is None:
            return '—'

        # Color based on score (0-10 scale)
        if obj.sentiment_score < 3:
            color = '#dc3545'  # Red (very negative)
            icon = '😠'
        elif obj.sentiment_score < 5:
            color = '#fd7e14'  # Orange (negative)
            icon = '😟'
        elif obj.sentiment_score < 7:
            color = '#ffc107'  # Yellow (neutral)
            icon = '😐'
        elif obj.sentiment_score < 9:
            color = '#28a745'  # Green (positive)
            icon = '🙂'
        else:
            color = '#20c997'  # Teal (very positive)
            icon = '😊'

        return format_html(
            '<span style="color: {}; font-size: 16px;">{}</span> '
            '<span style="font-weight: bold;">{:.1f}</span>',
            color, icon, obj.sentiment_score
        )
    sentiment_indicator.short_description = 'Sentiment'
    sentiment_indicator.admin_order_field = 'sentiment_score'

    def created_display(self, obj):
        """Formatted creation date."""
        if obj.cdtz:
            delta = timezone.now() - obj.cdtz
            if delta.days == 0:
                hours = int(delta.seconds / 3600)
                if hours == 0:
                    minutes = int(delta.seconds / 60)
                    return f"{minutes}m ago"
                return f"{hours}h ago"
            elif delta.days == 1:
                return "Yesterday"
            elif delta.days < 7:
                return f"{delta.days}d ago"
            return obj.cdtz.strftime("%b %d, %Y")
        return "—"
    created_display.short_description = 'Created'
    created_display.admin_order_field = 'cdtz'

    def priority_alert_badge(self, obj):
        """Show friendly risk badge."""
        try:
            # Get related prediction
            prediction = SLAPrediction.objects.filter(
                item_type='Ticket',
                item_id=obj.id
            ).first()
            
            if prediction:
                colors = {
                    'high': '#dc3545',
                    'medium': '#ffc107',
                    'low': '#28a745',
                }
                icons = {
                    'high': '🔴',
                    'medium': '🟠',
                    'low': '🟢',
                }
                return format_html(
                    '<span style="background: {}; padding: 3px 8px; border-radius: 3px; '
                    'color: white; font-weight: bold;">{} {}</span>',
                    colors.get(prediction.risk_level, '#6c757d'),
                    icons.get(prediction.risk_level, '⚪'),
                    prediction.get_risk_level_display().replace('🟢 ', '').replace('🟠 ', '').replace('🔴 ', '')
                )
            return '—'
        except (AttributeError, ObjectDoesNotExist):  # Security: Specific exceptions instead of bare Exception
            return '—'
    priority_alert_badge.short_description = 'Alert'
    priority_alert_badge.admin_order_field = 'sla_prediction__risk_level'

    def sla_indicator(self, obj):
        """SLA status indicator."""
        try:
            workflow = obj.workflow
            if workflow and workflow.is_escalated:
                return format_html(
                    '<span style="color: #dc3545; font-weight: bold;">⚠ ESC L{}</span>',
                    workflow.escalation_level
                )
        except (AttributeError, ObjectDoesNotExist):
            pass
        return format_html('<span style="color: #28a745;">✓ OK</span>')
    sla_indicator.short_description = 'SLA'

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'assignedtopeople',
            'assignedtogroup',
            'bu',
            'client',
            'ticketcategory',
            'location',
            'asset',
            'cuser',
            'muser'
        ).prefetch_related('workflow')
    
    def change_view(self, request, object_id, **kwargs):
        """Show priority alert info and smart assignment suggestions."""
        extra_context = kwargs.get('extra_context', {})
        
        ticket = self.get_object(request, object_id)
        if ticket:
            service = PriorityAlertService()
            risk = service.check_ticket_risk(ticket)
            extra_context['priority_alert'] = risk
            
            if not ticket.assignedtopeople:
                suggestions = SmartAssignmentService.suggest_assignee(ticket)
                extra_context['assignment_suggestions'] = suggestions
        
        kwargs['extra_context'] = extra_context
        return super().change_view(request, object_id, **kwargs)
    
    @admin.action(description='🤖 Auto-assign to best person')
    def smart_assign(self, request, queryset):
        """Automatically assign tickets using smart assignment."""
        assigned = 0
        
        for ticket in queryset.filter(assignedtopeople__isnull=True):
            result = SmartAssignmentService.auto_assign(ticket)
            if result:
                assigned += 1
        
        self.message_user(
            request,
            f"✅ Assigned {assigned} tickets using smart assignment"
        )
    
    actions = ['smart_assign']


@admin.register(EscalationMatrix)
class EscalationMatrixAdmin(admin.ModelAdmin):
    """Admin interface for escalation rules."""

    list_display = (
        'id',
        'job',
        'level',
        'frequency',
        'frequencyvalue',
        'notify',
        'assignedperson',
        'assignedgroup',
    )

    list_filter = ('frequency', 'assignedperson', 'assignedgroup', 'notify')
    search_fields = ('job__jobname', 'assignedperson__peoplename', 'assignedgroup__groupname')
    list_per_page = 50

    fieldsets = (
        ('Trigger Conditions', {
            'fields': ('job', 'level', 'frequency', 'frequencyvalue')
        }),
        ('Action Configuration', {
            'fields': ('notify', 'assignedperson', 'assignedgroup')
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'job',
            'assignedperson',
            'assignedgroup'
        )


@admin.register(SLAPolicy)
class SLAPolicyAdmin(admin.ModelAdmin):
    """Admin interface for SLA policies."""

    list_display = (
        'policy_id',
        'policy_name',
        'priority',
        'client',
        'response_time_display',
        'resolution_time_display',
        'is_active',
        'exclude_weekends',
        'exclude_holidays',
    )

    list_filter = ('priority', 'is_active', 'exclude_weekends', 'exclude_holidays')
    search_fields = ('client__btname',)
    list_per_page = 50

    fieldsets = (
        ('Policy Details', {
            'fields': ('priority', 'client', 'is_active')
        }),
        ('SLA Targets', {
            'fields': (
                'response_time_minutes',
                'resolution_time_minutes',
                'escalation_threshold_minutes'
            )
        }),
        ('Business Calendar', {
            'fields': ('business_hours_start', 'business_hours_end', 'exclude_weekends', 'exclude_holidays'),
            'classes': ('collapse',)
        }),
    )

    def response_time_display(self, obj):
        """Formatted response time."""
        hours = obj.response_time_minutes / 60
        return f"{hours:.1f}h"
    response_time_display.short_description = 'Response Time'

    def resolution_time_display(self, obj):
        """Formatted resolution time."""
        hours = obj.resolution_time_minutes / 60
        return f"{hours:.1f}h"
    resolution_time_display.short_description = 'Resolution Time'

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related('client')


@admin.register(TicketWorkflow)
class TicketWorkflowAdmin(admin.ModelAdmin):
    """Admin interface for ticket workflows (read-only for debugging)."""

    list_display = (
        'ticket',
        'workflow_status',
        'escalation_level',
        'is_escalated',
        'escalation_count',
        'last_activity_display',
    )

    list_filter = ('workflow_status', 'is_escalated')
    search_fields = ('ticket__ticketno',)
    list_per_page = 50

    readonly_fields = (
        'ticket',
        'workflow_status',
        'workflow_data',
        'escalation_level',
        'is_escalated',
        'escalation_count',
        'last_escalated_at',
        'response_time_hours',
        'resolution_time_hours',
        'last_activity_at',
        'activity_count',
    )

    def has_add_permission(self, request):
        """Workflows are auto-created, not manually added."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Workflows should not be deleted."""
        return False

    def last_activity_display(self, obj):
        """Formatted last activity time."""
        if obj.last_activity_at:
            delta = timezone.now() - obj.last_activity_at
            if delta.days == 0:
                hours = int(delta.seconds / 3600)
                if hours == 0:
                    minutes = int(delta.seconds / 60)
                    return f"{minutes}m ago"
                return f"{hours}h ago"
            return f"{delta.days}d ago"
        return "—"
    last_activity_display.short_description = 'Last Activity'

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related('ticket')


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    """Admin interface for ticket attachments with security indicators."""

    list_display = (
        'id',
        'filename',
        'ticket',
        'file_size_display',
        'scan_status_badge',
        'uploaded_by',
        'uploaded_at',
        'download_count',
    )

    list_filter = ('scan_status', 'content_type', 'uploaded_at')
    search_fields = ('filename', 'ticket__ticketno', 'uploaded_by__peoplename')
    list_per_page = 50

    readonly_fields = (
        'uuid',
        'file_size',
        'content_type',
        'uploaded_at',
        'download_count',
        'last_accessed_at',
        'scan_details',
    )

    fieldsets = (
        ('File Information', {
            'fields': ('file', 'filename', 'file_size', 'content_type')
        }),
        ('Association', {
            'fields': ('ticket', 'uploaded_by')
        }),
        ('Security Scan', {
            'fields': ('is_scanned', 'scan_status', 'scan_details'),
        }),
        ('Usage Tracking', {
            'fields': ('download_count', 'last_accessed_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('uuid', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )

    def file_size_display(self, obj):
        """Formatted file size."""
        size_kb = obj.file_size / 1024
        if size_kb < 1024:
            return f"{size_kb:.1f} KB"
        size_mb = size_kb / 1024
        return f"{size_mb:.1f} MB"
    file_size_display.short_description = 'File Size'

    def scan_status_badge(self, obj):
        """Visual scan status indicator."""
        colors = {
            'pending': '#ffc107',
            'clean': '#28a745',
            'infected': '#dc3545',
            'error': '#6c757d',
        }
        icons = {
            'pending': '⏳',
            'clean': '✅',
            'infected': '⛔',
            'error': '⚠️',
        }
        return format_html(
            '<span style="color: {}; font-size: 16px;">{}</span> <span>{}</span>',
            colors.get(obj.scan_status, '#6c757d'),
            icons.get(obj.scan_status, '?'),
            obj.get_scan_status_display()
        )
    scan_status_badge.short_description = 'Scan Status'

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete attachments."""
        return request.user.is_superuser

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related('ticket', 'uploaded_by')


@admin.register(TicketAuditLog)
class TicketAuditLogAdmin(admin.ModelAdmin):
    """Admin interface for audit logs (read-only for compliance)."""

    list_display = (
        'event_id',
        'event_type',
        'severity_badge',
        'user',
        'ticket',
        'timestamp',
        'integrity_status',
    )

    list_filter = ('event_category', 'severity_level', 'timestamp')
    search_fields = ('event_id', 'ticket__ticketno', 'user__peoplename', 'event_type')
    list_per_page = 50

    readonly_fields = (
        'event_id',
        'correlation_id',
        'event_type',
        'event_category',
        'severity_level',
        'user',
        'tenant',
        'ticket',
        'event_data',
        'old_values',
        'new_values',
        'ip_address',
        'user_agent',
        'request_method',
        'request_path',
        'timestamp',
        'processed_at',
        'integrity_hash',
        'previous_hash',
        'retention_until',
        'is_archived',
    )

    def has_add_permission(self, request):
        """Audit logs are auto-created, not manually added."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Audit logs are immutable."""
        return False

    def has_change_permission(self, request, obj=None):
        """Audit logs are immutable."""
        return False

    def severity_badge(self, obj):
        """Visual severity indicator."""
        colors = {
            'debug': '#6c757d',
            'info': '#17a2b8',
            'warning': '#ffc107',
            'error': '#dc3545',
            'critical': '#721c24',
        }
        return format_html(
            '<span style="background: {}; padding: 2px 6px; border-radius: 3px; '
            'color: white; font-size: 11px;">{}</span>',
            colors.get(obj.severity_level, '#6c757d'),
            obj.severity_level.upper()
        )
    severity_badge.short_description = 'Severity'

    def integrity_status(self, obj):
        """Check integrity hash."""
        try:
            is_valid = obj.verify_integrity()
            if is_valid:
                return format_html('<span style="color: #28a745;">✓ Valid</span>')
            return format_html('<span style="color: #dc3545;">⚠ Tampered</span>')
        except (AttributeError, ValueError, TypeError):
            return format_html('<span style="color: #6c757d;">? Unknown</span>')
    integrity_status.short_description = 'Integrity'

    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related('ticket', 'user', 'tenant')


@admin.register(SLAPrediction)
class SLAPredictionAdmin(admin.ModelAdmin):
    """Admin interface for Priority Alerts."""
    
    list_display = (
        'id',
        'item_display',
        'risk_badge',
        'confidence',
        'is_acknowledged',
        'acknowledged_by',
        'last_checked',
    )
    
    list_filter = (
        'risk_level',
        'is_acknowledged',
        'item_type',
    )
    
    search_fields = (
        'item_id',
    )
    
    readonly_fields = (
        'item_type',
        'item_id',
        'risk_factors_display',
        'suggested_actions_display',
        'last_checked',
        'alert_sent_at',
    )
    
    fieldsets = (
        ('Item Information', {
            'fields': ('item_type', 'item_id')
        }),
        ('Risk Assessment', {
            'fields': (
                'risk_level',
                'confidence',
                'risk_factors_display',
                'suggested_actions_display',
                'last_checked'
            )
        }),
        ('User Interaction', {
            'fields': (
                'is_acknowledged',
                'acknowledged_by',
                'acknowledged_at',
                'alert_sent_at'
            )
        }),
    )
    
    list_per_page = 50
    date_hierarchy = 'last_checked'
    
    def item_display(self, obj):
        """Show item type and ID."""
        return f"{obj.item_type} #{obj.item_id}"
    item_display.short_description = 'Item'
    
    def risk_badge(self, obj):
        """Show friendly risk badge."""
        colors = {
            'high': '#dc3545',
            'medium': '#ffc107',
            'low': '#28a745',
        }
        return format_html(
            '<span style="background: {}; padding: 3px 8px; border-radius: 3px; '
            'color: white; font-weight: bold;">{}</span>',
            colors.get(obj.risk_level, '#6c757d'),
            obj.get_risk_level_display()
        )
    risk_badge.short_description = 'Risk Level'
    risk_badge.admin_order_field = 'risk_level'
    
    def risk_factors_display(self, obj):
        """Display risk factors in readable format."""
        if not obj.risk_factors:
            return "No factors recorded"
        
        html = '<ul style="margin: 0; padding-left: 20px;">'
        for factor in obj.risk_factors:
            severity_color = {
                'high': '#dc3545',
                'medium': '#ffc107',
                'low': '#28a745',
            }.get(factor.get('severity', 'low'), '#6c757d')
            
            html += f'<li style="color: {severity_color};">'
            html += f'{factor.get("icon", "")} {factor.get("message", "")}'
            html += '</li>'
        html += '</ul>'
        return mark_safe(html)
    risk_factors_display.short_description = 'Risk Factors'
    
    def suggested_actions_display(self, obj):
        """Display suggested actions in readable format."""
        if not obj.suggested_actions:
            return "No suggestions"
        
        html = '<ol style="margin: 0; padding-left: 20px;">'
        for action in sorted(obj.suggested_actions, key=lambda x: x.get('priority', 99)):
            html += f'<li>{action.get("icon", "")} {action.get("text", "")}</li>'
        html += '</ol>'
        return mark_safe(html)
    suggested_actions_display.short_description = 'Suggested Actions'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('acknowledged_by')
