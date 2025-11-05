"""Client onboarding preferences and capabilities configuration forms."""
from django import forms
from django.conf import settings
from django_select2 import forms as s2forms
from apps.core import utils
from apps.peoples.utils import create_caps_choices_for_clientform
from apps.core.utils_new.business_logic import initailize_form_fields


class BuPrefForm(forms.Form):
    """Business Unit preferences form - base form for site capabilities."""
    required_css_class = "required"

    mobilecapability = forms.MultipleChoiceField(
        required=False,
        label="Mobile Capability",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
    )
    webcapability = forms.MultipleChoiceField(
        required=False,
        label="Web Capability",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
    )
    reportcapability = forms.MultipleChoiceField(
        required=False,
        label="Report Capability",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
    )
    portletcapability = forms.MultipleChoiceField(
        required=False,
        label="Portlet Capability",
        widget=s2forms.Select2MultipleWidget(attrs={"data-theme": "bootstrap5"}),
    )
    validimei = forms.CharField(max_length=15, required=False, label="IMEI No.")
    validip = forms.CharField(max_length=15, required=False, label="IP Address")
    usereliver = forms.BooleanField(
        initial=False, required=False, label="Reliver needed?"
    )
    malestrength = forms.IntegerField(initial=0, label="Male Strength")
    femalestrength = forms.IntegerField(initial=0, label="Female Strength")
    reliveronpeoplecount = forms.IntegerField(
        initial=0, label="Reliver On People Count", required=False
    )
    pvideolength = forms.IntegerField(
        initial=10, label="Panic Video Length (sec)", required=False
    )
    guardstrenth = forms.IntegerField(initial=0)
    siteclosetime = forms.TimeField(label="Site Close Time", required=False)
    tag = forms.CharField(max_length=200, required=False)
    siteopentime = forms.TimeField(required=False, label="Site Open Time")
    nearby_emergencycontacts = forms.CharField(max_length=500, required=False)
    ispermitneeded = forms.BooleanField(initial=False, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        result = super().is_valid()
        for x in self.fields if "__all__" in self.errors else self.errors:
            attrs = self.fields[x].widget.attrs
            attrs.update({"class": attrs.get("class", "") + " is-invalid"})
        return result


class ClientForm(BuPrefForm):
    """Extended client configuration form with billing and licensing."""
    BILLINGTYPES = [
        ("", ""),
        ("SITEBASED", "Site Based"),
        ("LICENSEBASED", "Liscence Based"),
        ("USERBASED", "User Based"),
    ]
    femalestrength = None
    guardstrenth = None
    malestrength = None
    startdate = forms.DateField(
        label="Start Date",
        required=True,
        input_formats=settings.DATE_INPUT_FORMATS,
        widget=forms.DateInput,
    )
    enddate = forms.DateField(
        label="End Date",
        required=True,
        input_formats=settings.DATE_INPUT_FORMATS,
        widget=forms.DateInput,
    )
    onstop = forms.BooleanField(label="On Stop", required=False, initial=False)
    onstopmessage = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 1}),
        label="On Stop Message",
        required=False,
    )
    clienttimezone = forms.ChoiceField(
        label="Time Zone",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        choices=[],
        required=False,
    )
    billingtype = forms.ChoiceField(
        label="Billing Type",
        widget=s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
        choices=BILLINGTYPES,
        initial="SITEBASED",
        required=False,
    )
    no_of_devices_allowed = forms.IntegerField(
        label="No of Devices Allowed", required=False, initial=0
    )
    devices_currently_added = forms.IntegerField(
        label="No of Devices Currently Added", required=False, initial=0
    )
    no_of_users_allowed_mob = forms.IntegerField(
        label="No of Users Allowed For Mobile", required=False, initial=0
    )
    no_of_users_allowed_web = forms.IntegerField(
        label="No of Users Allowed For Web", required=False, initial=0
    )
    no_of_users_allowed_both = forms.IntegerField(
        label="No of Users Allowed For Both", required=False, initial=0
    )

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        initailize_form_fields(self)
        web, mob, portlet, report = create_caps_choices_for_clientform()
        self.fields["webcapability"].choices = web
        self.fields["mobilecapability"].choices = mob
        self.fields["reportcapability"].choices = report
        self.fields["portletcapability"].choices = portlet

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("usereliver")
            and cleaned_data.get("reliveronpeoplecount") <= 0
        ):
            self.add_error(
                "reliveronpeoplecount",
                "Reliver on people count should be greater than 0",
            )

    def clean_validip(self):
        if val := self.cleaned_data.get("validip"):
            text = val.split(".")
            if len(text) != 4:
                raise forms.ValidationError("Invalid IP Address")
        return val

    def clean_validimei(self):
        if val := self.cleaned_data.get("validimei"):
            if not utils.isValidEMEI(val):
                raise forms.ValidationError("Invalid IMEI No.")
        return val

    def is_valid(self) -> bool:
        result = super().is_valid()
        utils.apply_error_classes(self)
        return result
