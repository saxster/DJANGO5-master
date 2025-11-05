"""Scheduler child tour-related forms - Child form variants."""
from django.conf import settings
from django import forms
from apps.activity.forms.job_form import JobForm, JobNeedForm
from apps.activity.models.question_model import QuestionSet
import apps.peoples.models as pm
from apps.client_onboarding.models import Bt, Shift
from apps.core.utils_new.business_logic import initailize_form_fields
import logging

logger = logging.getLogger(__name__)


class SchdChild_I_TourJobForm(JobForm):
    """Scheduler Child Inherited Tour Job Form."""
    timeInChoices = [("MIN", "Min"), ("HRS", "Hours")]

    class Meta(JobForm.Meta):
        fields = ["qset", "people", "asset", "expirytime", "seqno"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        self.fields["seqno"].widget.attrs = {"readonly": True}
        self.fields[
            "qset"
        ].queryset = QuestionSet.objects.get_proper_checklist_for_scheduling(
            self.request, ["CHECKLIST", "QUESTIONSET"]
        )
        self.fields["asset"].queryset = Asset.objects.filter(
            identifier__in=["CHECKPOINT", "ASSET"],
            client_id=self.request.session["client_id"],
            enable=True,
        )
        initailize_form_fields(self)


class Child_I_TourFormJobneed(JobNeedForm):
    """Child Inherited Tour Job Need Form."""

    class Meta(JobNeedForm.Meta):
        fields = ["qset", "asset", "plandatetime", "expirydatetime", "gracetime"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["qset"].queryset = QuestionSet.objects.filter_for_dd_qset_field(
            self.request, ["CHECKLIST"], sitewise=True
        )
        self.fields["asset"].queryset = Asset.objects.filter_for_dd_asset_field(
            self.request, ["CHECKPOINT", "ASSET"], sitewise=True
        )
        initailize_form_fields(self)


class TaskFormJobneed(JobNeedForm):
    """Task Job Need Form - extends parent tour form."""

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["jobdesc"].required = True
        initailize_form_fields(self)
        if not self.instance.id:
            self.fields["asset"].queryset = Asset.objects.filter(
                identifier__in=["Asset", "Smartplace"]
            )
            self.fields["qset"].queryset = QuestionSet.objects.filter(
                type=["QUESTIONSET"]
            )
