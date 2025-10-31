"""
OpenAPI Documentation URLs

Provides consolidated OpenAPI schema for all REST API endpoints (v1 + v2).
Enables Kotlin/Swift codegen for mobile clients.

Compliance with .claude/rules.md:
- Clear URL structure
- Public access for documentation
- Backward compatible endpoints
"""

from django.urls import path
from .views import (
    PublicSchemaView,
    PublicSwaggerView,
    PublicRedocView,
    SchemaMetadataView,
)

app_name = 'api_docs'

urlpatterns = [
    # ========== OPENAPI SCHEMA ENDPOINTS ==========
    # Primary endpoint for schema (defaults to JSON)
    path('', PublicSchemaView.as_view(), name='openapi-schema'),

    # Explicit format endpoints for codegen tools (use query param ?format=json/yaml)
    path('swagger.json', PublicSchemaView.as_view(), name='openapi-json'),
    path('swagger.yaml', PublicSchemaView.as_view(), name='openapi-yaml'),
    path('openapi.json', PublicSchemaView.as_view(), name='openapi-json-alt'),
    path('openapi.yaml', PublicSchemaView.as_view(), name='openapi-yaml-alt'),

    # Metadata endpoint for client discovery
    path('metadata/', SchemaMetadataView.as_view(), name='schema-metadata'),

    # ========== INTERACTIVE DOCUMENTATION ==========
    # Swagger UI (recommended for testing)
    path('swagger/', PublicSwaggerView.as_view(), name='swagger-ui'),

    # ReDoc (recommended for browsing)
    path('redoc/', PublicRedocView.as_view(), name='redoc-ui'),

    # Root docs redirect (legacy compatibility)
    path('docs/', PublicSwaggerView.as_view(), name='docs'),
]

# URL Summary for Kotlin Team:
# =============================
# JSON Schema: GET /api/schema/swagger.json
# YAML Schema: GET /api/schema/swagger.yaml
# Swagger UI:  GET /api/schema/swagger/
# ReDoc UI:    GET /api/schema/redoc/
# Metadata:    GET /api/schema/metadata/
