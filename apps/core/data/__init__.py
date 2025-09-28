"""
Configuration data package for Django 5 Enterprise Platform.

This package contains static configuration data extracted from monolithic
file_utils.py to comply with SRP and architecture limits.

Refactoring Date: 2025-09-27
Compliance: .claude/rules.md Rule #6 (Settings file size limits)
"""

from .excel_templates import HEADER_MAPPING, HEADER_MAPPING_UPDATE
from .excel_examples import Example_data, Example_data_update

__all__ = [
    'HEADER_MAPPING',
    'HEADER_MAPPING_UPDATE',
    'Example_data',
    'Example_data_update'
]