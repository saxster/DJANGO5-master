"""
Work Order Management - Work Permit Views

Handles work permit CRUD operations and complex approval workflows.

Classes:
    - WorkPermit: Work permit create, read, update, approve/reject workflows

Refactored: October 2025
Original: work_order_management/views.py:437-954 (517 lines)
After Refactoring: 328 lines (view logic) + 235 lines (service layer)
"""

from .base import (
    LoginRequiredMixin, View, render, transaction, IntegrityError,
    DatabaseError, ObjectDoesNotExist, ValidationError,
    HttpResponse, QueryDict, rp, render_to_string, logger, timezone,
    Wom, WomDetails, WorkPermitForm, QuestionSet, Bt, Vendor, Approver, utils,
    get_current_db_name, save_with_audit,
    save_approvers_injson, save_verifiers_injson, save_workpermit_name_injson,
    check_all_approved, reject_workpermit, reject_workpermit_verifier,
    get_approvers_code, get_verifiers_code,
    check_if_valid_approver, check_if_valid_verifier,
    send_email_notification_for_vendor_and_security_of_wp_cancellation,
    send_email_notification_for_vendor_and_security_for_rwp,
    send_email_notification_for_vendor_and_security_after_approval,
    send_email_notification_for_wp_verifier,
    WorkOrderQueryOptimizer,
)
from apps.work_order_management import utils as wom_utils
from apps.work_order_management.services.work_permit_service import WorkPermitService
from apps.core.utils_new.http_utils import get_clean_form_data
import uuid
import html


