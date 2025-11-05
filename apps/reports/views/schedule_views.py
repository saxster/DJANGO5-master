"""
Report Scheduling Views

Views for scheduling automated email reports and testing report designs.

Extracted from apps/reports/views/generation_views.py
Date: 2025-10-10
"""
from .base import (
    rp,
    render,
    JsonResponse,
    json,
    ValidationError,
    utils,
    log,
    debug_log,
    IntegrationException,
    MasterReportForm,
    LoginRequiredMixin,
    View,
)
import pandas as pd

from apps.reports.models import ScheduleReport


class DesignReport(LoginRequiredMixin, View):
    """Test report design view with multiple rendering options"""
    # change this file according to your design
    design_file = "reports/pdf_reports/testdesign.html"

    def get(self, request):
        R = request.GET  # Presuming you will use this for something later
        if R.get("text") == "html":
            return render(request, self.design_file)
        html_string = render_to_string(self.design_file, request=request)
        # pandoc rendering
        if R.get("text") == "pandoc":
            return self.render_using_pandoc(html_string)
        # excel file
        if R.get("text") == "xl":
            from apps.client_onboarding.models import Bt

            data = Bt.objects.get_sample_data()
            return self.render_excelfile(data)
        # defalult weasyprint
        return self.render_using_weasyprint(html_string)

    def render_using_weasyprint(self, html_string):
        html = HTML(string=html_string)
        # Specify the path to your local CSS file
        css = CSS(filename="frontend/static/assets/css/local/reports.css")
        font_config = FontConfiguration()
        pdf = html.write_pdf(stylesheets=[css], font_config=font_config)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = 'filename="report.pdf"'
        return response

    def render_using_pandoc(self, html_string):
        """
        SECURITY HARDENING: Use temporary directory to prevent file conflicts and race conditions
        """
        import tempfile
        import shutil

        # SECURITY CHECK: Verify pandoc is installed before attempting to use it
        if not shutil.which("pandoc"):
            raise RuntimeError(
                "pandoc not found in system PATH. "
                "Install with: brew install pandoc (macOS) or apt-get install pandoc (Linux)"
            )

        # Use temporary directory with automatic cleanup
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create safe temporary file paths within the temp directory
            temp_html = os.path.join(tmpdir, "temp.html")
            output_pdf = os.path.join(tmpdir, "output.pdf")

            # Write HTML to temporary file
            with open(temp_html, "w", encoding='utf-8') as file:
                file.write(html_string)

            # Specify the path to your local CSS file
            command = [
                "pandoc",
                temp_html,
                "-o",
                output_pdf,
                "--css=frontend/static/assets/css/local/reports.css",
                "--pdf-engine=xelatex",  # Replace with your preferred PDF engine
            ]

            # Run pandoc with timeout to prevent hanging
            try:
                subprocess.run(command, timeout=30, check=True)
            except subprocess.TimeoutExpired:
                raise RuntimeError("PDF generation timed out after 30 seconds")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"pandoc failed with exit code {e.returncode}")

            # Read generated PDF
            with open(output_pdf, "rb") as file:
                pdf = file.read()

            # Temporary files are automatically cleaned up when context exits

        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = 'filename="report.pdf"'

        return response

    def render_excelfile(self, data):
        # Format data as a Pandas DataFrame
        df = pd.DataFrame(list(data))

        # Create a Pandas Excel writer using XlsxWriter as the engine and BytesIO as file-like object
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine="xlsxwriter")
        df.to_excel(writer, sheet_name="Sheet1", index=False, startrow=2, header=True)

        # Get the xlsxwriter workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets["Sheet1"]

        # Autofit the columns to fit the data
        for i, width in enumerate(self.get_col_widths(df)):
            worksheet.set_column(i, i, width)

        # Define the format for the merged cell
        merge_format = workbook.add_format(
            {
                "bg_color": "#c1c1c1",
                "bold": True,
            }
        )

        # Write the additional content with the defined format
        additional_content = (
            "Client: Capgemini,  Report: Task Summary,  From 01-Jan-2023 To 30-Jan-2023"
        )
        worksheet.merge_range("A1:E1", additional_content, merge_format)

        # Close the Pandas Excel writer and output the Excel file
        writer.close()

        # Rewind the buffer
        output.seek(0)

        # Set up the HTTP response with the appropriate Excel headers
        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="downloaded_data.xlsx"'
        return response

    def get_col_widths(self, dataframe):
        """
        Get the maximum width of each column in a Pandas DataFrame.

        DEDUPLICATED (Oct 2025): Delegates to ReportExportService.get_column_widths()
        This method is kept for backward compatibility within DesignReport class.
        """
        from apps.reports.services.report_export_service import ReportExportService
        return ReportExportService.get_column_widths(dataframe)


