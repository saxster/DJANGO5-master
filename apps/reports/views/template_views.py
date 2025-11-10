"""
Template Management Views

Views for managing and retrieving report templates.

Migrated from apps/reports/views.py
Date: 2025-09-30
Performance optimizations added: November 5, 2025
"""
from .base import (
    LoginRequiredMixin,
    View,
    render,
    rp,
    QueryDict,
    on_client,
    on_core,
    putils,
    utils,
    QsetBelongingForm,
    rp_forms,
    QuestionSet,
    Jobneed,
    log,
    debug_log,
    IntegrationException,
    MasterReportForm,
    get_current_db_name,
    json,
    ValidationError,
    redirect,
    messages,
    IntegrityError,
    DatabaseError,
    ObjectDoesNotExist,
    asyncio,
)
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from apps.core.constants.cache_ttl import CACHE_TTL_MEDIUM, CACHE_TTL_SHORT
import tempfile
import requests


@method_decorator(cache_page(CACHE_TTL_MEDIUM), name='get')
class RetriveSiteReports(LoginRequiredMixin, View):
    """
    Retrieve and list site reports with optimized service layer

    Performance: Cached for CACHE_TTL_MEDIUM (5 minutes) - Added Nov 5, 2025
    """
    model = Jobneed
    template_path = "reports/sitereport_list.html"

    def get(self, request, *args, **kwargs):
        """Returns paginated site reports from db with optimized service layer"""
        response, requestData = None, request.GET
        if requestData.get("template"):
            return render(request, self.template_path)

        try:
            # Use the optimized service layer with proper error handling
            from apps.reports.services.report_data_service import ReportDataService
            report_data, error = ReportDataService.get_site_reports(request)

            if error:
                log.warning(f"Site reports error: {error}")
                messages.error(request, error, "alert alert-warning")
                response = rp.JsonResponse({"data": [], "error": error}, status=400)
            else:
                response = rp.JsonResponse(
                    {"data": report_data},
                    status=200,
                    encoder=utils.CustomJsonEncoderWithDistance,
                )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            log.critical("Unexpected error in site reports view", exc_info=True)
            messages.error(request, "Something went wrong", "alert alert-danger")
            response = redirect("/dashboard")

        return response


@method_decorator(cache_page(CACHE_TTL_MEDIUM), name='get')
class RetriveIncidentReports(LoginRequiredMixin, View):
    """
    Retrieve and list incident reports with optimized service layer

    Performance: Cached for CACHE_TTL_MEDIUM (5 minutes) - Added Nov 5, 2025
    """
    model = Jobneed
    template_path = "reports/incidentreport_list.html"

    def get(self, request, *args, **kwargs):
        """Returns paginated incident reports from db with optimized service layer"""
        response, requestData = None, request.GET
        if requestData.get("template"):
            return render(request, self.template_path)

        try:
            # Use the optimized service layer with proper error handling
            from apps.reports.services.report_data_service import ReportDataService
            reports_data, attachments_data, error = ReportDataService.get_incident_reports(request)

            if error:
                log.warning(f"Incident reports error: {error}")
                messages.error(request, error, "alert alert-warning")
                response = rp.JsonResponse({"data": [], "atts": [], "error": error}, status=400)
            else:
                response = rp.JsonResponse(
                    {"data": reports_data, "atts": attachments_data}, status=200
                )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            log.critical("Unexpected error in incident reports view", exc_info=True)
            messages.error(request, "Something went wrong", "alert alert-danger")
            response = redirect("/dashboard")

        return response


@method_decorator(cache_page(CACHE_TTL_MEDIUM), name='get')
class MasterReportTemplateList(LoginRequiredMixin, View):
    """
    Base class for listing report templates with pagination

    Performance: Cached for CACHE_TTL_MEDIUM (5 minutes) - Added Nov 5, 2025
    """
    model = QuestionSet
    template_path = None
    fields = ["id", "qsetname", "enable"]
    type = None

    def get(self, request, *args, **kwargs):
        """Retrieve paginated list of report templates"""
        resp, R, objects = None, request.GET, QuestionSet.objects.none()
        filtered = None

        if R.get("template"):
            return render(request, self.template_path)

        try:
            objects = QuestionSet.objects.filter(type="SITEREPORT").values(
                "id", "qsetname", "enable"
            )
            count = objects.count()

            if count:
                objects, filtered = utils.get_paginated_results(
                    R, objects, count, self.fields, [], self.model
                )

            filtered = count

            # Use iterator() for memory efficiency when converting to list
            data_list = (
                list(objects.iterator())
                if hasattr(objects, "iterator")
                else list(objects)
            )

            resp = rp.JsonResponse(
                data={
                    "draw": R["draw"],
                    "recordsTotal": count,
                    "data": data_list,
                    "recordsFiltered": filtered,
                },
                status=200,
            )
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError,
                ObjectDoesNotExist, TimeoutError, ValueError, asyncio.CancelledError):
            return redirect("/dashboard")

        return resp


