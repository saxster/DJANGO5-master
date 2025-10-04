"""
Enhanced Frontend-Friendly Serializers
Demonstrations of improved serializers using the frontend serializer system
These replace basic serializers with rich, frontend-optimized versions
"""

from rest_framework import serializers
from apps.core.serializers.frontend_serializers import (
    BaseFrontendSerializer,
    ComputedField,
    HumanReadableDateTimeField,
    FileFieldWithMetadata,
    RelationshipEagerLoadingMixin
)
from apps.peoples.models import People
from apps.onboarding.models import ConversationSession, LLMRecommendation
from apps.activity.models import Task
from apps.y_helpdesk.models import Ticket


class EnhancedPeopleSerializer(RelationshipEagerLoadingMixin, BaseFrontendSerializer):
    """
    Enhanced People serializer with frontend optimizations
    """

    # Computed fields for better UX
    full_name = ComputedField(lambda obj: f"{obj.peoplename}" if obj.peoplename else obj.loginid)
    initials = ComputedField(lambda obj: ''.join([name[0] for name in (obj.peoplename or '').split()[:2]]).upper())
    status_label = ComputedField(lambda obj: 'Active' if obj.enable else 'Inactive')
    verification_status = ComputedField(lambda obj: 'Verified' if obj.isverified else 'Pending Verification')

    # Enhanced datetime fields
    created_at = HumanReadableDateTimeField(source='cdtz', read_only=True)
    updated_at = HumanReadableDateTimeField(source='mdtz', read_only=True)

    # Enhanced file field
    profile_image = FileFieldWithMetadata(source='peopleimg', read_only=True)

    # Nested relationships for reduced API calls
    business_unit = serializers.SerializerMethodField()
    department_info = serializers.SerializerMethodField()

    class Meta:
        model = People
        fields = [
            'id', 'uuid', 'peoplecode', 'loginid', 'peoplename', 'email', 'mobno',
            'enable', 'isverified', 'isadmin',
            # Computed fields
            'full_name', 'initials', 'status_label', 'verification_status',
            # Enhanced datetime
            'created_at', 'updated_at',
            # Enhanced file field
            'profile_image',
            # Relationships
            'business_unit', 'department_info'
        ]
        read_only_fields = ['id', 'uuid', 'cdtz', 'mdtz']

        # Query optimization
        select_related = ['bu', 'department', 'designation']
        prefetch_related = []

    def get_business_unit(self, obj):
        """
        Get business unit information without additional queries
        """
        if obj.bu:
            return {
                'id': obj.bu.id,
                'name': obj.bu.buname,
                'code': obj.bu.bucode,
            }
        return None

    def get_department_info(self, obj):
        """
        Get department information
        """
        if obj.department:
            return {
                'id': obj.department.id,
                'name': obj.department.taname,
                'code': obj.department.tacode,
            }
        return None

    def get_form_schema(self):
        """
        Override to provide custom form schema
        """
        schema = super().get_form_schema()

        # Add custom UI hints
        schema['ui_schema'] = {
            'peoplecode': {
                'ui:help': 'Unique identifier for this person',
                'ui:placeholder': 'Enter unique code'
            },
            'email': {
                'ui:widget': 'email',
                'ui:help': 'Used for login and notifications'
            },
            'mobno': {
                'ui:widget': 'tel',
                'ui:help': 'Mobile number for SMS notifications'
            },
            'profile_image': {
                'ui:widget': 'file',
                'ui:options': {
                    'accept': '.jpg,.jpeg,.png,.gif',
                    'multiple': False
                }
            }
        }

        # Group fields logically
        schema['field_groups'] = [
            {
                'title': 'Basic Information',
                'fields': ['peoplecode', 'peoplename', 'email', 'mobno']
            },
            {
                'title': 'Profile',
                'fields': ['profile_image']
            },
            {
                'title': 'System Settings',
                'fields': ['enable', 'isadmin']
            }
        ]

        return schema


