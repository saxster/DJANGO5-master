"""
NOC Saved View Serializers.

Serializers for saved dashboard view configurations.
Follows .claude/rules.md Rule #7 (serializers <150 lines).
"""

from typing import Any, Dict, List

from rest_framework import serializers
from apps.noc.models import NOCSavedView
from apps.noc.services import NOCViewService

__all__ = [
    'NOCSavedViewSerializer',
    'NOCSavedViewListSerializer',
    'ViewShareSerializer',
]


class NOCSavedViewSerializer(serializers.ModelSerializer):
    """Full saved view serializer for CRUD operations."""

    user_name = serializers.CharField(
        source='user.peoplename',
        read_only=True
    )

    shared_with_users = serializers.SerializerMethodField()

    class Meta:
        model = NOCSavedView
        fields = [
            'id', 'user', 'user_name', 'name', 'description',
            'filters', 'widget_layout', 'time_range_hours',
            'refresh_interval_seconds', 'is_default', 'is_shared',
            'shared_with_users', 'version', 'usage_count',
            'last_used_at', 'cdtz', 'mdtz'
        ]
        read_only_fields = [
            'id', 'user_name', 'version', 'usage_count',
            'last_used_at', 'cdtz', 'mdtz', 'shared_with_users'
        ]

    def get_shared_with_users(self, obj) -> List[Dict[str, Any]]:
        """Get list of users this view is shared with."""
        if obj.is_shared:
            return [
                {'id': u.id, 'name': u.peoplename}
                for u in obj.shared_with.all()
            ]
        return []

    def validate_filters(self, value):
        """Validate filter structure."""
        if not NOCViewService.validate_filters(value):
            raise serializers.ValidationError(
                "Invalid filter structure"
            )
        return value

    def validate_widget_layout(self, value):
        """Validate widget layout structure."""
        if not NOCViewService.validate_widget_layout(value):
            raise serializers.ValidationError(
                "Invalid widget layout structure. "
                "Each widget must have: widget_id, x, y, width, height"
            )
        return value

    def validate_time_range_hours(self, value):
        """Validate time range."""
        if value < 1 or value > 8760:  # 1 hour to 1 year
            raise serializers.ValidationError(
                "Time range must be between 1 and 8760 hours"
            )
        return value

    def validate_refresh_interval_seconds(self, value):
        """Validate refresh interval."""
        if value < 10 or value > 3600:  # 10 seconds to 1 hour
            raise serializers.ValidationError(
                "Refresh interval must be between 10 and 3600 seconds"
            )
        return value


class NOCSavedViewListSerializer(serializers.ModelSerializer):
    """Lightweight saved view serializer for list views."""

    user_name = serializers.CharField(
        source='user.peoplename',
        read_only=True
    )

    is_owned = serializers.SerializerMethodField()

    class Meta:
        model = NOCSavedView
        fields = [
            'id', 'name', 'is_default', 'is_shared',
            'user_name', 'is_owned', 'usage_count', 'last_used_at'
        ]

    def get_is_owned(self, obj) -> bool:
        """Check if current user owns this view."""
        request = self.context.get('request')
        if request and request.user:
            return obj.user_id == request.user.id
        return False


class ViewShareSerializer(serializers.Serializer):
    """Validate view sharing operations."""

    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=1,
        help_text="List of user IDs to share view with"
    )

    action = serializers.ChoiceField(
        choices=['share', 'unshare'],
        default='share',
        help_text="Share or unshare action"
    )

    def validate_user_ids(self, value):
        """Validate user IDs exist in tenant."""
        from apps.peoples.models import People

        view = self.context.get('view')
        if not view:
            raise serializers.ValidationError("View context required")

        existing_users = People.objects.filter(
            id__in=value,
            tenant=view.tenant
        ).values_list('id', flat=True)

        if len(existing_users) != len(value):
            missing = set(value) - set(existing_users)
            raise serializers.ValidationError(
                f"Users not found in tenant: {missing}"
            )

        return value
