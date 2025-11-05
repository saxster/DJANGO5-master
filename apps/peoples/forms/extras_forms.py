"""Forms for user extras and capabilities configuration."""

from django import forms
from django_select2 import forms as s2forms

import apps.peoples.models as pm
from apps.activity.models.question_model import QuestionSet
from apps.client_onboarding.models import Bt
from apps.peoples.utils import create_caps_choices_for_peopleform
from apps.core.utils_new.business_logic import (
    apply_error_classes,
    initailize_form_fields,
)


class PeopleExtrasForm(forms.Form):
    """Form for configuring user capabilities and access preferences."""

    labels = {
        "mob": "Mobile Capability",
        "port": "Portlet Capability",
        "report": "Report Capability",
        "web": "Web Capability",
        "noc": "NOC Capability",
    }

    USERFOR_CHOICES = [
        ("Mobile", "Mobile"),
        ("Web", "Web"),
        ("Both", "Both"),
    ]

    andriodversion = forms.CharField(
        max_length=2, required=False, label="Andriod Version"
    )
    appversion = forms.CharField(max_length=8, required=False, label="App Version")
    mobilecapability = forms.MultipleChoiceField(required=False, label=labels["mob"])
    portletcapability = forms.MultipleChoiceField(required=False, label=labels["port"])
    reportcapability = forms.MultipleChoiceField(required=False, label=labels["report"])
    webcapability = forms.MultipleChoiceField(required=False, label=labels["web"])
    noccapability = forms.MultipleChoiceField(
        required=False, label=labels["noc"], widget=s2forms.Select2MultipleWidget
    )
    loacationtracking = forms.BooleanField(initial=False, required=False)
    capturemlog = forms.BooleanField(initial=False, required=False)
    showalltemplates = forms.BooleanField(
        initial=False, required=False, label="Show all Templates "
    )
    debug = forms.BooleanField(initial=False, required=False)
    showtemplatebasedonfilter = forms.BooleanField(
        initial=False, required=False, label="Display site wise templates"
    )
    blacklist = forms.BooleanField(initial=False, required=False)
    alertmails = forms.BooleanField(initial=False, label="Alert Mails", required=False)
    isemergencycontact = forms.BooleanField(
        initial=False, label="Emergency Contact", required=False
    )
    assignsitegroup = forms.MultipleChoiceField(required=False, label="Site Group")
    tempincludes = forms.MultipleChoiceField(required=False, label="Template")
    mlogsendsto = forms.CharField(max_length=25, required=False)
    currentaddress = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2, "cols": 15})
    )
    permanentaddress = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2, "cols": 15})
    )
    userfor = forms.ChoiceField(
        required=True, choices=USERFOR_CHOICES, label="User For",
        initial="Both"
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        S = self.request.session
        super().__init__(*args, **kwargs)
        self._setup_capability_widgets()
        self._setup_capability_choices(S)
        initailize_form_fields(self)

    def _setup_capability_widgets(self):
        """Configure Select2 widgets for all capability fields."""
        for field in [
            "mobilecapability",
            "tempincludes",
            "assignsitegroup",
            "portletcapability",
            "reportcapability",
            "noccapability",
            "webcapability",
        ]:
            self.fields[field].widget = s2forms.Select2MultipleWidget(
                attrs={
                    "class": "form-select form-select-solid",
                    "data-placeholder": "Select an option",
                    "data-theme": "bootstrap5",
                }
            )

    def _setup_capability_choices(self, session):
        """Populate capability field choices."""
        self.fields["assignsitegroup"].choices = pm.Pgroup.objects.get_assignedsitegroup_forclient(
            session["client_id"], self.request
        )
        self.fields["tempincludes"].choices = QuestionSet.objects.filter(
            type="SITEREPORT", bu_id__in=session["assignedsites"]
        ).values_list("id", "qsetname")

        web, mob, portlet, report, noc = create_caps_choices_for_peopleform(
            self.request.user.client
        )

        if not session["is_superadmin"]:
            self.fields["webcapability"].choices = session.get("client_webcaps") or web
            self.fields["mobilecapability"].choices = session.get("client_mobcaps") or mob
            self.fields["portletcapability"].choices = session.get("client_portletcaps") or portlet
            self.fields["reportcapability"].choices = session.get("client_reportcaps") or report
            self.fields["noccapability"].choices = session.get("client_noccaps") or noc
        else:
            from apps.peoples.utils import get_caps_choices
            self.fields["webcapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.WEB
            )
            self.fields["mobilecapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.MOB
            )
            self.fields["portletcapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.PORTLET
            )
            self.fields["reportcapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.REPORT
            )
            self.fields["noccapability"].choices = get_caps_choices(
                cfor=pm.Capability.Cfor.NOC
            )

    def is_valid(self) -> bool:
        """Add class to invalid fields"""
        result = super().is_valid()
        apply_error_classes(self)
        return result

    def clean(self):
        cd = super().clean()
        if cd.get("userfor") and cd["userfor"] != "":
            client = Bt.objects.filter(id=self.request.session["client_id"]).first()
            preferences = client.bupreferences
            if preferences["billingtype"] == "USERBASED":
                current_ppl_count = pm.People.objects.filter(
                    client=client, people_extras__userfor=cd["userfor"]
                ).count()
                mapping = {
                    "Mobile": "no_of_users_allowed_mob",
                    "Both": "no_of_users_allowed_both",
                    "Web": "no_of_users_allowed_web",
                }
                parameter = mapping.get(cd["userfor"])
                allowed_count = preferences[parameter]
                if allowed_count and current_ppl_count + 1 > int(allowed_count):
                    raise forms.ValidationError(
                        f'{cd["userfor"]} users limit exceeded {allowed_count} and curent people count is {current_ppl_count}'
                    )
        return cd
