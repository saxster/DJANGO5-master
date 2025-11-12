"""
Work Order Management - Approval & Reply Views

Handles approver management and all external email reply workflows.

Classes:
    - ApproverView: Approver CRUD operations (authenticated)
    - VerifierReplyWorkPermit: External verifier replies via email (public)
    - ReplyWorkPermit: External approver replies via email (public)
    - ReplySla: External SLA report replies via email (public)

Refactored: October 2025
Original: work_order_management/views.py:956-1261 (305 lines across 4 classes)
"""

from .base import (
    LoginRequiredMixin, View, render, transaction, IntegrityError,
    DatabaseError, ObjectDoesNotExist, ValidationError,
    HttpResponse, rp, logger, pg_errs, timezone,
    Wom, Approver, ApproverForm, People, Bt, utils,
    get_current_db_name, get_clean_form_data, save_with_audit,
    check_all_approved, check_all_verified, reject_workpermit,
    reject_workpermit_verifier, save_pdf_to_tmp_location,
    send_email_notification_for_sla_vendor,
    send_email_notification_for_vendor_and_security_after_approval,
    send_email_notification_for_workpermit_approval,
)
from apps.work_order_management.services.work_order_security_service import (
    WorkOrderSecurityService
)
from django.core.exceptions import PermissionDenied
from apps.work_order_management import utils as wom_utils
from apps.reports.report_designs.service_level_agreement import ServiceLevelAgreement


class ApproverView(LoginRequiredMixin, View):
    """
    Approver CRUD operations view.

    GET:
        - template: Render approver list template
        - action=list: Return approver list as JSON
        - action=form: Return empty approver form
        - action=delete&id=<id>: Delete approver
        - id=<id>: Return form with approver instance

    POST:
        - Create new approver (no pk)
        - Update existing approver (with pk)
    """

    params = {
        "form_class": ApproverForm,
        "template_form": "work_order_management/approver_form.html",
        "template_list": "work_order_management/approver_list.html",
        "related": ["people", "cuser"],
        "model": Approver,
        "fields": [
            "approverfor",
            "id",
            "sites",
            "cuser__peoplename",
            "people__peoplename",
            "forallsites",
            "bu__buname",
            "bu__bucode",
            "identifier",
        ],
    }

    def get(self, request, *args, **kwargs):
        R, resp, P, S = request.GET, None, self.params, request.session

        # Return template
        if R.get("template"):
            return render(request, P["template_list"])

        # Return approver list data
        if R.get("action", None) == "list":
            objs = P["model"].objects.get_approver_list(
                request, P["fields"], P["related"]
            )
            return rp.JsonResponse(data={"data": list(objs)})

        # Return empty form
        elif R.get("action", None) == "form":
            cxt = {
                "approver_form": P["form_class"](request=request),
                "msg": "create approver requested",
            }
            resp = utils.render_form(request, P, cxt)

        # Handle delete request
        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, P, False)

        # Return form with instance for update
        elif R.get("id", None):
            obj = utils.get_model_obj(int(R["id"]), request, P)
            resp = utils.render_form_for_update(request, P, "approver_form", obj)

        return resp

    def post(self, request, *args, **kwargs):
        """
        Handle approver create/update POST requests.

        Returns:
            JsonResponse with approver data or error message
        """
        resp, create = None, True
        try:
            data = get_clean_form_data(request)

            if pk := request.POST.get("pk", None):
                # Update existing approver
                ven = utils.get_model_obj(pk, request, self.params)
                form = self.params["form_class"](data, instance=ven, request=request)
                create = False
            else:
                # Create new approver
                form = self.params["form_class"](data, request=request)

            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.params, cxt)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist,
                TypeError, ValidationError, ValueError):
            resp = utils.handle_Exception(request)

        return resp

    def handle_valid_form(self, form, request, create):
        """
        Save validated approver form.

        Args:
            form: Validated ApproverForm instance
            request: Django request object
            create: True for create, False for update

        Returns:
            JsonResponse with saved approver data

        Raises:
            IntegrityError: On duplicate approver or unique constraint violation
        """
        logger.info("approver form is valid")
        try:
            with transaction.atomic(using=get_current_db_name()):
                approver = form.save(commit=False)
                approver = save_with_audit(approver, request.user, request.session, create=create)

                logger.info("approver form saved")
                data = {
                    "msg": f"{approver.people.peoplename}",
                    "row": Approver.objects.values(*self.params["fields"]).get(
                        id=approver.id
                    ),
                }
                return rp.JsonResponse(data, status=200)

        except (IntegrityError, pg_errs.UniqueViolation):
            return utils.handle_intergrity_error("Approver")


