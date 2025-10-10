"""
Backward Compatibility Module for Report Generation Views

This file re-exports all views from the new split modules for backward compatibility.

DEPRECATED: Import directly from specific modules instead:
- pdf_views for PDF generation (GeneratePdf, GenerateLetter, GenerateDecalartionForm, highlight_text_in_pdf)
- export_views for exports (DownloadReports, return_status_of_report, upload_pdf)
- frappe_integration_views for ERP integration (get_data, GenerateAttendance, Frappe wrappers)
- schedule_views for scheduling (ScheduleEmailReport, DesignReport)

Extracted from monolithic generation_views.py (1,102 lines → 4 focused modules)
Date: 2025-10-10
Target Removal: 2026-01-10 (3 sprints after split)
"""

import warnings
warnings.warn(
    "Importing from generation_views.py is deprecated. "
    "Import from specific view modules instead (pdf_views, export_views, frappe_integration_views, schedule_views).",
    DeprecationWarning,
    stacklevel=2
)

# Re-export PDF views
from .pdf_views import (
    GeneratePdf,
    GenerateLetter,
    GenerateDecalartionForm,
    highlight_text_in_pdf
)

# Re-export export views
from .export_views import (
    DownloadReports,
    return_status_of_report,
    upload_pdf
)

# Re-export Frappe integration views
from .frappe_integration_views import (
    get_data,
    GenerateAttendance,
    getClient,
    getCustomer,
    getPeriod,
    getCustomersSites,
    getAllUAN,
    get_frappe_data
)

# Re-export schedule views
from .schedule_views import (
    ScheduleEmailReport,
    DesignReport
)

__all__ = [
    # PDF views
    'GeneratePdf',
    'GenerateLetter',
    'GenerateDecalartionForm',
    'highlight_text_in_pdf',
    # Export views
    'DownloadReports',
    'return_status_of_report',
    'upload_pdf',
    # Frappe integration views
    'get_data',
    'GenerateAttendance',
    'getClient',
    'getCustomer',
    'getPeriod',
    'getCustomersSites',
    'getAllUAN',
    'get_frappe_data',
    # Schedule views
    'ScheduleEmailReport',
    'DesignReport'
]
