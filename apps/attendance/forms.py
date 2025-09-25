from django import forms
from django.contrib.gis.geos import GEOSGeometry
from django_select2 import forms as s2forms
from apps.core import utils
import apps.attendance.models as atdm
import apps.peoples.models as pm
from apps.core.utils_new.business_logic import initailize_form_fields


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
    try:
        val = GEOSGeometry(val, srid=4326)
    except ValueError as e:
        raise forms.ValidationError("lat lng string input unrecognized!") from e
    else:
        return val


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
            if self.instance.transportmodes:
                # Handle double-encoded transport modes data
                import json
                transport_data = self.instance.transportmodes
                
                # Check if it's double-encoded (e.g., ['["TRAM"]'])
                if transport_data and len(transport_data) > 0:
                    first_item = transport_data[0]
                    if isinstance(first_item, str) and first_item.startswith('['):
                        try:
                            # Parse the JSON string to get the actual list
                            actual_modes = json.loads(first_item)
                            self.fields['transportmodes'].initial = actual_modes
                        except:
                            self.fields['transportmodes'].initial = transport_data
                    else:
                        # Already properly formatted
                        self.fields['transportmodes'].initial = transport_data
            
            # Handle location fields - use the display properties from the model
            if self.instance.startlocation:
                location_display = self.instance.startlocation_display
                if location_display:
                    self.initial['startlocation'] = location_display
            
            if self.instance.endlocation:
                location_display = self.instance.endlocation_display
                if location_display:
                    self.initial['endlocation'] = location_display
        
        for visible in self.visible_fields():
            if visible.name in [
                "startlocation",
                "endlocation",
                "expamt",
                "transportmodes",
            ]:
                visible.required = False

    def clean(self):
        super(ConveyanceForm, self).clean()

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