class VerifierReplyWorkPermit(View):
    """
    External verifier replies to work permits via email.

    Public view (no LoginRequiredMixin) for email-based workflows.
    Uses approver validation to prevent unauthorized access.

    GET:
        - action=accepted&womid=<id>&peopleid=<id>&token=<token>: Approve work permit (verifier)
        - action=rejected&womid=<id>&peopleid=<id>&token=<token>: Reject work permit (verifier)

    POST:
        - Save rejection remarks (with token validation)
    
    Security: Validates that peopleid is authorized verifier for the work permit.
    """

    P = {
        "email_template": "work_order_management/workpermit_verifier_server_reply.html",
        "model": Wom,
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.P

        token = R.get("token")

        try:
            if R.get("action") == "accepted" and R.get("womid") and R.get("peopleid"):
                wom, verifier = WorkOrderSecurityService.validate_approver_access(
                    int(R["womid"]), int(R["peopleid"]), token
                )

                if wom.workpermit != Wom.WorkPermitStatus.REJECTED:
                    wp = Wom.objects.filter(id=R["womid"]).first()
                    p = People.objects.filter(id=R["peopleid"]).first()
                    logger.info("Verifier approval request: %s", R)

                    if is_all_verified := check_all_verified(wp.uuid, p.peoplecode):
                        if (
                            Wom.WorkPermitVerifierStatus.APPROVED
                            != Wom.objects.get(id=R["womid"]).workpermit
                        ):
                            Wom.objects.filter(id=R["womid"]).update(
                                verifiers_status=Wom.WorkPermitVerifierStatus.APPROVED
                            )

                            if is_all_verified:
                                wom_id = R["womid"]
                                wom = Wom.objects.get(id=wom_id)
                                sitename = Bt.objects.get(id=wom.bu_id).buname
                                permit_name = wom.other_data["wp_name"]
                                permit_no = wom.other_data["wp_seqno"]
                                client_id = wom.client.id

                                report_obj = wom_utils.get_report_object(permit_name)
                                report = report_obj(
                                    filename=permit_name,
                                    client_id=client_id,
                                    returnfile=True,
                                    formdata={"id": wom_id},
                                    request=None,
                                )
                                report_pdf_object = report.execute()
                                vendor_name = wom_utils.Vendor.objects.get(
                                    id=wom.vendor_id
                                ).name
                                pdf_path = wom_utils.save_pdf_to_tmp_location(
                                    report_pdf_object,
                                    report_name=permit_name,
                                    report_number=permit_no,
                                )

                                wp_approvers = wom.other_data["wp_approvers"]
                                workpermit_status = Wom.WorkPermitStatus.PENDING
                                approvers_name = [
                                    approver["name"] for approver in wp_approvers
                                ]
                                approvers_code = [
                                    approver["peoplecode"] for approver in wp_approvers
                                ]

                                logger.info(
                                    "Sending Email to Approver %s to approve the work permit",
                                    approvers_name,
                                )
                                send_email_notification_for_workpermit_approval.delay(
                                    wom_id,
                                    approvers_name,
                                    approvers_code,
                                    sitename,
                                    workpermit_status,
                                    permit_name,
                                    pdf_path,
                                    vendor_name,
                                    client_id,
                                )
                    else:
                        return render(
                            request,
                            P["email_template"],
                            context={"alreadyverified": True},
                        )

                    cxt = {
                        "status": Wom.WorkPermitVerifierStatus.APPROVED,
                        "seqno": wp.other_data["wp_seqno"],
                    }
                else:
                    cxt = {"alreadyrejected": True}

                return render(request, P["email_template"], context=cxt)

            elif R.get("action") == "rejected" and R.get("womid") and R.get("peopleid"):
                logger.info("Verifier rejection request: %s", R)
                wom = Wom.objects.get(id=R["womid"])

                if wom.workpermit == Wom.WorkPermitStatus.APPROVED:
                    return render(
                        request, P["email_template"], context={"alreadyverified": True}
                    )

                if wom.workpermit == Wom.WorkPermitStatus.REJECTED:
                    return render(
                        request, P["email_template"], context={"alreadyrejected": True}
                    )

                people = People.objects.get(id=R["peopleid"])
                wom.workpermit = Wom.WorkPermitVerifierStatus.REJECTED.value
                wom.save()
                reject_workpermit_verifier(wom.uuid, people.peoplecode)

                cxt = {
                    "status": Wom.WorkPermitVerifierStatus.REJECTED,
                    "action": "rejected",
                    "action_acknowledged": True,
                    "seqno": wom.other_data["wp_seqno"],
                    "wom_id": wom.id,
                    "people_code": people.peoplecode,
                }
                return render(request, P["email_template"], context=cxt)

            return render(
                request,
                P["email_template"],
                context={"error": _("Invalid verifier action")},
                status=400,
            )

        except (Wom.DoesNotExist, People.DoesNotExist):
            logger.error("Verifier access attempt for missing work order/people: %s", R)
            return render(
                request,
                P["email_template"],
                context={"error": _("Work permit not found")},
                status=404,
            )
        except PermissionDenied as exc:
            logger.warning("Verifier access denied: %s", exc)
            return render(
                request,
                P["email_template"],
                context={"error": str(exc)},
                status=403,
            )

    def post(self, request, *args, **kwargs):
        """Save verifier rejection remarks."""
        R, P = request.POST, self.P
        logger.info("R:%s", R)

        remarks = R.get("reason")
        people_code = R.get("peoplecode")
        seqno = R.get("workpermit_seqno")
        status = R.get("status")

        wom = Wom.objects.get(id=R["workpermitid"])
        if wom.remarks is None:
            wom.remarks = []

        wom.remarks.append({"people": people_code, "remarks": remarks})
        wom.save()

        return render(
            request, P["email_template"], context={"seqno": seqno, "status": status}
        )


class ReplyWorkPermit(View):
    """
    External approver replies to work permits via email.

    Public view (no LoginRequiredMixin) for email-based workflows.

    GET:
        - action=accepted&womid=<id>&peopleid=<id>: Approve work permit
        - action=rejected&womid=<id>&peopleid=<id>: Reject work permit
    """

    P = {
        "email_template": "work_order_management/workpermit_server_reply.html",
        "model": Wom,
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.P

        # Approver accepts work permit
        if R.get("action") == "accepted" and R.get("womid") and R.get("peopleid"):
            wom = Wom.objects.get(id=R["womid"])
            wp = Wom.objects.filter(id=R["womid"]).first()
            p = People.objects.filter(id=R["peopleid"]).first()
            logger.info("R:%s", R)

            if is_all_approved := check_all_approved(wp.uuid, p.peoplecode):
                if (
                    Wom.WorkPermitStatus.APPROVED
                    != Wom.objects.get(id=R["womid"]).workpermit
                ):
                    Wom.objects.filter(id=R["womid"]).update(
                        workpermit=Wom.WorkPermitStatus.APPROVED.value
                    )

                    if is_all_approved:
                        # All approvers approved - finalize
                        wom_id = R["womid"]
                        wom = Wom.objects.get(id=wom_id)
                        sitename = Bt.objects.get(id=wom.bu_id).buname
                        logger.info("Inside of the if sitename %s", sitename)

                        permit_name = wom.other_data["wp_name"]
                        permit_no = wom.other_data["wp_seqno"]
                        worpermit_status = "APPROVED"
                        client_id = R.get("client_id")

                        report_obj = wom_utils.get_report_object(permit_name)
                        report = report_obj(
                            filename=permit_name,
                            client_id=client_id,
                            returnfile=True,
                            formdata={"id": wom_id},
                            request=request,
                        )
                        report_pdf_object = report.execute()
                        vendor_name = wom_utils.Vendor.objects.get(id=wom.vendor_id).name
                        pdf_path = wom_utils.save_pdf_to_tmp_location(
                            report_pdf_object,
                            report_name=permit_name,
                            report_number=permit_no,
                        )

                        Wom.objects.filter(id=R["womid"]).update(
                            workstatus=Wom.Workstatus.INPROGRESS.value
                        )

                        send_email_notification_for_vendor_and_security_after_approval.delay(
                            wom_id,
                            sitename,
                            worpermit_status,
                            vendor_name,
                            pdf_path,
                            permit_name,
                            permit_no,
                        )
                else:
                    return render(
                        request, P["email_template"], context={"alreadyapproved": True}
                    )

            cxt = {
                "status": Wom.WorkPermitStatus.APPROVED.value,
                "action_acknowledged": True,
                "seqno": wp.other_data["wp_seqno"],
            }
            logger.info("work permit accepted through email")
            return render(request, P["email_template"], context=cxt)

        # Approver rejects work permit
        elif R.get("action") == "rejected" and R.get("womid") and R.get("peopleid"):
            logger.info("work permit rejected")
            wp = Wom.objects.filter(id=R["womid"]).first()

            if wp.workpermit == Wom.WorkPermitStatus.APPROVED:
                return render(
                    request, P["email_template"], context={"alreadyapproved": True}
                )

            if wp.workpermit == Wom.WorkPermitStatus.REJECTED:
                return render(
                    request, P["email_template"], context={"alreadyrejected": True}
                )

            p = People.objects.filter(id=R["peopleid"]).first()
            wp.workpermit = Wom.WorkPermitStatus.REJECTED.value
            wp.save()
            reject_workpermit(wp.uuid, p.peoplecode)

            cxt = {
                "status": Wom.WorkPermitStatus.REJECTED.value,
                "action_acknowledged": True,
                "seqno": wp.other_data["wp_seqno"],
            }
            logger.info("work permit rejected through email")
            return render(request, P["email_template"], context=cxt)


class ReplySla(View):
    """
    External SLA report replies via email.

    Public view (no LoginRequiredMixin) for email-based workflows.

    GET:
        - action=accepted&womid=<uuid>&peopleid=<id>: Approve SLA report
        - action=rejected&womid=<uuid>&peopleid=<id>: Reject SLA report
    """

    P = {
        "email_template": "work_order_management/sla_server_reply.html",
        "model": Wom,
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.P
        S = request.session

        # SLA approver accepts
        if R.get("action") == "accepted" and R.get("womid") and R.get("peopleid"):
            logger.info("Service level agreement report accepted")
            logger.info("R:%s", R)
            logger.info("Workpermit value", Wom.objects.get(uuid=R["womid"]).workpermit)

            p = People.objects.filter(id=R["peopleid"]).first()

            if is_all_approved := check_all_approved(R["womid"], p.peoplecode):
                logger.info("Inside of the if")

                if (
                    Wom.WorkPermitStatus.APPROVED.value
                    != Wom.objects.get(uuid=R["womid"]).workpermit
                ):
                    Wom.objects.filter(uuid=R["womid"]).update(
                        workpermit=Wom.WorkPermitStatus.APPROVED.value
                    )
                    logger.info("Inside of the second if")

                    if is_all_approved:
                        logger.info("Inside of the third if")
                        wom_id = R["womid"]
                        wom = Wom.objects.get(uuid=wom_id)
                        sitename = Bt.objects.get(id=wom.bu_id).buname
                        id_val = wom.id

                        sla_report_obj = ServiceLevelAgreement(
                            returnfile=True,
                            filename="Vendor Performance Report",
                            formdata={
                                "id": id_val,
                                "bu__buname": sitename,
                                "submit_button_flow": "true",
                                "filename": "Service Level Agreement",
                                "workpermit": wom.workpermit,
                            },
                        )
                        logger.info("sla_report_obj", sla_report_obj)

                        workpermit_attachment = sla_report_obj.execute()
                        report_path = save_pdf_to_tmp_location(
                            workpermit_attachment,
                            report_name="Vendor Performance Report",
                            report_number=wom.other_data["wp_seqno"],
                        )
                        logger.info("workpermit_attachment", report_path)

                        send_email_notification_for_sla_vendor.delay(
                            R["womid"], report_path, sitename
                        )
                else:
                    logger.info("Else case")
                    return render(
                        request, P["email_template"], context={"alreadyapproved": True}
                    )

            cxt = {
                "status": Wom.WorkPermitStatus.APPROVED.value,
                "action_acknowledged": True,
                "seqno": Wom.objects.get(uuid=R["womid"]).other_data["wp_seqno"],
            }
            logger.info("is approved", is_all_approved)
            logger.info("Service level agreement report accepted through email")
            return render(request, P["email_template"], context=cxt)

        # SLA approver rejects
        elif R.get("action") == "rejected" and R.get("womid") and R.get("peopleid"):
            wp = Wom.objects.filter(uuid=R["womid"]).first()

            if wp.workpermit == Wom.WorkPermitStatus.APPROVED:
                return render(
                    request, P["email_template"], context={"alreadyapproved": True}
                )

            p = People.objects.filter(id=R["peopleid"]).first()
            wp.workpermit = Wom.WorkPermitStatus.REJECTED.value
            wp.save()
            reject_workpermit(wp.uuid, p.peoplecode)

            cxt = {
                "status": Wom.WorkPermitStatus.REJECTED.value,
                "action_acknowledged": True,
                "seqno": wp.other_data["wp_seqno"],
            }
            logger.info("work permit rejected through email")
            return render(request, P["email_template"], context=cxt)
