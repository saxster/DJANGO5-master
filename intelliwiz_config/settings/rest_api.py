"""
REST API Configuration (Aggregator)

Imports REST API settings from split modules to comply with Rule #6 (< 200 lines).

Module Structure:
- rest_api_core.py: Core DRF settings, authentication, pagination
- rest_api_versioning.py: API versioning and deprecation policies
- rest_api_docs.py: OpenAPI/Swagger documentation settings

Compliance with .claude/rules.md:
- Rule #6: Settings files < 200 lines (this aggregator: ~20 lines)
"""

# Import from split modules
from .rest_api_core import REST_FRAMEWORK, SIMPLE_JWT
from .rest_api_versioning import API_VERSION_CONFIG, GRAPHQL_VERSION_CONFIG
from .rest_api_docs import SPECTACULAR_SETTINGS

__all__ = [
    'REST_FRAMEWORK',
    'SIMPLE_JWT',
    'API_VERSION_CONFIG',
    'GRAPHQL_VERSION_CONFIG',
    'SPECTACULAR_SETTINGS',
]
