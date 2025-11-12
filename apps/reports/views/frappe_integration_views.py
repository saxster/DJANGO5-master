"""
Modernized ERP integration views.

Only the endpoints that still power the attendance workflow remain.
All Frappe data access now goes through apps.reports.services.frappe_service.
"""

from urllib.parse import urljoin, urlencode

import requests

from .base import (
    render,
    JsonResponse,
    LoginRequiredMixin,
    View,
    ValidationError,
    json,
    csrf_protect_ajax,
    rate_limit,
    rp_forms,
    error_log,
)
from apps.reports.services.frappe_service import (
    get_frappe_service,
    FrappeCompany,
    FrappeServiceException,
)


def _parse_company(company_code: str) -> FrappeCompany:
    try:
        return FrappeCompany(company_code)
    except ValueError as exc:
        raise ValidationError(f"Unsupported company '{company_code}'") from exc


@csrf_protect_ajax
@rate_limit(max_requests=50, window_seconds=300)
def get_data(request):
    """
    Fetch customer, period, and site metadata from Frappe/ERPNext.
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not payload:
        return JsonResponse({"success": False})

    company = payload.get("company")
    if not company:
        return JsonResponse({"error": "Company is required"}, status=400)

    try:
        company_enum = _parse_company(company)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    frappe_service = get_frappe_service()

    try:
        if payload.get("customer_code"):
            sites = frappe_service.get_customer_sites(
                company_enum, payload["customer_code"]
            ) or []
            return JsonResponse(
                {"success": True, "data": [{"name": "", "bu_name": ""}] + sites}
            )

        customers = frappe_service.get_customers(company_enum) or []
        periods = frappe_service.get_periods(company_enum) or []
    except FrappeServiceException as exc:
        error_log.error("Failed to fetch Frappe metadata: %s", exc)
        return JsonResponse({"error": "Unable to fetch ERP data"}, status=503)

    return JsonResponse(
        {
            "success": True,
            "data": [{"customer_code": "", "name": ""}] + customers,
            "period": [{"end_date": "", "name": None, "start_date": ""}] + periods,
        }
    )


class GenerateAttendance(LoginRequiredMixin, View):
    """Generate attendance reports from external ERP system."""

    PARAMS = {
        "template_form": "reports/generate_pdf/generateattendance.html",
        "form": rp_forms.GeneratePDFForm,
    }

    def get(self, request, *args, **kwargs):
        import uuid

        form = self.PARAMS["form"](request=request)
        cxt = {"form": form, "ownerid": uuid.uuid4()}
        return render(request, self.PARAMS["template_form"], context=cxt)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        site_attendance_data = {}
        company = data.get("company")

        if company == "SPS":
            server_url = "http://leave.spsindia.com:8007"
        elif company == "SFS":
            server_url = "http://leave.spsindia.com:8008"
        elif company == "TARGET":
            server_url = "http://leave.spsindia.com:8002"
        else:
            return JsonResponse({"error": "Unsupported company"}, status=400)

        endpoint = "/api/method/sps.sps.api.getERPNextPostingData"
        if data.get("site"):
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

        url = urljoin(server_url, endpoint) + "?" + urlencode(params)

        try:
            response = requests.get(url, timeout=(5, 15))
        except requests.RequestException as exc:
            error_log.error("Attendance API request failed: %s", exc)
            return JsonResponse(
                {"success": False, "message": "Unable to contact ERP server"}
            )

        if response.status_code != 200:
            error_log.error(
                "Attendance API failure (%s): %s", response.status_code, response.text
            )
            return JsonResponse(
                {"success": False, "message": "Failed to fetch attendance data"}
            )

        resp_data = response.json()
        output_data = {"message": {}}
        for key, entries in resp_data.get("message", {}).items():
            transformed_entry = {}
            employee_details = []
            for entry in entries:
                employee_details.append(
                    {
                        "employee": entry.get("employee"),
                        "employee_name": entry.get("employee_name"),
                        "work_type": entry.get("work_type"),
                    }
                )
                if not transformed_entry:
                    transformed_entry = {
                        k: v
                        for k, v in entry.items()
                        if k not in {"employee", "employee_name", "work_type"}
                    }
            transformed_entry["employee_details"] = employee_details
            output_data["message"][key] = [transformed_entry]

        site_attendance_data["site_attendance_data"] = output_data["message"]
        site_attendance_data["period"] = data["period_from"][0]
        site_attendance_data["type_form"] = data["type_form"]

        if site_attendance_data["site_attendance_data"]:
            request.session["report_data"] = site_attendance_data
            return JsonResponse(
                {"success": True, "message": "Report generated successfully!"}
            )

        return JsonResponse({"success": False, "message": "No Data Found"})


__all__ = ["get_data", "GenerateAttendance"]
