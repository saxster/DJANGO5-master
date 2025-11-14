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
# Lazy import to avoid circular dependency: from apps.core_onboarding.models import TypeAssist
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


class PgroupForm(forms.ModelForm):
    required_css_class = "required"
    error_msg = {
        "invalid_code": "Spaces are not allowed in [Code]",
        "invalid_code2": "[Invalid code] Only ('-', '_') special characters are allowed",
        "invalid_code3": "[Invalid code] Code should not endwith '.' ",
        "invalid_name": "[Invalid name] Only these special characters [-, _, @, #] are allowed in name field",
    }
    peoples = forms.MultipleChoiceField(
        required=True,
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        label="Select People",
    )

    class Meta:
        model = pm.Pgroup
        fields = ["groupname", "grouplead", "enable", "identifier", "ctzoffset"]
        labels = {"name": "Name", "enable": "Enable", "grouplead": "Group Lead"}
        widgets = {
            "groupname": forms.TextInput(
                attrs={"placeholder": "Enter People Group Name"}
            ),
            "identifier": forms.TextInput(attrs={"style": "display:none"}),
        }

    def is_valid(self) -> bool:
        """Add class to invalid fields"""
        result = super().is_valid()
        apply_error_classes(self)
        return result

    def clean_peoples(self):
        if val := self.request.POST.get("peoples"):
            pass

    def clean_groupname(self):
        if value := self.cleaned_data.get("groupname"):
            regex = r"^[a-zA-Z0-9\-_@#\[\]\(\|\)\{\} ]*$"
            if not re.match(regex, value):
                raise forms.ValidationError(self.error_msg["invalid_name"])
        return value


class SiteGroupForm(PgroupForm):
    def __init__(self, *args, **kwargs):
        # Lazy import to avoid circular dependency
        from apps.core_onboarding.models import TypeAssist
        
        self.request = kwargs.pop("request")
        S = self.request.session
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
        self.fields["peoples"].required = False
        self.fields["identifier"].initial = TypeAssist.objects.get(
            tacode="SITEGROUP"
        )
        self.fields["grouplead"].queryset = pm.People.objects.filter(
            bu_id__in=S["assignedsites"], enable=True
        )


class PeopleGroupForm(PgroupForm):
    def __init__(self, *args, **kwargs):
        # Lazy import to avoid circular dependency
        from apps.core_onboarding.models import TypeAssist
        
        self.request = kwargs.pop("request")
        S = self.request.session
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
        site = self.request.user.bu.bucode if self.request.user.bu else ""
        self.fields["identifier"].initial = TypeAssist.objects.get(
            tacode="PEOPLEGROUP"
        )

        # filter for dropdown fields
        self.fields["peoples"].choices = pm.People.objects.peoplechoices_for_pgroupform(
            self.request
        )


class PgbelongingForm(forms.ModelForm):
    required_css_class = "required"

    class Meta:
        model = pm.Pgbelonging
        fields = ["isgrouplead"]
        labels = {"isgrouplead": "Group Lead"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        """Add class to invalid fields"""
        result = super().is_valid()
        apply_error_classes(self)
        return result


class CapabilityForm(forms.ModelForm):
    required_css_class = "required"
    error_msg = {
        "invalid_code": "Please don't enter spaces in your code",
        "invalid_code2": "Only these '-', '_' special characters are allowed in code",
        "invalid_code3": "Code's should not be endswith '.' ",
        "invalid_name": "[Invalid name] Only these special characters [-, _, @, #] are allowed in name field",
    }
    parent = forms.ModelChoiceField(
        queryset=pm.Capability.objects.filter(
            Q(parent__capscode="NONE") | Q(capscode="NONE")
        ),
        label="Belongs to",
        widget=s2forms.Select2Widget,
    )

    class Meta:
        model = pm.Capability
        fields = ["capscode", "capsname", "parent", "cfor", "ctzoffset"]
        labels = {
            "capscode": "Code",
            "capsname": "Capability",
            "parent": "Belongs to",
            "cfor": "Capability for",
        }
        widgets = {
            "capscode": forms.TextInput(
                attrs={"placeholder": "Code", "style": "  text-transform: uppercase;"}
            ),
            "capsname": forms.TextInput(attrs={"placeholder": "Enter name"}),
            "cfor": s2forms.Select2Widget,
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)

    def clean_capscode(self):
        import re

        if value := self.cleaned_data.get("capscode"):
            regex = r"^[a-zA-Z0-9\-_]*$"
            if " " in value:
                raise forms.ValidationError(self.error_msg["invalid_code"])
            if not re.match(regex, value):
                raise forms.ValidationError(self.error_msg["invalid_code2"])
            if value.endswith("."):
                raise forms.ValidationError(self.error_msg["invalid_code3"])
            return value.upper()

    def is_valid(self) -> bool:
        """Add class to invalid fields"""
        result = super().is_valid()
        apply_error_classes(self)
        return result

