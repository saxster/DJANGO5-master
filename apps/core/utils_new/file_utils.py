"""
DEPRECATED: Legacy file_utils.py - Backward Compatibility Shim.

This file has been refactored from 3,137 lines to ~50 lines by extracting
functionality into focused modules following SOLID principles.

Original violations:
- Rule #11: Utility functions < 50 lines (get_type_data was 828 lines!)
- SRP: Mixed data templates, uploads, Excel, and queries
- ISP: One function handling 13 entity types

Refactored architecture:
- Data templates: apps/core/data/excel_templates.py, excel_examples.py
- Upload operations: apps/core/utils_new/upload_utils.py
- Excel generation: apps/core/utils_new/excel_utils.py
- Data extraction: apps/core/utils_new/data_extractors/ (Strategy Pattern)
- GPS utilities: apps/core/utils_new/gps_utils.py

Compliance: .claude/rules.md Rules #6, #7, #11 (File/function size limits, SRP)

Migration date: 2025-09-27
Status: DEPRECATED - Use specific modules instead

Usage:
    # OLD (deprecated):
    from apps.core.utils_new.file_utils import get_type_data

    # NEW (recommended):
    from apps.core.utils_new.data_extractors import get_type_data
"""

from apps.core.data.excel_templates import (
    HEADER_MAPPING,
    HEADER_MAPPING_UPDATE
)

from apps.core.data.excel_examples import (
    Example_data,
    Example_data_update
)

from apps.core.utils_new.upload_utils import (
    get_home_dir,
    upload,
    upload_vendor_file
)

from apps.core.utils_new.excel_utils import (
    excel_file_creation,
    excel_file_creation_update,
    download_qrcode
)

from apps.core.utils_new.data_extractors import get_type_data


__all__ = [
    'HEADER_MAPPING',
    'Example_data',
    'HEADER_MAPPING_UPDATE',
    'Example_data_update',
    'get_home_dir',
    'upload',
    'upload_vendor_file',
    'download_qrcode',
    'excel_file_creation',
    'excel_file_creation_update',
    'get_type_data',
]