class EnhancedConversationSessionSerializer(BaseFrontendSerializer):
    """
    Enhanced conversation session serializer
    """

    # Computed fields
    session_duration = ComputedField(lambda obj: obj.get_duration() if hasattr(obj, 'get_duration') else None)
    progress_percentage = ComputedField(lambda obj: obj.get_progress() if hasattr(obj, 'get_progress') else 0)

    # Enhanced datetime
    started_at = HumanReadableDateTimeField(source='cdtz', read_only=True)
    last_activity = HumanReadableDateTimeField(source='mdtz', read_only=True)

    # Nested user information
    user_info = serializers.SerializerMethodField()

    class Meta:
        model = ConversationSession
        fields = [
            'session_id', 'language', 'conversation_type', 'current_state',
            'context_data', 'collected_data', 'error_message',
            # Computed fields
            'session_duration', 'progress_percentage',
            # Enhanced datetime
            'started_at', 'last_activity',
            # Relationships
            'user_info'
        ]
        read_only_fields = ['session_id', 'cdtz', 'mdtz']

    def get_user_info(self, obj):
        """
        Get user information without exposing sensitive data
        """
        if obj.user:
            return {
                'id': obj.user.id,
                'name': obj.user.peoplename or obj.user.loginid,
                'initials': ''.join([name[0] for name in (obj.user.peoplename or '').split()[:2]]).upper()
            }
        return None

    def get_ui_hints(self, obj):
        """
        Override to add conversation-specific UI hints
        """
        hints = super().get_ui_hints(obj)
        hints.update({
            'conversation_type': obj.conversation_type,
            'is_active': obj.current_state in ['active', 'processing'],
            'needs_attention': bool(obj.error_message),
        })
        return hints


class EnhancedTaskSerializer(RelationshipEagerLoadingMixin, BaseFrontendSerializer):
    """
    Enhanced Task serializer with rich metadata
    """

    # Computed fields
    priority_label = ComputedField(
        lambda obj: {
            1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical'
        }.get(getattr(obj, 'priority', 2), 'Medium')
    )

    status_color = ComputedField(
        lambda obj: {
            'pending': '#ffc107',
            'in_progress': '#377dff',
            'completed': '#00c9a7',
            'cancelled': '#de4437'
        }.get(getattr(obj, 'status', 'pending'), '#8392a5')
    )

    is_overdue = ComputedField(
        lambda obj: (
            obj.due_date and
            obj.due_date < timezone.now().date() and
            getattr(obj, 'status', 'pending') != 'completed'
        ) if hasattr(obj, 'due_date') else False
    )

    # Enhanced datetime fields
    created_at = HumanReadableDateTimeField(source='cdtz', read_only=True)
    due_date_info = serializers.SerializerMethodField()

    # Relationship data
    assignee_info = serializers.SerializerMethodField()
    location_info = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status', 'priority',
            # Computed fields
            'priority_label', 'status_color', 'is_overdue',
            # Enhanced datetime
            'created_at', 'due_date_info',
            # Relationships
            'assignee_info', 'location_info'
        ]

        # Query optimization
        select_related = ['assignee', 'location', 'created_by']
        prefetch_related = ['tags', 'attachments']

    def get_due_date_info(self, obj):
        """
        Get enhanced due date information
        """
        if not hasattr(obj, 'due_date') or not obj.due_date:
            return None

        from django.utils import timezone

        now = timezone.now().date()
        due_date = obj.due_date
        diff = (due_date - now).days

        return {
            'date': due_date.isoformat(),
            'days_until_due': diff,
            'is_overdue': diff < 0,
            'urgency': (
                'overdue' if diff < 0 else
                'critical' if diff <= 1 else
                'urgent' if diff <= 3 else
                'normal'
            )
        }

    def get_assignee_info(self, obj):
        """
        Get assignee information
        """
        if hasattr(obj, 'assignee') and obj.assignee:
            return {
                'id': obj.assignee.id,
                'name': obj.assignee.peoplename or obj.assignee.loginid,
                'email': obj.assignee.email,
                'initials': ''.join([name[0] for name in (obj.assignee.peoplename or '').split()[:2]]).upper()
            }
        return None

    def get_location_info(self, obj):
        """
        Get location information
        """
        if hasattr(obj, 'location') and obj.location:
            return {
                'id': obj.location.id,
                'name': obj.location.name,
                'code': obj.location.code,
            }
        return None


