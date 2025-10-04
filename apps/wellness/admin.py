"""
Django Admin Configuration for Wellness App

Comprehensive admin interface for managing wellness education content,
user progress, and content interactions with evidence-based verification.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Avg, Count
from .models import (
    WellnessContent, WellnessUserProgress, WellnessContentInteraction,
    WisdomConversationTranslation, TranslationQualityFeedback
)

# Import wisdom conversation admin interfaces
from .admin.wisdom_conversation_admin import (
    ConversationThreadAdmin, WisdomConversationAdmin,
    ConversationEngagementAdmin, ConversationBookmarkAdmin
)


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


@admin.register(WisdomConversationTranslation)
class WisdomConversationTranslationAdmin(admin.ModelAdmin):
    """Comprehensive admin for wisdom conversation translations"""

    list_display = (
        'conversation_preview', 'target_language', 'quality_display', 'status_display',
        'backend_used', 'confidence_display', 'cache_hits', 'created_at', 'is_expired_display'
    )

    list_filter = (
        'target_language', 'quality_level', 'status', 'translation_backend',
        'created_at', 'is_expired',
        ('expires_at', admin.DateFieldListFilter),
        ('tenant', admin.RelatedOnlyFieldListFilter),
    )

    search_fields = (
        'original_conversation__conversation_text',
        'translated_text',
        'warning_message',
        'original_conversation__id'
    )

    readonly_fields = (
        'id', 'created_at', 'updated_at', 'source_content_hash',
        'word_count_ratio', 'performance_metrics', 'translation_preview'
    )

    fieldsets = (
        ('Translation Details', {
            'fields': ('id', 'original_conversation', 'target_language', 'status',
                      'translation_version', 'created_at', 'updated_at')
        }),
        ('Content', {
            'fields': ('translation_preview', 'warning_message'),
            'classes': ('collapse',)
        }),
        ('Quality & Performance', {
            'fields': ('quality_level', 'confidence_score', 'translation_backend',
                      'word_count_original', 'word_count_translated', 'word_count_ratio',
                      'translation_time_ms', 'performance_metrics')
        }),
        ('Caching & Access', {
            'fields': ('cache_hit_count', 'last_accessed', 'expires_at',
                      'source_content_hash'),
            'classes': ('collapse',)
        }),
        ('Review & Quality Assurance', {
            'fields': ('reviewed_by', 'review_notes'),
            'classes': ('collapse',)
        }),
        ('Error Tracking', {
            'fields': ('error_message', 'retry_count'),
            'classes': ('collapse',)
        }),
    )

    actions = [
        'mark_for_review', 'mark_as_reviewed', 'extend_cache_expiry',
        'refresh_translation', 'bulk_quality_upgrade'
    ]

    def conversation_preview(self, obj):
        """Display conversation preview with link"""
        preview = obj.original_conversation.conversation_text[:100] + "..." if len(obj.original_conversation.conversation_text) > 100 else obj.original_conversation.conversation_text
        return format_html(
            '<a href="{}" title="View original conversation">{}</a>',
            reverse('admin:wellness_wisdomconversation_change', args=[obj.original_conversation.id]),
            preview
        )
    conversation_preview.short_description = 'Original Conversation'

    def quality_display(self, obj):
        """Display quality level with color coding"""
        colors = {
            'unverified': '#ffc107',
            'reviewed': '#28a745',
            'professional': '#007bff',
            'native': '#6f42c1'
        }
        color = colors.get(obj.quality_level, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8rem;">{}</span>',
            color,
            obj.get_quality_level_display()
        )
    quality_display.short_description = 'Quality'

    def status_display(self, obj):
        """Display status with appropriate styling"""
        colors = {
            'pending': '#6c757d',
            'processing': '#fd7e14',
            'completed': '#28a745',
            'failed': '#dc3545',
            'expired': '#6c757d'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'

    def confidence_display(self, obj):
        """Display confidence score with progress bar"""
        if obj.confidence_score is None:
            return "N/A"

        percentage = obj.confidence_score * 100
        color = '#28a745' if percentage >= 80 else '#ffc107' if percentage >= 60 else '#dc3545'

        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; color: white; text-align: center; padding: 2px 0; font-size: 0.8rem;">{:.0f}%</div>'
            '</div>',
            percentage, color, percentage
        )
    confidence_display.short_description = 'Confidence'

    def is_expired_display(self, obj):
        """Display expiry status"""
        if obj.is_expired:
            return format_html('<span style="color: #dc3545;">⚠️ Expired</span>')
        elif obj.expires_at:
            days_left = (obj.expires_at - timezone.now()).days
            if days_left <= 7:
                return format_html('<span style="color: #ffc107;">⏰ {} days left</span>', days_left)
            return format_html('<span style="color: #28a745;">✓ Valid</span>')
        return "No expiry"
    is_expired_display.short_description = 'Cache Status'

    def translation_preview(self, obj):
        """Display translation preview"""
        if len(obj.translated_text) > 200:
            return obj.translated_text[:200] + "..."
        return obj.translated_text
    translation_preview.short_description = 'Translation Preview'

    def word_count_ratio(self, obj):
        """Display word count ratio"""
        ratio = obj.word_count_ratio
        if ratio:
            return f"{ratio:.2f}"
        return "N/A"
    word_count_ratio.short_description = 'Word Ratio'

    def performance_metrics(self, obj):
        """Display performance metrics"""
        metrics = obj.calculate_performance_metrics()
        return format_html(
            '<div style="font-size: 0.9rem;">'
            'Speed: {} ms<br>'
            'Cache Hits: {}<br>'
            'Backend: {}<br>'
            'Quality: {:.1f}/10'
            '</div>',
            metrics.get('translation_speed', 'N/A'),
            metrics.get('cache_efficiency', 0),
            metrics.get('backend_used', 'Unknown'),
            (metrics.get('quality_score', 0) or 0) * 10
        )
    performance_metrics.short_description = 'Performance'

    def get_queryset(self, request):
        """Optimize queryset with proper relationships"""
        return super().get_queryset(request).select_related(
            'original_conversation', 'reviewed_by', 'tenant'
        ).prefetch_related('quality_feedback')

    # Admin actions
    def mark_for_review(self, request, queryset):
        """Mark translations for human review"""
        updated = queryset.update(quality_level='unverified')
        self.message_user(request, f"Marked {updated} translations for review.")
    mark_for_review.short_description = "Mark for review"

    def mark_as_reviewed(self, request, queryset):
        """Mark translations as reviewed"""
        updated = queryset.update(quality_level='reviewed')
        self.message_user(request, f"Marked {updated} translations as reviewed.")
    mark_as_reviewed.short_description = "Mark as reviewed"

    def extend_cache_expiry(self, request, queryset):
        """Extend cache expiry by 30 days"""
        from datetime import timedelta
        new_expiry = timezone.now() + timedelta(days=30)
        updated = queryset.update(expires_at=new_expiry)
        self.message_user(request, f"Extended cache expiry for {updated} translations.")
    extend_cache_expiry.short_description = "Extend cache expiry"

    def refresh_translation(self, request, queryset):
        """Queue refresh of selected translations"""
        from .tasks import translate_conversation_async

        count = 0
        for translation in queryset:
            translate_conversation_async.delay(
                conversation_id=translation.original_conversation.id,
                target_language=translation.target_language,
                priority='manual'
            )
            count += 1

        self.message_user(request, f"Queued {count} translations for refresh.")
    refresh_translation.short_description = "Refresh translations"

    def bulk_quality_upgrade(self, request, queryset):
        """Upgrade quality level for high-confidence translations"""
        high_confidence = queryset.filter(
            confidence_score__gte=0.9,
            quality_level='unverified'
        )
        updated = high_confidence.update(quality_level='reviewed')
        self.message_user(request, f"Upgraded quality for {updated} high-confidence translations.")
    bulk_quality_upgrade.short_description = "Upgrade high-confidence translations"


@admin.register(TranslationQualityFeedback)
class TranslationQualityFeedbackAdmin(admin.ModelAdmin):
    """Admin for translation quality feedback and improvement"""

    list_display = (
        'translation_preview', 'user_display', 'feedback_type', 'quality_rating_display',
        'is_helpful', 'created_at', 'admin_response_status'
    )

    list_filter = (
        'feedback_type', 'quality_rating', 'is_helpful', 'created_at',
        ('translation__target_language', admin.ChoicesFieldListFilter),
        ('tenant', admin.RelatedOnlyFieldListFilter),
    )

    search_fields = (
        'user__peoplename', 'user__loginid',
        'feedback_text', 'suggested_translation',
        'translation__translated_text'
    )

    readonly_fields = ('id', 'created_at', 'updated_at', 'translation_info')

    fieldsets = (
        ('Feedback Details', {
            'fields': ('id', 'translation', 'user', 'feedback_type', 'created_at', 'updated_at')
        }),
        ('Quality Assessment', {
            'fields': ('quality_rating', 'feedback_text', 'suggested_translation')
        }),
        ('Translation Context', {
            'fields': ('translation_info',),
            'classes': ('collapse',)
        }),
        ('Admin Management', {
            'fields': ('is_helpful', 'admin_response')
        }),
    )

    actions = ['mark_as_helpful', 'mark_as_not_helpful', 'export_feedback_report']

    def translation_preview(self, obj):
        """Display translation preview with link"""
        preview = obj.translation.translated_text[:80] + "..." if len(obj.translation.translated_text) > 80 else obj.translation.translated_text
        return format_html(
            '<a href="{}" title="View translation">{}</a>',
            reverse('admin:wellness_wisdomconversationtranslation_change', args=[obj.translation.id]),
            preview
        )
    translation_preview.short_description = 'Translation'

    def user_display(self, obj):
        """Display user with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:peoples_people_change', args=[obj.user.id]),
            obj.user.peoplename
        )
    user_display.short_description = 'User'

    def quality_rating_display(self, obj):
        """Display quality rating with stars"""
        if obj.quality_rating:
            stars = '⭐' * obj.quality_rating + '☆' * (5 - obj.quality_rating)
            return format_html(
                '<span title="{}/5 stars">{} ({})</span>',
                obj.quality_rating,
                stars,
                obj.get_quality_rating_display()
            )
        return "No rating"
    quality_rating_display.short_description = 'Rating'

    def admin_response_status(self, obj):
        """Display admin response status"""
        if obj.admin_response:
            return format_html('<span style="color: #28a745;">✓ Responded</span>')
        return format_html('<span style="color: #ffc107;">⏳ Pending</span>')
    admin_response_status.short_description = 'Response Status'

    def translation_info(self, obj):
        """Display detailed translation information"""
        translation = obj.translation
        return format_html(
            '<div style="font-size: 0.9rem;">'
            '<strong>Language:</strong> {}<br>'
            '<strong>Quality:</strong> {}<br>'
            '<strong>Backend:</strong> {}<br>'
            '<strong>Confidence:</strong> {:.1f}%<br>'
            '<strong>Created:</strong> {}'
            '</div>',
            translation.get_target_language_display(),
            translation.get_quality_level_display(),
            translation.get_translation_backend_display(),
            (translation.confidence_score or 0) * 100,
            translation.created_at.strftime('%Y-%m-%d %H:%M')
        )
    translation_info.short_description = 'Translation Details'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'translation', 'translation__original_conversation', 'user', 'tenant'
        )

    # Admin actions
    def mark_as_helpful(self, request, queryset):
        """Mark feedback as helpful"""
        updated = queryset.update(is_helpful=True)
        self.message_user(request, f"Marked {updated} feedback items as helpful.")
    mark_as_helpful.short_description = "Mark as helpful"

    def mark_as_not_helpful(self, request, queryset):
        """Mark feedback as not helpful"""
        updated = queryset.update(is_helpful=False)
        self.message_user(request, f"Marked {updated} feedback items as not helpful.")
    mark_as_not_helpful.short_description = "Mark as not helpful"

    def export_feedback_report(self, request, queryset):
        """Export feedback report for analysis"""
        # This would generate a CSV/Excel report of feedback
        # For now, just show a message
        count = queryset.count()
        self.message_user(
            request,
            f"Feedback report for {count} items would be exported here. "
            "This feature can be implemented with django-import-export."
        )
    export_feedback_report.short_description = "Export feedback report"


# Customize admin site headers
admin.site.site_header = 'IntelliWiz Wellness Education Administration'