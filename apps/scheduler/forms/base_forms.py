"""
Base Forms for Scheduling Application

This module provides base form classes that consolidate common
functionality across task and tour forms.

Follows Rule 8: All methods < 50 lines
Follows SRP: Single responsibility for each form type
"""

import logging
from django.conf import settings
from django import forms
from django.utils import timezone as dtimezone
from datetime import datetime

from apps.activity.forms.job_form import JobForm, JobNeedForm
from apps.core import utils
from apps.core.utils_new.business_logic import initailize_form_fields
from apps.core.caching.form_mixins import CachedDropdownMixin
from apps.scheduler.mixins.form_mixins import (
    ValidationMixin,
    TimeMixin,
    DropdownMixin
)

logger = logging.getLogger(__name__)


class BaseSchedulingForm(
    CachedDropdownMixin,
    ValidationMixin,
    TimeMixin,
    DropdownMixin,
    JobForm
):
    """
    Base form for all scheduling operations.

    Provides common functionality for tasks and tours including:
    - Common field configurations
    - Validation logic
    - Dropdown handling
    - Time conversion utilities
    """

    # Common choices used across scheduling forms
    ASSIGN_TO_CHOICES = [("PEOPLE", "People"), ("GROUP", "Group")]
    TIME_CHOICES = [("MIN", "Min"), ("HRS", "Hours"), ("DAYS", "Days")]

    # Common fields
    assign_to = forms.ChoiceField(choices=ASSIGN_TO_CHOICES, initial="PEOPLE")
    required_css_class = "required"

    # Common hidden fields that most scheduling forms hide
    COMMON_HIDDEN_FIELDS = [
        "identifier", "starttime", "endtime", "frequency"
    ]

    class Meta(JobForm.Meta):
        """Meta configuration inheriting from JobForm."""
        pass

    def __init__(self, *args, **kwargs):
        """Initialize base scheduling form with common setup."""
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        self.setup_common_fields()
        self.setup_datetime_formats()
        self.setup_initial_values()

        # Initialize form fields with business logic
        initailize_form_fields(self)

        logger.debug(f"Initialized {self.__class__.__name__}")

    def setup_common_fields(self):
        """Setup common field configurations."""
        # Hide common fields
        self.set_display_none_fields(self.COMMON_HIDDEN_FIELDS)

        # Set common field requirements
        if hasattr(self, 'required_fields'):
            self.set_required_fields(self.required_fields, required=True)

    def setup_datetime_formats(self):
        """Setup datetime input formats for date fields."""
        datetime_fields = ["fromdate", "uptodate", "plandatetime", "expirydatetime"]

        for field_name in datetime_fields:
            if field_name in self.fields:
                self.fields[field_name].input_formats = settings.DATETIME_INPUT_FORMATS

    def setup_initial_values(self):
        """Setup initial values for form fields."""
        # Override in subclasses for specific initial values
        pass

    def clean(self):
        """Common validation logic for all scheduling forms."""
        super().clean()
        cleaned_data = self.cleaned_data

        # Replace None values with defaults
        cleaned_data = self.check_nones(cleaned_data)

        # Validate assignments
        self.validate_assignment(
            cleaned_data.get("people"),
            cleaned_data.get("pgroup")
        )

        # Validate date ranges
        self.validate_date_range(
            cleaned_data.get("fromdate"),
            cleaned_data.get("uptodate")
        )

        self.cleaned_data = cleaned_data
        return cleaned_data

    def clean_cronstrue(self):
        """Validate cron expression."""
        cron_value = self.cleaned_data.get("cron")
        return self.validate_cron_expression(cron_value)

    def is_valid(self):
        """Override to add error classes for invalid fields."""
        result = super().is_valid()
        utils.apply_error_classes(self)
        return result