class SiteReportTemplate(MasterReportTemplateList):
    """Site report template listing view"""
    type = QuestionSet.Type.SITEREPORTTEMPLATE
    template_path = "reports/sitereport_template_list.html"


class IncidentReportTemplate(MasterReportTemplateList):
    """Incident report template listing view"""
    type = QuestionSet.Type.INCIDENTREPORTTEMPLATE
    template_path = "reports/incidentreport_template_list.html"


class AttendanceTemplate(LoginRequiredMixin, View):
    """
    Attendance report template and PDF generation view
    """
    PARAMS = {
        "template_normal": "reports/generate_pdf/attendance_template_normal.html",
        "template_form16": "reports/generate_pdf/attendance_template_form16.html",
        "download_template_normal": "reports/generate_pdf/generate_normal_attendance_pdf.html",
        "download_template_form16": "reports/generate_pdf/generate_form16_attendance_pdf.html",
    }

    def get(self, request, *args, **kwargs):
        """Display attendance template based on form type"""
        P, S = self.PARAMS, request.session
        attendance_data = S.get("report_data", {})

        if attendance_data:
            if attendance_data["type_form"] == "NORMAL FORM":
                return render(
                    request, P["template_normal"], {"attendance_data": attendance_data}
                )
            if attendance_data["type_form"] == "FORM 16":
                return render(
                    request, P["template_form16"], {"attendance_data": attendance_data}
                )

    def post(self, request, *args, **kwargs):
        """Generate and download attendance PDF report"""
        P, S = self.PARAMS, request.session
        attendance_data = S.get("report_data", {})

        if not attendance_data:
            return JsonResponse({"success": False, "message": "No Data Found"})

        # Get the appropriate template based on form type
        template_name = self._get_template_name(attendance_data.get("type_form"))
        if not template_name:
            return JsonResponse({"success": False, "message": "Invalid form type"})

        # Generate PDF
        try:
            pdf_response = self._generate_attendance_pdf(
                request, template_name, attendance_data
            )
            return pdf_response
        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError,
                PermissionError, TypeError, ValueError, json.JSONDecodeError,
                requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
            return JsonResponse(
                {"success": False, "message": f"Error generating PDF: {str(e)}"}
            )

    def _get_template_name(self, form_type):
        """Get appropriate template name based on form type"""
        P = self.PARAMS
        if form_type == "NORMAL FORM":
            return P["download_template_normal"]
        elif form_type == "FORM 16":
            return P["download_template_form16"]
        return None

    def _generate_attendance_pdf(self, request, template_name, attendance_data):
        """Generate PDF from attendance data"""
        # Parse attendance data from frontend
        attendance_data_frontend = json.loads(
            request.POST.get("complete_attendance_data", "{}")
        )
        summary_data_frontend = json.loads(request.POST.get("summary_data", "{}"))
        date_time_frontend = request.POST.get("submissionDateTime", "")

        # Transform attendance dictionary into a list for template processing
        for key, employees in attendance_data_frontend.items():
            for emp in employees:
                # Convert attendance dictionary {"day_1": "P", "day_2": "A"} → ["P", "A", ...]
                emp["attendance_list"] = [
                    emp["attendance"].get(f"day_{i}", "") for i in range(1, 32)
                ]

        # Render the template with processed data
        html_string = render_to_string(
            template_name,
            {
                "attendance_data": attendance_data,
                "complete_attendance_data": attendance_data_frontend,
                "summary_data": summary_data_frontend,
                "date_time": date_time_frontend,
            },
            request=request,
        )

        # Create a temporary file for the PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as output:
            pdf_file = output.name

        # Generate PDF using WeasyPrint
        HTML(string=html_string).write_pdf(
            pdf_file,
            stylesheets=[
                CSS(
                    string="""
                    @page {
                        margin: 1cm;
                        size: A4 landscape;
                    }
                """
                )
            ],
        )

        # Return PDF as a downloadable file
        response = FileResponse(
            open(pdf_file, "rb"), content_type="application/pdf"
        )
        response["Content-Disposition"] = 'attachment; filename="Attendance_Report.pdf"'
        return response
