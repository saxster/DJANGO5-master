from django.db.utils import IntegrityError
from django.db import transaction
from django.forms import model_to_dict
from django.http.request import QueryDict
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, AuthenticationError as DjangoAuthenticationError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError as DjangoValidationError, PermissionDenied
from django.http import response as rp
from django.shortcuts import redirect, render
from django.views import View
from django.http import response as rp
import logging
from django.core.exceptions import SuspiciousOperation
import json
from apps.onboarding.models import Bt
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.utils_new.file_utils import download_qrcode
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    AuthenticationError,
    WrongCredsError,
    PermissionDeniedError,
    SecurityException,
    EnhancedValidationException,
    SystemException,
    EmailServiceException,
    DatabaseException,
    UserManagementException
)
from apps.core.utils_new.http_utils import (
    render_form,
    handle_Exception,
    handle_invalid_form,
    render_form_for_delete,
    render_form_for_update,
    handle_invalid_form,
    get_clean_form_data,
    get_model_obj,
    save_user_session,
    get_instance_for_update,
)
from apps.peoples.filters import CapabilityFilter
from apps.core import utils
import apps.peoples.filters as pft
import apps.peoples.forms as pf
import apps.peoples.models as pm
import apps.onboarding.forms as obf
from .models import Pgbelonging, Pgroup, People
import apps.peoples.utils as putils
from django.contrib import messages
from .forms import PeopleForm, PeopleExtrasForm, LoginForm
from django_email_verification import send_email

logger = logging.getLogger("django")


