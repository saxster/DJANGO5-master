import logging
from import_export import resources, fields, widgets as wg
from apps.activity.models.job_model import Job
from django.db.models import Q
from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import QuestionSet
from apps.core.validators.field_validators import (
    clean_point_field,
    clean_string,
    validate_cron,
)
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, OperationalError
from apps.peoples import models as pm
from apps.onboarding import models as om
from apps.core.widgets import (
    BVForeignKeyWidget,
    BVForeignKeyWidgetUpdate,
    QsetFKWUpdate,
    TktCategoryFKWUpdate,
    AssetFKWUpdate,
    PeopleFKWUpdate,
    PgroupFKWUpdate,
)
from datetime import time, datetime, timezone as dt_timezone, timedelta
from django.utils import timezone
from typing import Any
import math

# Configure logger for this module
logger = logging.getLogger(__name__)
from apps.core.utils_new.db_utils import (
    get_or_create_none_typeassist,
    get_or_create_none_job,
    get_or_create_none_bv,
    get_or_create_none_pgroup,
    get_or_create_none_asset,
    get_or_create_none_qset,
    get_or_create_none_people,
    get_or_create_none_gf,
    get_or_create_none_tenant,
)
from apps.core import utils
import logging

logger = logging.getLogger("django")


def default_ta() -> Any:
    return get_or_create_none_typeassist()[0]

def default_fromdate() -> datetime:
    return timezone.now()

def default_uptodate() -> datetime:
    return timezone.now() + timedelta(days=365)


class PeopleFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return pm.People.objects.select_related().filter(
            (Q(client__bucode=row["Client*"]) & Q(enable=True)) | Q(peoplecode="NONE")
        )
    
    def clean(self, value, row=None, **kwargs):
        # Handle pandas NaN values  
        if value is None or str(value).strip().lower() in ['', 'nan', 'none']:
            # Return NONE person instead of trying to lookup NaN
            try:
                return pm.People.objects.get(peoplecode="NONE")
            except pm.People.DoesNotExist:
                return None
        return super().clean(value, row=row, **kwargs)


class PgroupFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return pm.Pgroup.objects.select_related().filter(
            (Q(client__bucode=row["Client*"]) & Q(enable=True)) | Q(groupname="NONE")
        )
    
    def clean(self, value, row=None, **kwargs):
        # Handle pandas NaN values
        if value is None or str(value).strip().lower() in ['', 'nan', 'none']:
            # Return NONE group instead of trying to lookup NaN
            try:
                return pm.Pgroup.objects.get(groupname="NONE")
            except pm.Pgroup.DoesNotExist:
                return None
        return super().clean(value, row=row, **kwargs)


class QsetFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return QuestionSet.objects.select_related().filter(
            Q(qsetname="NONE") | (Q(client__bucode=row["Client*"]) & Q(enable=True))
        )


class AssetFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return Asset.objects.select_related().filter(
            Q(assetcode="NONE") | (Q(client__bucode=row["Client*"]) & Q(enable=True))
        )


class TktCategoryFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        return om.TypeAssist.objects.select_related().filter(
            tatype__tacode="NOTIFYCATEGORY"
        )


class ParentFKW(wg.ForeignKeyWidget):
    def get_queryset(self, value, row, *args, **kwargs):
        """Get available parent tours for the given client/site"""
        client_code = row.get("Client*")
        site_code = row.get("Site*")
        
        from django.db.models import Q

        qset = Job.objects.select_related().filter(
            Q(parent__isnull=True) | Q(parent_id=1),  # Unified parent handling (must be first)
            client__bucode=client_code,
            bu__bucode=site_code,
            identifier="INTERNALTOUR",
            enable=True   # Only enabled tours
        ).exclude(jobname="NONE")
        
        logger.info(f"Available parent tours for {client_code}/{site_code}: {list(qset.values_list('jobname', flat=True))}")
        return qset


class BaseJobResource(resources.ModelResource):
    CLIENT = fields.Field(
        attribute="client",
        column_name="Client*",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
    )
    SITE = fields.Field(
        attribute="bu", column_name="Site*", widget=BVForeignKeyWidget(om.Bt, "bucode")
    )
    NAME = fields.Field(attribute="jobname", column_name="Name*")
    DESC = fields.Field(attribute="jobdesc", column_name="Description*", default="")
    QSET = fields.Field(
        attribute="qset",
        column_name="Question Set/Checklist*",
        widget=QsetFKW(QuestionSet, "qsetname"),
    )
    ASSET = fields.Field(
        attribute="asset", column_name="Asset*", widget=AssetFKW(Asset, "assetcode")
    )
    PARENT = fields.Field(
        attribute="parent",
        column_name="Belongs To*",
        widget=wg.ForeignKeyWidget(Job, "jobname"),
        default=get_or_create_none_job,
    )
    PDURATION = fields.Field(attribute="planduration", column_name="Plan Duration*")
    GRACETIME = fields.Field(attribute="gracetime", column_name="Gracetime Before*")
    EXPTIME = fields.Field(attribute="expirytime", column_name="Gracetime After*")
    CRON = fields.Field(attribute="cron", column_name="Scheduler*")
    FROMDATE = fields.Field(
        attribute="fromdate", column_name="From Date*", widget=wg.DateTimeWidget()
    )
    UPTODATE = fields.Field(
        attribute="uptodate", column_name="Upto Date*", widget=wg.DateTimeWidget()
    )
    SCANTYPE = fields.Field(
        attribute="scantype", column_name="Scan Type*", default="QR"
    )
    TKTCATEGORY = fields.Field(
        attribute="ticketcategory",
        column_name="Notify Category*",
        widget=TktCategoryFKW(om.TypeAssist, "tacode"),
        default=default_ta,
    )
    PRIORITY = fields.Field(
        attribute="priority", column_name="Priority*", default="LOW"
    )
    PEOPLE = fields.Field(
        attribute="people",
        column_name="People*",
        widget=PeopleFKW(pm.People, "peoplecode"),
    )
    PGROUP = fields.Field(
        attribute="pgroup",
        column_name="Group Name*",
        widget=PgroupFKW(pm.Pgroup, "groupname"),
    )
    STARTTIME = fields.Field(
        attribute="starttime",
        column_name="Start Time",
        default=time(0, 0, 0),
        widget=wg.TimeWidget(),
    )
    ENDTIME = fields.Field(
        attribute="endtime",
        column_name="End Time",
        default=time(0, 0, 0),
        widget=wg.TimeWidget(),
    )
    SEQNO = fields.Field(attribute="seqno", column_name="Seq No", default=-1)
    ID = fields.Field(attribute="id", column_name="ID")

    class Meta:
        model = Job
        skip_unchanged = True
        import_id_fields = ["ID"]
        report_skipped = True


