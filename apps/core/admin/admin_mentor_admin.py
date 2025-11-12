"""
Admin Mentor Admin Configuration

Django admin interface for managing AI mentor sessions and tips.
"""

from django.contrib import admin
from django.utils.html import format_html
from apps.core.models.admin_mentor import AdminMentorSession, AdminMentorTip


@admin.register(AdminMentorSession)
class AdminMentorSessionAdmin(admin.ModelAdmin):
    """Admin interface for mentor sessions"""
    
    list_display = [
        'admin_user',
        'page_context_short',
        'skill_level',
        'session_start',
        'tasks_completed',
        'time_saved_display',
        'efficiency_badge'
    ]
    
    list_filter = [
        'skill_level',
        'session_start',
        'tenant'
    ]
    
    search_fields = [
        'admin_user__username',
        'admin_user__first_name',
        'admin_user__last_name',
        'page_context'
    ]
    
    readonly_fields = [
        'session_start',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('admin_user', 'tenant', 'skill_level')
        }),
        ('Session Details', {
            'fields': ('page_context', 'session_start', 'session_end')
        }),
        ('Learning Tracking', {
            'fields': ('features_used', 'features_shown')
        }),
        ('Interactions', {
            'fields': ('questions_asked', 'suggestions_shown', 'suggestions_followed')
        }),
        ('Efficiency Metrics', {
            'fields': ('time_saved_estimate', 'tasks_completed', 'shortcuts_used')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def page_context_short(self, obj):
        """Show shortened page context"""
        if len(obj.page_context) > 50:
            return obj.page_context[:47] + '...'
        return obj.page_context
    page_context_short.short_description = 'Page'
    
    def time_saved_display(self, obj):
        """Display time saved in friendly format"""
        minutes = obj.time_saved_estimate // 60
        if minutes > 60:
            hours = minutes // 60
            return f"{hours}h {minutes % 60}m"
        return f"{minutes}m"
    time_saved_display.short_description = 'Time Saved'
    
    def efficiency_badge(self, obj):
        """Display efficiency score as colored badge"""
        score = min(obj.time_saved_estimate // 60, 100)
        
        if score >= 75:
            color = '#10b981'
            label = 'High'
        elif score >= 50:
            color = '#f59e0b'
            label = 'Medium'
        else:
            color = '#6b7280'
            label = 'Low'
        
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 12px; font-weight: bold;">{}</span>',
            color,
            label
        )
    efficiency_badge.short_description = 'Efficiency'


@admin.register(AdminMentorTip)
class AdminMentorTipAdmin(admin.ModelAdmin):
    """Admin interface for mentor tips"""
    
    list_display = [
        'tip_title',
        'trigger_context',
        'tip_type',
        'priority',
        'show_frequency',
        'active_badge'
    ]
    
    list_filter = [
        'active',
        'tip_type',
        'show_frequency',
        'priority',
        'tenant'
    ]
    
    search_fields = [
        'tip_title',
        'tip_content',
        'trigger_context'
    ]
    
    list_editable = ['active']
    
    fieldsets = (
        ('Tip Information', {
            'fields': ('tip_title', 'tip_content', 'tip_type', 'active')
        }),
        ('Trigger Configuration', {
            'fields': ('trigger_context', 'condition', 'show_frequency', 'priority')
        }),
        ('Action', {
            'fields': ('action_button_text', 'action_url')
        }),
        ('Tenant', {
            'fields': ('tenant',)
        })
    )
    
    def active_badge(self, obj):
        """Display active status as badge"""
        if obj.active:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 4px 12px; '
                'border-radius: 12px; font-size: 12px; font-weight: bold;">Active</span>'
            )
        return format_html(
            '<span style="background: #6b7280; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 12px; font-weight: bold;">Inactive</span>'
        )
    active_badge.short_description = 'Status'
    
    actions = ['activate_tips', 'deactivate_tips']
    
    def activate_tips(self, request, queryset):
        """Bulk activate tips"""
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} tips activated.')
    activate_tips.short_description = 'Activate selected tips'
    
    def deactivate_tips(self, request, queryset):
        """Bulk deactivate tips"""
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} tips deactivated.')
    deactivate_tips.short_description = 'Deactivate selected tips'