class SignIn(View):
    template_path = "peoples/login.html"
    error_msgs = {
        "invalid-details": "Sorry that didn't work <br> please try again \
                            with the proper username and password.",
        "invalid-cookies": "Please enable cookies in your browser...",
        "auth-error": "Authentication failed of user with loginid = %s\
                            password = %s",
        "invalid-form": "sign in form is not valid...",
        "critical-error": "something went wrong please follow the traceback to fix it... ",
        "unauthorized-User" : "You are a Mobile User not authorized to \
                                 access the Web Application"
    }

    def get(self, request, *args, **kwargs):
        logger.info("SignIn View")
        request.session.set_test_cookie()
        form = LoginForm()
        return render(request, self.template_path, context={"loginform": form})

    def post(self, request, *args, **kwargs):
        from .utils import display_user_session_info

        form, response = LoginForm(request.POST), None
        logger.info("form submitted")
        try:
            if not request.session.test_cookie_worked():
                logger.warning("cookies are not enabled in user browser", exc_info=True)
                form.add_error(None, self.error_msgs["invalid-cookies"])
                cxt = {"loginform": form}
                response = render(request, self.template_path, context=cxt)
            elif form.is_valid():
                logger.info("Signin form is valid")
                loginid = form.cleaned_data.get("username")
                password = form.cleaned_data.get("password")
                user = pm.People.objects.filter(loginid=loginid).values('people_extras__userfor')
                people = authenticate(request, username=loginid, password=password)
                # utils.set_db_for_router('icicibank')
                if people and (user[0]['people_extras__userfor'] in ['Web', 'Both']):
                    login(request, people)
                    request.session["ctzoffset"] = request.POST.get("timezone")
                    # response = redirect('onboarding:wizard_delete') if request.session.get('wizard_data') else redirect('/dashboard')
                    logger.info(
                        'Login Successfull for people "%s" with loginid "%s" client "%s" site "%s"',
                        people.peoplename,
                        people.loginid,
                        people.client.buname if people.client else "None",
                        people.bu.buname if people.bu else "None",
                    )
                    utils.save_user_session(request, request.user)
                    display_user_session_info(request.session)
                    logger.info(f"User logged in {request.user.peoplecode}")
                    if request.session.get('bu_id') in [1, None]: return redirect('peoples:no_site')
                    if request.session.get('sitecode') not in ["SPSESIC", "SPSPAYROLL", "SPSOPS", "SPSOPERATION", "SPSHR"]:
                        response = redirect('onboarding:wizard_delete') if request.session.get('wizard_data') else redirect('onboarding:rp_dashboard')
                    elif request.session.get('sitecode') in ["SPSOPS"]:
                        response = redirect('reports:generateattendance')
                    elif request.session.get('sitecode') in ["SPSHR"]:
                        response = redirect('employee_creation:employee_creation')
                    elif request.session.get('sitecode') in ["SPSOPERATION"]:
                        response = redirect('reports:generate_declaration_form')
                    else:
                        response = redirect("reports:generatepdf")
                else:
                    logger.warning(self.error_msgs["auth-error"], loginid, "********")
                    if user[0]['people_extras__userfor'] == 'Mobile':
                        form.add_error(None, self.error_msgs["unauthorized-User"])
                        cxt = {"loginform": form}
                        response = render(request, self.template_path, context=cxt)
                    else:
                        form.add_error(None, self.error_msgs["invalid-details"])
                        cxt = {"loginform": form}
                        response = render(request, self.template_path, context=cxt)
            else:
                logger.warning(self.error_msgs["invalid-form"])
                # Log detailed form errors
                logger.warning(f"Form errors: {form.errors}")
                logger.warning(f"Form non-field errors: {form.non_field_errors()}")
                cxt = {"loginform": form}
                response = render(request, self.template_path, context=cxt)
        except DjangoAuthenticationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'authentication', 'loginid': loginid if 'loginid' in locals() else 'unknown'},
                level='warning'
            )
            logger.warning(f"Authentication failed", extra={'correlation_id': correlation_id})
            form.add_error(None, self.error_msgs["invalid-details"])
            cxt = {"loginform": form}
            response = render(request, self.template_path, context=cxt)
        except DjangoValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'form_validation', 'form_data': 'redacted'},
                level='warning'
            )
            logger.warning(f"Form validation failed during login", extra={'correlation_id': correlation_id})
            form.add_error(None, "Invalid form data provided")
            cxt = {"loginform": form}
            response = render(request, self.template_path, context=cxt)
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'permission_check'},
                level='warning'
            )
            logger.warning(f"Permission denied during login", extra={'correlation_id': correlation_id})
            form.add_error(None, self.error_msgs["unauthorized-User"])
            cxt = {"loginform": form}
            response = render(request, self.template_path, context=cxt)
        except (DatabaseException, IntegrityError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'database_query'},
                level='error'
            )
            logger.error(f"Database error during authentication", extra={'correlation_id': correlation_id})
            form.add_error(None, "Service temporarily unavailable, please try again")
            cxt = {"loginform": form}
            response = render(request, self.template_path, context=cxt)
        except SuspiciousOperation as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'security_check', 'ip': request.META.get('REMOTE_ADDR')},
                level='critical'
            )
            logger.critical(f"Suspicious operation detected during login", extra={'correlation_id': correlation_id})
            form.add_error(None, "Security violation detected")
            cxt = {"loginform": form}
            response = render(request, self.template_path, context=cxt)
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'data_processing'},
                level='warning'
            )
            logger.warning(f"Data processing error during login", extra={'correlation_id': correlation_id})
            form.add_error(None, "Invalid data format provided")
            cxt = {"loginform": form}
            response = render(request, self.template_path, context=cxt)
        return response

class SignOut(LoginRequiredMixin, View):
    @staticmethod
    def get(request, *args, **kwargs):
        response = None
        try:
            logout(request)
            logger.info("User logged out DONE!")
            response = redirect("/")
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'logout', 'user_id': request.user.id if request.user.is_authenticated else None},
                level='warning'
            )
            logger.warning(f"Permission denied during logout", extra={'correlation_id': correlation_id})
            messages.warning(request, "Unable to log out: permission denied", "alert alert-warning")
            response = redirect("/dashboard")
        except SuspiciousOperation as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'logout_security', 'ip': request.META.get('REMOTE_ADDR')},
                level='critical'
            )
            logger.critical(f"Suspicious operation during logout", extra={'correlation_id': correlation_id})
            messages.error(request, "Security violation detected", "alert alert-danger")
            response = redirect("/")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'logout_system'},
                level='error'
            )
            logger.error(f"System error during logout", extra={'correlation_id': correlation_id})
            messages.warning(request, "System temporarily unavailable", "alert alert-warning")
            response = redirect("/dashboard")
        return response


