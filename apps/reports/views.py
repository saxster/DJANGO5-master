"""
Backward Compatibility Shim for apps.reports.views

This file provides 100% backward compatibility for code importing from apps.reports.views.
All views are re-exported from the new domain-specific view modules.

Migration Date: 2025-09-30
Original File: Archived to .archive/reports_views.py_*

IMPORTANT: This is a compatibility layer only!
New code should import directly from apps.reports.views package or domain-specific modules.

Usage:
    # OLD (still works via this file):
    from apps.reports.views import DownloadReports
    from apps.reports import views
    views.DownloadReports.as_view()

    # NEW (recommended):
    from apps.reports.views.generation_views import DownloadReports
    from apps.reports.views import generation_views
    generation_views.DownloadReports.as_view()
"""

# Import everything from the new views package
from apps.reports.views import *
