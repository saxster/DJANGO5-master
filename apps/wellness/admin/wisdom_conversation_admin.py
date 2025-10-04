"""
Wisdom Conversation Admin Interface

Django admin interface for managing wisdom conversations, threads, engagements,
and bookmarks. Provides comprehensive tools for content moderation, analytics,
and conversation quality management.
"""

from django.contrib import admin
from django.contrib.admin import register
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg, Q
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import render
import csv
import json

from ..models.wisdom_conversations import (
    ConversationThread, WisdomConversation, ConversationEngagement, ConversationBookmark
)

User = get_user_model()


class ConversationEngagementInline(admin.TabularInline):
    """Inline admin for conversation engagements"""
    model = ConversationEngagement
    extra = 0
    readonly_fields = ('engagement_date', 'engagement_type', 'effectiveness_rating', 'time_spent_seconds')
    fields = ('engagement_type', 'engagement_date', 'effectiveness_rating', 'time_spent_seconds', 'user_reflection_note')

    def has_add_permission(self, request, obj=None):
        return False


class ConversationBookmarkInline(admin.TabularInline):
    """Inline admin for conversation bookmarks"""
    model = ConversationBookmark
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('user', 'category', 'personal_note', 'reminder_enabled', 'created_at')


@register(ConversationThread)
class ConversationThreadAdmin(admin.ModelAdmin):
    """Admin interface for conversation threads"""

    list_display = (
        'title', 'user_link', 'thread_type', 'status', 'conversation_count',
        'first_conversation_date', 'last_conversation_date', 'priority_level'
    )

    list_filter = (
        'thread_type', 'status', 'priority_level', 'narrative_style',
        'first_conversation_date', 'last_conversation_date'
    )

    search_fields = ('title', 'user__peoplename', 'user__email', 'description')

    readonly_fields = (
        'id', 'conversation_count', 'first_conversation_date',
        'last_conversation_date', 'created_at', 'updated_at'
    )

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'tenant', 'title', 'description')
        }),
        ('Thread Configuration', {
            'fields': ('thread_type', 'status', 'priority_level', 'narrative_style')
        }),
        ('Statistics', {
            'fields': ('conversation_count', 'first_conversation_date', 'last_conversation_date'),
            'classes': ('collapse',)
        }),
        ('Personalization', {
            'fields': ('personalization_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['update_thread_stats', 'export_thread_data', 'archive_threads']

    def user_link(self, obj):
        """Link to user in admin"""
        if obj.user:
            url = reverse('admin:peoples_people_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.peoplename or obj.user.loginid)
        return '-'
    user_link.short_description = 'User'

    def update_thread_stats(self, request, queryset):
        """Action to update thread statistics"""
        updated = 0
        for thread in queryset:
            thread.update_conversation_stats()
            updated += 1

        self.message_user(request, f'Updated statistics for {updated} threads.')
    update_thread_stats.short_description = 'Update thread statistics'

    def export_thread_data(self, request, queryset):
        """Export thread data as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="conversation_threads.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Title', 'User', 'Thread Type', 'Status', 'Conversation Count',
            'First Conversation', 'Last Conversation', 'Priority Level'
        ])

        for thread in queryset:
            writer.writerow([
                thread.id, thread.title, thread.user.peoplename or thread.user.loginid,
                thread.get_thread_type_display(), thread.get_status_display(),
                thread.conversation_count,
                thread.first_conversation_date.strftime('%Y-%m-%d') if thread.first_conversation_date else '',
                thread.last_conversation_date.strftime('%Y-%m-%d') if thread.last_conversation_date else '',
                thread.priority_level
            ])

        return response
    export_thread_data.short_description = 'Export thread data'

    def archive_threads(self, request, queryset):
        """Archive selected threads"""
        queryset.update(status='archived')
        self.message_user(request, f'Archived {queryset.count()} threads.')
    archive_threads.short_description = 'Archive selected threads'


@register(WisdomConversation)
class WisdomConversationAdmin(admin.ModelAdmin):
    """Admin interface for wisdom conversations"""

    list_display = (
        'conversation_preview', 'user_link', 'thread_link', 'conversation_date',
        'conversation_tone', 'source_type', 'word_count', 'engagement_count',
        'effectiveness_score', 'is_milestone_conversation'
    )

    list_filter = (
        'conversation_tone', 'source_type', 'is_milestone_conversation',
        'conversation_date', 'thread__thread_type'
    )

    search_fields = (
        'conversation_text', 'user__peoplename', 'user__email',
        'thread__title', 'contextual_bridge_text'
    )

    readonly_fields = (
        'id', 'word_count', 'estimated_reading_time_seconds',
        'sequence_number', 'created_at', 'updated_at',
        'engagement_summary', 'conversation_preview_full'
    )

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'tenant', 'thread', 'conversation_date')
        }),
        ('Content', {
            'fields': ('conversation_preview_full', 'conversation_text', 'contextual_bridge_text')
        }),
        ('Configuration', {
            'fields': ('conversation_tone', 'source_type', 'is_milestone_conversation')
        }),
        ('Source Information', {
            'fields': ('source_intervention_delivery', 'source_journal_entry', 'bridges_from_conversation'),
            'classes': ('collapse',)
        }),
        ('Analytics', {
            'fields': (
                'word_count', 'estimated_reading_time_seconds', 'sequence_number',
                'personalization_score', 'engagement_summary'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('conversation_metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [ConversationEngagementInline, ConversationBookmarkInline]

    actions = [
        'regenerate_conversations', 'export_conversation_data',
        'mark_as_milestone', 'update_personalization_scores'
    ]

    def conversation_preview(self, obj):
        """Short preview of conversation text"""
        preview = obj.conversation_text[:100] + '...' if len(obj.conversation_text) > 100 else obj.conversation_text
        return preview
    conversation_preview.short_description = 'Preview'

    def conversation_preview_full(self, obj):
        """Full conversation text preview for detail view"""
        return format_html('<div style="max-height: 200px; overflow-y: scroll; border: 1px solid #ccc; padding: 10px;">{}</div>', obj.conversation_text)
    conversation_preview_full.short_description = 'Conversation Text Preview'

    def user_link(self, obj):
        """Link to user in admin"""
        if obj.user:
            url = reverse('admin:peoples_people_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.peoplename or obj.user.loginid)
        return '-'
    user_link.short_description = 'User'

    def thread_link(self, obj):
        """Link to thread in admin"""
        if obj.thread:
            url = reverse('admin:wellness_conversationthread_change', args=[obj.thread.pk])
            return format_html('<a href="{}">{}</a>', url, obj.thread.title)
        return '-'
    thread_link.short_description = 'Thread'

    def engagement_count(self, obj):
        """Count of engagements for this conversation"""
        return obj.engagements.count()
    engagement_count.short_description = 'Engagements'

    def effectiveness_score(self, obj):
        """Average effectiveness rating"""
        avg_score = obj.engagements.aggregate(avg_score=Avg('effectiveness_rating'))['avg_score']
        if avg_score:
            return f"{avg_score:.1f}/5"
        return '-'
    effectiveness_score.short_description = 'Effectiveness'

    def engagement_summary(self, obj):
        """Summary of engagement metrics"""
        engagements = obj.engagements.all()
        if not engagements:
            return 'No engagements'

        total = engagements.count()
        avg_rating = engagements.aggregate(avg_rating=Avg('effectiveness_rating'))['avg_rating']
        bookmarks = obj.bookmarks.count()

        summary = f"Total: {total}"
        if avg_rating:
            summary += f" | Avg Rating: {avg_rating:.1f}/5"
        if bookmarks:
            summary += f" | Bookmarks: {bookmarks}"

        return summary
    engagement_summary.short_description = 'Engagement Summary'

    def regenerate_conversations(self, request, queryset):
        """Regenerate selected conversations"""
        from ..services.wisdom_conversation_generator import WisdomConversationGenerator

        generator = WisdomConversationGenerator()
        regenerated = 0

        for conversation in queryset:
            if conversation.source_intervention_delivery:
                try:
                    # Delete existing conversation
                    old_id = conversation.id
                    conversation.delete()

                    # Generate new conversation
                    new_conversation = generator.generate_conversation_from_delivery(
                        conversation.source_intervention_delivery,
                        conversation.thread
                    )

                    if new_conversation:
                        regenerated += 1

                except Exception as e:
                    self.message_user(request, f'Error regenerating conversation {old_id}: {e}', level='ERROR')

        self.message_user(request, f'Regenerated {regenerated} conversations.')
    regenerate_conversations.short_description = 'Regenerate selected conversations'

    def export_conversation_data(self, request, queryset):
        """Export conversation data as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="wisdom_conversations.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'User', 'Thread', 'Date', 'Tone', 'Source Type', 'Word Count',
            'Reading Time (s)', 'Engagement Count', 'Is Milestone', 'Personalization Score'
        ])

        for conversation in queryset:
            writer.writerow([
                conversation.id, conversation.user.peoplename or conversation.user.loginid,
                conversation.thread.title, conversation.conversation_date.strftime('%Y-%m-%d %H:%M'),
                conversation.get_conversation_tone_display(), conversation.get_source_type_display(),
                conversation.word_count, conversation.estimated_reading_time_seconds,
                conversation.engagements.count(), conversation.is_milestone_conversation,
                conversation.personalization_score
            ])

        return response
    export_conversation_data.short_description = 'Export conversation data'

    def mark_as_milestone(self, request, queryset):
        """Mark selected conversations as milestones"""
        queryset.update(is_milestone_conversation=True)
        self.message_user(request, f'Marked {queryset.count()} conversations as milestones.')
    mark_as_milestone.short_description = 'Mark as milestone conversations'

    def update_personalization_scores(self, request, queryset):
        """Update personalization scores based on engagement"""
        updated = 0

        for conversation in queryset:
            # Calculate new score based on engagement effectiveness
            avg_rating = conversation.engagements.aggregate(
                avg_rating=Avg('effectiveness_rating')
            )['avg_rating']

            if avg_rating:
                # Adjust personalization score based on average rating
                if avg_rating >= 4.0:
                    new_score = min(1.0, conversation.personalization_score + 0.1)
                elif avg_rating <= 2.0:
                    new_score = max(0.0, conversation.personalization_score - 0.1)
                else:
                    new_score = conversation.personalization_score

                if new_score != conversation.personalization_score:
                    conversation.personalization_score = new_score
                    conversation.save(update_fields=['personalization_score'])
                    updated += 1

        self.message_user(request, f'Updated personalization scores for {updated} conversations.')
    update_personalization_scores.short_description = 'Update personalization scores'


@register(ConversationEngagement)
class ConversationEngagementAdmin(admin.ModelAdmin):
    """Admin interface for conversation engagements"""

    list_display = (
        'user_link', 'conversation_link', 'engagement_type', 'engagement_date',
        'effectiveness_rating', 'time_spent_seconds', 'access_context'
    )

    list_filter = (
        'engagement_type', 'effectiveness_rating', 'device_type',
        'access_context', 'engagement_date'
    )

    search_fields = (
        'user__peoplename', 'user__email', 'conversation__conversation_text',
        'user_reflection_note'
    )

    readonly_fields = ('id', 'engagement_date')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'conversation', 'engagement_type', 'engagement_date')
        }),
        ('Engagement Metrics', {
            'fields': (
                'time_spent_seconds', 'scroll_percentage', 'effectiveness_rating',
                'user_reflection_note'
            )
        }),
        ('Context', {
            'fields': ('device_type', 'access_context', 'engagement_metadata'),
            'classes': ('collapse',)
        }),
    )

    actions = ['export_engagement_data', 'analyze_engagement_patterns']

    def user_link(self, obj):
        """Link to user in admin"""
        if obj.user:
            url = reverse('admin:peoples_people_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.peoplename or obj.user.loginid)
        return '-'
    user_link.short_description = 'User'

    def conversation_link(self, obj):
        """Link to conversation in admin"""
        if obj.conversation:
            url = reverse('admin:wellness_wisdomconversation_change', args=[obj.conversation.pk])
            preview = obj.conversation.conversation_text[:50] + '...'
            return format_html('<a href="{}" title="{}">{}</a>', url, obj.conversation.conversation_text, preview)
        return '-'
    conversation_link.short_description = 'Conversation'

    def export_engagement_data(self, request, queryset):
        """Export engagement data as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="conversation_engagements.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'User', 'Engagement Type', 'Date', 'Effectiveness Rating',
            'Time Spent (s)', 'Scroll %', 'Device Type', 'Access Context'
        ])

        for engagement in queryset:
            writer.writerow([
                engagement.id, engagement.user.peoplename or engagement.user.loginid,
                engagement.get_engagement_type_display(), engagement.engagement_date.strftime('%Y-%m-%d %H:%M'),
                engagement.effectiveness_rating or '', engagement.time_spent_seconds,
                engagement.scroll_percentage, engagement.get_device_type_display(),
                engagement.get_access_context_display()
            ])

        return response
    export_engagement_data.short_description = 'Export engagement data'

    def analyze_engagement_patterns(self, request, queryset):
        """Analyze engagement patterns"""
        # This could redirect to a custom view with detailed analytics
        self.message_user(request, 'Engagement pattern analysis feature coming soon.')
    analyze_engagement_patterns.short_description = 'Analyze engagement patterns'


@register(ConversationBookmark)
class ConversationBookmarkAdmin(admin.ModelAdmin):
    """Admin interface for conversation bookmarks"""

    list_display = (
        'user_link', 'conversation_link', 'category', 'reminder_enabled',
        'reminder_frequency_days', 'created_at'
    )

    list_filter = (
        'category', 'reminder_enabled', 'reminder_frequency_days', 'created_at'
    )

    search_fields = (
        'user__peoplename', 'user__email', 'personal_note',
        'conversation__conversation_text'
    )

    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'conversation', 'category')
        }),
        ('Notes and Reminders', {
            'fields': (
                'personal_note', 'reminder_enabled', 'reminder_frequency_days',
                'last_reminder_sent'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['export_bookmark_data', 'send_reminders']

    def user_link(self, obj):
        """Link to user in admin"""
        if obj.user:
            url = reverse('admin:peoples_people_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.peoplename or obj.user.loginid)
        return '-'
    user_link.short_description = 'User'

    def conversation_link(self, obj):
        """Link to conversation in admin"""
        if obj.conversation:
            url = reverse('admin:wellness_wisdomconversation_change', args=[obj.conversation.pk])
            preview = obj.conversation.conversation_text[:50] + '...'
            return format_html('<a href="{}" title="{}">{}</a>', url, obj.conversation.conversation_text, preview)
        return '-'
    conversation_link.short_description = 'Conversation'

    def export_bookmark_data(self, request, queryset):
        """Export bookmark data as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="conversation_bookmarks.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'User', 'Category', 'Personal Note', 'Reminder Enabled',
            'Reminder Frequency', 'Last Reminder', 'Created Date'
        ])

        for bookmark in queryset:
            writer.writerow([
                bookmark.id, bookmark.user.peoplename or bookmark.user.loginid,
                bookmark.get_category_display(), bookmark.personal_note,
                bookmark.reminder_enabled, bookmark.reminder_frequency_days,
                bookmark.last_reminder_sent.strftime('%Y-%m-%d') if bookmark.last_reminder_sent else '',
                bookmark.created_at.strftime('%Y-%m-%d')
            ])

        return response
    export_bookmark_data.short_description = 'Export bookmark data'

    def send_reminders(self, request, queryset):
        """Send reminders for selected bookmarks"""
        # This would integrate with the notification system
        self.message_user(request, 'Bookmark reminder feature coming soon.')
    send_reminders.short_description = 'Send bookmark reminders'


