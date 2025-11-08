"""
Reports forms module - split for maintainability.

Exports all forms for backward compatibility.
"""

from .builder_forms import TestForm, ReportBuilderForm
from .report_forms import ReportForm
from .email_forms import EmailReportForm
from .pdf_forms import GeneratePDFForm

__all__ = [
    'TestForm',
    'ReportBuilderForm',
    'ReportForm',
    'EmailReportForm',
    'GeneratePDFForm',
]
