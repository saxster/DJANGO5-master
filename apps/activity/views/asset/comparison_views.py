"""
Asset comparison views for analyzing asset performance and parameters.

This module contains views for comparing assets and their parameters.
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import QueryDict
from django.http import response as rp
from django.shortcuts import render
from django.views.generic.base import View

from apps.activity.forms.asset_form import AssetComparisionForm, ParameterComparisionForm
from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import JobneedDetails
from apps.activity.models.question_model import QuestionSet, QuestionSetBelonging

logger = logging.getLogger(__name__)


class AssetComparisionView(LoginRequiredMixin, View):
    """View for comparing multiple assets."""

    template = "activity/asset_comparision.html"
    form = AssetComparisionForm

    def get(self, request, *args, **kwargs):
        """Handle GET requests for asset comparison."""
        R, S = request.GET, request.session

        if R.get("template"):
            cxt = {"asset_cmp_form": self.form(request=request)}
            return render(request, self.template, cxt)

        if R.get("action") == "get_assets" and R.get("of_type"):
            qset = (
                Asset.objects.filter(
                    client_id=S["client_id"], bu_id=S["bu_id"], type_id=R["of_type"]
                )
                .values("id", "assetname")
                .distinct()
            )
            return rp.JsonResponse(data={"options": list(qset)}, status=200)

        if R.get("action") == "get_qsets" and R.getlist("of_assets[]"):
            qset = (
                QuestionSet.objects.filter(
                    client_id=S["client_id"],
                    bu_id=S["bu_id"],
                    type__in=["CHECKLIST", "ASSETMAINTENANCE"],
                    parent_id=1,
                    enable=True,
                    assetincludes__contains=R.getlist("of_assets[]"),
                )
                .values("id", "qsetname")
                .distinct()
            )
            return rp.JsonResponse(data={"options": list(qset)}, status=200)

        if R.get("action") == "get_questions" and R.getlist("of_qset"):
            qset = (
                QuestionSetBelonging.objects.filter(
                    client_id=S["client_id"],
                    bu_id=S["bu_id"],
                    answertype="NUMERIC",
                    qset_id=R.get("of_qset"),
                )
                .select_related("question")
                .values("question_id", "question__quesname")
                .distinct()
            )
            return rp.JsonResponse(data={"options": list(qset)}, status=200)

        if R.get("action") == "get_data_for_graph" and R.get("formData"):
            formData = QueryDict(R["formData"])
            data = JobneedDetails.objects.get_asset_comparision(request, formData)
            return rp.JsonResponse({"series": data}, status=200, safe=False)


class ParameterComparisionView(LoginRequiredMixin, View):
    """View for comparing parameters across assets."""

    template = "activity/parameter_comparision.html"
    form = ParameterComparisionForm

    def get(self, request, *args, **kwargs):
        """Handle GET requests for parameter comparison."""
        R, S = request.GET, request.session

        if R.get("template"):
            cxt = {"asset_param_form": self.form(request=request)}
            return render(request, self.template, cxt)

        if R.get("action") == "get_assets" and R.get("of_type"):
            qset = (
                Asset.objects.filter(
                    client_id=S["client_id"], bu_id=S["bu_id"], type_id=R["of_type"]
                )
                .values("id", "assetname")
                .distinct()
            )
            return rp.JsonResponse(data={"options": list(qset)}, status=200)

        if R.get("action") == "get_questions":
            questionsets = (
                QuestionSet.objects.filter(
                    client_id=S["client_id"],
                    bu_id=S["bu_id"],
                    type__in=["CHECKLIST", "ASSETMAINTENANCE"],
                    parent_id=1,
                    enable=True,
                    assetincludes__contains=[R.get("of_asset")],
                )
                .values_list("id", flat=True)
                .distinct()
            )
            qset = (
                QuestionSetBelonging.objects.filter(
                    client_id=S["client_id"],
                    bu_id=S["bu_id"],
                    answertype="NUMERIC",
                    qset_id__in=questionsets,
                )
                .select_related("question")
                .values("question_id", "question__quesname")
                .distinct()
            )
            return rp.JsonResponse(data={"options": list(qset)}, status=200)

        if R.get("action") == "get_data_for_graph" and R.get("formData"):
            formData = QueryDict(R["formData"])
            data = JobneedDetails.objects.get_parameter_comparision(request, formData)
            return rp.JsonResponse({"series": data}, status=200, safe=False)