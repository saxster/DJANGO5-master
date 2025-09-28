from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import QuestionSet
import apps.schedhuler.utils as sutils
import apps.peoples.utils as putils
from django.contrib import messages
from django.core.exceptions import EmptyResultSet, ValidationError, PermissionDenied
from django.db.utils import IntegrityError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import Http404, QueryDict, response as rp, JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from apps.core import utils
from pprint import pformat
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    SchedulingException,
    DatabaseException,
    SystemException,
    EnhancedValidationException,
    BusinessLogicException
)

from apps.activity.models.job_model import Job, Jobneed, JobneedDetails
import apps.peoples.models as pm
from datetime import datetime, time, timedelta, timezone, date
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
import apps.schedhuler.forms as scd_forms
import logging
from django.db.models.deletion import RestrictedError
import json
from psycopg2.errors import NotNullViolation
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods

logger = logging.getLogger("django")
error_logger = logging.getLogger("error_logger")
debug_logger = logging.getLogger("debug_logger")

# Create your views here.


class Schd_I_TourFormJob(LoginRequiredMixin, View):
    template_path = "schedhuler/schd_i_tourform_job.html"
    form_class = scd_forms.Schd_I_TourJobForm
    subform = scd_forms.SchdChild_I_TourJobForm
    model = Job
    initial = {
        "starttime": time(00, 00, 00),
        "endtime": time(00, 00, 00),
        "expirytime": 0,
        "identifier": Job.Identifier.INTERNALTOUR,
        "priority": Job.Priority.LOW,
        "scantype": Job.Scantype.QR,
        "gracetime": 5,
        "fromdate": datetime.combine(date.today(), time(00, 00, 00)),
        "uptodate": datetime.combine(date.today(), time(23, 00, 00))
        + timedelta(days=2),
    }

    def get(self, request, *args, **kwargs):
        logger.info("create a guard tour requested")
        cxt = {
            "schdtourform": self.form_class(request=request, initial=self.initial),
            "childtour_form": self.subform(),
        }
        return render(request, self.template_path, context=cxt)

    def post(self, request, *args, **kwargs):
        """Handles creation of Pgroup instance."""
        logger.info("Guard Tour form submitted")
        data, create = QueryDict(request.POST["formData"]), True
        if pk := request.POST.get("pk", None):
            obj = utils.get_model_obj(pk, request, {"model": self.model})
            form = self.form_class(
                instance=obj, data=data, initial=self.initial, request=request
            )
            logger.info("retrieved existing guard tour jobname:= '%s'", (obj.jobname))
            create = False
        else:
            form = self.form_class(data=data, initial=self.initial, request=request)
            logger.info(
                "new guard tour submitted following is the form-data:\n%s\n",
                (pformat(form.data)),
            )
        response = None
        try:
            with transaction.atomic(using=get_current_db_name()):
                if form.is_valid():
                    response = self.process_valid_schd_tourform(request, form, create)
                else:
                    response = self.process_invalid_schd_tourform(form)
        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Form validation error in tour form processing")
            logger.warning(f"Tour form validation failed - {correlation_id}: {str(e)}")
            response = rp.JsonResponse({"errors": "Form validation failed"}, status=400)
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Database error in tour form processing")
            logger.error(f"Database error in tour form processing - {correlation_id}: {str(e)}")
            response = rp.JsonResponse({"errors": "Database error occurred"}, status=500)
        except SchedulingException as e:
            correlation_id = ErrorHandler.handle_exception(e, "Scheduling logic error in tour form")
            logger.warning(f"Scheduling logic error - {correlation_id}: {str(e)}")
            response = rp.JsonResponse({"errors": "Scheduling conflict detected"}, status=400)
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(e, "Permission denied in tour form processing")
            logger.warning(f"Permission denied - {correlation_id}: {str(e)}")
            response = rp.JsonResponse({"errors": "Access denied"}, status=403)
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "System error in tour form processing")
            logger.critical(f"System error in tour form processing - {correlation_id}: {str(e)}")
            response = rp.JsonResponse({"errors": "System error occurred"}, status=500)
        return response

    def process_valid_schd_tourform(self, request, form, create):
        resp = None
        logger.info("guard tour form processing/saving [ START ]")
        try:
            with transaction.atomic(using=get_current_db_name()):
                assigned_checkpoints = json.loads(
                    request.POST.get("asssigned_checkpoints")
                )
                job = form.save(commit=False)
                job.parent = None  # Top-level job (no parent)
                job.asset = None   # No specific asset assigned
                job.qset_id = -1   # Keep existing qset logic
                job.save()
                job = putils.save_userinfo(
                    job, request.user, request.session, create=create
                )
                self.save_checpoints_for_tour(assigned_checkpoints, job, request)
                logger.info("guard tour  and its checkpoints saved success...")
        except IntegrityError as e:
            logger.error(f"Database integrity error saving guard tour: {e}", exc_info=True)
            resp = rp.JsonResponse(
                {"error": "Data integrity error - please check your input"}, status=422
            )
            raise e
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid data in guard tour form: {e}", exc_info=True)
            resp = rp.JsonResponse(
                {"error": "Invalid form data provided"}, status=400
            )
            raise e
        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Validation error in guard tour form processing")
            logger.warning(f"Guard tour validation failed - {correlation_id}: {str(e)}")
            resp = rp.JsonResponse({"error": "Guard tour validation failed"}, status=400)
            raise e
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "Database error in guard tour processing")
            logger.error(f"Database error in guard tour processing - {correlation_id}: {str(e)}")
            resp = rp.JsonResponse({"error": "Database error occurred"}, status=500)
            raise e
        except SchedulingException as e:
            correlation_id = ErrorHandler.handle_exception(e, "Scheduling error in guard tour processing")
            logger.warning(f"Scheduling error in guard tour - {correlation_id}: {str(e)}")
            resp = rp.JsonResponse({"error": "Scheduling conflict detected"}, status=400)
            raise e
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(e, "Permission denied in guard tour processing")
            logger.warning(f"Permission denied in guard tour - {correlation_id}: {str(e)}")
            resp = rp.JsonResponse({"error": "Access denied"}, status=403)
            raise e
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "System error in guard tour processing")
            logger.critical(f"System error in guard tour processing - {correlation_id}: {str(e)}")
            resp = rp.JsonResponse({"error": "System error occurred"}, status=500)
            raise e
        else:
            logger.info("guard tour form is processed successfully")
            resp = rp.JsonResponse(
                {
                    "jobname": job.jobname,
                    "url": f"/operations/tours/update/{job.id}/",
                },
                status=200,
            )
        logger.info("guard tour form processing/saving [ END ]")
        return resp

    @staticmethod
    def process_invalid_schd_tourform(form):
        logger.info("processing invalid forms sending errors to the client [ START ]")
        cxt = {"errors": form.errors}
        logger.info("processing invalid forms sending errors to the client [ END ]")
        return rp.JsonResponse(cxt, status=404)

    def save_checpoints_for_tour(self, checkpoints, job, request):
        try:
            logger.info("saving Checkpoints [started]")
            self.insert_checkpoints(checkpoints, job, request)
            logger.info("saving QuestionSet Belonging [Ended]")
        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Validation error while saving checkpoints for tour")
            logger.warning(f"Checkpoint validation failed - {correlation_id}: {str(e)}")
            raise e
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Database error while saving checkpoints for tour")
            logger.error(f"Database error saving checkpoints - {correlation_id}: {str(e)}")
            raise e
        except SchedulingException as e:
            correlation_id = ErrorHandler.handle_exception(e, "Scheduling error while saving checkpoints for tour")
            logger.warning(f"Scheduling error in checkpoints - {correlation_id}: {str(e)}")
            raise e
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(e, "Permission denied while saving checkpoints for tour")
            logger.warning(f"Permission denied saving checkpoints - {correlation_id}: {str(e)}")
            raise e
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "System error while saving checkpoints for tour")
            logger.critical(f"System error saving checkpoints - {correlation_id}: {str(e)}")
            raise e

    def insert_checkpoints(self, checkpoints, job, request):
        logger.info("inserting checkpoints started...")
        logger.info("inserting checkpoints found %s checkpoints", (len(checkpoints)))
        CP = {}
        try:
            for cp in checkpoints:
                CP["expirytime"] = cp[5]
                CP["asset"] = cp[1]
                CP["qset"] = cp[3]
                CP["seqno"] = cp[0]
                checkpoint, created = self.model.objects.update_or_create(
                    parent_id=job.id,
                    asset_id=CP["asset"],
                    qset_id=CP["qset"],
                    defaults=sutils.job_fields(job, cp),
                )
                checkpoint.save()
                status = "CREATED" if created else "UPDATED"
                logger.info(
                    "\nsaving checkpoint:= '%s' for JOB:= '%s' with expirytime:= '%s'  %s\n",
                    cp[2],
                    job.jobname,
                    cp[5],
                    status,
                )
                putils.save_userinfo(
                    checkpoint, request.user, request.session, create=created
                )
        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Validation error while inserting checkpoints")
            logger.warning(f"Checkpoint insertion validation failed - {correlation_id}: {str(e)}")
            raise e
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Database error while inserting checkpoints")
            logger.error(f"Database error inserting checkpoints - {correlation_id}: {str(e)}")
            raise e
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Data processing error while inserting checkpoints")
            logger.warning(f"Data processing error in checkpoint insertion - {correlation_id}: {str(e)}")
            raise e
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(e, "Permission denied while inserting checkpoints")
            logger.warning(f"Permission denied inserting checkpoints - {correlation_id}: {str(e)}")
            raise e
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "System error while inserting checkpoints")
            logger.critical(f"System error inserting checkpoints - {correlation_id}: {str(e)}")
            raise e
        else:
            logger.info("inserting checkpoints finished...")


class Update_I_TourFormJob(Schd_I_TourFormJob, View):
    def get(self, request, *args, **kwargs):
        logger.info("Update Schedhule Tour form view")
        response = None
        try:
            pk = kwargs.get("pk")
            obj = self.model.objects.select_related(
                'jobneed', 'asset', 'asset__location', 'people', 'people__shift', 'people__bt'
            ).get(id=pk)
            logger.info("object retrieved {}".format(obj))
            form = self.form_class(instance=obj, initial=self.initial)
            checkpoints = self.get_checkpoints(obj=obj)
            cxt = {
                "schdtourform": form,
                "childtour_form": self.subform(),
                "edit": True,
                "checkpoints": checkpoints,
            }
            response = render(request, self.template_path, context=cxt)
        except self.model.DoesNotExist:
            messages.error(
                request, "Unable to edit object not found", "alert alert-danger"
            )
            response = redirect("/operations/tours/create/")
        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Validation error in tour update form")
            logger.warning(f"Tour update form validation failed - {correlation_id}: {str(e)}")
            messages.error(request, "Form validation failed", "alert alert-danger")
            response = redirect("/operations/tours/create/")
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(e, "Permission denied in tour update form")
            logger.warning(f"Permission denied in tour update - {correlation_id}: {str(e)}")
            messages.error(request, "Access denied", "alert alert-danger")
            response = redirect("/operations/tours/create/")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "System error in tour update form")
            logger.critical(f"System error in tour update - {correlation_id}: {str(e)}")
            messages.error(request, "System error occurred", "alert alert-danger")
            response = redirect("/operations/tours/create/")
        return response

    def get_checkpoints(self, obj):
        logger.info("getting checkpoints started...")
        checkpoints = None
        try:
            checkpoints = (
                self.model.objects.select_related(
                    "parent",
                    "asset",
                    "qset",
                    "pgroup",
                    "people",
                )
                .filter(parent_id=obj.id)
                .values(
                    "seqno",
                    "asset__assetname",
                    "asset__id",
                    "qset__qset_name",
                    "qset__id",
                    "expirytime",
                    "id",
                )
            )
        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Validation error while retrieving checkpoints")
            logger.warning(f"Checkpoint retrieval validation failed - {correlation_id}: {str(e)}")
            raise e
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "Database error while retrieving checkpoints")
            logger.error(f"Database error retrieving checkpoints - {correlation_id}: {str(e)}")
            raise e
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(e, "Permission denied while retrieving checkpoints")
            logger.warning(f"Permission denied retrieving checkpoints - {correlation_id}: {str(e)}")
            raise e
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "System error while retrieving checkpoints")
            logger.critical(f"System error retrieving checkpoints - {correlation_id}: {str(e)}")
            raise e
        else:
            logger.info("checkpoints retrieved returned success")
        return checkpoints


