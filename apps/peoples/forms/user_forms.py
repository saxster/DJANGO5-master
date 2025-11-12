from django import forms
from django.conf import settings
from django.core.validators import RegexValidator
from django.db.models import Q
from django.utils.html import format_html
from django.urls import reverse
import logging
import zlib
import binascii

import apps.peoples.models as pm  # people-models
from apps.activity.models.location_model import Location
from apps.activity.models.question_model import QuestionSet
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from django_select2 import forms as s2forms
from apps.core.utils_new.business_logic import (
    apply_error_classes,
    initailize_form_fields,
)
import re
from apps.peoples.utils import create_caps_choices_for_peopleform

from apps.core.utils_new.code_validators import (
    PEOPLECODE_VALIDATOR,
    LOGINID_VALIDATOR,
    MOBILE_NUMBER_VALIDATOR,
    NAME_VALIDATOR,
    validate_peoplecode,
    validate_loginid,
    validate_mobile_number,
    validate_name,
)

# Security form utilities
from apps.core.validation import SecureFormMixin, SecureCharField


class PeopleForm(forms.ModelForm):
    required_css_class = "required"
    error_msg = {
        "invalid_dates": "Date of birth & Date of join cannot be equal!",
        "dob_should_less_doj": "Date of birth cannot be greater than Date of join",
        "dob_should_less_dor": "Date of birth cannot be greater than Date of release",
        "invalid_id": "Please choose a different loginid",
        "invalid_mobno": "Please enter mob no with country code first +XX",
        "invalid_mobno2": "Please enter a valid mobile number",
        "invalid_id2": "Enter loginid without any spaces",
        "invalid_code": "Spaces are not allowed in [Code]",
        "invalid_code2": "[Invalid text] Only ('-', '_') special characters are allowed",
        "invalid_code3": "[Invalid text] Code should not endwith '.' ",
        "invalid_name": "[Invalid text] Only these special characters [-, _, @, #, ., &] are allowed in name field",
    }

    # defines field rendering order
    field_order = [
        "peoplecode",
        "peoplename",
        "loginid",
        "email",
        "mobno",
        "gender",
        "dateofbirth",
        "enable",
        "preferred_language",
        "peopletype",
        "dateofjoin",
        "department",
        "designation",
        "dateofreport",
        "reportto",
        "deviceid",
    ]

    peoplecode = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "style": "text-transform:uppercase;",
                "placeholder": "Enter text not including any spaces",
            }
        ),
        validators=[PEOPLECODE_VALIDATOR],
        label="Code",
    )
    email = forms.EmailField(
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Enter email address"}),
    )
    loginid = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={"placeholder": "Enter text not including any spaces"}
        ),
        validators=[LOGINID_VALIDATOR],
    )

    class Meta:
        model = pm.People
        # Note: After Sept 2025 refactoring, some fields moved to related models:
        # - PeopleProfile: peopleimg, gender, dateofbirth, dateofjoin, dateofreport
        # - PeopleOrganizational: location, department, designation, peopletype, worktype, bu, reportto
        # These fields are accessible via person.profile.* and person.organizational.* relations
        fields = [
            "peoplename",
            "peoplecode",
            # "peopleimg",  # Moved to PeopleProfile
            "mobno",
            "email",
            "loginid",
            # "dateofbirth",  # Moved to PeopleProfile
            "enable",
            "deviceid",
            # "gender",  # Moved to PeopleProfile
            "preferred_language",
            # "peopletype",  # Moved to PeopleOrganizational
            # "dateofjoin",  # Moved to PeopleProfile
            # "department",  # Moved to PeopleOrganizational
            # "dateofreport",  # Moved to PeopleProfile
            # "worktype",  # Moved to PeopleOrganizational
            # "designation",  # Moved to PeopleOrganizational
            # "reportto",  # Moved to PeopleOrganizational
            # "bu",  # Moved to PeopleOrganizational
            "isadmin",
            "ctzoffset",
            # "location",  # Moved to PeopleOrganizational
        ]
        labels = {
            "peoplename": "Name",
            "loginid": "Login Id",
            "email": "Email",
            "peopletype": "Employee Type",
            "reportto": "Report to",
            "designation": "Designation",
            "gender": "Gender",
            "dateofbirth": "Date of Birth",
            "enable": "Enable",
            "preferred_language": "Preferred Language",
            "department": "Department",
            "dateofjoin": "Date of Joining",
            "dateofreport": "Date of Release",
            "deviceid": "Device Id",
            "bu": "Site",
            "isadmin": "Admin",
            "worktype": "Work Type",
            "location": "Posting",
        }

        widgets = {
            # 'mobno'       : forms.TextInput(attrs={'placeholder': 'Eg:- +91XXXXXXXXXX, +44XXXXXXXXX'}),
            # 'peoplename'  : forms.TextInput(attrs={'placeholder': 'Enter people name'}),
            # 'loginid'     : forms.TextInput(attrs={'placeholder': 'Enter text not including any spaces'}),
            # 'dateofbirth' : forms.DateInput,
            # 'dateofjoin'  : forms.DateInput,
            # 'dateofreport': forms.DateInput,
            # 'peopletype'  : s2forms.Select2Widget(attrs={'class': 'form-control'}),
            # 'gender'      : s2forms.Select2Widget(attrs={'class': 'form-control'}),
            # 'department'  : s2forms.Select2Widget(attrs={'class': 'form-control'}),
            # 'designation' : s2forms.Select2Widget(attrs={'class': 'form-control'}),
            # 'reportto'    : s2forms.Select2Widget(attrs={'class': 'form-control'}),
            # 'bu'          : s2forms.Select2Widget(attrs={'class': 'form-control'}),
            'preferred_language': s2forms.Select2Widget(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select your preferred language'
            }),
        }

    def __init__(self, *args, **kwargs):
        """Initializes form add atttibutes and classes here."""
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)

        # NOTE: Date fields moved to PeopleProfile model after Sept 2025 refactoring
        if self.instance and self.instance.pk:
            if self.instance.email:
                self.initial['email'] = self.instance.email

            if self.instance.mobno:
                self.initial['mobno'] = self.instance.mobno

        # NOTE: Organizational fields moved to PeopleOrganizational model after Sept 2025 refactoring
        # If you need to edit these fields, use inline formsets or separate forms for PeopleProfile/PeopleOrganizational
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        """Add class to invalid fields"""
        result = super().is_valid()
        apply_error_classes(self)
        return result

    def clean(self):
        super(PeopleForm, self).clean()
        # NOTE: Date validation moved to PeopleProfile model after Sept 2025 refactoring
        # Date fields (dateofbirth, dateofjoin, dateofreport) are now in PeopleProfile
        # Validation is performed in PeopleProfile.clean() method

    # For field level validation define functions like clean_<func name>.

    def clean_peoplecode(self):
        import re

        if value := self.cleaned_data.get("peoplecode"):
            regex = r"^[a-zA-Z0-9\-_#]*$"
            if " " in value:
                raise forms.ValidationError(self.error_msg["invalid_code"])
            if not re.match(regex, value):
                raise forms.ValidationError(self.error_msg["invalid_code2"])
            if value.endswith("."):
                raise forms.ValidationError(self.error_msg["invalid_code3"])
            return value.upper()

    def clean_loginid(self):
        if value := self.cleaned_data.get("loginid"):
            if " " in value:
                raise forms.ValidationError(self.error_msg["invalid_id2"])
            regex = r"^[a-zA-Z0-9\-_@#]*$"
            if not re.match(regex, value):
                raise forms.ValidationError(self.error_msg["invalid_name"])
            return value

    def clean_peoplename(self):
        if value := self.cleaned_data.get("peoplename"):
            regex = r"^[a-zA-Z0-9\-_@#.\(\|\)& ]*$"
            if not re.match(regex, value):
                raise forms.ValidationError(self.error_msg["invalid_name"])
        return value

    def clean_mobno(self):
        import phonenumbers as pn
        from phonenumbers.phonenumberutil import NumberParseException

        if mobno := self.cleaned_data.get("mobno"):
            try:
                no = pn.parse(f"+{mobno}") if "+" not in mobno else pn.parse(mobno)
                if not pn.is_valid_number(no):
                    raise forms.ValidationError(self.error_msg["invalid_mobno2"])
            except NumberParseException as e:
                raise forms.ValidationError(self.error_msg["invalid_mobno2"]) from e
            return mobno

