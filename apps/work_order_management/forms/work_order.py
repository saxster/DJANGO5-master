"""
Work Order Form Module
Handles work order creation and management with multi-field initialization.

Part of: apps/work_order_management/forms/
"""

from django import forms
from django.db.models import Q
import django_select2.forms as s2forms
from django.utils import timezone
import logging

from apps.core_onboarding import models as om_core
from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import QuestionSet
from apps.activity.models.location_model import Location
from apps.work_order_management.models import Vendor, Wom
from apps.core.utils_new.business_logic import initailize_form_fields

logger = logging.getLogger(__name__)


class WorkOrderForm(forms.ModelForm):
    required_css_class = "required"

    categories = forms.MultipleChoiceField(
        label="Queue",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )

    class Meta:
        model = Wom
        fields = [
            "description",
            "plandatetime",
            "expirydatetime",
            "asset",
            "location",
            "qset",
            "ismailsent",
            "priority",
            "ticketcategory",
            "categories",
            "vendor",
            "ctzoffset",
            "workstatus",
        ]

        widgets = {
            "categories": s2forms.Select2MultipleWidget(
                attrs={"data-theme": "bootstrap5"}
            ),
            "vendor": s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Enter detailed description of work to be done...",
                }
            ),
            "workstatus": forms.TextInput(attrs={"readonly": True}),
            "ismailsent": forms.HiddenInput(),
        }
        labels = {
            "description": "Description",
            "qset": "Question Set",
            "workstatus": "Status",
            "asset": "Asset/Checkpoint",
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["qset"].required = True

        self.fields["categories"].choices = om_core.TypeAssist.objects.filter(
            (Q(client_id=S["client_id"]) | Q(cuser__is_superuser=True)),
            tatype__tacode="WORKORDER_CATEGORY",
            enable=True,
        ).values_list("tacode", "taname")
        self.fields[
            "ticketcategory"
        ].queryset = om_core.TypeAssist.objects.filter_for_dd_notifycategory_field(
            self.request, sitewise=True
        )
        self.fields["asset"].queryset = Asset.objects.filter_for_dd_asset_field(
            self.request, ["ASSET", "CHECKPOINT"], sitewise=True
        )
        self.fields["location"].queryset = Location.objects.filter(
            Q(client_id=S["client_id"]), bu_id=S["bu_id"]
        )
        self.fields["vendor"].queryset = Vendor.objects.filter(
            Q(enable=True) & Q(client_id=S["client_id"]) & Q(bu_id=S["bu_id"])
            | (Q(client_id=S["client_id"]) & Q(show_to_all_sites=True))
        )
        self.fields["qset"].queryset = QuestionSet.objects.filter(
            client_id=S["client_id"], enable=True, type=QuestionSet.Type.WORKORDER
        )
        initailize_form_fields(self)
        if not self.instance.id:
            self.fields["plandatetime"].initial = timezone.now()
            self.fields["priority"].initial = Wom.Priority.LOW
            self.fields["ticketcategory"].initial = om_core.TypeAssist.objects.get(
                tacode="AUTOCLOSED", tatype__tacode="NOTIFYCATEGORY"
            )
