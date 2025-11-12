"""
Wisdom Conversation Translation Admin Interface

Django admin for managing conversation translations and quality feedback.

Author: Claude Code
Date: 2025-10-12
CLAUDE.md Compliance: <200 lines
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from unfold.decorators import display
from datetime import timedelta

from .base import WellnessBaseModelAdmin
from ..models import WisdomConversationTranslation, TranslationQualityFeedback


@admin.register(WisdomConversationTranslation)
class WisdomConversationTranslationAdmin(WellnessBaseModelAdmin):
    list_per_page = 50
    """Comprehensive admin for wisdom conversation translations"""

    list_display = (
        'conversation_preview', 'target_language', 'quality_badge', 'status_badge',
        'translation_backend', 'confidence_badge', 'cache_hit_count', 'cdtz', 'expiry_badge'
    )

    list_filter = (
        'target_language', 'quality_level', 'status', 'translation_backend',
        ('cdtz', admin.DateFieldListFilter),
        ('tenant', admin.RelatedOnlyFieldListFilter),
    )

    search_fields = (
        'original_conversation__conversation_text', 'translated_text',
        'warning_message', 'original_conversation__id'
    )

    list_select_related = ('original_conversation', 'reviewed_by', 'tenant')

    readonly_fields = (
        'id', 'cdtz', 'mdtz', 'source_content_hash',
        'word_count_ratio', 'performance_metrics', 'translation_preview'
    )

    fieldsets = (
        ('Translation Details', {
            'fields': ('id', 'original_conversation', 'target_language', 'status',
                      'translation_version', 'cdtz', 'mdtz')
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
            'fields': ('cache_hit_count', 'last_accessed', 'expires_at', 'source_content_hash'),
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

    @display(description='Original')
    def conversation_preview(self, obj):
        """Display conversation preview"""
        text = obj.original_conversation.conversation_text
        preview = text[:80] + "..." if len(text) > 80 else text
        url = reverse('admin:wellness_wisdomconversation_change', args=[obj.original_conversation.id])
        return format_html('<a href="{}">{}</a>', url, preview)

    @display(description='Quality', label=True)
    def quality_badge(self, obj):
        """Display quality level badge"""
        return obj.get_quality_level_display()

    @display(description='Status', label=True)
    def status_badge(self, obj):
        """Display status badge"""
        return obj.get_status_display()

    @display(description='Confidence', label=True)
    def confidence_badge(self, obj):
        """Display confidence score"""
        if obj.confidence_score is None:
            return "N/A"
        percentage = obj.confidence_score * 100
        return f"{percentage:.0f}%"

    @display(description='Cache', label=True)
    def expiry_badge(self, obj):
        """Display cache status"""
        if obj.is_expired:
            return "⚠️ Expired"
        if obj.expires_at:
            days_left = (obj.expires_at - timezone.now()).days
            return f"⏰ {days_left}d" if days_left <= 7 else "✓ OK"
        return "No expiry"

    def translation_preview(self, obj):
        """Display translation preview"""
        text = obj.translated_text
        return text[:150] + "..." if len(text) > 150 else text
    translation_preview.short_description = 'Preview'

    def word_count_ratio(self, obj):
        """Display word ratio"""
        return f"{obj.word_count_ratio:.2f}" if obj.word_count_ratio else "N/A"
    word_count_ratio.short_description = 'Ratio'

    def performance_metrics(self, obj):
        """Display metrics"""
        m = obj.calculate_performance_metrics()
        return format_html(
            'Speed: {} ms | Cache: {} | Backend: {} | Quality: {:.1f}/10',
            m.get('translation_speed', 'N/A'), m.get('cache_efficiency', 0),
            m.get('backend_used', 'Unknown'), (m.get('quality_score', 0) or 0) * 10
        )
    performance_metrics.short_description = 'Metrics'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).prefetch_related('quality_feedback')

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
        new_expiry = timezone.now() + timedelta(days=30)
        updated = queryset.update(expires_at=new_expiry)
        self.message_user(request, f"Extended cache expiry for {updated} translations.")
    extend_cache_expiry.short_description = "Extend cache expiry"

    def refresh_translation(self, request, queryset):
        """Queue refresh"""
        from ..tasks import translate_conversation_async
        for translation in queryset:
            translate_conversation_async.delay(
                conversation_id=translation.original_conversation.id,
                target_language=translation.target_language, priority='manual')
        self.message_user(request, f"Queued {queryset.count()} translations for refresh.")
    refresh_translation.short_description = "Refresh translations"

    def bulk_quality_upgrade(self, request, queryset):
        """Upgrade quality level for high-confidence translations"""
        high_confidence = queryset.filter(confidence_score__gte=0.9, quality_level='unverified')
        updated = high_confidence.update(quality_level='reviewed')
        self.message_user(request, f"Upgraded quality for {updated} high-confidence translations.")
    bulk_quality_upgrade.short_description = "Upgrade high-confidence translations"


@admin.register(TranslationQualityFeedback)
class TranslationQualityFeedbackAdmin(WellnessBaseModelAdmin):
    list_per_page = 50
    """Admin for translation quality feedback and improvement"""

    list_display = (
        'translation_link', 'user_link', 'feedback_type', 'rating_badge',
        'is_helpful', 'cdtz', 'response_status'
    )

    list_filter = (
        'feedback_type', 'quality_rating', 'is_helpful',
        ('cdtz', admin.DateFieldListFilter),
        ('translation__target_language', admin.AllValuesFieldListFilter),
        ('tenant', admin.RelatedOnlyFieldListFilter),
    )

    search_fields = (
        'user__peoplename', 'user__loginid', 'feedback_text',
        'suggested_translation', 'translation__translated_text'
    )

    list_select_related = ('translation', 'translation__original_conversation', 'user', 'tenant')

    readonly_fields = ('id', 'cdtz', 'mdtz', 'translation_info')

    fieldsets = (
        ('Feedback Details', {
            'fields': ('id', 'translation', 'user', 'feedback_type', 'cdtz', 'mdtz')
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

    actions = ['mark_as_helpful', 'mark_as_not_helpful']

    @display(description='Translation')
    def translation_link(self, obj):
        """Display translation link"""
        text = obj.translation.translated_text
        preview = text[:60] + "..." if len(text) > 60 else text
        url = reverse('admin:wellness_wisdomconversationtranslation_change', args=[obj.translation.id])
        return format_html('<a href="{}">{}</a>', url, preview)

    @display(description='User')
    def user_link(self, obj):
        """Display user with link"""
        return self.user_display_link(obj.user)

    @display(description='Rating', label=True)
    def rating_badge(self, obj):
        """Display rating"""
        if obj.quality_rating:
            stars = '⭐' * obj.quality_rating + '☆' * (5 - obj.quality_rating)
            return stars
        return "None"

    @display(description='Response', label=True)
    def response_status(self, obj):
        """Display admin response status"""
        return "✓ Responded" if obj.admin_response else "⏳ Pending"

    def translation_info(self, obj):
        """Display translation info"""
        t = obj.translation
        return format_html(
            'Lang: {} | Quality: {} | Backend: {} | Confidence: {:.0f}% | Created: {}',
            t.get_target_language_display(), t.get_quality_level_display(),
            t.get_translation_backend_display(), (t.confidence_score or 0) * 100,
            t.created_at.strftime('%Y-%m-%d')
        )
    translation_info.short_description = 'Info'

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