class ScheduleEmailReport(LoginRequiredMixin, View):
    """Schedule automated email reports with AI insights"""
    P = {
        "template_form": "reports/schedule_email_report.html",
        "template_list": "reports/schedule_email_list.html",
        "form_class": rp_forms.EmailReportForm,
        "popup_form": rp_forms.ReportForm,
        "model": ScheduleReport,
        "ReportEssentials": rutils.ReportEssentials,
        "nodata": "No data found matching your report criteria.\
        Please check your entries and try generating the report again",
    }

    def get(self, request, *args, **kwargs):
        R, S = request.GET, request.session
        if R.get("template"):
            return render(request, self.P["template_list"])

        if R.get("id"):
            obj = utils.get_model_obj(R["id"], request, {"model": self.P["model"]})
            params_initial = obj.report_params
            cxt = {
                "form": self.P["form_class"](instance=obj, request=request),
                "popup_form": self.P["popup_form"](
                    request=request, initial=params_initial
                ),
            }
            return render(request, self.P["template_form"], cxt)

        if R.get("action") == "list":
            data = self.P["model"].objects.filter(bu_id=S["bu_id"]).values().iterator()
            return rp.JsonResponse({"data": list(data)}, status=200)

        if R.get("action") == "form":
            form = self.P["form_class"](request=request)
            form2 = self.P["popup_form"](request=request)
            cxt = {"form": form, "popup_form": form2}
            return render(request, self.P["template_form"], context=cxt)

    def post(self, request, *args, **kwargs):
        from apps.core.utils_new.http_utils import get_clean_form_data, clean_encoded_form_data
        # Use get_clean_form_data for the main form data
        data = get_clean_form_data(request)
        # For report_params, use clean_encoded_form_data directly
        report_params_raw = request.POST.get("report_params", "")
        report_params = clean_encoded_form_data(report_params_raw)
        P = self.P
        try:
            if pk := request.POST.get("pk", None):
                msg = f"updating record with id {pk}"
                form = utils.get_instance_for_update(
                    data, P, msg, int(pk), {"request": request}
                )
            else:
                form = P["form_class"](data, request=request)
            if form.is_valid():
                obj = form.save(commit=False)
                obj = putils.save_userinfo(obj, request.user, request.session)
                obj.report_params = report_params
                obj.save()

                # AI Integration: Trigger insights generation for scheduled reports
                self._schedule_ai_insights(obj, request)

                return rp.JsonResponse({"pk": obj.id}, status=200)
            else:
                cxt = {"errors": form.errors}
                return utils.handle_invalid_form(request, self.P, cxt)
        except IntegrityError as e:
            error_log.error(f"Integrity error occured {e}")
            cxt = {"errors": "Scheduled report with these criteria is already exist"}
            return utils.handle_invalid_form(request, self.P, cxt)

    def _schedule_ai_insights(self, scheduled_report, request):
        """Schedule AI insights generation for reports"""
        try:
            from apps.insights_engine.tasks import generate_automated_report

            # Create or get insight template based on report type
            template_name = f"Auto-Generated {scheduled_report.report_name or 'Report'}"

            # Check if this is a recurring report that should generate insights
            if hasattr(scheduled_report, 'frequency') and scheduled_report.frequency != 'ONCE':
                # For recurring reports, trigger automated insights
                generate_automated_report.delay(
                    template_id=None,  # Will use default template
                    client_id=scheduled_report.client_id,
                    parameters={
                        'report_type': scheduled_report.report_name,
                        'scheduled_report_id': scheduled_report.id,
                        'frequency': getattr(scheduled_report, 'frequency', 'MANUAL'),
                        'report_params': scheduled_report.report_params or {}
                    }
                )

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValidationError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            # Log error but don't fail report scheduling
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to schedule AI insights for report {scheduled_report.id}: {e}")
