"""Client onboarding shift and geofence configuration forms."""
from django import forms
from django.db.models.query_utils import Q
from django_select2 import forms as s2forms
import re

from ..models import TypeAssist
from apps.core_onboarding import models as obm
from apps.core.utils_new.business_logic import initailize_form_fields


class ShiftForm(forms.ModelForm):
    """Shift configuration form for duty scheduling."""
    required_css_class = "required"
    error_msg = {
        "invalid_code": "Spaces are not allowed in [Code]",
        "invalid_code2": "[Invalid code] Only ('-', '_') special characters are allowed",
        "invalid_code3": "[Invalid code] Code should not endwith '.' ",
        "max_hrs_exceed": "Maximum hours in a shift cannot be greater than 12hrs",
        "min_hrs_required": "Minimum hours of a shift should be greater than 4hrs",
        "invalid_overtime": "Overtime hours cannot exceed regular shift duration",
    }
    shiftduration = forms.CharField(
        widget=forms.TextInput(attrs={"readonly": True}),
        label="Duration",
        required=False,
    )
    overtime = forms.IntegerField(
        required=False,
        min_value=0,
        label="Overtime (hours)",
        widget=forms.NumberInput(attrs={"placeholder": "Enter overtime hours"}),
    )
    peoplecount = forms.IntegerField(
        required=True,
        min_value=1,
        label="People Count",
        widget=forms.NumberInput(attrs={"placeholder": "Enter people count"}),
    )

    class Meta:
        model = obm.Shift
        fields = [
            "shiftname",
            "starttime",
            "endtime",
            "ctzoffset",
            "nightshiftappicable",
            "shiftduration",
            "designation",
            "captchafreq",
            "peoplecount",
            "shift_data",
            "overtime",
        ]
        labels = {
            "shiftname": "Shift Name",
            "starttime": "Start Time",
            "endtime": "End Time",
            "captchafreq": "Captcha Frequency",
            "designation": "Designation",
            "peoplecount": "People Count",
            "shift_data": "Shift Data",
            "overtime": "Overtime Hours",
        }
        widgets = {
            "shiftname": forms.TextInput(attrs={"placeholder": "Enter shift name"}),
            "nightshiftappicable": forms.CheckboxInput(
                attrs={"onclick": "return false"}
            ),
            "designation": s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
            "overtime": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def clean_overtime(self):
        overtime = self.cleaned_data.get("overtime")
        shiftduration = self.cleaned_data.get("shiftduration")

        if overtime and shiftduration:
            if overtime > (shiftduration / 60):
                raise forms.ValidationError(self.error_msg["invalid_overtime"])
        return overtime

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["nightshiftappicable"].initial = False
        self.fields["designation"].queryset = TypeAssist.objects.filter(
            Q(bu_id__in=[S["bu_id"], 1])
            | Q(bu_id__in=S["assignedsites"])
            | Q(bu_id__isnull=True),
            Q(client_id__in=[S["client_id"], 1]),
            Q(tatype__tacode="DESIGNATION"),
        )
        self.fields["designation"].widget = forms.Select(
            choices=[
                (item.tacode, item.taname)
                for item in self.fields["designation"].queryset
            ]
        )
        initailize_form_fields(self)

    def clean_shiftname(self):
        if val := self.cleaned_data.get("shiftname"):
            return val

    def clean_shiftduration(self):
        if val := self.cleaned_data.get("shiftduration"):
            h, m = val.split(",")
            hrs = int(h.replace("Hrs", ""))
            mins = int(m.replace("min", ""))
            if hrs > 12:
                raise forms.ValidationError(self.error_msg["max_hrs_exceed"])
            if hrs < 5:
                raise forms.ValidationError(self.error_msg["min_hrs_required"])
            return hrs * 60 + mins

    def is_valid(self) -> bool:
        result = super().is_valid()
        for x in self.fields if "__all__" in self.errors else self.errors:
            attrs = self.fields[x].widget.attrs
            attrs.update({"class": attrs.get("class", "") + " is-invalid"})
        return result


class GeoFenceForm(forms.ModelForm):
    """Geofence boundary configuration form."""
    required_css_class = "required"

    class Meta:
        model = obm.GeofenceMaster
        fields = [
            "gfcode",
            "gfname",
            "alerttopeople",
            "bu",
            "alerttogroup",
            "alerttext",
            "enable",
            "ctzoffset",
        ]
        labels = {
            "gfcode": "Code",
            "gfname": "Name",
            "alerttopeople": "Alert to People",
            "alerttogroup": "Alert to Group",
            "alerttext": "Alert Text",
        }
        widgets = {
            "gfcode": forms.TextInput(
                attrs={
                    "style": "text-transform:uppercase;",
                    "placeholder": "Enter text without space & special characters",
                }
            )
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        self.fields["alerttogroup"].required = True
        self.fields["bu"].queryset = obm.Bt.objects.filter(
            id__in=self.request.session["assignedsites"]
        )
        self.fields["alerttopeople"].required = True
        self.fields["alerttext"].required = True
        self.fields["bu"].required = False
        initailize_form_fields(self)

    def clean_gfcode(self):
        return val.upper() if (val := self.cleaned_data.get("gfcode")) else val
