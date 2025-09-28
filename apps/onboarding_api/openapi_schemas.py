"""
OpenAPI/Swagger schemas for Conversational Onboarding API
"""
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# API Information
api_info = openapi.Info(
    title="Conversational Onboarding API",
    default_version='v1',
    description="""
    ## Conversational Onboarding API Documentation

    This API provides AI-powered conversational onboarding capabilities for facility management systems.

    ### Features:
    - **Conversation Management**: Start, process, and track onboarding conversations
    - **AI Recommendations**: Generate and validate configuration recommendations
    - **Knowledge Base**: Access authoritative knowledge for grounding AI responses
    - **Change Management**: Preview and apply system configuration changes with rollback support
    - **UI Compatibility**: Alternative endpoints for frontend compatibility

    ### Authentication:
    All endpoints require authentication via session cookies or API tokens.

    ### Rate Limiting:
    - Standard endpoints: 100 requests per minute
    - AI processing endpoints: 10 requests per minute
    - Knowledge search: 30 requests per minute

    ### Status Codes:
    - 200: Success
    - 202: Accepted (async processing)
    - 400: Bad Request
    - 401: Unauthorized
    - 403: Forbidden
    - 404: Not Found
    - 409: Conflict (e.g., active session exists)
    - 429: Too Many Requests
    - 500: Internal Server Error
    """,
    terms_of_service="https://example.com/terms/",
    contact=openapi.Contact(email="api-support@example.com"),
    license=openapi.License(name="Proprietary"),
)

# Schema view configuration
schema_view = get_schema_view(
    api_info,
    public=False,
    permission_classes=(permissions.IsAuthenticated,),
    patterns=None,
    url='/api/v1/onboarding/',
)

# Request/Response Schemas

# Common Parameters
session_id_param = openapi.Parameter(
    'conversation_id',
    openapi.IN_PATH,
    description="UUID of the conversation session",
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_UUID,
    required=True
)

task_id_param = openapi.Parameter(
    'task_id',
    openapi.IN_PATH,
    description="Celery task ID for async operations",
    type=openapi.TYPE_STRING,
    required=True
)

# Request Bodies
conversation_start_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=[],
    properties={
        'client_context': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            description='Initial context data about the client'
        ),
        'language': openapi.Schema(
            type=openapi.TYPE_STRING,
            description='ISO language code (e.g., "en", "es")',
            default='en'
        ),
        'resume_existing': openapi.Schema(
            type=openapi.TYPE_BOOLEAN,
            description='Whether to resume existing active session',
            default=False
        )
    }
)

conversation_process_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=['user_input'],
    properties={
        'user_input': openapi.Schema(
            type=openapi.TYPE_STRING,
            description='User response to conversation'
        ),
        'context': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            description='Additional context data'
        )
    }
)

recommendation_approval_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=['approved_items', 'rejected_items', 'dry_run'],
    properties={
        'session_id': openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_UUID,
            description='Conversation session ID'
        ),
        'approved_items': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'entity_type': openapi.Schema(type=openapi.TYPE_STRING),
                    'entity_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'changes': openapi.Schema(type=openapi.TYPE_OBJECT)
                }
            ),
            description='List of approved recommendation items'
        ),
        'rejected_items': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(type=openapi.TYPE_STRING),
            description='List of rejected item IDs'
        ),
        'reasons': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            description='Rejection reasons by item ID'
        ),
        'modifications': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            description='User modifications to recommendations'
        ),
        'dry_run': openapi.Schema(
            type=openapi.TYPE_BOOLEAN,
            description='Whether to perform a dry run',
            default=True
        )
    }
)

changeset_preview_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=['approved_items'],
    properties={
        'approved_items': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'entity_type': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        enum=['bt', 'shift', 'typeassist']
                    ),
                    'entity_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'changes': openapi.Schema(type=openapi.TYPE_OBJECT)
                }
            )
        ),
        'modifications': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            description='User modifications to apply'
        )
    }
)

# Response Schemas
conversation_start_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'conversation_id': openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_UUID
        ),
        'questions': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(type=openapi.TYPE_STRING)
        ),
        'enhanced_understanding': openapi.Schema(
            type=openapi.TYPE_OBJECT
        )
    }
)

async_process_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'status': openapi.Schema(
            type=openapi.TYPE_STRING,
            enum=['processing']
        ),
        'task_id': openapi.Schema(
            type=openapi.TYPE_STRING,
            description='Celery task ID'
        ),
        'friendly_task_id': openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_UUID
        ),
        'status_url': openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_URI
        ),
        'task_status_url': openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_URI
        )
    }
)

sync_process_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'enhanced_recommendations': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(type=openapi.TYPE_OBJECT)
        ),
        'consensus_confidence': openapi.Schema(
            type=openapi.TYPE_NUMBER,
            minimum=0.0,
            maximum=1.0
        ),
        'next_steps': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(type=openapi.TYPE_STRING)
        )
    }
)

