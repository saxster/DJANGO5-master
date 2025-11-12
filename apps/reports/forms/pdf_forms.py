from django import forms
from apps.client_onboarding import models as om_client
from apps.core_onboarding import models as om_core
from apps.peoples import models as pm
from django_select2 import forms as s2forms
from django.db.models import Q
from datetime import datetime, timedelta
from apps.activity.models.location_model import Location
from apps.activity.models.question_model import QuestionSet
from apps.activity.models.asset_model import Asset
from apps.reports.models import ScheduleReport, GeneratePDF
from enum import Enum
from apps.core.utils_new.business_logic import initailize_form_fields




class GeneratePDFForm(forms.ModelForm):
    required_css_class = "required"

    class Meta:
        model = GeneratePDF
        fields = [
            "additional_filter",
            "customer",
            "site",
            "period_from",
            "company",
            "document_type",
            "is_page_required",
            "type_of_form",
        ]  # period_to & number_of_period

    # data fields
    customer = forms.ChoiceField(label="Customer", required=True)
    site = forms.ChoiceField(label="Site", required=True)
    period_from = forms.MultipleChoiceField(
        label="Period",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        required=True,
    )
    # period_to           = forms.ChoiceField(label='Period To', required=True)
    is_page_required = forms.BooleanField(
        label="Include Only Highlighted Page",
        required=True,
        initial=True,
        help_text="Check this box to include only the highlighted page, excluding all unhighlighted pages.",
    )
    pf_code_no = forms.CharField(label="PF Code No.", required=True)
    esic_code_no = forms.CharField(label="ESIC Code No.", required=True)
    ticket_no = forms.CharField(label="Ticket No.", required=True)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        if not self.fields["customer"].initial:
            self.fields["customer"].required = False
        if not self.fields["site"].initial:
            self.fields["site"].required = False
        if not self.fields["period_from"].initial:
            self.fields["period_from"].required = False
        if not self.fields["is_page_required"].initial:
            self.fields["is_page_required"].required = False
        # if not self.fields['period_to'].initial:
        #     self.fields['period_to'].required = False
        initailize_form_fields(self)


