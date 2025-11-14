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
# Removed unused import: from apps.core_onboarding.models import TypeAssist
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


class PeopleExtrasForm(forms.Form):
    labels = {
        "mob": "Mobile Capability",
        "port": "Portlet Capability",
        "report": "Report Capability",
        "web": "Web Capability",
        "noc": "NOC Capability",
    }

    USERFOR_CHOICES = [
        ("Mobile", "Mobile"),
        ("Web", "Web"),
        ("Both", "Both"),
    ]

    andriodversion = forms.CharField(
        max_length=2, required=False, label="Andriod Version"
    )
    appversion = forms.CharField(max_length=8, required=False, label="App Version")
    mobilecapability = forms.MultipleChoiceField(required=False, label=labels["mob"])
    portletcapability = forms.MultipleChoiceField(required=False, label=labels["port"])
    reportcapability = forms.MultipleChoiceField(required=False, label=labels["report"])
    webcapability = forms.MultipleChoiceField(required=False, label=labels["web"])
    noccapability = forms.MultipleChoiceField(
        required=False, label=labels["noc"], widget=s2forms.Select2MultipleWidget
    )
    loacationtracking = forms.BooleanField(initial=False, required=False)
    capturemlog = forms.BooleanField(initial=False, required=False)
    showalltemplates = forms.BooleanField(
        initial=False, required=False, label="Show all Templates "
    )
    debug = forms.BooleanField(initial=False, required=False)
    showtemplatebasedonfilter = forms.BooleanField(
        initial=False, required=False, label="Display site wise templates"
    )
    blacklist = forms.BooleanField(initial=False, required=False)
    alertmails = forms.BooleanField(initial=False, label="Alert Mails", required=False)
    isemergencycontact = forms.BooleanField(
        initial=False, label="Emergency Contact", required=False
    )
    assignsitegroup = forms.MultipleChoiceField(required=False, label="Site Group")
    tempincludes = forms.MultipleChoiceField(required=False, label="Template")
    mlogsendsto = forms.CharField(max_length=25, required=False)
    currentaddress = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2, "cols": 15})
    )
    permanentaddress = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2, "cols": 15})
    )
    userfor = forms.ChoiceField(
        required=True, choices=USERFOR_CHOICES, label="User For",
        initial="Both"  # Set a default value
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["mobilecapability"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["tempincludes"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["assignsitegroup"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["portletcapability"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["reportcapability"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["noccapability"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["assignsitegroup"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["webcapability"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )

        # self.fields['userfor'].widget = s2forms.Select2Widget(attrs={'class': 'form-select form-select-solid', 'data-placeholder': 'Select an option', 'data-theme': 'bootstrap5'})
        self.fields[
            "assignsitegroup"
        ].choices = pm.Pgroup.objects.get_assignedsitegroup_forclient(
            S["client_id"], self.request
        )
        self.fields["tempincludes"].choices = QuestionSet.objects.filter(
            type="SITEREPORT", bu_id__in=S["assignedsites"]
        ).values_list("id", "qsetname")
        web, mob, portlet, report, noc = create_caps_choices_for_peopleform(
            self.request.user.client
        )
        if not (S["is_superadmin"]):
            self.fields["webcapability"].choices = S["client_webcaps"] or web
            self.fields["mobilecapability"].choices = S["client_mobcaps"] or mob
            self.fields["portletcapability"].choices = (
                S["client_portletcaps"] or portlet
            )
            self.fields["reportcapability"].choices = S["client_reportcaps"] or report
            self.fields["noccapability"].choices = S["client_noccaps"] or noc
        else:
            # if superadmin is logged in
            from .utils import get_caps_choices

            self.fields["webcapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.WEB
            )
            self.fields["mobilecapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.MOB
            )
            self.fields["portletcapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.PORTLET
            )
            self.fields["reportcapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.REPORT
            )
            self.fields["noccapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.NOC
            )
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        """Add class to invalid fields"""
        result = super().is_valid()
        apply_error_classes(self)
        return result

    def clean(self):
        cd = super().clean()
        if cd.get("userfor") and cd["userfor"] != "":
            client = Bt.objects.filter(id=self.request.session["client_id"]).first()
            preferences = client.bupreferences
            if preferences["billingtype"] == "USERBASED":
                current_ppl_count = pm.People.objects.filter(
                    client=client, people_extras__userfor=cd["userfor"]
                ).count()
                mapping = {
                    "Mobile": "no_of_users_allowed_mob",
                    "Both": "no_of_users_allowed_both",
                    "Web": "no_of_users_allowed_web",
                }
                parameter = mapping.get(cd["userfor"])
                allowed_count = preferences[parameter]
                if allowed_count and current_ppl_count + 1 > int(allowed_count):
                    raise forms.ValidationError(
                        f'{cd["userfor"]} users limit exceeded {allowed_count} and curent people count is {current_ppl_count}'
                    )


class PeopleGrpAllocation(forms.Form):
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