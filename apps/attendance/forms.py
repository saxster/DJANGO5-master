from django import forms
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ValidationError
from django_select2 import forms as s2forms
from apps.core import utils
import apps.attendance.models as atdm
import apps.peoples.models as pm
from apps.core.utils_new.business_logic import initailize_form_fields
import logging

logger = logging.getLogger(__name__)


class AttendanceForm(forms.ModelForm):
    required_css_class = "required"

    class Meta:
        model = atdm.PeopleEventlog
        fields = [
            "people",
            "datefor",
            "ctzoffset",
            "punchintime",
            "punchouttime",
            "peventtype",
            "verifiedby",
            "remarks",
            "shift",
            "facerecognitionin",
            "facerecognitionout",
        ]
        labels = {
            "people": "People",
            "punchintime": "In Time",
            "punchouttime": "Out Time",
            "datefor": "For Date",
            "peventtype": "Attendance Type",
            "verifiedby": "Verified By",
            "facerecognition": "Enable FaceRecognition",
            "remarks": "Remark",
        }
        widgets = {
            "people": s2forms.ModelSelect2Widget(
                model=pm.People,
                search_fields=["peoplename__icontains", "peoplecode__icontains"],
            ),
            "verifiedby": s2forms.ModelSelect2Widget(
                model=pm.People,
                search_fields=["peoplename__icontains", "peoplecode__icontains"],
            ),
            "shift": s2forms.Select2Widget,
            "peventtype": s2forms.Select2Widget,
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
        self.fields["datefor"].required = True
        self.fields["punchintime"].required = True
        self.fields["punchouttime"].required = True
        self.fields["verifiedby"].required = True
        self.fields["people"].required = True
        self.fields["peventtype"].required = True
        self.fields["shift"].initial = 1

    def is_valid(self) -> bool:
        """Adds 'is-invalid' class to invalid fields"""
        result = super().is_valid()
        utils.apply_error_classes(self)
        return result


def clean_geometry(val):
    """
    Enhanced geometry validation using centralized geospatial service
    """
    if not val or val.strip() == "":
        return None

    try:
        from apps.attendance.services.geospatial_service import GeospatialService

        # Handle various input formats
        val = val.strip()

        # If it's coordinate pair format "Lat: X, Lng: Y"
        if val.startswith("Lat:") and "Lng:" in val:
            import re
            match = re.search(r"Lat:\s*([-\d.]+),\s*Lng:\s*([-\d.]+)", val)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                return GeospatialService.create_point(lat, lon)

        # Try to parse as WKT or other geometry format
        geom = GEOSGeometry(val, srid=4326)

        # Validate coordinates if it's a Point
        if geom.geom_type == 'Point':
            lon, lat = GeospatialService.extract_coordinates(geom)
            # This will validate coordinate bounds
            GeospatialService.validate_coordinates(lat, lon)

        return geom

    except (ValueError, TypeError, ValidationError) as e:
        raise forms.ValidationError(
            f"Invalid geometry format. Expected coordinates or WKT geometry. Error: {str(e)}"
        ) from e
    except Exception as e:
        raise forms.ValidationError(
            f"Failed to process geometry data: {str(e)}"
        ) from e


class ConveyanceForm(forms.ModelForm):
    required_css_class = "required"
    transportmodes = forms.MultipleChoiceField(
        choices=atdm.PeopleEventlog.TransportMode.choices,
        required=False,
        widget=s2forms.Select2MultipleWidget(attrs={'class': 'form-control',"data-theme": "bootstrap5"}),
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
                attrs={'class': 'form-control',"data-theme": "bootstrap5"}
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

        # Handle transport modes initialization for existing instances
        if self.instance and self.instance.pk:
            self._initialize_transport_modes()
            self._initialize_location_fields()

        # Set field requirements
        self._configure_field_requirements()

    def _initialize_transport_modes(self):
        """Initialize transport modes field with proper data handling"""
        if not self.instance.transportmodes:
            return

        import json
        transport_data = self.instance.transportmodes

        try:
            # Handle various transport modes data formats
            if isinstance(transport_data, list) and transport_data:
                first_item = transport_data[0]

                # Check for double-encoded JSON string in list
                if isinstance(first_item, str) and first_item.startswith('['):
                    try:
                        # Parse the JSON string to get the actual list
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
                    # Already properly formatted list
                    self.fields['transportmodes'].initial = transport_data
            else:
                logger.warning(f"Unexpected transport modes format: {type(transport_data)}")
                self.fields['transportmodes'].initial = []

        except Exception as e:
            logger.error(f"Error initializing transport modes for conveyance {self.instance.id}: {e}")
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

        except Exception as e:
            logger.warning(f"Error initializing location fields: {e}")

    def _configure_field_requirements(self):
        """Configure field requirements and validation"""
        # Fields that should not be required for conveyance forms
        optional_fields = ["startlocation", "endlocation", "expamt", "transportmodes"]

        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False

        # Set minimum requirements for core fields
        if 'punchintime' in self.fields:
            self.fields['punchintime'].required = True
        if 'people' in self.fields:
            self.fields['people'].required = True

    def clean(self):
        """Enhanced validation with cross-field and business rule validation"""
        cleaned_data = super().clean()

        # Validate time fields
        punchintime = cleaned_data.get('punchintime')
        punchouttime = cleaned_data.get('punchouttime')

        if punchintime and punchouttime:
            # Validate time sequence
            if punchouttime <= punchintime:
                raise ValidationError({
                    'punchouttime': 'End time must be after start time'
                })

            # Validate reasonable duration (not more than 24 hours)
            time_diff = punchouttime - punchintime
            duration_hours = time_diff.total_seconds() / 3600

            if duration_hours > 24:
                raise ValidationError({
                    'punchouttime': 'Conveyance duration cannot exceed 24 hours'
                })

            # Auto-calculate duration in minutes
            cleaned_data['duration'] = int(time_diff.total_seconds() / 60)

        # Validate location fields if provided
        startlocation = cleaned_data.get('startlocation')
        endlocation = cleaned_data.get('endlocation')

        if startlocation and endlocation:
            try:
                from apps.attendance.services.geospatial_service import GeospatialService

                # Extract coordinates
                start_lon, start_lat = GeospatialService.extract_coordinates(startlocation)
                end_lon, end_lat = GeospatialService.extract_coordinates(endlocation)

                # Calculate distance
                calculated_distance = GeospatialService.haversine_distance(
                    start_lat, start_lon, end_lat, end_lon
                )

                # Validate reasonable distance (less than 1000km for single trip)
                if calculated_distance > 1000:
                    raise ValidationError({
                        'endlocation': f'Distance {calculated_distance:.1f}km seems unreasonably large for a single trip'
                    })

                # Auto-update distance if not provided or significantly different
                form_distance = cleaned_data.get('distance')
                if not form_distance or abs(form_distance - calculated_distance) > 5:
                    cleaned_data['distance'] = round(calculated_distance, 2)
                    logger.info(f"Auto-calculated distance: {calculated_distance:.2f}km")

            except Exception as e:
                logger.warning(f"Failed to validate locations: {e}")

        # Validate expense amount
        expamt = cleaned_data.get('expamt')
        distance = cleaned_data.get('distance')

        if expamt and distance:
            # Basic reasonableness check: expense per km should not exceed 100 (currency units)
            expense_per_km = expamt / distance if distance > 0 else expamt

            if expense_per_km > 100:
                raise ValidationError({
                    'expamt': f'Expense amount seems high: {expense_per_km:.2f} per km'
                })

        # Validate transport modes
        transport_modes = cleaned_data.get('transportmodes')
        if transport_modes:
            # Ensure all modes are valid choices
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

    def clean_startlocation(self):
        if val := self.cleaned_data.get("startlocation"):
            val = clean_geometry(val)
        return val

    def clean_endlocation(self):
        if val := self.cleaned_data.get("endlocation"):
            val = clean_geometry(val)
        return val

    def clean_journeypath(self):
        if val := self.cleaned_data.get("journeypath"):
            val = clean_geometry(val)
        return val
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Calculate duration properly from start and end times
        if instance.punchintime and instance.punchouttime:
            time_diff = instance.punchouttime - instance.punchintime
            duration_minutes = int(time_diff.total_seconds() / 60)
            instance.duration = duration_minutes
        
        if commit:
            instance.save()
        return instance


class TrackingForm(forms.ModelForm):
    gpslocation = forms.CharField(max_length=200, required=True)

    class Meta:
        model = atdm.Tracking
        fields = ["deviceid", "gpslocation", "receiveddate", "people", "transportmode"]

    def clean_gpslocation(self):
        if val := self.cleaned_data.get("gpslocation"):
            val = clean_geometry(val)
        return val
