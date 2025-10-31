"""
Custom Widgets for Question Import/Export.

Contains specialized widgets for:
- ArrayField handling (PostgreSQL arrays with NaN sanitization)
- Foreign key filtering (context-aware client/site scoping)

Extracted from: apps/activity/admin/question_admin.py (lines 649-686, 978-1010)
Date: 2025-10-10
"""
import math
from import_export import widgets as wg
from apps.activity.models.question_model import Question, QuestionSet


class ArrayFieldWidget(wg.Widget):
    """
    Custom widget for PostgreSQL ArrayField import/export.

    Handles:
    - NaN values from pandas (converts to empty list)
    - Float NaN values (converts to empty list)
    - String sanitization ('NONE', 'NULL', 'NAN' → empty list)
    - Comma-separated string splitting
    - Empty string filtering
    - List cleaning (removes 'NONE' and empty values)

    Examples:
        >>> widget = ArrayFieldWidget()
        >>> widget.clean(None)
        []
        >>> widget.clean(float('nan'))
        []
        >>> widget.clean("value1,value2,NONE")
        ['value1', 'value2']
        >>> widget.clean("NaN")
        []

    Returns:
        list: Cleaned list of values, or empty list if input is invalid/empty
    """
    def clean(self, value, row=None, **kwargs):
        """
        Clean and sanitize ArrayField input values.

        Args:
            value: Input value (can be None, float, list, or string)
            row: Row data (unused, for compatibility)
            **kwargs: Additional arguments (unused)

        Returns:
            list: Cleaned list of values
        """
        # Handle None or nan values
        if value is None:
            return []

        # Handle float nan
        if isinstance(value, float):
            if math.isnan(value):
                return []
            # If it's a non-nan float, convert to string
            value = str(value)

        # Handle list (already processed)
        if isinstance(value, list):
            # Filter out 'NONE' and empty strings from lists
            cleaned = [v for v in value if v and v.strip() and v.strip().upper() != 'NONE']
            return cleaned if cleaned else []

        # Handle string values
        if isinstance(value, str):
            value = value.strip()
            if not value or value.upper() in ['NAN', 'NONE', 'NULL']:
                return []
            # Split by comma and clean each value, excluding 'NONE'
            values = []
            for v in value.split(','):
                v = v.strip()
                if v and v.upper() != 'NONE':
                    values.append(v)
            return values

        # Default to empty list
        return []


class QsetFKW(wg.ForeignKeyWidget):
    """
    Foreign Key Widget for QuestionSet with client/site filtering.

    Filters QuestionSet records based on:
    - Client code (from row["Client*"])
    - Site code (from row["Site*"])
    - Only enabled question sets

    Used for: QuestionSetBelonging import (new records)

    Example:
        widget=QsetFKW(QuestionSet, "qsetname")
    """
    def get_queryset(self, value, row, *args, **kwargs):
        """
        Get filtered queryset for QuestionSet lookup.

        Args:
            value: Lookup value (question set name)
            row: Import row containing Client* and Site* fields

        Returns:
            QuerySet: Filtered QuestionSet records
        """
        return self.model.objects.select_related("client", "bu").filter(
            client__bucode__exact=row["Client*"],
            bu__bucode__exact=row["Site*"],
            enable=True,
        )


class QuesFKW(wg.ForeignKeyWidget):
    """
    Foreign Key Widget for Question with client filtering.

    Filters Question records based on:
    - Client code (from row["Client*"])
    - Only enabled questions

    Used for: QuestionSetBelonging import (new records)

    Example:
        widget=QuesFKW(Question, "quesname")
    """
    def get_queryset(self, value, row, *args, **kwargs):
        """
        Get filtered queryset for Question lookup.

        Args:
            value: Lookup value (question name)
            row: Import row containing Client* field

        Returns:
            QuerySet: Filtered Question records
        """
        return self.model.objects.filter(
            client__bucode__exact=row["Client*"], enable=True
        )


class QsetFKWUpdate(wg.ForeignKeyWidget):
    """
    Foreign Key Widget for QuestionSet with client/site filtering (UPDATE mode).

    Filters QuestionSet records based on:
    - Client code (from row["Client"] - no asterisk)
    - Site code (from row["Site"] - no asterisk)
    - Only enabled question sets

    Used for: QuestionSetBelonging update (existing records)

    Note: Column names differ from create mode (no asterisk suffix)

    Example:
        widget=QsetFKWUpdate(QuestionSet, "qsetname")
    """
    def get_queryset(self, value, row, *args, **kwargs):
        """
        Get filtered queryset for QuestionSet lookup (update mode).

        Args:
            value: Lookup value (question set name)
            row: Import row containing Client and Site fields

        Returns:
            QuerySet: Filtered QuestionSet records, or None if fields missing
        """
        if "Client" in row and "Site" in row:
            return self.model.objects.select_related("client", "bu").filter(
                client__bucode__exact=row["Client"],
                bu__bucode__exact=row["Site"],
                enable=True,
            )


class QuesFKWUpdate(wg.ForeignKeyWidget):
    """
    Foreign Key Widget for Question with client filtering (UPDATE mode).

    Filters Question records based on:
    - Client code (from row["Client"] - no asterisk)
    - Only enabled questions

    Used for: QuestionSetBelonging update (existing records)

    Note: Column name differs from create mode (no asterisk suffix)

    Example:
        widget=QuesFKWUpdate(Question, "quesname")
    """
    def get_queryset(self, value, row, *args, **kwargs):
        """
        Get filtered queryset for Question lookup (update mode).

        Args:
            value: Lookup value (question name)
            row: Import row containing Client field

        Returns:
            QuerySet: Filtered Question records, or None if field missing
        """
        if "Client" in row:
            return self.model.objects.filter(
                client__bucode__exact=row["Client"], enable=True
            )
