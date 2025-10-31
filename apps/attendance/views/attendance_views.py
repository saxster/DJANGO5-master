"""
Attendance view for managing employee attendance records.
Handles punch in/out, SOS alerts, site diversions, and crisis management.
"""

from .base import *


class Attendance(LoginRequiredMixin, View):
    """
    Main attendance view handling:
    - Attendance records (punch in/out)
    - SOS alerts
    - Site diversions
    - Site crisis management
    - Geofence location tracking
    """

    params = {
        "form_class": atf.AttendanceForm,
        "template_form": "attendance/partials/partial_attendance_form.html",
        "template_list": "attendance/attendance_modern.html",
        "template_list_sos": "attendance/sos_list.html",
        "template_list_site_diversions": "attendance/site_diversions.html",
        "template_list_sitecrisis": "attendance/sitecrisis_list.html",
        "partial_form": "attendance/partials/partial_attendance_form.html",
        "partial_list": "attendance/partials/partial_attendance_list.html",
        "related": ["people", "bu", "verifiedby", "peventtype", "shift"],
        "model": atdm.PeopleEventlog,
        "filter": AttendanceFilter,
        "form_initials": {},
        "fields": [
            "id",
            "people__peoplename",
            "people__peoplecode",
            "verifiedby__peoplename",
            "peventtype__taname",
            "peventtype__tacode",
            "bu__buname",
            "datefor",
            "uuid",
            "people__id",
            "punchintime",
            "punchouttime",
            "facerecognitionin",
            "facerecognitionout",
            "shift__shiftname",
            "ctzoffset",
            "peventlogextras",
            "sL",
            "eL",
            "people__location__locname",
            "people__mobno",
            "bu__siteincharge__peoplename",
            "bu__siteincharge__mobno",
            "bu__siteincharge__email",
            "shift__starttime",
            "shift__endtime",
        ],
    }

    def get(self, request, *args, **kwargs):
        R, P, resp = request.GET, self.params, None

        if R.get("template") == "sos_template":
            return render(request, P["template_list_sos"])
        if R.get("template") == "site_diversions":
            return render(request, P["template_list_site_diversions"])
        if R.get("template") == "sitecrisis":
            return render(request, P["template_list_sitecrisis"])

        if R.get("template"):
            return render(request, self.params["template_list"])
        # return attendance_list data

        if R.get("action") == "sos_list_view":
            objs = self.params["model"].objects.get_sos_listview(request)
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if R.get("action") == "get_site_diversion_list":
            objs = self.params["model"].objects.get_diversion_countorlist(request)
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if R.get("action") == "get_sitecrisis_list":
            objs = self.params["model"].objects.get_sitecrisis_countorlist(request)
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if R.get("action", None) == "list" or R.get("search_term"):
            d = {"list": "attd_list", "filt_name": "attd_filter"}
            self.params.update(d)
            objs = self.params["model"].objects.get_peopleevents_listview(
                P["related"], P["fields"], request
            )
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if request.GET.get("action") == "getLocationStatus":
            people_id = request.GET.get("peopleid")
            # client_code = request.GET.get("clientcode")

            # Query geofence_id
            get_geofence_id = am.Job.objects.filter(
                people_id=people_id, identifier="GEOFENCE"
            ).values("geofence_id")

            # Check if geofence_id exists
            if not get_geofence_id.exists():
                return rp.JsonResponse(
                    {"error": "No geofence_id found for this people_id"}, status=404
                )

            geofence_id = get_geofence_id[0]["geofence_id"]

            # Query geofence
            get_geofence = (
                ob.GeofenceMaster.objects.filter(id=geofence_id, enable=True)
                .exclude(id=1)
                .values("geofence")
            )

            # Check if geofence exists
            if not get_geofence.exists():
                return rp.JsonResponse(
                    {"error": "Geofence not found or disabled"}, status=404
                )

            try:
                from shapely.wkt import loads

                # Clean WKT and process polygon
                geofence_wkt_cleaned = str(get_geofence[0]["geofence"]).split(";")[1]
                polygon = loads(geofence_wkt_cleaned)
                coordinates_list = list(polygon.exterior.coords)

                # Return coordinates
                return rp.JsonResponse(
                    {"geofence_coords": coordinates_list}, status=200
                )

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                return rp.JsonResponse({"error": str(e)}, status=500)

        # return attemdance_form empty
        if R.get("action", None) == "form":
            cxt = {
                "attd_form": self.params["form_class"](),
                "msg": "create attendance requested",
            }
            resp = utils.render_form(request, self.params, cxt)

        # handle delete request
        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, self.params)

        # return form with instance
        elif R.get("id", None):
            obj = utils.get_model_obj(R["id"], request, self.params)
            resp = utils.render_form_for_update(request, self.params, "attd_form", obj)
        return resp

    def post(self, request, *args, **kwargs):
        resp, create = None, True
        try:
            data = QueryDict(request.POST["formData"])
            if pk := request.POST.get("pk", None):
                msg = "attendance_view"
                form = utils.get_instance_for_update(data, self.params, msg, int(pk))
                create = False
            else:
                form = self.params["form_class"](data)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.params, cxt)
        except ValidationError as e:
            # Handle Django validation errors
            user_msg, log_msg, status = handle_attendance_exception(
                AttendanceValidationError("Form validation failed", field_errors=getattr(e, 'error_dict', {})),
                context={'view': 'attendance', 'action': 'post', 'user': request.user.id}
            )
            logger.warning(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)

        except IntegrityError as e:
            # Handle database integrity errors
            user_msg, log_msg, status = handle_attendance_exception(
                AttendanceDataCorruptionError("Data integrity violation", details={'error': str(e)}),
                context={'view': 'attendance', 'action': 'post', 'user': request.user.id}
            )
            logger.error(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)

        except DatabaseError as e:
            # Handle database connection/query errors
            user_msg, log_msg, status = handle_attendance_exception(
                AttendanceProcessingError("Database operation failed", operation='attendance_save'),
                context={'view': 'attendance', 'action': 'post', 'user': request.user.id}
            )
            logger.error(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)

        except (ObjectDoesNotExist, TypeError, ValueError) as e:
            # Handle specific data errors
            mapped_exc = map_django_exception(e, "Invalid attendance data")
            user_msg, log_msg, status = handle_attendance_exception(
                mapped_exc,
                context={'view': 'attendance', 'action': 'post', 'user': request.user.id}
            )
            logger.warning(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)

        except AttendanceError as e:
            # Handle custom attendance errors
            user_msg, log_msg, status = handle_attendance_exception(
                e, context={'view': 'attendance', 'action': 'post', 'user': request.user.id}
            )
            logger.error(log_msg)
            return rp.JsonResponse({"error": user_msg}, status=status)
        return resp

    @staticmethod
    def handle_valid_form(form, request, create):
        logger.info("attendance form is valid")
        try:
            with transaction.atomic(using=get_current_db_name()):
                attd = form.save()
                putils.save_userinfo(attd, request.user, request.session, create)
                logger.info("attendance form saved")
                data = {
                    "success": "Record has been saved successfully",
                    "type": attd.peventtype.tacode,
                }
                return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return utils.handle_intergrity_error("Attendance")


__all__ = ['Attendance']
