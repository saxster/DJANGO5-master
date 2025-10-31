"""
Work Order Management - Vendor Views

Handles vendor entity CRUD operations.

Classes:
    - VendorView: Vendor create, read, update, delete operations

Refactored: October 2025
Original: work_order_management/views.py:54-142 (88 lines)
"""

from .base import (
    LoginRequiredMixin, View, render, transaction, IntegrityError,
    DatabaseError, ObjectDoesNotExist, ValidationError,
    rp, logger, pg_errs, Vendor, VendorForm, utils,
    get_current_db_name, get_clean_form_data, save_with_audit
)


class VendorView(LoginRequiredMixin, View):
    """
    Vendor CRUD operations view.

    GET:
        - template: Render vendor list template
        - action=list: Return vendor list as JSON
        - action=form: Return empty vendor form
        - action=delete&id=<id>: Delete vendor
        - id=<id>: Return form with vendor instance

    POST:
        - Create new vendor (no pk)
        - Update existing vendor (with pk)
    """

    params = {
        "form_class": VendorForm,
        "template_form": "work_order_management/vendor_form.html",
        "template_list": "work_order_management/vendor_list.html",
        "related": ["cuser"],
        "model": Vendor,
        "fields": [
            "code",
            "name",
            "mobno",
            "email",
            "cdtz",
            "type__taname",
            "cuser__peoplename",
            "ctzoffset",
            "id",
        ],
    }

    def get(self, request, *args, **kwargs):
        R, resp, P = request.GET, None, self.params

        # Return template
        if R.get("template"):
            return render(request, P["template_list"])

        # Return vendor list data
        if R.get("action", None) == "list":
            objs = P["model"].objects.get_vendor_list(
                request, P["fields"], P["related"]
            )
            return rp.JsonResponse(data={"data": list(objs)})

        # Return empty form
        elif R.get("action", None) == "form":
            cxt = {
                "vendor_form": P["form_class"](request=request),
                "msg": "create vendor requested",
            }
            resp = utils.render_form(request, P, cxt)

        # Handle delete request
        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, P, True)

        # Return form with instance for update
        elif R.get("id", None):
            obj = utils.get_model_obj(int(R["id"]), request, P)
            resp = utils.render_form_for_update(request, P, "vendor_form", obj)

        return resp

    def post(self, request, *args, **kwargs):
        """
        Handle vendor create/update POST requests.

        Returns:
            JsonResponse with vendor data or error message
        """
        resp, create = None, True
        try:
            data = get_clean_form_data(request)

            if pk := request.POST.get("pk", None):
                # Update existing vendor
                ven = utils.get_model_obj(pk, request, self.params)
                form = self.params["form_class"](data, instance=ven, request=request)
                create = False
            else:
                # Create new vendor
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
        Save validated vendor form with GPS location.

        Args:
            form: Validated VendorForm instance
            request: Django request object
            create: True for create, False for update

        Returns:
            JsonResponse with saved vendor data

        Raises:
            IntegrityError: On duplicate vendor code/unique constraint violation
        """
        logger.info("vendor form is valid")
        try:
            with transaction.atomic(using=get_current_db_name()):
                vendor = form.save(commit=False)
                vendor.gpslocation = form.cleaned_data["gpslocation"]
                vendor = save_with_audit(vendor, request.user, request.session, create=create)

                logger.info("vendor form saved")
                data = {
                    "msg": f"{vendor.name}",
                    "row": Vendor.objects.values(*self.params["fields"]).get(id=vendor.id),
                }
                return rp.JsonResponse(data, status=200)

        except (IntegrityError, pg_errs.UniqueViolation):
            return utils.handle_intergrity_error("Vendor")
