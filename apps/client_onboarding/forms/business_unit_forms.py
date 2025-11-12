"""Client onboarding business unit (Bt) forms."""
from django import forms
from django.db.models.query_utils import Q
from apps.core import utils
from django_select2 import forms as s2forms
from django.contrib.gis.geos import GEOSGeometry
from django.http import QueryDict
import re
import json

from ..models import Bt, TypeAssist
from apps.peoples import models as pm
from .type_forms import TypeAssistForm
from apps.core.utils_new.business_logic import initailize_form_fields


class BtForm(forms.ModelForm):
    """Business Unit (Site/Building) creation and management form."""
    required_css_class = "required"
    error_msg = {
        "invalid_bucode": "Spaces are not allowed in [Code]",
        "invalid_bucode2": "[Invalid code] Only ('-', '_') special characters are allowed",
        "invalid_bucode3": "[Invalid code] Code should not endwith '.' ",
        "invalid_latlng": "Please enter a correct gps coordinates.",
        "invalid_permissibledistance": "Please enter a correct value for Permissible Distance",
        "invalid_solid": "Please enter a correct value for Sol id",
        "invalid_name": "[Invalid text] Only these special characters [-, _, @, #, . , &] are allowed in name field",
    }
    parent = forms.ModelChoiceField(
        label="Belongs to",
        required=False,
        queryset=Bt.objects.none()
    )
    controlroom = forms.MultipleChoiceField(required=False, label="Control Room")
    permissibledistance = forms.IntegerField(
        required=False, label="Permissible Distance"
    )
    address = forms.CharField(required=False, label="Address", max_length=500)
    total_people_count = forms.IntegerField(
        required=False, min_value=0, label="Total People Count"
    )
    designation = forms.ModelChoiceField(
        label="Desigantion",
        required=False,
        queryset=TypeAssist.objects.none()
    )
    designation_count = forms.IntegerField(
        required=False, min_value=0, label="Designation Count"
    )
    posted_people = forms.MultipleChoiceField(
        label="Posted People",
        required=False,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select Posted People",
                "data-theme": "bootstrap5",
            }
        ),
    )
    jsonData = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Bt
        fields = [
            "bucode",
            "buname",
            "parent",
            "butype",
            "identifier",
            "siteincharge",
            "iswarehouse",
            "isserviceprovider",
            "isvendor",
            "enable",
            "ctzoffset",
            "gpsenable",
            "skipsiteaudit",
            "enablesleepingguard",
            "deviceevent",
            "solid",
        ]
        labels = {
            "bucode": "Code",
            "buname": "Name",
            "butype": "Site Type",
            "identifier": "Type",
            "iswarehouse": "Warehouse",
            "isenable": "Enable",
            "isvendor": "Vendor",
            "isserviceprovider": "Service Provider",
            "gpsenable": "GPS Enable",
            "skipsiteaudit": "Skip Site Audit",
            "enablesleepingguard": "Enable Sleeping Guard",
            "deviceevent": "Device Event Log",
            "solid": "Sol Id",
            "siteincharge": "Site Manager",
        }
        widgets = {
            "bucode": forms.TextInput(
                attrs={
                    "style": "text-transform:uppercase;",
                    "placeholder": "Enter text without space & special characters",
                }
            ),
            "buname": forms.TextInput(attrs={"placeholder": "Name"}),
        }

    def __init__(self, *args, **kwargs):
        self.client = kwargs.pop("client", False)
        self.request = kwargs.pop("request", False)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["parent"].widget = s2forms.Select2Widget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["controlroom"].widget = s2forms.Select2MultipleWidget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["address"].widget = forms.Textarea(attrs={"rows": 2, "cols": 15})
        self.fields["designation"].widget = s2forms.Select2Widget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["identifier"].widget = s2forms.Select2Widget(
            attrs={
                "class": "form-select form-select-solid",
                "data-placeholder": "Select an option",
                "data-theme": "bootstrap5",
            }
        )
        self.fields["butype"].widget = s2forms.Select2Widget(
            attrs={
                "data-placeholder": "Select an Option",
                "class": "form-select-solid",
                "data-theme": "bootstrap5",
            }
        )

        if self.client:
            self.fields["identifier"].initial = TypeAssist.objects.get(
                tacode="CLIENT"
            ).id
            self.fields["identifier"].required = True

        self.fields["siteincharge"].initial = 1
        self.fields["identifier"].queryset = TypeAssist.objects.filter(
            Q(tacode="CLIENT") if self.client else Q(tatype__tacode="BVIDENTIFIER")
        )
        self.fields["butype"].queryset = TypeAssist.objects.filter(
            tatype__tacode="SITETYPE", client_id=S["client_id"]
        )
        qset = Bt.objects.get_whole_tree(self.request.session["client_id"])
        self.fields["parent"].queryset = Bt.objects.filter(id__in=qset)
        self.fields["controlroom"].choices = pm.People.objects.controlroomchoices(
            self.request
        )
        self.fields[
            "posted_people"
        ].choices = pm.People.objects.get_people_for_posted_ppl_on_bu(self.request)
        self.fields["siteincharge"].queryset = pm.People.objects.filter(
            Q(peoplecode="NONE")
            | (Q(client_id=self.request.session["client_id"]) & Q(enable=True))
        )
        self.fields["designation"].queryset = TypeAssist.objects.filter(
            Q(bu_id__in=[S["bu_id"], 1])
            | Q(bu_id__in=S["assignedsites"])
            | Q(bu_id__isnull=True),
            Q(client_id__in=[S["client_id"], 1]),
            Q(tatype__tacode="DESIGNATION"),
        )
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        result = super().is_valid()
        utils.apply_error_classes(self)
        return result

    def clean(self):
        super().clean()
        from ..utils import create_bv_reportting_heirarchy
        from django.utils import timezone
        from datetime import timedelta

        newcode = self.cleaned_data.get("bucode")
        newtype = self.cleaned_data.get("identifier")
        parent = self.cleaned_data.get("parent")
        instance = self.instance

        if not instance.pk and newcode and newtype and parent:
            recent_cutoff = timezone.now() - timedelta(minutes=2)
            existing = Bt.objects.filter(
                bucode=newcode,
                parent=parent,
                identifier=newtype,
                cdtz__gte=recent_cutoff
            ).first()

            if existing:
                self.existing_record_id = existing.id

        if newcode and newtype and instance:
            create_bv_reportting_heirarchy(instance, newcode, newtype, parent)
        if self.cleaned_data.get("gpslocation"):
            data = QueryDict(self.request.POST["formData"])
            self.cleaned_data["gpslocation"] = self.clean_gpslocation(
                data.get("gpslocation", "NONE")
            )
        if self.request.POST.get("jsonData"):
            json_data = self.request.POST.get("jsonData")
            self.cleaned_data["jsonData"] = json.loads(json_data)
        return self.cleaned_data

    def clean_bucode(self):
        self.cleaned_data["gpslocation"] = self.data.get("gpslocation")
        if value := self.cleaned_data.get("bucode"):
            regex = r"^[a-zA-Z0-9\-_#()]*$"
            if " " in value:
                raise forms.ValidationError(self.error_msg["invalid_bucode"])
            if not re.match(regex, value):
                raise forms.ValidationError(self.error_msg["invalid_bucode2"])
            if value.endswith("."):
                raise forms.ValidationError(self.error_msg["invalid_bucode3"])
            return value.upper()

    def clean_gpslocation(self, val):
        if gps := val:
            if gps == "NONE":
                return GEOSGeometry(f"SRID=4326;POINT({0.0} {0.0})")
            regex = r"^([-+]?)([\d]{1,2})(((\.)(\d+)(,)))(\s*)(([-+]?)([\d]{1,3})((\.)(\d+))?)$"
            gps = gps.replace("(", "").replace(")", "")
            if not re.match(regex, gps):
                raise forms.ValidationError(self.error_msg["invalid_latlng"])
            gps.replace(" ", "")
            lat, lng = gps.split(",")
            gps = GEOSGeometry(f"SRID=4326;POINT({lng} {lat})")
        return gps

    def clean_permissibledistance(self):
        if val := self.cleaned_data.get("permissibledistance"):
            regex = "^[0-9]*$"
            if not re.match(regex, str(val)):
                raise forms.ValidationError(
                    self.error_msg["invalid_permissibledistance"]
                )
            if val < 0:
                raise forms.ValidationError(
                    self.error_msg["invalid_permissibledistance"]
                )
        return val

    def clean_solid(self):
        if val := self.cleaned_data.get("solid"):
            regex = "^[a-zA-Z0-9]*$"
            if not re.match(regex, str(val)):
                raise forms.ValidationError(self.error_msg["invalid_solid"])
        return val

    def clean_buname(self):
        if value := self.cleaned_data.get("buname"):
            regex = r"^[a-zA-Z0-9\-_@#.,\(\|\)& ]*$"
            if not re.match(regex, value):
                raise forms.ValidationError(self.error_msg["invalid_name"])
        return value
