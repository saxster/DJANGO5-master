"""
Attendance Form Module
Handles attendance punch in/out records and event logging.

Part of: apps/attendance/forms/
"""

from django import forms
import django_select2.forms as s2forms
import logging

from apps.attendance import models as atdm
from apps.peoples import models as pm
from apps.core import utils
from apps.core.utils_new.business_logic import initailize_form_fields

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
