"""
Shift Admin Module

Admin and import/export resources for Shift model management.

Migrated from apps/onboarding/admin.py
Date: 2025-09-30
"""
from .base import (
    BaseResource,
    BaseFieldSet2,
    admin,
    resources,
    fields,
    wg,
    ImportExportModelAdmin,
    tm,
    clean_point_field,
    clean_string,
    pm,
    BtForm,
    ShiftForm,
    Bt,
    Shift,
    TypeAssist,
    GeofenceMaster,
    Bu,
    get_or_create_none_typeassist,
    get_or_create_none_bv,
    get_or_create_none_people,
    utils,
    ValidationError,
    OperationalError,
    ProgrammingError,
    DatabaseError,
    re,
    isnan,
    EnabledTypeAssistWidget,
    bulk_create_geofence,
    Job,
)


class ShiftResource(resources.ModelResource):
    """Resource for importing and validating Shift data"""
    Client = fields.Field(
        column_name="Client",
        attribute="client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default="NONE",
    )
    BV = fields.Field(
        column_name="BV",
        attribute="bu",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        saves_null_values=True,
        default="NONE",
    )

    Name = fields.Field(attribute="shiftname", column_name="Shift Name")
    ID = fields.Field(attribute="id")
    StartTime = fields.Field(
        attribute="starttime", column_name="Start Time", widget=wg.TimeWidget()
    )
    EndTime = fields.Field(
        attribute="endtime", column_name="End Time", widget=wg.TimeWidget()
    )
    ShiftDuration = fields.Field(
        attribute="shiftduration", column_name="Shift Duration", widget=wg.TimeWidget()
    )
    IsNightShift = fields.Field(
        attribute="nightshiftappicable",
        column_name="Is Night Shift",
        widget=wg.BooleanWidget(),
    )
    Enable = fields.Field(attribute="enable", widget=wg.BooleanWidget())

    class Meta:
        model = om.Shift
        skip_unchanged = True
        # import_id_fields = ('ID',)
        report_skipped = True
        fields = (
            "ID",
            "Name",
            "ShiftDuration",
            "StartTime",
            "Client",
            "EndTime",
            "IsNightShift",
            "Enable",
            "BV",
        )


@admin.register(om.Shift)
class ShiftAdmin(ImportExportModelAdmin):
    list_per_page = 50
    """Django admin for Shift model with import/export functionality"""
    resource_class = ShiftResource
    form = ShiftForm
    fields = (
        "bu",
        "shiftname",
        "shiftduration",
        "starttime",
        "endtime",
        "nightshiftappicable",
        "captchafreq",
    )
    list_display = (
        "bu",
        "shiftname",
        "shiftduration",
        "starttime",
        "endtime",
        "nightshiftappicable",
    )
    list_display_links = ("shiftname",)
    list_select_related = ("bu", "client", "cuser", "muser", "tenant")