class TaskResource(BaseJobResource):
    # Override specific fields from BaseJobResource to match specification
    DESC = fields.Field(attribute="jobdesc", column_name="Description", default="")  # Optional description
    PDURATION = fields.Field(attribute="planduration", column_name="Plan Duration*")
    GRACETIME = fields.Field(attribute="gracetime", column_name="Grace Time*")
    FROMDATE = fields.Field(attribute="fromdate", column_name="From Date*", widget=wg.DateTimeWidget())
    UPTODATE = fields.Field(attribute="uptodate", column_name="Upto Date*", widget=wg.DateTimeWidget())
    CRON = fields.Field(attribute="cron", column_name="Scheduler*")
    SCANTYPE = fields.Field(attribute="scantype", column_name="Scan Type*")
    ASSET = fields.Field(attribute="asset", column_name="Asset/Checkpoint*", widget=AssetFKW(Asset, "assetcode"))
    QSET = fields.Field(attribute="qset", column_name="Question Set*", widget=QsetFKW(QuestionSet, "qsetname"))
    TKTCATEGORY = fields.Field(attribute="ticketcategory", column_name="Notify Category*", widget=TktCategoryFKW(om.TypeAssist, "tacode"))
    PRIORITY = fields.Field(attribute="priority", column_name="Priority*")
    PEOPLE = fields.Field(attribute="people", column_name="People", widget=PeopleFKW(pm.People, "peoplecode"))
    PGROUP = fields.Field(attribute="pgroup", column_name="Group Name", widget=PgroupFKW(pm.Pgroup, "groupname"))
    PARENT = fields.Field(attribute="parent", column_name="Belongs To", widget=wg.ForeignKeyWidget(Job, "jobname"), default=get_or_create_none_job)  # Optional parent
    IDF = fields.Field(
        attribute="identifier", column_name="Identifier*", default="TASK"
    )

    class Meta:
        model = Job
        skip_unchanged = True
        import_id_fields = ["ID"]
        report_skipped = True
        fields = [
            "CLIENT",
            "SITE",
            "NAME",
            "DESC",
            "QSET",
            "PDURATION",
            "GRACETIME",
            "EXPTIME",
            "CRON",
            "FROMDATE",
            "UPTODATE",
            "SCANTYPE",
            "TKTCATEGORY",
            "PRIORITY",
            "PEOPLE",
            "PGROUP",
            "IDF",
            "STARTTIME",
            "ENDTIME",
            "SEQNO",
            "PARENT",
            "bu",
            "client",
            "seqno",
            "parent",
            "geofence",
            "asset",
            "qset",
            "pgroup",
            "people",
            "priority",
            "planduration",
            "gracetime",
            "expirytime",
            "cron",
            "fromdate",
            "uptodate",
            "scantype",
            "ticketcategory",
            "identifier",
            "seqno",
            "enable",
            "geojson",
            "other_info",
            "frequency",
            "scantype",
            "ticketcategory",
            "endtime",
            "id",
            "tenant",
            "cuser",
            "muser",
            "starttime",
            "shift",
            "bu",
            "client",
            "seqno",
            "parent",
            "geofence",
            "asset",
            "cdtz",
            "mdtz",
            "ctzoffset",
            "jobname",
            "jobdesc",
            "lastgeneratedon",
            "sgroup",
            "ID",
            "ASSET",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)
        self.ctzoffset = kwargs.pop("ctzoffset", -1)

    def before_import_row(self, row, row_number, **kwargs):
        self.check_required_fields(row)
        self.validate_row(row)
        self.unique_record_check(row)
        self.check_valid_scantype(row)
        self.check_valid_priority(row)
        # Add new validations
        self.validate_assignment_rules(row)
        self.validate_references_exist(row)
        if not row.get("Identifier*"):
            row["Identifier*"] = "TASK"
        super().before_import_row(row, **kwargs)

    def check_valid_scantype(self, row):
        valid_scantypes = ["QR", "NFC", "SKIP", "ENTERED"]
        scan_type = row.get("Scan Type*")
        if scan_type not in valid_scantypes:
            raise ValidationError(
                {
                    "Scan Type*": f"{scan_type} is not a valid Scan Type. Please select a valid Scan Type from {valid_scantypes}"
                }
            )

    def check_valid_priority(self, row):
        valid_priorities = ["LOW", "MEDIUM", "HIGH"]
        priority = row.get("Priority*")
        if priority not in valid_priorities:
            raise ValidationError(
                {
                    "Priority*": f"{priority} is not a valid Priority. Please select a valid Priority from {valid_priorities}"
                }
            )

    def validate_assignment_rules(self, row):
        """Ensure at least one of People or Group Name is provided"""
        people = str(row.get("People", "")).strip()
        group = str(row.get("Group Name", "")).strip()
        
        if not people and not group:
            raise ValidationError({
                'Assignment': 'At least one of People or Group Name must be provided'
            })

    def validate_references_exist(self, row):
        """Validate that referenced entities exist"""
        client_code = row.get("Client*")
        site_code = row.get("Site*")
        
        # Validate Client exists
        if not om.Bt.objects.filter(bucode=client_code, identifier='CLIENT').exists():
            raise ValidationError({
                'Client*': f"Client with code '{client_code}' does not exist"
            })
        
        # Validate Site exists and belongs to Client
        if not om.Bt.objects.filter(
            bucode=site_code, 
            identifier='SITE',
            parent__bucode=client_code
        ).exists():
            raise ValidationError({
                'Site*': f"Site '{site_code}' does not exist or doesn't belong to client '{client_code}'"
            })

    def check_required_fields(self, row):
        required_fields = [
            "Name*",
            "From Date*",
            "Upto Date*",
            "Scheduler*",
            "Notify Category*",
            "Plan Duration*",
            "Grace Time*",
            "Question Set*",
            "Asset/Checkpoint*",
            "Priority*",
            "Scan Type*",
        ]
        # People and Group Name are optional but at least one should be provided (checked in validate_assignment_rules)
        integer_fields = ["Plan Duration*", "Grace Time*"]

        for field in required_fields:
            if field in row:
                value = row.get(field)
                if field in integer_fields:
                    try:
                        int_value = int(value)
                        if int_value < 0:
                            raise ValidationError(
                                {field: f"{field} must be a non-negative integer"}
                            )
                    except (ValueError, TypeError):
                        raise ValidationError(
                            {field: f"{field} must be a valid integer"}
                        )
                elif value in [None, ""]:
                    raise ValidationError({field: f"{field} is a required field"})

    def validate_row(self, row):
        row["Name*"] = clean_string(row["Name*"])
        if "Description" in row:
            row["Description"] = clean_string(row["Description"])
        row["Plan Duration*"] = int(row["Plan Duration*"])
        row["Grace Time*"] = int(row["Grace Time*"])
        # check valid cron
        if not validate_cron(row["Scheduler*"]):
            raise ValidationError(
                {
                    "Scheduler*": "Invalid value or Problematic Cron Expression for scheduler"
                }
            )

    def unique_record_check(self, row):
        if Job.objects.filter(
            jobname=row["Name*"],
            asset__assetcode=row["Asset/Checkpoint*"],
            qset__qsetname=row["Question Set/Checklist*"],
            identifier="TASK",
            client__bucode=row["Client*"],
        ).exists():
            raise ValidationError("Record Already with these values are already exist")

    def before_save_instance(self, instance, using_transactions, dry_run=False):
        utils.save_common_stuff(
            self.request, instance, self.is_superuser, self.ctzoffset
        )


