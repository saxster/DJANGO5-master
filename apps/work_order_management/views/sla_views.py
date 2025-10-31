"""
Work Order Management - SLA Views

Handles Service Level Agreement CRUD operations and scoring.

Classes:
    - SLA_View: SLA create, read, update, approve/reject, scoring

Refactored: October 2025
Original: work_order_management/views.py:1356-1544 (188 lines)
"""

from .base import (
    LoginRequiredMixin, View, render, transaction, IntegrityError,
    DatabaseError, ObjectDoesNotExist, ValidationError,
    HttpResponse, QueryDict, rp, logger, pg_errs, timezone, relativedelta, _,
    Wom, SlaForm, utils, check_all_approved, reject_workpermit,
    save_pdf_to_tmp_location, send_email_notification_for_sla_vendor,
)
from apps.work_order_management import utils as wom_utils
from apps.reports.report_designs import service_level_agreement as sla
import uuid
import datetime


class SLA_View(LoginRequiredMixin, View):
    """
    Service Level Agreement CRUD and scoring operations.

    GET:
        - template: Render SLA list template
        - action=list: Return SLA list as JSON
        - action=form: Return empty SLA form with month
        - action=approver_list&womid=<id>: Get approver/verifier status
        - action=printReport: Generate SLA PDF report
        - action=approve_sla&slaid=<id>: Approve SLA report
        - action=reject_sla&slaid=<id>: Reject SLA report
        - id=<id>: Return form with SLA instance
        - qsetid=<id>: Return form with questionnaire template

    POST:
        - Create new SLA (no pk)
        - Update existing SLA (with pk)
    """

    params = {
        "template_form": "work_order_management/sla_form.html",
        "template_list": "work_order_management/sla_list.html",
        "model": Wom,
        "form": SlaForm,
    }

    MONTH_CHOICES = {
        "1": "January",
        "2": "February",
        "3": "March",
        "4": "April",
        "5": "May",
        "6": "June",
        "7": "July",
        "8": "August",
        "9": "September",
        "10": "October",
        "11": "November",
        "12": "December",
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        action = R.get("action")

        # Return template
        if R.get("template"):
            return render(request, P["template_list"])

        # Return SLA list data
        if action == "list":
            objs = self.params["model"].objects.get_slalist(request)
            return rp.JsonResponse(data={"data": list(objs)}, safe=False)

        # Get approver/verifier status
        if action == "approver_list":
            objs = Wom.objects.get_approver_verifier_status(R["womid"])
            return rp.JsonResponse({"data": objs}, status=200)

        # Generate PDF report
        if action == "printReport":
            return self.send_report(R, request)

        # Approve SLA
        if action == "approve_sla" and R.get("slaid"):
            S = request.session
            wom = P["model"].objects.get(id=R["slaid"])
            filename = "Vendor Performance Report"

            sla_obj = sla.ServiceLevelAgreement(
                returnfile=True,
                filename=filename,
                client_id=S["client_id"],
                formdata={
                    "id": R["slaid"],
                    "bu__buname": S["sitename"],
                    "submit_button_flow": "true",
                    "filename": "Service Level Agreement",
                    "workpermit": wom.workpermit,
                },
            )
            sla_attachment = sla_obj.execute()
            report_path = save_pdf_to_tmp_location(
                sla_attachment,
                report_name=filename,
                report_number=wom.other_data["wp_seqno"],
            )

            if is_all_approved := check_all_approved(wom.uuid, request.user.peoplecode):
                Wom.objects.filter(id=R["slaid"]).update(
                    workpermit=Wom.WorkPermitStatus.APPROVED.value
                )
                if is_all_approved:
                    workpermit_status = "APPROVED"
                    sla_uuid = wom.uuid
                    send_email_notification_for_sla_vendor.delay(
                        sla_uuid, report_path, S["sitename"]
                    )

            return rp.JsonResponse(data={"status": "Approved"}, status=200)

        # Reject SLA
        if action == "reject_sla" and R.get("slaid"):
            wom = P["model"].objects.get(id=R["slaid"])
            if wom.workpermit == Wom.WorkPermitStatus.APPROVED:
                return HttpResponse(str(_("The work order is already approved")))

            Wom.objects.filter(id=R["slaid"]).update(
                workpermit=Wom.WorkPermitStatus.REJECTED.value
            )
            reject_workpermit(wom.uuid, request.user.peoplecode)
            return rp.JsonResponse(data={"status": "Rejected"}, status=200)

        # Return empty form with month
        if action == "form":
            month_name = (datetime.datetime.now() - relativedelta(months=1)).strftime(
                "%B"
            )
            cxt = {
                "slaform": P["form"](request=request),
                "msg": "create sla requested",
                "month_name": month_name,
                "ownerid": uuid.uuid4(),
            }
            return render(request, P["template_form"], cxt)

        # Return form with SLA instance
        if "id" in R:
            obj = utils.get_model_obj(int(R["id"]), request, P)
            sla_answer = Wom.objects.get_wp_answers(obj.id)
            wom_utils.get_overall_score(obj.id)
            wom = Wom.objects.get(id=R["id"])

            month_name = wom.other_data.get("month", None)
            if not month_name:
                month_number = wom.cdtz.month - 1
                month_name = self.MONTH_CHOICES.get(f"{month_number}")

            cxt = {
                "slaform": P["form"](request=request, instance=obj),
                "ownerid": obj.uuid,
                "sla_details": sla_answer,
                "month_name": month_name,
            }
            return render(request, P["template_form"], cxt)

        # Return form with questionnaire template
        if R.get("qsetid"):
            wp_details = Wom.objects.get_workpermit_details(request, R["qsetid"])
            approver_codes = R["approvers"].split(",")
            approvers = wom_utils.get_approvers(approver_codes)

            form = P["form"](
                request=request,
                initial={
                    "qset": R["qsetid"],
                    "approvers": R["approvers"].split(","),
                    "vendor": R["vendor"],
                    "month_name": R["month"],
                },
            )
            context = {
                "sla_details": wp_details,
                "slaform": form,
                "ownerid": uuid.uuid4(),
                "approvers": approvers,
                "month_name": datetime.datetime.now().strftime("%B"),
            }
            return render(request, P["template_form"], context=context)

    def get_month_name(self, month):
        """Convert month number to name."""
        if month == -1:
            return ""
        return self.MONTH_CHOICES.get(month)

    def get_month_number(self, month_name):
        """Convert month name to number."""
        for number, name in self.MONTH_CHOICES.items():
            if name.lower() == month_name.lower():
                return int(number)
        return None

    def send_report(self, R, request):
        """Generate SLA PDF report."""
        report = sla.ServiceLevelAgreement(
            filename=R["qset__qsetname"],
            client_id=request.session["client_id"],
            formdata=R,
            request=request,
        )
        return report.execute()

    def post(self, request, *args, **kwargs):
        """
        Handle SLA create/update POST requests.

        Returns:
            JsonResponse with SLA data or error message
        """
        R, P = request.POST, self.params
        try:
            if pk := R.get("pk", None):
                # Update existing SLA
                data = QueryDict(R["formData"]).copy()
                wp = utils.get_model_obj(pk, request, P)
                form = self.params["form"](data, instance=wp, request=request)
                create = False
            else:
                # Create new SLA
                data = QueryDict(R["formData"]).copy()
                data["month"] = wom_utils.get_month_number(
                    self.MONTH_CHOICES, request.POST.get("month_name")
                )
                form = self.params["form"](data, request=request)
                create = True

            if form.is_valid():
                resp = wom_utils.handle_valid_form(form, R, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.params, cxt)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist,
                TypeError, ValidationError, ValueError):
            resp = utils.handle_Exception(request)

        return resp
