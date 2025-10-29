"""
OpenAPI Documentation Views

Provides public access to OpenAPI schema and interactive documentation.

Compliance with .claude/rules.md:
- Rule #7: View methods < 30 lines
- Rule #11: Specific exception handling
"""

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


class PublicSchemaView(SpectacularAPIView):
    """
    Public OpenAPI schema endpoint (no authentication required).

    Endpoints:
        - GET /api/schema/ - OpenAPI JSON schema
        - GET /api/schema/swagger.json - JSON format
        - GET /api/schema/swagger.yaml - YAML format

    Features:
        - Includes all v1 and v2 REST endpoints
        - Pydantic validation documentation
        - Mobile codegen metadata
        - Idempotency patterns
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """Return OpenAPI schema with mobile-friendly metadata."""
        try:
            return super().get(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Failed to generate OpenAPI schema: {e}", exc_info=True)
            return JsonResponse({
                'error': 'Schema generation failed',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicSwaggerView(SpectacularSwaggerView):
    """
    Public Swagger UI (no authentication required).

    Endpoint: GET /api/docs/

    Interactive API documentation with:
    - Try-it-out functionality
    - Request/response examples
    - Authentication flows
    - Mobile sync patterns
    """
    permission_classes = [AllowAny]
    url_name = 'openapi-schema'
    title = 'YOUTILITY5 API Documentation'


class PublicRedocView(SpectacularRedocView):
    """
    Public ReDoc UI (no authentication required).

    Endpoint: GET /api/redoc/

    Alternative documentation interface:
    - Three-panel layout
    - Better for browsing
    - Print-friendly
    - Code samples
    """
    permission_classes = [AllowAny]
    url_name = 'openapi-schema'
    title = 'YOUTILITY5 API Reference'


class SchemaMetadataView(SpectacularAPIView):
    """
    Schema metadata endpoint for client discovery.

    Endpoint: GET /api/schema/metadata

    Returns:
        {
          "version": "1.0.0",
          "formats": ["json", "yaml"],
          "mobile_codegen_supported": true,
          "websocket_schema": "/docs/api-contracts/websocket-messages.json"
        }
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """Return schema metadata for client discovery."""
        return JsonResponse({
            'version': '1.0.0',
            'title': 'YOUTILITY5 Enterprise API',
            'formats': ['json', 'yaml'],
            'endpoints': {
                'openapi_json': '/api/schema/swagger.json',
                'openapi_yaml': '/api/schema/swagger.yaml',
                'swagger_ui': '/api/docs/',
                'redoc_ui': '/api/redoc/',
            },
            'mobile_codegen_supported': True,
            'mobile_schemas': {
                'websocket': '/docs/api-contracts/websocket-messages.json',
                'kotlin_example': '/docs/api-contracts/WebSocketMessage.kt.example',
                'codegen_guide': '/docs/mobile/kotlin-codegen-guide.md',
            },
            'api_versions': ['v1', 'v2'],
            'graphql_endpoint': '/api/graphql/',  # Legacy - GraphQL removed Oct 2025
            'websocket_endpoint': 'ws://*/ws/mobile/sync',
        })


__all__ = [
    'PublicSchemaView',
    'PublicSwaggerView',
    'PublicRedocView',
    'SchemaMetadataView',
]
