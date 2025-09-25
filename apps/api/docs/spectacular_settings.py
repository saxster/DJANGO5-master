"""
DRF Spectacular Settings for API Documentation

Configures OpenAPI schema generation and documentation UI.
"""

SPECTACULAR_SETTINGS = {
    'TITLE': 'YOUTILITY5 API',
    'DESCRIPTION': """
    ## YOUTILITY5 Comprehensive API Documentation
    
    Welcome to the YOUTILITY5 API documentation. This API provides comprehensive 
    access to all system functionality with modern features including:
    
    ### Features
    - **RESTful Design**: Clean, intuitive REST API following best practices
    - **GraphQL Support**: Flexible queries with GraphQL endpoint
    - **Authentication**: Multiple auth methods (JWT, API Key, OAuth2)
    - **Versioning**: API versioning for backward compatibility
    - **Pagination**: Flexible pagination options for large datasets
    - **Filtering**: Advanced filtering and search capabilities
    - **Performance**: Optimized queries with caching support
    - **Mobile Ready**: Dedicated endpoints for mobile applications
    
    ### Authentication
    
    The API supports multiple authentication methods:
    
    1. **JWT (JSON Web Tokens)**
       - Obtain token via `/api/v1/auth/token/`
       - Include in header: `Authorization: Bearer <token>`
    
    2. **API Keys**
       - Generate via `/api/v1/auth/api-key/`
       - Include in header: `X-API-Key: <key>`
    
    3. **OAuth2**
       - Initiate via `/api/v1/auth/oauth2/login/`
       - Supports Google, GitHub, Microsoft providers
    
    ### Rate Limiting
    
    - Anonymous: 60 requests/hour
    - Authenticated: 600 requests/hour
    - Premium: 6000 requests/hour
    
    ### Pagination
    
    All list endpoints support pagination:
    
    - Page-based: `?page=2&page_size=25`
    - Limit/Offset: `?limit=25&offset=50`
    - Cursor-based: `?cursor=cD0yMDIzLTEwLTE2KzAzJTNBMjQlM0E1MS4xNzI4NDI%3D`
    
    ### Filtering & Search
    
    Use query parameters for filtering:
    
    - Exact match: `?status=active`
    - Multiple values: `?status=active,pending`
    - Range: `?created_at__gte=2024-01-01&created_at__lte=2024-12-31`
    - Search: `?search=john`
    
    ### Field Selection
    
    Optimize responses by selecting specific fields:
    
    - Include fields: `?fields=id,name,email`
    - Exclude fields: `?exclude=password,secret`
    - Expand relations: `?expand=profile,groups`
    
    ### Bulk Operations
    
    Most endpoints support bulk operations:
    
    - Bulk create: `POST /api/v1/<resource>/bulk_create/`
    - Bulk update: `PUT /api/v1/<resource>/bulk_update/`
    - Bulk delete: `DELETE /api/v1/<resource>/bulk_delete/`
    
    ### Error Handling
    
    The API uses standard HTTP status codes and returns detailed error messages:
    
    ```json
    {
        "error": "Validation Error",
        "message": "Invalid input data",
        "details": {
            "email": ["This field is required."]
        },
        "status_code": 400,
        "timestamp": "2024-01-01T12:00:00Z"
    }
    ```
    
    ### Support
    
    For API support, please contact:
    - Email: api-support@youtility.in
    - Documentation: https://api.youtility.in/docs
    - Status Page: https://status.youtility.in
    """,
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    
    # Schema generation settings
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
    'SCHEMA_MOUNT_PATH': '/api/schema/',
    
    # UI Settings
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
    
    # Swagger UI settings
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
        'filter': True,
        'tryItOutEnabled': True,
        'displayRequestDuration': True,
        'docExpansion': 'none',
        'defaultModelsExpandDepth': 2,
        'defaultModelExpandDepth': 2,
        'showExtensions': True,
        'showCommonExtensions': True,
    },
    
    # Component settings
    'COMPONENT_SPLIT_REQUEST': True,
    'COMPONENT_SPLIT_PATCH': False,
    'COMPONENT_NO_READ_ONLY_REQUIRED': False,
    
    # Authentication
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
    
    # Tags
    'TAGS': [
        {'name': 'Authentication', 'description': 'Authentication endpoints'},
        {'name': 'People', 'description': 'People management'},
        {'name': 'Groups', 'description': 'Group management'},
        {'name': 'Assets', 'description': 'Asset management'},
        {'name': 'Jobs', 'description': 'Job and task management'},
        {'name': 'Reports', 'description': 'Reporting endpoints'},
        {'name': 'Mobile', 'description': 'Mobile-specific endpoints'},
        {'name': 'Admin', 'description': 'Administrative operations'},
    ],
    
    # Operation settings
    'OPERATION_SORTER': 'method',
    'SORT_OPERATIONS': True,
    
    # Preprocessing hooks
    'PREPROCESSING_HOOKS': [
        'apps.api.docs.preprocessors.custom_preprocessing_hook',
    ],
    
    # Postprocessing hooks
    'POSTPROCESSING_HOOKS': [
        'apps.api.docs.postprocessors.custom_postprocessing_hook',
    ],
    
    # Example generation
    'EXAMPLES': True,
    'EXAMPLE_VALUE_GENERATOR': 'apps.api.docs.examples.generate_example_value',
    
    # Enum settings
    'ENUM_NAME_OVERRIDES': {
        'ValidationErrorEnum': 'apps.api.docs.enums.ValidationErrorEnum',
        'OrderingEnum': 'apps.api.docs.enums.OrderingEnum',
    },
    
    # Contact information
    'CONTACT': {
        'name': 'YOUTILITY API Team',
        'email': 'api@youtility.in',
        'url': 'https://youtility.in',
    },
    
    # License
    'LICENSE': {
        'name': 'Proprietary',
        'url': 'https://youtility.in/api-license',
    },
    
    # External documentation
    'EXTERNAL_DOCS': {
        'description': 'Full API Documentation',
        'url': 'https://docs.youtility.in/api',
    },
    
    # Servers
    'SERVERS': [
        {'url': 'https://api.youtility.in', 'description': 'Production server'},
        {'url': 'https://staging-api.youtility.in', 'description': 'Staging server'},
        {'url': 'http://localhost:8000', 'description': 'Development server'},
    ],
}


