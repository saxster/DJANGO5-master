"""
Work Order Management - Work Order Views

Handles work order CRUD operations and external vendor replies.

Classes:
    - WorkOrderView: Work order create, read, update, delete operations
    - ReplyWorkOrder: External vendor replies via email (public)

Refactored: October 2025
Original: work_order_management/views.py:145-435 (290 lines)
"""

from .base import (
    LoginRequiredMixin, View, render, transaction, IntegrityError,
    DatabaseError, ObjectDoesNotExist, ValidationError,
    HttpResponse, QueryDict, rp, logger, pg_errs, timezone, _,
    Wom, WomDetails, WorkOrderForm, QuestionSetBelonging, utils,
    get_current_db_name, save_with_audit
)
from apps.work_order_management.services.work_order_security_service import (
    WorkOrderSecurityService
)
from django.core.exceptions import PermissionDenied
import uuid


class WorkOrderView(LoginRequiredMixin, View):
    """
    Work Order CRUD operations view.

    GET:
        - template: Render work order list template
        - action=list: Return work order list as JSON
        - action=form: Return empty work order form
        - action=close_wo&womid=<id>: Close work order
        - action=send_workorder_email&id=<id>: Send work order email
        - action=getAttachmentJND&id=<id>: Get attachments
        - action=get_wo_details&womid=<id>: Get work order details
        - id=<id>: Return form with work order instance

    POST:
        - Create new work order (no pk)
        - Update existing work order (with pk)
    """

    params = {
        "form_class": WorkOrderForm,
        "template_form": "work_order_management/work_order_form.html",
        "template_list": "work_order_management/work_order_list.html",
        "related": ["vendor", "cuser", "bu"],
        "model": Wom,
        "model_jnd": WomDetails,
        "fields": [
            "id",
            "ctzoffset",
            "cuser__peoplename",
            "cuser__peoplecode",
            "plandatetime",
            "cdtz",
            "bu__buname",
            "expirydatetime",
            "priority",
            "description",
            "vendor__name",
            "categories",
            "workstatus",
            "bu__bucode",
        ],
    }

    def get(self, request, *args, **kwargs):
        R, resp, P = request.GET, None, self.params

        # Return template
        if R.get("template"):
            return render(request, P["template_list"])

        # Return work order list data (filtered by user permissions)
        if R.get("action", None) == "list":
            # Use security service to get filtered queryset
            queryset = WorkOrderSecurityService.get_user_work_orders_queryset(
                request.user
            )
            objs = queryset.values(*P["fields"])
            return rp.JsonResponse(data={"data": list(objs)})

        # Return empty form
        elif R.get("action", None) == "form":
            cxt = {
                "woform": P["form_class"](request=request),
                "msg": "create workorder requested",
                "ownerid": uuid.uuid4(),
            }
            resp = render(request, P["template_form"], cxt)

        # Close work order (with authorization check)
        elif R.get("action") == "close_wo" and R.get("womid"):
            try:
                wo = WorkOrderSecurityService.validate_close_permission(
                    int(R["womid"]), request.user
                )
                wo.workstatus = "CLOSED"
                wo.save()
                return rp.JsonResponse({"pk": R["womid"]}, status=200)
            except PermissionDenied as e:
                return rp.JsonResponse({"error": str(e)}, status=403)

        # Handle delete request (with authorization check)
        elif R.get("action", None) == "delete" and R.get("id", None):
            try:
                WorkOrderSecurityService.validate_delete_permission(
                    int(R["id"]), request.user
                )
                resp = utils.render_form_for_delete(request, P, True)
            except PermissionDenied as e:
                return rp.JsonResponse({"error": str(e)}, status=403)

        # Send work order email (with authorization check)
        elif R.get("action") == "send_workorder_email":
            try:
                WorkOrderSecurityService.validate_work_order_access(
                    int(R["id"]), request.user, allow_tenant_access=True
                )
                from apps.work_order_management.utils import notify_wo_creation
                notify_wo_creation(id=R["id"])
                return rp.JsonResponse({"msg": "Email sent successfully"}, status=200)
            except PermissionDenied as e:
                return rp.JsonResponse({"error": str(e)}, status=403)

        # Get attachments (with authorization check)
        if R.get("action") == "getAttachmentJND":
            try:
                WorkOrderSecurityService.validate_work_order_access(
                    int(R["id"]), request.user, allow_tenant_access=True
                )
                att = self.params["model_jnd"].objects.getAttachmentJND(R["id"])
                return rp.JsonResponse(data={"data": list(att)})
            except PermissionDenied as e:
                return rp.JsonResponse({"error": str(e)}, status=403)

        # Get work order details (with authorization check)
        if R.get("action") == "get_wo_details" and R.get("womid"):
            try:
                WorkOrderSecurityService.validate_work_order_access(
                    int(R["womid"]), request.user, allow_tenant_access=True
                )
                objs = self.params["model_jnd"].objects.get_wo_details(R["womid"])
                return rp.JsonResponse({"data": list(objs)})
            except PermissionDenied as e:
                return rp.JsonResponse({"error": str(e)}, status=403)

        # Return form with instance for update (with authorization check)
        elif R.get("id", None):
            try:
                wo = WorkOrderSecurityService.validate_work_order_access(
                    int(R["id"]), request.user, allow_tenant_access=True
                )
                cxt = {
                    "woform": P["form_class"](request=request, instance=wo),
                    "ownerid": wo.uuid,
                }
                resp = render(request, P["template_form"], cxt)
            except PermissionDenied as e:
                return rp.JsonResponse({"error": str(e)}, status=403)

        return resp

    def post(self, request, *args, **kwargs):
        """
        Handle work order create/update POST requests.

        Returns:
            JsonResponse with work order data or error message
        """
        resp, create = None, True
        try:
            data = QueryDict(request.POST["formData"]).copy()

            if pk := request.POST.get("pk", None):
                # Update existing work order
                ven = utils.get_model_obj(pk, request, self.params)
                form = self.params["form_class"](data, instance=ven, request=request)
                create = False
            else:
                # Create new work order
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
        Save validated work order form with email notification.

        Args:
            form: Validated WorkOrderForm instance
            request: Django request object
            create: True for create, False for update

        Returns:
            JsonResponse with saved work order data

        Raises:
            IntegrityError: On database constraint violation
        """
        logger.info("workorder form is valid")
        try:
            from apps.work_order_management.utils import notify_wo_creation

            with transaction.atomic(using=get_current_db_name()):
                workorder = form.save(commit=False)
                workorder.uuid = request.POST.get("uuid")
                workorder.other_data["created_at"] = timezone.now().strftime(
                    "%d-%b-%Y %H:%M:%S"
                )
                # Generate secure token for email workflows
                workorder.other_data["token"] = WorkOrderSecurityService.generate_secure_token()
                workorder = save_with_audit(workorder, request.user, request.session, create=create)

                if not workorder.ismailsent:
                    workorder = notify_wo_creation(id=workorder.id)

                workorder.add_history()
                logger.info("workorder form saved")

                data = {
                    "msg": f"{workorder.id}",
                    "row": Wom.objects.values(*self.params["fields"]).get(id=workorder.id),
                    "pk": workorder.id,
                }

                return rp.JsonResponse(data, status=200)

        except (IntegrityError, pg_errs.UniqueViolation):
            return utils.handle_intergrity_error("WorkOrder")


class ReplyWorkOrder(View):
    """
    External vendor replies to work orders via email.

    Public view (no LoginRequiredMixin) for email-based workflows.
    Uses token-based authentication for security.

    GET:
        - action=accepted&womid=<id>&token=<token>: Accept work order, start progress
        - action=declined&womid=<id>&token=<token>: Decline work order, mark cancelled
        - action=request_for_submit_wod&womid=<id>&token=<token>: Load questionnaire form

    POST:
        - action=reply_form: Save vendor's reply/reason (with token validation)
        - action=save_work_order_details: Submit questionnaire answers (with token validation)
    
    Security: All actions require valid token from email link to prevent IDOR attacks.
    """

    params = {
        "template": "work_order_management/reply_workorder.html",
        "template_emailform": "work_order_management/wod_email_form.html",
        "model": Wom,
    }

    def get(self, request, *args, **kwargs):
        R = request.GET
        try:
            # Validate token for all actions (prevent IDOR)
            if not R.get("token"):
                return HttpResponse(str(_("Invalid or missing security token")), status=403)

            # Accept work order (with token validation)
            if R["action"] == "accepted" and R["womid"]:
                wo = WorkOrderSecurityService.validate_vendor_access(
                    int(R["womid"]), R["token"]
                )
                if wo.workstatus == Wom.Workstatus.COMPLETED:
                    return HttpResponse(str(_("The work order are already submitted!")))

                wo.workstatus = Wom.Workstatus.INPROGRESS
                logger.info("work order accepted by vendor")
                wo.starttime = timezone.now()
                wo.save()
                cxt = {"accepted": True, "wo": wo}
                return render(request, self.params["template"], context=cxt)

            # Decline work order (with token validation)
            if R["action"] == "declined" and R["womid"]:
                wo = WorkOrderSecurityService.validate_vendor_access(
                    int(R["womid"]), R["token"]
                )
                if wo.workstatus == Wom.Workstatus.COMPLETED:
                    return HttpResponse(str(_("The work order are already submitted!")))

                wo.isdenied = True
                wo.workstatus = Wom.Workstatus.CANCELLED
                logger.info("work order cancelled/denied by vendor")
                wo.save()
                cxt = {"declined": True, "wo": wo}
                return render(request, self.params["template"], context=cxt)

            # Request questionnaire form (with token validation)
            if R["action"] == "request_for_submit_wod":
                wo = WorkOrderSecurityService.validate_vendor_access(
                    int(R["womid"]), R["token"]
                )
                logger.info(f"wo status {wo.workstatus}")

                if wo.workstatus == Wom.Workstatus.INPROGRESS:
                    questions = QuestionSetBelonging.objects.filter(
                        qset_id=wo.qset_id
                    ).select_related("question")
                    cxt = {
                        "qsetname": wo.qset.qsetname,
                        "qsb": questions,
                        "womid": wo.id,
                    }
                    return render(request, self.params["template_emailform"], cxt)

                elif wo.workstatus == Wom.Workstatus.CANCELLED:
                    return HttpResponse(str(_("Sorry the work order is cancelled already!")))

                elif wo.workstatus == Wom.Workstatus.ASSIGNED:
                    return HttpResponse(
                        str(_("Please accept the work order and start the work!"))
                    )

                elif wo.workstatus == Wom.Workstatus.COMPLETED:
                    return HttpResponse(str(_("The work order are already submitted!")))

        except self.params["model"].DoesNotExist:
            return HttpResponse(str(_("The page you are looking for is not found")))

    def post(self, request, *args, **kwargs):
        R = request.POST
        try:
            # Validate token for all POST actions (prevent IDOR)
            if not R.get("token"):
                return HttpResponse(str(_("Invalid or missing security token")), status=403)
            
            wo = WorkOrderSecurityService.validate_vendor_access(
                int(R["womid"]), R["token"]
            )

            # Save vendor reply
            if R.get("action") == "reply_form":
                wo.isdenied = True
                wo.other_data["reply_from_vendor"] = R["reply_from_vendor"]
                wo.save()
                return render(request, self.params["template"])

            # Save work order details
            if R.get("action") == "save_work_order_details":
                self.save_work_order_details(R, wo, request)
                logger.info("form saved successfully")
                return render(
                    request, self.params["template_emailform"], {"wod_saved": True}
                )

        except PermissionDenied as e:
            return HttpResponse(str(e), status=403)
        except self.params["model"].DoesNotExist:
            return HttpResponse(str(_("The page you are looking for is not found")))

    def save_work_order_details(self, R, wo, request):
        """
        Save work order questionnaire answers from vendor.

        Args:
            R: POST data
            wo: Work order instance
            request: Django request object
        """
        logger.info(f"form post data {R}")
        post_data = R.copy()
        post_data.update(request.FILES)
        logger.info(f"postData = {post_data}")

        for k, v in post_data.items():
            if (
                k not in ["ctzoffset", "womid", "action", "csrfmiddlewaretoken"]
                and "_" in k
            ):
                qsb_id = k.split("_")[0]
                qsb_obj = (
                    QuestionSetBelonging.objects.filter(id=qsb_id)
                    .select_related("question")
                    .first()
                )

                # Determine if answer triggers alert
                if qsb_obj.answertype in ["CHECKBOX", "DROPDOWN"]:
                    alerts = v in qsb_obj.alerton
                elif qsb_obj.answertype in ["NUMERIC"] and len(qsb_obj.alerton) > 0:
                    alerton = (
                        qsb_obj.alerton.replace(">", "").replace("<", "").split(",")
                    )
                    if len(alerton) > 1:
                        _min, _max = alerton[0], alerton[1]
                        alerts = float(v) < float(_min) or float(v) > float(_max)
                else:
                    alerts = False

                # Create or update work order detail
                wod, _ = WomDetails.objects.update_or_create(
                    seqno=qsb_obj.seqno,
                    question_id=qsb_obj.question_id,
                    answertype=qsb_obj.answertype,
                    answer=v,
                    isavpt=qsb_obj.isavpt,
                    options=qsb_obj.options,
                    min=qsb_obj.min,
                    max=qsb_obj.max,
                    alerton=qsb_obj.alerton,
                    ismandatory=qsb_obj.ismandatory,
                    wom_id=wo.id,
                    alerts=alerts,
                    cuser_id=1,
                    muser_id=1,
                )

                # Handle file attachments
                if qsb_obj.isavpt and request.FILES:
                    k = f"{qsb_id}-{qsb_obj.answertype}"
                    isuploaded, filename, filepath = utils.upload_vendor_file(
                        request.FILES[k], womid=wo.id
                    )
                    att = self.create_att_record(
                        request.FILES[k], filename, filepath, wod
                    )
                    logger.info(
                        f"Is file uploaded {isuploaded} and attachment is created {att.id}"
                    )

        wo.workstatus = Wom.Workstatus.COMPLETED
        wo.endtime = timezone.now()
        logger.info("work order status changed to completed")
        wo.save()

    def create_att_record(self, file, filename, filepath, wod):
        """
        Create attachment record for uploaded file.

        Args:
            file: Uploaded file object
            filename: Filename
            filepath: File path
            wod: WomDetails instance

        Returns:
            Attachment instance
        """
        from apps.activity.models.attachment_model import Attachment
        from apps.core_onboarding.models import TypeAssist

        ownername = TypeAssist.objects.filter(tacode="WOMDETAILS").first()
        return Attachment.objects.create(
            filepath=filepath,
            filename=filename,
            size=file.size,
            owner=wod.uuid,
            cuser_id=1,
            muser_id=1,
            cdtz=timezone.now(),
            mdtz=timezone.now(),
            ctzoffset=wod.ctzoffset,
            attachmenttype=Attachment.AttachmentType.ATMT,
            ownername_id=ownername.id,
        )
