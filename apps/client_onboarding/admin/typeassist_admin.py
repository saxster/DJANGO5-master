"""
TypeAssist Admin Module

Admin and import/export resources for TypeAssist model management.

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
from apps.core_onboarding import models as om


def clean_nan(value):
    """Clean NaN values from data imports"""
    if isinstance(value, float) and isnan(value):
        return None
    if isinstance(value, str) and value.strip().lower() in ["nan", "none", ""]:
        return None
    return value


class TaResource(resources.ModelResource):
    """
    Resource for importing and validating TypeAssist data.

    Ensures data integrity by cleaning, validating, and checking for uniqueness
    before saving imported data.
    """
    CLIENT = fields.Field(
        column_name="Client*",
        attribute="client",
        widget=wg.ForeignKeyWidget(Bt, "bucode"),
        default="NONE",
    )

    TYPE = fields.Field(
        column_name="Type*",
        attribute="tatype",
        default=om.TypeAssist,
        widget=wg.ForeignKeyWidget(om.TypeAssist, "tacode"),
        saves_null_values=True,
    )
    CODE = fields.Field(attribute="tacode", column_name="Code*")
    NAME = fields.Field(attribute="taname", column_name="Name*")

    class Meta:
        model = om.TypeAssist
        skip_unchanged = True
        import_id_fields = (
            "CODE",
            "TYPE",
            "CLIENT",
        )  # Use tacode as the unique identifier
        exclude = ("id",)
        report_skipped = True
        fields = ("NAME", "CODE", "TYPE", "CLIENT")

    def __init__(self, *args, **kwargs):
        super(TaResource, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number, **kwargs):
        """
        Clean and validate import data before processing.

        - Handles empty strings, removes extra spaces
        - Converts to uppercase and replaces spaces with underscores
        - Validates required fields
        - Checks code format using regex
        - Ensures uniqueness
        """
        row["Code*"] = clean_string(row.get("Code*", "NONE"), code=True)
        row["Name*"] = clean_string(row.get("Name*", "NONE"))

        # Validates that required fields (Code*, Type*, and Name*) are not empty.
        if row["Code*"] in ["", None]:
            raise ValidationError("Code* is required field")
        if row["Type*"] in ["", None]:
            raise ValidationError("Type* is required field")
        if row["Name*"] in ["", None]:
            raise ValidationError("Name* is required field")

        # Validates the format of the Code* field using a regular expression.
        # It ensures no spaces and only allows alphanumeric characters, underscores, and hyphens.
        regex, value = r"^[a-zA-Z0-9\-_]*$", row["Code*"]
        if re.search(r"\s|__", value):
            raise ValidationError("Please enter text without any spaces")
        if not re.match(regex, value):
            raise ValidationError(
                "Please enter valid text avoid any special characters except [_, -]"
            )

        # Checks for uniqueness of the record based on a combination of Code*, Type*,
        # and CLIENT* fields. It raises an error if a duplicate record is found.
        if (
            om.TypeAssist.objects.select_related()
            .filter(
                tacode=row["Code*"],
                tatype__tacode=row["Type*"],
                client__bucode=row["Client*"],
            )
            .exists()
        ):
            raise ValidationError(
                f"Record with these values already exist {', '.join(row.values())}"
            )

        super().before_import_row(row, **kwargs)

    def before_save_instance(self, instance, row, **kwargs):
        """
        Prepares instance before saving — sets cuser, muser, timestamps etc.
        """
        utils.save_common_stuff(self.request, instance, self.is_superuser)


class TaResourceUpdate(resources.ModelResource):
    """Resource for updating existing TypeAssist records via import"""
    CLIENT = fields.Field(
        column_name="Client",
        attribute="client",
        widget=wg.ForeignKeyWidget(Bt, "bucode"),
        default="NONE",
    )

    TYPE = fields.Field(
        column_name="Type",
        attribute="tatype",
        default=om.TypeAssist,
        widget=EnabledTypeAssistWidget(om.TypeAssist, "tacode"),
        saves_null_values=True,
    )

    CODE = fields.Field(attribute="tacode", column_name="Code")
    NAME = fields.Field(attribute="taname", column_name="Name")
    ID = fields.Field(attribute="id", column_name="ID*")

    class Meta:
        model = om.TypeAssist
        skip_unchanged = True
        # import_id_fields = ['ID']
        report_skipped = True
        fields = ("ID", "NAME", "CODE", "TYPE", "CLIENT")

    def __init__(self, *args, **kwargs):
        super(TaResourceUpdate, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number, **kwargs):
        """
        Clean and validate update data.

        - Handles empty strings, removes extra spaces
        - Validates required fields and format
        - Ensures record exists for update
        """
        if "Code" in row:
            row["Code"] = clean_string(row.get("Code"), code=True)
        if "Name" in row:
            row["Name"] = clean_string(row.get("Name"))

        # Validates that required fields (Code*, Type*, and Name*) are not empty.
        if "Code" in row:
            if row["Code"] in ["", None]:
                raise ValidationError("Code is required field")
        if "Type" in row:
            if row["Type"] in ["", None]:
                raise ValidationError("Type is required field")
        if "Name" in row:
            if row["Name"] in ["", None]:
                raise ValidationError("Name is required field")
        if row.get("ID*") in ["", "NONE", None] or (
            isinstance(row.get("ID*"), float) and isnan(row.get("ID*"))
        ):
            raise ValidationError({"ID*": "This field is required"})

        # Validates the format of the Code* field using a regular expression.
        # It ensures no spaces and only allows alphanumeric characters, underscores, and hyphens.
        if "Code" in row:
            regex, value = r"^[a-zA-Z0-9\-_]*$", row["Code"]
            if re.search(r"\s|__", value):
                raise ValidationError("Please enter text without any spaces")
            if not re.match(regex, value):
                raise ValidationError(
                    "Please enter valid text avoid any special characters except [_, -]"
                )

        # Check record exists
        if not om.TypeAssist.objects.filter(id=row["ID*"]).exists():
            raise ValidationError(
                f"Record with these values not exist: ID - {row['ID*']}"
            )

        super().before_import_row(row, **kwargs)

    def before_save_instance(self, instance, using_transactions, dry_run=False):
        """
        Inserts data into the instance object before saving it to
        the database of cuser, muser, cdtz, and mdtz fields.
        """
        utils.save_common_stuff(self.request, instance, self.is_superuser)


@admin.register(om.TypeAssist)
class TaAdmin(ImportExportModelAdmin):
    list_per_page = 50
    """Django admin for TypeAssist model with import/export functionality"""
    resource_class = TaResource
    list_display = (
        "id",
        "tacode",
        "tatype",
        "mdtz",
        "taname",
        "cuser",
        "muser",
        "cdtz",
        "bu",
        "client",
    )
    list_select_related = ("tatype", "cuser", "muser", "bu", "client", "tenant")

    def get_resource_kwargs(self, request, *args, **kwargs):
        return {"request": request}

    def get_queryset(self, request):
        return om.TypeAssist.objects.select_related(
            "tatype", "cuser", "muser", "bu", "client", "tenant"
        ).all()