class Retrive_I_ToursJob(LoginRequiredMixin, View):
    params = {
        "model": Job,
        "template_path": "schedhuler/schd_i_tourlist_job.html",
        "fields": [
            "jobname",
            "people__peoplename",
            "pgroup__groupname",
            "fromdate",
            "uptodate",
            "planduration",
            "gracetime",
            "expirytime",
            "id",
        ],
        "related": ["pgroup", "people"],
    }

    model = Job
    template_path = "schedhuler/schd_i_tourlist_job.html"
    fields = [
        "jobname",
        "people__peoplename",
        "pgroup__groupname",
        "fromdate",
        "uptodate",
        "planduration",
        "gracetime",
        "expirytime",
        "id",
    ]
    related = ["pgroup", "people"]

    def get(self, request, *args, **kwargs):
        """returns the paginated results from db"""
        response = None
        try:
            logger.info("Retrieve Schedhuled Tours view")
            objects = (
                self.model.objects.select_related(*self.related)
                .filter(
                    ~Q(jobname="NONE"),
                    parent__jobname="NONE",
                    identifier=JobConstants.Identifier.INTERNALTOUR
                )
                .values(*self.fields)
                .order_by("-cdtz")
            )
            logger.info(f"Schedhuled Tours objects retrieved from db")

            cxt = self.paginate_results(request, objects)
            logger.info("Results paginated" if objects else "")
            response = render(request, self.template_path, context=cxt)
        except EmptyResultSet:
            logger.warning("empty objects retrieved", exc_info=True)
            response = render(request, self.template_path, context=cxt)
            messages.error(request, "List view not found", "alert alert-danger")
        except (ValidationError, EnhancedValidationException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "Validation error in tour list retrieval")
            logger.warning(f"Tour list validation failed - {correlation_id}: {str(e)}")
            messages.error(request, "Form validation failed", "alert alert-danger")
            response = redirect("/dashboard")
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(e, "Permission denied in tour list retrieval")
            logger.warning(f"Permission denied in tour list - {correlation_id}: {str(e)}")
            messages.error(request, "Access denied", "alert alert-danger")
            response = redirect("/dashboard")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "System error in tour list retrieval")
            logger.critical(f"System error in tour list - {correlation_id}: {str(e)}")
            messages.error(request, "System error occurred", "alert alert-danger")
            response = redirect("/dashboard")
        return response

    @staticmethod
    def paginate_results(request, objects):
        """paginate the results"""
        logger.info("Pagination Start" if objects else "")
        from .filters import SchdTourFilter

        if request.GET:
            objects = SchdTourFilter(request.GET, queryset=objects).qs
        filterform = SchdTourFilter().form
        page = request.GET.get("page", 1)
        paginator = Paginator(objects, 25)
        try:
            schdtour_list = paginator.page(page)
        except PageNotAnInteger:
            schdtour_list = paginator.page(1)
        except EmptyPage:
            schdtour_list = paginator.page(paginator.num_pages)
        return {"schdtour_list": schdtour_list, "schdtour_filter": filterform}


def deleteChekpointFromTour(request):
    if request.method != "POST":
        return rp.JsonResponse(
            {"errors": "POST method required for delete operations"}, status=405
        )

    # CSRF protection is automatically handled by Django middleware
    datasource = request.POST.get("datasource")
    checkpointid = request.POST.get("checkpointid")
    checklistid = request.POST.get("checklistid")
    job = request.POST.get("job")
    statuscode, msg = 404, ""
    try:
        if datasource == "job":
            sutils.delete_from_job(job, checkpointid, checklistid)
            statuscode, msg = 200, "Success"
        elif datasource == "jobneed":
            sutils.delete_from_jobneed(job, checkpointid, checklistid)
            statuscode, msg = 200, "Success"
    except RestrictedError:
        msg = "Unable to delete, due to its dependencies on other data!"
        error_logger.error("something went wrong", exc_info=True)
    except (ValidationError, EnhancedValidationException) as e:
        correlation_id = ErrorHandler.handle_exception(e, "Validation error in checkpoint deletion")
        logger.warning(f"Checkpoint deletion validation failed - {correlation_id}: {str(e)}")
        msg = "Validation failed"
    except PermissionDenied as e:
        correlation_id = ErrorHandler.handle_exception(e, "Permission denied in checkpoint deletion")
        logger.warning(f"Permission denied in checkpoint deletion - {correlation_id}: {str(e)}")
        msg = "Access denied"
    except SystemException as e:
        correlation_id = ErrorHandler.handle_exception(e, "System error in checkpoint deletion")
        logger.critical(f"System error in checkpoint deletion - {correlation_id}: {str(e)}")
        msg = "System error occurred"
    return rp.JsonResponse({"errors": msg}, status=statuscode)


class Retrive_I_ToursJobneed(LoginRequiredMixin, View):
    model = Jobneed
    template_path = "schedhuler/i_tourlist_jobneed.html"
    fields = [
        "jobdesc",
        "people__peoplename",
        "pgroup__groupname",
        "id",
        "plandatetime",
        "expirydatetime",
        "jobstatus",
        "gracetime",
        "performedby__peoplename",
    ]
    related = [
        "pgroup",
        "ticketcategory",
        "asset",
        "client",
        "frequency",
        "job",
        "qset",
        "people",
        "parent",
        "bu",
    ]

    def get(self, request, *args, **kwargs):
        """returns jobneed (internal-tours) from db"""
        response, session = None, request.session

        try:
            logger.info("Retrieve internal tours(jobneed) view")
            dt = datetime.now(tz=timezone.utc) - timedelta(days=10)
            objects = (
                self.model.objects.select_related(*self.related)
                .filter(
                    Q(bu_id=session["bu_id"])
                    & Q(parent__jobdesc="NONE")
                    & ~Q(jobdesc="NONE")
                    & Q(plandatetime__gte=dt)
                )
                .values(*self.fields)
                .order_by("-plandatetime")
            )
            logger.info("Internal Tours objects retrieved from db")
            cxt = self.paginate_results(request, objects)
            logger.info("Results paginated" if objects else "")
            response = render(request, self.template_path, context=cxt)

        except EmptyResultSet:
            logger.warning("empty objects retrieved", exc_info=True)
            response = render(request, self.template_path, context=cxt)
            messages.error(request, "List view not found", "alert alert-danger")
        except (ValidationError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "internal_tours_list_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Internal tours list error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "Unable to load tour data", "alert alert-danger")
            response = redirect("/dashboard")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "internal_tours_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"System error in internal tours: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "System error occurred", "alert alert-danger")
            response = redirect("/dashboard")
        return response

    @staticmethod
    def paginate_results(request, objects):
        """paginate the results"""
        logger.info("Pagination Start" if objects else "")
        from .filters import InternalTourFilter

        if request.GET:
            objects = InternalTourFilter(request.GET, queryset=objects).qs
        filterform = InternalTourFilter().form
        page = request.GET.get("page", 1)
        paginator = Paginator(objects, 25)

        try:
            tour_list = paginator.page(page)
        except PageNotAnInteger:
            tour_list = paginator.page(1)
        except EmptyPage:
            tour_list = paginator.page(paginator.num_pages)
        return {"tour_list": tour_list, "tour_filter": filterform}


