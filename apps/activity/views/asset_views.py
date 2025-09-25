"""
Asset views - organized imports from modular structure.

This module provides organized access to asset-related views by importing
from specialized modules for better code organization and maintainability.
"""

# Import from organized view modules
from apps.activity.views.asset.crud_views import AssetView, AssetDeleteView
from apps.activity.views.asset.list_views import MasterAsset, AssetMaintenanceList
from apps.activity.views.asset.comparison_views import AssetComparisionView, ParameterComparisionView
from apps.activity.views.asset.utility_views import PeopleNearAsset, Checkpoint, AssetLogView

# Maintain backward compatibility by exposing classes at module level
__all__ = [
    'AssetView',
    'AssetDeleteView',
    'MasterAsset',
    'AssetMaintenanceList',
    'AssetComparisionView',
    'ParameterComparisionView',
    'PeopleNearAsset',
    'Checkpoint',
    'AssetLogView',
]

# Legacy alias for backward compatibility
AssetMaintainceList = AssetMaintenanceList  # Keep original typo for compatibility