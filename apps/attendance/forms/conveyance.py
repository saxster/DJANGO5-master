"""
Conveyance and Transportation Form Module
Handles transportation expense tracking with location and distance validation.

Part of: apps/attendance/forms/
"""

from django import forms
from django.core.exceptions import ValidationError
import django_select2.forms as s2forms
import json
import logging
from apps.core.exceptions.patterns import BUSINESS_LOGIC_EXCEPTIONS, JSON_EXCEPTIONS, PARSING_EXCEPTIONS


from apps.attendance import models as atdm
from apps.core import utils
from apps.core.utils_new.business_logic import initailize_form_fields

logger = logging.getLogger(__name__)


class ConveyanceForm(forms.ModelForm):
    required_css_class = "required"
    transportmodes = forms.MultipleChoiceField(
        choices=atdm.PeopleEventlog.TransportMode.choices,
        required=False,
        widget=s2forms.Select2MultipleWidget(
            attrs={'class': 'form-control', "data-theme": "bootstrap5"}
        ),
        label="Transport Modes",
    )

    class Meta:
        model = atdm.PeopleEventlog
        fields = [
            "people",
            "transportmodes",
            "expamt",
            "duration",
            "ctzoffset",
            "distance",
            "startlocation",
            "endlocation",
            "punchintime",
            "punchouttime",
        ]
        widgets = {
            "startlocation": forms.Textarea(attrs={"rows": 3, "cols": 40, "class": "form-control"}),
            "endlocation": forms.Textarea(attrs={"rows": 3, "cols": 40, "class": "form-control"}),
            "duration": forms.NumberInput(attrs={"readonly": True, "class": "form-control"}),
            "people": s2forms.ModelSelect2Widget(
                model=atdm.PeopleEventlog._meta.get_field('people').related_model,
                search_fields=["peoplename__icontains"],
                attrs={'class': 'form-control', "data-theme": "bootstrap5"}
            ),
        }
        labels = {
            "expamt": "Expense Amount",
            "transportmodes": "Transport Modes",
            "startlocation": "Start Location",
            "endlocation": "End Location",
            "punchintime": "Start Time",
            "punchouttime": "End Time",
            "distance": "Distance",
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)

        if self.instance and self.instance.pk:
            self._initialize_transport_modes()
            self._initialize_location_fields()

        self._configure_field_requirements()

    def _initialize_transport_modes(self):
        """Initialize transport modes field with proper data handling"""
        if not self.instance.transportmodes:
            return

        transport_data = self.instance.transportmodes

        try:
            if isinstance(transport_data, list) and transport_data:
                first_item = transport_data[0]

                if isinstance(first_item, str) and first_item.startswith('['):
                    try:
                        actual_modes = json.loads(first_item)
                        if isinstance(actual_modes, list):
                            self.fields['transportmodes'].initial = actual_modes
                        else:
                            logger.warning(f"Invalid transport modes format: {actual_modes}")
                            self.fields['transportmodes'].initial = []
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Failed to parse transport modes JSON: {e}")
                        self.fields['transportmodes'].initial = transport_data
                else:
                    self.fields['transportmodes'].initial = transport_data
            else:
                logger.warning(f"Unexpected transport modes format: {type(transport_data)}")
                self.fields['transportmodes'].initial = []

        except JSON_EXCEPTIONS as e:
            logger.error(f"Error initializing transport modes for conveyance {self.instance.id}: {e}", exc_info=True)
            self.fields['transportmodes'].initial = []

    def _initialize_location_fields(self):
        """Initialize location fields using model display properties"""
        try:
            if self.instance.startlocation:
                location_display = self.instance.startlocation_display
                if location_display and location_display != "Invalid coordinates":
                    self.initial['startlocation'] = location_display

            if self.instance.endlocation:
                location_display = self.instance.endlocation_display
                if location_display and location_display != "Invalid coordinates":
                    self.initial['endlocation'] = location_display

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Error initializing location fields: {e}", exc_info=True)

    def _configure_field_requirements(self):
        """Configure field requirements and validation"""
        optional_fields = ["startlocation", "endlocation", "expamt", "transportmodes"]

        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False

        if 'punchintime' in self.fields:
            self.fields['punchintime'].required = True
        if 'people' in self.fields:
            self.fields['people'].required = True

    def clean(self):
        """Enhanced validation with cross-field and business rule validation"""
        cleaned_data = super().clean()

        punchintime = cleaned_data.get('punchintime')
        punchouttime = cleaned_data.get('punchouttime')

        if punchintime and punchouttime:
            if punchouttime <= punchintime:
                raise ValidationError({
                    'punchouttime': 'End time must be after start time'
                })

            time_diff = punchouttime - punchintime
            duration_hours = time_diff.total_seconds() / 3600

            if duration_hours > 24:
                raise ValidationError({
                    'punchouttime': 'Conveyance duration cannot exceed 24 hours'
                })

            cleaned_data['duration'] = int(time_diff.total_seconds() / 60)

        startlocation = cleaned_data.get('startlocation')
        endlocation = cleaned_data.get('endlocation')

        if startlocation and endlocation:
            try:
                from apps.attendance.services.geospatial_service import GeospatialService

                start_lon, start_lat = GeospatialService.extract_coordinates(startlocation)
                end_lon, end_lat = GeospatialService.extract_coordinates(endlocation)

                calculated_distance = GeospatialService.haversine_distance(
                    start_lat, start_lon, end_lat, end_lon
                )

                if calculated_distance > 1000:
                    raise ValidationError({
                        'endlocation': f'Distance {calculated_distance:.1f}km seems unreasonably large'
                    })

                form_distance = cleaned_data.get('distance')
                if not form_distance or abs(form_distance - calculated_distance) > 5:
                    cleaned_data['distance'] = round(calculated_distance, 2)
                    logger.info(f"Auto-calculated distance: {calculated_distance:.2f}km")

            except PARSING_EXCEPTIONS as e:
                logger.warning(f"Failed to validate locations: {e}", exc_info=True)

        expamt = cleaned_data.get('expamt')
        distance = cleaned_data.get('distance')

        if expamt and distance:
            expense_per_km = expamt / distance if distance > 0 else expamt

            if expense_per_km > 100:
                raise ValidationError({
                    'expamt': f'Expense amount seems high: {expense_per_km:.2f} per km'
                })

        transport_modes = cleaned_data.get('transportmodes')
        if transport_modes:
            valid_choices = [choice[0] for choice in atdm.PeopleEventlog.TransportMode.choices]
            invalid_modes = [mode for mode in transport_modes if mode not in valid_choices]

            if invalid_modes:
                raise ValidationError({
                    'transportmodes': f'Invalid transport modes: {invalid_modes}'
                })

        return cleaned_data

    def is_valid(self) -> bool:
        """Adds 'is-invalid' class to invalid fields"""
        result = super().is_valid()
        utils.apply_error_classes(self)
        return result

    def save(self, commit=True):
        instance = super().save(commit=False)

        if instance.punchintime and instance.punchouttime:
            time_diff = instance.punchouttime - instance.punchintime
            duration_minutes = int(time_diff.total_seconds() / 60)
            instance.duration = duration_minutes

        if commit:
            instance.save()
        return instance
