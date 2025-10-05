import graphene
from apps.core import utils
from apps.activity.models.location_model import Location
from apps.onboarding.models import GeofenceMaster, DownTimeHistory, Shift
from apps.peoples.models import Pgbelonging, Pgroup
from apps.attendance.models import PeopleEventlog
from logging import getLogger

from django.utils import timezone

log = getLogger("mobile_service_log")
import json

from .types import VerifyClientOutput, DowntimeResponse, SelectOutputType


class Query(graphene.ObjectType):
    get_locations = graphene.Field(
        SelectOutputType,
        mdtz=graphene.String(required=True),
        ctzoffset=graphene.Int(required=True),
        buid=graphene.Int(required=True),
    )

    get_groupsmodifiedafter = graphene.Field(
        SelectOutputType,
        mdtz=graphene.String(required=True),
        ctzoffset=graphene.Int(required=True),
        buid=graphene.Int(required=True),
    )

    get_gfs_for_siteids = graphene.Field(
        SelectOutputType, siteids=graphene.List(graphene.Int)
    )

    get_shifts = graphene.Field(
        SelectOutputType,
        mdtz=graphene.String(required=True),
        buid=graphene.Int(required=True),
        clientid=graphene.Int(required=True),
    )

    getsitelist = graphene.Field(
        SelectOutputType,
        clientid=graphene.Int(required=True),
        peopleid=graphene.Int(required=True),
    )

    verifyclient = graphene.Field(
        VerifyClientOutput, clientcode=graphene.String(required=True)
    )

    get_superadmin_message = graphene.Field(
        DowntimeResponse, client_id=graphene.Int(required=True)
    )
    get_site_visited_log = graphene.Field(
        SelectOutputType,
        clientid=graphene.Int(required=True),
        peopleid=graphene.Int(required=True),
        ctzoffset=graphene.Int(required=True),
    )

    @staticmethod
    def resolve_get_locations(self, info, mdtz, ctzoffset, buid):
        log.info(
            f"\n\nrequest for location-modified-after inputs : mdtz:{mdtz}, ctzoffset:{ctzoffset}, clientid:{buid}"
        )
        mdtzinput = utils.getawaredatetime(mdtz, ctzoffset)
        data = Location.objects.get_locations_modified_after(mdtzinput, buid, ctzoffset)
        # ✅ NEW: Use typed output for Apollo Kotlin codegen
        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(data, 'location')
        log.info(f"{count} objects returned...")
        return SelectOutputType(
            nrows=count,
            records=records_json,  # Deprecated but still works
            records_typed=typed_records,  # NEW: Type-safe
            record_type=record_type,  # NEW: Discriminator
            msg=msg
        )

    @staticmethod
    def resolve_get_groupsmodifiedafter(self, info, mdtz, ctzoffset, buid):
        log.info(
            f"\n\nrequest for groups-modified-after inputs : mdtz:{mdtz}, ctzoffset:{ctzoffset}, buid:{buid}"
        )
        mdtzinput = utils.getawaredatetime(mdtz, ctzoffset)
        data = Pgroup.objects.get_groups_modified_after(mdtzinput, buid)
        # ✅ NEW: Use typed output for Apollo Kotlin codegen
        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(data, 'pgroup')
        log.info(f"{count} objects returned...")
        return SelectOutputType(
            nrows=count,
            records=records_json,
            records_typed=typed_records,
            record_type=record_type,
            msg=msg
        )

    @staticmethod
    def resolve_get_gfs_for_siteids(self, info, siteids):
        log.info(f"\n\nrequest for getgeofence inputs : siteids:{siteids}")
        data = GeofenceMaster.objects.get_gfs_for_siteids(siteids)
        # ✅ NEW: Use typed output (geofence as generic asset-related type)
        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(data, 'location')
        log.info(f"{count} objects returned...")
        return SelectOutputType(
            nrows=count,
            records=records_json,
            records_typed=typed_records,
            record_type=record_type,
            msg=msg
        )

    @staticmethod
    def resolve_getsitelist(self, info, clientid, peopleid):
        log.info(
            f"\n\nrequest for sitelis inputs : clientid:{clientid}, peopleid:{peopleid}"
        )
        data = Pgbelonging.objects.get_assigned_sites_to_people(
            peopleid, forservice=True
        )
        # change bupreferences back to json
        for i in range(len(data)):
            data[i]["bupreferences"] = json.dumps(data[i]["bupreferences"])
        # ✅ NEW: Use typed output (pgbelonging as location-related type)
        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(data, 'location')
        log.info(f"{count} objects returned...")
        return SelectOutputType(
            nrows=count,
            records=records_json,
            records_typed=typed_records,
            record_type=record_type,
            msg=msg
        )

    @staticmethod
    def resolve_verifyclient(self, info, clientcode):
        try:
            url = utils.get_appropriate_client_url(clientcode)
            if not url:
                raise ValueError
            return VerifyClientOutput(msg="VALID", url=url)
        except ValueError as e:
            log.error(f"url not found for the specified {clientcode=}")
            return VerifyClientOutput(msg="INVALID", url=None, rc=1)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as ex:
            log.critical("something went wrong!", exc_info=True)
            return VerifyClientOutput(msg="INVALID", url=None, rc=1)

    def resolve_get_shifts(self, info, buid, clientid, mdtz):
        log.info(f"request get shifts input are: {buid} {clientid}")
        data = Shift.objects.get_shift_data(buid, clientid, mdtz)
        # ✅ NEW: Use typed output for Apollo Kotlin codegen
        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(data, 'typeassist')
        log.info(f"total {count} objects returned")
        return SelectOutputType(
            nrows=count,
            records=records_json,
            records_typed=typed_records,
            record_type=record_type,
            msg=msg
        )

    def resolve_get_superadmin_message(self, info, client_id):
        log.info(f"resolve_get_superadmin_message {client_id = }")
        record = (
            DownTimeHistory.objects.filter(client_id=client_id)
            .values("reason", "starttime", "endtime")
            .order_by("-cdtz")
            .first()
        )
        if timezone.now() < record["endtime"]:
            return DowntimeResponse(
                message=record["reason"],
                startDateTime=record["starttime"],
                endDateTime=record["endtime"],
            )
        else:
            return DowntimeResponse(message="")

    def resolve_get_site_visited_log(self, info, clientid, peopleid, ctzoffset):
        log.info(
            f"resolve_get_sitevisited_log {clientid = } {peopleid = } {ctzoffset = }"
        )
        data = PeopleEventlog.objects.get_sitevisited_log(clientid, peopleid, ctzoffset)
        # ✅ NEW: Use typed output for Apollo Kotlin codegen
        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(data, 'location')
        log.info(f"total {count} objects returned")
        return SelectOutputType(
            nrows=count,
            records=records_json,
            records_typed=typed_records,
            record_type=record_type,
            msg=msg
        )


