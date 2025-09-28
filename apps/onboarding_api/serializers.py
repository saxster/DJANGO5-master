"""
Serializers for Conversational Onboarding API (Phase 1 MVP)
"""
from rest_framework import serializers
from apps.onboarding.models import ConversationSession, LLMRecommendation, AuthoritativeKnowledge, UserFeedbackLearning


class ConversationStartSerializer(serializers.Serializer):
    """Serializer for starting a new conversation session"""
    language = serializers.CharField(max_length=10, default='en')
    user_type = serializers.CharField(max_length=50, required=False)
    client_context = serializers.JSONField(default=dict)
    initial_input = serializers.CharField(max_length=1000, required=False)
    resume_existing = serializers.BooleanField(default=False)


class ConversationSessionSerializer(serializers.ModelSerializer):
    """Serializer for conversation session data"""
    class Meta:
        model = ConversationSession
        fields = [
            'session_id', 'user', 'client', 'language', 'conversation_type',
            'context_data', 'current_state', 'collected_data', 'error_message',
            'cdtz', 'mdtz'
        ]
        read_only_fields = ['session_id', 'cdtz', 'mdtz']


class ConversationProcessSerializer(serializers.Serializer):
    """Serializer for processing conversation input"""
    user_input = serializers.CharField(max_length=2000)
    context = serializers.JSONField(default=dict, required=False)


class LLMRecommendationSerializer(serializers.ModelSerializer):
    """Serializer for LLM recommendations"""
    class Meta:
        model = LLMRecommendation
        fields = [
            'recommendation_id', 'session', 'maker_output', 'checker_output',
            'consensus', 'authoritative_sources', 'confidence_score',
            'user_decision', 'rejection_reason', 'modifications',
            'cdtz', 'mdtz'
        ]
        read_only_fields = ['recommendation_id', 'cdtz', 'mdtz']


class RecommendationApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting recommendations"""
    approved_items = serializers.ListField(
        child=serializers.UUIDField(),
        default=list
    )
    rejected_items = serializers.ListField(
        child=serializers.UUIDField(),
        default=list
    )
    reasons = serializers.JSONField(default=dict)
    modifications = serializers.JSONField(default=dict)
    dry_run = serializers.BooleanField(default=True)


class ConversationStatusSerializer(serializers.Serializer):
    """Serializer for conversation status response"""
    state = serializers.CharField()
    progress = serializers.FloatField()
    enhanced_recommendations = serializers.JSONField(required=False)
    error_message = serializers.CharField(required=False)


class TaskStatusSerializer(serializers.Serializer):
    """Serializer for async task status"""
    status = serializers.ChoiceField(choices=['processing', 'completed', 'failed'])
    status_url = serializers.URLField(required=False)
    result = serializers.JSONField(required=False)
    error = serializers.CharField(required=False)


class AuthoritativeKnowledgeSerializer(serializers.ModelSerializer):
    """Serializer for authoritative knowledge"""
    class Meta:
        model = AuthoritativeKnowledge
        fields = [
            'knowledge_id', 'source_organization', 'document_title',
            'document_version', 'authority_level', 'content_summary',
            'publication_date', 'last_verified', 'is_current'
        ]
        read_only_fields = ['knowledge_id', 'last_verified']


class UserFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for user feedback"""
    class Meta:
        model = UserFeedbackLearning
        fields = [
            'feedback_id', 'recommendation', 'user', 'client',
            'feedback_type', 'feedback_data', 'learning_extracted',
            'applied_to_model', 'cdtz', 'mdtz'
        ]
        read_only_fields = ['feedback_id', 'learning_extracted', 'applied_to_model', 'cdtz', 'mdtz']