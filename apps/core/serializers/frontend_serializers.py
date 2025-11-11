"""
Frontend-Friendly Serializers - Facade Module
This module provides backward compatibility by re-exporting from refactored submodules.

Original file has been split into:
- response_mixins.py: FrontendResponseMixin, MetadataSerializerMixin, FormSchemaSerializerMixin
- pagination_helpers.py: FrontendPagination, RelationshipEagerLoadingMixin
- caching_serializers.py: PerformanceSerializerMixin, CachingSerializerMixin, ComputedField, HumanReadableDateTimeField, FileFieldWithMetadata, BaseFrontendSerializer
"""

# Import all public classes from submodules for backward compatibility
from apps.core.serializers.response_mixins import (
    FrontendResponseMixin,
    MetadataSerializerMixin,
    FormSchemaSerializerMixin,
)

from apps.core.serializers.pagination_helpers import (
    FrontendPagination,
    RelationshipEagerLoadingMixin,
)

from apps.core.serializers.caching_serializers import (
    PerformanceSerializerMixin,
    CachingSerializerMixin,
    ComputedField,
    HumanReadableDateTimeField,
    FileFieldWithMetadata,
    BaseFrontendSerializer,
)

# Explicit public API
__all__ = [
    # Response formatting
    'FrontendResponseMixin',
    'MetadataSerializerMixin',
    'FormSchemaSerializerMixin',
    # Pagination and query optimization
    'FrontendPagination',
    'RelationshipEagerLoadingMixin',
    # Caching and performance
    'PerformanceSerializerMixin',
    'CachingSerializerMixin',
    'ComputedField',
    'HumanReadableDateTimeField',
    'FileFieldWithMetadata',
    'BaseFrontendSerializer',
]
