"""Scheduler tour-related forms - Inherited Tour Job Forms"""
from django.conf import settings
from django import forms
from django.utils.translation import gettext_lazy as _
from apps.activity.forms.job_form import JobForm, JobNeedForm
from apps.client_onboarding import utils as client_utils
from apps.core import utils
from django_select2 import forms as s2forms
from django.db.models import Q
from apps.activity.models.question_model import QuestionSet
import apps.peoples.models as pm
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
from django.utils import timezone as dtimezone
from datetime import datetime
from apps.core.utils_new.business_logic import initailize_form_fields
from apps.core.caching.form_mixins import CachedDropdownMixin, OptimizedModelForm
from apps.core.utils_new.cron_utilities import validate_cron_for_form
import logging

logger = logging.getLogger(__name__)


class Schd_I_TourJobForm(CachedDropdownMixin, JobForm):
    """Scheduler Inherited Tour Job Form with cached dropdown optimization."""
    ASSIGNTO_CHOICES = [("PEOPLE", "People"), ("GROUP", "Group")]
    assign_to = forms.ChoiceField(choices=ASSIGNTO_CHOICES, initial="PEOPLE")
    istimebound = forms.BooleanField(
        initial=True, required=False, label="Is Time Restricted"
    )
    isdynamic = forms.BooleanField(initial=False, required=False, label="Is Dynamic")
    required_css_class = "required"

    cached_dropdown_fields = {
        'ticketcategory': {
            'model': TypeAssist,
            'filter_method': 'filter_for_dd_notifycategory_field',
            'sitewise': True,
            'version': '1.0'
        },
        'pgroup': {
            'model': pm.Pgroup,
            'filter_method': 'filter_for_dd_pgroup_field',
            'sitewise': True,
            'version': '1.0'
        },
        'people': {
            'model': pm.People,
            'filter_method': 'filter_for_dd_people_field',
            'sitewise': False,
            'version': '1.0'
        }
    }

    class Meta(JobForm.Meta):
        exclude = ["shift"]
        JobForm.Meta.widgets.update(
            {
                "identifier": forms.TextInput(attrs={"style": "display:none;"}),
                "starttime": forms.TextInput(attrs={"style": "display:none;"}),
                "endtime": forms.TextInput(attrs={"style": "display:none;"}),
                "frequency": forms.TextInput(attrs={"style": "display:none;"}),
            }
        )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.get("request", None)
        super().__init__(*args, **kwargs)
        self.set_initial_values()
        self.set_required_false_for_dynamic()
        self.set_display_none()
        self.fields["fromdate"].input_formats = settings.DATETIME_INPUT_FORMATS
        self.fields["uptodate"].input_formats = settings.DATETIME_INPUT_FORMATS
        self.fields["ticketcategory"].required = True
        initailize_form_fields(self)
        logger.debug(f"Initialized {self.__class__.__name__} with cached dropdowns")

    def clean(self):
        super().clean()
        cd = self.cleaned_data
        self.cleaned_data = self.check_nones(self.cleaned_data)
        self.caluclate_planduration_gracetime(cd)
        self.set_instance_data_for_dynamic()

        if not cd.get("ticketcategory"):
            raise forms.ValidationError(
                {"ticketcategory": "Notify Category is required."}
            )

        if cd["people"] is None and cd["pgroup"] is None:
            raise forms.ValidationError(
                "Cannot be proceed assigned tour to either people or group."
            )
        if (
            cd.get("fromdate")
            and cd.get("uptodate")
            and cd["fromdate"] > cd["uptodate"]
        ):
            raise forms.ValidationError(
                {"uptodate": "Valid To cannot be less than Valid From."}
            )
        if cd.get("isdynamic"):
            cd["fromdate"] = dtimezone.now()
            cd["uptodate"] = datetime(9999, 12, 30, 23, 59)
            cd["planduration"] = cd["gracetime"] = cd["expirytime"] = 0
        return cd

    def set_display_none(self):
        for field in ["identifier", "expirytime", "starttime", "endtime", "frequency"]:
            self.fields[field].widget.attrs = {"style": "display:none"}

    def set_initial_values(self):
        if self.instance.id:
            self.fields["istimebound"].initial = self.instance.other_info["istimebound"]
            self.fields["isdynamic"].initial = self.instance.other_info["isdynamic"]

    def set_required_false_for_dynamic(self):
        if "isdynamic" in self.data or (
            self.instance.id and self.instance.other_info["isdynamic"]
        ):
            if self.data.get("isdynamic") or (
                self.instance.id and self.instance.other_info["isdynamic"]
            ):
                for field in [
                    "planduration",
                    "gracetime",
                    "cron",
                    "fromdate",
                    "uptodate",
                ]:
                    self.fields[field].required = False

    def set_instance_data_for_dynamic(self):
        if self.instance.id and self.instance.other_info["isdynamic"]:
            self.cleaned_data["fromdate"] = self.instance.fromdate
            self.cleaned_data["uptodate"] = self.instance.uptodate
            self.cleaned_data["planduration"] = self.instance.planduration
            self.cleaned_data["gracetime"] = self.instance.gracetime
            self.cleaned_data["istimebound"] = self.instance.other_info["istimebound"]
            self.cleaned_data["isdynamic"] = self.instance.other_info["isdynamic"]

    def caluclate_planduration_gracetime(self, cd):
        times_names = ["planduration", "gracetime"]
        types_names = ["freq_duration", "freq_duration2"]
        times = [cd.get(time) for time in times_names]
        types = [cd.get(type) for type in types_names]
        if times and types:
            for time, type, name in zip(times, types, times_names):
                self.cleaned_data[name] = self.convertto_mins(type, time)

    def clean_from_date(self):
        if val := self.cleaned_data.get("fromdate"):
            val = client_utils.to_utc(val)
            return val

    def clean_upto_date(self):
        if val := self.cleaned_data.get("uptodate"):
            val = client_utils.to_utc(val)
            return val

    def is_valid(self) -> bool:
        result = super(Schd_I_TourJobForm, self).is_valid()
        utils.apply_error_classes(self)
        return result

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

    @staticmethod
    def clean_slno():
        return -1

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


