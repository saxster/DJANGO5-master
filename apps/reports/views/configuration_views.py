"""
Report Configuration Views

Views for configuring site reports, incident reports, and work permit report templates.

Migrated from apps/reports/views.py
Date: 2025-09-30
"""
from .base import *


class ConfigSiteReportTemplate(LoginRequiredMixin, View):
    """Configuration view for site report templates"""
    params = {
        "template_form": "reports/sitereport_tempform.html",
        "template_list": "reports/sitereport_template_list.html",
        "model": QuestionSet,
        "form_class": rp_forms.SiteReportTemplate,
        "initial": {"type": QuestionSet.Type.SITEREPORTTEMPLATE},
        "related": [],
        "fields": ["id", "qsetname", "enable"],
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        if R.get("template"):
            return render(request, P["template_list"])

        if R.get("action") == "list":
            objs = P["model"].objects.get_configured_sitereporttemplates(
                request, P["related"], P["fields"], P["initial"]["type"]
            )
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if R.get("action") == "form":
            cxt = {
                "reporttemp_form": P["form_class"](
                    initial=P["initial"], request=request
                ),
                "test": rp_forms.TestForm,
            }
            return render(request, P["template_form"], cxt)

        if R.get("action") == "get_sections":
            parent_id = 0 if R["parent_id"] == "undefined" else R["parent_id"]
            qset = P["model"].objects.get_qset_with_questionscount(parent_id)
            return rp.JsonResponse({"data": list(qset)}, status=200)

        if R.get("action") == "delete" and R.get("id") not in [None, "None"]:
            P["model"].objects.filter(id=R["id"]).update(enable=False)
            log.info(f'site report template with this id : {R["id"]} is deleted')
            return rp.JsonResponse(data={}, status=200)

        if R.get("id"):
            obj = utils.get_model_obj(R["id"], request, {"model": P["model"]})
            cxt = {
                "reporttemp_form": P["form_class"](instance=obj, request=request),
                "test": rp_forms.TestForm,
            }
            return render(request, P["template_form"], cxt)

    def post(self, request, *args, **kwargs):
        R, P = request.POST, self.params
        try:
            data = QueryDict(request.POST["formData"])
            if pk := request.POST.get("pk", None):
                msg = "site report template updated successfully"
                form = utils.get_instance_for_update(
                    data, P, msg, int(pk), {"request": request}
                )
                create = False
            else:
                form = P["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, data)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, P, cxt)
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, asyncio.CancelledError, json.JSONDecodeError):
            resp = utils.handle_Exception(request)
        return resp

    @staticmethod
    def handle_valid_form(form, request, data):
        try:
            with transaction.atomic(using=get_current_db_name()):
                template = form.save()
                template.parent_id = data.get("parent_id", 1)
                template = putils.save_userinfo(template, request.user, request.session)
                return rp.JsonResponse({"parent_id": template.id}, status=200)
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, asyncio.CancelledError, json.JSONDecodeError):
            return utils.handle_Exception(request)


class ConfigIncidentReportTemplate(LoginRequiredMixin, View):
    """Configuration view for incident report templates"""
    params = {
        "template_form": "reports/incidentreport_tempform.html",
        "template_list": "reports/incidentreport_template_list.html",
        "model": QuestionSet,
        "form_class": rp_forms.SiteReportTemplate,
        "initial": {"type": QuestionSet.Type.INCIDENTREPORTTEMPLATE},
        "related": [],
        "fields": ["id", "qsetname", "enable"],
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        if R.get("template"):
            return render(request, P["template_list"])

        if R.get("action") == "list":
            objs = P["model"].objects.get_configured_sitereporttemplates(
                request, P["related"], P["fields"], P["initial"]["type"]
            )
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if R.get("action") == "form":
            cxt = {
                "reporttemp_form": P["form_class"](
                    initial=P["initial"], request=request
                ),
                "test": rp_forms.TestForm,
            }
            return render(request, P["template_form"], cxt)

        if R.get("action") == "loadQuestions":
            qset = Question.objects.questions_of_client(request, R)
            return rp.JsonResponse(
                {"items": list(qset), "total_count": len(qset)}, status=200
            )

        if R.get("action") == "get_sections":
            parent_id = 0 if R["parent_id"] == "undefined" else R["parent_id"]
            qset = P["model"].objects.get_qset_with_questionscount(parent_id)
            return rp.JsonResponse({"data": list(qset)}, status=200)

        if R.get("action") == "delete" and R.get("id") not in [None, "None"]:
            P["model"].objects.filter(id=R["id"]).update(enable=False)
            log.info(f'site report template with this id : {R["id"]} is deleted')
            return rp.JsonResponse(data={}, status=200)

        if R.get("id"):
            obj = utils.get_model_obj(R["id"], request, {"model": P["model"]})
            cxt = {
                "reporttemp_form": P["form_class"](instance=obj, request=request),
                "test": rp_forms.TestForm,
            }
            return render(request, P["template_form"], cxt)

    def post(self, request, *args, **kwargs):
        R, P = request.POST, self.params
        try:
            data = QueryDict(request.POST["formData"])
            if pk := request.POST.get("pk", None):
                msg = "incident report template updated successfully"
                form = utils.get_instance_for_update(
                    data, P, msg, int(pk), {"request": request}
                )
                create = False
            else:
                form = P["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, data)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, P, cxt)
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, asyncio.CancelledError, json.JSONDecodeError):
            resp = utils.handle_Exception(request)
        return resp

    @staticmethod
    def handle_valid_form(form, request, data):
        try:
            with transaction.atomic(using=get_current_db_name()):
                template = form.save()
                template.parent_id = data.get("parent_id", 1)
                template = putils.save_userinfo(template, request.user, request.session)
                return rp.JsonResponse({"parent_id": template.id}, status=200)
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, asyncio.CancelledError, json.JSONDecodeError):
            return utils.handle_Exception(request)


