"""
REST API Configuration
Configures Django REST Framework with comprehensive versioning and deprecation support.

Compliance with .claude/rules.md:
- Rule #6: Settings files < 200 lines
- Implements RFC 9745 (Deprecation Header) and RFC 8594 (Sunset Header) standards
"""

from datetime import timedelta

REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'VERSION_PARAM': 'version',

    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],

    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],

    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'MAX_PAGE_SIZE': 100,

    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],

    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],

    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],

    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],

    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/hour',
        'user': '600/hour',
        'premium': '6000/hour',
    },

    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

    'EXCEPTION_HANDLER': 'apps.core.api_versioning.exception_handler.versioned_exception_handler',

    'NON_FIELD_ERRORS_KEY': 'errors',

    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S.%fZ',
    'DATETIME_INPUT_FORMATS': ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S'],

    'COERCE_DECIMAL_TO_STRING': False,
    'COMPACT_JSON': True,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': 'youtility-api',

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    'JTI_CLAIM': 'jti',
}

API_VERSION_CONFIG = {
    'CURRENT_VERSION': 'v1',
    'SUPPORTED_VERSIONS': ['v1', 'v2'],
    'DEPRECATED_VERSIONS': [],
    'SUNSET_VERSIONS': [],

    'VERSION_HEADER_NAME': 'X-API-Version',
    'DEPRECATION_HEADER_NAME': 'Deprecation',
    'SUNSET_HEADER_NAME': 'Sunset',
    'WARNING_HEADER_NAME': 'Warning',
    'LINK_HEADER_NAME': 'Link',

    'DEFAULT_DEPRECATION_PERIOD_DAYS': 90,
    'DEFAULT_SUNSET_WARNING_DAYS': 30,
    'MINIMUM_SUPPORTED_VERSIONS': 2,

    'ENABLE_DEPRECATION_ANALYTICS': True,
    'ENABLE_VERSION_NEGOTIATION': True,
    'ENABLE_BACKWARD_COMPATIBILITY_MODE': True,
}

GRAPHQL_VERSION_CONFIG = {
    'SCHEMA_VERSION': '1.0',
    'ENABLE_FIELD_DEPRECATION': True,
    'ENABLE_DEPRECATION_TRACKING': True,
    'DEPRECATION_REASON_REQUIRED': True,

    'DEPRECATED_MUTATIONS': [
        {
            'name': 'upload_attachment',
            'deprecated_in': '1.0',
            'removed_in': '2.0',
            'sunset_date': '2026-06-30',
            'replacement': 'secure_file_upload',
            'migration_url': '/docs/api-migrations/file-upload-v2/',
        },
    ],

    'DEPRECATED_FIELDS': [],

    'ENABLE_INTROSPECTION_DEPRECATION_INFO': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'YOUTILITY5 Enterprise API',
    'DESCRIPTION': """
    ## YOUTILITY5 Comprehensive API Documentation

    Enterprise facility management platform with modern features:

    ### Features
    - **RESTful Design**: Clean REST API (v1/v2) with versioning
    - **GraphQL Support**: Flexible queries at /api/graphql/
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
    'REST_FRAMEWORK',
    'SIMPLE_JWT',
    'API_VERSION_CONFIG',
    'GRAPHQL_VERSION_CONFIG',
    'SPECTACULAR_SETTINGS',
]