feature_status_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'enabled': openapi.Schema(type=openapi.TYPE_BOOLEAN),
        'flags': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'dual_llm_enabled': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'streaming_enabled': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'personalization_enabled': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'knowledge_base_enabled': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'ai_experiments_enabled': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            }
        ),
        'configuration': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'max_session_duration_minutes': openapi.Schema(type=openapi.TYPE_INTEGER),
                'max_recommendations_per_session': openapi.Schema(type=openapi.TYPE_INTEGER),
                'languages_supported': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING)
                ),
                'llm_provider': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ),
        'version': openapi.Schema(type=openapi.TYPE_STRING),
        'user_capabilities': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'can_approve_recommendations': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'can_access_admin_dashboard': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'can_override_ai_decisions': openapi.Schema(type=openapi.TYPE_BOOLEAN)
            }
        )
    }
)

changeset_diff_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'changes': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'entity_type': openapi.Schema(type=openapi.TYPE_STRING),
                    'entity_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'operation': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        enum=['create', 'update']
                    ),
                    'before': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'after': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'fields_changed': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'field': openapi.Schema(type=openapi.TYPE_STRING),
                                'old': openapi.Schema(type=openapi.TYPE_STRING),
                                'new': openapi.Schema(type=openapi.TYPE_STRING)
                            }
                        )
                    )
                }
            )
        ),
        'summary': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'total_changes': openapi.Schema(type=openapi.TYPE_INTEGER),
                'fields_modified': openapi.Schema(type=openapi.TYPE_INTEGER),
                'entities_affected': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING)
                )
            }
        )
    }
)

# Error Response
error_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'error': openapi.Schema(
            type=openapi.TYPE_STRING,
            description='Error message'
        ),
        'detail': openapi.Schema(
            type=openapi.TYPE_STRING,
            description='Detailed error information'
        ),
        'code': openapi.Schema(
            type=openapi.TYPE_STRING,
            description='Error code'
        )
    }
)


# API Documentation decorator functions
def document_conversation_start():
    """Decorator for conversation start endpoint documentation"""
    return {
        'operation_description': """
        Start a new conversational onboarding session.

        This endpoint initializes a new conversation with the AI assistant.
        If an active session already exists, it will return a 409 Conflict error
        unless `resume_existing` is set to true or the session is stale (>30 mins).
        """,
        'request_body': conversation_start_body,
        'responses': {
            200: openapi.Response('Conversation started', conversation_start_response),
            400: openapi.Response('Bad request', error_response),
            409: openapi.Response('Active session exists', error_response)
        },
        'tags': ['Conversation']
    }


def document_conversation_process():
    """Decorator for conversation process endpoint documentation"""
    return {
        'operation_description': """
        Process a conversation step with user input.

        This endpoint handles user responses and generates AI recommendations.
        For long inputs (>500 chars) or complex sessions, processing is async.
        """,
        'manual_parameters': [session_id_param],
        'request_body': conversation_process_body,
        'responses': {
            200: openapi.Response('Sync processing complete', sync_process_response),
            202: openapi.Response('Async processing started', async_process_response),
            404: openapi.Response('Session not found', error_response)
        },
        'tags': ['Conversation']
    }


def document_feature_status():
    """Decorator for feature status endpoint documentation"""
    return {
        'operation_description': """
        Get conversational onboarding feature status and configuration.

        Returns current feature flags, configuration settings, and user capabilities.
        """,
        'responses': {
            200: openapi.Response('Feature status', feature_status_response)
        },
        'tags': ['Status']
    }


def document_changeset_preview():
    """Decorator for changeset preview endpoint documentation"""
    return {
        'operation_description': """
        Preview changes that would be applied to the system.

        Generates a diff showing before/after states for configuration changes.
        Requires 'can_approve_ai_recommendations' permission.
        """,
        'request_body': changeset_preview_body,
        'responses': {
            200: openapi.Response('Change preview', changeset_diff_response),
            400: openapi.Response('Bad request', error_response),
            403: openapi.Response('Insufficient permissions', error_response)
        },
        'tags': ['Change Management']
    }


def document_task_status():
    """Decorator for task status endpoint documentation"""
    return {
        'operation_description': """
        Get the status of an async task.

        Returns current state, progress, and results when complete.
        """,
        'manual_parameters': [task_id_param],
        'responses': {
            200: openapi.Response('Task status', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'task_id': openapi.Schema(type=openapi.TYPE_STRING),
                    'state': openapi.Schema(type=openapi.TYPE_STRING),
                    'progress': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'result': openapi.Schema(type=openapi.TYPE_OBJECT)
                }
            ))
        },
        'tags': ['Tasks']
    }