"""
Asset views package - Exports concrete implementations.

This package contains refactored asset views organized by functionality:
- crud_views: Basic CRUD operations (AssetView, AssetDeleteView)
- list_views: List and filtering views (MasterAsset, AssetMaintenanceList)
- comparison_views: Analytics and comparison (AssetComparisionView, ParameterComparisionView)
- utility_views: Specialized utilities (PeopleNearAsset, Checkpoint, AssetLogView)

Migration from placeholder views completed: 2025-10-31
"""

# Import concrete implementations
from .crud_views import AssetView, AssetDeleteView
from .list_views import MasterAsset, AssetMaintenanceList
from .comparison_views import AssetComparisionView, ParameterComparisionView
from .utility_views import PeopleNearAsset, Checkpoint, AssetLogView

# Export all views
__all__ = [
    # CRUD operations
    'AssetView',
    'AssetDeleteView',
    # List views
    'MasterAsset',
    'AssetMaintenanceList',
    # Comparison/Analytics
    'AssetComparisionView',
    'ParameterComparisionView',
    # Utilities
    'PeopleNearAsset',
    'Checkpoint',
    'AssetLogView',
]
