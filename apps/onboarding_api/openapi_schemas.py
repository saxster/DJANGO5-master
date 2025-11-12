"""
OpenAPI/Swagger schemas for Conversational Onboarding API

Uses drf-spectacular for OpenAPI 3.0 schema generation.
drf-spectacular is already installed (v0.27.2) and is the modern replacement for drf-yasg.
"""

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
    inline_serializer
)
from rest_framework import serializers

# Schema views for URL configuration
schema_view = SpectacularSwaggerView.as_view(url_name='onboarding_api:schema')
schema_json_view = SpectacularAPIView.as_view()
schema_redoc_view = SpectacularRedocView.as_view(url_name='onboarding_api:schema')

# Decorator utilities for API documentation
# Usage in views:
# @extend_schema(
#     parameters=[OpenApiParameter(name='user_id', type=int, location=OpenApiParameter.QUERY)],
#     responses={200: YourSerializer}
# )
# def your_api_view(request):
#     ...

# Common schema components for reuse
conversation_start_body = inline_serializer(
    name='ConversationStart',
    fields={
        'message': serializers.CharField(help_text="Initial message from user"),
        'session_id': serializers.UUIDField(required=False, help_text="Optional session ID for resuming"),
    }
)

conversation_response_schema = inline_serializer(
    name='ConversationResponse',
    fields={
        'response': serializers.CharField(help_text="AI response message"),
        'session_id': serializers.UUIDField(help_text="Session identifier for conversation continuity"),
        'suggested_actions': serializers.ListField(
            child=serializers.CharField(),
            required=False,
            help_text="Suggested next actions/questions"
        ),
    }
)

__all__ = [
    'extend_schema',
    'OpenApiParameter',
    'OpenApiExample',
    'OpenApiResponse',
    'inline_serializer',
    'schema_view',
    'schema_json_view',
    'schema_redoc_view',
    'conversation_start_body',
    'conversation_response_schema',
]
