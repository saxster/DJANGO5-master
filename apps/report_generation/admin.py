"""
Django Admin Interface for Report Generation

Provides comprehensive admin interface for managing templates, reports,
exemplars, and viewing learning statistics.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg

from apps.report_generation.models import (
    ReportTemplate,
    GeneratedReport,
    ReportAIInteraction,
    ReportQualityMetrics,
    ReportExemplar,
    ReportIncidentTrend,
)


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    """Admin interface for report templates."""
    
    list_display = [
        'name', 'category', 'is_system_template', 'is_active',
        'version', 'created_by', 'approved_by', 'created_at'
    ]
    list_filter = ['category', 'is_system_template', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'is_active', 'version')
        }),
        ('Configuration', {
            'fields': ('schema', 'questioning_strategy', 'quality_gates'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('is_system_template', 'created_by', 'approved_by', 'approved_at', 'tenant'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Set tenant and creator."""
        if not change:
            obj.tenant = request.user.tenant
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class ReportAIInteractionInline(admin.TabularInline):
    """Inline for AI interactions."""
    model = ReportAIInteraction
    extra = 0
    readonly_fields = ['question', 'answer', 'question_type', 'iteration', 'created_at']
    can_delete = False
    max_num = 20
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    """Admin interface for generated reports with quality insights."""
    
    list_display = [
        'title', 'template_link', 'author', 'status_badge',
        'quality_badge', 'is_exemplar', 'created_at'
    ]
    list_filter = [
        'status', 'template__category', 'is_exemplar',
        'created_at', 'quality_score'
    ]
    search_fields = ['title', 'author__first_name', 'author__last_name']
    readonly_fields = [
        'quality_score', 'completeness_score', 'clarity_score',
        'created_at', 'updated_at', 'submitted_at', 'reviewed_at'
    ]
    inlines = [ReportAIInteractionInline]
    
    fieldsets = (
        ('Report Information', {
            'fields': ('title', 'template', 'author', 'status')
        }),
        ('Related Entity', {
            'fields': ('related_content_type', 'related_object_id'),
            'classes': ('collapse',)
        }),
        ('Report Data', {
            'fields': ('report_data',),
            'classes': ('collapse',)
        }),
        ('Quality Metrics', {
            'fields': ('quality_score', 'completeness_score', 'clarity_score'),
        }),
        ('Review Information', {
            'fields': ('submitted_at', 'reviewed_by', 'reviewed_at', 'supervisor_feedback'),
            'classes': ('collapse',)
        }),
        ('Learning', {
            'fields': ('is_exemplar', 'exemplar_category'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_exemplar', 'recalculate_quality']
    
    def template_link(self, obj):
        """Link to template."""
        url = reverse('admin:report_generation_reporttemplate_change', args=[obj.template.id])
        return format_html('<a href="{}">{}</a>', url, obj.template.name)
    template_link.short_description = 'Template'
    
    def status_badge(self, obj):
        """Colored status badge."""
        colors = {
            'draft': 'gray',
            'pending_review': 'orange',
            'approved': 'green',
            'rejected': 'red',
            'archived': 'lightgray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def quality_badge(self, obj):
        """Colored quality score badge."""
        score = obj.quality_score
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}/100</span>',
            color, score
        )
    quality_badge.short_description = 'Quality'
    
    def mark_as_exemplar(self, request, queryset):
        """Bulk action to mark reports as exemplar."""
        count = 0
        for report in queryset.filter(status='approved', quality_score__gte=80):
            report.is_exemplar = True
            report.save()
            count += 1
        
        self.message_user(request, f'{count} reports marked as exemplar')
    mark_as_exemplar.short_description = 'Mark as exemplar (approved, quality >= 80)'
    
    def recalculate_quality(self, request, queryset):
        """Recalculate quality metrics for selected reports."""
        from apps.report_generation.services import QualityGateService
        
        count = 0
        for report in queryset:
            QualityGateService.calculate_quality_metrics(report)
            count += 1
        
        self.message_user(request, f'Recalculated quality for {count} reports')
    recalculate_quality.short_description = 'Recalculate quality metrics'


@admin.register(ReportQualityMetrics)
class ReportQualityMetricsAdmin(admin.ModelAdmin):
    """Admin interface for detailed quality metrics."""
    
    list_display = [
        'report', 'completeness_score', 'clarity_score',
        'readability_score', 'actionability_score', 'causal_chain_strength'
    ]
    list_filter = ['completeness_score', 'clarity_score', 'readability_score']
    search_fields = ['report__title']
    readonly_fields = [
        'report', 'completeness_score', 'clarity_score',
        'readability_score', 'jargon_density', 'assumption_count',
        'causal_chain_strength', 'actionability_score',
        'improvement_suggestions', 'jargon_examples', 'missing_details'
    ]
    
    def has_add_permission(self, request):
        return False


@admin.register(ReportExemplar)
class ReportExemplarAdmin(admin.ModelAdmin):
    """Admin interface for exemplar reports."""
    
    list_display = [
        'report', 'exemplar_category', 'narrative_quality',
        'root_cause_depth', 'approved_by', 'times_referenced'
    ]
    list_filter = ['exemplar_category', 'narrative_quality', 'root_cause_depth', 'approval_date']
    search_fields = ['report__title', 'why_exemplar']
    readonly_fields = ['approval_date', 'times_referenced']
    
    fieldsets = (
        ('Exemplar Information', {
            'fields': ('report', 'exemplar_category', 'why_exemplar')
        }),
        ('Learning Points', {
            'fields': ('learning_points', 'demonstrates_frameworks')
        }),
        ('Quality Ratings', {
            'fields': ('narrative_quality', 'root_cause_depth')
        }),
        ('Metadata', {
            'fields': ('approved_by', 'approval_date', 'times_referenced'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReportIncidentTrend)
class ReportIncidentTrendAdmin(admin.ModelAdmin):
    """Admin interface for incident trends."""
    
    list_display = [
        'trend_type', 'pattern_summary', 'severity_badge',
        'occurrence_count', 'probability_badge', 'is_active', 'is_addressed'
    ]
    list_filter = [
        'trend_type', 'severity_level', 'is_active',
        'is_addressed', 'first_occurrence'
    ]
    search_fields = ['pattern_description']
    readonly_fields = [
        'occurrence_count', 'first_occurrence', 'last_occurrence',
        'created_at', 'updated_at'
    ]
    filter_horizontal = ['related_reports']
    
    fieldsets = (
        ('Trend Information', {
            'fields': ('trend_type', 'pattern_description', 'occurrence_count')
        }),
        ('Risk Assessment', {
            'fields': ('severity_level', 'predicted_recurrence_probability')
        }),
        ('Recommendations', {
            'fields': ('recommended_actions',)
        }),
        ('Related Reports', {
            'fields': ('related_reports',),
            'classes': ('collapse',)
        }),
        ('Timeline', {
            'fields': ('first_occurrence', 'last_occurrence'),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('is_active', 'is_addressed', 'addressed_by', 'addressed_at')
        }),
    )
    
    def pattern_summary(self, obj):
        """Truncated pattern description."""
        return obj.pattern_description[:60] + '...' if len(obj.pattern_description) > 60 else obj.pattern_description
    pattern_summary.short_description = 'Pattern'
    
    def severity_badge(self, obj):
        """Colored severity badge."""
        colors = {1: 'lightblue', 2: 'yellow', 3: 'orange', 4: 'darkorange', 5: 'red'}
        color = colors.get(obj.severity_level, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">Level {}</span>',
            color, obj.severity_level
        )
    severity_badge.short_description = 'Severity'
    
    def probability_badge(self, obj):
        """Colored probability badge."""
        prob = obj.predicted_recurrence_probability
        if prob >= 0.7:
            color = 'red'
            label = 'High'
        elif prob >= 0.4:
            color = 'orange'
            label = 'Medium'
        else:
            color = 'green'
            label = 'Low'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{} ({}%)</span>',
            color, label, int(prob * 100)
        )
    probability_badge.short_description = 'Recurrence Probability'


# Custom admin site configuration
admin.site.site_header = "Intelligent Report Generation Admin"
admin.site.site_title = "Report Generation Admin"
admin.site.index_title = "Report Generation Management"