class Get_I_TourJobneed(LoginRequiredMixin, View):
    model = Jobneed
    template_path = "schedhuler/i_tourform_jobneed.html"
    form_class = scd_forms.I_TourFormJobneed
    subform = scd_forms.Child_I_TourFormJobneed
    initial = {
        "identifier": Jobneed.Identifier.INTERNALTOUR,
        "frequency": Jobneed.Frequency.NONE,
    }

    def get(self, request, *args, **kwargs):
        logger.info("retrieving internal tour datasource[jobneed]")
        parent_jobneed, response = kwargs.get("pk"), None

        try:
            obj = self.model.objects.get(id=parent_jobneed)
            form = self.form_class(instance=obj, initial=self.initial)
            logger.info("object retrieved %s", (obj.jobdesc))
            checkpoints = self.get_checkpoints(obj=obj)
            cxt = {
                "internaltourform": form,
                "child_internaltour": self.subform(prefix="child"),
                "edit": True,
                "checkpoints": checkpoints,
            }
            response = render(request, self.template_path, context=cxt)

        except self.model.DoesNotExist:
            error_logger.error("object does not exist", exc_info=True)
            response = redirect("/operations/tours/internal/")

        except (ValidationError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "tour_edit_data_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Tour edit data error: {str(e)}", extra={"correlation_id": correlation_id})
            response = redirect("/operations/tours/internal/")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "tour_edit_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"Tour edit system error: {str(e)}", extra={"correlation_id": correlation_id})
            response = redirect("/operations/tours/internal/")
        return response

    @staticmethod
    def post(request, *args, **kwargs):
        logger.info("saving internal tour datasource[jobneed]")

    def get_checkpoints(self, obj):
        logger.info("getting checkpoints for the internal tour [start]")
        checkpoints = None

        try:
            checkpoints = (
                self.model.objects.select_related(
                    "parent",
                    "asset",
                    "qset",
                    "pgroup",
                    "people",
                    "job",
                    "client",
                    "bu",
                    "ticketcategory",
                )
                .filter(parent_id=obj.id)
                .values(
                    "asset__assetname",
                    "asset__id",
                    "qset__id",
                    "qset__qset_name",
                    "plandatetime",
                    "expirydatetime",
                    "gracetime",
                    "seqno",
                    "jobstatus",
                    "id",
                )
                .order_by("seqno")
            )

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "checkpoint_retrieval_error", {"object_id": obj.id if obj else None})
            logger.error(f"Checkpoint retrieval database error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "checkpoint_validation_error", {"object_id": obj.id if obj else None})
            logger.error(f"Checkpoint validation error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "checkpoint_system_error", {"object_id": obj.id if obj else None})
            logger.critical(f"Checkpoint system error: {str(e)}", extra={"correlation_id": correlation_id})
            raise

        else:
            logger.info("checkpoints retrieved returned success")
        return checkpoints


def add_cp_internal_tour(request):  # jobneed
    resp = None
    if request.method == "POST":
        formData = request.POST.get("formData")
        parentid = request.POST.get("parentid")
        try:
            parent = Jobneed.objects.select_related(
                'job', 'performedby', 'job__asset', 'job__asset__location'
            ).get(id=parentid)
            data = {
                "jobdesc": parent.jobdesc,
                "receivedonserver": parent.receivedonserver,
                "starttime": parent.starttime,
                "endtime": parent.endtime,
                "gpslocation": parent.gpslocation,
                "remarks": parent.remarks,
                "frequency": parent.frequency,
                "job": parent.job,
                "jobstatus": parent.jobstatus,
                "jobtype": parent.jobtype,
                "performedby": parent.performedby,
                "priority": "",
            }
            form = scd_forms.ChildInternalTourForm(data=formData)

        except Jobneed.DoesNotExist:
            msg = "Parent not found failed to add checkpoint!"
            resp = rp.JsonResponse({"errors": msg}, status=404)
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "checkpoint_form_validation_error", {"parent_id": parentid})
            logger.error(f"Checkpoint form validation error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse({"errors": "Invalid form data"}, status=400)
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "checkpoint_add_database_error", {"parent_id": parentid})
            logger.error(f"Checkpoint database error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse({"errors": "Database error occurred"}, status=500)
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "checkpoint_add_system_error", {"parent_id": parentid})
            logger.critical(f"Checkpoint system error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse({"errors": "System error occurred"}, status=500)


class Schd_E_TourFormJob(LoginRequiredMixin, View):
    params = {
        "model": Jobneed,
        "form_class": scd_forms.Schd_E_TourJobForm,
        "subform": scd_forms.EditAssignedSiteForm,
        "template_path": "schedhuler/schd_e_tourform_job.html",
        "initial": {
            "seqno": -1,
            "scantype": Job.Scantype.QR,
            "frequency": Job.Frequency.NONE,
            "identifier": Job.Identifier.EXTERNALTOUR,
            "starttime": time(00, 00, 00),
            "endtime": time(00, 00, 00),
            "priority": Job.Priority.HIGH,
            "expirytime": 0,
        },
    }

    def get(self, request, *args, **kwargs):
        logger.info("create a guard tour requested")
        cxt = {
            "schdexternaltourform": self.form_class(
                request=request, initial=self.initial
            ),
            "editsiteform": self.subform(),
        }
        return render(request, self.template_path, context=cxt)

    def post(self, request, *args, **kwargs):
        """Handles creation of Pgroup instance."""
        logger.info("External Tour form submitted")
        formData, create = QueryDict(request.POST.get("formData")), True
        if pk := request.POST.get("pk", None):
            obj = utils.get_model_obj(pk, request, {"model": self.model})
            form = self.form_class(instance=obj, data=formData, initial=self.initial)
            logger.info("retrieved existing guard tour jobname:= '%s'", (obj.jobname))
            create = False
        else:
            form = self.form_class(data=formData, initial=self.initial)
            logger.info(
                "new guard tour submitted following is the form-data:\n%s\n",
                (pformat(form.data)),
            )
        response = None
        try:
            with transaction.atomic(using=get_current_db_name()):
                if form.is_valid():
                    response = self.process_valid_schd_tourform(request, form, create)
                else:
                    response = self.process_invalid_schd_tourform(form)
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "tour_form_validation_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"Tour form validation error: {str(e)}", extra={"correlation_id": correlation_id})
            response = rp.JsonResponse(
                {"errors": "Form validation failed"}, status=400
            )
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "tour_form_database_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"Tour form database error: {str(e)}", extra={"correlation_id": correlation_id})
            response = rp.JsonResponse(
                {"errors": "Database error occurred"}, status=500
            )
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "tour_form_system_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.critical(f"Tour form system error: {str(e)}", extra={"correlation_id": correlation_id})
            response = rp.JsonResponse(
                {"errors": "System error occurred"}, status=500
            )
        return response

    @staticmethod
    def process_invalid_schd_tourform(form):
        logger.info("processing invalid forms sending errors to the client [ START ]")
        cxt = {"errors": form.errors}
        logger.info("processing invalid forms sending errors to the client [ END ]")
        return rp.JsonResponse(cxt, status=404)

    @staticmethod
    def process_valid_schd_tourform(request, form, create):
        resp = None
        logger.info("external tour form processing/saving [ START ]")
        try:
            job = form.save(commit=False)
            job.parent = get_none_job()  # NONE parent placeholder
            job.asset = get_none_asset()  # NONE asset placeholder
            job.save()
            job = putils.save_userinfo(job, request.user, request.session)
            logger.info("external tour  and its checkpoints saved success...")
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_save_validation_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"External tour save validation error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse(
                {"error": "Tour validation failed"}, status=400
            )
            raise
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_save_database_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"External tour save database error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse(
                {"error": "Database error during tour save"}, status=500
            )
            raise
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_save_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"External tour save system error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse(
                {"error": "System error occurred"}, status=500
            )
            raise
        else:
            logger.info("external tour form is processed successfully")
            resp = rp.JsonResponse(
                {
                    "jobname": job.jobname,
                    "url": f"/operations/tours/external/update/{job.id}/",
                },
                status=200,
            )
        logger.info("external tour form processing/saving [ END ]")
        return resp