class ChangePeoplePassword(LoginRequiredMixin, View):
    template_path = "peoples/people_form_modern.html"
    form_class = PeopleForm
    json_form = PeopleExtrasForm
    model = People

    @staticmethod
    def post(request, *args, **kwargs):
        from django.contrib.auth.forms import SetPasswordForm
        from django.http import JsonResponse

        id, response = request.POST.get("people"), None
        people = People.objects.get(id=id)
        form = SetPasswordForm(people, request.POST)
        if form.is_valid():
            form.save()
            response = JsonResponse(
                {"res": "Password is changed successfully!", "status": 200}
            )
        else:
            response = JsonResponse({"res": form.errors, "status": 500})
        return response


def delete_master(request, params):
    raise NotImplementedError()


class Capability(LoginRequiredMixin, View):
    params = {
        "form_class": pf.CapabilityForm,
        "template_form": "peoples/partials/partial_cap_form.html",
        "template_list": "peoples/capability.html",
        "partial_form": "peoples/partials/partial_cap_form.html",
        "partial_list": "peoples/partials/partial_cap_list.html",
        "related": ["parent"],
        "model": pm.Capability,
        "filter": CapabilityFilter,
        "fields": ["id", "capscode", "capsname", "cfor", "parent__capscode"],
        "form_initials": {"initial": {}},
    }

    def get(self, request, *args, **kwargs):
        R, resp, objects, filtered = request.GET, None, [], 0

        # first load the template
        if R.get("template"):
            return render(request, self.params["template_list"])

        # return cap_list data
        if R.get("action", None) == "list" or R.get("search_term"):
            d = {"list": "cap_list", "filt_name": "cap_filter"}
            self.params.update(d)
            objs = (
                self.params["model"]
                .objects.select_related(*self.params["related"])
                .filter(~Q(capscode="NONE"))
                .values(*self.params["fields"])
            )
            resp = rp.JsonResponse(data={"data": list(objs)}, status=200, safe=False)

        # return cap_form empty
        elif R.get("action", None) == "form":
            cxt = {
                "cap_form": self.params["form_class"](request=request),
                "msg": "create capability requested",
            }
            resp = render_form(request, self.params, cxt)

        # handle delete request
        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = render_form_for_delete(request, self.params, True)

        # return form with instance
        elif R.get("id", None):
            obj = get_model_obj(int(R["id"]), request, self.params)
            resp = render_form_for_update(request, self.params, "cap_form", obj)
        return resp

    def post(self, request, *args, **kwargs):
        resp, create = None, True
        try:
            data = QueryDict(request.POST["formData"])
            pk = request.POST.get("pk", None)
            if pk:
                msg, create = "capability_view", False
                form = get_instance_for_update(
                    data, self.params, msg, int(pk), {"request": request}
                )

            else:
                form = self.params["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = handle_invalid_form(request, self.params, cxt)

        except DjangoValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'capability_form_validation'},
                level='warning'
            )
            logger.warning(f"Capability form validation failed", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Invalid form data provided"}, status=400)
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'capability_save'},
                level='error'
            )
            logger.error(f"Database integrity error saving capability", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Capability already exists or violates constraints"}, status=409)
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'capability_permission'},
                level='warning'
            )
            logger.warning(f"Permission denied for capability operation", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Permission denied"}, status=403)
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'capability_data_processing'},
                level='warning'
            )
            logger.warning(f"Data processing error in capability view", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Invalid data format"}, status=400)
        return resp

    def handle_valid_form(self, form, request, create):
        logger.info("capability form is valid")
        from apps.core.utils import handle_intergrity_error

        try:
            cap = form.save()
            putils.save_userinfo(cap, request.user, request.session, create=create)
            logger.info("capability form saved")
            data = {
                "success": "Record has been saved successfully",
                "row": pm.Capability.objects.values(*self.params["fields"]).get(
                    id=cap.id
                ),
            }
            return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return handle_intergrity_error("Capability")


class PeopleView(LoginRequiredMixin, View):
    params = {
        "form_class": pf.PeopleForm,
        "json_form": pf.PeopleExtrasForm,
        "template_form": "peoples/people_form.html",
        "template_list": "peoples/people_list_modern.html",
        "related": ["peopletype", "bu"],
        "model": pm.People,
        "filter": pft.PeopleFilter,
        "fields": [
            "id",
            "peoplecode",
            "peoplename",
            "peopletype__taname",
            "bu__buname",
            "isadmin",
            "enable",
            "email",
            "mobno",
            "department__taname",
            "designation__taname",
        ],
        "form_initials": {"initial": {}},
    }

    def get(self, request, *args, **kwargs):
        R, resp = request.GET, None

        if R.get("template") == "true":
            # Default to modern view unless explicitly requesting old view
            if R.get("old") == "true":
                return render(request, "peoples/people_list.html")
            else:
                return render(request, self.params["template_list"])  # Modern view by default

        # return cap_list data
        if R.get("action", None) == "list" or R.get("search_term"):
            draw = int(request.GET.get("draw", 1))
            start = int(request.GET.get("start", 0))
            length = int(request.GET.get("length", 10))
            search_value = request.GET.get("search[value]", "").strip()

            order_col = request.GET.get("order[0][column]")
            order_dir = request.GET.get("order[0][dir]")
            column_name = request.GET.get(f"columns[{order_col}][data]")

            objs = self.params["model"].objects.people_list_view(
                request, self.params["fields"], self.params["related"]
            )
            if search_value:
                objs = objs.filter(
                    Q(peoplename__icontains=search_value)
                    | Q(peoplecode__icontains=search_value)
                    | Q(department__taname__icontains=search_value)
                    | Q(bu__buname__icontains=search_value)
                )

            if column_name:
                order_prefix = "" if order_dir == "asc" else "-"
                objs = objs.order_by(f"{order_prefix}{column_name}")

            total = objs.count()
            paginated = objs[start : start + length]
            data = list(paginated)

            from apps.core.services.secure_encryption_service import SecureEncryptionService
            encrypted_fields = ['email', 'mobno']

            for row in data:
                for field in encrypted_fields:
                    if field in row and row[field]:
                        try:
                            value = row[field]
                            if SecureEncryptionService.is_securely_encrypted(value):
                                row[field] = SecureEncryptionService.decrypt(value)
                            elif value.startswith('ENC_V1:'):
                                legacy_payload = value[len('ENC_V1:'):]
                                migration_successful, result = SecureEncryptionService.migrate_legacy_data(legacy_payload)
                                if migration_successful:
                                    row[field] = SecureEncryptionService.decrypt(result)
                                else:
                                    row[field] = legacy_payload
                            else:
                                row[field] = value
                        except (ValueError, TypeError) as e:
                            correlation_id = ErrorHandler.handle_exception(
                                e,
                                context={'operation': 'field_decryption', 'field': field},
                                level='warning'
                            )
                            logger.warning(f"Field decryption failed for {field}, treating as plain text", extra={'correlation_id': correlation_id})
                        except SecurityException as e:
                            correlation_id = ErrorHandler.handle_exception(
                                e,
                                context={'operation': 'field_decryption_security', 'field': field},
                                level='critical'
                            )
                            logger.critical(f"Security issue during field decryption for {field}", extra={'correlation_id': correlation_id})
                            row[field] = "[ENCRYPTED]"  # Hide sensitive data

            return rp.JsonResponse(
                {
                    "draw": draw,
                    "recordsTotal": total,
                    "recordsFiltered": total,
                    "data": data,
                },
                status=200,
            )

        if (
            R.get("action", None) == "qrdownload"
            and R.get("code", None)
            and R.get("name", None)
        ):
            return download_qrcode(
                R["code"], R["name"], "PEOPLEQR", request.session, request
            )

        # return cap_form empty
        if R.get("action", None) == "form":
            cxt = {
                "peopleform": self.params["form_class"](request=request),
                "pref_form": self.params["json_form"](request=request),
                "ta_form": obf.TypeAssistForm(auto_id=False, request=request),
                "msg": "create people requested",
            }
            resp = render(request, self.params["template_form"], cxt)

        # handle delete request
        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = render_form_for_delete(request, self.params, True)

        # return form with instance
        elif R.get("id", None):
            from .utils import get_people_prefform

            people = get_model_obj(R["id"], request, self.params)
            cxt = {
                "peopleform": self.params["form_class"](
                    instance=people, request=request
                ),
                "pref_form": get_people_prefform(people, request),
                "ta_form": obf.TypeAssistForm(auto_id=False, request=request),
                "msg": "update people requested",
            }
            resp = render(request, self.params["template_form"], context=cxt)
            
        # default case - redirect to people list if no specific action
        else:
            from django.shortcuts import redirect
            resp = redirect(f"{request.path}?template=true&modern=true")
            
        return resp

    def post(self, request, *args, **kwargs):
        import html
        resp, create = None, True
        
        # Decode HTML entities in the formData string
        form_data_string = request.POST.get("formData", "")
        decoded_form_data = html.unescape(form_data_string)
        data = QueryDict(decoded_form_data)
        
        try:
            if pk := request.POST.get("pk", None):
                msg, create = "people_view", False
                people = get_model_obj(pk, request, self.params)
                form = self.params["form_class"](
                    data, files=request.FILES, instance=people, request=request
                )
            else:
                form = self.params["form_class"](data, request=request)
            jsonform = self.params["json_form"](data, request=request)
            if form.is_valid() and jsonform.is_valid():
                resp = self.handle_valid_form(form, jsonform, request, create)
            else:
                cxt = {"errors": form.errors}
                if jsonform.errors:
                    cxt["errors"] = jsonform.errors
                resp = handle_invalid_form(request, self.params, cxt)
        except DjangoValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'people_form_validation'},
                level='warning'
            )
            logger.warning(f"People form validation failed", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Invalid form data provided"}, status=400)
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'people_save'},
                level='error'
            )
            logger.error(f"Database integrity error saving people record", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "People record already exists or violates constraints"}, status=409)
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'people_permission'},
                level='warning'
            )
            logger.warning(f"Permission denied for people operation", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Permission denied"}, status=403)
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'people_data_processing'},
                level='warning'
            )
            logger.warning(f"Data processing error in people view", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Invalid data format"}, status=400)
        return resp

    @staticmethod
    def handle_valid_form(form, jsonform, request, create):
        logger.info("people form is valid")
        from apps.core.utils import handle_intergrity_error

        try:
            people = form.save()
            if request.FILES.get("peopleimg"):
                people.peopleimg = request.FILES["peopleimg"]
            if not people.password:
                people.set_password(form.cleaned_data["peoplecode"])
            if putils.save_jsonform(jsonform, people):
                buid = people.bu.id if people.bu else None
                people = putils.save_userinfo(
                    people, request.user, request.session, create=create, bu=buid
                )
                logger.info("people form saved")
            data = {"pk": people.id}
            return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return handle_intergrity_error("People")


class PeopleGroup(LoginRequiredMixin, View):
    params = {
        "form_class": pf.PeopleGroupForm,
        "template_form": "peoples/partials/partial_pgroup_form.html",
        "template_list": "peoples/peoplegroup.html",
        "partial_form": "peoples/partials/partial_pgroup_form.html",
        "related": ["identifier", "bu"],
        "model": pm.Pgroup,
        "fields": ["groupname", "enable", "id", "bu__buname", "bu__bucode"],
        "form_initials": {},
    }

    def get(self, request, *args, **kwargs):
        R, resp, objects, filtered = request.GET, None, [], 0
        # first load the template
        if R.get("template"):
            # Check if classic view is explicitly requested
            if R.get("classic"):
                return render(request, self.params["template_list"])
            # Default to modern view, preserving any additional parameters
            context = {}
            if R.get("type"):
                context["type_param"] = R.get("type")
            return render(request, "peoples/peoplegroup_modern.html", context)

        # return list data
        if R.get("action", None) == "list" or R.get("search_term"):
            objs = (
                self.params["model"]
                .objects.select_related(*self.params["related"])
                .filter(
                    ~Q(id=-1),
                    bu_id=request.session["bu_id"],
                    identifier__tacode="PEOPLEGROUP",
                    client_id=request.session["client_id"],
                )
                .values(*self.params["fields"])
                .order_by("-mdtz")
            )
            return rp.JsonResponse(data={"data": list(objs)})

        # return form empty
        if R.get("action", None) == "form":
            cxt = {
                "pgroup_form": self.params["form_class"](request=request),
                "msg": "create people group requested",
            }
            resp = render_form(request, self.params, cxt)

        # handle delete request
        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.delete_pgroup_pgbelonging_data(request)

        elif R.get("id", None):
            obj = get_model_obj(int(R["id"]), request, self.params)
            peoples = pm.Pgbelonging.objects.filter(pgroup=obj).values_list(
                "people", flat=True
            )
            FORM = self.params["form_class"](
                request=request, instance=obj, initial={"peoples": list(peoples)}
            )
            resp = render_form_for_update(
                request, self.params, "pgroup_form", obj, FORM=FORM
            )
        return resp

    def post(self, request, *args, **kwargs):
        resp, create = None, True
        try:
            data = get_clean_form_data(request)
            if pk := request.POST.get("pk", None):
                pm.Pgbelonging.objects.filter(pgroup_id=int(pk)).delete()
                msg = "pgroup_view"
                form = get_instance_for_update(
                    data, self.params, msg, int(pk), kwargs={"request": request}
                )
                create = False
            else:
                form = self.params["form_class"](data, request=request)

            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = handle_invalid_form(request, self.params, cxt)
        except DjangoValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'people_group_validation'},
                level='warning'
            )
            logger.warning(f"People group form validation failed", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Invalid form data provided"}, status=400)
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'people_group_save'},
                level='error'
            )
            logger.error(f"Database integrity error saving people group", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "People group already exists or violates constraints"}, status=409)
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'people_group_permission'},
                level='warning'
            )
            logger.warning(f"Permission denied for people group operation", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Permission denied"}, status=403)
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'people_group_data_processing'},
                level='warning'
            )
            logger.warning(f"Data processing error in people group view", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Invalid data format"}, status=400)
        return resp

    def handle_valid_form(self, form, request, create):
        logger.info("pgroup form is valid")
        from apps.core.utils import handle_intergrity_error

        try:
            pg = form.save(commit=False)
            putils.save_userinfo(pg, request.user, request.session, create=create)
            save_pgroupbelonging(pg, request)
            logger.info("people group form saved")
            data = {"row": Pgroup.objects.values(*self.params["fields"]).get(id=pg.id)}
            return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return handle_intergrity_error("Pgroup")


class SiteGroup(LoginRequiredMixin, View):
    params = {
        "form_class": pf.SiteGroupForm,
        "template_form": "peoples/sitegroup_form.html",
        "template_list": "peoples/sitegroup_list.html",
        "related": ["identifier"],
        "model": pm.Pgroup,
        "fields": ["groupname", "enable", "id"],
        "form_initials": {},
    }

    def get(self, request, *args, **kwargs):
        R, resp, objects, filtered = request.GET, None, [], 0
        # first load the template
        if R.get("template"):
            # Check if classic view is explicitly requested
            if R.get("classic"):
                return render(request, self.params["template_list"])
            # Default to modern view
            return render(request, "peoples/sitegroup_list_modern.html")

        # for list view of group
        if R.get("action") == "list":
            total, filtered, objs = pm.Pgroup.objects.list_view_sitegrp(R, request)
            logger.info(
                "SiteGroup objects %s retrieved from db", (total or "No Records!")
            )
            resp = rp.JsonResponse(
                data={
                    "draw": R["draw"],
                    "data": list(objs),
                    "recordsFiltered": filtered,
                    "recordsTotal": total,
                }
            )
            return resp

        # to populate all sites table
        if R.get("action", None) == "allsites":
            objs, idfs = Bt.objects.get_bus_idfs(
                R, request=request, idf=R["sel_butype"]
            )
            resp = rp.JsonResponse(data={"data": list(objs), "idfs": list(idfs)})
            return resp

        if R.get("action") == "loadSites":
            site_group_id = R.get("id")
            # Check if ID is valid (not empty or None)
            if not site_group_id or not site_group_id.strip():
                resp = rp.JsonResponse(
                    data={
                        "assigned_sites": [],
                        "error": "Site group ID is required"
                    },
                    status=400
                )
                return resp
            
            try:
                # Convert to int to validate it's a number
                site_group_id = int(site_group_id)
                data = Pgbelonging.objects.get_assigned_sitesto_sitegrp(site_group_id)
                resp = rp.JsonResponse(
                    data={
                        "assigned_sites": list(data),
                    }
                )
                return resp
            except (ValueError, TypeError):
                resp = rp.JsonResponse(
                    data={
                        "assigned_sites": [],
                        "error": "Invalid site group ID"
                    },
                    status=400
                )
                return resp

        # form without instance to create new data
        if R.get("action", None) == "form":
            # options = self.get_options()
            cxt = {
                "sitegrpform": self.params["form_class"](request=request),
                "msg": "create site group requested",
            }
            return render(request, self.params["template_form"], context=cxt)

        # handle delete request
        if R.get("action", None) == "delete" and R.get("id", None):
            obj = get_model_obj(R["id"], request, self.params)
            pm.Pgbelonging.objects.filter(pgroup_id=obj.id).delete()
            obj.delete()
            return rp.JsonResponse(data=None, status=200, safe=False)

        # form with instance to load existing data
        if R.get("id", None):
            obj = get_model_obj(int(R["id"]), request, self.params)
            sites = pm.Pgbelonging.objects.filter(pgroup=obj).values_list(
                "assignsites", flat=True
            )
            cxt = {
                "sitegrpform": self.params["form_class"](request=request, instance=obj),
                "assignedsites": sites,
            }
            resp = render(request, self.params["template_form"], context=cxt)
            return resp

    def post(self, request, *args, **kwargs):
        import json
        import html
        
        # Parse and clean the form data
        raw_form_data = request.POST["formData"]
        
        # If the form data is HTML-encoded, decode it
        if '&amp;' in raw_form_data:
            raw_form_data = html.unescape(raw_form_data)
        
        data = QueryDict(raw_form_data)
        
        # Parse assignedSites with error handling
        try:
            import urllib.parse
            import html
            assigned_sites_raw = request.POST.get("assignedSites", "[]")
            
            # If it's URL encoded, decode it first
            if assigned_sites_raw.startswith('%5B'):  # URL encoded '['
                assigned_sites_raw = urllib.parse.unquote(assigned_sites_raw)
            
            # HTML decode to convert &quot; to " and other HTML entities
            assigned_sites_raw = html.unescape(assigned_sites_raw)
            
            assignedSites = json.loads(assigned_sites_raw)
        except (json.JSONDecodeError, ValueError) as e:
            # Log the actual data for debugging
            assigned_sites_raw = request.POST.get("assignedSites", "[]")
            print(f"Failed to parse assignedSites: '{assigned_sites_raw}'")
            print(f"Error: {str(e)}")
            
            return rp.JsonResponse(
                data={
                    "success": False,
                    "errors": {"assignedSites": ["Invalid JSON format for assigned sites"]},
                    "error_details": f"Raw data: '{assigned_sites_raw[:100]}...' Error: {str(e)}"
                },
                status=400
            )
        pk = data.get("pk", None)
        try:
            # Check if pk is valid (not None, "None", or empty string)
            if pk and pk not in ["None", ""] and pk.strip():
                msg = "pgroup_view"
                form = get_instance_for_update(
                    data, self.params, msg, int(pk), kwargs={"request": request}
                )
                create = False
            else:
                form = self.params["form_class"](data, request=request)

            if form.is_valid():
                resp = self.handle_valid_form(form, assignedSites, request)
            else:
                cxt = {"errors": form.errors}
                resp = handle_invalid_form(request, self.params, cxt)
        except DjangoValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'site_group_validation'},
                level='warning'
            )
            logger.warning(f"Site group form validation failed", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Invalid form data provided"}, status=400)
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'site_group_save'},
                level='error'
            )
            logger.error(f"Database integrity error saving site group", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Site group already exists or violates constraints"}, status=409)
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'site_group_permission'},
                level='warning'
            )
            logger.warning(f"Permission denied for site group operation", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Permission denied"}, status=403)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'site_group_data_processing'},
                level='warning'
            )
            logger.warning(f"Data processing error in site group view", extra={'correlation_id': correlation_id})
            resp = rp.JsonResponse({"error": "Invalid data format or JSON syntax"}, status=400)
        return resp

    def handle_valid_form(self, form, assignedSites, request):
        logger.info("pgroup form is valid")
        from apps.core.utils import handle_intergrity_error

        try:
            with transaction.atomic(using=get_current_db_name()):
                pg = form.save(commit=False)
                putils.save_userinfo(pg, request.user, request.session)
                self.save_assignedSites(pg, assignedSites, request)
                logger.info("people group form saved")
                data = {
                    "success": "Record has been saved successfully",
                    "pk": pg.pk,
                    "row": model_to_dict(pg),
                }
                return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return handle_intergrity_error("Pgroup")

    @staticmethod
    def resest_assignedsites(pg):
        pm.Pgbelonging.objects.filter(pgroup_id=pg.id).delete()

    def save_assignedSites(self, pg, sitesArray, request):
        S = request.session
        self.resest_assignedsites(pg)
        for site in sitesArray:
            pgb = pm.Pgbelonging(
                pgroup=pg,
                people_id=1,
                assignsites_id=site["buid"],
                client_id=S["client_id"],
                bu_id=S["bu_id"],
                tenant_id=S.get("tenantid", 1),
            )
            putils.save_userinfo(pgb, request.user, request.session)


