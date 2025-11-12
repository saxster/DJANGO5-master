"""Client onboarding type definition forms."""
from django import forms
from django.db.models.query_utils import Q
from apps.core import utils
from django_select2 import forms as s2forms
import re

from ..models import TypeAssist
from apps.core.utils_new.business_logic import initailize_form_fields


class SuperTypeAssistForm(forms.ModelForm):
    """Base form for TypeAssist model with common validation."""
    required_css_class = "required"
    error_msg = {
        "invalid_code": "(Spaces are not allowed in [Code]",
        "invalid_code2": "[Invalid code] Only ('-', '_') special characters are allowed",
        "invalid_code3": "[Invalid code] Code should not endwith '.' ",
    }

    class Meta:
        model = TypeAssist
        fields = ["tacode", "taname", "tatype", "ctzoffset", "enable"]
        labels = {
            "tacode": "Code",
            "taname": "Name",
            "tatype": "Type",
            "enable": "Enable",
        }
        widgets = {
            "tatype": s2forms.Select2Widget(attrs={"data-theme": "bootstrap5"}),
            "tacode": forms.TextInput(
                attrs={
                    "placeholder": "Enter code without space and special characters",
                    "style": "text-transform: uppercase;",
                }
            ),
            "taname": forms.TextInput(attrs={"placeholder": "Enter name"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super(SuperTypeAssistForm, self).__init__(*args, **kwargs)
        initailize_form_fields(self)
        self.fields["enable"].initial = True

    def is_valid(self) -> bool:
        result = super().is_valid()
        utils.apply_error_classes(self)
        return result

    def clean_tatype(self):
        return self.cleaned_data.get("tatype")

    def clean_tacode(self):
        value = self.cleaned_data.get("tacode")
        regex = r"^[a-zA-Z0-9\-_()#]*$"
        if " " in value:
            raise forms.ValidationError(self.error_msg["invalid_code"])
        if not re.match(regex, value):
            raise forms.ValidationError(self.error_msg["invalid_code2"])
        if value.endswith("."):
            raise forms.ValidationError(self.error_msg["invalid_code3"])
        return value.upper()


class TypeAssistForm(SuperTypeAssistForm):
    """Extended TypeAssist form for client-specific types."""
    required_css_class = "required"

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        S = self.request.session
        super().__init__(*args, **kwargs)
        self.fields["enable"].initial = True
        self.fields["tatype"].queryset = TypeAssist.objects.filter(
            (Q(cuser__is_superuser=True) | Q(client_id__in=[S["client_id"], 1])),
            enable=True,
        )
        initailize_form_fields(self)

    def is_valid(self) -> bool:
        result = super().is_valid()
        utils.apply_error_classes(self)
        return result

    def clean(self):
        super().clean()

    def clean_tacode(self):
        super().clean_tacode()
        if val := self.cleaned_data.get("tacode"):
            val = val.upper()
            if len(val) > 25:
                raise forms.ValidationError("Max Length reached!!")
        return val