class WorkPermit(LoginRequiredMixin, View):
    """
    Work Permit CRUD and approval workflow operations.

    GET:
        - template: Render work permit list template
        - action=list: Return work permit list as JSON
        - action=verifier_approve_wp&womid=<id>: Verify work permit
        - action=approve_wp&womid=<id>: Approve work permit
        - action=verifier_reject_wp&womid=<id>: Reject as verifier
        - action=reject_wp&womid=<id>: Reject work permit
        - action=form: Return empty work permit form
        - action=approver_list&womid=<id>: Get approver/verifier status
        - action=get_answers_of_template&qsetid&womid: Get filled answers
        - action=getAttachments&id=<id>: Get attachments
        - action=printReport: Generate work permit PDF
        - qsetid=<id>: Return form with questionnaire template
        - id=<id>: Return form with work permit instance

    POST:
        - action=submit_return_workpermit: Submit return work permit
        - action=cancellation_remark: Cancel work permit with remarks
        - Default: Create/update work permit
    """

    params = {
        "template_list": "work_order_management/workpermit_list.html",
        "template_form": "work_order_management/workpermit_form.html",
        "partial_form": "work_order_management/partial_wp_questionform.html",
        "email_template": "work_order_management/workpermit_approver_action.html",
        "model": Wom,
        "form": WorkPermitForm,
        "related": ["qset", "cuser", "bu"],
        "fields": [
            "cdtz",
            "id",
            "other_data__wp_seqno",
            "qset__qsetname",
            "workpermit",
            "cuser__peoplename",
            "bu__bucode",
            "bu__buname",
        ],
    }

    def get(self, request, *args, **kwargs):
        """Handle all GET requests for work permits."""
        R, P = request.GET, self.params

        # Load template
        if R.get("template"):
            return render(request, self.params["template_list"])

        # Get action
        action = R.get("action")

        # Return work permit list
        if action == "list" or R.get("search_term"):
            objs = self.params["model"].objects.get_workpermitlist(request)
            return rp.JsonResponse(data={"data": list(objs)}, safe=False)

        # Verifier approves work permit
        if action == "verifier_approve_wp" and R.get("womid"):
            wom = P["model"].objects.get(id=R["womid"])
            work_order_service = WorkOrderQueryOptimizer()
            try:
                result = work_order_service.verify_work_permit(
                    wom_id=R["womid"],
                    verifier_code=request.user.peoplecode,
                    client_id=request.session.get("client_id"),
                    user_data={"request": request},
                )
                if result["status"] == "verified":
                    return rp.JsonResponse(data={"data": result["message"]}, status=200)
                elif result["status"] == "already_cancelled":
                    return rp.JsonResponse(data={"data": result["message"]}, status=200)
                else:
                    return rp.JsonResponse(data={"data": result["message"]}, status=400)
            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                return rp.JsonResponse(data={"error": str(e)}, status=400)

        # Approver approves work permit
        if action == "approve_wp" and R.get("womid"):
            S = request.session
            wom = P["model"].objects.get(id=R["womid"])

            if wom.workpermit == Wom.Workstatus.CANCELLED:
                return rp.JsonResponse(
                    data={"data": "Work Permit is already cancelled"}, status=200
                )

            if is_all_approved := check_all_approved(wom.uuid, request.user.peoplecode):
                Wom.objects.filter(id=R["womid"]).update(
                    workpermit=Wom.WorkPermitStatus.APPROVED.value
                )

                if is_all_approved:
                    # Generate approved permit PDF and notify vendor
                    ReportObject = WorkPermitService.get_report_object(R["permit_name"])
                    client_id = request.session.get("client_id")
                    permit_name = R["permit_name"]

                    report = ReportObject(
                        filename=permit_name,
                        client_id=client_id,
                        returnfile=True,
                        formdata={"id": R["womid"]},
                        request=request,
                    )

                    sitename = Bt.objects.model(id=wom.bu_id).buname
                    workpermit_attachment = report.execute()
                    vendor_name = Vendor.objects.get(id=wom.vendor_id).name
                    permit_no = wom.other_data["wp_seqno"]
                    pdf_path = wom_utils.save_pdf_to_tmp_location(
                        workpermit_attachment,
                        report_name=permit_name,
                        report_number=permit_no,
                    )
                    workpermit_status = "APPROVED"

                    Wom.objects.filter(id=R["womid"]).update(
                        workstatus=Wom.Workstatus.INPROGRESS.value
                    )

                    send_email_notification_for_vendor_and_security_after_approval.delay(
                        R["womid"],
                        sitename,
                        workpermit_status,
                        vendor_name,
                        pdf_path,
                        permit_name,
                        permit_no,
                    )

            return rp.JsonResponse(data={"status": "Approved"}, status=200)

        # Verifier rejects work permit
        if R.get("action") == "verifier_reject_wp" and R.get("womid"):
            logger.info("Rejected Request:%s", R)
            wom = Wom.objects.get(id=R["womid"])
            wom.verifiers_status = Wom.WorkPermitVerifierStatus.REJECTED.value
            wom.workstatus = Wom.Workstatus.CANCELLED.value
            wom.workpermit = Wom.WorkPermitStatus.PENDING.value
            wom.save()
            reject_workpermit_verifier(wom.uuid, request.user.peoplecode)
            return rp.JsonResponse(data={"status": "Rejected"}, status=200)

        # Reject work permit
        if action == "reject_wp" and R.get("womid"):
            wom = P["model"].objects.get(id=R["womid"])
            Wom.objects.filter(id=R["womid"]).update(
                workpermit=Wom.WorkPermitStatus.REJECTED.value,
                workstatus=Wom.Workstatus.CANCELLED.value,
            )
            reject_workpermit(wom.uuid, request.user.peoplecode)
            return rp.JsonResponse(data={"status": "Rejected"}, status=200)

        # Return empty form
        if action == "form":
            logged_in_user = request.user.peoplecode
            cxt = {
                "wpform": P["form"](request=request),
                "msg": "create workpermit requested",
                "ownerid": uuid.uuid4(),
                "remarks": "None",
                "logged_in_user": logged_in_user,
            }
            return render(request, P["template_form"], cxt)

        # Get approver/verifier status
        if action == "approver_list":
            objs = Wom.objects.get_approver_verifier_status(R["womid"])
            return rp.JsonResponse({"data": objs}, status=200)

        # Return form with questionnaire template
        if R.get("qsetid"):
            wp_details = Wom.objects.get_workpermit_details(request, R["qsetid"])
            approver_codes = R["approvers"].split(",")
            approvers = wom_utils.get_approvers(approver_codes)

            # Remove return work permit section if present
            rwp_details = []
            if len(wp_details) > 1:
                last_section = wp_details[-1]
                section_name = last_section.get("section", "").lower()
                if "return" in section_name or "completion" in section_name:
                    rwp_details = wp_details.pop(-1)

            logged_in_user = request.user.peoplecode
            form = P["form"](
                request=request,
                initial={
                    "qset": R["qsetid"],
                    "approvers": R["approvers"].split(","),
                    "vendor": R["vendor"],
                    "verifiers": R["verifiers"].split(","),
                },
            )

            context = {
                "wp_details": wp_details,
                "wpform": form,
                "ownerid": uuid.uuid4(),
                "approvers": approvers,
                "remarks": "None",
                "logged_in_user": logged_in_user,
            }
            return render(request, P["template_form"], context=context)

        # Get filled questionnaire answers
        if action == "get_answers_of_template" and R.get("qsetid") and R.get("womid"):
            wp_answers = Wom.objects.get_wp_answers(R["womid"])
            questionsform = render_to_string(
                P["partial_form"], context={"wp_details": wp_answers[1]}
            )
            return rp.JsonResponse({"html": questionsform}, status=200)

        # Get attachments
        if action == "getAttachments":
            att = P["model"].objects.get_attachments(R["id"])
            return rp.JsonResponse(data={"data": list(att)})

        # Generate PDF report
        if action == "printReport":
            return WorkPermitService.send_report(R, request)

        # Return form with work permit instance for edit
        if "id" in R:
            logger.info("In this view")

            obj = utils.get_model_obj(int(R["id"]), request, P)
            wp_answers = Wom.objects.get_wp_answers(obj.id)
            work_status = Wom.objects.get(id=R["id"]).workstatus
            remarks = Wom.objects.get(id=R["id"]).remarks
            logged_in_user = request.user.peoplecode
            people_id = request.session.get("people_id")

            approvers_other_data = obj.other_data["wp_approvers"]
            verifiers_other_data = obj.other_data["wp_verifiers"]
            approvers_code = get_approvers_code(approvers_other_data)
            verifiers_code = get_verifiers_code(verifiers_other_data)
            is_valid_approver = check_if_valid_approver(logged_in_user, approvers_code)
            is_valid_verifier = check_if_valid_verifier(logged_in_user, verifiers_code)

            try:
                identifier = Approver.objects.get(
                    people_id=people_id, approverfor="{WORKPERMIT}"
                ).identifier
            except Approver.DoesNotExist:
                identifier = None

            cxt = {
                "wpform": P["form"](request=request, instance=obj),
                "ownerid": obj.uuid,
                "wp_details": wp_answers,
            }
            cxt["remarks"] = "None" if remarks is None else remarks
            cxt["logged_in_user"] = logged_in_user
            cxt["identifier"] = identifier
            cxt["is_valid_approver"] = is_valid_approver
            cxt["is_valid_verifier"] = is_valid_verifier

            # If approved but not completed, show return work permit section
            if (
                obj.workpermit == Wom.WorkPermitStatus.APPROVED
                and obj.workstatus != Wom.Workstatus.COMPLETED
                and (identifier != "APPROVER" and identifier != "VERIFIER")
            ):
                qset_id = obj.qset.id
                rwp_details = Wom.objects.get_return_wp_details(qset_id)
                logger.info(f"return work permit details are as follows: {rwp_details}")
                cxt["rwp_details"] = [rwp_details]
                cxt["work_status"] = work_status

            return render(request, P["template_form"], cxt)

    def post(self, request, *args, **kwargs):
        """Handle all POST requests for work permits."""
        R, P = request.POST, self.params

        try:
            logger.info("R: %s", R)

            # Submit return work permit
            if R.get("action") == "submit_return_workpermit":
                logger.info("submitting return work permit")
                wom = Wom.objects.get(id=R["wom_id"])
                return_wp_formdata = QueryDict(
                    request.POST["return_work_permit_formdata"]
                ).copy()
                rwp_seqno = Wom.objects.filter(parent_id=R["wom_id"]).count() + 1

                # Delegate to service
                WorkPermitService.create_workpermit_details(
                    R["wom_id"], wom, request, return_wp_formdata, rwp_seqno=rwp_seqno
                )

                wom.workstatus = Wom.Workstatus.COMPLETED
                wom.save()

                permit_name = wom.other_data["wp_name"]
                permit_no = wom.other_data["wp_seqno"]
                workpermit_status = "COMPLETED"
                client_id = request.session.get("client_id")

                report_obj = wom_utils.get_report_object(permit_name)
                report = report_obj(
                    filename=permit_name,
                    client_id=client_id,
                    returnfile=True,
                    formdata={"id": R["wom_id"]},
                    request=request,
                )
                report_pdf_object = report.execute()
                vendor_name = Vendor.objects.get(id=wom.vendor_id).name
                site_name = Bt.objects.get(id=wom.bu_id).buname
                pdf_path = wom_utils.save_pdf_to_tmp_location(
                    report_pdf_object, report_name=permit_name, report_number=permit_no
                )

                send_email_notification_for_vendor_and_security_for_rwp.delay(
                    R["wom_id"],
                    site_name,
                    workpermit_status,
                    vendor_name,
                    pdf_path,
                    permit_name,
                    permit_no,
                )
                return rp.JsonResponse({"pk": wom.id})

            # Cancel work permit with remarks
            if R.get("action") == "cancellation_remark":
                logged_in_user = R.get("logged_in_user")
                wom = Wom.objects.get(id=R["wom_id"])
                remarks = R.get("cancelation_remarks")

                if wom.remarks is None:
                    wom.remarks = []

                wom.remarks.append({"people": logged_in_user, "remarks": remarks})
                wom.workstatus = Wom.Workstatus.CANCELLED
                wom.save()

                site_name = Bt.objects.get(id=wom.bu_id).buname
                workpermit_status = wom.workstatus
                vendor_name = Vendor.objects.get(id=wom.vendor_id).name
                permit_name = wom.other_data["wp_name"]
                permit_no = wom.other_data["wp_seqno"]

                send_email_notification_for_vendor_and_security_of_wp_cancellation.delay(
                    R["wom_id"],
                    site_name,
                    workpermit_status,
                    vendor_name,
                    permit_name,
                    permit_no,
                )
                return rp.JsonResponse({"pk": R["wom_id"]})

            # Create or update work permit
            if pk := R.get("pk", None):
                data = QueryDict(R["formData"]).copy()
                wp = utils.get_model_obj(pk, request, P)
                form = self.params["form"](data, instance=wp, request=request)
                create = False
            else:
                data = get_clean_form_data(request)
                form = self.params["form"](data, request=request)
                create = True

            if form.is_valid():
                resp = self.handle_valid_form(form, R, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.params, cxt)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist,
                TypeError, ValidationError, ValueError):
            resp = utils.handle_Exception(request)

        return resp

    def handle_valid_form(self, form, R, request, create=True):
        """
        Save validated work permit form with questionnaire details.

        Args:
            form: Validated WorkPermitForm instance
            R: POST data
            request: Django request object
            create: True for create, False for update

        Returns:
            JsonResponse with work permit ID

        Process:
            1. Save work permit with audit info
            2. Save approvers/verifiers in JSON
            3. Process questionnaire details (delegate to service)
            4. Generate PDF report
            5. Send email notification to verifiers

        Raises:
            IntegrityError: On database constraint violation
        """
        S = request.session
        permit_name = request.POST["permit_name"]

        try:
            with transaction.atomic(using=get_current_db_name()):
                workpermit = form.save(commit=False)
                workpermit.uuid = request.POST.get("uuid")
                workpermit = save_with_audit(workpermit, request.user, request.session, create=create)
                workpermit = save_approvers_injson(workpermit)
                workpermit = save_verifiers_injson(workpermit)
                workpermit = save_workpermit_name_injson(workpermit, permit_name)

                # Decode and parse questionnaire form data
                raw_formdata = request.POST["workpermitdetails"]
                logger.info(f"Raw form data: {raw_formdata}")

                decoded_formdata = html.unescape(raw_formdata)
                logger.info(f"Decoded form data: {decoded_formdata}")

                formdata = QueryDict(decoded_formdata).copy()
                logger.info(f"Parsed form data keys: {list(formdata.keys())}")

                # Delegate questionnaire processing to service
                WorkPermitService.create_workpermit_details(
                    request.POST, workpermit, request, formdata
                )

                # Generate PDF and send to verifiers
                sitename = S.get("sitename", "demo")
                workpermit_status = "PENDING"
                report_object = wom_utils.get_report_object(permit_name)
                client_id = request.session.get("client_id")

                report = report_object(
                    filename=permit_name,
                    client_id=client_id,
                    returnfile=True,
                    formdata={"id": workpermit.id},
                    request=request,
                )
                report_pdf_object = report.execute()
                vendor_name = Vendor.objects.get(id=workpermit.vendor_id).name
                pdf_path = wom_utils.save_pdf_to_tmp_location(
                    report_pdf_object,
                    report_name=permit_name,
                    report_number=workpermit.other_data["wp_seqno"],
                )

                logger.info(f"Work permit created successfully: {workpermit.id}")

                send_email_notification_for_wp_verifier.delay(
                    workpermit.id,
                    workpermit.verifiers,
                    sitename,
                    workpermit_status,
                    permit_name,
                    vendor_name,
                    client_id,
                    pdf_path,
                )

                return rp.JsonResponse({"pk": workpermit.id})

        except IntegrityError:
            return utils.handle_intergrity_error("WorkPermit")
