"""
Serializers for Conversational Onboarding API (Phase 1 MVP)
"""
from rest_framework import serializers
from apps.core_onboarding.models import ConversationSession, LLMRecommendation, AuthoritativeKnowledge
from apps.core_onboarding.models import UserFeedbackLearning


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


class VoiceInputSerializer(serializers.Serializer):
    """
    Serializer for voice input requests.

    Validates audio file and language parameters for voice-to-text transcription.
    """
    language = serializers.CharField(
        max_length=10,
        default='en-US',
        required=False,
        help_text="BCP-47 language code (e.g., 'en-US', 'hi-IN')"
    )
    context = serializers.JSONField(
        default=dict,
        required=False,
        help_text="Additional context for voice processing"
    )

    def validate_language(self, value):
        """
        Validate that the language is supported for voice input.

        Raises:
            ValidationError: If language is not supported
        """
        from apps.core_onboarding.services.speech_service import OnboardingSpeechService
        service = OnboardingSpeechService()

        if not service.is_language_supported(value):
            supported = list(service.SUPPORTED_LANGUAGES.keys())
            raise serializers.ValidationError(
                f"Language '{value}' is not supported. "
                f"Supported languages: {', '.join(supported)}"
            )
        return value


class VoiceTranscriptionResponseSerializer(serializers.Serializer):
    """Serializer for voice transcription API response."""
    conversation_id = serializers.UUIDField(
        help_text="UUID of the conversation session"
    )
    transcription = serializers.JSONField(
        help_text="Transcription details including text, confidence, duration"
    )
    response = serializers.CharField(
        allow_blank=True,
        help_text="LLM response to the voice input"
    )
    next_questions = serializers.ListField(
        child=serializers.JSONField(),
        help_text="Follow-up questions generated by LLM"
    )
    state = serializers.CharField(
        help_text="Current conversation session state"
    )
    voice_interaction_count = serializers.IntegerField(
        required=False,
        help_text="Total number of voice interactions in this session"
    )


class VoiceCapabilityResponseSerializer(serializers.Serializer):
    """Serializer for voice capability check response."""
    voice_enabled = serializers.BooleanField(
        help_text="Whether voice input is enabled globally"
    )
    service_available = serializers.BooleanField(
        help_text="Whether Google Cloud Speech API is available"
    )
    supported_languages = serializers.DictField(
        help_text="Dictionary of supported language codes"
    )
    configuration = serializers.DictField(
        help_text="Voice processing configuration limits"
    )
    supported_formats = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of supported audio MIME types"
    )
    features = serializers.DictField(
        help_text="Available voice processing features"
    )