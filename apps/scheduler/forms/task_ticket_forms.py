"""Scheduler task and ticket-related forms."""
from django.conf import settings
from django import forms
from django.utils.translation import gettext_lazy as _
from apps.activity.forms.job_form import JobForm, JobNeedForm
from apps.client_onboarding import utils as client_utils
from apps.core import utils
from django_select2 import forms as s2forms
from apps.activity.models.question_model import QuestionSet
import apps.peoples.models as pm
from apps.core_onboarding.models import TypeAssist
from apps.core.utils_new.business_logic import initailize_form_fields
from apps.core.utils_new.cron_utilities import validate_cron_for_form
import logging

logger = logging.getLogger(__name__)


class SchdTaskFormJob(JobForm):
    """Scheduler Task Job Form - for planned tasks."""
    ASSIGNTO_CHOICES = [("PEOPLE", "People"), ("GROUP", "Group")]
    timeInChoices = [("MINS", "Min"), ("HRS", "Hour"), ("DAYS", "Day")]
    required_css_class = "required"

    planduration_type = forms.ChoiceField(
        choices=timeInChoices,
        initial="MIN",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
    )
    gracetime_type = forms.ChoiceField(
        choices=timeInChoices,
        initial="MIN",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
    )
    expirytime_type = forms.ChoiceField(
        choices=timeInChoices,
        initial="MIN",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
    )
    assign_to = forms.ChoiceField(choices=ASSIGNTO_CHOICES, initial="PEOPLE")

    class Meta(JobForm.Meta):
        exclude = ["shift"]
        JobForm.Meta.widgets.update(
            {
                "identifier": forms.TextInput(attrs={"style": "display:none;"}),
                "starttime": forms.TextInput(attrs={"style": "display:none;"}),
                "endtime": forms.TextInput(attrs={"style": "display:none;"}),
                "frequency": forms.TextInput(attrs={"style": "display:none;"}),
                "ticketcategory": s2forms.Select2Widget(
                    attrs={"data-theme": "bootstrap5"}
                ),
                "scantype": s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
                "priority": s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
            }
        )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request
        super(SchdTaskFormJob, self).__init__(*args, **kwargs)
        self.fields["fromdate"].input_formats = settings.DATETIME_INPUT_FORMATS
        self.fields["uptodate"].input_formats = settings.DATETIME_INPUT_FORMATS
        self.fields["jobdesc"].required = False
        self.fields["identifier"].widget.attrs = {"style": "display:none"}
        self.fields["starttime"].widget.attrs = {"style": "display:none"}
        self.fields["endtime"].widget.attrs = {"style": "display:none"}
        self.fields["frequency"].widget.attrs = {"style": "display:none"}
        self.fields["expirytime"].label = "Grace Time (After)"
        self.fields["gracetime"].label = "Grace Time (Before)"

        self.fields[
            "ticketcategory"
        ].queryset = TypeAssist.objects.filter_for_dd_notifycategory_field(
            S, sitewise=True
        )
        self.fields["qset"].queryset = QuestionSet.objects.filter_for_dd_qset_field(
            S, ["CHECKLIST"], sitewise=True
        )
        self.fields["asset"].queryset = Asset.objects.filter_for_dd_asset_field(
            S, identifiers=["ASSET", "CHECKPOINT"], sitewise=True
        )
        self.fields["pgroup"].queryset = pm.Pgroup.objects.filter_for_dd_pgroup_field(
            S, sitewise=True
        )
        self.fields["people"].queryset = pm.People.objects.filter_for_dd_people_field(
            S, sitewise=True
        )
        initailize_form_fields(self)

    def clean(self):
        cd = self.cleaned_data
        times_names = ["planduration", "expirytime", "gracetime"]
        types_names = ["planduration_type", "expirytime_type", "gracetime_type"]
        self.cleaned_data = self.check_nones(self.cleaned_data)

        times = [cd.get(time) for time in times_names]
        types = [cd.get(type) for type in types_names]
        for time, type, name in zip(times, types, times_names):
            self.cleaned_data[name] = self.convertto_mins(type, time)

        if cd.get("people") is None and cd.get("pgroup") is None:
            raise forms.ValidationError(
                "Cannot be proceed assigned tour to either people or group."
            )

        if cd.get("fromdate") and cd.get("uptodate"):
            if cd["fromdate"] > cd["uptodate"]:
                raise forms.ValidationError(
                    {"uptodate": "Valid To cannot be less than Valid From."}
                )

    @staticmethod
    def convertto_mins(_type, _time):
        if _type == "HRS":
            return _time * 60
        return _time * 24 * 60 if _type == "DAYS" else _time

    def check_nones(self, cd):
        fields = {
            "parent": "get_or_create_none_job",
            "people": "get_or_create_none_people",
            "pgroup": "get_or_create_none_pgroup",
            "asset": "get_or_create_none_asset",
        }
        for field, func in fields.items():
            if cd.get(field) in [None, ""]:
                cd[field] = getattr(utils, func)()
        return cd

    def clean_cronstrue(self):
        val = self.cleaned_data.get("cron")
        if not val:
            raise forms.ValidationError(_("Invalid Cron"))

        error = validate_cron_for_form(val)
        if error:
            raise forms.ValidationError(error)

        parts = val.strip().split()
        if len(parts) == 5 and parts[0] == "*":
            raise forms.ValidationError(
                "Warning: Scheduling every minute is not allowed!"
            )

        return val


