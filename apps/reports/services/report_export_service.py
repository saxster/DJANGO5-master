"""
Report Export Service

Handles report export functionality including file processing,
data formatting, and secure file operations.

Security Features:
- CSV formula injection protection (CVE-2014-3524, CVE-2017-0199)
- File size validation
- Format whitelisting
- Comprehensive error logging
"""

import os
import re
import json
import tempfile
import logging
from typing import Dict, Any, Optional, Tuple, List
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import HttpResponse, FileResponse
from django.conf import settings
from django.core.files.storage import default_storage

# Import CSV injection protection
from apps.core.security.csv_injection_protection import (
    CSVInjectionProtector,
    sanitize_csv_data
)

logger = logging.getLogger("django")


class ReportExportService:
    """
    Service class for handling report export operations.

    Provides secure file handling, format conversion,
    and export validation functionality.

    Security Features:
    - Path traversal prevention (OWASP A05:2021)
    - File type validation with whitelist
    - File size limits enforcement
    - Comprehensive path normalization
    - Security event logging
    """

    ALLOWED_EXPORT_FORMATS = ['PDF', 'EXCEL', 'CSV', 'JSON']
    ALLOWED_FILE_EXTENSIONS = {'.pdf', '.xlsx', '.csv', '.json', '.html'}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit
    SAFE_PATH_PATTERN = re.compile(r'^[a-zA-Z0-9_\-./]+$')

    @staticmethod
    def validate_export_request(export_format: str, file_size: int = 0) -> Tuple[bool, Optional[str]]:
        """
        Validate export request parameters.

        Args:
            export_format: Format for export (PDF, EXCEL, CSV, JSON)
            file_size: Size of file being exported (optional)

        Returns:
            Tuple containing (is_valid, error_message)
        """
        try:
            # Validate export format
            if not export_format:
                return False, "Export format is required"

            if export_format.upper() not in ReportExportService.ALLOWED_EXPORT_FORMATS:
                return False, f"Unsupported export format: {export_format}"

            # Validate file size if provided
            if file_size > ReportExportService.MAX_FILE_SIZE:
                return False, f"File size exceeds maximum limit of {ReportExportService.MAX_FILE_SIZE // (1024*1024)}MB"

            logger.debug(f"Export request validation passed for format: {export_format}")
            return True, None

        except Exception as e:
            logger.error(f"Error validating export request: {str(e)}", exc_info=True)
            return False, "Validation error occurred"

    @staticmethod
    def export_to_excel(data: List[Dict], filename: str = "report.xlsx") -> Tuple[Optional[HttpResponse], Optional[str]]:
        """
        Export data to Excel format.

        Args:
            data: List of dictionaries containing report data
            filename: Name for the Excel file

        Returns:
            Tuple containing (http_response, error_message)
        """
        try:
            import pandas as pd
            from io import BytesIO

            # Validate inputs
            if not data:
                raise ValidationError("No data provided for export")

            if not filename.endswith('.xlsx'):
                filename += '.xlsx'

            # Convert data to DataFrame
            df = pd.DataFrame(data)

            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, sheet_name="Report", index=False, startrow=2, header=True)

                # Get workbook and worksheet objects for formatting
                workbook = writer.book
                worksheet = writer.sheets["Report"]

                # Auto-fit columns
                for i, width in enumerate(ReportExportService._get_column_widths(df)):
                    worksheet.set_column(i, i, width)

                # Add header with formatting
                merge_format = workbook.add_format({
                    "bg_color": "#c1c1c1",
                    "bold": True,
                })

                # Add report metadata
                from datetime import datetime
                header_text = f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                worksheet.merge_range("A1:E1", header_text, merge_format)

            output.seek(0)

            # Create HTTP response
            response = HttpResponse(
                output.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            logger.info(f"Successfully exported {len(data)} records to Excel: {filename}")
            return response, None

        except ImportError as e:
            logger.error(f"Missing Excel export dependencies: {str(e)}")
            return None, "Excel export not available - missing dependencies"
        except ValidationError as e:
            logger.warning(f"Excel export validation error: {str(e)}")
            return None, str(e)
        except Exception as e:
            logger.error(f"Error exporting to Excel: {str(e)}", exc_info=True)
            return None, "Failed to export to Excel"

    @staticmethod
    def export_to_csv(data: List[Dict], filename: str = "report.csv") -> Tuple[Optional[HttpResponse], Optional[str]]:
        """
        Export data to CSV format with formula injection protection.

        Security Features:
        - Automatic CSV formula injection protection
        - Sanitizes cells starting with =, +, -, @, |, %
        - Detects dangerous patterns (cmd, powershell, etc.)
        - Comprehensive sanitization logging

        Args:
            data: List of dictionaries containing report data
            filename: Name for the CSV file

        Returns:
            Tuple containing (http_response, error_message)
        """
        try:
            import csv
            from io import StringIO

            # Validate inputs
            if not data:
                raise ValidationError("No data provided for export")

            if not filename.endswith('.csv'):
                filename += '.csv'

            # SECURITY: Sanitize data against CSV formula injection
            protector = CSVInjectionProtector(strict_mode=True)
            sanitized_data = protector.sanitize_data(data)

            # Log sanitization report
            report = protector.get_sanitization_report()
            if report['cells_sanitized'] > 0:
                logger.warning(
                    "CSV formula injection protection activated",
                    extra={
                        'filename': filename,
                        'total_cells': report['total_cells_processed'],
                        'sanitized_cells': report['cells_sanitized'],
                        'sanitization_rate': f"{report['sanitization_rate']:.2f}%"
                    }
                )

            # Create CSV content with sanitized data
            output = StringIO()

            if sanitized_data:
                fieldnames = sanitized_data[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(sanitized_data)

            # Create HTTP response
            response = HttpResponse(output.getvalue(), content_type="text/csv")
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            logger.info(
                "Successfully exported CSV with security protection",
                extra={
                    'filename': filename,
                    'record_count': len(data),
                    'sanitization_applied': report['cells_sanitized'] > 0
                }
            )
            return response, None

        except ValidationError as e:
            logger.warning(f"CSV export validation error: {str(e)}")
            return None, str(e)
        except ImportError as e:
            logger.error(f"Missing CSV export dependencies: {str(e)}")
            return None, "CSV export not available - missing dependencies"
        except (IOError, OSError) as e:
            logger.error(f"File system error during CSV export: {str(e)}", exc_info=True)
            return None, "Failed to export CSV - file system error"
        except (TypeError, ValueError) as e:
            logger.error(f"Data format error during CSV export: {str(e)}", exc_info=True)
            return None, "Failed to export CSV - invalid data format"

    @staticmethod
    def export_to_json(data: List[Dict], filename: str = "report.json") -> Tuple[Optional[HttpResponse], Optional[str]]:
        """
        Export data to JSON format.

        Args:
            data: List of dictionaries containing report data
            filename: Name for the JSON file

        Returns:
            Tuple containing (http_response, error_message)
        """
        try:
            # Validate inputs
            if not isinstance(data, list):
                raise ValidationError("Data must be a list")

            if not filename.endswith('.json'):
                filename += '.json'

            # Create JSON content with proper formatting
            json_content = json.dumps(data, indent=2, default=str, ensure_ascii=False)

            # Create HTTP response
            response = HttpResponse(json_content, content_type="application/json")
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            logger.info(f"Successfully exported {len(data)} records to JSON: {filename}")
            return response, None

        except ValidationError as e:
            logger.warning(f"JSON export validation error: {str(e)}")
            return None, str(e)
        except json.JSONDecodeError as e:
            logger.error(f"JSON encoding error: {str(e)}")
            return None, "Failed to encode data as JSON"
        except Exception as e:
            logger.error(f"Error exporting to JSON: {str(e)}", exc_info=True)
            return None, "Failed to export to JSON"

    @staticmethod
    def validate_export_path(file_path: str, allowed_base_dirs: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive validation of export file paths.

        Security Checks:
        - Path traversal prevention (../, ..\, etc.)
        - Null byte injection prevention
        - Symlink attack prevention
        - Base directory restriction
        - File extension whitelist validation

        Args:
            file_path: Path to validate
            allowed_base_dirs: List of allowed base directories (default: MEDIA_ROOT, TEMP_REPORTS_GENERATED)

        Returns:
            Tuple containing (is_valid, error_message)
        """
        try:
            if not file_path:
                return False, "File path is required"

            # Default allowed directories
            if allowed_base_dirs is None:
                allowed_base_dirs = [
                    settings.MEDIA_ROOT,
                    getattr(settings, 'TEMP_REPORTS_GENERATED', '/tmp/reports')
                ]

            # SECURITY: Detect path traversal attempts
            if '..' in file_path:
                logger.warning(
                    "Path traversal attempt detected",
                    extra={'path': file_path, 'attack_type': 'path_traversal'}
                )
                return False, "Invalid path: directory traversal detected"

            # SECURITY: Detect null byte injection
            if '\x00' in file_path:
                logger.warning(
                    "Null byte injection attempt detected",
                    extra={'path': file_path, 'attack_type': 'null_byte_injection'}
                )
                return False, "Invalid path: null byte detected"

            # SECURITY: Validate path contains only safe characters
            if not ReportExportService.SAFE_PATH_PATTERN.match(file_path):
                logger.warning(
                    "Invalid characters in file path",
                    extra={'path': file_path, 'attack_type': 'invalid_characters'}
                )
                return False, "Invalid path: contains forbidden characters"

            # Normalize path (resolves ., .., symlinks)
            try:
                normalized_path = os.path.realpath(file_path)
            except (OSError, ValueError) as e:
                logger.warning(f"Path normalization failed: {str(e)}")
                return False, "Invalid path format"

            # SECURITY: Ensure path is within allowed directories
            is_in_allowed_dir = any(
                normalized_path.startswith(os.path.realpath(allowed_dir))
                for allowed_dir in allowed_base_dirs
            )

            if not is_in_allowed_dir:
                logger.warning(
                    "File access outside allowed directories",
                    extra={
                        'path': normalized_path,
                        'allowed_dirs': allowed_base_dirs,
                        'attack_type': 'directory_escape'
                    }
                )
                return False, "Access denied: file outside allowed directories"

            # Validate file extension
            file_ext = os.path.splitext(normalized_path)[1].lower()
            if file_ext not in ReportExportService.ALLOWED_FILE_EXTENSIONS:
                logger.warning(
                    "Forbidden file extension",
                    extra={'extension': file_ext, 'path': normalized_path}
                )
                return False, f"Invalid file type: {file_ext}"

            logger.debug(f"Path validation passed: {normalized_path}")
            return True, None

        except (OSError, IOError) as e:
            logger.error(f"File system error during path validation: {str(e)}")
            return False, "Path validation failed"
        except (TypeError, AttributeError) as e:
            logger.error(f"Path validation error: {str(e)}")
            return False, "Invalid path format"

    @staticmethod
    def secure_file_download(file_path: str, original_filename: str) -> Tuple[Optional[FileResponse], Optional[str]]:
        """
        Securely serve a file for download with comprehensive validation.

        Security Features:
        - Multi-layer path validation
        - File existence and type verification
        - Size limit enforcement
        - Filename sanitization
        - Security event logging

        Args:
            file_path: Path to the file to download
            original_filename: Original filename for the download

        Returns:
            Tuple containing (file_response, error_message)
        """
        try:
            # SECURITY: Comprehensive path validation
            is_valid, error_msg = ReportExportService.validate_export_path(file_path)
            if not is_valid:
                logger.warning(
                    "File download blocked by path validation",
                    extra={'path': file_path, 'reason': error_msg}
                )
                return None, error_msg

            # Get normalized path
            normalized_path = os.path.realpath(file_path)

            # Check if file exists
            if not os.path.exists(normalized_path):
                logger.info(f"File not found: {normalized_path}")
                return None, "File not found"

            # SECURITY: Verify it's a regular file (not directory/device/pipe)
            if not os.path.isfile(normalized_path):
                logger.warning(
                    "Attempted download of non-file object",
                    extra={'path': normalized_path, 'attack_type': 'non_file_access'}
                )
                return None, "Invalid file type"

            # SECURITY: Check file size
            file_size = os.path.getsize(normalized_path)
            if file_size > ReportExportService.MAX_FILE_SIZE:
                logger.warning(
                    "File size exceeds maximum limit",
                    extra={'path': normalized_path, 'size': file_size}
                )
                return None, f"File too large ({file_size // (1024*1024)}MB exceeds {ReportExportService.MAX_FILE_SIZE // (1024*1024)}MB limit)"

            # Sanitize filename
            safe_filename = ReportExportService._sanitize_filename(original_filename)

            # Create secure file response
            file_handle = open(normalized_path, 'rb')
            response = FileResponse(file_handle, as_attachment=True, filename=safe_filename)

            logger.info(
                "Secure file download initiated",
                extra={
                    'filename': safe_filename,
                    'size': file_size,
                    'path': normalized_path
                }
            )
            return response, None

        except PermissionDenied as e:
            logger.warning(f"File access denied: {str(e)}")
            return None, "Access denied"
        except (FileNotFoundError, IOError, OSError) as e:
            logger.warning(f"File operation error: {str(e)}")
            return None, "File access error"
        except (ValidationError, ValueError) as e:
            logger.warning(f"File download validation error: {str(e)}")
            return None, str(e)

    @staticmethod
    def get_column_widths(dataframe) -> List[int]:
        """
        Calculate optimal column widths for Excel export.

        PUBLIC API: Use this instead of duplicating get_col_widths() logic.
        This method is now the canonical implementation for all column width calculations.

        Args:
            dataframe: Pandas DataFrame

        Returns:
            List of column widths (integers representing character widths)

        Example:
            >>> df = pd.DataFrame({'A': [1, 2], 'BB': [10, 20]})
            >>> widths = ReportExportService.get_column_widths(df)
            >>> widths
            [1, 2]
        """
        try:
            return [
                max([len(str(s)) for s in dataframe[col].values] + [len(col)])
                for col in dataframe.columns
            ]
        except AttributeError as e:
            logger.warning(f"Invalid dataframe object for column width calculation: {e}")
            return [15] * len(getattr(dataframe, 'columns', []))
        except (KeyError, IndexError) as e:
            logger.warning(f"Column access error in width calculation: {e}")
            return [15] * len(dataframe.columns)
        except (TypeError, ValueError) as e:
            logger.warning(f"Data type error in width calculation: {e}")
            return [15] * len(dataframe.columns)
        except MemoryError as e:
            logger.error(f"Memory error calculating column widths for large dataframe: {e}")
            return [15] * len(dataframe.columns)
        except Exception as e:
            logger.exception(f"Unexpected error calculating column widths: {e}")
            return [15] * len(dataframe.columns)

    @staticmethod
    def _get_column_widths(dataframe) -> List[int]:
        """
        DEPRECATED: Use get_column_widths() instead.
        This private method is kept for backward compatibility in internal service calls.
        """
        return ReportExportService.get_column_widths(dataframe)

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent security issues.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        import re

        if not filename:
            return "download"

        # Remove directory separators and dangerous characters
        filename = re.sub(r'[/\\:*?"<>|]', '_', filename)

        # Limit length
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:90] + ext

        # Ensure filename is not empty
        if not filename.strip():
            filename = "download"

        return filename

    @staticmethod
    def cleanup_temp_file(file_path: str) -> bool:
        """
        Safely clean up temporary files.

        Args:
            file_path: Path to the temporary file

        Returns:
            Boolean indicating success
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
                return True
            return True  # File doesn't exist, consider it cleaned

        except Exception as e:
            logger.warning(f"Failed to cleanup temporary file {file_path}: {str(e)}")
            return False