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




class EmailReportForm(forms.ModelForm):
    class CronType(Enum):
        """Enum for different cron expression types."""

        DAILY = "daily"
        WEEKLY = "weekly"
        MONTHLY = "monthly"
        WORKINGDAYS = "workingdays"
        UNKNOWN = "unknown"

    required_css_class = "required"
    WORKINGDAYS_CHOICES = ScheduleReport.WORKINGDAYS
    frequencytypes = [
        ("workingdays", "Working Days"),
        ("somethingelse", "Something Else"),
    ]

    cc = forms.MultipleChoiceField(
        label="Email-CC",
        required=False,
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
    )
    to_addr = forms.MultipleChoiceField(
        label="Email-To",
        required=False,
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
    )
    cronstrue = forms.CharField(
        widget=forms.Textarea(attrs={"readonly": True, "rows": 2}), required=False
    )
    frequencytype = forms.ChoiceField(
        label="Frequency Type",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        choices=frequencytypes,
        required=False,
    )
    workingdays = forms.ChoiceField(
        label="Working Days",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        choices=WORKINGDAYS_CHOICES,
        required=False,
    )
    workingperiod = forms.TimeField(label="Period", required=False)

    class Meta:
        fields = [
            "report_type",
            "report_name",
            "cron",
            "report_sendtime",
            "enable",
            "ctzoffset",
            "to_addr",
            "cc",
            "crontype",
            "workingdays",
        ]
        model = ScheduleReport
        labels = {"cron": "Scheduler"}

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["cc"].choices = pm.People.objects.filter(
            isverified=True, client_id=self.S["client_id"]
        ).values_list("email", "peoplename")
        self.fields["to_addr"].choices = pm.People.objects.filter(
            isverified=True, client_id=self.S["client_id"]
        ).values_list("email", "peoplename")

        initailize_form_fields(self)

    def clean(self):
        cd = super().clean()
        # Only process crontype if cron field is present and valid
        if cd.get("cron"):
            cd.update({"crontype": self.cron_type(cd["cron"])})
        return cd

    def cron_type(self, cron_expr):
        if not cron_expr or not isinstance(cron_expr, str):
            return self.CronType.UNKNOWN.value
        fields = cron_expr.split()
        if len(fields) != 5:
            return self.CronType.UNKNOWN.value

        # Check for daily cron expressions
        if all(field == "*" for field in fields[2:]):
            return self.CronType.DAILY.value

        # Revised check for weekly cron expressions
        elif (
            fields[2] == "*" and fields[3] == "*" and fields[4] in map(str, range(0, 8))
        ):
            return self.CronType.WEEKLY.value

        # Revised check for monthly cron expressions
        elif (
            fields[2] in map(str, range(1, 32))
            and fields[3] == "*"
            and fields[4] == "*"
        ):
            return self.CronType.MONTHLY.value

        # Otherwise, return unknown
        else:
            return self.CronType.WORKINGDAYS.value