class TicketForm(JobNeedForm):
    """Ticket/Incident form for work ticket tracking."""
    ASSIGNTO_CHOICES = [("PEOPLE", "People"), ("GROUP", "Group")]
    assign_to = forms.ChoiceField(choices=ASSIGNTO_CHOICES, initial="PEOPLE")
    required_css_class = "required"

    class Meta(JobNeedForm.Meta):
        JobNeedForm.Meta.widgets.update(
            {
                "scantype": forms.TextInput(attrs={"style": "display:none"}),
                "frequency": forms.TextInput(attrs={"style": "display:none"}),
                "starttime": forms.TextInput(attrs={"style": "display:none"}),
                "endtime": forms.TextInput(attrs={"style": "display:none"}),
                "identifier": forms.TextInput(attrs={"style": "display:none"}),
                "cuser": s2forms.Select2Widget(attrs={"disabled": "readonly"}),
            }
        )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super(TicketForm, self).__init__(*args, **kwargs)
        self.fields["plandatetime"].input_formats = settings.DATETIME_INPUT_FORMATS
        self.fields["expirydatetime"].input_formats = settings.DATETIME_INPUT_FORMATS
        if not self.instance.id:
            self.fields["jobstatus"].widget.attrs = {"disabled": "readonly"}
            self.fields["ticketno"].widget.attrs = {
                "disabled": "disabled",
                "readonly": "readonly",
            }
        self.fields["cuser"].required = False
        self.fields["asset"].label = "Location"

        self.fields["ticketcategory"].queryset = TypeAssist.objects.filter(
            tatype__tacode="TICKETCATEGORY",
            client_id=S["client_id"],
            bu_id=S["bu_id"],
            enable=True,
        )
        self.fields[
            "assignedtopeople"
        ].queryset = pm.People.objects.filter_for_dd_people_field(
            self.request, sitewise=True
        )
        self.fields[
            "assignedtogroup"
        ].queryset = pm.Pgroup.objects.filter_for_dd_pgroup_field(
            self.request, sitewise=True
        )
        self.fields[
            "location"
        ].queryset = Location.objects.filter_for_dd_location_field(
            self.request, sitewise=True
        )
        self.fields["asset"].queryset = Asset.objects.filter_for_dd_asset_field(
            self.request, ["ASSET", "CHECKPOINT"], sitewise=True
        )
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        result = super(TicketForm, self).is_valid()
        client_utils.apply_error_classes(self)
        return result

    def clean_plandatetime(self):
        if val := self.cleaned_data.get("plandatetime"):
            val = client_utils.to_utc(val)
            return val

    def clean_expirydatetime(self):
        if val := self.cleaned_data.get("expirydatetime"):
            val = client_utils.to_utc(val)
            return val

    def clean_starttime(self):
        if val := self.cleaned_data.get("starttime"):
            val = client_utils.to_utc(val)
            return val

    def clean_endtime(self):
        if val := self.cleaned_data.get("endtime"):
            val = client_utils.to_utc(val)
            return val

    @staticmethod
    def clean_frequency():
        return "NONE"