# Additional admin views for analytics and management

class WisdomConversationAnalyticsView:
    """Custom admin view for conversation analytics"""

    def analytics_view(self, request):
        """Display conversation analytics dashboard"""

        # Get basic statistics
        total_conversations = WisdomConversation.objects.count()
        total_users = User.objects.filter(wisdom_conversations__isnull=False).distinct().count()
        total_threads = ConversationThread.objects.count()

        # Get engagement statistics
        engagement_stats = ConversationEngagement.objects.aggregate(
            total_engagements=Count('id'),
            avg_effectiveness=Avg('effectiveness_rating'),
            avg_time_spent=Avg('time_spent_seconds')
        )

        # Get conversation statistics by type and tone
        conversation_by_tone = WisdomConversation.objects.values('conversation_tone').annotate(
            count=Count('id')
        ).order_by('-count')

        conversation_by_source = WisdomConversation.objects.values('source_type').annotate(
            count=Count('id')
        ).order_by('-count')

        context = {
            'title': 'Wisdom Conversations Analytics',
            'total_conversations': total_conversations,
            'total_users': total_users,
            'total_threads': total_threads,
            'engagement_stats': engagement_stats,
            'conversation_by_tone': conversation_by_tone,
            'conversation_by_source': conversation_by_source,
        }

        return render(request, 'admin/wellness/conversation_analytics.html', context)


# Register custom admin site configurations if needed
admin.site.site_header = "Wellness Administration"
admin.site.site_title = "Wellness Admin Portal"
admin.site.index_title = "Welcome to Wellness Administration"