class BaseTourForm(BaseSchedulingForm):
    """
    Base form for tour-related operations.

    Extends BaseSchedulingForm with tour-specific functionality.
    """

    # Tour-specific fields
    istimebound = forms.BooleanField(
        initial=True,
        required=False,
        label="Is Time Restricted"
    )
    isdynamic = forms.BooleanField(
        initial=False,
        required=False,
        label="Is Dynamic"
    )

    # Default required fields for tours
    required_fields = ["ticketcategory"]

    def setup_initial_values(self):
        """Setup tour-specific initial values."""
        super().setup_initial_values()

        if self.instance.id and hasattr(self.instance, 'other_info'):
            other_info = self.instance.other_info or {}
            self.fields["istimebound"].initial = other_info.get("istimebound", True)
            self.fields["isdynamic"].initial = other_info.get("isdynamic", False)

    def set_required_false_for_dynamic(self):
        """Set fields as not required when dynamic tour is enabled."""
        is_dynamic = (
            self.data.get("isdynamic") or
            (self.instance.id and
             hasattr(self.instance, 'other_info') and
             self.instance.other_info.get("isdynamic", False))
        )

        if is_dynamic:
            dynamic_optional_fields = [
                "planduration", "gracetime", "cron", "fromdate", "uptodate"
            ]
            self.set_required_fields(dynamic_optional_fields, required=False)

    def set_instance_data_for_dynamic(self):
        """Preserve instance data for dynamic tours."""
        if (self.instance.id and
            hasattr(self.instance, 'other_info') and
            self.instance.other_info.get("isdynamic", False)):

            preserved_fields = [
                "fromdate", "uptodate", "planduration",
                "gracetime", "istimebound", "isdynamic"
            ]

            for field in preserved_fields:
                if hasattr(self.instance, field):
                    if field in ["istimebound", "isdynamic"]:
                        self.cleaned_data[field] = self.instance.other_info.get(field)
                    else:
                        self.cleaned_data[field] = getattr(self.instance, field)

    def clean(self):
        """Tour-specific validation logic."""
        super().clean()
        cleaned_data = self.cleaned_data

        # Handle dynamic tour settings
        if cleaned_data.get("isdynamic"):
            cleaned_data["fromdate"] = dtimezone.now()
            cleaned_data["uptodate"] = datetime(9999, 12, 30, 23, 59)
            cleaned_data["planduration"] = 0
            cleaned_data["gracetime"] = 0
            cleaned_data["expirytime"] = 0

        # Validate ticketcategory requirement
        if not cleaned_data.get("ticketcategory"):
            raise forms.ValidationError({
                "ticketcategory": "Notify Category is required."
            })

        return cleaned_data


class BaseTaskForm(BaseSchedulingForm):
    """
    Base form for task-related operations.

    Extends BaseSchedulingForm with task-specific functionality.
    """

    # Task-specific time conversion fields
    planduration_type = forms.ChoiceField(
        choices=BaseSchedulingForm.TIME_CHOICES,
        initial="MIN"
    )
    gracetime_type = forms.ChoiceField(
        choices=BaseSchedulingForm.TIME_CHOICES,
        initial="MIN"
    )
    expirytime_type = forms.ChoiceField(
        choices=BaseSchedulingForm.TIME_CHOICES,
        initial="MIN"
    )

    def clean(self):
        """Task-specific validation logic."""
        super().clean()
        cleaned_data = self.cleaned_data

        # Convert time durations to minutes
        time_fields = ["planduration", "expirytime", "gracetime"]
        type_fields = ["planduration_type", "expirytime_type", "gracetime_type"]

        self.calculate_durations(cleaned_data, time_fields, type_fields)

        return cleaned_data


class BaseJobneedForm(ValidationMixin, TimeMixin, JobNeedForm):
    """
    Base form for jobneed-related operations.

    Provides common jobneed functionality across task and tour jobneeds.
    """

    ASSIGN_TO_CHOICES = BaseSchedulingForm.ASSIGN_TO_CHOICES
    TIME_CHOICES = [("MIN", "Min"), ("HRS", "Hour"), ("DAY", "Day"), ("WEEK", "Week")]

    assign_to = forms.ChoiceField(choices=ASSIGN_TO_CHOICES, initial="PEOPLE")
    required_css_class = "required"

    def __init__(self, *args, **kwargs):
        """Initialize base jobneed form."""
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        self.setup_datetime_formats()
        initailize_form_fields(self)

    def setup_datetime_formats(self):
        """Setup datetime formats for jobneed fields."""
        datetime_fields = ["plandatetime", "expirydatetime", "starttime", "endtime"]

        for field_name in datetime_fields:
            if field_name in self.fields:
                self.fields[field_name].input_formats = settings.DATETIME_INPUT_FORMATS

    def clean_plandatetime(self):
        """Clean plan datetime field."""
        return self.clean_datetime_field(self.cleaned_data.get("plandatetime"))

    def clean_expirydatetime(self):
        """Clean expiry datetime field."""
        return self.clean_datetime_field(self.cleaned_data.get("expirydatetime"))

    def clean_starttime(self):
        """Clean start time field."""
        return self.clean_datetime_field(self.cleaned_data.get("starttime"))

    def clean_endtime(self):
        """Clean end time field."""
        return self.clean_datetime_field(self.cleaned_data.get("endtime"))

    @staticmethod
    def clean_frequency():
        """Default frequency for jobneeds."""
        return "NONE"

    def is_valid(self):
        """Override to add error classes."""
        result = super().is_valid()
        utils.apply_error_classes(self)
        return result