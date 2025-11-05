"""
Vendor Form Module
Handles vendor management form with GPS location validation.

Part of: apps/work_order_management/forms/
"""

from django import forms
from django.http import QueryDict
from django.contrib.gis.geos import GEOSGeometry
import django_select2.forms as s2forms
import re
import logging

from apps.core_onboarding import models as om_core
from apps.work_order_management.models import Vendor
from apps.core.utils_new.business_logic import initailize_form_fields

logger = logging.getLogger(__name__)


class VendorForm(forms.ModelForm):
    required_css_class = "required"

    class Meta:
        model = Vendor
        fields = [
            "code",
            "name",
            "address",
            "mobno",
            "type",
            "show_to_all_sites",
            "email",
            "ctzoffset",
            "enable",
            "description",
        ]
        labels = {
            "code": "Code",
            "name": "Name",
            "address": "Address",
            "mobno": "Mob no",
            "email": "Email",
            "description": "Description",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Enter Name..."}),
            "address": forms.Textarea(attrs={"rows": 4}),
            "code": forms.TextInput(
                attrs={
                    "style": "text-transform: uppercase;",
                    "placeholder": "Enter characters without spaces...",
                }
            ),
            "type": s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Enter detailed description of vendor...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["address"].required = True
        self.fields["type"].required = False
        self.fields["type"].queryset = om_core.TypeAssist.objects.filter(
            tatype__tacode="VENDOR_TYPE", enable=True, client_id=S["client_id"]
        )
        initailize_form_fields(self)

    def clean(self):
        super().clean()
        self.cleaned_data["gpslocation"] = self.data.get("gpslocation")
        if self.cleaned_data.get("gpslocation"):
            data = QueryDict(self.request.POST["formData"])
            self.cleaned_data["gpslocation"] = self.clean_gpslocation(
                data.get("gpslocation", "NONE")
            )
        return self.cleaned_data

    def clean_gpslocation(self, val):
        if gps := val:
            if gps == "NONE":
                return None
            regex = r"^([-+]?)([\d]{1,2})(((\.)(\d+)(,)))(\s*)(([-+]?)([\d]{1,3})((\.)(\d+))?)$"
            gps = gps.replace("(", "").replace(")", "")
            if not re.match(regex, gps):
                raise forms.ValidationError(self.error_msg["invalid_latlng"])
            gps.replace(" ", "")
            lat, lng = gps.split(",")
            gps = GEOSGeometry(f"SRID=4326;POINT({lng} {lat})")
        return gps

    def clean_code(self):
        return val.upper() if (val := self.cleaned_data.get("code")) else val
