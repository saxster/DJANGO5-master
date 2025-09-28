import graphene
from apps.work_order_management.models import Wom, Approver
from apps.service.types import GetPdfUrl, SelectOutputType
from graphql import GraphQLError
from background_tasks.tasks import (
    send_email_notification_for_workpermit_approval,
    send_email_notification_for_vendor_and_security_after_approval,
)
from apps.work_order_management.utils import check_all_approved, check_all_verified
from apps.work_order_management.models import Wom
from apps.onboarding.models import Bt
from apps.work_order_management.views import WorkPermit
from apps.work_order_management.utils import save_pdf_to_tmp_location
from apps.work_order_management.utils import reject_workpermit
from apps.activity.models.question_model import QuestionSet
from apps.work_order_management.models import Vendor
from apps.peoples.models import People
from logging import getLogger
from apps.core import utils
from pydantic import ValidationError
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import PermissionDenied
from apps.service.pydantic_schemas.workpermit_schema import (
    WomPdfUrlSchema,
    WomRecordSchema,
    ApproveWorkpermitSchema,
    RejectWorkpermitSchema,
    ApproverSchema,
    VendorSchema,
)
from apps.service.decorators import require_authentication, require_tenant_access, require_permission

log = getLogger("mobile_service_log")


class WorkPermitQueries(graphene.ObjectType):
    get_pdf_url = graphene.Field(
        GetPdfUrl, 
        wom_uuid=graphene.String(required=True, description="Wom uuid"),
        peopleid=graphene.Int(required=True, description="People id")
    )

    get_wom_records = graphene.Field(
        SelectOutputType, 
        workpermit=graphene.String(required=True, description="Workpermit"),
        peopleid=graphene.Int(required=True, description="People id"),
        buid=graphene.Int(description="Bu id"),
        parentid=graphene.Int(description="Parent id"),
        clientid=graphene.Int(description="Client id"),
        fromdate=graphene.String(required=True, description="From date"),
        todate=graphene.String(required=True, description="To date")
    )

    get_approve_workpermit = graphene.Field(
        SelectOutputType, 
        peopleid=graphene.Int(required=True, description="People id"),
        identifier=graphene.String(required=True, description="Identifier"),
        wom_uuid=graphene.String(required=True, description="Wom uuid")
    )

    get_reject_workpermit = graphene.Field(
        SelectOutputType, 
        peopleid=graphene.Int(required=True, description="People id"),
        identifier=graphene.String(required=True, description="Identifier"),
        wom_uuid=graphene.String(required=True, description="Wom uuid")
    )

    get_approvers = graphene.Field(
        SelectOutputType, 
        buid=graphene.Int(required=True, description="Bu id"),
        clientid=graphene.Int(required=True, description="Client id")
    )

    get_vendors = graphene.Field(
        SelectOutputType, 
        clientid=graphene.Int(required=True, description="Client id"),
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        buid=graphene.Int(required=True, description="Bu id"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset")
    )

    @staticmethod
    @require_tenant_access
    def resolve_get_vendors(self, info, clientid, mdtz, buid, ctzoffset):
        try:
            log.info("request for get_vendors")
            filter_data = {'clientid': clientid, 'mdtz': mdtz, 'buid': buid, 'ctzoffset': ctzoffset}
            validated = VendorSchema(**filter_data)
            data = Vendor.objects.get_vendors_for_mobile(
                info.context,
                buid=validated.buid,
                mdtz=validated.mdtz,
                ctzoffset=validated.ctzoffset,
                clientid=validated.clientid,
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_vendors", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Vendor.DoesNotExist:
            log.warning("Vendors not found")
            raise GraphQLError("Vendors not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_vendors", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
    def resolve_get_approvers(self, info, buid, clientid):
        try:
            log.info("request for get_approver")
            filter_data = {'buid': buid, 'clientid': clientid}
            validated = ApproverSchema(**filter_data)
            data = Approver.objects.get_approver_list_for_mobile(
                validated.buid, validated.clientid
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_approvers", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Approver.DoesNotExist:
            log.warning("Approvers not found")
            raise GraphQLError("Approvers not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_approvers", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_permission('can_approve_work_permits')
    def resolve_approve_workpermit(self, info, peopleid, identifier, wom_uuid):
        try:
            log.info("request for change wom status")
            filter_data = {'peopleid': peopleid, 'identifier': identifier, 'wom_uuid': wom_uuid}
            validated = ApproveWorkpermitSchema(**filter_data)
            wom = Wom.objects.get(uuid=validated.wom_uuid)
            sitename = Bt.objects.get(id=wom.bu_id).buname
            workpermit_status = wom.workstatus
            wp_approvers = wom.other_data["wp_approvers"]
            approvers = [approver["name"] for approver in wp_approvers]
            approvers_code = [approver["peoplecode"] for approver in wp_approvers]
            vendor_name = Vendor.objects.get(id=wom.vendor.id).name
            client_id = wom.client.id
            permit_name = QuestionSet.objects.get(id=wom.qset.id).qsetname
            report_object = WorkPermit.get_report_object(wom, permit_name)
            report = report_object(
                filename=permit_name,
                client_id=wom.client_id,
                returnfile=True,
                formdata={"id": wom.id},
                request=None,
            )
            report_pdf_object = report.execute()
            permit_no = wom.other_data["wp_seqno"]
            pdf_path = save_pdf_to_tmp_location(
                report_pdf_object,
                report_name=permit_name,
                report_number=wom.other_data["wp_seqno"],
            )
            if validated.identifier == "APPROVER":
                p = People.objects.filter(id=validated.peopleid).first()
                if is_all_approved := check_all_approved(
                    validated.wom_uuid, p.peoplecode
                ):
                    log.info(f"Is all approved in side of if: {is_all_approved}")
                    updated = Wom.objects.filter(uuid=validated.wom_uuid).update(
                        workpermit=Wom.WorkPermitStatus.APPROVED.value
                    )
                if is_all_approved:
                    workpermit_status = "APPROVED"
                    Wom.objects.filter(id=wom.id).update(
                        workstatus=Wom.Workstatus.INPROGRESS.value
                    )
                    permit_name = QuestionSet.objects.get(id=wom.qset.id).qsetname
                    report_object = WorkPermit.get_report_object(wom, permit_name)
                    report = report_object(
                        filename=permit_name,
                        client_id=wom.client_id,
                        returnfile=True,
                        formdata={"id": wom.id},
                        request=None,
                    )
                    report_pdf_object = report.execute()
                    permit_no = wom.other_data["wp_seqno"]
                    pdf_path = save_pdf_to_tmp_location(
                        report_pdf_object,
                        report_name=permit_name,
                        report_number=wom.other_data["wp_seqno"],
                    )
                    send_email_notification_for_vendor_and_security_after_approval.delay(
                        wom.id,
                        sitename,
                        workpermit_status,
                        vendor_name,
                        pdf_path,
                        permit_name,
                        permit_no,
                    )
                    pass
                rc, msg = 0, "success"
            else:
                p = People.objects.filter(id=validated.peopleid).first()
                if is_all_verified := check_all_verified(
                    validated.wom_uuid, p.peoplecode
                ):
                    updated = Wom.objects.filter(uuid=validated.wom_uuid).update(
                        verifiers_status=Wom.WorkPermitStatus.APPROVED.value
                    )
                if is_all_verified:
                    send_email_notification_for_workpermit_approval.delay(
                        wom.id,
                        approvers,
                        approvers_code,
                        sitename,
                        workpermit_status,
                        permit_name,
                        pdf_path,
                        vendor_name,
                        client_id,
                    )
                    # Sending Email to Approver
                rc, msg = 0, "success"
        except ValidationError as ve:
            log.error("Validation error in approve_workpermit", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Wom.DoesNotExist:
            log.error("Work permit not found")
            rc, msg = 1, "Work permit not found"
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in approve_workpermit", exc_info=True)
            rc, msg = 1, "Database operation failed"
        except (IOError, OSError) as e:
            log.error("PDF generation error in approve_workpermit", exc_info=True)
            rc, msg = 1, "PDF generation failed"
        return SelectOutputType(nrows=rc, records=msg)

    @staticmethod
    @require_permission('can_approve_work_permits')
    def resolve_reject_workpermit(self, info, peopleid, identifier, wom_uuid):
        try:
            log.info("request for change wom status")
            filter_data = {'peopleid': peopleid, 'identifier': identifier, 'wom_uuid': wom_uuid}
            validated = RejectWorkpermitSchema(**filter_data)
            p = People.objects.filter(id=validated.peopleid).first()
            Wom.objects.filter(uuid=validated.wom_uuid).update(
                workpermit=Wom.WorkPermitStatus.REJECTED.value
            )
            reject_workpermit(validated.wom_uuid, p.peoplecode)
            rc, msg = 0, "success"
        except ValidationError as ve:
            log.error("Validation error in reject_workpermit", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Wom.DoesNotExist:
            log.error("Work permit not found")
            rc, msg = 1, "Work permit not found"
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in reject_workpermit", exc_info=True)
            rc, msg = 1, "Database operation failed"
        return SelectOutputType(nrows=rc, records=msg)

    @staticmethod
    @require_authentication
    def resolve_get_wom_records(self, info, workpermit, peopleid, fromdate, todate, buid=None, parentid=None, clientid=None):
        try:
            log.info("request for get_wom_records")
            filter_data = {'workpermit': workpermit, 'peopleid': peopleid, 'fromdate': fromdate, 'todate': todate, 'buid': buid, 'parentid': parentid, 'clientid': clientid}
            validated = WomRecordSchema(**filter_data)
            data = Wom.objects.get_wom_records_for_mobile(
                fromdate=validated.fromdate,
                todate=validated.todate,
                peopleid=validated.peopleid,
                workpermit=validated.workpermit,
                buid=validated.buid,
                clientid=validated.clientid,
                parentid=validated.parentid,
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_wom_records", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Wom.DoesNotExist:
            log.warning("Work permit records not found")
            raise GraphQLError("Work permit records not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_wom_records", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_authentication
    def resolve_get_pdf_url(self, info, wom_uuid, peopleid):
        import os
        from intelliwiz_config import settings
        from urllib.parse import urljoin
        from apps.work_order_management.utils import (
            save_pdf_to_tmp_location,
            get_report_object,
        )
        from apps.activity.models.question_model import QuestionSet

        try:
            filter_data = {'wom_uuid': wom_uuid, 'peopleid': peopleid}
            validated = WomPdfUrlSchema(**filter_data)
            wom = Wom.objects.get(uuid=validated.wom_uuid)
            permit_name = QuestionSet.objects.get(id=wom.qset.id).qsetname
            permit_no = wom.other_data["wp_seqno"]
            client_id = wom.client.id
            report_obj = get_report_object(permit_name)
            report = report_obj(
                filename=permit_name,
                client_id=client_id,
                returnfile=True,
                formdata={"id": wom.id},
                request=None,
            )
            report_pdf_object = report.execute()
            pdf_path = save_pdf_to_tmp_location(
                report_pdf_object, report_name=permit_name, report_number=permit_no
            )
            file_url = urljoin(settings.MEDIA_URL, pdf_path.split("/")[-1])
            full_url = os.path.join(settings.MEDIA_ROOT, file_url)
            return GetPdfUrl(url=full_url)
        except ValidationError as ve:
            log.error("Validation error in get_pdf_url", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Wom.DoesNotExist:
            log.error("Work permit not found for PDF generation")
            raise GraphQLError("Work permit not found")
        except (IOError, OSError) as e:
            log.error("PDF generation or file error", exc_info=True)
            raise GraphQLError("PDF generation failed")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_pdf_url", exc_info=True)
            raise GraphQLError("Database operation failed")
