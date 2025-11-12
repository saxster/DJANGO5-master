"""
Approval Form Module
Handles approval and verification configuration forms.

Part of: apps/work_order_management/forms/
"""

from django import forms
from django.db.models import Q
import django_select2.forms as s2forms
import logging

from apps.core_onboarding import models as om_core
from apps.work_order_management.models import Approver, Vendor, Wom
from apps.peoples.models import Pgbelonging, People
from apps.core.utils_new.business_logic import initailize_form_fields

logger = logging.getLogger(__name__)


class ApproverForm(forms.ModelForm):
    required_css_class = "required"
    approverfor = forms.MultipleChoiceField(
        required=True, label="Approver/Verifier For "
    )
    sites = forms.MultipleChoiceField(required=False, label="Sites")

    class Meta:
        model = Approver
        fields = [
            "approverfor",
            "forallsites",
            "sites",
            "people",
            "ctzoffset",
            "identifier",
        ]
        labels = {
            "identifier": "Name",
            "forallsites": "Applicable to all sites",
            "people": "Approver/Verifier",
            "approverfor": "Approver/Verifier For",
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        S = self.request.session
        super().__init__(*args, **kwargs)
        logger.debug("Identifier choices: %s", self.fields["identifier"].choices)

        self.fields["identifier"] = forms.ChoiceField(
            choices=Approver.Identifier.choices,
            required=True,
            label="Name",
            widget=s2forms.Select2Widget(
                attrs={
                    "class": "form-select form-select-solid",
                    "data-placeholder": "Select an option",
                    "data-theme": "bootstrap5",
                }
            ),
        )

        self.fields["identifier"].widget.attrs.update(
            {
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
            }
        )

        self.fields["approverfor"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["people"].widget = s2forms.Select2Widget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["sites"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )

        initailize_form_fields(self)

        self.fields["approverfor"].choices = om_core.TypeAssist.objects.filter(
            Q(client_id=S["client_id"]) | Q(client_id=2), tatype__tacode="APPROVERFOR"
        ).values_list("tacode", "taname")
        self.fields["sites"].choices = Pgbelonging.objects.get_assigned_sites_to_people(
            self.request.user.id, makechoice=True
        )
        self.fields["people"].queryset = People.objects.filter(
            client_id=S["client_id"], isverified=True, enable=True
        )

    def clean(self):
        cd = super().clean()
        if cd["forallsites"] == True:
            self.cleaned_data["sites"] = None
        if cd["sites"] not in (None, ""):
            self.cleaned_data["forallsites"] = False
        return self.cleaned_data