class TourResource(resources.ModelResource):
    CLIENT = fields.Field(
        attribute="client",
        column_name="Client*",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv,
    )
    SITE = fields.Field(
        attribute="bu", column_name="Site*", widget=BVForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv
    )
    NAME = fields.Field(attribute="jobname", column_name="Name*", default="Untitled Tour")
    DESC = fields.Field(attribute="jobdesc", column_name="Description", default="")
    PDURATION = fields.Field(attribute="planduration", column_name="Plan Duration*", default=60)
    GRACETIME = fields.Field(attribute="gracetime", column_name="Grace Time*", default=30) 
    CRON = fields.Field(attribute="cron", column_name="Scheduler*", default="0 8 * * *")
    FROMDATE = fields.Field(
        attribute="fromdate", column_name="From Date*", widget=wg.DateTimeWidget(),
        default=default_fromdate
    )
    UPTODATE = fields.Field(
        attribute="uptodate", column_name="Upto Date*", widget=wg.DateTimeWidget(),
        default=default_uptodate
    )
    SCANTYPE = fields.Field(
        attribute="scantype", column_name="Scan Type*", default="QR"
    )
    TKTCATEGORY = fields.Field(
        attribute="ticketcategory",
        column_name="Notify Category*",
        widget=TktCategoryFKW(om.TypeAssist, "tacode"),
        default=default_ta,
    )
    PRIORITY = fields.Field(
        attribute="priority", column_name="Priority*", default="LOW"
    )
    PEOPLE = fields.Field(
        attribute="people",
        column_name="People",
        widget=PeopleFKW(pm.People, "peoplecode"),
        default=lambda: None,  # Allow empty people
    )
    PGROUP = fields.Field(
        attribute="pgroup",
        column_name="Group Name",
        widget=PgroupFKW(pm.Pgroup, "groupname"),
        default=get_or_create_none_pgroup,  # Handle empty/NaN group names
    )
    # Dynamic tour fields
    ISDYNAMIC = fields.Field(column_name="Is Dynamic")
    ISTIMEBOUND = fields.Field(column_name="Is Time Restricted")

    class Meta:
        model = Job
        skip_unchanged = True
        report_skipped = True
        fields = [
            "NAME",
            "DESC",
            "PEOPLE",
            "PGROUP",
            "PRIORITY",
            "TKTCATEGORY",
            "PDURATION",
            "GRACETIME",
            "CRON",
            "FROMDATE",
            "UPTODATE",
            "SCANTYPE",
            "CLIENT",
            "SITE",
            "ISTIMEBOUND",
            "ISDYNAMIC",
        ]

    def __init__(self, *args, **kwargs):
        super(TourResource, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)
        self.ctzoffset = kwargs.pop("ctzoffset", -1)
        
    def get_import_id_fields(self):
        """Override to return empty list since we don't use import ID fields for tours"""
        return []

    def dehydrate_ISDYNAMIC(self, instance):
        """Extract the isdynamic boolean value from other_info dictionary"""
        if isinstance(instance.other_info, dict):
            return instance.other_info.get('isdynamic', False)
        return False

    def dehydrate_ISTIMEBOUND(self, instance):
        """Extract the istimebound boolean value from other_info dictionary"""
        if isinstance(instance.other_info, dict):
            return instance.other_info.get('istimebound', False)
        return False

    def before_import_row(self, row, row_number, **kwargs):
        self.check_required_fields(row)
        self.validate_row(row)
        self.validate_dynamic_tour_logic(row)  # New method
        self.validate_assignment_rules(row)  # Validate People/Group Name mutual exclusivity
        self.unique_record_check(row)
        # Store row for before_save_instance
        self._current_row = row
        super().before_import_row(row, **kwargs)

    def check_required_fields(self, row):
        required_fields = [
            "Name*",
            "Priority*",
            "Notify Category*",
            "Plan Duration*",
            "Grace Time*",
            "Scheduler*",
            "From Date*",
            "Upto Date*",
            "Scan Type*",
            "Client*",
            "Site*",
        ]
        integer_fields = ["Plan Duration*", "Grace Time*"]

        for field in required_fields:
            if field in row:
                value = row.get(field)
                if field in integer_fields:
                    try:
                        int_value = int(value)
                        if int_value < 0:
                            raise ValidationError(
                                {field: f"{field} must be a non-negative integer"}
                            )
                    except (ValueError, TypeError):
                        raise ValidationError(
                            {field: f"{field} must be a valid integer"}
                        )
                elif value in [None, ""]:
                    raise ValidationError({field: f"{field} is a required field"})

    def validate_row(self, row):
        row["Name*"] = clean_string(row["Name*"])
        if "Description" in row:
            row["Description"] = clean_string(row["Description"])
        row["Plan Duration*"] = int(row["Plan Duration*"])
        row["Grace Time*"] = int(row["Grace Time*"])
        # check valid cron
        if not validate_cron(row["Scheduler*"]):
            raise ValidationError(
                {
                    "Scheduler*": "Invalid value or Problematic Cron Expression for scheduler"
                }
            )

    def validate_dynamic_tour_logic(self, row):
        """Validate dynamic vs static tour requirements"""
        is_dynamic = str(row.get('Is Dynamic', '')).strip().lower() in ('true', '1', 'yes', 'on')
        
        if is_dynamic:
            # For dynamic tours, ensure no scheduling fields are provided
            conditional_fields = ['Plan Duration*', 'Grace Time*', 'Scheduler*', 'From Date*', 'Upto Date*']
            provided_fields = []
            
            for field in conditional_fields:
                value = str(row.get(field, '')).strip()
                if value and value.lower() not in ['', 'none', 'null']:
                    provided_fields.append(field)
            
            if provided_fields:
                raise ValidationError({
                    'Dynamic Tour Error': f"Dynamic tours should not have scheduling fields. Please remove: {', '.join(provided_fields)}"
                })
        else:
            # For static tours, ensure all scheduling fields are provided
            required_fields = ['Plan Duration*', 'Grace Time*', 'Scheduler*', 'From Date*', 'Upto Date*']
            for field in required_fields:
                value = str(row.get(field, '')).strip()
                if not value or value.lower() in ['', 'none', 'null']:
                    raise ValidationError({
                        field: f"Static tours require {field}"
                    })

    def validate_assignment_rules(self, row):
        """Ensure People and Group Name are mutually exclusive (either-or, not both)"""
        people = str(row.get("People", "")).strip()
        group = str(row.get("Group Name", "")).strip()
        
        # Define what constitutes "empty" values (including pandas NaN)
        empty_values = ['NONE', '', 'nan', 'NaN', 'NAN']
        
        # Check if both are provided (not allowed)
        people_has_value = people and people.upper() not in empty_values
        group_has_value = group and group.upper() not in empty_values
        
        if people_has_value and group_has_value:
            raise ValidationError({
                'Assignment': 'People and Group Name are mutually exclusive. Please provide only one, not both.'
            })
        
        # Check if neither is provided (not allowed)
        if not people_has_value and not group_has_value:
            raise ValidationError({
                'Assignment': 'Either People or Group Name must be provided.'
            })

    def unique_record_check(self, row):
        if Job.objects.filter(
            jobname=row["Name*"],
            bu__bucode=row["Site*"],
            identifier="INTERNALTOUR",
            client__bucode=row["Client*"],
        ).exists():
            raise ValidationError("Record Already with these values are already exist")

    def before_save_instance(self, instance, row, **kwargs):
        # Imports moved to top of file
        
        # Set the identifier for tours
        instance.identifier = 'INTERNALTOUR'
        
        # Set as top-level parent tour (required for checkpoints to reference it)
        instance.parent_id = 1
        
        # Always Applied System Field Defaults
        if not instance.seqno:
            instance.seqno = -1  # Sequence number for parent tours
        if not instance.expirytime:
            instance.expirytime = 0  # Expiry time in minutes
        if not hasattr(instance, 'starttime') or not instance.starttime:
            instance.starttime = time(0, 0, 0)  # Start time (00:00:00)
        if not hasattr(instance, 'endtime') or not instance.endtime:
            instance.endtime = time(0, 0, 0)  # End time (00:00:00)
        
        # Handle dynamic tour other_info - ensure it's a dict
        is_dynamic = str(row.get('Is Dynamic', '')).strip().lower() in ('true', '1', 'yes', 'on')
        is_timebound = str(row.get('Is Time Restricted', '')).strip().lower() in ('true', '1', 'yes', 'on')
        
        # Initialize other_info as dict if it's not already
        if not instance.other_info or not isinstance(instance.other_info, dict):
            instance.other_info = {}
            
        instance.other_info['isdynamic'] = is_dynamic
        instance.other_info['istimebound'] = is_timebound
        
        # Dynamic Tour Conditional Defaults
        if is_dynamic:
            # Dynamic tour defaults - override user-provided values for dynamic tours
            instance.planduration = 0  # Plan duration in minutes
            instance.gracetime = 0  # Grace time in minutes  
            instance.cron = '* * * * *'  # Default cron expression
            now = timezone.now()
            instance.fromdate = now  # Current UTC time
            instance.uptodate = now + timedelta(days=365)  # One year from now
        else:
            # Static tour - ensure dates are properly set if missing
            if not instance.fromdate:
                instance.fromdate = timezone.now()
            if not instance.uptodate:
                instance.uptodate = timezone.now() + timedelta(days=365)
        
        # Foreign Key Defaults - Set to default records if null or missing
        if not instance.asset_id:
            instance.asset = get_or_create_none_asset()
        if not instance.qset_id:
            instance.qset = get_or_create_none_qset()
        if not instance.people_id:
            # Use the function or fallback to ID=1 for "None" person
            try:
                instance.people = get_or_create_none_people()
            except (DatabaseError, OperationalError, ObjectDoesNotExist, ValidationError, AttributeError) as e:
                logger.warning(f"Failed to create default people object: {e}")
                instance.people_id = 1  # Default "None" person ID
        if not instance.pgroup_id:
            instance.pgroup_id = 1  # Default "None" group ID
        if not hasattr(instance, 'geofence_id') or not instance.geofence_id:
            try:
                instance.geofence = get_or_create_none_gf()
            except (DatabaseError, OperationalError, ObjectDoesNotExist, ValidationError, AttributeError) as e:
                logger.warning(f"Failed to create default geofence object: {e}")
                instance.geofence_id = 1  # Default geofence ID
        if not hasattr(instance, 'tenant_id') or not instance.tenant_id:
            try:
                instance.tenant = get_or_create_none_tenant()
            except (DatabaseError, OperationalError, ObjectDoesNotExist, ValidationError, AttributeError) as e:
                logger.warning(f"Failed to create default tenant object: {e}")
                instance.tenant_id = 1  # Default tenant ID
        
        # Additional system defaults for fields that might be missing
        if not hasattr(instance, 'sgroup_id') or not instance.sgroup_id:
            instance.sgroup_id = 1  # Default site group ID
        if not hasattr(instance, 'shift_id') or not instance.shift_id:
            instance.shift_id = 1  # Default shift ID
        
        utils.save_common_stuff(self.request, instance, self.is_superuser)


