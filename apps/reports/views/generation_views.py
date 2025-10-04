"""
Report Generation Views

Views for generating, downloading, and exporting various report types.

Migrated from apps/reports/views.py
Date: 2025-09-30
"""
from .base import *
import pandas as pd
from frappeclient import FrappeClient
from apps.onboarding.models import ScheduleReport


class DownloadReports(LoginRequiredMixin, View):
    """Download and export reports view with async processing"""
    PARAMS = {
        "template_form": "reports/report_export_form.html",
        "form": rp_forms.ReportForm,
        "ReportEssentials": rutils.ReportEssentials,
        "nodata": "No data found matching your report criteria.\
        Please check your entries and try generating the report again",
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.PARAMS
        S = request.session
        if R.get("action") == "form_behaviour":
            return self.form_behaviour(R)

        if R.get("action") == "get_site" and R.get("of_site") and R.get("of_type"):
            qset = (
                on.TypeAssist.objects.filter(
                    bu_id=R["of_site"],
                    client_id=S["client_id"],
                    tatype__tacode=R["of_type"],
                )
                .values("id", "taname")
                .distinct()
            )
            return rp.JsonResponse(data={"options": list(qset)}, status=200)

        if R.get("action") == "get_asset" and R.get("of_type"):
            qset = (
                Asset.objects.filter(
                    client_id=S["client_id"], bu_id=S["bu_id"], type_id=R["of_type"]
                )
                .values("id", "assetname")
                .distinct()
            )
            return rp.JsonResponse(data={"options": list(qset)}, status=200)

        if R.get("action") == "get_qset" and R.get("of_asset"):
            qset = (
                QuestionSet.objects.filter(
                    client_id=S["client_id"],
                    bu_id=S["bu_id"],
                    type__in=["CHECKLIST", "ASSETMAINTENANCE"],
                    parent_id=1,
                    enable=True,
                    assetincludes__contains=[R.get("of_asset")],
                )
                .values("id", "qsetname")
                .distinct()
            )
            return rp.JsonResponse(data={"options": list(qset)}, status=200)

        form = P["form"](request=request)
        cxt = {
            "form": form,
        }
        return render(request, P["template_form"], context=cxt)

    def post(self, request, *args, **kwargs):
        form = self.PARAMS["form"](data=request.POST, request=request)
        log.debug("Form validation result", extra={'is_valid': form.is_valid()})
        if not form.is_valid():
            log.warning("Form validation failed", extra={'errors': form.errors.as_json()})
            return render(request, self.PARAMS["template_form"], {"form": form})
        log.info("form is valid")
        formdata = form.cleaned_data
        log.info(f"Formdata submitted by user: {pformat(formdata)}")

        try:
            return self.export_report(formdata, dict(request.session), request, form)
        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            log.critical("Something went wrong while exporting report", exc_info=True)
            messages.error(request, "Error while exporting report", "alert-danger")
        return render(request, self.PARAMS["template_form"], {"form": form})

    def export_report(self, formdata, session, request, form):
        returnfile = formdata.get("export_type") == "SEND"
        if returnfile:
            messages.success(
                request,
                "Report has been processed for sending on email. You will receive the report shortly.",
                "alert-success",
            )
        else:
            messages.success(
                request,
                "Report has been processed to download. Check status with 'Check Report Status' button",
                "alert-success",
            )
        task_id = create_save_report_async.delay(
            formdata, session["client_id"], request.user.email, request.user.id
        )
        log.info("Report generation task created", extra={'task_id': str(task_id), 'user_id': request.user.id})
        return render(
            request, self.PARAMS["template_form"], {"form": form, "task_id": task_id}
        )

    def form_behaviour(self, R):
        report_essentials = self.PARAMS["ReportEssentials"](
            report_name=R["report_name"]
        )
        return rp.JsonResponse({"behaviour": report_essentials.behaviour_json})


@login_required
def return_status_of_report(request):
    """Check async report generation status and download if ready"""
    if request.method == "GET":
        form = rp_forms.ReportForm(request=request)
        template = "reports/report_export_form.html"
        cxt = {
            "form": form,
        }
        R = request.GET
        task = AsyncResult(R["task_id"])
        if task.status == "SUCCESS":
            result = task.get()
            if result["status"] == 200 and result.get("filepath"):
                if not os.path.exists(result["filepath"]):
                    messages.error(
                        request, "Report file not found on server", "alert-danger"
                    )
                    return render(request, template, cxt)
                else:
                    try:
                        file = open(result["filepath"], "rb")
                        response = FileResponse(file)
                        filename = result["filename"]
                        response[
                            "Content-Disposition"
                        ] = f'attachment; filename="{filename}"'
                        return response
                    finally:
                        remove_reportfile(result["filepath"])
            if result["status"] == 404:
                messages.error(request, result["message"], "alert-danger")
                return render(request, template, cxt)
            if result["status"] == 500:
                messages.error(request, result["message"], "alert-danger")
                return render(request, template, cxt)
            if result["status"] == 201:
                messages.success(request, result["message"], "alert-success")
                return render(request, template, cxt)
        elif task.status == "FAILURE":
            messages.error(
                request,
                "Report generation failed. Please try again later.",
                "alert-danger",
            )
            return render(request, template, cxt)
        else:
            messages.info(request, "Report is still in queue", "alert-info")
            return render(request, template, cxt)


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
            from apps.onboarding.models import Bt

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
        with open("temp.html", "w") as file:
            file.write(html_string)

        # Specify the path to your local CSS file
        command = [
            "pandoc",
            "temp.html",
            "-o",
            "output.pdf",
            "--css=frontend/static/assets/css/local/reports.css",
            "--pdf-engine=xelatex",  # Replace with your preferred PDF engine
        ]
        subprocess.run(command)

        with open("output.pdf", "rb") as file:
            pdf = file.read()

        # Delete the temporary files
        os.remove("temp.html")
        os.remove("output.pdf")

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
        """
        return [
            max([len(str(s)) for s in dataframe[col].values] + [len(col)])
            for col in dataframe.columns
        ]


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


class GeneratePdf(LoginRequiredMixin, View):
    """Generate PDF with highlighted text for compliance documents"""
    PARAMS = {
        "template_form": "reports/generate_pdf/generate_pdf_file.html",
        "form": rp_forms.GeneratePDFForm,
    }

    def get(self, request, *args, **kwargs):
        import uuid

        P = self.PARAMS
        form = P["form"](request=request)
        cxt = {"form": form, "ownerid": uuid.uuid4()}
        return render(request, P["template_form"], context=cxt)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            file_name = data["file_name"]
            page_required = data["page_required"]
            file_path = rutils.find_file(data["file_name"])
            if file_path:
                if data["document_type"] == "PF":
                    uan_list = getAllUAN(
                        data["company"],
                        data["customer"],
                        data["site"],
                        data["period_from"],
                        data["document_type"],
                    )[0]
                elif data["document_type"] == "ESIC":
                    uan_list = getAllUAN(
                        data["company"],
                        data["customer"],
                        data["site"],
                        data["period_from"],
                        data["document_type"],
                    )[1]
                else:
                    people_code = getAllUAN(
                        data["company"],
                        data["customer"],
                        data["site"],
                        data["period_from"],
                        data["document_type"],
                    )[0]
                    people_acc_no = getAllUAN(
                        data["company"],
                        data["customer"],
                        data["site"],
                        data["period_from"],
                        data["document_type"],
                    )[1]
                    uan_list = [people_code, people_acc_no]
                input_pdf_path = file_path
                output_pdf_path = (
                    rutils.trim_filename_from_path(input_pdf_path)
                    + "downloaded_file.pdf"
                )
                if len(uan_list) != 0:
                    highlight_text_in_pdf(
                        input_pdf_path, output_pdf_path, uan_list, page_required
                    )
                    # Generate a response with the PDF file
                    with open(output_pdf_path, "rb") as pdf:
                        pdf_content = pdf.read()
                    response = HttpResponse(pdf_content, content_type="application/pdf")
                    response[
                        "Content-Disposition"
                    ] = f'attachment; filename="Highlighted-{file_name}.pdf"'
                    os.remove(output_pdf_path)
                    return response
                return HttpResponse(str(_("UAN Not Found")), status=404)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)


@csrf_protect_ajax
@rate_limit(max_requests=50, window_seconds=300)
def get_data(request):
    """Get customer and period data from external system"""
    try:
        data = json.loads(request.body.decode("utf-8"))
        if data:
            customer = getCustomer(data["company"])
            period = getPeriod(data["company"])
            if "customer_code" in data:
                site = getCustomersSites(data["company"], data["customer_code"])
                return JsonResponse(
                    {"success": True, "data": [{"name": "", "bu_name": ""}] + site}
                )
            return JsonResponse(
                {
                    "success": True,
                    "data": [{"customer_code": "", "name": ""}] + customer,
                    "period": [{"end_date": "", "name": None, "start_date": ""}]
                    + period,
                }
            )
        else:
            return JsonResponse({"success": False})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


def getClient(company):
    """Get FrappeClient instance for specified company"""
    client = None
    server_url = None
    secerate_key = None
    api_key = None
    if company == "SPS":
        server_url = "http://leave.spsindia.com:8007"
        secerate_key = "c7047cc28b4a14e"
        api_key = "3a6bfc7224a228c"
        client = FrappeClient(server_url, api_key=api_key, api_secret=secerate_key)
    elif company == "SFS":
        server_url = "http://leave.spsindia.com:8008"
        secerate_key = "8dc1421ac748917"
        api_key = "ca9b240aa73a9b8"
        client = FrappeClient(server_url, api_key=api_key, api_secret=secerate_key)
    elif company == "TARGET":
        server_url = "http://leave.spsindia.com:8002"

        client = FrappeClient(server_url, api_key=api_key, api_secret=secerate_key)
    else:
        return None
    client = FrappeClient(server_url, api_key=api_key, api_secret=secerate_key)
    return client


def getCustomer(company):
    """Get customer list from Frappe"""
    filters = {"disabled": 0}
    fields = ["name", "customer_code"]
    frappe_data = get_frappe_data(company, "Customer", filters, fields)
    return frappe_data


def getPeriod(company):
    """Get active payroll periods from Frappe"""
    filters = {"status": "Active"}
    fields = ["name", "start_date", "end_date"]
    frappe_data = get_frappe_data(company, "Salary Payroll Period", filters, fields)
    return frappe_data


def getCustomersSites(company, customer_code):
    """Get sites for specific customer from Frappe"""
    filters = {"status": "Active", "business_unit": customer_code, "bu_type": "Site"}
    fields = ["name", "bu_name"]
    frappe_data = get_frappe_data(company, "Business Unit", filters, fields)
    return frappe_data


def getAllUAN(company, customer_code, site_code, periods, document_type):
    """Get UAN, ESIC, and payroll data from Frappe for specified criteria"""
    # Set filters based on the presence of site_code
    filters = None
    if site_code:
        filters = {
            "customer_code": customer_code,
            "site": site_code,
            "period": ["in", periods],
        }
    else:
        filters = {"customer_code": customer_code, "period": ["in", periods]}

    if document_type == "PAYROLL":
        # Define fields to fetch from Processed Payroll and Difference Processed Payroll
        fields = ["emp_id", "bank_ac_no"]
        client = getClient(company)
        # Fetch data from Processed Payroll
        processed_payroll_emp_list = (
            get_frappe_data(company, "Processed Payroll", filters, fields) or []
        )
        # Prepare a dictionary for easier access to payroll data by emp_id
        payroll_data_map = {row["emp_id"]: row for row in processed_payroll_emp_list}
        # Separate fields into lists
        employee_list = []
        bank_ac_no_list = []
        for payroll_detail in processed_payroll_emp_list:
            employee_list.append(
                payroll_detail.get("emp_id", "").strip()
                if payroll_detail.get("emp_id", "")
                else ""
            )
            bank_ac_no_list.append(
                payroll_detail.get("bank_ac_no", "").strip()
                if payroll_detail.get("bank_ac_no", "")
                else ""
            )
        return (
            employee_list,
            bank_ac_no_list,
        )
    elif document_type == "ATTENDANCE":
        if site_code:
            filters = {
                "customer_code": customer_code,
                "site": site_code,
                "attendance_period": ["in", periods],
            }
        else:
            filters = {
                "customer_code": customer_code,
                "attendance_period": ["in", periods],
            }
        fields = ["attendance_name"]
        client = getClient(company)
        people_attendance_emp_list = (
            get_frappe_data(company, "People Attendance", filters, fields) or []
        )
        filters = {"attendance_name": ["in", people_attendance_emp_list]}
        fields = ["employee", "employee_name", "work_type"]
        client = getClient(company)
        attendance_data = client.get_doc(
            "People Attendance", people_attendance_emp_list[0]["attendance_name"]
        )
        return attendance_data

    else:
        # Define fields to fetch from Processed Payroll and Difference Processed Payroll
        fields = [
            "emp_id",
            "pf_deduction_amount",
            "pf_employee_amount",
            "calcesi",
            "esi_employee",
        ]
        client = getClient(company)

        # Fetch data from Processed Payroll and Difference Processed Payroll
        processed_payroll_emp_list = (
            get_frappe_data(company, "Processed Payroll", filters, fields) or []
        )
        difference_processed_payroll_emp_list = (
            get_frappe_data(company, "Difference Processed Payroll", filters, fields)
            or []
        )

        # Combine the two lists
        combined_payroll_data = (
            processed_payroll_emp_list + difference_processed_payroll_emp_list
        )
        emp_id_list = [row["emp_id"] for row in combined_payroll_data]

        # Fetch UAN data for the filtered employees
        filters = {"name": ["in", emp_id_list]}
        fields = [
            "uan_number",
            "esi_number",
            "employee",
            "bank_ac_no",
            "employee_name",
            "work_type",
        ]
        uan_data = get_frappe_data(company, "Employee", filters, fields) or []

        # Prepare a dictionary for easier access to payroll data by emp_id
        payroll_data_map = {row["emp_id"]: row for row in combined_payroll_data}

        # Separate fields into lists
        uan_list = []
        esic_list = []
        employee_list = []
        bank_ac_no_list = []
        name_list = []
        designation_list = []
        pf_deduction_amount_list = []
        pf_employee_amount_list = []
        calcesi_list = []
        esi_employee_list = []

        for uan_detail in uan_data:
            emp_id = uan_detail.get("employee")
            payroll_data = payroll_data_map.get(emp_id, {})

            # Append data to respective lists
            uan_list.append(
                uan_detail.get("uan_number", "").strip()
                if uan_detail.get("uan_number", "")
                else ""
            )
            esic_list.append(
                uan_detail.get("esi_number", "").strip()
                if uan_detail.get("esi_number", "")
                else ""
            )
            employee_list.append(
                uan_detail.get("employee", "").strip()
                if uan_detail.get("employee", "")
                else ""
            )
            bank_ac_no_list.append(
                uan_detail.get("bank_ac_no", "").strip()
                if uan_detail.get("bank_ac_no", "")
                else ""
            )
            name_list.append(
                uan_detail.get("employee_name", "").strip()
                if uan_detail.get("employee_name", "")
                else ""
            )
            designation_list.append(
                uan_detail.get("work_type", "").strip()
                if uan_detail.get("work_type", "")
                else ""
            )
            pf_deduction_amount_list.append(
                int(payroll_data.get("pf_deduction_amount", 0))
            )
            pf_employee_amount_list.append(
                int(payroll_data.get("pf_employee_amount", 0))
            )
            calcesi_list.append(int(payroll_data.get("calcesi", 0)))
            esi_employee_list.append(int(payroll_data.get("esi_employee", 0)))

        return (
            uan_list,
            esic_list,
            employee_list,
            bank_ac_no_list,
            name_list,
            designation_list,
            pf_deduction_amount_list,
            pf_employee_amount_list,
            calcesi_list,
            esi_employee_list,
        )


def highlight_text_in_pdf(
    input_pdf_path, output_pdf_path, texts_to_highlight, page_required
):
    """Highlight specified texts in PDF and optionally filter pages"""
    import fitz  # PyMuPDF library

    # Open the PDF
    document = fitz.open(input_pdf_path)
    pages_to_keep = []
    orange_color = (1, 0.647, 0)  # RGB values for orange

    # Normalize the texts_to_highlight to a flat list
    if any(isinstance(item, list) for item in texts_to_highlight):
        normalized_texts_to_highlight = [
            text for sublist in texts_to_highlight for text in sublist
        ]
    else:
        normalized_texts_to_highlight = texts_to_highlight

    # Function to handle text splitting
    def find_and_highlight_text(page, text):
        """Search for text and highlight it if not already highlighted."""
        words = page.get_text("words")  # Extract words as bounding boxes
        existing_highlights = page.annots()  # Get existing annotations on the page

        # Helper function to check if a bounding box overlaps with existing highlights
        def is_already_highlighted(bbox):
            if not existing_highlights:
                return False
            for annot in existing_highlights:
                if annot.rect.intersects(fitz.Rect(bbox)):
                    return True
            return False

        for i, word in enumerate(words):
            if text.startswith(word[4]):
                combined_text = word[4]
                bbox = [word[:4]]  # Collect bounding boxes
                j = i + 1

                # Try to combine subsequent words
                while j < len(words) and not combined_text == text:
                    combined_text += words[j][4]
                    bbox.append(words[j][:4])
                    j += 1

                if combined_text == text:
                    # Highlight only if not already highlighted
                    if not any(is_already_highlighted(box) for box in bbox):
                        for box in bbox:
                            highlight = page.add_highlight_annot(fitz.Rect(box))
                            highlight.set_colors(
                                stroke=orange_color
                            )  # Set highlight color
                            highlight.update()
                        return True
        return False

    # Check and highlight text on each page
    for page_num in range(document.page_count):
        page = document[page_num]
        page_has_highlight = False
        for text in normalized_texts_to_highlight:
            if text and find_and_highlight_text(page, text):
                page_has_highlight = True

        # Logic to determine whether to keep the page
        if page_required:
            if page_has_highlight or page_num == 0:  # Always keep the first page
                pages_to_keep.append(page_num)
        else:
            if (
                page_has_highlight
                or page_num == 0
                or page_num == document.page_count - 1
            ):  # Keep first, last, and highlighted pages
                pages_to_keep.append(page_num)

    # Create a new document with all pages to be kept
    new_document = fitz.open()
    for page_num in pages_to_keep:
        new_document.insert_pdf(document, from_page=page_num, to_page=page_num)

    # Save the updated PDF
    new_document.save(output_pdf_path)
    new_document.close()
    document.close()


def get_frappe_data(company, document_type, filters, fields):
    """Get paginated data from Frappe with specified filters"""
    client = getClient(company)
    all_frappe_data = []
    if client:
        start = 0
        limit = 100
        while True:
            frappe_data = client.get_list(
                document_type,
                filters=filters,
                fields=fields,
                limit_start=start,
                limit_page_length=limit,
            )
            if not frappe_data:
                break
            all_frappe_data.extend(frappe_data)
            start += limit
        return all_frappe_data


# SECURE REPLACEMENT: This function has been replaced with a secure implementation
# to prevent path traversal attacks (CVSS 9.1). The original vulnerable code
# is preserved in comments for reference during security reviews.

# VULNERABLE CODE (REMOVED):
# - Direct path concatenation: f"{home_dir}/{foldertype}/"
# - No filename sanitization: people_id + "-" + filename
# - Generic exception handling: except Exception as e
# - No authentication/authorization checks
# - No file type validation

def upload_pdf(request):
    """
    SECURE REPLACEMENT for vulnerable upload_pdf function.

    This function now delegates to the SecureReportUploadService which provides:
    - Comprehensive path traversal prevention
    - Filename sanitization and validation
    - Authentication and authorization checks
    - Specific exception handling
    - File content validation
    - Comprehensive security logging

    Complies with Rules #3, #11, and #14 from .claude/rules.md
    """
    # Import here to avoid circular imports
    from apps.reports.services.secure_report_upload_service import secure_upload_pdf

    # Delegate to secure implementation
    return secure_upload_pdf(request)


class GenerateLetter(LoginRequiredMixin, View):
    """Generate employment verification letter with payroll data"""
    PARAMS = {
        "template_form": "reports/generate_pdf/generate_letter.html",
        "form": rp_forms.GeneratePDFForm,
    }

    def get(self, request, *args, **kwargs):
        import uuid

        P = self.PARAMS
        form = P["form"](request=request)
        cxt = {"form": form, "ownerid": uuid.uuid4()}
        return render(request, P["template_form"], context=cxt)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            person_data = {}
            person_data["uan_list"] = getAllUAN(
                data["company"],
                data["customer"],
                data["site"],
                data["period_from"],
                "PF",
            )[0]
            person_data["esic_list"] = getAllUAN(
                data["company"],
                data["customer"],
                data["site"],
                data["period_from"],
                "PF",
            )[1]
            person_data["employee_list"] = getAllUAN(
                data["company"],
                data["customer"],
                data["site"],
                data["period_from"],
                "PF",
            )[2]
            person_data["name_list"] = getAllUAN(
                data["company"],
                data["customer"],
                data["site"],
                data["period_from"],
                "PF",
            )[4]
            person_data["designation_list"] = getAllUAN(
                data["company"],
                data["customer"],
                data["site"],
                data["period_from"],
                "PF",
            )[5]
            person_data["pf_deduction_amount_list"] = getAllUAN(
                data["company"],
                data["customer"],
                data["site"],
                data["period_from"],
                "PF",
            )[6]
            person_data["pf_employee_amount_list"] = getAllUAN(
                data["company"],
                data["customer"],
                data["site"],
                data["period_from"],
                "PF",
            )[7]
            person_data["calcesi_list"] = getAllUAN(
                data["company"],
                data["customer"],
                data["site"],
                data["period_from"],
                "PF",
            )[8]
            person_data["esi_employee_list"] = getAllUAN(
                data["company"],
                data["customer"],
                data["site"],
                data["period_from"],
                "PF",
            )[9]
            from django.http import HttpResponse
            from weasyprint import HTML
            from django.template.loader import render_to_string

            if len(person_data) != 0:
                html_string = render_to_string(
                    "/reports/generate_pdf/letterpad_template.html",
                    {
                        "Customer": data["customerName"],
                        "Site": data["siteName"],
                        "YearMonth": data["period_from"][0],
                        "PFCodeNo": data["pf_code_no"],
                        "ESICCodeNo": data["esic_code_no"],
                        "table_data": person_data,
                        "Company": data["company"],
                    },
                )

            # Convert HTML to PDF
            pdf = HTML(string=html_string).write_pdf()

            # Send the PDF as a downloadable response
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = "attachment; filename=letterpad.pdf"
            return response

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)


class GenerateAttendance(LoginRequiredMixin, View):
    """Generate attendance reports from external ERP system"""
    PARAMS = {
        "template_form": "reports/generate_pdf/generateattendance.html",
        "form": rp_forms.GeneratePDFForm,
    }

    def get(self, request, *args, **kwargs):
        import uuid

        P = self.PARAMS
        form = P["form"](request=request)
        cxt = {"form": form, "ownerid": uuid.uuid4()}
        return render(request, P["template_form"], context=cxt)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            site_attendance_data = {}
            if data["company"] == "SPS":
                server_url = "http://leave.spsindia.com:8007"
            elif data["company"] == "SFS":
                server_url = "http://leave.spsindia.com:8008"
            elif data["company"] == "TARGET":
                server_url = "http://leave.spsindia.com:8002"
            else:
                return None

            import requests
            from urllib.parse import urljoin, urlencode

            # API endpoint
            endpoint = "/api/method/sps.sps.api.getERPNextPostingData"
            # Query parameters
            if data["site"]:
                params = {
                    "period": data["period_from"][0],
                    "customer": data["customerName"],
                    "site": data["site"],
                }
            else:
                params = {
                    "period": data["period_from"][0],
                    "customer": data["customerName"],
                }
            # Construct the full URL
            url = urljoin(server_url, endpoint) + "?" + urlencode(params)
            # Make the GET request
            try:
                response = requests.get(url, timeout=(5, 15))
                # Check if the request was successful (status code 200)
                if response.status_code == 200:
                    # Parse the response (assuming it's JSON)
                    resp_data = response.json()
                    output_data = {"message": {}}
                    for key, entries in resp_data["message"].items():
                        transformed_entry = {}
                        employee_details = []
                        for entry in entries:
                            employee_details.append(
                                {
                                    "employee": entry["employee"],
                                    "employee_name": entry["employee_name"],
                                    "work_type": entry["work_type"],
                                }
                            )
                            # Copy non-employee specific fields once
                            if not transformed_entry:
                                transformed_entry = {
                                    k: v
                                    for k, v in entry.items()
                                    if k
                                    not in ["employee", "employee_name", "work_type"]
                                }
                        transformed_entry["employee_details"] = employee_details
                        output_data["message"][key] = [transformed_entry]

                    site_attendance_data["site_attendance_data"] = output_data[
                        "message"
                    ]
                    site_attendance_data["period"] = data["period_from"][0]
                    site_attendance_data["type_form"] = data["type_form"]
                    if site_attendance_data["site_attendance_data"]:
                        request.session["report_data"] = site_attendance_data
                        return JsonResponse(
                            {
                                "success": True,
                                "message": "Report generated successfully!",
                            }
                        )
                    else:
                        return JsonResponse(
                            {"success": False, "message": "No Data Found"}
                        )
                else:
                    # Handle errors
                    error_log.error(
                        f"Failed to fetch data. Status code: {response.status_code}"
                    )
                    error_log.error(f"Response: {response.text}")
            except requests.exceptions.RequestException as e:
                # Handle exceptions (e.g., network issues)
                error_log.error(f"An error occurred: {e}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)


class GenerateDecalartionForm(LoginRequiredMixin, View):
    """Generate employee declaration form with payroll data"""
    PARAMS = {
        "template_form": "reports/generate_pdf/generate_declaration_form.html",
        "form": rp_forms.GeneratePDFForm,
    }

    def get(self, request, *args, **kwargs):
        import uuid

        P = self.PARAMS
        form = P["form"](request=request)
        cxt = {"form": form, "ownerid": uuid.uuid4()}
        return render(request, P["template_form"], context=cxt)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            get_client = getClient("SPS")
            doc_employee_detail = get_client.get_list(
                "Employee", filters={"name": data["ticket_no"]}
            )
            doc_payroll_detail = get_client.get_list(
                "Processed Payroll", filters={"emp_id": data["ticket_no"]}
            )

            import pandas as pd

            # Load the Excel file
            file_path = "/home/pankaj/Pankaj/codebase (1)/JNPT LEAVE BONUS SAL DATA AUG -DEC 2024.xls"  # Change this to your actual file path
            df = pd.read_excel(file_path)

            # Find the matching row
            matched_row = df[df["Row Labels"] == data["ticket_no"]]

            # Fetch required columns
            if not matched_row.empty:
                row_data = matched_row[
                    [
                        "Row Labels",
                        "Name",
                        "Sum of Bonus Amt",
                        "Leave amt",
                        "Dec 24 net pay",
                        "MLWF",
                        "PF AMT",
                    ]
                ]
            if str(doc_payroll_detail[0]["net_pay"]).endswith(".0"):
                result = str(doc_payroll_detail[0]["net_pay"]).split(".")[0]
            else:
                result = str(doc_payroll_detail[0]["net_pay"])
            date_str = str(doc_employee_detail[0]["date_of_joining"])
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_from_date = date_obj.strftime("%b-%y").upper()
            from django.http import HttpResponse
            from weasyprint import HTML
            from django.template.loader import render_to_string

            if len(doc_employee_detail) != 0 and len(doc_payroll_detail) != 0:
                html_string = render_to_string(
                    "/reports/generate_pdf/declaration_form_template.html",
                    {
                        "FullName": doc_employee_detail[0]["employee_name"],
                        "FatherName": doc_employee_detail[0]["father_name"],
                        "CurrentAddress": doc_employee_detail[0]["current_address"],
                        "BankACNo": doc_employee_detail[0]["bank_ac_no"],
                        "BankBranch": doc_employee_detail[0]["bank_branch"],
                        "BankIFSCCode": doc_employee_detail[0]["bank_ifsc_code"],
                        "FromDate": formatted_from_date,
                        "ToDate": "DEC-24",
                        "CompanyName": doc_employee_detail[0]["company"],
                        "NetPay": row_data["Dec 24 net pay"].values[0],
                        "Bonus": row_data["Sum of Bonus Amt"].values[0],
                        "Leave": row_data["Leave amt"].values[0],
                        "MLWF": row_data["MLWF"].values[0],
                        "PFAMT": row_data["PF AMT"].values[0]
                        if not pd.isna(row_data["PF AMT"].values[0])
                        else "NILL",
                    },
                )

            # Convert HTML to PDF
            pdf = HTML(string=html_string).write_pdf()

            # Send the PDF as a downloadable response
            response = HttpResponse(pdf, content_type="application/pdf")
            response[
                "Content-Disposition"
            ] = "attachment; filename=declaration_form.pdf"
            return response

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
