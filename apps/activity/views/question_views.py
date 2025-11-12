import logging

try:
    import psycopg2.errors as pg_errs
except ImportError:  # pragma: no cover - dev environments without psycopg2
    from django.db import DatabaseError

    class _PGErrorShim:
        class UniqueViolation(DatabaseError):
            """Fallback UniqueViolation when psycopg2 is unavailable."""
            pass

    pg_errs = _PGErrorShim()

from apps.core.utils_new.db_utils import get_current_db_name

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, DatabaseError, transaction
from django.core.exceptions import ValidationError

from django.shortcuts import render
from django.views.generic.base import View

import apps.activity.filters as aft
from apps.activity.forms.question_form import (
    QuestionForm,
    ChecklistForm,
    QuestionSetForm,
    QsetBelongingForm,
)
from apps.activity.forms.asset_form import CheckpointForm
from apps.activity.models.question_model import (
    QuestionSet,
    QuestionSetBelonging,
    Question,
)
from apps.activity.models.asset_model import Asset
import apps.activity.utils as av_utils
import apps.peoples.utils as putils
from apps.core import utils

logger = logging.getLogger("django")


# Create your views here.
class Question(LoginRequiredMixin, View):
    params = {
        "form_class": QuestionForm,
        "template_form": "activity/partials/partial_ques_form.html",
        "template_list": "activity/question.html",
        "partial_form": "peoples/partials/partial_ques_form.html",
        "partial_list": "peoples/partials/partial_people_list.html",
        "related": ["unit"],
        "model": Question,
        "filter": aft.QuestionFilter,
        "fields": [
            "id",
            "quesname",
            "answertype",
            "unit__tacode",
            "isworkflow",
        ],
        "form_initials": {
            "answertype": Question.AnswerType.DROPDOWN,
            "category": 1,
            "unit": 1,
        },
    }

    def get(self, request, *args, **kwargs):
        R, resp = request.GET, None

        # return cap_list data
        if R.get("template"):
            # Check if classic view is explicitly requested
            if R.get("classic"):
                return render(request, self.params["template_list"])
            # Default to modern view, preserving any additional parameters
            context = {}
            if R.get("type"):
                context["type_param"] = R.get("type")
            return render(request, "activity/question_modern.html", context)
        if R.get("action", None) == "list":
            objs = self.params["model"].objects.questions_listview(
                request, self.params["fields"], self.params["related"]
            )
            return rp.JsonResponse(data={"data": list(objs)})

        # return cap_form empty
        elif R.get("action", None) == "form":
            cxt = {
                "ques_form": self.params["form_class"](
                    request=request, initial=self.params["form_initials"]
                ),
                "msg": "create question requested",
            }
            resp = utils.render_form(request, self.params, cxt)

        # handle delete request
        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, self.params, True)
        # return form with instance
        elif R.get("id", None):
            obj = utils.get_model_obj(int(R["id"]), request, self.params)
            resp = utils.render_form_for_update(request, self.params, "ques_form", obj)
        return resp

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for question creation and updates.
        Refactored to use service layer for better maintainability.
        """
        from apps.activity.services.question_service import QuestionService, FormDataService
        from django.http import JsonResponse

        try:
            # Clean and validate form data using service
            form_data = FormDataService.clean_question_form_data(request.POST)

            # Additional validation
            validation_errors = FormDataService.validate_question_data(form_data)
            if validation_errors:
                return JsonResponse({
                    'success': False,
                    'errors': validation_errors,
                    'message': 'Form validation failed'
                }, status=400)

            # Determine if this is an update or create operation
            pk = request.POST.get("pk", None)

            if pk:
                # Update existing question
                result = QuestionService.update_question(int(pk), form_data, request)
            else:
                # Create new question
                result = QuestionService.create_question(form_data, request)

            # Return appropriate response
            if result['success']:
                return JsonResponse(result, status=200)
            else:
                status_code = 400
                if result.get('error_type') == 'not_found':
                    status_code = 404
                elif result.get('error_type') == 'integrity_error':
                    status_code = 409

                return JsonResponse(result, status=status_code)

        except (TypeError, ValidationError, ValueError) as e:
            # Use centralized error handling
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'view': 'Question.post',
                    'method': request.method,
                    'path': request.path
                }
            )

            return JsonResponse({
                'success': False,
                'message': 'An unexpected error occurred',
                'correlation_id': correlation_id
            }, status=500)

    def handle_valid_form(self, form, request, create):
        logger.info("ques form is valid")
        logger.info(f"Form cleaned data: {form.cleaned_data}")
        logger.info(f"Options field value: {form.cleaned_data.get('options')}")
        ques = None
        from apps.activity.models.question_model import Question

        try:
            ques = form.save()
            ques = putils.save_userinfo(
                ques, request.user, request.session, create=create
            )
            logger.info("question form saved")
            row_data = Question.objects.optimized_filter_for_display(
                ques.id, self.params["fields"]
            )
            data = {
                "msg": f"Question '{ques.quesname}' saved successfully",
                "row": row_data,
            }
            return rp.JsonResponse(data, status=200)
        except (IntegrityError, pg_errs.UniqueViolation):
            return utils.handle_intergrity_error("Question")


class QuestionSet(LoginRequiredMixin, View):
    params = {
        "form_class": QuestionSetForm,
        "template_form": "activity/questionset_form.html",
        "template_list": "activity/questionset_list.html",
        "related": ["unit", "bu"],
        "model": QuestionSet,
        "filter": aft.MasterQsetFilter,
        "fields": [
            "qsetname",
            "type",
            "id",
            "ctzoffset",
            "cdtz",
            "mdtz",
            "bu__bucode",
            "bu__buname",
        ],
        "form_initials": {"type": "CHECKLIST"},
    }

    def get(self, request, *args, **kwargs):
        R, P, resp = request.GET, self.params, None
        # first load the template
        if R.get("template"):
            return render(request, P["template_list"])

        # return qset_list data
        if R.get("action", None) == "list" or R.get("search_term"):
            objs = self.params["model"].objects.checklist_listview(
                request, P["fields"], P["related"]
            )
            return rp.JsonResponse(data={"data": list(objs)})

        # return questionset_form empty
        if R.get("action", None) == "form":
            cxt = {
                "checklistform": self.params["form_class"](
                    request=request, initial=self.params["form_initials"]
                ),
                "qsetbng": QsetBelongingForm(initial={"ismandatory": True}),
                "msg": "create checklist form requested",
            }

            resp = render(request, self.params["template_form"], context=cxt)

        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, self.params, False)

        elif R.get("id", None):
            logger.info("detail view requested")
            obj = utils.get_model_obj(int(R["id"]), request, self.params)
            cxt = {
                "checklistform": self.params["form_class"](
                    request=request, instance=obj
                )
            }
            resp = render(request, self.params["template_form"], context=cxt)
        return resp

    def post(self, request, *args, **kwargs):
        resp, create = None, True
        try:
            from apps.core.utils_new.http_utils import get_clean_form_data

            data = get_clean_form_data(request).copy()
            
            # Add type from URL parameter if not in form data
            if not data.get('type') and request.GET.get('type'):
                data['type'] = request.GET.get('type')
                logger.info(f"Added type from URL: {data['type']}")
            
            if pk := request.POST.get("pk", None):
                msg = "checklist"
                form = utils.get_instance_for_update(
                    data, self.params, msg, int(pk), {"request": request}
                )
                create = False
            else:
                form = self.params["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, self.params, cxt)
        except (ValidationError, ValueError) as e:
            logger.error(
                f"Validation error in QuestionSet.post: {type(e).__name__}",
                extra={'error_message': str(e), 'user_id': request.user.id}
            )
            resp = utils.handle_invalid_form(request, self.params, {"errors": {"form": str(e)}})
        except (DatabaseError, IntegrityError) as e:
            logger.error(
                f"Database error in QuestionSet.post: {type(e).__name__}",
                extra={'error_message': str(e), 'user_id': request.user.id}
            )
            resp = utils.handle_intergrity_error("QuestionSet")
        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            logger.critical(
                f"Unexpected error in QuestionSet.post: {type(e).__name__}",
                extra={'error_message': str(e), 'user_id': request.user.id},
                exc_info=True
            )
            resp = utils.handle_Exception(request)
        return resp

    @staticmethod
    def get_questions_for_form(qset):
        try:
            questions = list(
                QuestionSetBelonging.objects.select_related("question")
                .filter(qset_id=qset)
                .values(
                    "ismandatory",
                    "seqno",
                    "max",
                    "min",
                    "alerton",
                    "isavpt",
                    "avpttype",
                    "options",
                    "question__quesname",
                    "answertype",
                    "question__id",
                    "display_conditions",  # Add conditional logic field for web interface
                )
            )
        except DatabaseError as e:
            logger.error(
                f"Database error in get_questions_for_form: {type(e).__name__}",
                extra={'error_message': str(e), 'qset_id': qset},
                exc_info=True
            )
            raise
        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            logger.critical(
                f"Unexpected error in get_questions_for_form: {type(e).__name__}",
                extra={'error_message': str(e), 'qset_id': qset},
                exc_info=True
            )
            raise
        else:
            return questions

    def handle_valid_form(self, form, request, create):
        logger.info("checklist form is valid")
        try:
            with transaction.atomic(using=get_current_db_name()):
                # assigned_questions = json.loads(
                #     request.POST.get("asssigned_questions"))
                qset = form.save()
                putils.save_userinfo(qset, request.user, request.session, create=create)
                logger.info("checklist form is valid")
                fields = {
                    "qset": qset.id,
                    "qsetname": qset.qsetname,
                    "client": qset.client_id,
                }
                # self.save_qset_belonging(request, assigned_questions, fields)
                data = {
                    "success": "Record has been saved successfully",
                    "parent_id": qset.id,
                }
                return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return utils.handle_intergrity_error("Question Set")

    @staticmethod
    def save_qset_belonging(request, assigned_questions, fields):
        try:
            logger.info("saving QuestoinSet Belonging [started]")
            logger.info(
                f'{" " * 4} saving QuestoinSet Belonging found {len(assigned_questions)} questions'
            )
            av_utils.insert_questions_to_qsetblng(
                assigned_questions, QuestionSetBelonging, fields, request
            )
            logger.info("saving QuestionSet Belongin [Ended]")
        except (DatabaseError, IntegrityError) as e:
            logger.error(
                f"Database error in save_qset_belonging: {type(e).__name__}",
                extra={
                    'error_message': str(e),
                    'assigned_questions_count': len(assigned_questions) if assigned_questions else 0
                },
                exc_info=True
            )
            raise
        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.critical(
                f"Unexpected error in save_qset_belonging: {type(e).__name__}",
                extra={
                    'error_message': str(e),
                    'assigned_questions_count': len(assigned_questions) if assigned_questions else 0
                },
                exc_info=True
            )
            raise


def deleteQSB(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "POST method required for delete operations"}, status=405
        )

    status = None
    try:
        quesname = request.POST.get("quesname")
        answertype = request.POST.get("answertype")
        qset = request.POST.get("qset")
        logger.info("request for delete QSB '%s' start", (quesname))
        QuestionSetBelonging.objects.get(
            question__quesname=quesname, answertype=answertype, qset_id=qset
        ).delete()
        statuscode = 200
        logger.info("Delete request executed successfully")
    except QuestionSetBelonging.DoesNotExist:
        logger.warning(
            f"QuestionSetBelonging not found for deletion: {quesname}",
            extra={'quesname': quesname, 'answertype': answertype, 'qset': qset}
        )
        statuscode = 404
    except (DatabaseError, IntegrityError) as e:
        logger.error(
            f"Database error in deleteQSB: {type(e).__name__}",
            extra={
                'error_message': str(e),
                'quesname': quesname,
                'answertype': answertype,
                'qset': qset
            },
            exc_info=True
        )
        statuscode = 500
        raise
    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            f"Unexpected error in deleteQSB: {type(e).__name__}",
            extra={
                'error_message': str(e),
                'quesname': quesname,
                'answertype': answertype,
                'qset': qset
            },
            exc_info=True
        )
        statuscode = 500
        raise
    status = "success" if statuscode == 200 else "failed"
    data = {"status": status}
    return rp.JsonResponse(data, status=statuscode)


class QsetNQsetBelonging(LoginRequiredMixin, View):
    params = {
        "model1": QuestionSet,
        "qsb": QuestionSetBelonging,
        "fields": [
            "id",
            "quesname",
            "answertype",
            "min",
            "max",
            "options",
            "alerton",
            "ismandatory",
            "isavpt",
            "avpttype",
        ],
    }

    def get(self, request, *args, **kwargs):
        from apps.activity.models.question_model import Question

        R, P = request.GET, self.params
        if R.get("action") == "loadQuestions":
            qset = Question.objects.questions_of_client(request, R)
            return rp.JsonResponse(
                {"items": list(qset), "total_count": len(qset)}, status=200
            )

        if (R.get("action") == "getquestion") and R.get("questionid") not in [
            None,
            "null",
        ]:
            objs = Question.objects.get_questiondetails(R["questionid"])
            return rp.JsonResponse({"qsetbng": list(objs)}, status=200)

        if R.get("action") == "get_questions_of_qset":
            objs = QuestionSetBelonging.objects.get_questions_of_qset(R)
            return rp.JsonResponse({"data": list(objs)}, status=200)
        
        if R.get("action") == "get_questions_with_logic":
            # New endpoint for mobile with conditional logic
            data = QuestionSetBelonging.objects.get_questions_with_logic(R.get("qset_id"))
            return rp.JsonResponse(data, status=200)
        
        if R.get("action") == "get_qsb_options":
            # Endpoint for getting question options for dependency configuration
            qsb_id = R.get("qsb_id")
            if qsb_id:
                try:
                    qsb = QuestionSetBelonging.objects.select_related('question').get(pk=qsb_id)
                    return rp.JsonResponse({
                        "answertype": qsb.answertype,
                        "options": qsb.options,
                        "min": qsb.min,
                        "max": qsb.max,
                        "question_name": qsb.question.quesname
                    }, status=200)
                except QuestionSetBelonging.DoesNotExist:
                    return rp.JsonResponse({"error": "Question not found"}, status=404)
            return rp.JsonResponse({"error": "No question ID provided"}, status=400)

    def post(self, request, *args, **kwargs):
        from apps.activity.models.question_model import QuestionSet

        R, P = request.POST, self.params
        if R.get("questionset"):
            data = QuestionSet.objects.handle_qsetpostdata(request)
            return rp.JsonResponse({"data": list(data)}, status=200, safe=False)
        if R.get("question"):
            data = QuestionSetBelonging.objects.handle_questionpostdata(request)
            return rp.JsonResponse(data, status=200, safe=False)


class Checkpoint(LoginRequiredMixin, View):
    params = {
        "form_class": CheckpointForm,
        "template_form": "activity/partials/partial_checkpoint_form.html",
        "template_list": "activity/checkpoint_list.html",
        "partial_form": "peoples/partials/partial_checkpoint_form.html",
        "partial_list": "peoples/partials/chekpoint_list.html",
        "related": ["parent", "type", "bu", "location"],
        "model": Asset,
        "fields": [
            "assetname",
            "assetcode",
            "runningstatus",
            "identifier",
            "location__locname",
            "parent__assetname",
            "gps",
            "id",
            "enable",
            "bu__buname",
            "bu__bucode",
        ],
        "form_initials": {
            "runningstatus": "WORKING",
            "identifier": "CHECKPOINT",
            "iscritical": False,
            "enable": True,
        },
    }

    def get(self, request, *args, **kwargs):
        R, resp, P = request.GET, None, self.params

        # first load the template
        if R.get("template"):
            # Check if classic view is explicitly requested
            if R.get("classic"):
                return render(request, P["template_list"], {"label": "Checkpoint"})
            # Default to modern view, preserving any additional parameters
            context = {"label": "Checkpoint"}
            if R.get("type"):
                context["type_param"] = R.get("type")
            return render(request, "activity/checkpoint_list_modern.html", context)
        # return qset_list data
        if R.get("action", None) == "list":
            objs = P["model"].objects.get_checkpointlistview(
                request, P["related"], P["fields"]
            )
            return rp.JsonResponse(data={"data": list(objs)})

        if (
            R.get("action", None) == "qrdownload"
            and R.get("code", None)
            and R.get("name", None)
        ):
            return utils.download_qrcode(
                R["code"], R["name"], "CHECKPOINTQR", request.session, request
            )

        # return questionset_form empty
        if R.get("action", None) == "form":
            P["form_initials"].update({"type": 1, "parent": 1})
            cxt = {
                "master_assetform": P["form_class"](
                    request=request, initial=P["form_initials"]
                ),
                "msg": "create checkpoint requested",
                "label": "Checkpoint",
            }

            resp = utils.render_form(request, P, cxt)

        elif R.get("action", None) == "delete" and R.get("id", None):
            resp = utils.render_form_for_delete(request, P, True)
        elif R.get("id", None):
            obj = utils.get_model_obj(int(R["id"]), request, P)
            cxt = {"label": "Checkpoint"}
            resp = utils.render_form_for_update(
                request, P, "master_assetform", obj, extra_cxt=cxt
            )
        return resp

    def post(self, request, *args, **kwargs):
        resp, create, P = None, False, self.params
        try:
            #            data = QueryDict(request.POST["formData"])
            from apps.core.utils_new.http_utils import get_clean_form_data

            data = get_clean_form_data(request)

            if pk := request.POST.get("pk", None):
                msg = "Checkpoint_view"
                form = utils.get_instance_for_update(
                    data, P, msg, int(pk), kwargs={"request": request}
                )
                create = False
            else:
                form = P["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, create)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, P, cxt)
        except (ValidationError, ValueError) as e:
            logger.error(
                f"Validation error in Checkpoint.post: {type(e).__name__}",
                extra={'error_message': str(e), 'user_id': request.user.id}
            )
            resp = utils.handle_invalid_form(request, P, {"errors": {"form": str(e)}})
        except (DatabaseError, IntegrityError) as e:
            logger.error(
                f"Database error in Checkpoint.post: {type(e).__name__}",
                extra={'error_message': str(e), 'user_id': request.user.id}
            )
            resp = utils.handle_intergrity_error("Checkpoint")
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.critical(
                f"Unexpected error in Checkpoint.post: {type(e).__name__}",
                extra={'error_message': str(e), 'user_id': request.user.id},
                exc_info=True
            )
            resp = utils.handle_Exception(request)
        return resp

    def handle_valid_form(self, form, request, create):
        logger.info("checkpoint form is valid")
        P = self.params
        try:
            cp = form.save(commit=False)
            cp.gpslocation = form.cleaned_data["gpslocation"]
            putils.save_userinfo(cp, request.user, request.session, create=create)
            logger.info("checkpoint form saved")
            data = {
                "msg": f"{cp.assetcode}",
                "row": Asset.objects.get_checkpointlistview(
                    request, P["related"], P["fields"], id=cp.id
                ),
            }
            return rp.JsonResponse(data, status=200)
        except IntegrityError:
            return utils.handle_intergrity_error("Checkpoint")