class NoSite(View):
    def get(self, request):
        cxt = {"nositeform": pf.NoSiteForm(session=request.session)}
        return render(request, "peoples/nosite.html", cxt)

    def post(self, request):
        form = pf.NoSiteForm(request.POST, session=request.session)
        if form.is_valid():
            bu_id = form.cleaned_data["site"]
            bu = Bt.objects.get(id=bu_id)
            request.session["bu_id"] = bu_id
            request.session["sitename"] = bu.buname
            pm.People.objects.filter(id=request.user.id).update(bu_id=bu_id)
            return redirect("/dashboard/")


def verifyemail(request):
    logger.info("Email verification requested", extra={'user_id': request.GET.get("userid"), 'correlation_id': getattr(request, 'correlation_id', None)})
    userid = request.GET.get("userid")
    
    if not userid:
        messages.error(
            request, "Invalid request: No user ID provided", "alert alert-danger"
        )
        return redirect("login")
    
    try:
        user = People.objects.get(id=userid)
        
        # Store the user ID in session to use during verification
        request.session['pending_verification_user_id'] = userid
        
        send_email(user)
        messages.success(
            request,
            "Verification email has been sent to your email address",
            "alert alert-success",
        )
        logger.info("message sent to %s (ID: %s)", user.email, userid)
    except People.DoesNotExist:
        messages.error(
            request, f"User with ID {userid} not found", "alert alert-danger"
        )
        logger.error("User with id %s does not exist", userid)
    except EmailServiceException as e:
        correlation_id = ErrorHandler.handle_exception(
            e,
            context={'operation': 'email_verification', 'userid': userid},
            level='error'
        )
        messages.error(
            request, "Email service temporarily unavailable", "alert alert-danger"
        )
        logger.error(f"Email verification failed - service error", extra={'correlation_id': correlation_id})
    except PermissionDenied as e:
        correlation_id = ErrorHandler.handle_exception(
            e,
            context={'operation': 'email_verification_permission', 'userid': userid},
            level='warning'
        )
        messages.error(
            request, "Permission denied for email verification", "alert alert-danger"
        )
        logger.warning(f"Email verification permission denied", extra={'correlation_id': correlation_id})
    except (ValueError, TypeError) as e:
        correlation_id = ErrorHandler.handle_exception(
            e,
            context={'operation': 'email_verification_data', 'userid': userid},
            level='warning'
        )
        messages.error(
            request, "Invalid user data for verification", "alert alert-danger"
        )
        logger.warning(f"Email verification data error", extra={'correlation_id': correlation_id})
    except SystemException as e:
        correlation_id = ErrorHandler.handle_exception(
            e,
            context={'operation': 'email_verification_system', 'userid': userid},
            level='critical'
        )
        messages.error(
            request, "System error during email verification", "alert alert-danger"
        )
        logger.critical(f"Email verification system error", extra={'correlation_id': correlation_id})
    return redirect("login")
