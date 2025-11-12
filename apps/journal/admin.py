"""
Django Admin Configuration for Journal App

Provides comprehensive admin interface for managing journal entries,
media attachments, and privacy settings with proper security controls.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import JournalEntry, JournalMediaAttachment, JournalPrivacySettings


class JournalMediaAttachmentInline(admin.TabularInline):
    """Inline admin for journal media attachments"""
    model = JournalMediaAttachment
    extra = 0
    fields = ('media_type', 'file', 'caption', 'display_order', 'is_hero_image', 'sync_status')
    readonly_fields = ('file_size', 'mime_type', 'created_at')


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    """Comprehensive admin for journal entries with privacy controls"""

    inlines = [JournalMediaAttachmentInline]

    list_display = (
        'title', 'user_display', 'entry_type', 'privacy_scope',
        'mood_rating', 'stress_level', 'timestamp', 'sync_status'
    )

    list_filter = (
        'entry_type', 'privacy_scope', 'sync_status', 'is_draft',
        'mood_rating', 'stress_level', 'created_at', 'tenant'
    )

    search_fields = ('title', 'content', 'user__peoplename', 'location_site_name')

    readonly_fields = (
        'id', 'created_at', 'updated_at', 'version', 'last_sync_timestamp',
        'user_wellbeing_summary', 'privacy_warning'
    )

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'tenant', 'entry_type', 'title', 'subtitle', 'content')
        }),
        ('Timing & Location', {
            'fields': ('timestamp', 'duration_minutes', 'location_site_name',
                      'location_address', 'location_coordinates')
        }),
        ('Wellbeing Metrics', {
            'fields': ('mood_rating', 'mood_description', 'stress_level', 'energy_level',
                      'stress_triggers', 'coping_strategies', 'user_wellbeing_summary'),
            'classes': ('collapse',)
        }),
        ('Positive Psychology', {
            'fields': ('gratitude_items', 'daily_goals', 'affirmations',
                      'achievements', 'learnings', 'challenges'),
            'classes': ('collapse',)
        }),
        ('Work Context', {
            'fields': ('team_members', 'completion_rate', 'efficiency_score',
                      'quality_score', 'items_processed'),
            'classes': ('collapse',)
        }),
        ('Privacy & Sharing', {
            'fields': ('privacy_scope', 'consent_given', 'consent_timestamp',
                      'sharing_permissions', 'privacy_warning'),
            'description': 'Handle with care - this contains sensitive personal data'
        }),
        ('Categorization', {
            'fields': ('tags', 'priority', 'severity', 'is_bookmarked')
        }),
        ('System Fields', {
            'fields': ('sync_status', 'mobile_id', 'version', 'last_sync_timestamp',
                      'is_draft', 'is_deleted', 'created_at', 'updated_at', 'metadata'),
            'classes': ('collapse',)
        }),
    )

    list_per_page = 50

    def user_display(self, obj):
        """Display user name with link to user profile"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:peoples_people_change', args=[obj.user.id]),
            obj.user.peoplename
        )
    user_display.short_description = 'User'

    def user_wellbeing_summary(self, obj):
        """Display wellbeing metrics summary"""
        if not obj.has_wellbeing_metrics:
            return "No wellbeing data"

        summary = []
        if obj.mood_rating:
            summary.append(f"Mood: {obj.mood_rating}/10")
        if obj.stress_level:
            summary.append(f"Stress: {obj.stress_level}/5")
        if obj.energy_level:
            summary.append(f"Energy: {obj.energy_level}/10")

        return " | ".join(summary)
    user_wellbeing_summary.short_description = 'Wellbeing Summary'

    def privacy_warning(self, obj):
        """Display privacy warning for sensitive entries"""
        if obj.privacy_scope == 'private' and obj.is_wellbeing_entry:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠️ CONFIDENTIAL WELLBEING DATA</span>'
            )
        elif obj.privacy_scope == 'private':
            return format_html(
                '<span style="color: orange;">🔒 Private Entry</span>'
            )
        return format_html(
            '<span style="color: green;">👥 Shared Entry</span>'
        )
    privacy_warning.short_description = 'Privacy Status'

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related('user', 'tenant').prefetch_related('media_attachments')

    def has_change_permission(self, request, obj=None):
        """Restrict editing of private entries to owners and superusers"""
        if obj and obj.privacy_scope == 'private' and not request.user.is_superuser:
            # Only allow owner to edit private entries
            return obj.user.id == request.user.id
        return super().has_change_permission(request, obj)