class ConfigWorkPermitReportTemplate(LoginRequiredMixin, View):
    """Configuration view for work permit report templates"""
    params = {
        "template_form": "reports/workpermitreport_tempform.html",
        "template_list": "reports/workpermitreport_template_list.html",
        "model": QuestionSet,
        "form_class": rp_forms.SiteReportTemplate,
        "initial": {"type": QuestionSet.Type.WORKPERMITTEMPLATE},
        "related": [],
        "fields": ["id", "qsetname", "enable"],
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        if R.get("template"):
            return render(request, P["template_list"])

        if R.get("action") == "list":
            objs = P["model"].objects.get_configured_sitereporttemplates(
                P["related"], P["fields"], P["initial"]["type"]
            )
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if R.get("action") == "form":
            cxt = {
                "reporttemp_form": P["form_class"](
                    initial=P["initial"], request=request
                ),
                "test": rp_forms.TestForm,
            }
            return render(request, P["template_form"], cxt)

        if R.get("action") == "loadQuestions":
            qset = Question.objects.questions_of_client(request, R)
            return rp.JsonResponse(
                {"items": list(qset), "total_count": len(qset)}, status=200
            )

        if R.get("action") == "get_sections":
            parent_id = 0 if R["parent_id"] == "undefined" else R["parent_id"]
            qset = P["model"].objects.get_qset_with_questionscount(parent_id)
            return rp.JsonResponse({"data": list(qset)}, status=200)

        if R.get("action") == "delete" and R.get("id") not in [None, "None"]:
            P["model"].objects.filter(id=R["id"]).update(enable=False)
            log.info(f'site report template with this id : {R["id"]} is deleted')
            return rp.JsonResponse(data={}, status=200)

        if R.get("id"):
            obj = utils.get_model_obj(R["id"], request, {"model": P["model"]})
            cxt = {
                "reporttemp_form": P["form_class"](instance=obj, request=request),
                "test": rp_forms.TestForm,
            }
            return render(request, P["template_form"], cxt)

    def post(self, request, *args, **kwargs):
        R, P = request.POST, self.params
        try:
            data = QueryDict(request.POST["formData"])
            if pk := request.POST.get("pk", None):
                msg = f"{self.label}_view"
                form = utils.get_instance_for_update(
                    data, P, msg, int(pk), {"request": request}
                )
                create = False
            else:
                form = P["form_class"](data, request=request)
            if form.is_valid():
                resp = self.handle_valid_form(form, request, data)
            else:
                cxt = {"errors": form.errors}
                resp = utils.handle_invalid_form(request, P, cxt)
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, asyncio.CancelledError, json.JSONDecodeError):
            resp = utils.handle_Exception(request)
        return resp

    @staticmethod
    def handle_valid_form(form, request, data):
        try:
            with transaction.atomic(using=get_current_db_name()):
                template = form.save()
                template.parent_id = data.get("parent_id", 1)
                template = putils.save_userinfo(template, request.user, request.session)
                return rp.JsonResponse({"parent_id": template.id}, status=200)
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, asyncio.CancelledError, json.JSONDecodeError):
            return utils.handle_Exception(request)
