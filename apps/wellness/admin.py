"""
Django Admin Configuration for Wellness App

Comprehensive admin interface for managing wellness education content,
user progress, and content interactions with evidence-based verification.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import WellnessContent, WellnessUserProgress, WellnessContentInteraction


@admin.register(WellnessContent)
class WellnessContentAdmin(admin.ModelAdmin):
    """Comprehensive admin for wellness education content"""

    list_display = (
        'title', 'category', 'evidence_level', 'priority_score',
        'delivery_context', 'is_active', 'verification_status', 'interaction_count'
    )

    list_filter = (
        'category', 'delivery_context', 'content_level', 'evidence_level',
        'is_active', 'workplace_specific', 'field_worker_relevant', 'tenant'
    )

    search_fields = ('title', 'summary', 'content', 'source_name', 'tags')

    readonly_fields = (
        'id', 'created_at', 'updated_at', 'verification_status',
        'interaction_summary', 'effectiveness_metrics'
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
                      'citations', 'last_verified_date', 'verification_status'),
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

    def verification_status(self, obj):
        """Display verification status with color coding"""
        if obj.needs_verification:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠️ NEEDS VERIFICATION</span>'
            )
        elif obj.is_high_evidence:
            return format_html(
                '<span style="color: green;">✓ High Evidence ({}) </span>',
                obj.get_evidence_level_display()
            )
        else:
            return format_html(
                '<span style="color: orange;">📋 {} </span>',
                obj.get_evidence_level_display()
            )
    verification_status.short_description = 'Evidence Status'

    def interaction_count(self, obj):
        """Display number of user interactions"""
        count = obj.interactions.count()
        if count > 0:
            return format_html(
                '<a href="{}?content__id__exact={}">{} interactions</a>',
                reverse('admin:wellness_wellnesscontentinteraction_changelist'),
                obj.id,
                count
            )
        return "No interactions"
    interaction_count.short_description = 'User Interactions'

    def interaction_summary(self, obj):
        """Display interaction summary statistics"""
        interactions = obj.interactions.all()
        if not interactions:
            return "No interaction data"

        total = interactions.count()
        completed = interactions.filter(interaction_type='completed').count()
        avg_rating = interactions.filter(user_rating__isnull=False).aggregate(
            avg=Avg('user_rating')
        )['avg']

        completion_rate = (completed / total * 100) if total > 0 else 0

        summary = f"Total: {total} | Completion Rate: {completion_rate:.1f}%"
        if avg_rating:
            summary += f" | Avg Rating: {avg_rating:.1f}/5"

        return summary
    interaction_summary.short_description = 'Interaction Summary'

    def effectiveness_metrics(self, obj):
        """Calculate and display content effectiveness"""
        interactions = obj.interactions.all()
        if not interactions.exists():
            return "No effectiveness data"

        # Calculate effectiveness metrics
        total = interactions.count()
        positive = interactions.filter(
            interaction_type__in=['completed', 'bookmarked', 'acted_upon', 'requested_more']
        ).count()
        negative = interactions.filter(interaction_type='dismissed').count()

        effectiveness = (positive / total * 100) if total > 0 else 0
        dismissal_rate = (negative / total * 100) if total > 0 else 0

        return f"Effectiveness: {effectiveness:.1f}% | Dismissal: {dismissal_rate:.1f}%"
    effectiveness_metrics.short_description = 'Effectiveness Metrics'

    def get_queryset(self, request):
        """Optimize queryset with interaction counts"""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('interactions').select_related('tenant', 'created_by')

    actions = ['mark_needs_verification', 'mark_verified', 'activate_content', 'deactivate_content']

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


@admin.register(WellnessUserProgress)
class WellnessUserProgressAdmin(admin.ModelAdmin):
    """Admin for user wellness progress and gamification"""

    list_display = (
        'user_display', 'current_streak', 'total_score', 'completion_rate_display',
        'last_activity_date', 'achievement_count'
    )

    list_filter = (
        'preferred_content_level', 'daily_tip_enabled', 'contextual_delivery_enabled',
        'milestone_alerts_enabled', 'current_streak', 'tenant'
    )

    search_fields = ('user__peoplename', 'user__loginid')

    readonly_fields = (
        'created_at', 'updated_at', 'completion_rate_display',
        'achievement_summary', 'progress_visualization'
    )

    fieldsets = (
        ('User Information', {
            'fields': ('user', 'tenant', 'created_at', 'updated_at')
        }),
        ('Engagement Metrics', {
            'fields': ('current_streak', 'longest_streak', 'last_activity_date',
                      'total_content_viewed', 'total_content_completed',
                      'total_time_spent_minutes', 'total_score', 'completion_rate_display')
        }),
        ('Category Progress', {
            'fields': ('mental_health_progress', 'physical_wellness_progress',
                      'workplace_health_progress', 'substance_awareness_progress',
                      'preventive_care_progress', 'progress_visualization'),
            'classes': ('collapse',)
        }),
        ('User Preferences', {
            'fields': ('preferred_content_level', 'preferred_delivery_time',
                      'enabled_categories', 'daily_tip_enabled', 'contextual_delivery_enabled')
        }),
        ('Gamification', {
            'fields': ('achievements_earned', 'milestone_alerts_enabled', 'achievement_summary'),
            'classes': ('collapse',)
        }),
    )

    def user_display(self, obj):
        """Display user name with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:peoples_people_change', args=[obj.user.id]),
            obj.user.peoplename
        )
    user_display.short_description = 'User'

    def completion_rate_display(self, obj):
        """Display completion rate as percentage"""
        rate = obj.completion_rate * 100
        color = 'green' if rate >= 70 else 'orange' if rate >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            rate
        )
    completion_rate_display.short_description = 'Completion Rate'

    def achievement_count(self, obj):
        """Display number of achievements earned"""
        count = len(obj.achievements_earned)
        if count > 0:
            return format_html(
                '<span style="color: gold;">🏆 {} achievements</span>',
                count
            )
        return "No achievements"
    achievement_count.short_description = 'Achievements'

    def achievement_summary(self, obj):
        """Display achievement summary"""
        if not obj.achievements_earned:
            return "No achievements earned yet"

        achievements_display = {
            'week_streak': '📅 Week Streak',
            'month_streak': '🗓️ Month Streak',
            'content_explorer': '🔍 Content Explorer',
            'wellness_scholar': '📚 Wellness Scholar',
        }

        displayed = []
        for achievement in obj.achievements_earned:
            display_name = achievements_display.get(achievement, achievement)
            displayed.append(display_name)

        return " | ".join(displayed)
    achievement_summary.short_description = 'Achievements Earned'

    def progress_visualization(self, obj):
        """Simple text-based progress visualization"""
        categories = {
            'Mental Health': obj.mental_health_progress,
            'Physical Wellness': obj.physical_wellness_progress,
            'Workplace Health': obj.workplace_health_progress,
            'Substance Awareness': obj.substance_awareness_progress,
            'Preventive Care': obj.preventive_care_progress,
        }

        visualization = []
        for category, score in categories.items():
            bar_length = min(score // 5, 20)  # Max 20 characters
            bar = '█' * bar_length
            visualization.append(f"{category}: {bar} ({score})")

        return format_html('<br>'.join(visualization))
    progress_visualization.short_description = 'Category Progress'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user', 'tenant')


@admin.register(WellnessContentInteraction)
class WellnessContentInteractionAdmin(admin.ModelAdmin):
    """Admin for wellness content interactions and engagement analytics"""

    list_display = (
        'user_display', 'content_title', 'interaction_type', 'engagement_score_display',
        'user_rating', 'delivery_context', 'interaction_date'
    )

    list_filter = (
        'interaction_type', 'delivery_context', 'user_rating', 'action_taken',
        'interaction_date', 'content__category'
    )

    search_fields = (
        'user__peoplename', 'content__title', 'user_feedback',
        'trigger_journal_entry__title'
    )

    readonly_fields = (
        'id', 'interaction_date', 'engagement_score_display', 'context_summary'
    )

    fieldsets = (
        ('Interaction Details', {
            'fields': ('id', 'user', 'content', 'interaction_type', 'delivery_context',
                      'interaction_date')
        }),
        ('Engagement Metrics', {
            'fields': ('time_spent_seconds', 'completion_percentage', 'user_rating',
                      'user_feedback', 'action_taken', 'engagement_score_display')
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

    def user_display(self, obj):
        """Display user name with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:peoples_people_change', args=[obj.user.id]),
            obj.user.peoplename
        )
    user_display.short_description = 'User'

    def content_title(self, obj):
        """Display content title with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:wellness_wellnesscontent_change', args=[obj.content.id]),
            obj.content.title[:50] + ('...' if len(obj.content.title) > 50 else '')
        )
    content_title.short_description = 'Content'

    def engagement_score_display(self, obj):
        """Display engagement score with color coding"""
        score = obj.engagement_score
        if score >= 4:
            color = 'green'
        elif score >= 2:
            color = 'orange'
        elif score >= 0:
            color = 'black'
        else:
            color = 'red'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            score
        )
    engagement_score_display.short_description = 'Engagement Score'

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

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'user', 'content', 'trigger_journal_entry'
        )

    # Custom actions
    actions = ['mark_high_engagement', 'export_analytics']

    def mark_high_engagement(self, request, queryset):
        """Mark interactions as high engagement examples"""
        high_engagement = queryset.filter(engagement_score__gte=4)
        count = high_engagement.count()
        self.message_user(request, f"Found {count} high engagement interactions.")
    mark_high_engagement.short_description = "Identify high engagement interactions"


# Customize admin site headers
admin.site.site_header = 'IntelliWiz Wellness Education Administration'