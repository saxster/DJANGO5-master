"""
REST API Documentation Configuration (OpenAPI/Swagger)

Configures drf-spectacular for automatic OpenAPI schema generation.

Compliance with .claude/rules.md:
- Rule #6: Settings files < 200 lines
"""

SPECTACULAR_SETTINGS = {
    'TITLE': 'YOUTILITY5 Enterprise API',
    'DESCRIPTION': """
    ## YOUTILITY5 Comprehensive API Documentation

    Enterprise facility management platform with modern features:

    ### Features
    - **RESTful Design**: Clean REST API (v1/v2) with versioning
    - **GraphQL Support**: Flexible queries at /api/graphql/ (being phased out)
    - **WebSocket Support**: Real-time sync at ws://*/ws/mobile/sync
    - **Type Safety**: Pydantic validation across all endpoints
    - **Mobile Ready**: Dedicated sync endpoints for Android/iOS
    - **Idempotency**: 24-hour idempotency guarantees for mobile retries

    ### Authentication

    1. **JWT (JSON Web Tokens)** - Recommended for mobile
       - Obtain: POST /api/v1/auth/token/
       - Header: `Authorization: Bearer <token>`

    2. **API Keys** - For server-to-server
       - Header: `X-API-Key: <key>`

    ### Rate Limiting
    - Anonymous: 60 requests/hour
    - Authenticated: 600 requests/hour
    - Premium: 6000 requests/hour

    ### Pagination
    All list endpoints support:
    - Page-based: `?page=2&page_size=25`
    - Max page size: 100 items

    ### Codegen for Kotlin
    - REST: OpenAPI Generator with kotlinx.serialization
    - GraphQL: Apollo Kotlin
    - WebSocket: JSON Schema → sealed classes
    - Guide: /docs/mobile/kotlin-codegen-guide.md
    """,
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],  # Public docs

    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
    'SCHEMA_MOUNT_PATH': '/api/schema/',

    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',

    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
        'filter': True,
        'tryItOutEnabled': True,
        'displayRequestDuration': True,
        'docExpansion': 'none',  # Collapsed by default for better UX
        'defaultModelsExpandDepth': 2,
        'defaultModelExpandDepth': 2,
        'showExtensions': True,
        'showCommonExtensions': True,
    },

    'COMPONENT_SPLIT_REQUEST': True,
    'COMPONENT_SPLIT_PATCH': False,
    'COMPONENT_NO_READ_ONLY_REQUIRED': False,

    'PREPROCESSING_HOOKS': [
        'apps.api.docs.preprocessors.add_v2_tags',
        'apps.api.docs.preprocessors.filter_internal_endpoints',
    ],
    'POSTPROCESSING_HOOKS': [
        'apps.api.docs.postprocessors.add_kotlin_metadata',
        'apps.api.docs.postprocessors.add_idempotency_docs',
    ],

    'SECURITY': [
        {
            'Bearer': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        },
        {
            'ApiKey': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-API-Key',
            }
        }
    ],

    'TAGS': [
        {'name': 'Authentication', 'description': 'JWT tokens, API keys, OAuth2'},
        {'name': 'Mobile Sync', 'description': 'Mobile SDK sync operations (v1/v2)'},
        {'name': 'Tasks', 'description': 'Task and job management'},
        {'name': 'Attendance', 'description': 'Attendance tracking and GPS logs'},
        {'name': 'People', 'description': 'User and employee management'},
        {'name': 'Assets', 'description': 'Asset tracking and maintenance'},
        {'name': 'Tickets', 'description': 'Help desk and ticketing'},
        {'name': 'Reports', 'description': 'Report generation and scheduling'},
        {'name': 'Admin', 'description': 'Administrative operations'},
    ],

    'OPERATION_SORTER': 'method',
    'SORT_OPERATIONS': True,

    'EXAMPLES': True,
    'ENUM_NAME_OVERRIDES': {},

    'CONTACT': {
        'name': 'YOUTILITY API Team',
        'email': 'api@youtility.in',
        'url': 'https://youtility.in',
    },

    'LICENSE': {
        'name': 'Proprietary',
        'url': 'https://youtility.in/api-license',
    },

    'EXTERNAL_DOCS': {
        'description': 'Full API Documentation',
        'url': 'https://docs.youtility.in/api',
    },

    'SERVERS': [
        {'url': 'https://api.youtility.in', 'description': 'Production server'},
        {'url': 'https://staging-api.youtility.in', 'description': 'Staging server'},
        {'url': 'http://localhost:8000', 'description': 'Development server'},
    ],
}

__all__ = [
    'SPECTACULAR_SETTINGS',
]
