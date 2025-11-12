"""
Django Admin configuration for Help Center models.

Provides rich content management interfaces for:
- HelpArticle: Rich text editor, versioning, publishing workflow
- HelpCategory: Hierarchical tree management
- HelpTag: Simple tag CRUD
- HelpSearchHistory: Read-only analytics
- HelpArticleInteraction: Read-only engagement metrics
- HelpTicketCorrelation: Read-only ticket correlation

Following CLAUDE.md:
- Clean, maintainable code
- Single responsibility per admin class
- Proper filtering and search
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from apps.help_center.models import (
    HelpTag,
    HelpCategory,
    HelpArticle,
    HelpSearchHistory,
    HelpArticleInteraction,
    HelpTicketCorrelation,
)


@admin.register(HelpTag)
class HelpTagAdmin(admin.ModelAdmin):
    """Admin interface for help tags."""

    list_display = ['name', 'slug', 'tenant']
    search_fields = ['name', 'slug']
    list_filter = ['tenant']
    prepopulated_fields = {'slug': ('name',)}
    list_per_page = 50


@admin.register(HelpCategory)
class HelpCategoryAdmin(admin.ModelAdmin):
    """Admin interface for help categories with hierarchical display."""

    list_display = ['name', 'parent', 'display_order', 'is_active', 'article_count_display', 'tenant']
    list_filter = ['is_active', 'tenant', 'parent']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['display_order', 'is_active']
    ordering = ['display_order', 'name']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'parent', 'tenant')
        }),
        ('Display Settings', {
            'fields': ('icon', 'color', 'display_order', 'is_active')
        }),
    )

    list_per_page = 50

    def article_count_display(self, obj):
        """Show count of published articles."""
        from django.db.models import Q
        count = HelpArticle.objects.filter(
            Q(category=obj),
            status=HelpArticle.Status.PUBLISHED
        ).count()
        return format_html('<span style="color: #28a745;">{}</span>', count)

    article_count_display.short_description = 'Published Articles'


class HelpArticleTagInline(admin.TabularInline):
    """Inline for managing article tags."""

    model = HelpArticle.tags.through
    extra = 1
    verbose_name = 'Tag'
    verbose_name_plural = 'Tags'


@admin.register(HelpArticle)
class HelpArticleAdmin(admin.ModelAdmin):
    """
    Admin interface for help articles with rich editor.

    Features:
    - Rich text editor for content (configured in Media class)
    - Publishing workflow (Draft → Review → Published)
    - Versioning support
    - Analytics display (views, helpful ratio)
    """

    list_display = [
        'title',
        'category',
        'status_badge',
        'difficulty_level',
        'view_count',
        'helpful_ratio_display',
        'version',
        'published_date',
        'is_stale_badge',
    ]

    list_filter = [
        'status',
        'difficulty_level',
        'category',
        'tenant',
        'published_date',
        'created_at',
    ]

    search_fields = ['title', 'summary', 'content', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_date'

    readonly_fields = [
        'view_count',
        'helpful_count',
        'not_helpful_count',
        'helpful_ratio_display',
        'version',
        'created_at',
        'updated_at',
        'is_stale_badge',
    ]

    filter_horizontal = ['tags']

    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'summary', 'content', 'category', 'tags')
        }),
        ('Targeting & Difficulty', {
            'fields': ('difficulty_level', 'target_roles')
        }),
        ('Publishing', {
            'fields': ('status', 'version', 'previous_version', 'published_date', 'last_reviewed_date')
        }),
        ('Analytics', {
            'fields': ('view_count', 'helpful_count', 'not_helpful_count', 'helpful_ratio_display', 'is_stale_badge'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'last_updated_by', 'tenant', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['publish_articles', 'archive_articles', 'mark_for_review']

    list_per_page = 50

    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'DRAFT': '#6c757d',
            'REVIEW': '#ffc107',
            'PUBLISHED': '#28a745',
            'ARCHIVED': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = 'Status'

    def helpful_ratio_display(self, obj):
        """Display helpful ratio as percentage with color."""
        ratio = obj.helpful_ratio
        percentage = int(ratio * 100)

        if percentage >= 70:
            color = '#28a745'  # Green
        elif percentage >= 50:
            color = '#ffc107'  # Yellow
        else:
            color = '#dc3545'  # Red

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            percentage
        )

    helpful_ratio_display.short_description = 'Helpful Ratio'

    def is_stale_badge(self, obj):
        """Display stale status badge."""
        if obj.is_stale:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px;">NEEDS UPDATE</span>'
            )
        return format_html(
            '<span style="color: #28a745;">✓ Current</span>'
        )

    is_stale_badge.short_description = 'Freshness'

    def publish_articles(self, request, queryset):
        """Bulk action to publish articles."""
        updated = 0
        for article in queryset:
            if article.status == HelpArticle.Status.DRAFT:
                article.status = HelpArticle.Status.PUBLISHED
                article.published_date = timezone.now()
                article.last_updated_by = request.user
                article.save()
                updated += 1

        self.message_user(request, f'{updated} article(s) published successfully.')

    publish_articles.short_description = 'Publish selected articles'

    def archive_articles(self, request, queryset):
        """Bulk action to archive articles."""
        updated = queryset.update(status=HelpArticle.Status.ARCHIVED)
        self.message_user(request, f'{updated} article(s) archived.')

    archive_articles.short_description = 'Archive selected articles'

    def mark_for_review(self, request, queryset):
        """Bulk action to mark articles for review."""
        updated = queryset.update(status=HelpArticle.Status.REVIEW)
        self.message_user(request, f'{updated} article(s) marked for review.')

    mark_for_review.short_description = 'Mark for review'


@admin.register(HelpSearchHistory)
class HelpSearchHistoryAdmin(admin.ModelAdmin):
    """
    Read-only admin interface for search analytics.

    Use for:
    - Identifying popular searches
    - Finding zero-result queries (content gaps)
    - Analyzing click-through rates
    """

    list_display = [
        'query',
        'user',
        'results_count',
        'clicked_article_link',
        'click_position',
        'timestamp',
    ]

    list_filter = [
        'results_count',
        'timestamp',
        'tenant',
    ]

    search_fields = ['query', 'user__username']
    date_hierarchy = 'timestamp'
    list_per_page = 50

    readonly_fields = [
        'query',
        'user',
        'results_count',
        'clicked_article',
        'click_position',
        'refinement_of',
        'session_id',
        'timestamp',
        'tenant',
    ]

    def has_add_permission(self, request):
        """Disable adding (analytics only)."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deletion (preserve analytics)."""
        return False

    def clicked_article_link(self, obj):
        """Display clicked article as link."""
        if obj.clicked_article:
            url = reverse('admin:help_center_helparticle_change', args=[obj.clicked_article.id])
            return format_html('<a href="{}">{}</a>', url, obj.clicked_article.title)
        return '-'

    clicked_article_link.short_description = 'Clicked Article'


