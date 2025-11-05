"""
Work Permit and SLA Template Form Module
Handles work permit and SLA template management forms.

Part of: apps/work_order_management/forms/
"""

from django import forms
from django.db.models import Q
import django_select2.forms as s2forms
import logging

from apps.activity.models.question_model import QuestionSet
from apps.work_order_management.models import Approver, Vendor, Wom
from apps.core.utils_new.business_logic import initailize_form_fields

logger = logging.getLogger(__name__)


class WorkPermitForm(forms.ModelForm):
    required_css_class = "required"
    seqno = forms.IntegerField(
        label="Seq. Number",
        required=False,
        widget=forms.TextInput(attrs={"readonly": True}),
    )
    approvers = forms.MultipleChoiceField(
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        label="Approvers",
    )
    verifiers = forms.MultipleChoiceField(
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        label="Verifiers",
    )

    class Meta:
        model = Wom
        fields = [
            "qset",
            "seqno",
            "ctzoffset",
            "workpermit",
            "performedby",
            "parent",
            "approvers",
            "vendor",
            "verifiers",
            "identifier",
        ]
        labels = {
            "qset": "Permit to work",
            "seqno": "Seq No",
        }
        widgets = {"wptype": s2forms.Select2Widget}

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        S = self.request.session
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
        self.fields["approvers"].choices = Approver.objects.get_approver_options_wp(
            self.request
        ).values_list("people__peoplecode", "people__peoplename")
        self.fields["verifiers"].choices = Approver.objects.get_verifier_options_wp(
            self.request
        ).values_list("people__peoplecode", "people__peoplename")
        self.fields["qset"].queryset = (
            QuestionSet.objects.filter(
                type="WORKPERMIT", client_id=S["client_id"], enable=True, parent_id=1
            )
            .filter(
                Q(bu_id=S["bu_id"])
                | Q(buincludes__contains=[str(S["bu_id"])])
                | Q(show_to_all_sites=True)
            )
            .order_by("qsetname")
        )
        self.fields["vendor"].queryset = Vendor.objects.filter(
            Q(bu_id=S["bu_id"])
            | Q(Q(show_to_all_sites=True) & Q(client_id=S["client_id"]))
        )


class SlaForm(forms.ModelForm):
    MONTH_CHOICES = [
        ("-", "---------"),
        ("1", "January"),
        ("2", "February"),
        ("3", "March"),
        ("4", "April"),
        ("5", "May"),
        ("6", "June"),
        ("7", "July"),
        ("8", "August"),
        ("9", "September"),
        ("10", "October"),
        ("11", "November"),
        ("12", "December"),
    ]

    required_css_class = "required"
    seqno = forms.IntegerField(
        label="Seq. Number",
        required=False,
        widget=forms.TextInput(attrs={"readonly": True}),
    )
    approvers = forms.MultipleChoiceField(
        widget=s2forms.Select2MultipleWidget, label="Approvers"
    )
    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        label="Select Month",
        required=True,
        widget=forms.Select(attrs={"readonly": True}),
    )

    class Meta:
        model = Wom
        fields = [
            "qset",
            "seqno",
            "ctzoffset",
            "workpermit",
            "performedby",
            "parent",
            "approvers",
            "vendor",
            "identifier",
        ]
        labels = {"qset": "Template", "seqno": "Seq No", "month": "Select the Month"}
        widgets = {"wptype": s2forms.Select2Widget}

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        S = self.request.session
        super().__init__(*args, **kwargs)
        month_value = self.request.POST.get("month_name")
        if month_value:
            self.fields["month"].initial = month_value
        initailize_form_fields(self)
        self.fields["approvers"].choices = Approver.objects.get_approver_options_sla(
            self.request
        ).values_list("people__peoplecode", "people__peoplename")
        self.fields["qset"].queryset = QuestionSet.objects.filter(
            type="SLA_TEMPLATE", client_id=S["client_id"], enable=True, parent_id=1
        ).filter(
            Q(bu_id=S["bu_id"])
            | Q(buincludes__contains=[str(S["bu_id"])])
            | Q(show_to_all_sites=True)
        )
        self.fields["vendor"].queryset = Vendor.objects.filter(
            Q(enable=True)
            & (
                Q(bu_id=S["bu_id"])
                | Q(Q(show_to_all_sites=True) & Q(client_id=S["client_id"]))
            )
        )
