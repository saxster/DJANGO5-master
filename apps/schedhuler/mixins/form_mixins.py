"""
Form Mixins for Scheduling Application

These mixins extract common functionality from scheduling forms
to reduce code duplication and improve maintainability.

Follows Rule 8: All methods < 50 lines
Follows SRP: Each mixin has single responsibility
"""

import logging
from django import forms
from django.core.exceptions import ValidationError
from apps.core import utils
from apps.core.utils_new.cron_utilities import validate_cron_for_form
import apps.onboarding.utils as ob_utils

logger = logging.getLogger(__name__)


class ValidationMixin:
    """Common validation logic for scheduling forms."""

    def validate_date_range(self, from_date, to_date, from_field='fromdate', to_field='uptodate'):
        """
        Validate that from_date is not greater than to_date.

        Args:
            from_date: Start date value
            to_date: End date value
            from_field: Name of from date field
            to_field: Name of to date field

        Raises:
            ValidationError: If date range is invalid
        """
        if from_date and to_date and from_date > to_date:
            raise ValidationError({
                to_field: f"Valid To cannot be less than Valid From."
            })

    def validate_assignment(self, people, pgroup):
        """
        Validate that either people or group is assigned.

        Args:
            people: People assignment value
            pgroup: Group assignment value

        Raises:
            ValidationError: If neither people nor group is assigned
        """
        if people is None and pgroup is None:
            raise ValidationError(
                "Cannot proceed: assign tour to either people or group."
            )

    def validate_cron_expression(self, cron_value):
        """
        Validate cron expression with business rules.

        Args:
            cron_value: Cron expression string

        Returns:
            str: Validated cron expression

        Raises:
            ValidationError: If cron expression is invalid
        """
        if not cron_value:
            raise ValidationError("Invalid Cron")

        # Use centralized cron validation
        error = validate_cron_for_form(cron_value)
        if error:
            raise ValidationError(error)

        # Business rule: block "* * * * *" (every minute)
        parts = cron_value.strip().split()
        if len(parts) == 5 and parts[0] == "*":
            raise ValidationError(
                "Warning: Scheduling every minute is not allowed!"
            )

        return cron_value

    def check_nones(self, cleaned_data):
        """
        Replace None values with appropriate default objects.

        Args:
            cleaned_data: Form cleaned data dictionary

        Returns:
            dict: Cleaned data with None values replaced
        """
        fields_mapping = {
            "parent": "get_or_create_none_job",
            "people": "get_or_create_none_people",
            "pgroup": "get_or_create_none_pgroup",
            "asset": "get_or_create_none_asset",
        }

        for field, func_name in fields_mapping.items():
            if cleaned_data.get(field) in [None, ""]:
                cleaned_data[field] = getattr(utils, func_name)()

        return cleaned_data


class TimeMixin:
    """Time-related operations for scheduling forms."""

    TIME_CONVERSION_MAPPING = {
        "HRS": lambda time: time * 60,
        "DAYS": lambda time: time * 24 * 60,
    }

    def convert_to_minutes(self, time_type, time_value):
        """
        Convert time value to minutes based on type.

        Args:
            time_type: Time unit type (MIN, HRS, DAYS)
            time_value: Time value to convert

        Returns:
            int: Time value in minutes
        """
        if time_type in self.TIME_CONVERSION_MAPPING:
            return self.TIME_CONVERSION_MAPPING[time_type](time_value)

        # Default case: assume minutes
        return time_value

    def calculate_durations(self, cleaned_data, time_fields, type_fields):
        """
        Calculate durations in minutes for multiple time fields.

        Args:
            cleaned_data: Form cleaned data
            time_fields: List of time field names
            type_fields: List of corresponding type field names
        """
        for time_field, type_field in zip(time_fields, type_fields):
            time_value = cleaned_data.get(time_field)
            type_value = cleaned_data.get(type_field)

            if time_value is not None and type_value:
                cleaned_data[time_field] = self.convert_to_minutes(type_value, time_value)

    def clean_datetime_field(self, field_value):
        """
        Clean datetime field by converting to UTC.

        Args:
            field_value: Datetime field value

        Returns:
            datetime: UTC converted datetime or None
        """
        if field_value:
            return ob_utils.to_utc(field_value)
        return field_value


class DropdownMixin:
    """Dropdown field setup and management for scheduling forms."""

    def setup_dropdown_fields(self, request, field_configurations=None):
        """
        Setup dropdown fields based on configuration.

        Args:
            request: HTTP request object containing session data
            field_configurations: Dict mapping field names to configuration
        """
        if not field_configurations:
            return

        session = request.session if request else {}

        for field_name, config in field_configurations.items():
            if field_name in self.fields:
                self._configure_dropdown_field(field_name, config, session)

    def _configure_dropdown_field(self, field_name, config, session):
        """
        Configure individual dropdown field.

        Args:
            field_name: Name of the form field
            config: Configuration dictionary for the field
            session: User session data
        """
        try:
            model = config['model']
            filter_method = config['filter_method']
            sitewise = config.get('sitewise', False)

            # Get the filter method from the model manager
            if hasattr(model.objects, filter_method):
                method = getattr(model.objects, filter_method)
                if sitewise:
                    queryset = method(session, sitewise=True)
                else:
                    queryset = method(session)

                self.fields[field_name].queryset = queryset

        except (AttributeError, KeyError) as e:
            logger.warning(f"Failed to configure dropdown {field_name}: {e}")

    def set_display_none_fields(self, field_names):
        """
        Hide specified fields by setting display:none style.

        Args:
            field_names: List of field names to hide
        """
        for field_name in field_names:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs = {"style": "display:none"}

    def set_required_fields(self, field_names, required=True):
        """
        Set required attribute for specified fields.

        Args:
            field_names: List of field names
            required: Whether fields should be required
        """
        for field_name in field_names:
            if field_name in self.fields:
                self.fields[field_name].required = required