# Add to Django settings
def configure_spectacular(settings):
    """
    Configure DRF Spectacular in Django settings.
    
    Add this to your settings.py:
    from apps.api.docs.spectacular_settings import configure_spectacular
    configure_spectacular(locals())
    """
    
    # Ensure DRF is configured
    if 'REST_FRAMEWORK' not in settings:
        settings['REST_FRAMEWORK'] = {}
    
    # Add spectacular settings
    settings['SPECTACULAR_SETTINGS'] = SPECTACULAR_SETTINGS
    
    # Configure REST_FRAMEWORK
    settings['REST_FRAMEWORK'].update({
        'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework_simplejwt.authentication.JWTAuthentication',
            'apps.api.authentication.backends.APIKeyAuthentication',
            'rest_framework.authentication.SessionAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
        'DEFAULT_PAGINATION_CLASS': 'apps.api.v1.pagination.custom_pagination.StandardResultsSetPagination',
        'PAGE_SIZE': 25,
        'DEFAULT_FILTER_BACKENDS': [
            'apps.api.v1.filters.custom_filters.DynamicFilterBackend',
            'apps.api.v1.filters.custom_filters.SmartSearchFilter',
            'apps.api.v1.filters.custom_filters.AdvancedOrderingFilter',
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
        },
        'EXCEPTION_HANDLER': 'apps.api.exceptions.custom_exception_handler',
        'NON_FIELD_ERRORS_KEY': 'errors',
        'DEFAULT_VERSION': 'v1',
        'ALLOWED_VERSIONS': ['v1', 'v2'],
        'VERSION_PARAM': 'version',
    })
    
    # Ensure spectacular is in installed apps
    if 'drf_spectacular' not in settings.get('INSTALLED_APPS', []):
        settings['INSTALLED_APPS'].append('drf_spectacular')
    
    # Add spectacular middleware for better error handling
    if 'MIDDLEWARE' in settings:
        middleware_class = 'apps.api.middleware.APIMiddleware'
        if middleware_class not in settings['MIDDLEWARE']:
            settings['MIDDLEWARE'].insert(0, middleware_class)