class TaskResourceUpdate(resources.ModelResource):
    CLIENT = fields.Field(
        attribute="client",
        column_name="Client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
    )
    SITE = fields.Field(
        attribute="bu",
        column_name="Site",
        widget=BVForeignKeyWidgetUpdate(om.Bt, "bucode"),
    )
    NAME = fields.Field(attribute="jobname", column_name="Name")
    DESC = fields.Field(attribute="jobdesc", column_name="Description", default="")
    QSET = fields.Field(
        attribute="qset",
        column_name="Question Set/Checklist",
        widget=QsetFKWUpdate(QuestionSet, "qsetname"),
    )
    ASSET = fields.Field(
        attribute="asset",
        column_name="Asset",
        widget=AssetFKWUpdate(Asset, "assetcode"),
    )
    PARENT = fields.Field(
        attribute="parent",
        column_name="Belongs To",
        widget=wg.ForeignKeyWidget(Job, "jobname"),
        default=get_or_create_none_job,
    )
    PDURATION = fields.Field(attribute="planduration", column_name="Plan Duration")
    GRACETIME = fields.Field(attribute="gracetime", column_name="Gracetime Before")
    EXPTIME = fields.Field(attribute="expirytime", column_name="Gracetime After")
    CRON = fields.Field(attribute="cron", column_name="Scheduler")
    FROMDATE = fields.Field(
        attribute="fromdate", column_name="From Date", widget=wg.DateTimeWidget()
    )
    UPTODATE = fields.Field(
        attribute="uptodate", column_name="Upto Date", widget=wg.DateTimeWidget()
    )
    SCANTYPE = fields.Field(attribute="scantype", column_name="Scan Type", default="QR")
    TKTCATEGORY = fields.Field(
        attribute="ticketcategory",
        column_name="Notify Category",
        widget=TktCategoryFKWUpdate(om.TypeAssist, "tacode"),
        default=default_ta,
    )
    PRIORITY = fields.Field(attribute="priority", column_name="Priority", default="LOW")
    PEOPLE = fields.Field(
        attribute="people",
        column_name="People",
        widget=PeopleFKWUpdate(pm.People, "peoplecode"),
    )
    PGROUP = fields.Field(
        attribute="pgroup",
        column_name="Group Name",
        widget=PgroupFKWUpdate(pm.Pgroup, "groupname"),
    )
    STARTTIME = fields.Field(
        attribute="starttime",
        column_name="Start Time",
        default=time(0, 0, 0),
        widget=wg.TimeWidget(),
    )
    ENDTIME = fields.Field(
        attribute="endtime",
        column_name="End Time",
        default=time(0, 0, 0),
        widget=wg.TimeWidget(),
    )
    SEQNO = fields.Field(attribute="seqno", column_name="Seq No", default=-1)
    ID = fields.Field(attribute="id", column_name="ID*")

    class Meta:
        model = Job
        skip_unchanged = True
        # import_id_fields = ['ID']
        report_skipped = True
        fields = [
            "ID",
            "CLIENT",
            "SITE",
            "NAME",
            "DESC",
            "QSET",
            "ASSET",
            "PDURATION",
            "GRACETIME",
            "EXPTIME",
            "CRON",
            "FROMDATE",
            "UPTODATE",
            "SCANTYPE",
            "TKTCATEGORY",
            "PRIORITY",
            "PEOPLE",
            "PGROUP",
            "STARTTIME",
            "ENDTIME",
            "SEQNO",
            "PARENT",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number, **kwargs):
        self.check_required_fields(row)
        self.validate_row(row)
        self.check_record_exists(row)
        self.check_valid_scantype(row)
        self.check_valid_priority(row)
        super().before_import_row(row, **kwargs)

    def check_valid_scantype(self, row):
        if "Scan Type" in row:
            valid_scantypes = ["QR", "NFC", "SKIP", "ENTERED"]
            scan_type = row.get("Scan Type")
            if scan_type not in valid_scantypes:
                raise ValidationError(
                    {
                        "Scan Type": "%(type)s is not a valid Scan Type. Please select a valid Scan Type from %(valid)s"
                        % {"type": scan_type, "valid": valid_scantypes}
                    }
                )

    def check_valid_priority(self, row):
        if "Priority" in row:
            valid_priorities = ["LOW", "MEDIUM", "HIGH"]
            priority = row.get("Priority")
            if priority not in valid_priorities:
                raise ValidationError(
                    {
                        "Priority": "%(priority)s is not a valid Priority. Please select a valid Priority from %(valid)s"
                        % {"priority": priority, "valid": valid_priorities}
                    }
                )

    def check_required_fields(self, row):
        if row.get("ID*") in ["", "NONE", None] or (
            isinstance(row.get("ID*"), float) and math.isnan(row.get("ID*"))
        ):
            raise ValidationError({"ID*": "This field is required"})
        required_fields = [
            "Name",
            "From Date",
            "Upto Date",
            "Scheduler",
            "Notify Category",
            "Plan Duration",
            "Gracetime Before",
            "Gracetime After",
            "Question Set/Checklist",
            "Asset",
            "Priority",
            "People",
            "Group Name",
            "Belongs To",
        ]
        integer_fields = ["Plan Duration", "Gracetime Before", "Gracetime After"]

        for field in required_fields:
            if field in row:
                value = row.get(field)
                if field in integer_fields:
                    try:
                        int_value = int(value)
                        if int_value < 0:
                            raise ValidationError(
                                {field: f"{field} must be a non-negative integer"}
                            )
                    except (ValueError, TypeError):
                        raise ValidationError(
                            {field: f"{field} must be a valid integer"}
                        )
                elif value in [None, ""]:
                    raise ValidationError({field: f"{field} is a required field"})

    def validate_row(self, row):
        if "Name" in row:
            row["Name"] = clean_string(row["Name"])
        if "Description" in row:
            row["Description"] = clean_string(row["Description"])
        if "Plan Duration" in row:
            row["Plan Duration"] = int(row["Plan Duration"])
        if "Gracetime Before" in row:
            row["Gracetime Before"] = int(row["Gracetime Before"])
        if "Gracetime After" in row:
            row["Gracetime After"] = int(row["Gracetime After"])
        # check valid cron
        if "Scheduler" in row:
            if not validate_cron(row["Scheduler"]):
                raise ValidationError(
                    {
                        "Scheduler": "Invalid value or Problematic Cron Expression for scheduler"
                    }
                )

    def check_record_exists(self, row):
        if not Job.objects.filter(id=row["ID*"]).exists():
            raise ValidationError(
                f"Record with these values not exist: ID - {row['ID*']}"
            )

    def before_save_instance(self, instance, using_transactions, dry_run=False):
        utils.save_common_stuff(self.request, instance, self.is_superuser)


