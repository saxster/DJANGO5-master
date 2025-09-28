"""
Excel Generation Utilities for Django 5 Enterprise Platform.

This module provides Excel file creation functionality for bulk import/export
operations across various entity types.

Refactored from: apps.core.utils_new.file_utils (3,122 lines)
Purpose: SRP compliance - separate Excel operations from upload/data logic
Compliance: .claude/rules.md Rule #6 (File size limits)

Usage:
    from apps.core.utils_new.excel_utils import excel_file_creation
    buffer = excel_file_creation({'template': 'TYPEASSIST'})
"""

import pandas as pd
from io import BytesIO
from typing import Dict, Any
from apps.core.data.excel_templates import HEADER_MAPPING, HEADER_MAPPING_UPDATE
from apps.core.data.excel_examples import Example_data, Example_data_update


def excel_file_creation(R: Dict[str, Any]) -> BytesIO:
    """
    Create Excel template file with reference data and empty data section.

    Args:
        R: Dictionary containing 'template' key with entity type name

    Returns:
        BytesIO: Excel file buffer ready for download
    """
    columns = HEADER_MAPPING.get(R["template"])
    data_ex = Example_data.get(R["template"])

    df = pd.DataFrame(data_ex, columns=columns)
    main_header = pd.DataFrame([columns], columns=columns)
    empty_row = pd.DataFrame([[""] * len(df.columns)], columns=df.columns)
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, header=True, startrow=2)
        empty_row.to_excel(writer, index=False, header=False, startrow=len(df) + 3)
        main_header = pd.DataFrame([columns], columns=columns)
        main_header.to_excel(writer, index=False, header=False, startrow=len(df) + 6)
        workbook = writer.book
        worksheet = writer.sheets["Sheet1"]
        bold_format = workbook.add_format({"bold": True, "border": 1})
        for col_num, value in enumerate(columns):
            worksheet.write(len(df) + 6, col_num, value, bold_format)
        merge_format = workbook.add_format({"bg_color": "#E2F4FF", "border": 1})
        Text_for_sample_data = "[ Refernce Data ] Take the Reference of the below data to fill data in correct format :-"
        Text_for_actual_data = (
            "[ Actual Data ] Start filling data below the following headers :-"
        )
        worksheet.merge_range("A2:D2", Text_for_sample_data, merge_format)
        worksheet.merge_range("A9:D9", Text_for_actual_data, merge_format)

    buffer.seek(0)
    return buffer


def excel_file_creation_update(R: Dict[str, Any], S: Dict[str, Any]) -> BytesIO:
    """
    Create Excel template file for updating existing records.

    Includes reference data, existing database data, and empty section for updates.

    Args:
        R: Dictionary containing 'template' key with entity type name
        S: Session data dictionary for database query context

    Returns:
        BytesIO: Excel file buffer ready for download
    """
    from apps.core.utils_new.data_extractors import get_type_data

    columns = HEADER_MAPPING_UPDATE.get(R["template"])
    data_ex = Example_data_update.get(R["template"])
    get_data = get_type_data(R["template"], S)
    df = pd.DataFrame(data_ex, columns=columns)
    main_header = pd.DataFrame(get_data, columns=columns)
    empty_row = pd.DataFrame([[""] * len(df.columns)], columns=df.columns)
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, header=True, startrow=2)
        empty_row.to_excel(writer, index=False, header=False, startrow=len(df) + 3)
        main_header = pd.DataFrame(get_data, columns=columns)
        main_header.to_excel(writer, index=False, header=False, startrow=len(df) + 7)
        workbook = writer.book
        worksheet = writer.sheets["Sheet1"]
        bold_format = workbook.add_format({"bold": True, "border": 1})
        for col_num, value in enumerate(columns):
            worksheet.write(len(df) + 6, col_num, value, bold_format)
        merge_format = workbook.add_format({"bg_color": "#E2F4FF", "border": 1})
        Text_for_sample_data = "[ Refernce Data ] Take the Reference of the below data to fill data in correct format :-"
        Text_for_actual_data = "[ Actual Data ] Please update the data only for the columns in the database table that need to be changed :-"
        worksheet.merge_range("A2:D2", Text_for_sample_data, merge_format)
        worksheet.merge_range("A9:D9", Text_for_actual_data, merge_format)

    buffer.seek(0)
    return buffer


def download_qrcode(
    code: str,
    name: str,
    report_name: str,
    session: Dict[str, Any],
    request
) -> Any:
    """
    Generate and download QR code report.

    Args:
        code: QR code value to encode
        name: Display name for the QR code
        report_name: Name of the report template to use
        session: Session data dictionary containing client_id
        request: Django HTTP request object

    Returns:
        Generated report object (format depends on ReportFormat implementation)
    """
    from apps.reports import utils as rutils

    report_essentials = rutils.ReportEssentials(report_name=report_name)
    ReportFormat = report_essentials.get_report_export_object()
    report = ReportFormat(
        filename=report_name,
        client_id=session["client_id"],
        formdata={"print_single_qr": code, "qrsize": 200, "name": name},
        request=request,
        returnfile=False,
    )
    return report.execute()


__all__ = [
    'excel_file_creation',
    'excel_file_creation_update',
    'download_qrcode'
]