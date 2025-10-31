"""
⚠️ DEPRECATED: This file has been replaced with concrete implementations.

**Migration Date**: 2025-10-31
**Status**: PLACEHOLDER FILE - DO NOT USE

This file previously contained placeholder views that returned stub responses.
All asset views have been migrated to the `apps.activity.views.asset` package
with fully functional implementations.

## Migration Guide

**Old imports (DEPRECATED):**
```python
from apps.activity.views.asset_views import AssetView
```

**New imports (CURRENT):**
```python
from apps.activity.views.asset import AssetView
```

## Concrete Implementations

All views are now in dedicated modules:
- `apps/activity/views/asset/crud_views.py` - AssetView, AssetDeleteView
- `apps/activity/views/asset/list_views.py` - MasterAsset, AssetMaintenanceList
- `apps/activity/views/asset/comparison_views.py` - AssetComparisionView, ParameterComparisionView
- `apps/activity/views/asset/utility_views.py` - PeopleNearAsset, Checkpoint, AssetLogView

## Timeline

- **Before 2025-10-31**: Placeholders returned "to be implemented" strings
- **2025-10-31**: Migrated to concrete implementations
- **Future**: This file will be removed in a future release

## Backward Compatibility

For temporary backward compatibility, this file re-exports the concrete
implementations. However, you MUST update your imports to use the new
package location.

⚠️ **WARNING**: This re-export mechanism will be removed in the next major version.
"""

import warnings

# Issue deprecation warning when this module is imported
warnings.warn(
    "apps.activity.views.asset_views is deprecated. "
    "Use 'from apps.activity.views.asset import <ViewName>' instead. "
    "This compatibility shim will be removed in the next major version.",
    DeprecationWarning,
    stacklevel=2
)

# Temporary backward compatibility: re-export concrete implementations
# DO NOT rely on these imports - they will be removed!
from apps.activity.views.asset import (
    AssetView,
    AssetDeleteView,
    MasterAsset,
    AssetMaintenanceList,
    AssetComparisionView,
    ParameterComparisionView,
    PeopleNearAsset,
    Checkpoint,
    AssetLogView,
)

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
    'AssetMaintainceList',  # Typo preserved for backward compatibility
]

# Legacy alias for backward compatibility (preserves typo)
AssetMaintainceList = AssetMaintenanceList
