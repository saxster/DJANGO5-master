"""
GraphQL Security Module

Comprehensive security utilities for GraphQL operations including:
- Field-level permission controls
- Object-level authorization
- Query analysis and validation
- JWT/CSRF protection

Exports all GraphQL security utilities for easy importing.

Usage:
    from apps.core.security import (
        FieldPermissionChecker,
        ObjectPermissionValidator,
        GraphQLQuerySecurityAnalyzer
    )
"""

from .graphql_field_permissions import (
    FieldPermissionChecker,
    require_field_permission,
    filter_fields_by_permission,
    FieldPermissionMixin,
    create_permission_aware_type,
    GraphQLFieldAccessLog,
)

from .graphql_object_permissions import (
    ObjectPermissionValidator,
    can_view_object,
    can_modify_object,
    can_delete_object,
)

from .graphql_query_analysis import (
    GraphQLQuerySecurityAnalyzer,
    QueryAnalysisResult,
    SecurityIssue,
    ComplexityAnalyzer,
    DepthAnalyzer,
    IntrospectionAnalyzer,
    CostAnalyzer,
    PerformanceAnalyzer,
)

from .jwt_csrf_protection import (
    validate_jwt_csrf_token,
    generate_jwt_csrf_token,
)


__all__ = [
    'FieldPermissionChecker',
    'require_field_permission',
    'filter_fields_by_permission',
    'FieldPermissionMixin',
    'create_permission_aware_type',
    'GraphQLFieldAccessLog',
    'ObjectPermissionValidator',
    'can_view_object',
    'can_modify_object',
    'can_delete_object',
    'GraphQLQuerySecurityAnalyzer',
    'QueryAnalysisResult',
    'SecurityIssue',
    'ComplexityAnalyzer',
    'DepthAnalyzer',
    'IntrospectionAnalyzer',
    'CostAnalyzer',
    'PerformanceAnalyzer',
    'validate_jwt_csrf_token',
    'generate_jwt_csrf_token',
]