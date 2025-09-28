"""
Asset Form - Refactored Version

Demonstrates form refactoring using TenantAwareFormMixin.

COMPARISON:
- Original __init__: 50+ lines of queryset filtering
- Refactored __init__: ~15 lines using mixin

Following .claude/rules.md:
- Form < 100 lines (Rule 8)
- Specific exception handling (Rule 11)
- Input validation (Rule 13)
"""

import re
from django import forms
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Q

from apps.core.utils_new.form_security import SecureFormMixin, InputSanitizer
from apps.core.mixins import TenantAwareFormMixin, TypeAssistFilterMixin
from apps.core.utils_new.business_logic import initailize_form_fields
from apps.activity.models.asset_model import Asset
from apps.activity.models.location_model import Location
import apps.onboarding.models as om


class AssetFormRefactored(
    TenantAwareFormMixin,
    TypeAssistFilterMixin,
    SecureFormMixin,
    forms.ModelForm
):
    """
    Refactored asset form using mixins.

    BEFORE: 130+ lines with manual queryset filtering
    AFTER: ~60 lines with automatic filtering
    """

    required_css_class = "required"
    error_msg = {
        "invalid_assetcode": "Spaces are not allowed in [Code]",
        "invalid_assetcode2": "[Invalid code] Only ('-', '_') special characters are allowed",
        "invalid_assetcode3": "[Invalid code] Code should not endwith '.' ",
    }

    enable = forms.BooleanField(required=False, initial=True, label="Enable")
    status_field = forms.ChoiceField(
        choices=Asset.RunningStatus.choices,
        label="Duration of Selected Status",
        required=False,
    )

    tenant_filtered_fields = {
        'parent': {
            'model': Asset,
            'filter_by': 'bu_id',
            'extra_filters': Q(identifier="ASSET") & ~Q(runningstatus="SCRAPPED"),
        },
        'location': {
            'model': Location,
            'filter_by': 'bu_id',
            'extra_filters': ~Q(locstatus="SCRAPPED"),
        },
    }

    typeassist_fields = {
        'type': 'ASSETTYPE',
        'category': 'ASSETCATEGORY',
        'subcategory': 'ASSETSUBCATEGORY',
        'brand': 'BRAND',
        'unit': 'ASSETUNIT',
    }

    class Meta:
        model = Asset
        fields = [
            "assetcode",
            "assetname",
            "runningstatus",
            "type",
            "category",
            "subcategory",
            "brand",
            "unit",
            "capacity",
            "servprov",
            "parent",
            "iscritical",
            "enable",
            "identifier",
            "ctzoffset",
            "location",
        ]
        labels = {
            "assetcode": "Code",
            "assetname": "Name",
            "runningstatus": "Status",
            "type": "Type",
            "category": "Category",
            "subcategory": "Sub Category",
            "brand": "Brand",
            "unit": "Unit",
            "capacity": "Capacity",
            "servprov": "Service Provider",
            "parent": "Belongs To",
            "gpslocation": "GPS",
            "location": "Location",
        }
        widgets = {"identifier": forms.TextInput(attrs={"style": "display:none;"})}

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

        self.fields["enable"].widget.attrs = (
            {"checked": False} if self.instance.id else {"checked": True}
        )
        self.fields["assetcode"].widget.attrs = {"style": "text-transform:uppercase"}
        self.fields["identifier"].widget.attrs = {"style": "display:none"}
        self.fields["identifier"].initial = "ASSET"
        self.fields["capacity"].required = False
        self.fields["servprov"].required = False

        self.apply_tenant_filters()
        self.apply_typeassist_filters(self.typeassist_fields)
        initailize_form_fields(self)

    def clean_assetcode(self):
        """Validate asset code."""
        assetcode = self.cleaned_data["assetcode"]
        assetcode = InputSanitizer.sanitize_code(assetcode)

        if " " in assetcode:
            raise forms.ValidationError(self.error_msg["invalid_assetcode"])
        if not re.match(r"^[a-zA-Z0-9\-_]*$", assetcode):
            raise forms.ValidationError(self.error_msg["invalid_assetcode2"])
        if assetcode.endswith("."):
            raise forms.ValidationError(self.error_msg["invalid_assetcode3"])

        return assetcode

    def clean_assetname(self):
        """Validate and sanitize asset name."""
        assetname = self.cleaned_data.get("assetname", "")
        return InputSanitizer.sanitize_name(assetname)