class TourResourceUpdate(resources.ModelResource):
    CLIENT = fields.Field(
        attribute="client",
        column_name="Client",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv,
    )
    SITE = fields.Field(
        attribute="bu",
        column_name="Site",
        widget=BVForeignKeyWidgetUpdate(om.Bt, "bucode"),
    )
    NAME = fields.Field(attribute="jobname", column_name="Name")
    DESC = fields.Field(attribute="jobdesc", column_name="Description", default="")
    QSET = fields.Field(
        attribute="qset",
        column_name="Question Set/Checklist",
        widget=QsetFKWUpdate(QuestionSet, "qsetname"),
    )
    ASSET = fields.Field(
        attribute="asset",
        column_name="Asset",
        widget=AssetFKWUpdate(Asset, "assetcode"),
    )
    PARENT = fields.Field(
        attribute="parent",
        column_name="Belongs To",
        widget=wg.ForeignKeyWidget(Job, "jobname"),
        default=get_or_create_none_job,
    )
    PDURATION = fields.Field(attribute="planduration", column_name="Plan Duration")
    GRACETIME = fields.Field(attribute="gracetime", column_name="Gracetime")
    EXPTIME = fields.Field(attribute="expirytime", column_name="Expiry Time")
    CRON = fields.Field(attribute="cron", column_name="Scheduler")
    FROMDATE = fields.Field(
        attribute="fromdate", column_name="From Date", widget=wg.DateTimeWidget()
    )
    UPTODATE = fields.Field(
        attribute="uptodate", column_name="Upto Date", widget=wg.DateTimeWidget()
    )
    SCANTYPE = fields.Field(attribute="scantype", column_name="Scan Type", default="QR")
    TKTCATEGORY = fields.Field(
        attribute="ticketcategory",
        column_name="Notify Category",
        widget=TktCategoryFKWUpdate(om.TypeAssist, "tacode"),
        default=default_ta,
    )
    PRIORITY = fields.Field(attribute="priority", column_name="Priority", default="LOW")
    PEOPLE = fields.Field(
        attribute="people",
        column_name="People",
        widget=PeopleFKWUpdate(pm.People, "peoplecode"),
    )
    PGROUP = fields.Field(
        attribute="pgroup",
        column_name="Group Name",
        widget=PgroupFKWUpdate(pm.Pgroup, "groupname"),
    )
    STARTTIME = fields.Field(
        attribute="starttime",
        column_name="Start Time",
        default=time(0, 0, 0),
        widget=wg.TimeWidget(),
    )
    ENDTIME = fields.Field(
        attribute="endtime",
        column_name="End Time",
        default=time(0, 0, 0),
        widget=wg.TimeWidget(),
    )
    SEQNO = fields.Field(attribute="seqno", column_name="Seq No", default=-1)
    ID = fields.Field(attribute="id", column_name="ID*")

    class Meta:
        model = Job
        skip_unchanged = True
        # import_id_fields = ['ID']
        report_skipped = True
        fields = [
            "ID",
            "CLIENT",
            "SITE",
            "NAME",
            "DESC",
            "QSET",
            "PDURATION",
            "GRACETIME",
            "EXPTIME",
            "CRON",
            "FROMDATE",
            "UPTODATE",
            "SCANTYPE",
            "TKTCATEGORY",
            "PRIORITY",
            "PEOPLE",
            "PGROUP",
            "STARTTIME",
            "ENDTIME",
            "SEQNO",
            "PARENT",
            "ASSET",
        ]

    def __init__(self, *args, **kwargs):
        super(TourResourceUpdate, self).__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)

    def before_import_row(self, row, row_number, **kwargs):
        self.check_required_fields(row)
        self.validate_row(row)
        self.check_record_exists(row)
        super().before_import_row(row, **kwargs)

    def check_required_fields(self, row):
        if row.get("ID*") in ["", "NONE", None] or (
            isinstance(row.get("ID*"), float) and math.isnan(row.get("ID*"))
        ):
            raise ValidationError({"ID*": "This field is required"})
        required_fields = [
            "Name",
            "From Date",
            "Upto Date",
            "Scheduler",
            "Notify Category",
            "Plan Duration",
            "Expiry Time",
            "Gracetime",
            "Seq No",
            "Question Set/Checklist",
            "Asset",
            "Priority",
            "People",
            "Group Name",
            "Belongs To",
        ]
        integer_fields = ["Plan Duration", "Gracetime", "Expiry Time", "Seq No"]

        for field in required_fields:
            if field in row:
                value = row.get(field)
                if field in integer_fields:
                    try:
                        int_value = int(value)
                        if int_value < 0:
                            raise ValidationError(
                                {field: f"{field} must be a non-negative integer"}
                            )
                    except (ValueError, TypeError):
                        raise ValidationError(
                            {field: f"{field} must be a valid integer"}
                        )
                elif value in [None, ""]:
                    raise ValidationError({field: f"{field} is a required field"})

    def validate_row(self, row):
        if "Identifier" in row:
            row["Identifier"] = "INTERNALTOUR"
        if "Name" in row:
            row["Name"] = clean_string(row["Name"])
        if "Description" in row:
            row["Description"] = clean_string(row["Description"])
        if "Plan Duration" in row:
            row["Plan Duration"] = int(row["Plan Duration"])
        if "Gracetime" in row:
            row["Gracetime"] = int(row["Gracetime"])
        if "Expiry Time" in row:
            row["Expiry Time"] = int(row["Expiry Time"])
        if "Seq No" in row:
            row["Seq No"] = int(row["Seq No"])
        # check valid cron
        if "Scheduler" in row:
            if not validate_cron(row["Scheduler"]):
                raise ValidationError(
                    {
                        "Scheduler": "Invalid value or Problematic Cron Expression for scheduler"
                    }
                )

    def check_record_exists(self, row):
        if not Job.objects.filter(id=row["ID*"]).exists():
            raise ValidationError(
                f"Record with these values not exist: ID - {row['ID*']}"
            )

    def before_save_instance(self, instance, using_transactions, dry_run=False):
        utils.save_common_stuff(self.request, instance, self.is_superuser)


