"""
Agent Skill Admin - Management interface for agent skills.

Following CLAUDE.md:
- Admin < 100 lines per ModelAdmin
- Clear, user-friendly displays
"""

from django.contrib import admin
from django.utils.html import format_html
from apps.peoples.models import AgentSkill


@admin.register(AgentSkill)
class AgentSkillAdmin(admin.ModelAdmin):
    """
    Admin interface for managing agent skills.
    
    Features:
    - Visual star ratings
    - Certification badges
    - Performance metrics
    - Tenant filtering
    """
    
    list_display = [
        'agent',
        'category',
        'skill_stars',
        'certified_badge',
        'total_handled',
        'success_rate_display',
        'last_used'
    ]
    
    list_filter = ['skill_level', 'certified', 'category']
    search_fields = ['agent__username', 'agent__first_name', 'agent__last_name', 'category__taname']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('agent', 'category', 'skill_level', 'certified')
        }),
        ('Performance Metrics', {
            'fields': ('total_handled', 'avg_completion_time', 'success_rate', 'last_used'),
            'classes': ('collapse',)
        }),
        ('Tenant', {
            'fields': ('tenant',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['total_handled', 'avg_completion_time', 'success_rate', 'last_used']
    
    list_per_page = 50
    
    @admin.display(description='Skill Level')
    def skill_stars(self, obj):
        """Display skill level as stars."""
        stars = '⭐' * obj.skill_level
        return format_html('<span style="font-size: 18px">{}</span>', stars)
    
    @admin.display(description='Certified')
    def certified_badge(self, obj):
        """Display certification status."""
        if obj.certified:
            return format_html(
                '<span style="background: #28a745; padding: 3px 8px; '
                'border-radius: 3px; color: white; font-weight: bold;">✓ Certified</span>'
            )
        return '—'
    
    @admin.display(description='Success Rate')
    def success_rate_display(self, obj):
        """Display success rate with color coding."""
        if obj.success_rate:
            color = 'success' if obj.success_rate >= 90 else 'warning'
            bg_color = '#28a745' if obj.success_rate >= 90 else '#ffc107'
            return format_html(
                '<span style="background: {}; padding: 3px 8px; '
                'border-radius: 3px; color: white; font-weight: bold;">{:.1f}%</span>',
                bg_color, obj.success_rate
            )
        return '—'
    
    def get_queryset(self, request):
        """Optimize queryset to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related('agent', 'category', 'tenant')
