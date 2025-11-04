"""
Work Permit Service Layer

Business logic for work permit operations, extracted from WorkPermit view.

Classes:
    - WorkPermitService: Service layer for work permit operations

Methods:
    - create_child_wom: Creates hierarchical WOM records for multi-section permits
    - create_workpermit_details: Processes and saves questionnaire answers
    - get_report_object: Maps permit names to PDF report classes
    - send_report: Generates work permit PDF reports

Created: October 2025
Extracted from: work_order_management/views.py (WorkPermit class helper methods)
Compliance: CLAUDE.md service layer pattern (<150 lines per class)
"""

import logging
from django.http import QueryDict
from apps.work_order_management.models import Wom, WomDetails
from apps.activity.models.question_model import QuestionSetBelonging, QuestionSet

logger = logging.getLogger("django")


class WorkPermitService:
    """
    Business logic service for work permit operations.

    Extracted from WorkPermit view class to comply with CLAUDE.md
    architectural limits and Single Responsibility Principle.
    """

    @staticmethod
    def create_child_wom(wom, qset_id, rwp_seqno=None):
        """
        Create or retrieve child WOM record for hierarchical work permits.

        Work permits can have multiple sections (questionnaire sets),
        each stored as a separate child WOM record linked to parent.

        Args:
            wom: Parent Wom instance
            qset_id: QuestionSet ID for this section
            rwp_seqno: Optional sequence number for return work permits

        Returns:
            Wom: Child WOM instance (existing or newly created)

        Note:
            Idempotent - returns existing child if already created
        """
        qset = QuestionSet.objects.get(id=qset_id)

        # Check if child WOM already exists
        if childwom := Wom.objects.filter(
            parent_id=wom.id, qset_id=qset.id, seqno=rwp_seqno or qset.seqno
        ).first():
            logger.info(f"wom already exist with qset_id {qset_id} so returning it")
            return childwom

        # Create new child WOM
        logger.info(f"creating wom for qset_id {qset_id}")
        return Wom.objects.create(
            parent_id=wom.id,
            description=qset.qsetname,
            plandatetime=wom.plandatetime,
            expirydatetime=wom.expirydatetime,
            starttime=wom.starttime,
            gpslocation=wom.gpslocation,
            asset=wom.asset,
            location=wom.location,
            workstatus=wom.workstatus,
            seqno=rwp_seqno or qset.seqno,
            approvers=wom.approvers,
            verifiers=wom.verifiers,
            workpermit=wom.workpermit,
            priority=wom.priority,
            vendor=wom.vendor,
            client=wom.client,
            bu=wom.bu,
            ticketcategory=wom.ticketcategory,
            other_data=wom.other_data,
            qset=qset,
            cuser=wom.cuser,
            muser=wom.muser,
            ctzoffset=wom.ctzoffset,
        )

    @staticmethod
    def create_workpermit_details(R, wom, request, formdata, rwp_seqno=None):
        """
        Process and save work permit questionnaire answers.

        Handles multi-section questionnaires with alert detection for:
        - CHECKBOX/DROPDOWN: Alert if value matches alerton list
        - MULTISELECT: Alert if any selected value in alerton list
        - NUMERIC: Alert if value outside min/max range

        Args:
            R: POST data dictionary
            wom: Parent Wom instance
            request: Django request object
            formdata: QueryDict with questionnaire answers
            rwp_seqno: Optional sequence number for return work permits

        Creates:
            - Child WOM records for each section (via create_child_wom)
            - WomDetails records for each answer
        """
        logger.info(f"creating wp_details started {R}")

        for k, v in formdata.items():
            # Skip non-question fields
            if (
                k not in ["ctzoffset", "wom_id", "action", "csrfmiddlewaretoken"]
                and "_" in k
            ):
                logger.info(f"Processing field: {k} = {v}")

                # Parse field key: "<qsb_id>_<qset_id>"
                ids = k.split("_")
                qsb_id = ids[0]
                qset_id = ids[1]
                logger.info(f"Parsed IDs: qsb_id={qsb_id}, qset_id={qset_id}")

                # Get question configuration
                qsb_obj = QuestionSetBelonging.objects.filter(id=qsb_id).first()

                # Determine if answer triggers alert
                if qsb_obj.answertype in ["CHECKBOX", "DROPDOWN"]:
                    alerts = (qsb_obj.alerton and v in qsb_obj.alerton) or False

                elif qsb_obj.answertype == "MULTISELECT":
                    selected_values = formdata.getlist(k)
                    if selected_values:
                        if qsb_obj.alerton:
                            alerts = any(
                                value in qsb_obj.alerton for value in selected_values
                            )
                        else:
                            alerts = False
                        v = ",".join(selected_values)
                    else:
                        alerts = False
                        v = ""

                elif qsb_obj.answertype in ["NUMERIC"] and len(qsb_obj.alerton) > 0:
                    alerton = (
                        qsb_obj.alerton.replace(">", "").replace("<", "").split(",")
                    )
                    if len(alerton) > 1:
                        _min, _max = alerton[0], alerton[1]
                        alerts = float(v) < float(_min) or float(v) > float(_max)
                else:
                    alerts = False

                # Create or get child WOM for this section
                childwom = WorkPermitService.create_child_wom(
                    wom, qset_id, rwp_seqno=rwp_seqno
                )

                # Create detail record
                lookup_args = {
                    "wom_id": childwom.id,
                    "question_id": qsb_obj.question_id,
                    "qset_id": qset_id,
                }
                default_data = {
                    "seqno": qsb_obj.seqno,
                    "answertype": qsb_obj.answertype,
                    "answer": v,
                    "isavpt": qsb_obj.isavpt,
                    "options": qsb_obj.options,
                    "min": qsb_obj.min,
                    "max": qsb_obj.max,
                    "alerton": qsb_obj.alerton,
                    "ismandatory": qsb_obj.ismandatory,
                    "alerts": alerts,
                    "cuser_id": request.user.id,
                    "muser_id": request.user.id,
                }
                data = lookup_args | default_data
                WomDetails.objects.create(**data)
                logger.info(
                    f"wom detail is created for the child wom: {childwom.description}"
                )

    @staticmethod
    def get_report_object(permit_name):
        """
        Map work permit name to corresponding PDF report class.

        Args:
            permit_name: Work permit type name

        Returns:
            Report class for PDF generation

        Supported permit types:
            - Cold Work Permit
            - Hot Work Permit
            - Confined Space Work Permit
            - Electrical Work Permit
            - Height Work Permit
            - Entry Request
        """
        from apps.reports.report_designs import workpermit as wp

        return {
            "Cold Work Permit": wp.ColdWorkPermit,
            "Hot Work Permit": wp.HotWorkPermit,
            "Confined Space Work Permit": wp.ConfinedSpaceWorkPermit,
            "Electrical Work Permit": wp.ElectricalWorkPermit,
            "Height Work Permit": wp.HeightWorkPermit,
            "Entry Request": wp.EntryRequest,
        }.get(permit_name)

    @staticmethod
    def get_report_format_by_type(R):
        """
        Get report format based on questionnaire set name.

        Args:
            R: Request data dictionary with qset__qsetname

        Returns:
            Report class for PDF generation

        Note:
            Alternative method to get_report_object using qset name
        """
        from apps.reports.report_designs import workpermit as wp

        return {
            "Cold Work Permit": wp.ColdWorkPermit,
            "Hot Work Permit": wp.HotWorkPermit,
            "Confined Space Work Permit": wp.ConfinedSpaceWorkPermit,
            "Electrical Work Permit": wp.ElectricalWorkPermit,
            "Height Work Permit": wp.HeightWorkPermit,
            "Entry Request": wp.EntryRequest,
        }.get(R["qset__qsetname"])

    @staticmethod
    def send_report(R, request):
        """
        Generate work permit PDF report.

        Args:
            R: Request data with qset__qsetname
            request: Django request object with session data

        Returns:
            PDF report bytes
        """
        ReportFormat = WorkPermitService.get_report_format_by_type(R)
        report = ReportFormat(
            filename=R["qset__qsetname"],
            client_id=request.session["client_id"],
            formdata=R,
            request=request,
        )
        return report.execute()

    @staticmethod
    def generate_pdf_url(wom_uuid, user_id):
        """
        Generate PDF URL for work permit.

        Args:
            wom_uuid: Work permit UUID
            user_id: User ID requesting the PDF

        Returns:
            str: Full URL to PDF file

        Raises:
            Wom.DoesNotExist: If work permit not found
            IOError: If PDF generation fails
        """
        import os
        from intelliwiz_config import settings
        from urllib.parse import urljoin
        from apps.work_order_management.utils import (
            save_pdf_to_tmp_location,
            get_report_object,
        )
        from apps.activity.models.question_model import QuestionSet

        wom = Wom.objects.get(uuid=wom_uuid)
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

        return full_url

    @staticmethod
    def approve_work_permit(wom_uuid, people_id, identifier):
        """
        Approve work permit.

        Args:
            wom_uuid: Work permit UUID
            people_id: ID of person approving
            identifier: "APPROVER" or "VERIFIER"

        Returns:
            dict: Result with success status and message

        Raises:
            Wom.DoesNotExist: If work permit not found
            ValidationError: If approval validation fails
        """
        from apps.peoples.models import People
        from apps.client_onboarding.models import Bt
        from apps.activity.models.question_model import QuestionSet
        from apps.work_order_management.utils import (
            check_all_approved,
            check_all_verified,
            save_pdf_to_tmp_location,
        )
        from apps.work_order_management.views import WorkPermit
        from background_tasks.tasks import (
            send_email_notification_for_workpermit_approval,
            send_email_notification_for_vendor_and_security_after_approval,
        )

        wom = Wom.objects.get(uuid=wom_uuid)
        p = People.objects.filter(id=people_id).first()
        sitename = Bt.objects.get(id=wom.bu_id).buname
        workpermit_status = wom.workstatus
        permit_name = QuestionSet.objects.get(id=wom.qset.id).qsetname

        # Generate PDF
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
            report_number=permit_no,
        )

        if identifier == "APPROVER":
            if is_all_approved := check_all_approved(wom_uuid, p.peoplecode):
                Wom.objects.filter(uuid=wom_uuid).update(
                    workpermit=Wom.WorkPermitStatus.APPROVED.value
                )

            if is_all_approved:
                workpermit_status = "APPROVED"
                Wom.objects.filter(id=wom.id).update(
                    workstatus=Wom.Workstatus.INPROGRESS.value
                )

                vendor_name = Vendor.objects.get(id=wom.vendor.id).name
                send_email_notification_for_vendor_and_security_after_approval.delay(
                    wom.id,
                    sitename,
                    workpermit_status,
                    vendor_name,
                    pdf_path,
                    permit_name,
                    permit_no,
                )

            return {'success': True, 'message': 'Work permit approved successfully'}

        else:  # VERIFIER
            if is_all_verified := check_all_verified(wom_uuid, p.peoplecode):
                Wom.objects.filter(uuid=wom_uuid).update(
                    verifiers_status=Wom.WorkPermitStatus.APPROVED.value
                )

            if is_all_verified:
                wp_approvers = wom.other_data["wp_approvers"]
                approvers = [approver["name"] for approver in wp_approvers]
                approvers_code = [approver["peoplecode"] for approver in wp_approvers]
                vendor_name = Vendor.objects.get(id=wom.vendor.id).name
                client_id = wom.client.id

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

            return {'success': True, 'message': 'Work permit verified successfully'}

    @staticmethod
    def reject_work_permit(wom_uuid, people_id, identifier, reason=''):
        """
        Reject work permit.

        Args:
            wom_uuid: Work permit UUID
            people_id: ID of person rejecting
            identifier: "APPROVER" or "VERIFIER"
            reason: Rejection reason (optional)

        Returns:
            dict: Result with success status and message

        Raises:
            Wom.DoesNotExist: If work permit not found
        """
        from apps.peoples.models import People
        from apps.work_order_management.utils import reject_workpermit

        p = People.objects.filter(id=people_id).first()
        Wom.objects.filter(uuid=wom_uuid).update(
            workpermit=Wom.WorkPermitStatus.REJECTED.value
        )
        reject_workpermit(wom_uuid, p.peoplecode)

        return {'success': True, 'message': 'Work permit rejected'}
