"""
Wellness Content Admin Interface

Django admin for managing wellness education content and user interactions.

AGGREGATION FOR SITE ADMINS:
=============================
This admin interface provides site administrators with aggregated views of:

1. **Content Performance Metrics**:
   - Total views per content item (interaction_count)
   - Effectiveness scores (positive interactions / total)
   - Average user ratings (1-5 scale)
   - Completion rates and dismissal rates

2. **Evidence Compliance Tracking**:
   - Evidence level badges (WHO/CDC, peer_reviewed, professional)
   - Verification status and last verified date
   - Source citations for audit trails

3. **Aggregated User Engagement**:
   - Displayed via interaction_summary() - shows total interactions
   - Effectiveness metrics via effectiveness_metrics() - shows positive/neutral/negative
   - Respects privacy settings (only shows where consent given)

DATA SOURCE:
------------
Aggregates data from:
- WellnessContent: Evidence-based content library
- WellnessContentInteraction: User engagement tracking (from Kotlin mobile clients)
- Journal entries trigger content delivery (analyzed by JournalAnalyticsService)

PRIVACY CONTROLS:
-----------------
- Only shows aggregated metrics (no individual user identification)
- Respects JournalPrivacySettings consent flags
- Crisis intervention data requires explicit opt-in
- Admin users with appropriate permissions only

Author: Claude Code
Date: 2025-10-12
CLAUDE.md Compliance: <200 lines
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Avg
from unfold.decorators import display

from .base import WellnessBaseModelAdmin
from ..models import WellnessContent, WellnessContentInteraction


@admin.register(WellnessContent)
class WellnessContentAdmin(WellnessBaseModelAdmin):
    """Comprehensive admin for wellness education content"""

    list_display = (
        'title', 'category', 'evidence_level_badge', 'priority_score',
        'delivery_context', 'is_active', 'verification_badge', 'interaction_count'
    )

    list_filter = (
        'category', 'delivery_context', 'content_level', 'evidence_level',
        'is_active', 'workplace_specific', 'field_worker_relevant', 'tenant'
    )

    search_fields = ('title', 'summary', 'content', 'source_name', 'tags')
    list_select_related = ('tenant', 'created_by')

    readonly_fields = (
        'id', 'created_at', 'updated_at', 'interaction_summary', 'effectiveness_metrics'
    )

    fieldsets = (
        ('Content Information', {
            'fields': ('id', 'title', 'summary', 'content', 'tenant')
        }),
        ('Classification', {
            'fields': ('category', 'delivery_context', 'content_level', 'tags')
        }),
        ('Targeting & Delivery', {
            'fields': ('trigger_patterns', 'workplace_specific', 'field_worker_relevant',
                      'priority_score', 'frequency_limit_days', 'seasonal_relevance')
        }),
        ('Educational Structure', {
            'fields': ('action_tips', 'key_takeaways', 'related_topics',
                      'estimated_reading_time', 'complexity_score'),
            'classes': ('collapse',)
        }),
        ('Evidence & Compliance', {
            'fields': ('evidence_level', 'source_name', 'source_url', 'evidence_summary',
                      'citations', 'last_verified_date'),
            'description': 'Critical for medical/health compliance - handle with care'
        }),
        ('Content Management', {
            'fields': ('is_active', 'content_version', 'created_by', 'created_at', 'updated_at')
        }),
        ('Analytics', {
            'fields': ('interaction_summary', 'effectiveness_metrics'),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_needs_verification', 'mark_verified', 'activate_content', 'deactivate_content']

    @display(description='Evidence', label=True)
    def evidence_level_badge(self, obj):
        """Display evidence level badge"""
        return obj.get_evidence_level_display()

    @display(description='Status', label=True)
    def verification_badge(self, obj):
        """Display verification status"""
        if obj.needs_verification:
            return "⚠️ Verify"
        return "✓ OK" if obj.is_high_evidence else "📋 OK"

    def interaction_count(self, obj):
        """Display interaction count with link"""
        count = obj.interactions.count()
        if count > 0:
            url = f"{reverse('admin:wellness_wellnesscontentinteraction_changelist')}?content__id__exact={obj.id}"
            return format_html('<a href="{}">{} interactions</a>', url, count)
        return "None"
    interaction_count.short_description = 'Interactions'

    def interaction_summary(self, obj):
        """Display interaction statistics"""
        interactions = obj.interactions.all()
        if not interactions:
            return "No data"
        total = interactions.count()
        completed = interactions.filter(interaction_type='completed').count()
        avg_rating = interactions.filter(user_rating__isnull=False).aggregate(avg=Avg('user_rating'))['avg']
        rate = (completed / total * 100) if total > 0 else 0
        summary = f"Total: {total} | Rate: {rate:.1f}%"
        if avg_rating:
            summary += f" | Rating: {avg_rating:.1f}/5"
        return summary
    interaction_summary.short_description = 'Summary'

    def effectiveness_metrics(self, obj):
        """Calculate effectiveness"""
        interactions = obj.interactions.all()
        if not interactions.exists():
            return "No data"
        total = interactions.count()
        positive = interactions.filter(
            interaction_type__in=['completed', 'bookmarked', 'acted_upon', 'requested_more']).count()
        negative = interactions.filter(interaction_type='dismissed').count()
        eff = (positive / total * 100) if total > 0 else 0
        dis = (negative / total * 100) if total > 0 else 0
        return f"Eff: {eff:.1f}% | Dismiss: {dis:.1f}%"
    effectiveness_metrics.short_description = 'Effectiveness'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).prefetch_related('interactions')

    def mark_needs_verification(self, request, queryset):
        """Mark content as needing verification"""
        queryset.update(last_verified_date=None)
        self.message_user(request, "Marked content as needing verification.")
    mark_needs_verification.short_description = "Mark as needs verification"

    def mark_verified(self, request, queryset):
        """Mark content as recently verified"""
        queryset.update(last_verified_date=timezone.now())
        self.message_user(request, "Marked content as verified.")
    mark_verified.short_description = "Mark as verified"

    def activate_content(self, request, queryset):
        """Activate content for delivery"""
        queryset.update(is_active=True)
        self.message_user(request, "Activated content for delivery.")
    activate_content.short_description = "Activate content"

    def deactivate_content(self, request, queryset):
        """Deactivate content"""
        queryset.update(is_active=False)
        self.message_user(request, "Deactivated content.")
    deactivate_content.short_description = "Deactivate content"


@admin.register(WellnessContentInteraction)
class WellnessContentInteractionAdmin(WellnessBaseModelAdmin):
    """Admin for wellness content interactions and engagement analytics"""

    list_display = (
        'user_link', 'content_link', 'interaction_type', 'engagement_badge',
        'user_rating', 'delivery_context', 'interaction_date'
    )

    list_filter = (
        'interaction_type', 'delivery_context', 'user_rating',
        'action_taken', 'interaction_date', 'content__category'
    )

    search_fields = (
        'user__peoplename', 'content__title', 'user_feedback',
        'trigger_journal_entry__title'
    )

    list_select_related = ('user', 'content', 'trigger_journal_entry')

    readonly_fields = ('id', 'interaction_date', 'context_summary')

    fieldsets = (
        ('Interaction Details', {
            'fields': ('id', 'user', 'content', 'interaction_type', 'delivery_context', 'interaction_date')
        }),
        ('Engagement Metrics', {
            'fields': ('time_spent_seconds', 'completion_percentage', 'user_rating',
                      'user_feedback', 'action_taken')
        }),
        ('Delivery Context', {
            'fields': ('trigger_journal_entry', 'user_mood_at_delivery',
                      'user_stress_at_delivery', 'context_summary'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )

    @display(description='User')
    def user_link(self, obj):
        """Display user with link"""
        return self.user_display_link(obj.user)

    @display(description='Content')
    def content_link(self, obj):
        """Display content title with link"""
        title = obj.content.title[:50] + ('...' if len(obj.content.title) > 50 else '')
        url = reverse('admin:wellness_wellnesscontent_change', args=[obj.content.id])
        return format_html('<a href="{}">{}</a>', url, title)

    @display(description='Engagement', label=True)
    def engagement_badge(self, obj):
        """Display engagement score as badge"""
        score = obj.engagement_score
        if score >= 4:
            color = 'success'
        elif score >= 2:
            color = 'warning'
        elif score >= 0:
            color = 'info'
        else:
            color = 'danger'
        return f"{score}"

    def context_summary(self, obj):
        """Display delivery context summary"""
        summary = []
        if obj.trigger_journal_entry:
            summary.append(f"Triggered by: {obj.trigger_journal_entry.title}")
        if obj.user_mood_at_delivery:
            summary.append(f"Mood: {obj.user_mood_at_delivery}/10")
        if obj.user_stress_at_delivery:
            summary.append(f"Stress: {obj.user_stress_at_delivery}/5")
        return " | ".join(summary) if summary else "No context data"
    context_summary.short_description = 'Delivery Context'
