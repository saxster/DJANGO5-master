"""
Reports forms - Refactored modular structure with backward compatibility.

This package provides all forms for the reports app, organized by functionality:
- template_forms: Report template forms (SiteReportTemplate, IncidentReportTemplate)
- report_forms: Main report generation form (ReportForm)
- scheduled_forms: Scheduled report and PDF generation forms
- utility_forms: Test and report builder forms

All imports are re-exported here for 100% backward compatibility with the original
monolithic forms.py file (616 lines -> 4 focused modules, ~580 lines).
"""

# Report templates
from .template_forms import (
    MasterReportTemplate,
    SiteReportTemplate,
    IncidentReportTemplate,
)

# Report generation
from .report_forms import ReportForm

# Scheduled reports and PDF
from .scheduled_forms import (
    EmailReportForm,
    GeneratePDFForm,
)

# Utilities
from .utility_forms import (
    TestForm,
    ReportBuilderForm,
)

__all__ = [
    # Templates
    "MasterReportTemplate",
    "SiteReportTemplate",
    "IncidentReportTemplate",
    # Report generation
    "ReportForm",
    # Scheduled
    "EmailReportForm",
    "GeneratePDFForm",
    # Utilities
    "TestForm",
    "ReportBuilderForm",
]
