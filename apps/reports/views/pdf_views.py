"""
PDF Generation Views

Views for generating, highlighting, and manipulating PDF documents.

Extracted from apps/reports/views/generation_views.py
Date: 2025-10-10
"""
from .base import *
import pandas as pd

# Import centralized Frappe ERP service (Oct 2025 - technical debt elimination)
from apps.reports.services.frappe_service import (
    FrappeService,
    get_frappe_service,
    FrappeCompany,
    PayrollDocumentType,
    FrappeServiceException
)

# Backward compatibility wrappers (DEPRECATED - Oct 2025)
from .frappe_integration_views import getAllUAN

# Import PDF utilities (and re-export for backward compatibility)
from apps.reports.report_utils.pdf_utils import highlight_text_in_pdf

# Re-export for backward compatibility
__all__ = ['GeneratePdf', 'GenerateLetter', 'GenerateDecalartionForm', 'highlight_text_in_pdf']


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
            # Import wrapper for backward compatibility
            from .frappe_integration_views import getClient
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