class TourCheckpointResource(resources.ModelResource):
    """Resource for importing tour checkpoints as child records of existing tours"""
    
    CLIENT = fields.Field(
        attribute="client",
        column_name="Client*",
        widget=wg.ForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv
    )
    SITE = fields.Field(
        attribute="bu", 
        column_name="Site*", 
        widget=BVForeignKeyWidget(om.Bt, "bucode"),
        default=get_or_create_none_bv
    )
    SEQNO = fields.Field(attribute="seqno", column_name="Seq No*", default=1)
    ASSET = fields.Field(
        attribute="asset", 
        column_name="Asset/Checkpoint*", 
        widget=AssetFKW(Asset, "assetcode"),
        default=get_or_create_none_asset
    )
    QSET = fields.Field(
        attribute="qset", 
        column_name="Question Set*", 
        widget=QsetFKW(QuestionSet, "qsetname"),
        default=get_or_create_none_qset
    )
    EXPTIME = fields.Field(attribute="expirytime", column_name="Expiry Time*", default=15)
    BELONGSTO = fields.Field(
        attribute="parent", 
        column_name="Belongs To*", 
        widget=ParentFKW(Job, "jobname")
    )

    class Meta:
        model = Job
        skip_unchanged = True
        import_id_fields = []
        report_skipped = True
        fields = [
            "CLIENT", "SITE", "SEQNO", "ASSET", "QSET", "EXPTIME", "BELONGSTO"
        ]
        exclude = [
            "id", "cdtz", "mdtz", "cuser", "muser", "tenant", "lastgeneratedon"
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_superuser = kwargs.pop("is_superuser", None)
        self.request = kwargs.pop("request", None)
        self.ctzoffset = kwargs.pop("ctzoffset", -1)

    def before_import_row(self, row, row_number, **kwargs):
        self.check_required_fields(row)
        self.validate_row(row)
        self.check_parent_exists(row)
        # Store row for before_save_instance
        self._current_row = row
        super().before_import_row(row, **kwargs)

    def check_required_fields(self, row):
        """Validate all required checkpoint fields"""
        required_fields = [
            "Seq No*", "Asset/Checkpoint*", "Question Set*", 
            "Expiry Time*", "Belongs To*", "Client*", "Site*"
        ]
        
        for field in required_fields:
            value = row.get(field)
            if field == "Seq No*":
                try:
                    seq_value = int(value)
                    if seq_value <= 0:
                        raise ValidationError({field: f"{field} must be a positive integer"})
                except (ValueError, TypeError):
                    raise ValidationError({field: f"{field} must be a valid positive integer"})
            elif field == "Expiry Time*":
                try:
                    exp_value = int(value)
                    if exp_value <= 0:
                        raise ValidationError({field: f"{field} must be a positive integer (minutes)"})
                except (ValueError, TypeError):
                    raise ValidationError({field: f"{field} must be a valid positive integer"})
            elif value in [None, "", "NONE"]:
                raise ValidationError({field: f"{field} is required"})

    def validate_row(self, row):
        """Clean and validate row data"""
        # Clean sequence number
        try:
            row["Seq No*"] = int(row["Seq No*"])
        except (ValueError, TypeError):
            raise ValidationError({"Seq No*": "Sequence number must be a valid integer"})
        
        # Clean expiry time
        try:
            row["Expiry Time*"] = int(row["Expiry Time*"])
        except (ValueError, TypeError):
            raise ValidationError({"Expiry Time*": "Expiry time must be a valid integer (minutes)"})

    def check_parent_exists(self, row):
        """Validate that parent tour exists and is enabled"""
        try:
            parent_tour = Job.objects.filter(
                Q(parent__isnull=True) | Q(parent_id=1),  # Unified parent handling (must be first)
                jobname=row['Belongs To*'],
                client__bucode=row['Client*'],
                bu__bucode=row['Site*'],
                identifier='INTERNALTOUR',
                enable=True   # Must be enabled
            ).first()

            if not parent_tour:
                raise Job.DoesNotExist
            # Store parent reference for before_save_instance
            row['_parent_tour'] = parent_tour
        except Job.DoesNotExist:
            raise ValidationError({
                'Belongs To*': f"Enabled top-level parent tour '{row['Belongs To*']}' not found for client '{row['Client*']}' and site '{row['Site*']}'. Please ensure the tour exists and is enabled."
            })

    def before_save_instance(self, instance, row, **kwargs):
        """Set up checkpoint-specific instance data with comprehensive null handling"""
        # Import moved to top of file
        
        # Set identifier for checkpoint (System Field Default)
        instance.identifier = 'INTERNALTOUR'
        
        # Set parent from validation - with safety fallback
        parent_tour = None
        if hasattr(self, '_current_row') and '_parent_tour' in self._current_row:
            parent_tour = self._current_row['_parent_tour']
        elif instance.parent:
            parent_tour = instance.parent
        
        # Ensure parent is set
        instance.parent = parent_tour
        
        # Parent Inheritance Defaults (14 Fields) - Copy from parent tour
        if parent_tour:
            # Basic job information
            instance.jobname = parent_tour.jobname  # Same name as parent tour
            
            # Assignment and priority inheritance
            instance.people = parent_tour.people if parent_tour.people else None
            instance.pgroup = parent_tour.pgroup if parent_tour.pgroup else None
            instance.priority = parent_tour.priority if parent_tour.priority else 'MEDIUM'
            instance.ticketcategory = parent_tour.ticketcategory if parent_tour.ticketcategory else None
            
            # Scheduling fields inheritance  
            instance.planduration = parent_tour.planduration if parent_tour.planduration else 0
            instance.gracetime = parent_tour.gracetime if parent_tour.gracetime else 0
            instance.cron = parent_tour.cron if parent_tour.cron else '* * * * *'
            instance.fromdate = parent_tour.fromdate if parent_tour.fromdate else None
            instance.uptodate = parent_tour.uptodate if parent_tour.uptodate else None
            instance.scantype = parent_tour.scantype if parent_tour.scantype else 'QR'
            
            # JSON metadata inheritance with null safety
            if parent_tour.other_info and isinstance(parent_tour.other_info, dict):
                instance.other_info = parent_tour.other_info.copy()
            else:
                instance.other_info = {'isdynamic': False, 'istimebound': False}
        else:
            # Fallback defaults if no parent found
            instance.jobname = "Unknown Checkpoint"
            instance.priority = 'MEDIUM'
            instance.scantype = 'QR'
            instance.planduration = 0
            instance.gracetime = 0
            instance.cron = '* * * * *'
            instance.other_info = {'isdynamic': False, 'istimebound': False}
        
        # Generated Description Logic with null safety
        if parent_tour and instance.asset and instance.qset:
            # Check if parent description already contains site name
            if instance.bu and hasattr(instance.bu, 'buname') and parent_tour.jobdesc:
                if instance.bu.buname not in parent_tour.jobdesc:
                    base_desc = f"{instance.bu.buname} :: {parent_tour.jobdesc}"
                else:
                    base_desc = parent_tour.jobdesc
            else:
                base_desc = parent_tour.jobdesc if parent_tour.jobdesc else parent_tour.jobname
            
            # Add question set name
            qset_name = instance.qset.qsetname if hasattr(instance.qset, 'qsetname') else 'Unknown Question Set'
            instance.jobdesc = f"{base_desc} :: {qset_name}"
        else:
            # Fallback description if components are missing
            instance.jobdesc = "Checkpoint"
        
        # Instance-Level System Defaults (6 Fields)
        if not hasattr(instance, 'starttime') or not instance.starttime:
            instance.starttime = time(0, 0, 0)  # Start time (00:00:00)
        if not hasattr(instance, 'endtime') or not instance.endtime:
            instance.endtime = time(0, 0, 0)  # End time (00:00:00)
        
        # Foreign Key System Defaults with try/except for safety
        if not hasattr(instance, 'geofence_id') or not instance.geofence_id:
            try:
                instance.geofence = get_or_create_none_gf()
            except (DatabaseError, OperationalError, ObjectDoesNotExist, ValidationError, AttributeError) as e:
                logger.warning(f"Failed to create default geofence object: {e}")
                instance.geofence_id = 1  # Default geofence ID
        
        if not hasattr(instance, 'sgroup_id') or not instance.sgroup_id:
            instance.sgroup_id = 1  # Default site group ID
        
        if not hasattr(instance, 'shift_id') or not instance.shift_id:
            instance.shift_id = 1  # Default shift ID
        
        if not hasattr(instance, 'tenant_id') or not instance.tenant_id:
            try:
                instance.tenant = get_or_create_none_tenant()
            except (DatabaseError, OperationalError, ObjectDoesNotExist, ValidationError, AttributeError) as e:
                logger.warning(f"Failed to create default tenant object: {e}")
                instance.tenant_id = 1  # Default tenant ID
        
        utils.save_common_stuff(self.request, instance, self.is_superuser, self.ctzoffset)