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




class ReportForm(forms.Form):
    required_css_class = "required"
    report_templates = [
        ("", "Select Report"),
        ("TASKSUMMARY", "Task Summary"),
        ("TOURSUMMARY", "Tour Summary"),
        ("LISTOFTASKS", "List of Tasks"),
        ("LISTOFTOURS", "List of Internal Tours"),
        ("DYNAMICTOURLIST", "Dynamic Tour List"),
        ("STATICTOURLIST", "Static Tour List"),
        ("PPMSUMMARY", "PPM Summary"),
        ("LISTOFTICKETS", "List of Tickets"),
        ("WORKORDERLIST", "Work Order List"),
        ("SITEREPORT", "Site Report"),
        ("PEOPLEQR", "People-QR"),
        ("ASSETQR", "Asset-QR"),
        ("CHECKPOINTQR", "Checkpoint-QR"),
        ("LOCATIONQR", "Location-QR"),
        ("ASSETWISETASKSTATUS", "Assetwise Task Status"),
        ("STATICDETAILEDTOURSUMMARY", "Static Detailed Tour Summary"),
        ("DYNAMICDETAILEDTOURSUMMARY", "Dynamic Detailed Tour Summary"),
        ("DYNAMICTOURDETAILS", "Dynamic Tour Details"),
        ("STATICTOURDETAILS", "Static Tour Details"),
        ("SITEVISITREPORT", "SiteVisitReport"),
        ("LOGSHEET", "Log Sheet"),
        ("RP_SITEVISITREPORT", "Route Plan Site Visit Report"),
        ("PEOPLEATTENDANCESUMMARY", "People Attendance Summary"),
    ]
    download_or_send_options = [
        ("DOWNLOAD", "Download"),
        ("SEND", "Email"),
    ]
    format_types = [
        ("", "Select Format"),
        ("pdf", "PDF"),
        ("xlsx", "XLSX"),
        ("html", "HTML"),
        ("json", "JSON"),
        ("csv", "CSV"),
    ]
    SIZES = [
        (120, "Small"),
        (200, "Medium"),
        (300, "Large"),
    ]

    People_or_Site_CHOICES = [("PEOPLE", "People"), ("SITE", "Site")]
    Asset_or_Site_CHOICES = [("ASSET", "Asset"), ("SITE", "Site")]
    Checkpoint_or_Site_CHOICES = [("CHECKPOINT", "Checkpoint"), ("SITE", "Site")]
    Location_or_Site_CHOICES = [("LOCATION", "Location"), ("SITE", "Site")]

    # data fields
    report_name = forms.ChoiceField(
        label="Report Name",
        required=True,
        choices=report_templates,
        initial="TASK_SUMMARY",
    )
    site = forms.ChoiceField(
        label="Site",
        required=False,
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
    )
    sitegroup = forms.MultipleChoiceField(
        label="Site Group",
        required=False,
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
    )
    fromdate = forms.DateField(
        label="From Date", required=False, input_formats=["%d-%b-%Y", "%Y-%m-%d"]
    )
    fromdatetime = forms.DateTimeField(
        label="From Date Time",
        required=False,
        input_formats=["%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M:%S"],
    )
    uptodate = forms.DateField(
        label="To Date", required=False, input_formats=["%d-%b-%Y", "%Y-%m-%d"]
    )
    uptodatetime = forms.DateTimeField(
        label="To Date Time",
        required=False,
        input_formats=["%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M:%S"],
    )
    asset = forms.ChoiceField(
        label="Asset",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )
    qset = forms.ChoiceField(
        label="Question Set",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )
    assettype = forms.ChoiceField(
        label="Asset Type",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )
    checkpoint = forms.CharField(
        label="Checkpoint",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )
    location = forms.CharField(
        label="Location",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )
    checkpoint_type = forms.CharField(
        label="Checkpoint Type",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )
    location_type = forms.CharField(
        label="Location Type",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )
    ticketcategory = forms.CharField(
        label="Ticket Category",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )
    peoplegroup = forms.ChoiceField(
        label="People Group",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
        choices=[],
    )
    people = forms.ChoiceField(
        label="People",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
        choices=[],
    )
    mult_people = forms.MultipleChoiceField(
        label="People",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        required=False,
        choices=[],
    )
    mult_asset = forms.MultipleChoiceField(
        label="Asset",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        required=False,
        choices=[],
    )
    mult_checkpoint = forms.MultipleChoiceField(
        label="Checkpoint",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        required=False,
        choices=[],
    )
    mult_location = forms.MultipleChoiceField(
        label="Location",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
        required=False,
        choices=[],
    )
    qrsize = forms.ChoiceField(
        label="QR Size",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        choices=SIZES,
        initial=120,
        required=False,
    )
    assetcategory = forms.ChoiceField(
        label="Asset Category",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        required=False,
    )
    site_or_people = forms.ChoiceField(
        label="Site/People",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        choices=People_or_Site_CHOICES,
        required=False,
    )
    site_or_asset = forms.ChoiceField(
        label="Site/Asset",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        choices=Asset_or_Site_CHOICES,
        required=False,
    )
    site_or_checkpoint = forms.ChoiceField(
        label="Site/Checkpoint",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        choices=Checkpoint_or_Site_CHOICES,
        required=False,
    )
    site_or_location = forms.ChoiceField(
        label="Site/Location",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        choices=Location_or_Site_CHOICES,
        required=False,
    )

    # other form fields
    format = forms.ChoiceField(
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        label="Format",
        required=True,
        choices=format_types,
    )
    export_type = forms.ChoiceField(
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        label="Get File with",
        required=True,
        choices=download_or_send_options,
        initial="DOWNLOAD",
    )
    cc = forms.MultipleChoiceField(
        label="CC",
        required=False,
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
    )
    to_addr = forms.MultipleChoiceField(
        label="To",
        required=False,
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
    )
    preview = forms.CharField(widget=forms.HiddenInput, required=False, initial="false")
    email_body = forms.CharField(
        label="Email Body",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    ctzoffset = forms.IntegerField(required=False)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields[
            "site"
        ].choices = pm.Pgbelonging.objects.get_assigned_sites_to_people(
            S.get("_auth_user_id"), True
        )
        self.fields["sitegroup"].choices = [("", "")] + list(
            pm.Pgroup.objects.filter(
                identifier__tacode="SITEGROUP",
                bu_id__in=S["assignedsites"],
                enable=True,
            ).values_list("id", "groupname")
        )
        self.fields[
            "peoplegroup"
        ].choices = pm.Pgroup.objects.filter_for_dd_pgroup_field(
            self.request, sitewise=True, choices=True
        )
        self.fields["people"].choices = self.fields[
            "mult_people"
        ].choices = pm.People.objects.filter_for_dd_people_field(
            self.request, sitewise=True, choices=True
        )
        self.fields["asset"].choices = self.fields[
            "mult_asset"
        ].choices = Asset.objects.asset_choices_for_report(
            self.request, sitewise=True, choices=True, identifier="ASSET"
        )
        self.fields["location"].choices = self.fields[
            "mult_location"
        ].choices = Location.objects.location_choices_for_report(
            self.request, sitewise=True, choices=True
        )
        self.fields["checkpoint"].choices = self.fields[
            "mult_checkpoint"
        ].choices = Asset.objects.asset_choices_for_report(
            self.request, sitewise=True, choices=True, identifier="CHECKPOINT"
        )
        self.fields["assettype"].choices = Asset.objects.asset_type_choices_for_report(
            self.request
        )
        self.fields[
            "location_type"
        ].choices = Location.objects.location_type_choices_for_report(self.request)
        self.fields[
            "assetcategory"
        ].choices = Asset.objects.asset_category_choices_for_report(self.request)
        self.fields["qset"].choices = QuestionSet.objects.qset_choices_for_report(
            self.request
        )
        self.fields["fromdate"].initial = self.get_default_range_of_dates()[0]
        self.fields["uptodate"].initial = self.get_default_range_of_dates()[1]
        self.fields["cc"].choices = pm.People.objects.filter(
            isverified=True, client_id=S["client_id"]
        ).values_list("email", "peoplename")
        self.fields["to_addr"].choices = pm.People.objects.filter(
            isverified=True, client_id=S["client_id"]
        ).values_list("email", "peoplename")
        initailize_form_fields(self)

    def get_default_range_of_dates(self):
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_month - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)
        return first_day_of_last_month, last_day_of_last_month

    def clean(self):
        cd = super().clean()
        if (
            cd["report_name"] == "SITEREPORT"
            and cd.get("people") in ["", None]
            and cd.get("sitegroup") in ["", None]
        ):
            raise forms.ValidationError(
                f"Both Site Group and People cannot be empty, when the report is {cd.get('report_name')}"
            )

        self.validate_date_range(
            cd, "fromdate", "uptodate", "From date cannot be greater than To date"
        )
        self.validate_date_range(
            cd,
            "fromdatetime",
            "uptodatetime",
            "From datetime cannot be greater than To datetime",
        )

        if cd.get("format") != "pdf":
            self.cleaned_data["preview"] = "false"
        return cd

    def validate_date_range(self, cd, field1, field2, error_msg):
        date1 = cd.get(field1)
        date2 = cd.get(field2)

        if date1 and date2 and date1 > date2:
            raise forms.ValidationError(error_msg)

        if date1 and date2 and (date2 - date1).days > 31:
            raise forms.ValidationError(
                "The difference between {} and {} should not be greater than 1 month".format(
                    field1, field2
                )
            )




