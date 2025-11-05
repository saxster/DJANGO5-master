"""Profile and user information forms."""

import re
import phonenumbers as pn
from phonenumbers.phonenumberutil import NumberParseException

from django import forms
from django_select2 import forms as s2forms

import apps.peoples.models as pm
from apps.core.validators import (
    PEOPLECODE_VALIDATOR,
    LOGINID_VALIDATOR,
    MOBILE_NUMBER_VALIDATOR,
)
from apps.core.utils_new.business_logic import (
    apply_error_classes,
    initailize_form_fields,
)


class PeopleForm(forms.ModelForm):
    """Main form for creating/editing people records."""

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
        fields = [
            "peoplename",
            "peoplecode",
            "mobno",
            "email",
            "loginid",
            "enable",
            "deviceid",
            "preferred_language",
            "isadmin",
            "ctzoffset",
        ]
        labels = {
            "peoplename": "Name",
            "loginid": "Login Id",
            "email": "Email",
            "enable": "Enable",
            "preferred_language": "Preferred Language",
            "deviceid": "Device Id",
            "isadmin": "Admin",
        }
        widgets = {
            'preferred_language': s2forms.Select2Widget(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select your preferred language'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.email:
                self.initial['email'] = self.instance.email
            if self.instance.mobno:
                self.initial['mobno'] = self.instance.mobno
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        """Add class to invalid fields"""
        result = super().is_valid()
        apply_error_classes(self)
        return result

    def clean(self):
        super(PeopleForm, self).clean()

    def clean_peoplecode(self):
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
        if mobno := self.cleaned_data.get("mobno"):
            try:
                no = pn.parse(f"+{mobno}") if "+" not in mobno else pn.parse(mobno)
                if not pn.is_valid_number(no):
                    raise forms.ValidationError(self.error_msg["invalid_mobno2"])
            except NumberParseException as e:
                raise forms.ValidationError(self.error_msg["invalid_mobno2"]) from e
            return mobno
