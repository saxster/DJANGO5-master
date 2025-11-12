"""Scheduler exclusive tour-related forms."""
from django.conf import settings
from django import forms
from django.utils.translation import gettext_lazy as _
from apps.activity.forms.job_form import JobForm
from apps.client_onboarding import utils as client_utils
from apps.core import utils
from django_select2 import forms as s2forms
from django.db.models import Q
from apps.activity.models.question_model import QuestionSet
import apps.peoples.models as pm
from apps.core_onboarding.models import TypeAssist
from apps.core.utils_new.business_logic import initailize_form_fields
from apps.core.utils_new.cron_utilities import validate_cron_for_form
import logging

logger = logging.getLogger(__name__)


class Schd_E_TourJobForm(JobForm):
    """Scheduler Exclusive Tour Job Form."""
    ASSIGNTO_CHOICES = [("PEOPLE", "People"), ("GROUP", "Group")]
    timeInChoices = [("MIN", "Min"), ("HRS", "Hours")]
    assign_to = forms.ChoiceField(choices=ASSIGNTO_CHOICES, initial="PEOPLE")
    israndom = forms.BooleanField(initial=False, label="Random Tour", required=False)
    tourfrequency = forms.IntegerField(
        min_value=1, max_value=3, initial=1, label="Frequency", required=False
    )
    breaktime = forms.IntegerField(label="Frequency", required=False)
    required_css_class = "required"

    class Meta(JobForm.Meta):
        JobForm.Meta.labels.update(
            {
                "sgroup": "Route Name",
                "qset": "Question Set",
                "planduration": "Plan Duration (mins)",
                "gracetime": "Grace Time (mins)",
            }
        )
        JobForm.Meta.widgets.update(
            {
                "identifier": forms.TextInput(attrs={"style": "display:none;"}),
                "starttime": forms.TextInput(attrs={"style": "display:none;"}),
                "endtime": forms.TextInput(attrs={"style": "display:none;"}),
                "frequency": forms.TextInput(attrs={"style": "display:none;"}),
                "priority": forms.TextInput(attrs={"style": "display:none;"}),
                "seqno": forms.TextInput(attrs={"style": "display:none;"}),
                "ticketcategory": forms.TextInput(attrs={"style": "display:none;"}),
            }
        )
        exclude = ["jobdesc"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        request, S = self.request, self.request.session
        super().__init__(*args, **kwargs)
        self.fields["israndom"].widget.attrs["class"] = "btdeciders"
        self.fields["tourfrequency"].widget.attrs["class"] = "btdeciders"
        self.fields["fromdate"].input_formats = settings.DATETIME_INPUT_FORMATS
        self.fields["uptodate"].input_formats = settings.DATETIME_INPUT_FORMATS
        self.fields["ticketcategory"].initial = TypeAssist.objects.get(
            tacode="AUTOCLOSED"
        )
        self.fields["sgroup"].required = True
        self.fields["qset"].required = True
        self.fields["identifier"].widget.attrs = {"style": "display:none"}
        self.fields["expirytime"].widget.attrs = {"style": "display:none"}
        self.fields["starttime"].widget.attrs = {"style": "display:none"}
        self.fields["endtime"].widget.attrs = {"style": "display:none"}
        self.fields["frequency"].widget.attrs = {"style": "display:none"}
        self.fields["priority"].widget.attrs = {"style": "display:none"}
        self.fields["seqno"].widget.attrs = {"style": "display:none"}
        self.fields["people"].widget.attrs = {"data-theme": "bootstrap5"}
        self.fields[
            "qset"
        ].queryset = QuestionSet.objects.get_proper_checklist_for_scheduling(
            request, ["RPCHECKLIST"]
        )
        self.fields[
            "ticketcategory"
        ].queryset = TypeAssist.objects.filter_for_dd_notifycategory_field(request)
        self.fields["sgroup"].queryset = pm.Pgroup.objects.filter(
            identifier__tacode="SITEGROUP", bu_id__in=S["assignedsites"], enable=True
        )
        self.fields["people"].queryset = pm.People.objects.filter_for_dd_people_field(
            request
        )
        self.fields["pgroup"].queryset = pm.Pgroup.objects.filter_for_dd_pgroup_field(
            request
        )
        self.fields["shift"].queryset = ShiftModel.objects.filter(
            ~Q(shiftname="NONE"),
            client_id=request.session["client_id"],
            bu_id=request.session["bu_id"],
            enable=True,
        )
        initailize_form_fields(self)

    def clean(self):
        super().clean()
        cd = self.cleaned_data
        self.cleaned_data = self.check_nones(self.cleaned_data)
        if cd["people"] is None and cd["pgroup"] is None:
            raise forms.ValidationError(
                "Cannot be proceed assigned tour to either people or group."
            )
        if cd.get("fromdate") and cd.get("uptodate"):
            if cd["fromdate"] > cd["uptodate"]:
                raise forms.ValidationError(
                    {"uptodate": "Valid To cannot be less than Valid From."}
                )

    def check_nones(self, cd):
        fields = {
            "parent": "get_or_create_none_job",
            "people": "get_or_create_none_people",
            "pgroup": "get_or_create_none_pgroup",
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
