"""
Reports Views Module - Backward Compatibility Layer

This module provides 100% backward compatibility for the refactored reports views.
All view classes and helper functions are re-exported from their new locations.

Migration Date: 2025-09-30
Original File: apps/reports/views.py (1,911 lines)
New Structure: 4 domain-focused modules (base, template, configuration, generation)

Usage:
    # Old import (still works):
    from apps.reports.views import DownloadReports

    # New import (recommended):
    from apps.reports.views.generation_views import DownloadReports
"""

# Base classes and exceptions
from .base import (
    IntegrationException,
    MasterReportForm,
    MasterReportBelonging,
    SiteReportTemplateForm,
    IncidentReportTemplateForm,
)

# Template management views
from .template_views import (
    RetriveSiteReports,
    RetriveIncidentReports,
    MasterReportTemplateList,
    SiteReportTemplate,
    IncidentReportTemplate,
    AttendanceTemplate,
)

# Configuration views
from .configuration_views import (
    ConfigSiteReportTemplate,
    ConfigIncidentReportTemplate,
    ConfigWorkPermitReportTemplate,
)

# Generation views and helper functions
from .generation_views import (
    # View classes
    DownloadReports,
    DesignReport,
    ScheduleEmailReport,
    GeneratePdf,
    GenerateLetter,
    GenerateAttendance,
    GenerateDecalartionForm,
    # Helper functions
    return_status_of_report,
    get_data,
    getClient,
    getCustomer,
    getPeriod,
    getCustomersSites,
    getAllUAN,
    highlight_text_in_pdf,
    get_frappe_data,
    upload_pdf,
)

# Explicit __all__ for clarity and documentation
__all__ = [
    # Base
    "IntegrationException",
    "MasterReportForm",
    "MasterReportBelonging",
    "SiteReportTemplateForm",
    "IncidentReportTemplateForm",
    # Template Management
    "RetriveSiteReports",
    "RetriveIncidentReports",
    "MasterReportTemplateList",
    "SiteReportTemplate",
    "IncidentReportTemplate",
    "AttendanceTemplate",
    # Configuration
    "ConfigSiteReportTemplate",
    "ConfigIncidentReportTemplate",
    "ConfigWorkPermitReportTemplate",
    # Generation - View Classes
    "DownloadReports",
    "DesignReport",
    "ScheduleEmailReport",
    "GeneratePdf",
    "GenerateLetter",
    "GenerateAttendance",
    "GenerateDecalartionForm",
    # Generation - Helper Functions
    "return_status_of_report",
    "get_data",
    "getClient",
    "getCustomer",
    "getPeriod",
    "getCustomersSites",
    "getAllUAN",
    "highlight_text_in_pdf",
    "get_frappe_data",
    "upload_pdf",
]
