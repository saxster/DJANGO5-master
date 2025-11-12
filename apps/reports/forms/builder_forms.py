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




class TestForm(forms.Form):
    firstname = forms.CharField(max_length=10, required=False)
    lastname = forms.CharField(max_length=10, required=True)
    middlename = forms.CharField(max_length=10, required=True)




class ReportBuilderForm(forms.Form):
    model = forms.ChoiceField(
        label="Model",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        help_text="Select a model where you want data from",
    )
    columns = forms.MultipleChoiceField(
        label="Coumns",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        help_text="Select columns required in the report",
    )


def get_report_templates():
    return