class EnhancedTicketSerializer(RelationshipEagerLoadingMixin, BaseFrontendSerializer):
    """
    Enhanced Help Desk Ticket serializer
    """

    # Computed fields
    priority_badge = ComputedField(
        lambda obj: {
            'low': {'color': '#28a745', 'text': 'Low Priority'},
            'medium': {'color': '#ffc107', 'text': 'Medium Priority'},
            'high': {'color': '#fd7e14', 'text': 'High Priority'},
            'critical': {'color': '#dc3545', 'text': 'Critical'}
        }.get(getattr(obj, 'priority', 'medium'), {'color': '#6c757d', 'text': 'Unknown'})
    )

    sla_status = ComputedField(lambda obj: obj.get_sla_status() if hasattr(obj, 'get_sla_status') else 'unknown')
    time_to_resolution = ComputedField(lambda obj: obj.get_resolution_time() if hasattr(obj, 'get_resolution_time') else None)

    # Enhanced datetime
    created_at = HumanReadableDateTimeField(source='cdtz', read_only=True)
    updated_at = HumanReadableDateTimeField(source='mdtz', read_only=True)

    # Relationship data
    reporter_info = serializers.SerializerMethodField()
    assignee_info = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_number', 'title', 'description', 'status', 'priority',
            # Computed fields
            'priority_badge', 'sla_status', 'time_to_resolution',
            # Enhanced datetime
            'created_at', 'updated_at',
            # Relationships
            'reporter_info', 'assignee_info'
        ]

        # Query optimization
        select_related = ['reporter', 'assignee', 'category']
        prefetch_related = ['attachments', 'comments']

    def get_reporter_info(self, obj):
        """
        Get ticket reporter information
        """
        if hasattr(obj, 'reporter') and obj.reporter:
            return {
                'id': obj.reporter.id,
                'name': obj.reporter.peoplename or obj.reporter.loginid,
                'email': obj.reporter.email,
            }
        return None

    def get_assignee_info(self, obj):
        """
        Get assigned technician information
        """
        if hasattr(obj, 'assignee') and obj.assignee:
            return {
                'id': obj.assignee.id,
                'name': obj.assignee.peoplename or obj.assignee.loginid,
                'email': obj.assignee.email,
            }
        return None


class EnhancedLLMRecommendationSerializer(BaseFrontendSerializer):
    """
    Enhanced LLM Recommendation serializer
    """

    # Computed fields
    confidence_level = ComputedField(
        lambda obj: (
            'high' if obj.confidence_score >= 0.8 else
            'medium' if obj.confidence_score >= 0.6 else
            'low'
        ) if hasattr(obj, 'confidence_score') and obj.confidence_score else 'unknown'
    )

    recommendation_summary = ComputedField(
        lambda obj: obj.get_summary() if hasattr(obj, 'get_summary') else None
    )

    # Enhanced datetime
    created_at = HumanReadableDateTimeField(source='cdtz', read_only=True)

    class Meta:
        model = LLMRecommendation
        fields = [
            'recommendation_id', 'maker_output', 'checker_output', 'consensus',
            'confidence_score', 'user_decision', 'rejection_reason',
            # Computed fields
            'confidence_level', 'recommendation_summary',
            # Enhanced datetime
            'created_at'
        ]
        read_only_fields = ['recommendation_id', 'cdtz', 'mdtz']

    def get_ui_hints(self, obj):
        """
        Add recommendation-specific UI hints
        """
        hints = super().get_ui_hints(obj)
        hints.update({
            'needs_review': obj.user_decision is None,
            'is_consensus': obj.consensus,
            'confidence_color': {
                'high': '#28a745',
                'medium': '#ffc107',
                'low': '#dc3545'
            }.get(self.get_confidence_level(obj), '#6c757d')
        })
        return hints

    def get_confidence_level(self, obj):
        """
        Helper method to get confidence level
        """
        if hasattr(obj, 'confidence_score') and obj.confidence_score:
            if obj.confidence_score >= 0.8:
                return 'high'
            elif obj.confidence_score >= 0.6:
                return 'medium'
            else:
                return 'low'
        return 'unknown'


# Response envelope utility
class FrontendResponseSerializer(serializers.Serializer):
    """
    Standardized response envelope for frontend consumption
    """
    success = serializers.BooleanField()
    status_code = serializers.IntegerField()
    message = serializers.CharField(required=False, allow_blank=True)
    data = serializers.JSONField()
    meta = serializers.JSONField()
    timestamp = serializers.DateTimeField()
    errors = serializers.ListField(required=False, allow_empty=True)
    error_code = serializers.CharField(required=False, allow_blank=True)


# Collection response with pagination
class CollectionResponseSerializer(serializers.Serializer):
    """
    Serializer for paginated collections
    """
    results = serializers.ListField()
    pagination = serializers.JSONField()
    filters = serializers.JSONField(required=False)
    sorting = serializers.JSONField(required=False)


# Export serializers dictionary for easy import
ENHANCED_SERIALIZERS = {
    'people': EnhancedPeopleSerializer,
    'conversation_session': EnhancedConversationSessionSerializer,
    'task': EnhancedTaskSerializer,
    'ticket': EnhancedTicketSerializer,
    'llm_recommendation': EnhancedLLMRecommendationSerializer,
}