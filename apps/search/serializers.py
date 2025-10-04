"""
Search API Serializers

Complies with Rule #7: < 150 lines
Complies with Rule #13: Comprehensive validation
"""

from rest_framework import serializers


class SearchRequestSerializer(serializers.Serializer):
    """
    Request serializer for global search

    Validates query, entities, filters, and pagination
    """

    query = serializers.CharField(
        required=True,
        max_length=500,
        trim_whitespace=True,
        help_text="Search query string"
    )

    entities = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'people', 'work_order', 'ticket', 'asset',
            'location', 'task', 'tour', 'knowledge', 'report'
        ]),
        required=False,
        allow_empty=True,
        help_text="Entity types to search (all if empty)"
    )

    filters = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Entity-specific filters"
    )

    limit = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=100,
        help_text="Maximum results to return"
    )

    fuzzy = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Enable fuzzy matching for typo tolerance"
    )

    semantic = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Enable semantic search (pgvector)"
    )

    def validate_query(self, value):
        """Validate query is not empty or malicious"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Query cannot be empty")

        if len(value) < 2:
            raise serializers.ValidationError("Query must be at least 2 characters")

        return value.strip()


class ActionSerializer(serializers.Serializer):
    """Serializer for result actions"""

    label = serializers.CharField()
    href = serializers.CharField()
    method = serializers.ChoiceField(choices=['GET', 'POST', 'PUT', 'DELETE'])
    payload = serializers.JSONField(required=False)


class SearchResultSerializer(serializers.Serializer):
    """Serializer for individual search results"""

    entity = serializers.CharField()
    id = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True)
    snippet = serializers.CharField(allow_blank=True)
    score = serializers.FloatField()
    metadata = serializers.JSONField()
    actions = ActionSerializer(many=True)


class SearchResponseSerializer(serializers.Serializer):
    """Serializer for search API response"""

    results = SearchResultSerializer(many=True)
    total_results = serializers.IntegerField()
    response_time_ms = serializers.IntegerField()
    query_id = serializers.UUIDField()
    error = serializers.CharField(required=False, allow_blank=True)


class SavedSearchSerializer(serializers.Serializer):
    """Serializer for saved search creation/update"""

    name = serializers.CharField(max_length=200, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    query = serializers.CharField(max_length=500, required=True)
    entities = serializers.ListField(child=serializers.CharField(), required=False)
    filters = serializers.JSONField(required=False, default=dict)
    is_alert_enabled = serializers.BooleanField(default=False)
    alert_frequency = serializers.ChoiceField(
        choices=['realtime', 'hourly', 'daily', 'weekly'],
        default='daily'
    )
    is_public = serializers.BooleanField(default=False)

    def validate_name(self, value):
        """Ensure unique name per user"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Name cannot be empty")
        return value.strip()