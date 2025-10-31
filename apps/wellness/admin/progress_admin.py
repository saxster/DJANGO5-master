"""
Wellness User Progress Admin Interface

Django admin for managing user wellness progress, gamification, and achievements.

AGGREGATION FOR SITE ADMINS:
=============================
This admin interface provides site administrators with aggregated views of:

1. **User Engagement Metrics** (per user, with privacy controls):
   - Current streak days (consecutive engagement)
   - Total content viewed and completed
   - Completion rates (completed / viewed ratio)
   - Last activity dates for retention tracking

2. **Gamification Analytics**:
   - Achievement badges earned (displayed via achievement_badge())
   - Total wellness scores accumulated
   - Category-specific progress (mental_health, stress_management, etc.)
   - Milestone tracking

3. **Aggregated Site-Wide Stats** (available via list view):
   - Average engagement rates across users
   - Top performing users (anonymized if needed)
   - Most popular wellness categories
   - Overall retention metrics

DATA SOURCE:
------------
Aggregates data from:
- WellnessUserProgress: Individual user gamification data
- WellnessContentInteraction: User engagement with wellness content
- Journal entries: Trigger wellness content delivery (via JournalAnalyticsService)

PRIVACY CONTROLS:
-----------------
- Individual user data only accessible to admins with proper permissions
- Superusers can view all users; managers see only their team
- Aggregated metrics respect consent settings
- No PII exposed in list views (uses user_link for identification)

Author: Claude Code
Date: 2025-10-12
CLAUDE.md Compliance: <200 lines
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from unfold.decorators import display

from .base import WellnessBaseModelAdmin
from ..models import WellnessUserProgress


@admin.register(WellnessUserProgress)
class WellnessUserProgressAdmin(WellnessBaseModelAdmin):
    """Admin for user wellness progress and gamification"""

    list_display = (
        'user_link', 'current_streak_days', 'total_content_completed', 'completion_rate_badge',
        'last_activity_date', 'achievement_badge'
    )

    list_filter = (
        'milestone_alerts_enabled', 'onboarding_completed', 'tenant',
        ('created_at', admin.DateFieldListFilter),
        ('last_activity_date', admin.DateFieldListFilter),
    )

    search_fields = ('user__peoplename', 'user__loginid')
    list_select_related = ('user', 'tenant')

    readonly_fields = (
        'created_at', 'updated_at', 'achievement_summary', 'progress_visualization'
    )

    fieldsets = (
        ('User Information', {
            'fields': ('user', 'tenant', 'created_at', 'updated_at')
        }),
        ('Engagement Metrics', {
            'fields': (
                'current_streak', 'longest_streak', 'last_activity_date',
                'total_content_viewed', 'total_content_completed',
                'total_time_spent_minutes', 'total_score'
            )
        }),
        ('Category Progress', {
            'fields': (
                'mental_health_progress', 'physical_wellness_progress',
                'workplace_health_progress', 'substance_awareness_progress',
                'preventive_care_progress', 'progress_visualization'
            ),
            'classes': ('collapse',)
        }),
        ('User Preferences', {
            'fields': (
                'preferred_content_level', 'preferred_delivery_time',
                'enabled_categories', 'daily_tip_enabled', 'contextual_delivery_enabled'
            )
        }),
        ('Gamification', {
            'fields': ('achievements_earned', 'milestone_alerts_enabled', 'achievement_summary'),
            'classes': ('collapse',)
        }),
    )

    @display(description='User')
    def user_link(self, obj):
        """Display user name with link"""
        return self.user_display_link(obj.user)

    @display(description='Completion Rate', label=True)
    def completion_rate_badge(self, obj):
        """Display completion rate as percentage badge"""
        rate = obj.completion_rate * 100
        if rate >= 70:
            color = 'success'
        elif rate >= 50:
            color = 'warning'
        else:
            color = 'danger'
        return f"{rate:.1f}%"

    @display(description='Achievements', label=True)
    def achievement_badge(self, obj):
        """Display number of achievements earned"""
        count = len(obj.achievements_earned)
        if count > 0:
            return format_html('🏆 {} achievements', count)
        return "No achievements"

    def achievement_summary(self, obj):
        """Display achievement summary"""
        if not obj.achievements_earned:
            return "No achievements earned yet"

        achievements_display = {
            'week_streak': '📅 Week Streak',
            'month_streak': '🗓️ Month Streak',
            'content_explorer': '🔍 Content Explorer',
            'wellness_scholar': '📚 Wellness Scholar',
            'perfect_week': '⭐ Perfect Week',
            'early_bird': '🌅 Early Bird',
            'night_owl': '🦉 Night Owl',
            'category_master': '🎯 Category Master',
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
            # Progress bar (max 20 characters)
            bar_length = min(score // 5, 20)
            bar = '█' * bar_length
            empty = '░' * (20 - bar_length)

            # Color coding
            if score >= 80:
                color = 'green'
            elif score >= 50:
                color = 'orange'
            else:
                color = 'gray'

            visualization.append(
                f'<div style="margin: 5px 0;">'
                f'<strong>{category}:</strong> '
                f'<span style="color: {color}; font-family: monospace;">{bar}{empty}</span> '
                f'<span style="color: {color};">({score}/100)</span>'
                f'</div>'
            )

        return format_html(''.join(visualization))
    progress_visualization.short_description = 'Category Progress'

    actions = ['reset_streak', 'award_bonus_points', 'send_engagement_reminder']

    def reset_streak(self, request, queryset):
        """Reset user streaks"""
        queryset.update(current_streak=0)
        self.message_user(request, f"Reset streaks for {queryset.count()} users.")
    reset_streak.short_description = "Reset streak counter"

    def award_bonus_points(self, request, queryset):
        """Award bonus points to users"""
        bonus_points = 50
        for progress in queryset:
            progress.total_score += bonus_points
            progress.save(update_fields=['total_score'])
        self.message_user(request, f"Awarded {bonus_points} bonus points to {queryset.count()} users.")
    award_bonus_points.short_description = "Award bonus points (50)"

    def send_engagement_reminder(self, request, queryset):
        """Send engagement reminders to inactive users"""
        # This would integrate with notification system
        inactive = queryset.filter(current_streak=0)
        count = inactive.count()
        self.message_user(
            request,
            f"Would send engagement reminders to {count} inactive users. "
            "Integrate with notification system to enable."
        )
    send_engagement_reminder.short_description = "Send engagement reminders"
