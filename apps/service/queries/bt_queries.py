import graphene
from apps.onboarding.models import GeofenceMaster, Shift, DownTimeHistory
from apps.activity.models.location_model import Location
from apps.peoples.models import Pgbelonging, Pgroup, People
from apps.attendance.models import PeopleEventlog
from graphql.error import GraphQLError
from apps.service.pydantic_schemas.bt_schema import (
    LocationSchema,
    GeofenceSchema,
    ShiftSchema,
    GroupsModifiedAfterSchema,
    SiteListSchema,
    SendEmailVerificationLinkSchema,
    SuperAdminMessageSchema,
    SiteVisitedLogSchema,
    VerifyClientSchema,
)
from apps.service.types import SelectOutputType, VerifyClientOutput, BasicOutput
from logging import getLogger
from apps.core import utils
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import PermissionDenied
from apps.service.types import DowntimeResponse
import json
from pydantic import ValidationError
from apps.service.decorators import require_authentication, require_tenant_access


log = getLogger("mobile_service_log")


class BtQueries(graphene.ObjectType):
    get_locations = graphene.Field(
        SelectOutputType, 
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset"),
        buid=graphene.Int(required=True, description="Business unit id")
    )

    get_groupsmodifiedafter = graphene.Field(
        SelectOutputType, 
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset"),
        buid=graphene.Int(required=True, description="Business unit id")
    )

    get_gfs_for_siteids = graphene.Field(
        SelectOutputType, 
        siteids=graphene.List(graphene.Int, required=True, description="List of site ids")
    )

    get_shifts = graphene.Field(
        SelectOutputType, 
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        buid=graphene.Int(required=True, description="Business unit id"),
        clientid=graphene.Int(required=True, description="Client id")
    )

    getsitelist = graphene.Field(
        SelectOutputType, 
        clientid=graphene.Int(required=True, description="Client id"),
        peopleid=graphene.Int(required=True, description="People id")
    )
    send_email_verification_link = graphene.Field(
        BasicOutput, 
        clientcode=graphene.String(required=True, description="Client code"),
        loginid=graphene.String(required=True, description="Login id")
    )
    get_superadmin_message = graphene.Field(
        SelectOutputType, 
        client_id=graphene.Int(required=True, description="Client id")
    )
    get_site_visited_log = graphene.Field(
        SelectOutputType, 
        ctzoffset=graphene.Int(required=True, description="Client timezone offset"),
        clientid=graphene.Int(required=True, description="Client id"),
        peopleid=graphene.Int(required=True, description="People id")
    )

    verifyclient = graphene.Field(
        VerifyClientOutput, 
        clientcode=graphene.String(required=True, description="Client code")
    )

    @staticmethod
    def resolve_verifyclient(self, info, clientcode):
        try:
            log.info("request for verifyclient")
            filter_data = {'clientcode': clientcode}
            validated = VerifyClientSchema(**filter_data)
            url = utils.get_appropriate_client_url(validated.clientcode)
            if not url:
                raise ValueError
            return VerifyClientOutput(msg="VALID", url=url)
        except ValueError as e:
            log.error(f"url not found for the specified {validated.clientcode=}")
            return VerifyClientOutput(msg="INVALID", url=None, rc=1)
        except ValidationError as ve:
            log.error("Validation error in verifyclient", exc_info=True)
            raise GraphQLError(f"Invalid client code: {str(ve)}")
        except (IOError, OSError) as e:
            log.error("File or network error in verifyclient", exc_info=True)
            return VerifyClientOutput(msg="INVALID", url=None, rc=1)

    @staticmethod
    @require_tenant_access
    def resolve_get_locations(self, info, mdtz, ctzoffset, buid):
        try:
            log.info("request for get_locations")
            filter_data = {'mdtz': mdtz, 'ctzoffset': ctzoffset, 'buid': buid}
            validated = LocationSchema(**filter_data)
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz, offset=validated.ctzoffset
            )
            data = Location.objects.get_locations_modified_after(
                mdtzinput, validated.buid, validated.ctzoffset
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_locations", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Location.DoesNotExist:
            log.warning("Locations not found")
            raise GraphQLError("Locations not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_locations", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
    def resolve_get_groupsmodifiedafter(self, info, mdtz, ctzoffset, buid):
        try:
            log.info("request for get_groupsmodifiedafter")
            filter_data = {'mdtz': mdtz, 'ctzoffset': ctzoffset, 'buid': buid}
            validated = GroupsModifiedAfterSchema(**filter_data)
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz, offset=validated.ctzoffset
            )
            data = Pgroup.objects.get_groups_modified_after(mdtzinput, validated.buid)
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_groupsmodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Pgroup.DoesNotExist:
            log.warning("Groups not found")
            raise GraphQLError("Groups not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_groupsmodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_authentication
    def resolve_get_gfs_for_siteids(self, info, siteids):
        try:
            log.info("request for get_gfs_for_siteids")
            filter_data = {'siteids': siteids}
            validated = GeofenceSchema(**filter_data)
            data = GeofenceMaster.objects.get_gfs_for_siteids(validated.siteids)
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_gfs_for_siteids", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except GeofenceMaster.DoesNotExist:
            log.warning("Geofences not found")
            raise GraphQLError("Geofences not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_gfs_for_siteids", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
    def resolve_get_shifts(self, info, mdtz, buid, clientid):
        try:
            log.info("request for get_shifts")
            filter_data = {'mdtz': mdtz, 'buid': buid, 'clientid': clientid}
            validated = ShiftSchema(**filter_data)
            data = Shift.objects.get_shift_data(
                validated.buid, validated.clientid, validated.mdtz
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_shifts", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Shift.DoesNotExist:
            log.warning("Shifts not found")
            raise GraphQLError("Shifts not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_shifts", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
    def resolve_getsitelist(self, info, clientid, peopleid):
        try:
            log.info("request for getsitelist")
            filter_data = {'clientid': clientid, 'peopleid': peopleid}
            validated = SiteListSchema(**filter_data)
            data = Pgbelonging.objects.get_assigned_sites_to_people(
                validated.peopleid, forservice=True
            )
            for i in range(len(data)):
                data[i]["bupreferences"] = json.dumps(data[i]["bupreferences"])
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in getsitelist", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Pgbelonging.DoesNotExist:
            log.warning("Site list not found")
            raise GraphQLError("Site assignments not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in getsitelist", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    def resolve_send_email_verification_link(self, info, clientcode, loginid):
        try:
            log.info("request for send_email_verification_link")
            from django_email_verification import send_email

            filter_data = {'clientcode': clientcode, 'loginid': loginid}
            validated = SendEmailVerificationLinkSchema(**filter_data)
            user = People.objects.filter(
                loginid=validated.loginid, client__bucode=validated.clientcode
            ).first()
            if user:
                send_email(user, info.context)
                rc, msg = 0, "Success"
            else:
                rc, msg = 1, "Failed"
        except ValidationError as ve:
            log.error("Validation error in send_email_verification_link", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except People.DoesNotExist:
            log.warning("User not found for email verification")
            rc, msg = 1, "User not found"
        except (IOError, OSError) as e:
            log.error("Email service error", exc_info=True)
            rc, msg = 1, "Email service unavailable"
        return BasicOutput(rc=rc, msg=msg, email=user.email)

    @staticmethod
    @require_authentication
    def resolve_get_superadmin_message(self, info, client_id):
        try:
            log.info("request for get_superadmin_message")
            filter_data = {'client_id': client_id}
            validated = SuperAdminMessageSchema(**filter_data)
            record = (
                DownTimeHistory.objects.filter(client_id=validated.client_id)
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
        except ValidationError as ve:
            log.error("Validation error in get_superadmin_message", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except DownTimeHistory.DoesNotExist:
            log.warning("No downtime message found")
            return DowntimeResponse(message="")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_superadmin_message", exc_info=True)
            raise GraphQLError("Database operation failed")
        except (TypeError, KeyError) as e:
            log.error("Data format error in get_superadmin_message", exc_info=True)
            return DowntimeResponse(message="")

    @staticmethod
    @require_tenant_access
    def resolve_get_site_visited_log(self, info, ctzoffset, clientid, peopleid):
        try:
            log.info("request for get_site_visited_log")
            filter_data = {'ctzoffset': ctzoffset, 'clientid': clientid, 'peopleid': peopleid}
            validated = SiteVisitedLogSchema(**filter_data)
            data = PeopleEventlog.objects.get_sitevisited_log(
                validated.clientid, validated.peopleid, validated.ctzoffset
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_site_visited_log", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except PeopleEventlog.DoesNotExist:
            log.warning("Site visit log not found")
            raise GraphQLError("Site visit log not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_site_visited_log", exc_info=True)
            raise GraphQLError("Database operation failed")