class Update_E_TourFormJob(Schd_E_TourFormJob, LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        logger.info("Update External Schedhule Tour form view")
        response = None
        try:
            pk = kwargs.get("pk")
            obj = self.model.objects.get(id=pk)
            logger.info("object retrieved {}".format(obj))
            form = self.form_class(instance=obj, initial=self.initial)
            checkpoints = self.get_checkpoints(obj=obj)
            cxt = {
                "schdexternaltourform": form,
                "edit": True,
                "editsiteform": self.subform(),
                "checkpoints": checkpoints,
                "qsetname": obj.qset.qsetname,
                "qset": obj.qset.id,
            }
            response = render(request, self.template_path, context=cxt)
        except self.model.DoesNotExist:
            messages.error(
                request, "Unable to edit object not found", "alert alert-danger"
            )
            response = redirect("/operations/tours/create/")
        except (ValidationError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_edit_error", {"tour_id": pk})
            logger.error(f"External tour edit error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "Unable to load tour data", "alert alert-danger")
            response = redirect("/operations/tours/create/")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_edit_system_error", {"tour_id": pk})
            logger.critical(f"External tour edit system error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "System error occurred", "alert alert-danger")
            response = redirect("/operations/tours/create/")
        return response

    @staticmethod
    def get_checkpoints(obj):
        logger.info("getting checkpoints started...")
        checkpoints = None
        try:
            checkpoints = (
                pm.Pgbelonging.objects.select_related("assignsites", "identifier")
                .filter(pgroup_id=obj.sgroup_id)
                .values(
                    "assignsites__buname",
                    "assignsites_id",
                    "assignsites__bucode",
                    "assignsites__gpslocation",
                )
            )
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_checkpoints_database_error", {"sgroup_id": obj.sgroup_id if obj else None})
            logger.error(f"External checkpoints database error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_checkpoints_validation_error", {"sgroup_id": obj.sgroup_id if obj else None})
            logger.error(f"External checkpoints validation error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_checkpoints_system_error", {"sgroup_id": obj.sgroup_id if obj else None})
            logger.critical(f"External checkpoints system error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        else:
            if checkpoints:
                logger.info(
                    "total %s checkpoints retrieved returned success",
                    (len(checkpoints)),
                )
            else:
                logger.info("checkpoints not found")
        return checkpoints


class Retrive_E_ToursJob(LoginRequiredMixin, View):
    model = Job
    template_path = "schedhuler/schd_e_tourlist_job.html"
    fields = [
        "jobname",
        "people__peoplename",
        "pgroup__groupname",
        "fromdate",
        "uptodate",
        "planduration",
        "gracetime",
        "expirytime",
        "id",
        "bu__buname",
    ]
    related = ["pgroup", "people"]

    def get(self, request, *args, **kwargs):
        """returns the paginated results from db"""
        response = None
        try:
            logger.info("Retrieve Schedhuled External Tours view")
            objects = (
                self.model.objects.select_related(*self.related)
                .filter(
                    ~Q(jobname="NONE"),
                    parent__jobname="NONE",
                    identifier=JobConstants.Identifier.EXTERNALTOUR,
                )
                .values(*self.fields)
                .order_by("-cdtz")
            )
            logger.info("Schedhuled External Tours objects retrieved from db")
            cxt = self.paginate_results(request, objects)
            logger.info("Results paginated" if objects else "")
            response = render(request, self.template_path, context=cxt)
        except EmptyResultSet:
            logger.warning("empty objects retrieved", exc_info=True)
            response = render(request, self.template_path, context=cxt)
            messages.error(request, "List view not found", "alert alert-danger")
        except (ValidationError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tours_list_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"External tours list error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "Unable to load tour data", "alert alert-danger")
            response = redirect("/dashboard")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tours_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"External tours system error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "System error occurred", "alert alert-danger")
            response = redirect("/dashboard")
        return response

    @staticmethod
    def paginate_results(request, objects):
        """paginate the results"""
        logger.info("Pagination Start" if objects else "")
        from .filters import SchdExtTourFilter

        if request.GET:
            objects = SchdExtTourFilter(request.GET, queryset=objects).qs
        filterform = SchdExtTourFilter().form
        page = request.GET.get("page", 1)
        paginator = Paginator(objects, 25)
        try:
            schdtour_list = paginator.page(page)
        except PageNotAnInteger:
            schdtour_list = paginator.page(1)
        except EmptyPage:
            schdtour_list = paginator.page(paginator.num_pages)
        return {"ext_schdtour_list": schdtour_list, "ext_schdtour_filter": filterform}


@require_http_methods(["POST"])
def run_internal_tour_scheduler(request):
    """Schedules an internal tour based on the POST request."""
    job_id = request.POST.get("job_id")
    action = request.POST.get("action")
    checkpoints = json.loads(request.POST.get("checkpoints", "[]"))

    # Start structured logging
    logger.info(
        "run_guardtour_scheduler initiated", extra={"phase": "START", "job_id": job_id}
    )

    # Validate inputs
    if not job_id:
        error_logger.error(
            "Job ID not found in request", extra={"request": request.POST}
        )
        return rp.JsonResponse({"errors": "Job ID not found"}, status=404)

    # Fetch the Job
    job = _get_job(job_id)

    if job is None:
        error_logger.error("Job not found in database", extra={"job_id": job_id})
        return rp.JsonResponse({"errors": "Job not found"}, status=404)

    # Handle Randomized External Tour
    if (
        job["other_info"]["is_randomized"] in [True, "true"]
        and action == "saveCheckpoints"
    ):
        logger.info("Tour type random is going to schedule", extra={"job": job})
        _handle_random_external_tour(job, checkpoints, request)

    if job["other_info"]["isdynamic"]:
        resp = sutils.create_dynamic_job([job["id"]])
        resp = rp.JsonResponse(resp, status=200, safe=False)
    else:
        # Create a new job
        response, _ = sutils.create_job([job["id"]])
        resp = rp.JsonResponse(response, status=200, safe=False)

    # End logging
    logger.info(
        "run_guardtour_scheduler ended",
        extra={"phase": "END", "job_id": job_id, "response": resp},
    )

    return resp


def _get_job(job_id):
    """Fetch a job from the database by its ID"""
    jobs = (
        Job.objects.filter(id=job_id)
        .select_related("asset", "pgroup", "sgroup", "cuser", "muser", "qset", "people")
        .values(*utils.JobFields.fields)
    )
    return jobs[0] if jobs else None


def _handle_random_external_tour(job, checkpoints, request):
    """Handle a randomized external tour"""
    Job.objects.filter(parent_id=job["id"]).delete()
    logger.info("saving checkpoints started...", extra={"job": job})

    for checkpoint in checkpoints:
        obj = Job.objects.create(**sutils.job_fields(job, checkpoint, external=True))
        putils.save_userinfo(obj, request.user, request.session, bu=checkpoint["buid"])
        logger.info(f"checkpoint saved", extra={"checkpoint": obj.jobname})

    logger.info("saving checkpoints ended...", extra={"job": job})


def get_cron_datetime(request):
    if request.method != "GET":
        return Http404

    logger.info("get_cron_datetime [start]")
    cron = request.GET.get("cron")
    logger.info(f"get_cron_datetime cron:{cron}")
    cronDateTime = itr = None
    startdtz = datetime.now()
    enddtz = datetime.now() + timedelta(days=1)
    DT, res = [], None
    try:
        from croniter import croniter

        itr = croniter(cron, startdtz)
        while True:
            cronDateTime = itr.get_next(datetime)
            if cronDateTime < enddtz:
                DT.append(cronDateTime)
            else:
                break
        res = rp.JsonResponse({"rows": DT}, status=200)
    except ImportError as e:
        correlation_id = ErrorHandler.handle_exception(e, "croniter_import_error", {"cron": cron})
        logger.error(f"Croniter import error: {str(e)}", extra={"correlation_id": correlation_id})
        res = rp.JsonResponse({"errors": "Cron library not available"}, status=500)
    except ValueError as e:
        correlation_id = ErrorHandler.handle_exception(e, "cron_validation_error", {"cron": cron})
        logger.error(f"Invalid cron expression: {str(e)}", extra={"correlation_id": correlation_id})
        res = rp.JsonResponse({"errors": "Invalid cron expression"}, status=400)
    except SystemException as e:
        correlation_id = ErrorHandler.handle_exception(e, "cron_system_error", {"cron": cron})
        logger.critical(f"Cron system error: {str(e)}", extra={"correlation_id": correlation_id})
        res = rp.JsonResponse({"errors": "System error occurred"}, status=500)
    return res


def save_assigned_sites_for_externaltour(request):
    if request.method == "POST":
        logger.info("save_assigned_sites_for_externaltour [start+]")
        formData = QueryDict(request.POST.get("formData"))
        parentJobId = request.POST.get("pk")
        with transaction.atomic(using=get_current_db_name()):
            save_sites_in_job(request, parentJobId)


def save_sites_in_job(request, parentid):
    try:
        checkpoints = json.loads(request.POST.get("assignedSites"))
        job = Job.objects.select_related(
            'jobneed', 'asset', 'asset__location', 'people', 'people__shift'
        ).get(id=parentid)
        for cp in checkpoints:
            Job.objects.update_or_create(
                parent_id=job.id,
                asset_id=cp["asset"],
                qset_id=cp["qset"],
                breaktime=cp["breaktime"],
                defaults=sutils.job_fields(job, cp, external=True),
            )

    except Job.DoesNotExist:
        msg = "Parent job not found failed to save assigned sites!"
        error_logger.error(f"{msg}", exc_info=True)
        raise
    except (json.JSONDecodeError, ValueError) as e:
        correlation_id = ErrorHandler.handle_exception(e, "site_data_parsing_error", {"parent_id": parentid})
        logger.error(f"Site data parsing error: {str(e)}", extra={"correlation_id": correlation_id})
        raise
    except (IntegrityError, DatabaseException) as e:
        correlation_id = ErrorHandler.handle_exception(e, "site_save_database_error", {"parent_id": parentid})
        logger.error(f"Site save database error: {str(e)}", extra={"correlation_id": correlation_id})
        raise
    except SystemException as e:
        correlation_id = ErrorHandler.handle_exception(e, "site_save_system_error", {"parent_id": parentid})
        logger.critical(f"Site save system error: {str(e)}", extra={"correlation_id": correlation_id})
        raise


class SchdTaskFormJob(LoginRequiredMixin, View):
    template_path = "schedhuler/schd_taskform_job.html"
    form_class = scd_forms.SchdTaskFormJob
    model = Job
    initial = {
        "starttime": time(00, 00, 00),
        "endtime": time(00, 00, 00),
        "fromdate": datetime.combine(date.today(), time(00, 00, 00)),
        "uptodate": datetime.combine(date.today(), time(23, 00, 00))
        + timedelta(days=2),
        "identifier": Job.Identifier.TASK,
        "frequency": Job.Frequency.NONE,
        "scantype": Job.Scantype.QR,
        "priority": Job.Priority.LOW,
        "planduration": 5,
        "gracetime": 5,
        "expirytime": 5,
    }

    def get(self, request, *args, **kwargs):
        logger.info("create task to schedule is requested")
        cxt = {"schdtaskform": self.form_class(initial=self.initial)}
        return render(request, self.template_path, context=cxt)

    def post(self, request, *args, **kwargs):
        logger.info("Task form submitted")
        data, create = QueryDict(request.POST["formData"]), True
        utils.display_post_data(data)
        if pk := request.POST.get("pk", None):
            obj = utils.get_model_obj(pk, request, {"model": self.model})
            form = self.form_class(instance=obj, data=data, initial=self.initial)
            logger.info("retrieved existing task whose jobname:= '%s'", (obj.jobname))
        else:
            form = self.form_class(data=data, initial=self.initial)
            logger.info(
                "new task submitted following is the form-data:\n%s\n",
                (pformat(form.data)),
            )
        response = None
        try:
            with transaction.atomic(using=get_current_db_name()):
                if form.is_valid():
                    response = self.process_valid_schd_taskform(request, form)
                else:
                    response = self.process_invalid_schd_taskform(form)
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_form_validation_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"Task form validation error: {str(e)}", extra={"correlation_id": correlation_id})
            response = rp.JsonResponse(
                {"errors": "Form validation failed"}, status=400
            )
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_form_database_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"Task form database error: {str(e)}", extra={"correlation_id": correlation_id})
            response = rp.JsonResponse(
                {"errors": "Database error occurred"}, status=500
            )
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_form_system_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.critical(f"Task form system error: {str(e)}", extra={"correlation_id": correlation_id})
            response = rp.JsonResponse(
                {"errors": "System error occurred"}, status=500
            )
        return response

    @staticmethod
    def process_valid_schd_taskform(request, form):
        resp = None
        logger.info("task form processing/saving [ START ]")
        try:
            job = form.save(commit=False)
            job.parent = get_none_job()  # NONE parent placeholder
            job.save()
            job = putils.save_userinfo(job, request.user, request.session)
            logger.info("task form saved success...")
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_save_validation_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Task save validation error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse(
                {"error": "Task validation failed"}, status=400
            )
            raise
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_save_database_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Task save database error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse(
                {"error": "Database error during task save"}, status=500
            )
            raise
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_save_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"Task save system error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse(
                {"error": "System error occurred"}, status=500
            )
            raise
        else:
            logger.info("task form is processed successfully")
            resp = rp.JsonResponse(
                {
                    "jobname": job.jobname,
                    "url": f"/operations/tasks/update/{job.id}/",
                },
                status=200,
            )
        logger.info("task form processing/saving [ END ]")
        return resp

    @staticmethod
    def process_invalid_schd_taskform(form):
        logger.info(
            "processing invalidt task form sending errors to the client [ START ]"
        )
        cxt = {"errors": form.errors}
        logger.error(f"Form validation errors: {form.errors}")
        logger.info(
            "processing invalidt task form sending errors to the client [ END ]"
        )
        return rp.JsonResponse(cxt, status=404)


class RetriveSchdTasksJob(LoginRequiredMixin, View):
    model = Job
    template_path = "schedhuler/schd_tasklist_job.html"
    fields = [
        "jobname",
        "people__peoplename",
        "pgroup__groupname",
        "fromdate",
        "uptodate",
        "qset__qsetname",
        "asset__assetname",
        "planduration",
        "gracetime",
        "expirytime",
        "id",
    ]
    related = ["pgroup", "people", "asset"]

    def get(self, request, *args, **kwargs):
        """returns the paginated results from db"""
        R, resp = request.GET, None
        try:
            # first load the template
            if R.get("template"):
                return render(request, self.template_path)

            # then load the table with objects for table_view
            if R.get("action") == "list":
                logger.info("Retrieve Tasks view")
                objects = (
                    self.model.objects.select_related(*self.related)
                    .filter(
                        ~Q(jobname="NONE"), parent__jobname="NONE", identifier=JobConstants.Identifier.TASK
                    )
                    .values(*self.fields)
                    .order_by("-cdtz")
                    .iterator()
                )
                logger.info("Tasks objects retrieved from db")
                response = rp.JsonResponse(data={"data": list(objects)})
        except EmptyResultSet:
            logger.warning("empty objects retrieved", exc_info=True)
            response = render(request, self.template_path)
            messages.error(request, "List view not found", "alert alert-danger")
        except (ValidationError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "tasks_list_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Tasks list error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "Unable to load task data", "alert alert-danger")
            response = redirect("/dashboard")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "tasks_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"Tasks system error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "System error occurred", "alert alert-danger")
            response = redirect("/dashboard")
        return response

    @staticmethod
    def paginate_results(request, objects):
        """paginate the results"""
        logger.info("Pagination Start" if objects else "")
        from .filters import SchdTaskFilter

        if request.GET:
            objects = SchdTaskFilter(request.GET, queryset=objects).qs
        filterform = SchdTaskFilter().form
        page = request.GET.get("page", 1)
        paginator = Paginator(objects, 25)
        try:
            schdtour_list = paginator.page(page)
        except PageNotAnInteger:
            schdtour_list = paginator.page(1)
        except EmptyPage:
            schdtour_list = paginator.page(paginator.num_pages)
        return {"schd_task_list": schdtour_list, "schd_task_filter": filterform}


class UpdateSchdTaskJob(SchdTaskFormJob):
    def get(self, request, *args, **kwargs):
        logger.info("Update task form view")
        try:
            pk = kwargs.get("pk")
            obj = self.model.objects.get(id=pk)
            logger.info(f"object retrieved {obj}")
            form = self.form_class(instance=obj)
            cxt = {"schdtaskform": form, "edit": True}

            response = render(request, self.template_path, context=cxt)
        except self.model.DoesNotExist:
            messages.error(
                request, "Unable to edit object not found", "alert alert-danger"
            )
            response = redirect("/operations/tours/create/")
        except (ValidationError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_edit_error", {"task_id": pk})
            logger.error(f"Task edit error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "Unable to load task data", "alert alert-danger")
            response = redirect("/operations/tasks/create/")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_edit_system_error", {"task_id": pk})
            logger.critical(f"Task edit system error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "System error occurred", "alert alert-danger")
            response = redirect("/operations/tasks/create/")
        return response


class RetrieveTasksJobneed(LoginRequiredMixin, View):
    model = Jobneed
    template_path = "schedhuler/tasklist_jobneed.html"

    fields = [
        "jobdesc",
        "people__peoplename",
        "pgroup__groupname",
        "id",
        "plandatetime",
        "expirydatetime",
        "jobstatus",
        "gracetime",
        "performedby__peoplename",
        "asset__assetname",
        "qset__qsetname",
    ]
    related = [
        "pgroup",
        "ticketcategory",
        "asset",
        "client",
        "frequency",
        "job",
        "qset",
        "people",
        "parent",
        "bu",
    ]

    def get(self, request, *args, **kwargs):
        """returns jobneed (tasks) from db"""
        response, session = None, request.session

        try:
            logger.info("Retrieve tasks(jobneed) view")
            dt = datetime.now(tz=timezone.utc) - timedelta(days=10)
            objects = (
                self.model.objects.select_related(*self.related)
                .filter(
                    Q(bu_id=session["bu_id"]),
                    ~Q(parent__jobdesc="NONE"),
                    ~Q(jobdesc="NONE"),
                    Q(plandatetime__gte=dt),
                    Q(identifier=Jobneed.Identifier.TASK),
                )
                .values(*self.fields)
                .order_by("-plandatetime")
            )
            logger.info("tasks objects retrieved from db")
            cxt = self.paginate_results(request, objects)
            logger.info("Results paginated" if objects else "")
            response = render(request, self.template_path, context=cxt)

        except EmptyResultSet:
            logger.warning("no objects found", exc_info=True)
            response = render(request, self.template_path, context=cxt)
            messages.error(request, "List view not found", "alert alert-danger")
        except (ValidationError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "retrieve_tasks_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Retrieve tasks error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "Unable to load task data", "alert alert-danger")
            response = redirect("/dashboard")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "retrieve_tasks_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"Retrieve tasks system error: {str(e)}", extra={"correlation_id": correlation_id})
            messages.error(request, "System error occurred", "alert alert-danger")
            response = redirect("/dashboard")
        return response

    @staticmethod
    def paginate_results(request, objects):
        """paginate the results"""
        logger.info("Pagination Start" if objects else "")
        from .filters import TaskListJobneedFilter

        if request.GET:
            objects = TaskListJobneedFilter(request.GET, queryset=objects).qs
        filterform = TaskListJobneedFilter().form
        page = request.GET.get("page", 1)
        paginator = Paginator(objects, 25)

        try:
            tour_list = paginator.page(page)
        except PageNotAnInteger:
            tour_list = paginator.page(1)
        except EmptyPage:
            tour_list = paginator.page(paginator.num_pages)
        return {"task_list": tour_list, "task_filter": filterform}


class GetTaskFormJobneed(LoginRequiredMixin, View):
    model = Jobneed
    template_path = "schedhuler/taskform_jobneed.html"
    form_class = scd_forms.TaskFormJobneed
    initial = {
        "identifier": Jobneed.Identifier.TASK,
        "frequency": Jobneed.Frequency.NONE,
    }

    def get(self, request, *args, **kwargs):
        logger.info("retrieving task datasource[jobneed]")
        parent_jobneed, response = kwargs.get("pk"), None

        try:
            obj = self.model.objects.get(id=parent_jobneed)
            form = self.form_class(instance=obj)
            logger.info(f"object retrieved {obj.jobdesc}")
            cxt = {"taskformjobneed": form, "edit": True}
            response = render(request, self.template_path, context=cxt)

        except self.model.DoesNotExist:
            error_logger.error("object does not exist", exc_info=True)
            response = redirect("/operations/tasks/")

        except (ValidationError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_jobneed_edit_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Task jobneed edit error: {str(e)}", extra={"correlation_id": correlation_id})
            response = redirect("/operations/tasks/")
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "task_jobneed_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"Task jobneed system error: {str(e)}", extra={"correlation_id": correlation_id})
            response = redirect("/operations/tasks/")
        return response

    @staticmethod
    def post(request, *args, **kwargs):
        logger.info("saving tasks datasource[jobneed]")


class JobneedTours(LoginRequiredMixin, View):
    params = {
        "model": Jobneed,
        "template_path": "schedhuler/i_tourlist_jobneed.html",
        "template_modern": "schedhuler/tourlist_jobneed_modern.html",
        "template_form": "schedhuler/i_tourform_jobneed.html",
        "fields": [
            "jobdesc",
            "people__peoplename",
            "pgroup__groupname",
            "id",
            "ctzoffset",
            "jobtype",
            "plandatetime",
            "expirydatetime",
            "jobstatus",
            "gracetime",
            "performedby__peoplename",
            "assignedto",
            "other_info__isdynamic",
            "bu__buname",
            "bu__bucode",
            "client__buname",
            "client_name",
            "site_name",
            "no_of_checkpoints",
            "completed",
            "missed",
            "starttime",
            "endtime",
        ],
        "related": [
            "pgroup",
            "ticketcategory",
            "asset",
            "client",
            "job",
            "qset",
            "people",
            "parent",
            "bu",
        ],
        "form_class": scd_forms.I_TourFormJobneed,
        "subform": scd_forms.Child_I_TourFormJobneed,
        "initial": {
            "identifier": Jobneed.Identifier.INTERNALTOUR,
            "frequency": Jobneed.Frequency.NONE,
        },
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        # first load the template
        if R.get("template"):
            # Check for view type preference
            if R.get("old", "false").lower() == "true":
                return render(request, P["template_path"])  # Classic table view
            elif R.get("list", "false").lower() == "true":
                return render(request, "schedhuler/tourlist_jobneed_modern_list.html", {"tour_type": "Internal Tour"})  # Modern list view
            return render(request, P.get("template_modern", P["template_path"]), {"tour_type": "Internal Tour"})  # Modern card view (default)

        # then load the table with objects for table_view
        if R.get("action", None) == "list" or R.get("search_term"):
            start = int(R.get("start", 0))
            length = int(R.get("length", 10))
            search = R.get("search[value]", "").strip()
            order_col = request.GET.get("order[0][column]")
            order_dir = request.GET.get("order[0][dir]")
            column_name = request.GET.get(f"columns[{order_col}][data]")

            objs = P["model"].objects.get_internaltourlist_jobneed(
                request, P["related"], P["fields"]
            )

            if search:
                objs = objs.filter(
                    Q(bu__buname=search)
                    | Q(bu__bucode=search)
                    | Q(jobdesc__contains=search)
                )

            if column_name:
                order_prefix = "" if order_dir == "asc" else "-"
                objs = objs.order_by(f"{order_prefix}{column_name}")

            total = objs.count()
            # Use values() to convert to list for pagination
            paginated_data = list(objs[start : start + length])
            return rp.JsonResponse(
                {
                    "draw": int(R.get("draw", 1)),
                    "recordsTotal": total,
                    "recordsFiltered": total,
                    "data": paginated_data,
                }
            )
            # return rp.JsonResponse(data = {'data':list(objs)})

        if R.get("action") == "checklist_details" and R.get("jobneedid"):
            objs = JobneedDetails.objects.get_e_tour_checklist_details(R["jobneedid"])
            return rp.JsonResponse(data={"data": list(objs)})

        if R.get("action") == "get_checkpointdetails":
            qset = P["model"].objects.get_tourdetails(R)
            return rp.JsonResponse({"data": list(qset)}, status=200)

        if R.get("action") == "getAttachmentJobneed" and R.get("id"):
            att = P["model"].objects.getAttachmentJobneed(R["id"])
            return rp.JsonResponse(data={"data": list(att)})

        if R.get("action") == "getAttachmentJND" and R.get("id"):
            att = JobneedDetails.objects.getAttachmentJND(R["id"])
            return rp.JsonResponse(data={"data": list(att)})

        if R.get("id"):
            obj = P["model"].objects.get(id=R["id"])
            form = P["form_class"](instance=obj, initial=P["initial"], request=request)
            logger.info("object retrieved %s", (obj.jobdesc))
            checkpoints = self.get_checkpoints(P, obj=obj)
            cxt = {
                "internaltourform": form,
                "child_internaltour": P["subform"](prefix="child", request=request),
                "edit": True,
                "checkpoints": checkpoints,
            }
            return render(request, P["template_form"], context=cxt)

    @staticmethod
    def get_checkpoints(P, obj):
        logger.info("getting checkpoints for the internal tour [start]")
        checkpoints = None

        try:
            checkpoints = (
                P["model"]
                .objects.select_related(
                    "parent",
                    "asset",
                    "qset",
                    "pgroup",
                    "people",
                    "job",
                    "client",
                    "bu",
                    "ticketcategory",
                )
                .filter(parent_id=obj.id)
                .values(
                    "asset__assetname",
                    "asset__id",
                    "qset__id",
                    "ctzoffset",
                    "qset__qsetname",
                    "plandatetime",
                    "expirydatetime",
                    "gracetime",
                    "seqno",
                    "jobstatus",
                    "id",
                )
                .order_by("seqno")
            )

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "jobneed_checkpoints_database_error", {"object_id": obj.id if obj else None})
            logger.error(f"Jobneed checkpoints database error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "jobneed_checkpoints_validation_error", {"object_id": obj.id if obj else None})
            logger.error(f"Jobneed checkpoints validation error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "jobneed_checkpoints_system_error", {"object_id": obj.id if obj else None})
            logger.critical(f"Jobneed checkpoints system error: {str(e)}", extra={"correlation_id": correlation_id})
            raise

        else:
            logger.info("checkpoints retrieved returned success")
        return checkpoints


class JobneedExternalTours(LoginRequiredMixin, View):
    params = {
        "model": Jobneed,
        "template_path": "schedhuler/e_tourlist_jobneed.html",
        "template_modern": "schedhuler/tourlist_jobneed_modern.html",
        "template_form": "schedhuler/e_tourform_jobneed.html",
        "fields": [
            "jobdesc",
            "people__peoplename",
            "pgroup__groupname",
            "id",
            "ctzoffset",
            "bu__buname",
            "bu__solid",
            "plandatetime",
            "expirydatetime",
            "jobstatus",
            "gracetime",
            "performedby__peoplename",
            "seqno",
            "qset__qsetname",
            "attachmentcount",
        ],
        "related": [
            "pgroup",
            "ticketcategory",
            "asset",
            "client",
            "job",
            "qset",
            "people",
            "parent",
            "bu",
        ],
        "form_class": scd_forms.E_TourFormJobneed,
        "initial": {
            "identifier": Jobneed.Identifier.EXTERNALTOUR,
            "frequency": Jobneed.Frequency.NONE,
        },
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        # first load the template
        if R.get("template"):
            # Check for view type preference
            if R.get("old", "false").lower() == "true":
                return render(request, P["template_path"])  # Classic table view
            elif R.get("list", "false").lower() == "true":
                return render(request, "schedhuler/tourlist_jobneed_modern_list.html", {"tour_type": "External Tour"})  # Modern list view
            return render(request, P.get("template_modern", P["template_path"]), {"tour_type": "External Tour"})  # Modern card view (default)

        # then load the table with objects for table_view
        if R.get("action", None) == "list" or R.get("search_term"):
            objs = P["model"].objects.get_externaltourlist_jobneed(
                request, P["related"], P["fields"]
            )
            return rp.JsonResponse(data={"data": list(objs)})

        if R.get("action") == "checkpoints":
            objs = P["model"].objects.get_ext_checkpoints_jobneed(
                request, P["related"], P["fields"]
            )
            return rp.JsonResponse(data={"data": list(objs)})

        if R.get("action") == "checklist_details" and R.get("jobneedid"):
            objs = JobneedDetails.objects.get_e_tour_checklist_details(R["jobneedid"])
            return rp.JsonResponse(data={"data": list(objs)})

        if R.get("action") == "getAttachmentJobneed" and R.get("id"):
            att = P["model"].objects.getAttachmentJobneed(R["id"])
            return rp.JsonResponse(data={"data": list(att)})

        if R.get("action") == "getAttachmentJND" and R.get("id"):
            att = JobneedDetails.objects.getAttachmentJND(R["id"])
            return rp.JsonResponse(data={"data": list(att)})

        if R.get("id"):
            obj = P["model"].objects.get(id=R["id"])
            form = P["form_class"](instance=obj, initial=P["initial"])
            logger.info("object retrieved %s", (obj.jobdesc))
            checkpoints = self.get_checkpoints(P, obj=obj)
            cxt = {"externaltourform": form, "edit": True, "checkpoints": checkpoints}
            return render(request, P["template_form"], context=cxt)

    @staticmethod
    def get_checkpoints(P, obj):
        logger.info("getting checkpoints for the internal tour [start]")
        checkpoints = None

        try:
            checkpoints = (
                P["model"]
                .objects.select_related(
                    "parent",
                    "asset",
                    "qset",
                    "pgroup",
                    "people",
                    "job",
                    "client",
                    "bu",
                    "ticketcategory",
                    "gpslocation",
                )
                .annotate(
                    bu__gpslocation=AsGeoJSON("bu__gpslocation"),
                    gps=AsGeoJSON("gpslocation"),
                )
                .filter(parent_id=obj.id)
                .values(
                    "asset__assetname",
                    "asset__id",
                    "qset__id",
                    "qset__qsetname",
                    "plandatetime",
                    "expirydatetime",
                    "bu__gpslocation",
                    "gps",
                    "gracetime",
                    "seqno",
                    "jobstatus",
                    "id",
                )
                .order_by("seqno")
            )

        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_jobneed_checkpoints_database_error", {"object_id": obj.id if obj else None})
            logger.error(f"External jobneed checkpoints database error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_jobneed_checkpoints_validation_error", {"object_id": obj.id if obj else None})
            logger.error(f"External jobneed checkpoints validation error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_jobneed_checkpoints_system_error", {"object_id": obj.id if obj else None})
            logger.critical(f"External jobneed checkpoints system error: {str(e)}", extra={"correlation_id": correlation_id})
            raise

        else:
            logger.info("checkpoints retrieved returned success")
        return checkpoints


class JobneedTasks(LoginRequiredMixin, View):
    params = {
        "model": Jobneed,
        "model_jnd": JobneedDetails,
        "template_path": "schedhuler/tasklist_jobneed.html",
        "template_modern": "schedhuler/tasklist_jobneed_modern.html",
        "fields": [
            "jobdesc",
            "people__peoplename",
            "pgroup__groupname",
            "id",
            "plandatetime",
            "expirydatetime",
            "jobstatus",
            "gracetime",
            "asset__assetname",
            "performedby__peoplename",
            "asset__assetname",
            "qset__qsetname",
            "bu__buname",
            "bu__bucode",
            "ctzoffset",
            "assignedto",
            "jobtype",
            "ticketcategory__taname",
            "other_info__isAcknowledged",
        ],
        "related": [
            "pgroup",
            "ticketcategory",
            "asset",
            "client",
            "ctzoffset",
            "frequency",
            "job",
            "qset",
            "people",
            "parent",
            "bu",
        ],
        "template_form": "schedhuler/taskform_jobneed.html",
        "form_class": scd_forms.TaskFormJobneed,
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params

        # first load the template
        if R.get("template"):
            # Check for view type preference
            if R.get("old", "false").lower() == "true":
                return render(request, P["template_path"])  # Classic table view
            elif R.get("list", "false").lower() == "true":
                return render(request, "schedhuler/tasklist_jobneed_modern_list.html")  # Modern list view
            return render(request, P.get("template_modern", P["template_path"]))  # Modern card view (default)

        # then load the table with objects for table_view
        if R.get("action", None) == "list" or R.get("search_term"):
            draw = int(request.GET.get("draw", 1))
            start = int(request.GET.get("start", 0))
            length = int(request.GET.get("length", 10))
            search_value = request.GET.get("search[value]", "").strip()

            order_col = request.GET.get("order[0][column]")
            order_dir = request.GET.get("order[0][dir]")
            column_name = request.GET.get(f"columns[{order_col}][data]")

            objs = P["model"].objects.get_task_list_jobneed(
                P["related"], P["fields"], request
            )

            if search_value:
                objs = objs.filter(
                    Q(jobdesc__icontains=search_value)
                    | Q(jobstatus__icontains=search_value)
                    | Q(bu__buname__icontains=search_value)
                    | Q(bu__bucode__icontains=search_value)
                    | Q(qset__qsetname__icontains=search_value)
                    | Q(asset__assetname__icontains=search_value)
                )
            if column_name:
                order_prefix = "" if order_dir == "asc" else "-"
                objs = objs.order_by(f"{order_prefix}{column_name}")

            total = objs.count()
            paginated = objs[start : start + length]
            data = list(paginated)
            return rp.JsonResponse(
                {
                    "draw": draw,
                    "recordsTotal": total,
                    "recordsFiltered": total,
                    "data": data,
                },
                status=200,
            )

        if R.get("action") == "getAttachmentJND":
            att = P["model_jnd"].objects.getAttachmentJND(R["id"])
            return rp.JsonResponse(data={"data": list(att)})

        if R.get("action") == "get_task_details" and R.get("taskid"):
            objs = P["model_jnd"].objects.get_task_details(R["taskid"])
            return rp.JsonResponse({"data": list(objs)})

        if R.get("action") == "acknowledgeAutoCloseTask":
            obj = P["model"].objects.filter(id=R["id"]).first()
            obj.other_info["isAcknowledged"] = True
            obj.other_info["acknowledged_by"] = request.user.peoplecode
            obj.save()
            objs = P["model"].objects.get_task_list_jobneed(
                P["related"], P["fields"], request, obj.id
            )
            return rp.JsonResponse({"row": objs[0]}, status=200)

        # load form with instance
        if R.get("id"):
            obj = utils.get_model_obj(int(R["id"]), request, P)
            cxt = {
                "taskformjobneed": P["form_class"](request=request, instance=obj),
                "edit": True,
            }
            return render(request, P["template_form"], context=cxt)
        
        # return empty form for new task creation
        if R.get("action") == "form":
            cxt = {
                "taskformjobneed": P["form_class"](request=request),
                "edit": False,
            }
            return render(request, P["template_form"], context=cxt)


class SchdTasks(LoginRequiredMixin, View):
    params = {
        "model": Job,
        "template_path": "schedhuler/schd_tasklist_job.html",
        "fields": [
            "jobname",
            "people__peoplename",
            "pgroup__groupname",
            "fromdate",
            "uptodate",
            "qset__qsetname",
            "asset__assetname",
            "planduration",
            "gracetime",
            "expirytime",
            "id",
            "ctzoffset",
            "assignedto",
            "bu__buname",
            "bu__bucode",
        ],
        "related": ["pgroup", "people", "asset", "bu"],
        "form_class": scd_forms.SchdTaskFormJob,
        "template_form": "schedhuler/schd_taskform_job.html",
        "initial": {
            "starttime": time(00, 00, 00),
            "endtime": time(00, 00, 00),
            "fromdate": datetime.combine(date.today(), time(00, 00, 00)),
            "uptodate": datetime.combine(date.today(), time(23, 00, 00))
            + timedelta(days=2),
            "identifier": Job.Identifier.TASK,
            "frequency": Job.Frequency.NONE,
            "scantype": Job.Scantype.QR,
            "priority": Job.Priority.LOW,
            "planduration": 0,
            "gracetime": 0,
            "expirytime": 0,
        },
    }

    @method_decorator(cache_page(3))
    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        # first load the template
        if R.get("template"):
            return render(request, P["template_path"])

        # then load the table with objects for table_view
        if R.get("action") == "list":
            logger.info("Retrieve Tasks view")
            objects = P["model"].objects.get_scheduled_tasks(
                request, P["related"], P["fields"]
            )
            logger.info(
                f"Tasks objects {len(objects)} retrieved from db"
                if objects
                else "No Records!"
            )
            return rp.JsonResponse(data={"data": list(objects)})

        # load form with instance
        if R.get("id"):
            obj = utils.get_model_obj(int(R["id"]), request, P)
            cxt = {
                "schdtaskform": P["form_class"](request=request, instance=obj),
                "edit": True,
            }
            return render(request, P["template_form"], context=cxt)

        # return empty form
        if R.get("action") == "form":
            cxt = {
                "schdtaskform": P["form_class"](initial=P["initial"], request=request)
            }
            return render(request, P["template_form"], context=cxt)

        if R.get("runscheduler"):
            # run job scheduler
            pass
        
        # Default: return template if no specific action
        return render(request, P["template_path"])

    def post(self, request, *args, **kwargs):
        R = request.POST
        logger.info("Task form submitted")
        from apps.core.utils_new.http_utils import get_clean_form_data
        data, create = get_clean_form_data(request), True
        utils.display_post_data(data)
        if pk := R.get("pk", None):
            obj = utils.get_model_obj(pk, request, {"model": self.params["model"]})
            form = self.params["form_class"](instance=obj, data=data, request=request)
            logger.info("retrieved existing task whose jobname:= '%s'", (obj.jobname))
        else:
            form = self.params["form_class"](data=data, request=request)
            logger.info(
                "new task submitted following is the form-data:\n%s\n",
                (pformat(form.data)),
            )
        response = None
        try:
            with transaction.atomic(using=get_current_db_name()):
                if form.is_valid():
                    response = self.process_valid_schd_taskform(request, form)
                else:
                    response = self.process_invalid_schd_taskform(form)
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "jobneed_task_form_validation_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"Jobneed task form validation error: {str(e)}", extra={"correlation_id": correlation_id})
            response = rp.JsonResponse(
                {"errors": "Form validation failed"}, status=400
            )
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "jobneed_task_form_database_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"Jobneed task form database error: {str(e)}", extra={"correlation_id": correlation_id})
            response = rp.JsonResponse(
                {"errors": "Database error occurred"}, status=500
            )
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "jobneed_task_form_system_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.critical(f"Jobneed task form system error: {str(e)}", extra={"correlation_id": correlation_id})
            response = rp.JsonResponse(
                {"errors": "System error occurred"}, status=500
            )
        return response

    @staticmethod
    def process_valid_schd_taskform(request, form):
        resp = None
        logger.info("task form processing/saving [ START ]")
        try:
            job = form.save(commit=False)
            job.parent = get_none_job()  # NONE parent placeholder
            job.save()
            job = putils.save_userinfo(job, request.user, request.session)
            logger.info("task form saved success...")
        except IntegrityError as ex:
            return utils.handle_intergrity_error("Task")
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "jobneed_task_save_validation_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Jobneed task save validation error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse(
                {"error": "Task validation failed"}, status=400
            )
            raise
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "jobneed_task_save_database_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Jobneed task save database error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse(
                {"error": "Database error during task save"}, status=500
            )
            raise
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "jobneed_task_save_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"Jobneed task save system error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = rp.JsonResponse(
                {"error": "System error occurred"}, status=500
            )
            raise
        else:
            logger.info("task form is processed successfully")
            resp = rp.JsonResponse(
                {
                    "jobname": job.jobname,
                    "url": f'/operations/tasks/scheduled/?id={job.id}',
                },
                status=200,
            )
        logger.info("task form processing/saving [ END ]")
        return resp

    @staticmethod
    def process_invalid_schd_taskform(form):
        logger.info(
            "processing invalidt task form sending errors to the client [ START ]"
        )
        cxt = {"errors": form.errors}
        logger.error(f"Form validation errors: {form.errors}")
        logger.info(
            "processing invalidt task form sending errors to the client [ END ]"
        )
        return rp.JsonResponse(cxt, status=404)


class InternalTourScheduling(LoginRequiredMixin, View):
    params = {
        "template_form": "schedhuler/schd_i_tourform_job.html",
        "template_list": "schedhuler/schd_i_tourlist_job.html",
        "form_class": scd_forms.Schd_I_TourJobForm,
        "subform": scd_forms.SchdChild_I_TourJobForm,
        "model": Job,
        "related": ["pgroup", "people", "bu"],
        "initial": {
            "starttime": time(00, 00, 00),
            "endtime": time(00, 00, 00),
            "expirytime": 0,
            "identifier": Job.Identifier.INTERNALTOUR,
            "priority": Job.Priority.LOW,
            "scantype": Job.Scantype.QR,
            "gracetime": 0,
            "planduration": 0,
        },
        "fields": [
            "id",
            "jobname",
            "people__peoplename",
            "pgroup__groupname",
            "fromdate",
            "uptodate",
            "planduration",
            "gracetime",
            "expirytime",
            "assignedto",
            "bu__bucode",
            "bu__buname",
            "ctzoffset",
        ],
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        # return template
        if R.get("template") == "true":
            return render(request, P["template_list"])

        if R.get("action") == "loadTourCheckpoints":
            parentid = R.get("parentid", "")
            if parentid and parentid != "None" and parentid.strip():
                objs = (
                    P["model"]
                    .objects.filter(parent_id=parentid)
                    .select_related("asset", "qset")
                    .values(
                        "pk",
                        "qset__qsetname",
                        "asset__assetname",
                        "seqno",
                        "expirytime",
                        "asset_id",
                        "qset_id",
                    )
                    .order_by("seqno")
                )
            else:
                objs = P["model"].objects.none()
            return rp.JsonResponse({"data": list(objs)})

        if R.get("action") == "loadAssetChekpointsForSelectField":
            objs = Asset.objects.get_asset_checkpoints_for_tour(request)
            return rp.JsonResponse(
                {"items": list(objs), "total_count": len(objs)}, status=200
            )

        if R.get("action") == "loadQuestionSetsForSelectField":
            objs = QuestionSet.objects.get_qsets_for_tour(request)
            return rp.JsonResponse(
                {"items": list(objs), "total_count": len(objs)}, status=200
            )

        if R.get("id"):
            obj = utils.get_model_obj(int(R["id"]), request, P)
            logger.info(f"object retrieved {obj}")
            form = P["form_class"](instance=obj, request=request)
            cxt = {
                "schdtourform": form,
                "edit": True,
            }
            return render(request, P["template_form"], cxt)

        # return resp to delete request
        if R.get("action", None) == "delete" and R.get("id", None):
            return utils.render_form_for_delete(request, self.params, False)

        if R.get("action") == "list":
            objs = P["model"].objects.get_scheduled_internal_tours(
                request, P["related"], P["fields"]
            )
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if R.get("action") == "form":
            cxt = {
                "schdtourform": P["form_class"](request=request, initial=P["initial"])
            }
            return render(request, P["template_form"], cxt)

    def post(self, request, *args, **kwargs):
        R, P = request.POST, self.params

        full_form_data = request.POST.get('formData', 'NOT FOUND')
        logger.info(
            "Form data received",
            extra={
                'correlation_id': getattr(request, 'correlation_id', None),
                'form_data_length': len(full_form_data) if full_form_data != 'NOT FOUND' else 0,
                'has_gracetime': 'gracetime' in full_form_data if full_form_data != 'NOT FOUND' else False,
                'has_cron': 'cron' in full_form_data if full_form_data != 'NOT FOUND' else False,
            }
        )
        logger.info("Form data validation", extra={'has_fromdate': 'fromdate' in full_form_data if full_form_data != 'NOT FOUND' else False})
        
        from apps.core.utils_new.http_utils import get_clean_form_data
        
        # Try direct raw access to bypass potential SafeExceptionReporterFilter truncation
        try:
            raw_body = request.body.decode('utf-8')
            logger.info(f"Raw request.body length: {len(raw_body)}")
            logger.info(f"Raw body contains gracetime: {'gracetime' in raw_body}")
            logger.info(f"Raw body contains cron: {'cron' in raw_body}")
            logger.info(f"Raw body contains fromdate: {'fromdate' in raw_body}")
        except (UnicodeDecodeError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(e, "request_body_decode_error", {"content_length": len(request.body) if hasattr(request, 'body') else None})
            logger.error(f"Could not decode request.body: {str(e)}", extra={"correlation_id": correlation_id})
        
        pk, data = request.POST.get("pk", None), get_clean_form_data(request)
        
        # Debug logging
        logger.info(f"Tour form POST data keys: {list(data.keys())}")
        logger.info(f"Tour form data values: {dict(data.items())}")
        logger.info(f"isdynamic field: {data.get('isdynamic', 'MISSING')}")
        for key in ['fromdate', 'uptodate', 'cron', 'gracetime', 'scantype']:
            logger.info(f"Field '{key}': {data.get(key, 'MISSING')}")
        
        if R.get("postType") == "saveCheckpoint":
            data = P["model"].objects.handle_save_checkpoint_guardtour(request)
            return rp.JsonResponse(data, status=200, safe=False)
        try:
            if pk:
                msg = "internal scheduler tour"
                form = utils.get_instance_for_update(
                    data, P, msg, int(pk), kwargs={"request": request}
                )
                self.updatecheckpoints(pk)
            else:
                form = P["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.params, cxt)
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_jobneed_validation_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"External tour jobneed validation error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = utils.handle_Exception(request)
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_jobneed_database_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"External tour jobneed database error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = utils.handle_Exception(request)
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_jobneed_system_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.critical(f"External tour jobneed system error: {str(e)}", extra={"correlation_id": correlation_id})
            resp = utils.handle_Exception(request)
        return resp

    def handle_valid_form(self, form, request):
        data = request.POST.get("asssigned_checkpoints")
        logger.info(f"Raw asssigned_checkpoints data: {repr(data)}")
        logger.info(f"Data type: {type(data)}")
        try:
            with transaction.atomic(using=get_current_db_name()):
                assigned_checkpoints = []
                if data and data.strip():
                    logger.info(f"Attempting to parse JSON: {data[:200]}...")
                    try:
                        # First decode HTML entities if present
                        import html
                        decoded_data = html.unescape(data)
                        logger.info(f"Decoded JSON data: {decoded_data[:200]}...")
                        assigned_checkpoints = json.loads(decoded_data)
                        logger.info(f"Successfully parsed {len(assigned_checkpoints)} checkpoints")
                    except json.JSONDecodeError as je:
                        logger.error(f"JSON decode error: {je}")
                        logger.error(f"Invalid JSON data: {repr(data)}")
                        # Try to handle common JSON issues
                        if data == "[]" or data == "null" or data == "undefined":
                            assigned_checkpoints = []
                            logger.info("Handled empty/null checkpoint data")
                        else:
                            # If it's still malformed, proceed with empty list but log the issue
                            logger.warning("Proceeding with empty checkpoint list due to malformed JSON")
                            assigned_checkpoints = []
                else:
                    logger.info("No checkpoint data provided, using empty list")
                job = form.save(commit=False)
                job.parent = get_none_job()  # NONE parent placeholder
                job.asset = get_none_asset()  # NONE asset placeholder
                job.qset_id = 1  # Keep existing qset logic
                job.other_info["istimebound"] = form.cleaned_data["istimebound"]
                job.other_info["isdynamic"] = form.cleaned_data["isdynamic"]
                job.save()
                job = putils.save_userinfo(job, request.user, request.session)
                logger.info("guard tour  and its checkpoints saved success...")
                return rp.JsonResponse(
                    {
                        "jobname": job.jobname,
                        "url": f'/operations/schedules/tours/internal/?id={job.id}',
                    },
                    status=200,
                )
        except NotNullViolation as e:
            error_logger.error("Not null error catched")
        except IntegrityError as ex:
            return utils.handle_intergrity_error("Tour")
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "tour_checkpoint_save_validation_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Tour checkpoint save validation error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "tour_checkpoint_save_database_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"Tour checkpoint save database error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "tour_checkpoint_save_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"Tour checkpoint save system error: {str(e)}", extra={"correlation_id": correlation_id})
            raise

    def updatecheckpoints(self, pk):
        job = Job.objects.select_related(
            'jobneed', 'asset', 'asset__location', 'people', 'people__shift', 'people__bt'
        ).get(id=pk)
        updated = Job.objects.filter(parent_id=pk).update(
            people_id=job.people_id, pgroup_id=job.pgroup_id
        )
        logger.info(
            "checkpoints also updated according to parent record %s" % (updated)
        )

    # def save_checpoints_for_tour(self, checkpoints, job, request):
    #     try:
    #         logger.info(f"saving Checkpoints found {len(checkpoints)} [started]")
    #         CP = {}
    #         job = Job.objects.filter(id = job.id).values()[0]
    #         self.params['model'].objects.filter(parent_id = job['id']).delete()
    #         count=0
    #         for cp in checkpoints:
    #             CP['expirytime'] = cp[5]
    #             CP['qsetname'] = cp[4]
    #             CP['assetid']    = cp[1]
    #             CP['qsetid']     = cp[3]
    #             CP['seqno']       = cp[0]
    #             obj = Job.objects.create(
    #                 **sutils.job_fields(job, CP)
    #             )
    #             putils.save_userinfo(obj, request.user, request.session)
    #             count+=1
    #         if count == len(checkpoints):
    #             logger.info('all checkpoints saved successfully')
    #     except (DatabaseError, IntegrityError, ValueError, TypeError, ObjectDoesNotExist) as ex:
    #         error_logger.error(
    #             "failed to insert checkpoints, something went wrong", exc_info = True)
    #         raise ex
    #     else:
    #         logger.info("inserting checkpoints finished...")

    # @staticmethod
    # def get_checkpoints(obj, P):
    #     logger.info("getting checkpoints started...")
    #     checkpoints = None
    #     try:
    #         checkpoints = P['model'].objects.select_related(
    #             'parent', 'asset', 'qset', 'pgroup',
    #             'people',
    #         ).filter(parent_id = obj.id).annotate(
    #             assetname = F('asset__assetname'),
    #             qsetname = F('qset__qsetname')
    #             ).values(
    #             'seqno',
    #             'assetname',
    #             'asset_id',
    #             'qsetname',
    #             'qset_id',
    #             'expirytime',
    #             'id')
    #     except (DatabaseError, IntegrityError, ValueError, TypeError, ObjectDoesNotExist):
    #         logger.critical("something went wrong", exc_info = True)
    #         raise
    #     else:
    #         logger.info("checkpoints retrieved returned success")
    #     return checkpoints


class ExternalTourScheduling(LoginRequiredMixin, View):
    params = {
        "template_form": "schedhuler/schd_e_tourform_job.html",
        "template_list": "schedhuler/schd_e_tourlist_job.html",
        "form_class": scd_forms.Schd_E_TourJobForm,
        "model": Job,
        "related": ["pgroup", "people"],
        "initial": {
            "seqno": -1,
            "identifier": Job.Identifier.EXTERNALTOUR,
            "scantype": Job.Scantype.QR,
            "starttime": time(00, 00, 00),
            "endtime": time(00, 00, 00),
            "priority": Job.Priority.HIGH,
            "expirytime": 0,
            "gracetime": 0,
            "planduration": 0,
            "pgroup": 1,
        },
        "fields": [
            "id",
            "jobname",
            "people__peoplename",
            "pgroup__groupname",
            "fromdate",
            "uptodate",
            "planduration",
            "gracetime",
            "expirytime",
            "bu__buname",
            "assignedto",
        ],
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params

        # return template first
        if R.get("template") == "true":
            return render(request, P["template_list"])

        # return resp for for list view
        if R.get("action") == "list":
            objs = P["model"].objects.get_listview_objs_schdexttour(request)
            return rp.JsonResponse({"data": list(objs)}, status=200)

        # return resp for job creation
        if R.get("action") == "form":
            cxt = {
                "schdexternaltourform": P["form_class"](
                    request=request, initial=P["initial"]
                )
            }
            return render(request, P["template_form"], context=cxt)

        # return resp to populate the sites from sitgroup
        if R.get("action") == "get_sitesfromgroup":
            if R.get("id") in ["None", "", None]:
                return rp.JsonResponse({"data": []}, status=200)
            job = Job.objects.filter(id=int(R["id"])).values(*utils.JobFields.fields)[0]
            objs = pm.Pgbelonging.objects.get_sitesfromgroup(job)
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if (
            R.get("action") == "forcegetfromgroup"
            and R.get("sgroup_id") not in ["None", "", None]
            and R.get("id") not in ["None", "", None]
        ):
            job = Job.objects.filter(id=int(R["id"])).values(*utils.JobFields.fields)[0]
            objs = pm.Pgbelonging.objects.get_sitesfromgroup(job, force=True)
            return rp.JsonResponse({"rows": list(objs)}, status=200)

        # return resp to load checklist
        if R.get("action") == "loadChecklist":
            qset = QuestionSet.objects.load_checklist(request)
            return rp.JsonResponse(
                {"items": list(qset), "total_count": len(qset)}, status=200
            )

        # return resp to delete request
        if R.get("action", None) == "delete" and R.get("id", None):
            return utils.render_form_for_delete(request, self.params, False)

        # return resp for updation of job
        if R.get("id"):
            obj = utils.get_model_obj(int(R["id"]), request, P)
            initial = {
                "israndom": obj.other_info["is_randomized"],
                "tourfrequency": obj.other_info["tour_frequency"],
                "breaktime": obj.other_info["breaktime"],
            }  # obj.other_info['breaktime']}
            cxt = {
                "schdexternaltourform": P["form_class"](
                    instance=obj, request=request, initial=initial
                )
            }
            return render(request, P["template_form"], context=cxt)

    def post(self, request, *args, **kwargs):
        P = self.params
        pk, R = request.POST.get("pk", None), request.POST
        from apps.core.utils_new.http_utils import get_clean_form_data
        formData = get_clean_form_data(request)
        
        logger.info(
            "Form data received",
            extra={
                'correlation_id': getattr(request, 'correlation_id', None),
                'post_keys_count': len(list(R.keys())),
                'form_data_length': len(str(formData))
            }
        )
        try:
            if R.get("postType") == "saveCheckpoint":
                data = Job.objects.handle_save_checkpoint_sitetour(request)
                return rp.JsonResponse(data, status=200, safe=False)
            if R.get("action") == "saveCheckpoints":
                try:
                    import html
                    checkpoints_data = R.get("checkpoints", "")
                    logger.info(f"Raw checkpoints data: '{checkpoints_data[:100]}...'")  # Truncate for readability
                    if not checkpoints_data:
                        logger.error("No checkpoints data received")
                        return rp.JsonResponse({"error": "No checkpoints data provided"}, status=400)
                    
                    # Decode HTML entities before parsing JSON
                    decoded_data = html.unescape(checkpoints_data)
                    logger.info(f"Decoded checkpoints data: '{decoded_data[:100]}...'")
                    checkpoints = json.loads(decoded_data)
                    return self.saveCheckpointsinJob(R, checkpoints, P, request)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in checkpoints data: {e}")
                    logger.error(f"Raw data was: '{R.get('checkpoints', '')[:100]}...'")
                    return rp.JsonResponse({"error": f"Invalid JSON data: {str(e)}"}, status=400)
            if pk:
                msg = "external scheduler tour"
                form = utils.get_instance_for_update(
                    formData, P, msg, int(pk), kwargs={"request": request}
                )
            else:
                form = P["form_class"](formData, request=request)
            if form.is_valid():
                return self.handle_valid_form(form, request, P)
            cxt = {"errors": form.errors}
            return utils.handle_invalid_form(request, self.params, cxt)
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tours_jobneed_validation_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"External tours jobneed validation error: {str(e)}", extra={"correlation_id": correlation_id})
            return utils.handle_Exception(request)
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tours_jobneed_database_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.error(f"External tours jobneed database error: {str(e)}", extra={"correlation_id": correlation_id})
            return utils.handle_Exception(request)
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tours_jobneed_system_error", {"form_data": bool(form.data if 'form' in locals() else None)})
            logger.critical(f"External tours jobneed system error: {str(e)}", extra={"correlation_id": correlation_id})
            return utils.handle_Exception(request)

    @staticmethod
    def handle_valid_form(form, request, P):
        try:
            with transaction.atomic(using=get_current_db_name()):
                job = form.save(commit=False)
                if request.POST.get("pk"):
                    Job.objects.filter(parent_id=job.id).update(
                        qset_id=job.qset_id,
                        people_id=job.people_id,
                        pgroup_id=job.pgroup_id,
                    )
                if not request.POST.get("pk"):
                    job.other_info["tour_frequency"] = form.cleaned_data[
                        "tourfrequency"
                    ]
                    job.other_info["is_randomized"] = form.cleaned_data["israndom"]
                    job.other_info["breaktime"] = form.cleaned_data["breaktime"]
                job.save()
                job = putils.save_userinfo(job, request.user, request.session)
                # self.save_checkpoints_injob_fromgroup(job, P)
                return rp.JsonResponse({"pk": job.id}, status=200)
        except IntegrityError as ex:
            return utils.handle_intergrity_error("Task")
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_save_validation_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"External tour save validation error: {str(e)}", extra={"correlation_id": correlation_id})
            return utils.handle_Exception(request)
        except DatabaseException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_save_database_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.error(f"External tour save database error: {str(e)}", extra={"correlation_id": correlation_id})
            return utils.handle_Exception(request)
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "external_tour_save_system_error", {"user": request.user.id if hasattr(request, 'user') else None})
            logger.critical(f"External tour save system error: {str(e)}", extra={"correlation_id": correlation_id})
            return utils.handle_Exception(request)

    @staticmethod
    def saveCheckpointsinJob(R, checkpoints, P, request):
        try:
            job = Job.objects.filter(id=int(R["job_id"])).values()[0]
            P["model"].objects.filter(parent_id=job["id"]).delete()
            count = 0
            for cp in checkpoints:
                obj = Job.objects.create(**sutils.job_fields(job, cp, external=True))
                putils.save_userinfo(obj, request.user, request.session, bu=cp["buid"])
                count += 1
            if count == len(checkpoints):
                objs = P["model"].objects.get_sitecheckpoints_exttour(job)
                return rp.JsonResponse({"count": count, "data": list(objs)}, status=200)
            return rp.JsonResponse({"error": "Checkpoints not saved"}, status=400)
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(e, "checkpoint_save_validation_error", {"job_id": R.get("job_id") if R else None})
            logger.error(f"Checkpoint save validation error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except (IntegrityError, DatabaseException) as e:
            correlation_id = ErrorHandler.handle_exception(e, "checkpoint_save_database_error", {"job_id": R.get("job_id") if R else None})
            logger.error(f"Checkpoint save database error: {str(e)}", extra={"correlation_id": correlation_id})
            raise
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(e, "checkpoint_save_system_error", {"job_id": R.get("job_id") if R else None})
            logger.critical(f"Checkpoint save system error: {str(e)}", extra={"correlation_id": correlation_id})
            raise


class JobneednJNDEditor(LoginRequiredMixin, View):
    params = {
        "model": Jobneed,
        "jnd": JobneedDetails,
        "fields": [
            "id",
            "quesname",
            "answertype",
            "min",
            "max",
            "options",
            "alerton",
            "ismandatory",
        ],
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        if R.get("action") == "get_jndofjobneed" and R.get("jobneedid"):
            objs = P["jnd"].objects.get_jndofjobneed(R)
            return rp.JsonResponse({"data": list(objs)}, status=200)
        return rp.JsonResponse({"data": []}, status=200)

    def post(self, request, *args, **kwargs):
        R, P = request.POST, self.params
        if R.get("tourjobneed"):
            data = P["model"].objects.handle_jobneedpostdata(request)
            return rp.JsonResponse({"data": list(data)}, status=200, safe=False)
        if R.get("question"):
            data = P["qsb"].objects.handle_questionpostdata(request)
            return rp.JsonResponse({"data": list(data)}, status=200, safe=False)


class ExternalTourTracking(LoginRequiredMixin, View):
    model = Jobneed
    template = "schedhuler/site_tour_tracking.html"

    def get(self, request, *args, **kwargs):
        R = request.GET
        if R.get("action") == "get_checkpoints":
            (
                checkpoints,
                info,
                path,
                latestloc,
            ) = self.model.objects.get_latlng_of_checkpoints(R["jobneed_id"])
            return rp.JsonResponse(
                {
                    "checkpoints": checkpoints,
                    "info": info,
                    "path": path,
                    "latestloc": latestloc,
                },
                status=200,
                safe=False,
            )
        return render(request, self.template, {"jobneed_id": R["jobneed_id"]})
