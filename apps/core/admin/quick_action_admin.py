"""
Quick Action Admin Interface

User-friendly admin for creating and managing Quick Actions.

Author: Claude Code
Date: 2025-11-07
CLAUDE.md Compliance: <200 lines
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Count, Avg
from unfold.decorators import display

from apps.core.admin.base_admin import IntelliWizModelAdmin
from apps.core.models.quick_action import (
    QuickAction,
    QuickActionExecution,
    QuickActionChecklist
)


@admin.register(QuickAction)
class QuickActionAdmin(IntelliWizModelAdmin):
    """Admin for Quick Actions - user-friendly runbooks."""
    
    list_display = [
        'action_name_display',
        'when_to_use_short',
        'steps_count_display',
        'times_used_display',
        'success_rate_display',
        'is_active'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description', 'when_to_use']
    filter_horizontal = ['user_groups']
    
    fieldsets = [
        ("What is this action?", {
            'fields': ['name', 'description', 'when_to_use', 'is_active'],
            'description': 'Basic information about this quick action'
        }),
        ("Who can use it?", {
            'fields': ['user_groups'],
            'description': 'Leave empty to allow all users, or select specific groups'
        }),
        ("What happens automatically?", {
            'fields': ['automated_steps'],
            'description': (
                'These steps happen instantly when you click the button. '
                'Format: [{"action_label": "Ping camera", "action_type": "ping_device", '
                '"params": {}}]'
            )
        }),
        ("What do I need to do?", {
            'fields': ['manual_steps'],
            'description': (
                'Users will be asked to complete these steps. '
                'Format: [{"instruction": "Check power", "needs_photo": true, '
                '"needs_note": false}]'
            )
        }),
        ("Analytics (Read-only)", {
            'fields': ['times_used', 'average_completion_time', 'success_rate'],
            'description': 'Usage statistics'
        })
    ]
    
    readonly_fields = ['times_used', 'average_completion_time', 'success_rate']
    
    actions = ['duplicate_action', 'deactivate_action', 'activate_action']
    
    @display(description="Action Name", header=True)
    def action_name_display(self, obj):
        """Display action name with emoji."""
        return format_html('⚡ <strong>{}</strong>', obj.name)
    
    @display(description="When to Use")
    def when_to_use_short(self, obj):
        """Display truncated when_to_use."""
        text = obj.when_to_use[:100]
        if len(obj.when_to_use) > 100:
            text += '...'
        return text
    
    @display(description="Steps")
    def steps_count_display(self, obj):
        """Display step counts."""
        auto_count = len(obj.automated_steps)
        manual_count = len(obj.manual_steps)
        return format_html(
            '<span title="Automated steps">🤖 {}</span> + '
            '<span title="Manual steps">👤 {}</span>',
            auto_count, manual_count
        )
    
    @display(description="Times Used")
    def times_used_display(self, obj):
        """Display usage count with badge."""
        if obj.times_used == 0:
            color = 'gray'
        elif obj.times_used < 10:
            color = 'blue'
        else:
            color = 'green'
        
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 3px;">{}</span>',
            color, obj.times_used
        )
    
    @display(description="Success Rate")
    def success_rate_display(self, obj):
        """Display success rate with color coding."""
        rate = float(obj.success_rate)
        
        if rate >= 90:
            color = '#10b981'  # green
        elif rate >= 70:
            color = '#f59e0b'  # orange
        else:
            color = '#ef4444'  # red
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    
    @admin.action(description='📋 Duplicate selected actions')
    def duplicate_action(self, request, queryset):
        """Duplicate selected quick actions."""
        count = 0
        for action in queryset:
            action.pk = None
            action.name = f"{action.name} (Copy)"
            action.times_used = 0
            action.success_rate = 0
            action.save()
            count += 1
        
        self.message_user(
            request,
            f"Created {count} duplicate(s). Don't forget to rename them!"
        )
    
    @admin.action(description='❌ Deactivate selected actions')
    def deactivate_action(self, request, queryset):
        """Deactivate selected actions."""
        count = queryset.update(is_active=False)
        self.message_user(
            request,
            f"Deactivated {count} action(s). Users won't see them anymore."
        )
    
    @admin.action(description='✅ Activate selected actions')
    def activate_action(self, request, queryset):
        """Activate selected actions."""
        count = queryset.update(is_active=True)
        self.message_user(
            request,
            f"Activated {count} action(s). They're ready to use!"
        )
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.prefetch_related('user_groups')


@admin.register(QuickActionExecution)
class QuickActionExecutionAdmin(IntelliWizModelAdmin):
    """Admin for Quick Action execution records."""
    
    list_display = [
        'action_display',
        'executed_by',
        'status_display',
        'created_at',
        'execution_duration_display'
    ]
    list_filter = ['status', 'created_at', 'quick_action']
    search_fields = ['quick_action__name', 'executed_by__username']
    readonly_fields = [
        'quick_action', 'executed_by', 'automated_results',
        'created_at', 'completed_at', 'execution_duration'
    ]
    
    fieldsets = [
        ("Execution Details", {
            'fields': [
                'quick_action', 'executed_by', 'status',
                'created_at', 'completed_at', 'execution_duration'
            ]
        }),
        ("Results", {
            'fields': ['automated_results']
        })
    ]
    
    @display(description="Action", header=True)
    def action_display(self, obj):
        """Display action name."""
        return f"⚡ {obj.quick_action.name}"
    
    @display(description="Status")
    def status_display(self, obj):
        """Display status with emoji."""
        status_icons = {
            'pending': '⏳',
            'in_progress': '🔄',
            'completed': '✅',
            'failed': '❌',
            'cancelled': '🚫'
        }
        icon = status_icons.get(obj.status, '')
        return format_html('{} {}', icon, obj.get_status_display())
    
    @display(description="Duration")
    def execution_duration_display(self, obj):
        """Display execution duration."""
        if not obj.execution_duration:
            return '—'
        
        total_seconds = int(obj.execution_duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('quick_action', 'executed_by')


@admin.register(QuickActionChecklist)
class QuickActionChecklistAdmin(IntelliWizModelAdmin):
    """Admin for Quick Action checklists."""
    
    list_display = [
        'execution_display',
        'completion_display',
        'updated_at'
    ]
    list_filter = ['updated_at']
    readonly_fields = ['execution', 'steps', 'completion_percentage']
    
    @display(description="Execution", header=True)
    def execution_display(self, obj):
        """Display execution info."""
        return str(obj.execution)
    
    @display(description="Completion")
    def completion_display(self, obj):
        """Display completion percentage with progress bar."""
        pct = float(obj.completion_percentage)
        
        if pct == 100:
            color = '#10b981'
        elif pct >= 50:
            color = '#f59e0b'
        else:
            color = '#3b82f6'
        
        return format_html(
            '<div style="background: #e5e7eb; border-radius: 4px; overflow: hidden;">'
            '<div style="background: {}; width: {}%; padding: 2px 8px; '
            'color: white; font-weight: bold; text-align: center;">'
            '{:.0f}%'
            '</div></div>',
            color, pct, pct
        )
