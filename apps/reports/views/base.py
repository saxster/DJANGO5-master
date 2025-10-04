"""
Base classes for Reports views

Shared base classes and forms for report management.

Migrated from apps/reports/views.py
Date: 2025-09-30
"""
import logging
import json
import asyncio
from pprint import pformat
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError, DatabaseError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.views.generic.base import View
from django.contrib import messages
from django.http import (
    JsonResponse,
    QueryDict,
    response as rp,
    FileResponse,
    HttpResponse,
)
from io import BytesIO
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from django.urls import reverse
from apps.onboarding import models as on
from apps.peoples import utils as putils
from apps.core import utils
from apps.activity.forms.question_form import QsetBelongingForm
from apps.reports import forms as rp_forms
import subprocess, os
from django.conf import settings
from apps.reports import utils as rutils
from background_tasks.tasks import create_save_report_async
from background_tasks.report_tasks import remove_reportfile
from celery.result import AsyncResult
from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Jobneed
from apps.activity.models.question_model import QuestionSet, Question
from apps.core.decorators import csrf_protect_ajax, rate_limit
from datetime import datetime
from apps.core.utils_new.db_utils import get_current_db_name


# Exception for integration errors (if not defined elsewhere)
class IntegrationException(Exception):
    """Custom exception for integration failures"""
    pass


log = logging.getLogger("django")
debug_log = logging.getLogger("debug_logger")
error_log = logging.getLogger("error_logger")


class MasterReportForm(LoginRequiredMixin, View):
    """
    Base form class for report template management

    Provides common functionality for creating and updating report templates
    """
    template_path = None
    form_class = None
    subform = QsetBelongingForm
    model = QuestionSet
    initial = {"type": None}
    viewname = None

    def get(self, request, *args, **kwargs):
        """Handle GET requests for report template forms"""
        R, resp = request.GET, None
        utils.PD(get=R)

        if R.get("template"):
            return self._handle_template_request(request, R, kwargs)
        elif R.get("get_reports"):
            resp = self.get_reports(R)

        return resp

    def _handle_template_request(self, request, R, kwargs):
        """Handle template-specific GET requests"""
        # Return empty form if no id
        if not R.get("id"):
            cxt = {
                "reporttemp_form": self.form_class(
                    request=request, initial=self.initial
                ),
                "qsetbng": self.subform(),
            }
            return render(request, self.template_path, context=cxt)

        # Return form with instance loaded
        if R.get("id") or kwargs.get("id"):
            pk = R["id"] or kwargs.get("id")
            obj = self.model.objects.get(id=pk)
            form = self.form_class(
                instance=obj, initial=self.initial, request=request
            )
            cxt = {"reporttemp_form": form, "qsetbng": self.subform()}
            return render(request, self.template_path, context=cxt)

    def post(self, request, *args, **kwargs):
        """Handles creation and update of report template instances"""
        R, create = QueryDict(request.POST), True
        utils.PD(post=R)
        response = None

        # Process existing data for update
        if pk := request.POST.get("pk", None):
            obj = utils.get_model_obj(pk, request, {"model": self.model})
            form = self.form_class(request=request, instance=obj, data=request.POST)
            create = False
        # Process new data for creation
        else:
            form = self.form_class(
                data=request.POST, request=request, initial=self.initial
            )

        # Check for validation
        try:
            if form.is_valid():
                response = self.process_valid_form(request, form, create)
            else:
                response = self.process_invalid_form(form)
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError,
                ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError,
                asyncio.CancelledError):
            log.critical("failed to process form, something went wrong", exc_info=True)
            response = rp.JsonResponse(
                {"errors": "Failed to process form, something went wrong"}, status=404
            )

        return response

    def process_valid_form(self, request, form, create):
        """Process and save valid report template form"""
        resp = None
        log.info("report template form processing/saving [ START ]")

        try:
            utils.PD(cleaned=form.data)
            report = form.save(commit=False)
            report.buincludes = json.dumps(request.POST.getlist("buincludes", []))
            report.site_grp_includes = json.dumps(
                request.POST.getlist("site_grp_includes", [])
            )
            report.site_type_includes = json.dumps(
                request.POST.getlist("site_type_includes", [])
            )
            report.parent_id = -1
            report.save()
            report = putils.save_userinfo(
                report, request.user, request.session, create=create
            )
            debug_log.debug("report saved:%s", (report.qsetname))
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError,
                ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError,
                asyncio.CancelledError, json.JSONDecodeError) as ex:
            log.critical("%s form is failed to process", self.viewname, exc_info=True)
            resp = rp.JsonResponse(
                {"errors": "saving %s template form failed..." % self.viewname},
                status=404,
            )
            raise ex
        else:
            log.info("%s template form is processed successfully", self.viewname)
            resp = rp.JsonResponse(
                {
                    "msg": report.qsetname,
                    "url": reverse("reports:sitereport_template_form"),
                    "id": report.id,
                },
                status=200,
            )

        log.info("%s template form processing/saving [ END ]", self.viewname)
        return resp

    @staticmethod
    def process_invalid_form(form):
        """Process and return errors for invalid forms"""
        log.info("processing invalid forms sending errors to the client [ START ]")
        cxt = {"errors": form.errors}
        log.info("processing invalid forms sending errors to the client [ END ]")
        return rp.JsonResponse(cxt, status=404)

    def get_reports(self, R):
        """Retrieve reports based on parent ID"""
        qset, count = [], 0
        if parent := R.get("parent_id"):
            qset = self.model.objects.filter(parent_id=parent).values(
                "id", "qsetname", "asset_id", "seqno"
            )
            count = qset.count()

        log.info(
            "site reports found for the parent with id %s" % R["id"]
            if qset
            else "Not found any reports"
        )
        resp = {"data": list(qset)}
        return JsonResponse(data=resp, status=200)


class MasterReportBelonging(LoginRequiredMixin, View):
    """
    Base class for report belonging/association management
    """
    model = QuestionSet

    def get(self, request, *args, **kwargs):
        """Handle GET requests for report associations"""
        R = request.GET
        if R.get("dataSource") == "sitereporttemplate" and R.get("parent"):
            objs = self.model.objects.filter(parent_id=int(R["parent"])).values(
                "id",
                "qsetname",
                "enable",
                "seqno",
                "parent_id",
                "type",
                "bu_id",
                "buincludes",
                "assetincludes",
                "site_grp_includes",
                "site_type_includes",
            )
            return JsonResponse({"data": list(objs)}, status=200)

        return JsonResponse({"data": []}, status=200)


class SiteReportTemplateForm(MasterReportForm):
    """Site report template form view"""
    template_path = "reports/sitereport_tempform.html"
    form_class = rp_forms.SiteReportTemplate
    viewname = "site report"
    initial = {"type": QuestionSet.Type.SITEREPORTTEMPLATE}
    model = QuestionSet


class IncidentReportTemplateForm(MasterReportForm):
    """Incident report template form view"""
    template_path = "reports/incidentreport_tempform.html"
    form_class = rp_forms.IncidentReportTemplate
    viewname = "incident report"
    initial = {"type": QuestionSet.Type.INCIDENTREPORTTEMPLATE}
    model = QuestionSet