@admin.register(HelpArticleInteraction)
class HelpArticleInteractionAdmin(admin.ModelAdmin):
    """
    Read-only admin interface for user engagement metrics.

    Use for:
    - Analyzing user engagement patterns
    - Identifying popular articles
    - Understanding user feedback
    """

    list_display = [
        'user',
        'article_link',
        'interaction_type',
        'time_spent_seconds',
        'scroll_depth_percent',
        'timestamp',
    ]

    list_filter = [
        'interaction_type',
        'timestamp',
        'tenant',
    ]

    search_fields = ['user__username', 'article__title', 'feedback_comment']
    date_hierarchy = 'timestamp'
    list_per_page = 50

    readonly_fields = [
        'article',
        'user',
        'interaction_type',
        'time_spent_seconds',
        'scroll_depth_percent',
        'feedback_comment',
        'session_id',
        'referrer_url',
        'timestamp',
        'tenant',
    ]

    def has_add_permission(self, request):
        """Disable adding (analytics only)."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deletion (preserve analytics)."""
        return False

    def article_link(self, obj):
        """Display article as link."""
        url = reverse('admin:help_center_helparticle_change', args=[obj.article.id])
        return format_html('<a href="{}">{}</a>', url, obj.article.title)

    article_link.short_description = 'Article'


@admin.register(HelpTicketCorrelation)
class HelpTicketCorrelationAdmin(admin.ModelAdmin):
    """
    Read-only admin interface for ticket correlation analytics.

    Use for:
    - Measuring ticket deflection effectiveness
    - Identifying content gaps
    - Analyzing help-to-ticket conversion rates
    """

    list_display = [
        'ticket_link',
        'help_attempted_badge',
        'content_gap_badge',
        'resolution_time_minutes',
        'suggested_article_link',
    ]

    list_filter = [
        'help_attempted',
        'content_gap',
        'relevant_article_exists',
        'tenant',
    ]

    search_fields = ['ticket__title', 'search_queries']
    list_per_page = 50
    readonly_fields = [
        'ticket',
        'help_attempted',
        'help_session_id',
        'articles_viewed',
        'search_queries',
        'relevant_article_exists',
        'content_gap',
        'suggested_article',
        'resolution_time_minutes',
        'analyzed_at',
        'tenant',
    ]

    filter_horizontal = ['articles_viewed']

    def has_add_permission(self, request):
        """Disable adding (auto-created by signals)."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deletion (preserve analytics)."""
        return False

    def ticket_link(self, obj):
        """Display ticket as link."""
        url = reverse('admin:y_helpdesk_ticket_change', args=[obj.ticket.id])
        return format_html('<a href="{}">Ticket #{}</a>', url, obj.ticket.id)

    ticket_link.short_description = 'Ticket'

    def help_attempted_badge(self, obj):
        """Display help attempted status."""
        if obj.help_attempted:
            return format_html('<span style="color: #28a745;">✓ Yes</span>')
        return format_html('<span style="color: #dc3545;">✗ No</span>')

    help_attempted_badge.short_description = 'Help Attempted'

    def content_gap_badge(self, obj):
        """Display content gap status."""
        if obj.content_gap:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px;">GAP</span>'
            )
        return format_html('<span style="color: #28a745;">✓ OK</span>')

    content_gap_badge.short_description = 'Content Gap'

    def suggested_article_link(self, obj):
        """Display suggested article as link."""
        if obj.suggested_article:
            url = reverse('admin:help_center_helparticle_change', args=[obj.suggested_article.id])
            return format_html('<a href="{}">{}</a>', url, obj.suggested_article.title)
        return '-'

    suggested_article_link.short_description = 'Suggested Article'
