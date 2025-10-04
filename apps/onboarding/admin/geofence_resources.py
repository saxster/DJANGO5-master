"""
Geofence Resources Module

Import/export resources for Geofence and GeofencePeople management.
Note: These are Resources only (no Admin classes) used for bulk imports.

Migrated from apps/onboarding/admin.py
Date: 2025-09-30
"""
from .base import *


class GeofenceResource(resources.ModelResource):
    """
    Resource for importing and validating Geofence data.

    Handles geofence creation with automatic boundary calculation based on
    site GPS location and radius.
    """
    Client = fields.Field(
        column_name="Client*",
        attribute="client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv,
    )
    BV = fields.Field(
        column_name="Site*",
        attribute="bu",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        saves_null_values=True,
        default=get_or_create_none_bv,
    )
    AlertToPeople = fields.Field(
        column_name="Alert to People*",
        attribute="alerttopeople",
        widget=wg.ForeignKeyWidget(pm.People, "peoplecode"),
    )
    AlertToGroup = fields.Field(
        column_name="Alert to Group*",
        attribute="alerttogroup",
        widget=wg.ForeignKeyWidget(pm.Pgroup, "groupname"),
    )

    ID = fields.Field(attribute="id", column_name="ID")
    Code = fields.Field(attribute="gfcode", column_name="Code*")
    Name = fields.Field(attribute="gfname", column_name="Name*")
    AlertText = fields.Field(attribute="alerttext", column_name="Alert Text*")
    Enable = fields.Field(attribute="enable", column_name="Enable", default=True)

    class Meta:
        model = om.GeofenceMaster
        skip_unchanged = True
        # import_id_fields = ['ID']
        report_skipped = True
        fields = (
            "Name",
            "Code",
            "AlertToPeople",
            "AlertToGroup",
            "Enable",
            "AlertText",
            "Site",
            "BV",
            "Client",
            "ID",
        )

    def __init__(self, *args, **kwargs):
        super(GeofenceResource, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, **kwargs):
        """
        Validate and prepare geofence data before import.

        - Validates required fields
        - Ensures either AlertToPeople or AlertToGroup is provided (not both)
        - Validates code format
        - Calculates geofence boundaries from site GPS location
        - Checks uniqueness
        """
        if row["Code*"] in ["", None]:
            raise ValidationError("Code* is required field")
        if row["Name*"] in ["", None]:
            raise ValidationError("Name* is required field")
        if row["Site*"] in ["", None]:
            raise ValidationError("Site* is required field")
        if row["Client*"] in ["", None]:
            raise ValidationError("Client* is required field")
        if row["Alert to People*"] in ["", None]:
            raise ValidationError("Alert to People* is required field")
        if row["Alert to Group*"] in ["", None]:
            raise ValidationError("Alert to Group* is required field")
        if row["Alert Text*"] in ["", None]:
            raise ValidationError("Alert Text* is required field")

        if row["Alert to People*"] == "NONE" and row["Alert to Group*"] == "NONE":
            raise ValidationError(
                "Either 'Alert to People*' or 'Alert to Group*' must be provided (cannot both be NONE)"
            )
        if row["Alert to People*"] != "NONE" and row["Alert to Group*"] != "NONE":
            raise ValidationError(
                "Only one of 'Alert to People*' or 'Alert to Group*' should be provided"
            )

        row["Code*"] = clean_string(row.get("Code*", "NONE"), code=True)
        row["Name*"] = clean_string(row.get("Name*", "NONE"))
        self._alerttopeople = row["Alert to People*"]
        self._alerttogroup = row["Alert to Group*"]
        self._enable = row["Enable"]
        self._alerttext = row["Alert Text*"]
        self._client = row["Client*"]
        self._site = row["Site*"]

        # code validation
        regex, value = r"^[a-zA-Z0-9\-_]*$", row["Code*"]
        if re.search(r"\s|__", value):
            raise ValidationError("Please enter text without any spaces")
        if not re.match(regex, value):
            raise ValidationError(
                "Please enter valid text avoid any special characters except [_, -]"
            )

        get_geofence = om.Bt.objects.filter(bucode=row["Site*"]).values("gpslocation")

        get_final_geofence = bulk_create_geofence(
            get_geofence[0]["gpslocation"], row["Radius*"]
        )

        self._geofence = get_final_geofence
        if (
            om.GeofenceMaster.objects.select_related()
            .filter(gfcode=row["Code*"], client__bucode=row["Client*"])
            .exists()
        ):
            raise ValidationError(
                f"Record with these values already exist {row.values()}"
            )

        super().before_import_row(row, **kwargs)

    def before_save_instance(self, instance, using_transactions, dry_run):
        """Set calculated geofence boundary before saving"""
        if hasattr(self, "_geofence"):
            instance.geofence = self._geofence
        utils.save_common_stuff(self.request, instance)


