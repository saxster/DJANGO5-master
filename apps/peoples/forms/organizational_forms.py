"""Organizational forms for groups, capabilities, and group allocation."""

import re
from django import forms
from django.db.models import Q
from django_select2 import forms as s2forms

import apps.peoples.models as pm
from apps.core_onboarding.models import TypeAssist
from apps.core.utils_new.business_logic import (
    apply_error_classes,
    initailize_form_fields,
)


class PgroupForm(forms.ModelForm):
    """Base form for people groups."""

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

    def clean_groupname(self):
        if value := self.cleaned_data.get("groupname"):
            regex = r"^[a-zA-Z0-9\-_@#\[\]\(\|\)\{\} ]*$"
            if not re.match(regex, value):
                raise forms.ValidationError(self.error_msg["invalid_name"])
        return value


class SiteGroupForm(PgroupForm):
    """Form for creating/editing site groups."""

    def __init__(self, *args, **kwargs):
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
    """Form for creating/editing people groups."""

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        S = self.request.session
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
        site = self.request.user.bu.bucode if self.request.user.bu else ""
        self.fields["identifier"].initial = TypeAssist.objects.get(
            tacode="PEOPLEGROUP"
        )
        self.fields["peoples"].choices = pm.People.objects.peoplechoices_for_pgroupform(
            self.request
        )


class PgbelongingForm(forms.ModelForm):
    """Form for managing group membership."""

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
    """Form for creating/editing capabilities."""

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
                attrs={"placeholder": "Code", "style": "text-transform: uppercase;"}
            ),
            "capsname": forms.TextInput(attrs={"placeholder": "Enter name"}),
            "cfor": s2forms.Select2Widget,
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)

    def clean_capscode(self):
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


class PeopleGrpAllocation(forms.Form):
    """Form for allocating people to groups."""

    people = forms.ChoiceField(required=True, widget=s2forms.Select2Widget)
    is_grouplead = forms.BooleanField(required=False, initial=False)

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
        site = request.user.bu.bucode if request.user.bu else ""
        self.fields["people"].choices = (
            pm.People.objects.select_related("bu")
            .filter(bu__bucode=site)
            .values_list("id", "peoplename")
        )

    def is_valid(self) -> bool:
        """Add class to invalid fields"""
        result = super().is_valid()
        apply_error_classes(self)
        return result


class NoSiteForm(forms.Form):
    """Form for users with no default site assigned."""

    site = forms.ChoiceField(
        required=False,
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        label="Default Site",
    )

    def __init__(self, *args, **kwargs):
        session = kwargs.pop("session")
        super().__init__(*args, **kwargs)
        self.fields[
            "site"
        ].choices = pm.Pgbelonging.objects.get_assigned_sites_to_people(
            session.get("_auth_user_id"), True
        )
        initailize_form_fields(self)
