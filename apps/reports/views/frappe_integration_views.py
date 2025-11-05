"""
Frappe/ERPNext ERP Integration Views

Views and endpoints for integrating with external ERP systems (Frappe/ERPNext).

Extracted from apps/reports/views/generation_views.py
Date: 2025-10-10
"""
from .base import (
    rp,
    render,
    ValidationError,
    json,
    utils,
    log,
    debug_log,
    IntegrationException,
    MasterReportForm,
)
import pandas as pd

# Optional ERP integration - only needed for specific report types
try:
    from frappeclient import FrappeClient
    FRAPPE_AVAILABLE = True
except ImportError:
    FrappeClient = None
    FRAPPE_AVAILABLE = False
    import logging
    logger = logging.getLogger(__name__)
    logger.info("frappeclient not installed - ERP integration features disabled")

# Import centralized Frappe ERP service (Oct 2025 - technical debt elimination)
from apps.reports.services.frappe_service import (
    FrappeService,
    get_frappe_service,
    FrappeCompany,
    PayrollDocumentType,
    FrappeServiceException
)


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


# ============================================================================
# BACKWARD COMPATIBILITY WRAPPERS (DEPRECATED - Oct 2025)
# These functions delegate to the new FrappeService.
# Will be removed in 2 sprints (target: 2025-12-10)
# ============================================================================

def getClient(company: str):
    """
    Get FrappeClient instance for specified company.

    DEPRECATED: Use FrappeService.get_client() instead.
    This wrapper is for backward compatibility only.

    Args:
        company: Company code string (e.g., "SPS", "SFS", "TARGET")

    Returns:
        FrappeClient instance or None
    """
    import warnings
    warnings.warn(
        "getClient() is deprecated. Use FrappeService.get_client() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    try:
        frappe_service = get_frappe_service()
        company_enum = FrappeCompany(company)
        return frappe_service.get_client(company_enum)
    except (ValueError, FrappeServiceException) as e:
        logger.error(f"Failed to get Frappe client for {company}: {e}")
        return None


def getCustomer(company: str):
    """
    Get customer list from Frappe.

    DEPRECATED: Use FrappeService.get_customers() instead.
    """
    import warnings
    warnings.warn(
        "getCustomer() is deprecated. Use FrappeService.get_customers() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    try:
        frappe_service = get_frappe_service()
        company_enum = FrappeCompany(company)
        return frappe_service.get_customers(company_enum)
    except (ValueError, FrappeServiceException) as e:
        logger.error(f"Failed to get customers for {company}: {e}")
        return []


def getPeriod(company: str):
    """
    Get active payroll periods from Frappe.

    DEPRECATED: Use FrappeService.get_periods() instead.
    """
    import warnings
    warnings.warn(
        "getPeriod() is deprecated. Use FrappeService.get_periods() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    try:
        frappe_service = get_frappe_service()
        company_enum = FrappeCompany(company)
        return frappe_service.get_periods(company_enum)
    except (ValueError, FrappeServiceException) as e:
        logger.error(f"Failed to get periods for {company}: {e}")
        return []


def getCustomersSites(company: str, customer_code: str):
    """
    Get sites for specific customer from Frappe.

    DEPRECATED: Use FrappeService.get_customer_sites() instead.
    """
    import warnings
    warnings.warn(
        "getCustomersSites() is deprecated. Use FrappeService.get_customer_sites() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    try:
        frappe_service = get_frappe_service()
        company_enum = FrappeCompany(company)
        return frappe_service.get_customer_sites(company_enum, customer_code)
    except (ValueError, FrappeServiceException) as e:
        logger.error(f"Failed to get customer sites for {company}: {e}")
        return []


def getAllUAN(company: str, customer_code: str, site_code: str, periods: list, document_type: str):
    """
    Get UAN, ESIC, and payroll data from Frappe for specified criteria.

    DEPRECATED: Use FrappeService.get_payroll_data() instead.
    """
    import warnings
    warnings.warn(
        "getAllUAN() is deprecated. Use FrappeService.get_payroll_data() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    try:
        frappe_service = get_frappe_service()
        company_enum = FrappeCompany(company)
        doc_type_enum = PayrollDocumentType(document_type)
        return frappe_service.get_payroll_data(
            company=company_enum,
            customer_code=customer_code,
            site_code=site_code,
            periods=periods,
            document_type=doc_type_enum
        )
    except (ValueError, FrappeServiceException) as e:
        logger.error(f"Failed to get payroll data for {company}: {e}")
        # Return empty tuples matching expected structure
        return ([], [], [], [], [], [], [], [], [], [])


def get_frappe_data(company: str, document_type: str, filters: dict, fields: list):
    """
    Get paginated data from Frappe with specified filters.

    DEPRECATED: Use FrappeService.get_paginated_data() instead.
    """
    import warnings
    warnings.warn(
        "get_frappe_data() is deprecated. Use FrappeService.get_paginated_data() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    try:
        frappe_service = get_frappe_service()
        company_enum = FrappeCompany(company)
        return frappe_service.get_paginated_data(
            company=company_enum,
            document_type=document_type,
            filters=filters,
            fields=fields
        )
    except (ValueError, FrappeServiceException) as e:
        logger.error(f"Failed to get Frappe data for {company}/{document_type}: {e}")
        return []


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
