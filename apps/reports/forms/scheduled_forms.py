"""Forms for scheduled reports and PDF generation."""

from enum import Enum

from django import forms
from django_select2 import forms as s2forms

from apps.peoples import models as pm
from apps.reports.models import ScheduleReport, GeneratePDF
from apps.core.utils_new.business_logic import initailize_form_fields


class EmailReportForm(forms.ModelForm):
    """Form for scheduling reports via email."""

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
        if cd.get("cron"):
            cd.update({"crontype": self.cron_type(cd["cron"])})
        return cd

    def cron_type(self, cron_expr):
        if not cron_expr or not isinstance(cron_expr, str):
            return self.CronType.UNKNOWN.value
        fields = cron_expr.split()
        if len(fields) != 5:
            return self.CronType.UNKNOWN.value
        if all(field == "*" for field in fields[2:]):
            return self.CronType.DAILY.value
        elif fields[2] == "*" and fields[3] == "*" and fields[4] in map(str, range(0, 8)):
            return self.CronType.WEEKLY.value
        elif fields[2] in map(str, range(1, 32)) and fields[3] == "*" and fields[4] == "*":
            return self.CronType.MONTHLY.value
        else:
            return self.CronType.WORKINGDAYS.value


class GeneratePDFForm(forms.ModelForm):
    """Form for generating PDF reports."""

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
        ]

    customer = forms.ChoiceField(label="Customer", required=True)
    site = forms.ChoiceField(label="Site", required=True)
    period_from = forms.MultipleChoiceField(
        label="Period",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        required=True,
    )
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
        self._set_conditional_required_fields()
        initailize_form_fields(self)

    def _set_conditional_required_fields(self):
        """Set required status based on initial values."""
        if not self.fields["customer"].initial:
            self.fields["customer"].required = False
        if not self.fields["site"].initial:
            self.fields["site"].required = False
        if not self.fields["period_from"].initial:
            self.fields["period_from"].required = False
        if not self.fields["is_page_required"].initial:
            self.fields["is_page_required"].required = False
