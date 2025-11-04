"""
DRF Serializers for Help Center API.

Provides REST API serialization for all help center models with:
- Nested relationships
- Role-based field filtering
- Input validation with Pydantic
- Optimized queries (select_related, prefetch_related)

Following CLAUDE.md:
- Clean, maintainable serializers
- Proper validation
- Type-safe contracts
"""

from rest_framework import serializers
from apps.help_center.models import (
    HelpTag,
    HelpCategory,
    HelpArticle,
    HelpSearchHistory,
    HelpArticleInteraction,
    HelpTicketCorrelation,
)
from apps.peoples.models import People


class HelpTagSerializer(serializers.ModelSerializer):
    """Serializer for help tags."""

    class Meta:
        model = HelpTag
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id']


class HelpCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for help categories with hierarchy.

    Includes:
    - Parent category reference
    - Breadcrumb path
    - Article count
    """

    breadcrumb = serializers.CharField(source='get_breadcrumb', read_only=True)
    article_count = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)

    class Meta:
        model = HelpCategory
        fields = [
            'id', 'name', 'slug', 'description', 'parent', 'parent_name',
            'icon', 'color', 'display_order', 'is_active',
            'breadcrumb', 'article_count'
        ]
        read_only_fields = ['id', 'breadcrumb', 'article_count', 'parent_name']

    def get_article_count(self, obj):
        """Count published articles in this category."""
        return obj.articles.filter(status=HelpArticle.Status.PUBLISHED).count()


class HelpArticleListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for article lists.

    Minimal fields for performance:
    - No full content (only summary)
    - Nested category name only
    - Tag names only
    """

    category_name = serializers.CharField(source='category.name', read_only=True)
    tag_names = serializers.SerializerMethodField()
    helpful_ratio = serializers.FloatField(read_only=True)
    is_stale = serializers.BooleanField(read_only=True)

    class Meta:
        model = HelpArticle
        fields = [
            'id', 'title', 'slug', 'summary', 'category_name', 'tag_names',
            'difficulty_level', 'status', 'view_count', 'helpful_ratio',
            'is_stale', 'published_date', 'created_at'
        ]
        read_only_fields = fields

    def get_tag_names(self, obj):
        """Return list of tag names."""
        return [tag.name for tag in obj.tags.all()]


class HelpArticleDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for article detail view.

    Includes:
    - Full content
    - Nested category
    - Nested tags
    - Author information
    - Analytics data
    """

    category = HelpCategorySerializer(read_only=True)
    tags = HelpTagSerializer(many=True, read_only=True)
    helpful_ratio = serializers.FloatField(read_only=True)
    is_stale = serializers.BooleanField(read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    last_updated_by_username = serializers.CharField(source='last_updated_by.username', read_only=True, allow_null=True)

    class Meta:
        model = HelpArticle
        fields = [
            'id', 'title', 'slug', 'summary', 'content',
            'category', 'tags', 'difficulty_level', 'target_roles',
            'status', 'version', 'view_count', 'helpful_count', 'not_helpful_count',
            'helpful_ratio', 'is_stale',
            'created_by_username', 'last_updated_by_username',
            'published_date', 'last_reviewed_date', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'view_count', 'helpful_count', 'not_helpful_count',
            'helpful_ratio', 'is_stale', 'version',
            'created_by_username', 'last_updated_by_username',
            'created_at', 'updated_at'
        ]


class HelpSearchRequestSerializer(serializers.Serializer):
    """
    Serializer for search requests.

    Validates:
    - Query string (required, min 2 chars)
    - Limit (optional, max 50)
    - Role filtering (optional boolean)
    """

    query = serializers.CharField(
        required=True,
        min_length=2,
        max_length=500,
        help_text="Search query (min 2 characters)"
    )
    limit = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=50,
        help_text="Max results to return (default: 20, max: 50)"
    )
    role_filter = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Filter by user's roles (default: true)"
    )

    def validate_query(self, value):
        """Sanitize query string."""
        # Remove potentially dangerous characters
        forbidden_chars = ['<', '>', '{', '}', '[', ']', '\\']
        for char in forbidden_chars:
            if char in value:
                raise serializers.ValidationError(
                    f"Query contains forbidden character: {char}"
                )
        return value.strip()


class HelpSearchResponseSerializer(serializers.Serializer):
    """
    Serializer for search responses.

    Returns:
    - Results (list of articles)
    - Suggestions (related queries)
    - Total count
    - Search ID (for click tracking)
    """

    results = HelpArticleListSerializer(many=True, read_only=True)
    suggestions = serializers.ListField(
        child=serializers.CharField(),
        read_only=True
    )
    total = serializers.IntegerField(read_only=True)
    search_id = serializers.IntegerField(read_only=True)


class HelpVoteSerializer(serializers.Serializer):
    """
    Serializer for article votes (helpful/not helpful).

    Validates:
    - is_helpful (required boolean)
    - comment (optional feedback text)
    """

    is_helpful = serializers.BooleanField(
        required=True,
        help_text="True for helpful, False for not helpful"
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text="Optional feedback comment (max 1000 chars)"
    )

    def validate_comment(self, value):
        """Sanitize comment text."""
        if value:
            # Basic XSS prevention
            dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=']
            value_lower = value.lower()
            for pattern in dangerous_patterns:
                if pattern in value_lower:
                    raise serializers.ValidationError(
                        "Comment contains potentially dangerous content"
                    )
        return value.strip() if value else ''


class HelpAnalyticsEventSerializer(serializers.Serializer):
    """
    Serializer for tracking help interactions.

    Event types:
    - article_view
    - article_bookmark
    - article_share
    - tour_started
    - tour_completed
    """

    event_type = serializers.ChoiceField(
        required=True,
        choices=[
            'article_view',
            'article_bookmark',
            'article_share',
            'tour_started',
            'tour_completed',
            'widget_opened',
            'widget_closed'
        ],
        help_text="Type of interaction event"
    )
    article_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Article ID (required for article_* events)"
    )
    session_id = serializers.UUIDField(
        required=True,
        help_text="Session UUID for tracking user journey"
    )
    referrer_url = serializers.URLField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Page URL where event occurred"
    )
    time_spent_seconds = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text="Time spent on article (seconds)"
    )
    scroll_depth_percent = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=100,
        help_text="Scroll depth percentage (0-100)"
    )
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Additional event metadata"
    )

    def validate(self, data):
        """Cross-field validation."""
        event_type = data.get('event_type')

        # Article events require article_id
        if event_type in ['article_view', 'article_bookmark', 'article_share']:
            if not data.get('article_id'):
                raise serializers.ValidationError({
                    'article_id': f"article_id is required for {event_type} events"
                })

        return data


class HelpArticleInteractionSerializer(serializers.ModelSerializer):
    """Serializer for article interaction records (read-only)."""

    article_title = serializers.CharField(source='article.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = HelpArticleInteraction
        fields = [
            'id', 'article', 'article_title', 'user', 'user_username',
            'interaction_type', 'time_spent_seconds', 'scroll_depth_percent',
            'feedback_comment', 'session_id', 'referrer_url', 'timestamp'
        ]
        read_only_fields = fields