class GeofencePeopleResource(resources.ModelResource):
    """
    Resource for importing Geofence-People assignments.

    Creates Job records for people assigned to geofences with time-based validity.
    """
    ID = fields.Field(attribute="id", column_name="ID")
    Client = fields.Field(
        column_name="Client*",
        attribute="client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv,
    )
    BV = fields.Field(
        column_name="Site*",
        attribute="bu",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        saves_null_values=True,
        default=get_or_create_none_bv,
    )
    Code = fields.Field(
        column_name="Code*",
        attribute="geofence",
        widget=wg.ForeignKeyWidget(om.GeofenceMaster, "gfcode"),
    )
    PeopleCode = fields.Field(
        column_name="People Code*",
        attribute="peoplecode",
        widget=wg.ForeignKeyWidget(pm.People, "peoplecode"),
    )
    ValidFrom = fields.Field(column_name="Valid From*", attribute="fromdate")
    ValidTo = fields.Field(column_name="Valid To*", attribute="uptodate")
    StartTime = fields.Field(column_name="Start Time*", attribute="starttime")
    EndTime = fields.Field(column_name="End Time*", attribute="endtime")

    class Meta:
        model = Job
        skip_unchanged = True
        # import_id_fields = ["ID"]
        report_skipped = True
        fields = (
            "Code",
            "PeopleCode",
            "ValidFrom",
            "ValidTo",
            "StartTime",
            "EndTime",
            "Site",
            "Client",
            "ID",
            "BV",
        )

    def __init__(self, *args, **kwargs):
        super(GeofencePeopleResource, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, **kwargs):
        """
        Validate and prepare geofence-people assignment data.

        - Validates required fields
        - Converts date formats (DD-MM-YYYY → YYYY-MM-DD)
        - Validates time formats (HH:MM:SS)
        - Validates code format
        - Checks people and geofence existence
        - Prevents duplicate assignments
        """
        from datetime import datetime, time
        from django.core.exceptions import ValidationError
        import re

        # Mandatory fields validation
        if row["Site*"] in ["", None]:
            raise ValidationError("Site* is required field")
        if row["Client*"] in ["", None]:
            raise ValidationError("Client* is required field")
        if row["Code*"] in ["", None]:
            raise ValidationError("Code* is required")
        if row["People Code*"] in ["", None]:
            raise ValidationError("People Code* is required")
        if row["Valid From*"] in ["", None]:
            raise ValidationError("Valid From* is required")
        if row["Valid To*"] in ["", None]:
            raise ValidationError("Valid To* is required")
        if row["Start Time*"] in ["", None]:
            raise ValidationError("Start Time* is required")
        if row["End Time*"] in ["", None]:
            raise ValidationError("End Time* is required")

        # Validate date fields (convert them to YYYY-MM-DD format if needed)
        try:
            row["Valid From*"] = datetime.strptime(
                row["Valid From*"], "%d-%m-%Y"
            ).strftime("%Y-%m-%d")
        except ValueError:
            raise ValidationError(
                "Invalid format for 'Valid From*', expected DD-MM-YYYY"
            )

        try:
            row["Valid To*"] = datetime.strptime(row["Valid To*"], "%d-%m-%Y").strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            raise ValidationError("Invalid format for 'Valid To*', expected DD-MM-YYYY")

        # Time format validation
        start_time = row["Start Time*"]
        end_time = row["End Time*"]

        if isinstance(start_time, time):
            start_time = start_time.strftime("%H:%M:%S")
        if isinstance(end_time, time):
            end_time = end_time.strftime("%H:%M:%S")

        # Time format validation
        if not re.match(r"^\d{2}:\d{2}:\d{2}$", start_time):
            raise ValidationError("Invalid Start Time format, must be HH:MM:SS")
        if not re.match(r"^\d{2}:\d{2}:\d{2}$", end_time):
            raise ValidationError("Invalid End Time format, must be HH:MM:SS")

        # Code format validation
        regex, value = r"^[a-zA-Z0-9\-_]*$", row["Code*"]
        if re.search(r"\s|__", value):
            raise ValidationError("Please enter text without any spaces")
        if not re.match(regex, value):
            raise ValidationError(
                "Please enter valid text avoiding special characters except [_, -]"
            )

        # Validate People and prevent duplicates
        get_people = pm.People.objects.filter(
            peoplecode=row["People Code*"], client__bucode=row["Client*"]
        ).values("id", "peoplecode", "peoplename")
        if not get_people:
            raise ValidationError("Invalid People Code* for the given Client*")

        get_geofence_name = om.GeofenceMaster.objects.filter(
            gfcode=row["Code*"], client__bucode=row["Client*"]
        ).values("gfname")
        if not get_people:
            raise ValidationError("Invalid Code* for the given Client*")

        self._people = get_people[0]["id"]
        self._peoplename = get_people[0]["peoplename"]
        self._peoplecode = get_people[0]["peoplecode"]
        self._geofencecode = row["Code*"]
        self._geofencename = get_geofence_name[0]["gfname"]

        if (
            Job.objects.select_related("geofence", "client", "people")
            .filter(
                geofence__gfcode=row["Code*"],
                client__bucode=row["Client*"],
                identifier="GEOFENCE",
                people__id=self._people,
                enable=True,
            )
            .exists()
        ):
            raise ValidationError(
                f"Record with these values already exists: {row.values()}"
            )

        super().before_import_row(row, **kwargs)

    def before_save_instance(self, instance, using_transactions, dry_run):
        """Create Job instance for geofence-people assignment"""
        instance.planduration = 0
        instance.gracetime = 0
        instance.expirytime = 0
        instance.seqno = -1
        instance.people_id = self._people
        instance.identifier = "GEOFENCE"
        instance.jobname = (
            self._geofencecode + "-" + self._peoplename + " (" + self._peoplecode + ")"
        )
        instance.jobdesc = (
            self._geofencecode
            + "-"
            + self._geofencename
            + "-"
            + self._peoplename
            + " ("
            + self._peoplecode
            + ")"
        )
        utils.save_common_stuff(self.request, instance)
