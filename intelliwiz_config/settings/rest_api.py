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
    'DESCRIPTION': 'Enterprise facility management platform with versioned REST and GraphQL APIs',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticatedOrReadOnly'],

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
        'docExpansion': 'list',
        'defaultModelsExpandDepth': 2,
        'defaultModelExpandDepth': 2,
    },

    'COMPONENT_SPLIT_REQUEST': True,
    'PREPROCESSING_HOOKS': [],
    'POSTPROCESSING_HOOKS': [],

    'SERVERS': [
        {'url': 'https://api.youtility.in', 'description': 'Production'},
        {'url': 'https://staging-api.youtility.in', 'description': 'Staging'},
        {'url': 'http://localhost:8000', 'description': 'Development'},
    ],

    'CONTACT': {
        'name': 'YOUTILITY API Team',
        'email': 'api@youtility.in',
    },

    'LICENSE': {
        'name': 'Proprietary',
    },
}

__all__ = [
    'REST_FRAMEWORK',
    'SIMPLE_JWT',
    'API_VERSION_CONFIG',
    'GRAPHQL_VERSION_CONFIG',
    'SPECTACULAR_SETTINGS',
]