# NOTE: get_db_rows function has been removed
# All PostgreSQL functions have been migrated to Django ORM
# Direct SQL execution is no longer supported
# Use the Django ORM implementations below instead


def get_externaltouremodifiedafter(peopleid, siteid, clientid):
    """Get external tour job needs using Django ORM."""
    from apps.activity.models.job_model import Jobneed
    from apps.activity.managers.job_manager_orm import JobneedManagerORM
    
    # Use the ORM implementation
    results = JobneedManagerORM.get_external_tour_job_needs(
        Jobneed.objects, peopleid, siteid, clientid
    )
    
    # Convert to expected format
    data_json = json.dumps(results, default=str)
    count = len(results)
    return SelectOutputType(
        records=data_json,
        msg=f"Total {count} records fetched successfully!",
        nrows=count,
    )


def get_assetdetails(mdtz, buid):
    """Get asset details using Django ORM."""
    from apps.activity.managers.asset_manager_orm import AssetManagerORM
    
    # Use the ORM implementation
    results = AssetManagerORM.get_asset_details(mdtz, buid)
    
    # Convert to expected format
    data_json = json.dumps(results, default=str)
    count = len(results)
    return SelectOutputType(
        records=data_json,
        msg=f"Total {count} records fetched successfully!",
        nrows=count,
    )
