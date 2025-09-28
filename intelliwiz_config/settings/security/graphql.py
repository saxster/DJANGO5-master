"""
GraphQL security configuration (CVSS 8.1 vulnerability fix).
GraphQL-specific security settings, rate limiting, and CSRF protection.
"""

import environ

env = environ.Env()

# GRAPHQL SECURITY CONFIGURATION (CVSS 8.1 vulnerability fix)

# GraphQL endpoint paths that require CSRF protection
GRAPHQL_PATHS = [
    '/api/graphql/',
    '/graphql/',
    '/graphql'
]

# GraphQL-specific rate limiting
ENABLE_GRAPHQL_RATE_LIMITING = True
GRAPHQL_RATE_LIMIT_WINDOW = 300  # 5 minutes
GRAPHQL_RATE_LIMIT_MAX = 100     # Max requests per window

# GraphQL query complexity limits
GRAPHQL_MAX_QUERY_DEPTH = 10
GRAPHQL_MAX_QUERY_COMPLEXITY = 1000

# GraphQL introspection settings
GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION = True

# GraphQL CSRF protection settings
GRAPHQL_CSRF_HEADER_NAMES = [
    'HTTP_X_CSRFTOKEN',
    'HTTP_X_CSRF_TOKEN',
]

# GraphQL security logging
GRAPHQL_SECURITY_LOGGING = {
    'ENABLE_REQUEST_LOGGING': True,
    'ENABLE_MUTATION_LOGGING': True,
    'ENABLE_RATE_LIMIT_LOGGING': True,
    'LOG_FAILED_CSRF_ATTEMPTS': True,
}

# GraphQL origin validation
GRAPHQL_ALLOWED_ORIGINS = env.list('GRAPHQL_ALLOWED_ORIGINS', default=[])
GRAPHQL_STRICT_ORIGIN_VALIDATION = env.bool('GRAPHQL_STRICT_ORIGIN_VALIDATION', default=False)