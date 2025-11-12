"""
Conveyance (Travel Expense) view for managing employee travel expenses.
Handles transport mode tracking, journey paths, and expense calculations.
"""

from .base import (
    LoginRequiredMixin,
    IntegrityError,
    DatabaseError,
    transaction,
    rp,
    QueryDict,
    render,
    View,
    ObjectDoesNotExist,
    ValidationError,
    atf,
    atdm,
    am,
    AttendanceFilter,
    putils,
    save_linestring_and_update_pelrecord,
    get_current_db_name,
    AttendanceError,
    AttendanceValidationError,
    AttendanceProcessingError,
    AttendanceDataCorruptionError,
    handle_attendance_exception,
    map_django_exception,
    logging,
    json,
    utils,
    logger,
)


class Conveyance(LoginRequiredMixin, View):
    """
    Travel expense view handling:
    - Travel expense records
    - Transport mode tracking
    - Journey path visualization
    - Distance and duration calculations
    """

    model = (atdm.PeopleEventlog,)
    params = {
        "fields": [
            "punchintime",
            "punchouttime",
            "bu__buname",
            "ctzoffset",
            "bu__bucode",
            "people__peoplename",
            "people__peoplecode",
            "transportmodes",
            "distance",
            "duration",
            "expamt",
            "id",
            "start",
            "end",
        ],
        "template_list": "attendance/travel_expense.html",
        "template_form": "attendance/travel_expense_form.html",
        "related": ["bu", "people"],
        "model": atdm.PeopleEventlog,
        "form_class": atf.ConveyanceForm,
    }

    def get(self, request, *args, **kwargs):
        R, resp, objects, filtered = request.GET, None, [], 0

        # first load the template
        if R.get("template"):
            return render(request, self.params["template_list"])

        # then load the table with objects for table_view
        if R.get("action", None) == "list" or R.get("search_term"):
            objs = self.params["model"].objects.get_lastmonth_conveyance(
                request, self.params["fields"], self.params["related"]
            )
            resp = rp.JsonResponse(data={"data": list(objs)})

        # return cap_form empty for creation
        elif R.get("action", None) == "form":
            cxt = {
                "conveyanceform": self.params["form_class"](),
                "msg": "create conveyance requested",
            }
            resp = render(request, self.params["template_form"], context=cxt)

        # handle delete request
        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, self.params, False)

        # return form with instance for update
        elif R.get("id", None):
            obj = utils.get_model_obj(int(R["id"]), request, self.params)
            save_linestring_and_update_pelrecord(obj)
            
            # Create the form
            form = self.params["form_class"](request=request, instance=obj)
            
            # Prepare initial values for the template
            initial_transport_modes = []
            if obj.transportmodes:
                transport_data = obj.transportmodes
                if transport_data and len(transport_data) > 0:
                    first_item = transport_data[0]
                    if isinstance(first_item, str) and first_item.startswith('['):
                        try:
                            initial_transport_modes = json.loads(first_item)
                        except (json.JSONDecodeError, ValueError, TypeError) as e:
                            initial_transport_modes = transport_data
                    else:
                        initial_transport_modes = transport_data
            
            # Get geojson location strings
            geojson_startlocation = ""
            geojson_endlocation = ""
            if obj.geojson:
                geojson_startlocation = obj.geojson.get("startlocation", "")
                geojson_endlocation = obj.geojson.get("endlocation", "")
            
            cxt = {
                "conveyanceform": form,
                "edit": True,
                "transport_modes_initial": json.dumps(initial_transport_modes) if initial_transport_modes else "[]",
                "startlocation_initial": obj.startlocation_display if obj.startlocation else "",
                "endlocation_initial": obj.endlocation_display if obj.endlocation else "",
                "geojson_startlocation": geojson_startlocation,
                "geojson_endlocation": geojson_endlocation,
            }
            resp = render(request, self.params["template_form"], context=cxt)

        # return journey path of instance
        elif R.get("action") == "getpath":
            data = atdm.PeopleEventlog.objects.getjourneycoords(R["conid"])
            resp = rp.JsonResponse(data={"obj": list(data)}, status=200)
        return resp

    def post(self, request, *args, **kwargs):
        resp, create = None, True
        try:
            # convert queryparams to python datatypes
            data = QueryDict(request.POST["formData"])
            if pk := data.get("pk", None):
                msg = "conveyance_view"
                form = utils.get_instance_for_update(data, self.params, msg, int(pk))
                create = False
            else:
                form = self.params["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.params, cxt)
        except ValidationError as e:
            # Handle Django validation errors
            user_msg, log_msg, status = handle_attendance_exception(
                AttendanceValidationError("Conveyance form validation failed", field_errors=getattr(e, 'error_dict', {})),
                context={'view': 'conveyance', 'action': 'post', 'user': request.user.id}
            )
            logger.warning(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)

        except IntegrityError as e:
            # Handle database integrity errors
            user_msg, log_msg, status = handle_attendance_exception(
                AttendanceDataCorruptionError("Conveyance data integrity violation", details={'error': str(e)}),
                context={'view': 'conveyance', 'action': 'post', 'user': request.user.id}
            )
            logger.error(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)

        except DatabaseError as e:
            # Handle database connection/query errors
            user_msg, log_msg, status = handle_attendance_exception(
                AttendanceProcessingError("Conveyance database operation failed", operation='conveyance_save'),
                context={'view': 'conveyance', 'action': 'post', 'user': request.user.id}
            )
            logger.error(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)

        except json.JSONDecodeError as e:
            # Handle JSON parsing errors
            user_msg, log_msg, status = handle_attendance_exception(
                AttendanceValidationError("Invalid JSON data in request", details={'json_error': str(e)}),
                context={'view': 'conveyance', 'action': 'post', 'user': request.user.id}
            )
            logger.warning(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)

        except (ObjectDoesNotExist, TypeError, ValueError) as e:
            # Handle specific data errors
            mapped_exc = map_django_exception(e, "Invalid conveyance data")
            user_msg, log_msg, status = handle_attendance_exception(
                mapped_exc,
                context={'view': 'conveyance', 'action': 'post', 'user': request.user.id}
            )
            logger.warning(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)

        except AttendanceError as e:
            # Handle custom attendance errors
            user_msg, log_msg, status = handle_attendance_exception(
                e, context={'view': 'conveyance', 'action': 'post', 'user': request.user.id}
            )
            logger.error(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)
        return resp

    @staticmethod
    def handle_valid_form(form, request, create):
        logger.info("conveyance form is valid")
        from apps.core.utils import handle_intergrity_error

        try:
            with transaction.atomic(using=get_current_db_name()):
                cy = form.save()
                putils.save_userinfo(cy, request.user, request.session, create=create)
                logger.info("conveyance form saved")
                return rp.JsonResponse(data={"pk": cy.id}, status=200)
        except IntegrityError:
            return handle_intergrity_error("conveyance")


__all__ = ['Conveyance']
