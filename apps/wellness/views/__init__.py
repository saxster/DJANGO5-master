"""
Wellness Views Package

Modular view organization for the wellness application.
"""

from .wisdom_conversation_views import (
    conversations_with_wisdom_view,
    toggle_conversation_bookmark,
    track_conversation_engagement,
    conversation_reflection_view,
    conversation_export_view,
    conversation_analytics_api,
    conversation_search_api,
)

from .translation_api_views import (
    translate_conversation,
    get_supported_languages,
    get_translation_status,
    submit_translation_feedback,
    get_translation_analytics,
    batch_translate_conversations,
)

__all__ = [
    # Wisdom Conversation Views
    'conversations_with_wisdom_view',
    'toggle_conversation_bookmark',
    'track_conversation_engagement',
    'conversation_reflection_view',
    'conversation_export_view',
    'conversation_analytics_api',
    'conversation_search_api',

    # Translation API Views
    'translate_conversation',
    'get_supported_languages',
    'get_translation_status',
    'submit_translation_feedback',
    'get_translation_analytics',
    'batch_translate_conversations',
]