class I_TourFormJobneed(JobNeedForm):
    """Inherited Tour Job Need Form."""
    timeInChoices = [("MIN", "Min"), ("HRS", "Hour"), ("DAY", "Day"), ("WEEK", "Week")]
    ASSIGNTO_CHOICES = [("PEOPLE", "People"), ("GROUP", "Group")]
    assign_to = forms.ChoiceField(choices=ASSIGNTO_CHOICES, initial="PEOPLE")
    timeIn = forms.ChoiceField(
        choices=timeInChoices,
        initial="MIN",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
    )
    required_css_class = "required"

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["plandatetime"].input_formats = settings.DATETIME_INPUT_FORMATS
        self.fields["expirydatetime"].input_formats = settings.DATETIME_INPUT_FORMATS
        self.fields["identifier"].widget.attrs = {
            "style": "display:none",
            "data-theme": "bootstrap5",
        }
        self.fields["starttime"].widget.attrs = {
            "disabled": "disabled",
            "data-theme": "bootstrap5",
        }
        self.fields["endtime"].widget.attrs = {
            "disabled": "disabled",
            "data-theme": "bootstrap5",
        }
        self.fields["performedby"].widget.attrs = {
            "disabled": "disabled",
            "data-theme": "bootstrap5",
        }
        self.fields["qset"].widget.attrs = {"data-theme": "bootstrap5"}
        self.fields["asset"].widget.attrs = {"data-theme": "bootstrap5"}
        self.fields["qset"].label = "Checklist"
        self.fields["asset"].label = "Asset/Smartplace"
        self.fields[
            "ticketcategory"
        ].widget.queryset = TypeAssist.objects.filter_for_dd_notifycategory_field(
            self.request, sitewise=True
        )
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        result = super(I_TourFormJobneed, self).is_valid()
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


class E_TourFormJobneed(JobNeedForm):
    """Exclusive Tour Job Need Form."""
    timeInChoices = [("MIN", "Min"), ("HRS", "Hour"), ("DAY", "Day"), ("WEEK", "Week")]
    ASSIGNTO_CHOICES = [("PEOPLE", "People"), ("GROUP", "Group")]
    assign_to = forms.ChoiceField(choices=ASSIGNTO_CHOICES, initial="PEOPLE")
    timeIn = forms.ChoiceField(
        choices=timeInChoices, initial="MIN", widget=s2forms.Select2Widget
    )
    required_css_class = "required"

    def __init__(self, *args, **kwargs):
        super(JobNeedForm, self).__init__(*args, **kwargs)
        self.fields["endtime"].label = "End Time"
        for k in ["scantype", "starttime", "endtime"]:
            self.fields[k].widget.attrs.pop("style")
            if k in ["starttime", "endtime"]:
                self.fields[k].widget.attrs.update({"disabled": True})
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        result = super(I_TourFormJobneed, self).is_valid()
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
