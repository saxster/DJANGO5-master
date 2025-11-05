"""
Business Unit Admin Module

Admin and import/export resources for Business Unit (Bt) model management.
Handles sites, customers, and organizational hierarchy.

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


class BtResource(resources.ModelResource):
    """
    Resource for importing and validating Business Unit data.

    Handles complex data import including GPS location, addresses, control room
    assignments, and cache management.
    """
    BelongsTo = fields.Field(
        column_name="Belongs To*",
        default=get_or_create_none_bv,
        attribute="parent",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
    )

    BuType = fields.Field(
        column_name="Site Type",
        default=default_ta,
        attribute="butype",
        widget=wg.ForeignKeyWidget(om.TypeAssist, "tacode"),
    )

    Identifier = fields.Field(
        column_name="Type*",
        attribute="identifier",
        default=default_ta,
        widget=wg.ForeignKeyWidget(om.TypeAssist, "tacode"),
    )

    Sitemanager = fields.Field(
        column_name="Site Manager*",
        attribute="siteincharge",
        default=get_or_create_none_people,
        widget=wg.ForeignKeyWidget(pm.People, "peoplecode"),
    )

    Code = fields.Field(attribute="bucode", column_name="Code*")
    Name = fields.Field(attribute="buname", column_name="Name*")
    GPS = fields.Field(
        attribute="gpslocation", column_name="GPS Location", saves_null_values=True
    )
    Address = fields.Field(
        column_name="Address", widget=wg.CharWidget(), saves_null_values=True
    )
    State = fields.Field(
        column_name="State", widget=wg.CharWidget(), saves_null_values=True
    )
    City = fields.Field(
        column_name="City", widget=wg.CharWidget(), saves_null_values=True
    )
    Country = fields.Field(
        column_name="Country", widget=wg.CharWidget(), saves_null_values=True
    )
    SOLID = fields.Field(
        attribute="solid", column_name="Sol Id", widget=wg.CharWidget()
    )
    Enable = fields.Field(attribute="enable", column_name="Enable", default=True)

    class Meta:
        model = om.Bt
        skip_unchanged = True
        report_skipped = True
        import_id_fields = ("Code",)
        fields = (
            "Name",
            "Code",
            "BuType",
            "SOLID",
            "Enable",
            "GPS",
            "Address",
            "State",
            "City",
            "Country",
            "Identifier",
            "BelongsTo",
            "Sitemanager",
        )

    def __init__(self, *args, **kwargs):
        super(BtResource, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, **kwargs):
        """
        Clean and validate import data before processing.

        Handles:
        - Code and name cleaning
        - GPS location parsing
        - Control room assignments
        - Permissible distance validation
        - Required field checks
        - Code format validation
        - Uniqueness checks
        """
        row["Code*"] = clean_string(row.get("Code*", "NONE"), code=True)
        row["Name*"] = clean_string(row.get("Name*", "NONE"))
        self._gpslocation = clean_point_field(row["GPS Location"])
        self._solid = clean_nan(row["Sol Id"])
        self._address = clean_nan(row["Address"])
        self._state = clean_nan(row["State"])
        self._city = clean_nan(row["City"])
        self._country = clean_nan(row["Country"])
        self._latlng = clean_nan(row["GPS Location"])
        if row["Control Room"]:
            control_room_list = (
                row["Control Room"].strip("[]").replace("'", "").split(", ")
            )
        else:
            control_room_list = []
        from django.db.models import Q

        control_id_list = list(
            pm.People.objects.filter(
                Q(Q(designation__tacode__in=["CR"]) | Q(worktype__tacode__in=["CR"])),
                enable=True,
                peoplecode__in=control_room_list,
            ).values_list("id", flat=True)
        )
        control_id_list = [str(id) for id in control_id_list]
        self._controlroom = control_id_list
        pdist_val = clean_nan(row["Permissible Distance"])
        if pdist_val not in [None, ""]:
            try:
                pdist_val = float(pdist_val)
            except (TypeError, ValueError):
                raise ValidationError("Permissible Distance must be a number")
            if pdist_val < 0:
                raise ValidationError(
                    "Permissible Distance is greater than or equal to zero"
                )
        self._permissibledistance = pdist_val
        # check required fields
        if row["Code*"] in ["", None]:
            raise ValidationError("Code* is required field")
        if row["Type*"] in ["", None]:
            raise ValidationError("Type* is required field")
        if row["Name*"] in ["", None]:
            raise ValidationError("Name* is required field")
        if row["Belongs To*"] in ["", None]:
            raise ValidationError("Belongs To* is required field")
        # code validation
        regex, value = r"^[a-zA-Z0-9\-_]*$", row["Code*"]
        if re.search(r"\s|__", value):
            raise ValidationError("Please enter text without any spaces")
        if not re.match(regex, value):
            raise ValidationError(
                "Please enter valid text avoid any special characters except [_, -]"
            )

        # unique record check
        if (
            om.Bt.objects.select_related()
            .filter(
                bucode=row["Code*"],
                parent__bucode=row["Belongs To*"],
                identifier__tacode=row["Type*"],
            )
            .exists()
        ):
            raise ValidationError(
                f"Record with these values already exist {row.values()}"
            )

        super().before_import_row(row, **kwargs)

    def before_save_instance(self, instance, row, **kwargs):
        """Set GPS location and preferences before saving"""
        instance.gpslocation = self._gpslocation
        instance.bupreferences["address"] = self._address
        instance.bupreferences["controlroom"] = self._controlroom
        instance.bupreferences["permissibledistance"] = self._permissibledistance
        instance.bupreferences["address2"] = {
            "city": self._city,
            "country": self._country,
            "state": self._state,
            "formattedAddress": self._address,
            "latlng": self._latlng,
        }
        if self._solid and not (isinstance(self._solid, float) and isnan(self._solid)):
            instance.solid = int(self._solid)
        else:
            instance.solid = None

        utils.save_common_stuff(self.request, instance)

    def get_queryset(self):
        return om.Bt.objects.select_related().all()

    def after_import(self, dataset, result, using_transactions, dry_run, **kwargs):
        """
        Clear cache after bulk import of BUs.

        Clears all BU-related cache patterns to ensure data consistency
        after bulk operations.
        """
        if not dry_run:
            from django.core.cache import cache
            import logging

            logger = logging.getLogger(__name__)

            # Clear all BU-related cache patterns
            # Since we don't know which specific BUs were affected,
            # we'll clear cache for common patterns
            cache_patterns = []

            # Get all unique parent IDs from imported data
            parent_ids = set()
            for row in dataset.dict:
                if 'Belongs To*' in row and row['Belongs To*']:
                    # Try to find the parent BU
                    try:
                        parent_bu = om.Bt.objects.filter(bucode=row['Belongs To*']).first()
                        if parent_bu:
                            parent_ids.add(parent_bu.id)
                    except (OperationalError, ProgrammingError, DatabaseError) as e:
                        logger.warning(f"Database error looking up parent BU '{row.get('Belongs To*', 'N/A')}': {e}")
                    except (KeyError, AttributeError) as e:
                        logger.warning(f"Data access error looking up parent BU: {e}")
                    except Exception as e:
                        logger.exception(f"Unexpected error looking up parent BU '{row.get('Belongs To*', 'N/A')}': {e}")

            # Clear cache for all affected parent BUs
            for parent_id in parent_ids:
                for include_parents in [True, False]:
                    for include_children in [True, False]:
                        for return_type in ['array', 'text', 'jsonb']:
                            cache_key = f"bulist_{parent_id}_{include_parents}_{include_children}_{return_type}"
                            cache.delete(cache_key)

                # Also clear idnf cache patterns
                for include_customers in [True, False]:
                    for include_sites in [True, False]:
                        cache_key = f"bulist_idnf_{parent_id}_{include_customers}_{include_sites}"
                        cache.delete(cache_key)

            logger.info(f"Cache cleared after bulk import of {result.total_rows} BUs")


class BtResourceUpdate(resources.ModelResource):
    """Resource for updating existing Business Unit records via import"""
    BelongsTo = fields.Field(
        column_name="Belongs To",
        default=get_or_create_none_bv,
        attribute="parent",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
    )

    BuType = fields.Field(
        column_name="Site Type",
        default=default_ta,
        attribute="butype",
        widget=wg.ForeignKeyWidget(om.TypeAssist, "tacode"),
    )

    Identifier = fields.Field(
        column_name="Type",
        attribute="identifier",
        default=default_ta,
        widget=wg.ForeignKeyWidget(om.TypeAssist, "tacode"),
    )

    Sitemanager = fields.Field(
        column_name="Site Manager",
        attribute="siteincharge",
        default=get_or_create_none_people,
        widget=wg.ForeignKeyWidget(pm.People, "peoplecode"),
    )

    ID = fields.Field(attribute="id", column_name="ID*")
    Code = fields.Field(attribute="bucode", column_name="Code")
    Name = fields.Field(attribute="buname", column_name="Name")
    GPS = fields.Field(
        attribute="gpslocation", column_name="GPS Location", saves_null_values=True
    )
    Address = fields.Field(
        column_name="Address",
        attribute="bupreferences.address",
        widget=wg.CharWidget(),
        saves_null_values=True,
    )
    State = fields.Field(
        column_name="State",
        attribute="bupreferences.address2.state",
        widget=wg.CharWidget(),
        saves_null_values=True,
    )
    City = fields.Field(
        column_name="City",
        attribute="bupreferences.address2.city",
        widget=wg.CharWidget(),
        saves_null_values=True,
    )
    Country = fields.Field(
        column_name="Country",
        attribute="bupreferences.address2.country",
        widget=wg.CharWidget(),
        saves_null_values=True,
    )
    SOLID = fields.Field(
        attribute="solid", column_name="Sol Id", widget=wg.CharWidget()
    )
    Enable = fields.Field(
        attribute="enable",
        column_name="Enable",
        widget=wg.BooleanWidget(),
        default=True,
    )

    class Meta:
        model = om.Bt
        skip_unchanged = True
        # import_id_fields = ['ID']
        report_skipped = True
        fields = (
            "ID",
            "Name",
            "Code",
            "BuType",
            "SOLID",
            "Enable",
            "GPS",
            "Address",
            "State",
            "City",
            "Country",
            "Identifier",
            "BelongsTo",
            "Sitemanager",
        )

    def __init__(self, *args, **kwargs):
        super(BtResourceUpdate, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, **kwargs):
        """
        Clean and validate update data.

        Handles partial updates with optional field groups
        (address fields must be provided together).
        """
        if "Code" in row:
            row["Code"] = clean_string(row.get("Code"), code=True)
        if "Name" in row:
            row["Name"] = clean_string(row.get("Name"))
        if "GPS Location" in row:
            self._gpslocation = clean_point_field(row["GPS Location"])
        if "Sol Id" in row:
            self._solid = row["Sol Id"]
        required_fields = ["Address", "State", "City", "Country", "GPS Location"]
        present_fields = [field for field in required_fields if field in row]
        if len(present_fields) == len(required_fields):
            self._address = row["Address"]
            self._state = row["State"]
            self._city = row["City"]
            self._country = row["Country"]
            self._latlng = row["GPS Location"]
        elif len(present_fields) > 0:
            raise ValidationError(
                "To create a complete address, you need to provide the Address, State, City, Country, and GPS Location."
            )

        # check required fields
        if row.get("ID*") in ["", "NONE", None] or (
            isinstance(row.get("ID*"), float) and isnan(row.get("ID*"))
        ):
            raise ValidationError({"ID*": "This field is required"})
        if "Code" in row:
            if row["Code"] in ["", None]:
                raise ValidationError("Code is required field")
        if "Type" in row:
            if row["Type"] in ["", None]:
                raise ValidationError("Type is required field")
        if "Name" in row:
            if row["Name"] in ["", None]:
                raise ValidationError("Name is required field")
        if "Belongs To" in row:
            if row["Belongs To"] in ["", None]:
                raise ValidationError("Belongs To is required field")

        # code validation
        if "Code" in row:
            regex, value = r"^[a-zA-Z0-9\-_]*$", row["Code"]
            if re.search(r"\s|__", value):
                raise ValidationError("Please enter text without any spaces")
            if not re.match(regex, value):
                raise ValidationError(
                    "Please enter valid text avoid any special characters except [_, -]"
                )

        # check record exists
        if not om.Bt.objects.filter(id=row["ID*"]).exists():
            raise ValidationError(
                f"Record with these values not exist: ID - {row['ID*']}"
            )

        super().before_import_row(row, **kwargs)

    def before_save_instance(self, instance, using_transactions, dry_run):
        """Update GPS location and preferences if provided"""
        if hasattr(self, "_gpslocation") and self._gpslocation is not None:
            instance.gpslocation = self._gpslocation
        if hasattr(self, "_address") and self._gpslocation is not None:
            instance.bupreferences["address"] = self._address
        instance.bupreferences["address2"] = {
            "city": self._city
            if hasattr(self, "_city") and self._city is not None
            else None,
            "country": self._country
            if hasattr(self, "_country") and self._country is not None
            else None,
            "state": self._state
            if hasattr(self, "_state") and self._state is not None
            else None,
            "formattedAddress": self._address
            if hasattr(self, "_address") and self._address is not None
            else None,
            "latlng": self._latlng
            if hasattr(self, "_latlng") and self._latlng is not None
            else None,
        }
        if self._solid and not (isinstance(self._solid, float) and isnan(self._solid)):
            instance.solid = int(self._solid)
        else:
            instance.solid = None

        utils.save_common_stuff(self.request, instance)


@admin.register(om.Bt)
class BtAdmin(ImportExportModelAdmin):
    """Django admin for Business Unit model with import/export functionality"""
    resource_class = BtResource
    fields = (
        "bucode",
        "buname",
        "butype",
        "parent",
        "gpslocation",
        "identifier",
        "iswarehouse",
        "enable",
        "bupreferences",
    )
    exclude = ["bupath"]
    list_display = (
        "bucode",
        "id",
        "buname",
        "butype",
        "identifier",
        "parent",
        "butree",
    )
    list_display_links = ("bucode",)
    list_select_related = ("butype", "identifier", "parent", "cuser", "muser", "client", "tenant")
    form = BtForm

    def get_resource_kwargs(self, request, *args, **kwargs):
        return {"request": request}

    def get_queryset(self, request):
        return om.Bt.objects.select_related("butype", "identifier", "parent").all()
