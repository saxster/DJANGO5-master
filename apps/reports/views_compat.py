"""
Backward Compatibility Shim for apps.reports.views

⚠️ DEPRECATED: This file will be removed in 2 sprints (target: 2025-12-10)
Renamed from views.py → views_compat.py to resolve name collision with views/ package.

This file provides 100% backward compatibility for code importing from apps.reports.views_compat.
All views are re-exported from the new domain-specific view modules.

Migration Date: 2025-09-30 (initial split)
Rename Date: 2025-10-10 (name collision fix)
Original File: Archived to .archive/reports_views.py_*

CRITICAL: Name collision resolved!
- OLD: apps/reports/views.py (file) conflicted with apps/reports/views/ (package)
- NEW: apps/reports/views_compat.py (file) + apps/reports/views/ (package)

IMPORTANT: This is a temporary compatibility layer!
New code MUST import directly from apps.reports.views package or domain-specific modules.

Usage:
    # ❌ DEPRECATED (still works but will be removed):
    from apps.reports import views_compat
    views_compat.DownloadReports.as_view()

    # ✅ CORRECT (use this pattern):
    from apps.reports.views.generation_views import DownloadReports
    # OR
    from apps.reports.views import generation_views
    generation_views.DownloadReports.as_view()

Migration Guide:
    1. Search codebase for: `from apps.reports import views`
    2. Replace with: `from apps.reports.views import generation_views`
    3. Update references: `views.DownloadReports` → `generation_views.DownloadReports`
"""

import warnings

# Issue deprecation warning when this module is imported
warnings.warn(
    "apps.reports.views_compat is deprecated and will be removed in 2 sprints. "
    "Import directly from apps.reports.views.generation_views or other view modules instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import everything from the new views package
from apps.reports.views import *