@admin.register(JournalMediaAttachment)
class JournalMediaAttachmentAdmin(admin.ModelAdmin):
    """Admin for journal media attachments"""

    list_display = (
        'original_filename', 'media_type', 'journal_entry_title',
        'file_size_display', 'is_hero_image', 'sync_status'
    )

    list_filter = ('media_type', 'sync_status', 'is_hero_image', 'created_at')

    search_fields = (
        'original_filename', 'journal_entry__title',
        'journal_entry__user__peoplename'
    )

    readonly_fields = ('id', 'file_size', 'mime_type', 'created_at', 'updated_at')

    fields = (
        'journal_entry', 'media_type', 'file', 'original_filename',
        'mime_type', 'file_size_display', 'caption', 'display_order',
        'is_hero_image', 'mobile_id', 'sync_status', 'is_deleted'
    )

    list_per_page = 50

    def journal_entry_title(self, obj):
        """Display journal entry title with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:journal_journalentry_change', args=[obj.journal_entry.id]),
            obj.journal_entry.title
        )
    journal_entry_title.short_description = 'Journal Entry'

    def file_size_display(self, obj):
        """Display file size in human readable format"""
        if obj.file_size:
            if obj.file_size > 1024 * 1024:  # MB
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
            elif obj.file_size > 1024:  # KB
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size} bytes"
        return "Unknown"
    file_size_display.short_description = 'File Size'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('journal_entry', 'journal_entry__user')


@admin.register(JournalPrivacySettings)
class JournalPrivacySettingsAdmin(admin.ModelAdmin):
    """Admin for user privacy settings"""

    list_display = (
        'user_display', 'default_privacy_scope', 'wellbeing_sharing_consent',
        'analytics_consent', 'data_retention_days', 'updated_at'
    )

    list_filter = (
        'default_privacy_scope', 'wellbeing_sharing_consent',
        'manager_access_consent', 'analytics_consent', 'crisis_intervention_consent'
    )

    search_fields = ('user__peoplename', 'user__loginid')

    readonly_fields = ('consent_timestamp', 'updated_at', 'consent_summary')

    fieldsets = (
        ('User Information', {
            'fields': ('user', 'consent_timestamp', 'updated_at')
        }),
        ('Default Privacy Settings', {
            'fields': ('default_privacy_scope',)
        }),
        ('Consent Management', {
            'fields': ('wellbeing_sharing_consent', 'manager_access_consent',
                      'analytics_consent', 'crisis_intervention_consent', 'consent_summary'),
            'description': 'These settings control how the user\'s data can be used'
        }),
        ('Data Retention', {
            'fields': ('data_retention_days', 'auto_delete_enabled'),
        }),
    )

    list_per_page = 50

    def user_display(self, obj):
        """Display user name with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:peoples_people_change', args=[obj.user.id]),
            obj.user.peoplename
        )
    user_display.short_description = 'User'

    def consent_summary(self, obj):
        """Display consent summary"""
        consents = []
        if obj.wellbeing_sharing_consent:
            consents.append("Wellbeing Sharing")
        if obj.manager_access_consent:
            consents.append("Manager Access")
        if obj.analytics_consent:
            consents.append("Analytics")
        if obj.crisis_intervention_consent:
            consents.append("Crisis Intervention")

        if consents:
            return format_html(
                '<span style="color: green;">✓ {}</span>',
                ", ".join(consents)
            )
        return format_html(
            '<span style="color: orange;">No consents given</span>'
        )
    consent_summary.short_description = 'Active Consents'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user')


# NOTE: Admin site branding set centrally in intelliwiz_config/urls_optimized.py to avoid conflicts
# admin.site.site_header = 'IntelliWiz Journal & Wellness Administration'
# admin.site.site_title = 'Journal Admin'
# admin.site.index_title = 'Journal & Wellness Management'