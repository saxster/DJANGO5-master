"""
RESTful URL Configuration for Reports App

Removes verb prefixes, uses HTTP methods for actions.
Follows URL_STANDARDS.md conventions.

Migration from legacy reports/urls.py (Phase 2 - October 2025)
"""

from django.urls import path
from apps.reports import views

app_name = "reports"

urlpatterns = [
    # ========== SITE REPORTS ==========
    # RESTful resource: /reports/site-reports/

    # List all site reports
    path('site-reports/', views.RetriveSiteReports.as_view(), name='site-report-list'),

    # Site report templates
    path('site-reports/templates/', views.SiteReportTemplateForm.as_view(), name='site-report-template-list'),
    path('site-reports/templates/configure/', views.ConfigSiteReportTemplate.as_view(), name='site-report-template-configure'),
    path('site-reports/templates/<int:template_id>/', views.SiteReportTemplateForm.as_view(), name='site-report-template-detail'),

    # ========== INCIDENT REPORTS ==========
    # RESTful resource: /reports/incident-reports/

    # List all incident reports
    path('incident-reports/', views.RetriveIncidentReports.as_view(), name='incident-report-list'),

    # Incident report templates
    path('incident-reports/templates/', views.IncidentReportTemplate.as_view(), name='incident-report-template-list'),
    path('incident-reports/templates/configure/', views.ConfigIncidentReportTemplate.as_view(), name='incident-report-template-configure'),
    path('incident-reports/templates/form/', views.IncidentReportTemplateForm.as_view(), name='incident-report-template-form'),

    # ========== WORK PERMIT REPORTS ==========
    # RESTful resource: /reports/work-permits/

    path('work-permits/templates/configure/', views.ConfigWorkPermitReportTemplate.as_view(), name='work-permit-template-configure'),

    # ========== REPORT GENERATION ==========
    # Use HTTP POST for generation actions

    # Generate PDF report (POST action)
    path('pdf/generate/', views.GeneratePdf.as_view(), name='pdf-generate'),
    path('pdf/data/', views.get_data, name='pdf-data'),  # Get data for PDF generation
    path('pdf/upload/', views.upload_pdf, name='pdf-upload'),  # Upload generated PDF

    # Generate letter (POST action)
    path('letters/generate/', views.GenerateLetter.as_view(), name='letter-generate'),

    # Generate attendance report (POST action)
    path('attendance/generate/', views.GenerateAttendance.as_view(), name='attendance-generate'),
    path('attendance/templates/', views.AttendanceTemplate.as_view(), name='attendance-template'),

    # Generate declaration form (POST action)
    path('declaration-forms/generate/', views.GenerateDecalartionForm.as_view(), name='declaration-form-generate'),

    # ========== REPORT EXPORT ==========
    # Use HTTP GET with format parameter or separate endpoints

    # Export reports (GET with format parameter: ?format=pdf|excel|csv)
    path('export/', views.DownloadReports.as_view(), name='report-export'),

    # Check report status (for async generation)
    path('status/<str:report_id>/', views.return_status_of_report, name='report-status'),

    # ========== REPORT CONFIGURATION ==========

    # Master report belongings (question sets)
    path('config/belongings/', views.MasterReportBelonging.as_view(), name='report-belongings'),

    # Report design/customization
    path('design/', views.DesignReport.as_view(), name='report-design'),

    # ========== SCHEDULED REPORTS ==========
    # Email report scheduling

    path('schedule/email/', views.ScheduleEmailReport.as_view(), name='schedule-email-report'),

    # ========== LEGACY COMPATIBILITY ==========
    # Keep old URL patterns for backward compatibility (6 months)

    # Legacy verb-based URLs
    path('get_reports/', views.DownloadReports.as_view(), name='exportreports_legacy'),  # Was: exportreports
    path('get_report_status/', views.return_status_of_report, name='report_status_legacy'),
    path('generatepdf/', views.GeneratePdf.as_view(), name='generatepdf_legacy'),
    path('generatepdf-getdata/', views.get_data, name='generatepdf-getdata_legacy'),
    path('upload-pdf/', views.upload_pdf, name='upload-pdf_legacy'),
    path('generateletter/', views.GenerateLetter.as_view(), name='generateletter_legacy'),
    path('generateattendance/', views.GenerateAttendance.as_view(), name='generateattendance_legacy'),
    path('generate_declaration_form/', views.GenerateDecalartionForm.as_view(), name='generate_declaration_form_legacy'),

    # Legacy list URLs
    path('sitereport_list/', views.RetriveSiteReports.as_view(), name='sitereport_list_legacy'),
    path('incidentreport_list/', views.RetriveIncidentReports.as_view(), name='incidentreport_list_legacy'),

    # Legacy template URLs
    path('sitereport_template/', views.ConfigSiteReportTemplate.as_view(), name='config_sitereport_template_legacy'),
    path('incidentreport_template/', views.ConfigIncidentReportTemplate.as_view(), name='config_incidentreport_template_legacy'),
    path('workpermitreport_template/', views.ConfigWorkPermitReportTemplate.as_view(), name='config_workpermitreport_template_legacy'),
    path('incidentreport_temp_list/', views.IncidentReportTemplate.as_view(), name='incidentreport_template_list_legacy'),
    path('sitereport_temp_form/', views.SiteReportTemplateForm.as_view(), name='sitereport_template_form_legacy'),
    path('incidentreport_temp_form/', views.IncidentReportTemplateForm.as_view(), name='incident_template_form_legacy'),
    path('attendance_template/', views.AttendanceTemplate.as_view(), name='attendance_template_legacy'),

    # Legacy config URLs
    path('srqsetbelonging/', views.MasterReportBelonging.as_view(), name='srqsetbelonging_legacy'),
    path('design/', views.DesignReport.as_view(), name='design_legacy'),
    path('schedule-email-report/', views.ScheduleEmailReport.as_view(), name='schedule_email_report_legacy'),
]

# ========== URL MIGRATION NOTES ==========
"""
Legacy → RESTful Migration:

VERB REMOVAL (Actions use HTTP methods):
    OLD: GET  /reports/get_reports/             → NEW: GET  /reports/export/
    OLD: GET  /reports/generatepdf/             → NEW: POST /reports/pdf/generate/
    OLD: POST /reports/upload-pdf/              → NEW: POST /reports/pdf/upload/
    OLD: GET  /reports/generateletter/          → NEW: POST /reports/letters/generate/
    OLD: GET  /reports/generateattendance/      → NEW: POST /reports/attendance/generate/
    OLD: GET  /reports/generate_declaration_form/ → NEW: POST /reports/declaration-forms/generate/

NAMING STANDARDIZATION (Hyphens, consistent plurals):
    OLD: /reports/sitereport_list/              → NEW: /reports/site-reports/
    OLD: /reports/incidentreport_list/          → NEW: /reports/incident-reports/
    OLD: /reports/sitereport_template/          → NEW: /reports/site-reports/templates/configure/
    OLD: /reports/srqsetbelonging/              → NEW: /reports/config/belongings/
    OLD: /reports/schedule-email-report/        → NEW: /reports/schedule/email/

HTTP METHOD USAGE:
    GET requests:
        - List resources: GET /reports/site-reports/
        - View detail: GET /reports/site-reports/{id}/
        - Export data: GET /reports/export/?format=pdf

    POST requests:
        - Create resource: POST /reports/site-reports/
        - Generate report: POST /reports/pdf/generate/
        - Upload file: POST /reports/pdf/upload/

    PUT/PATCH requests:
        - Update resource: PUT /reports/site-reports/{id}/

    DELETE requests:
        - Delete resource: DELETE /reports/site-reports/{id}/

QUERY PARAMETERS (Instead of URL paths):
    OLD: /reports/get_reports/pdf/
    NEW: /reports/export/?format=pdf

    OLD: /reports/get_reports/excel/
    NEW: /reports/export/?format=excel

    OLD: /reports/get_report_status/123/
    NEW: /reports/status/123/

ASYNC REPORT GENERATION PATTERN:
    1. Request generation:
       POST /reports/pdf/generate/
       Response: {"report_id": "abc123", "status": "processing"}

    2. Check status:
       GET /reports/status/abc123/
       Response: {"status": "completed", "download_url": "/reports/download/abc123/"}

    3. Download:
       GET /reports/download/abc123/
       Response: <PDF file>

API RESPONSE EXAMPLE (With HATEOAS):
    {
        "id": 123,
        "name": "Site Visit Report - 2025-10",
        "type": "site_visit",
        "status": "completed",
        "created_at": "2025-10-11T14:30:00Z",
        "generated_by": "john.doe",
        "_links": {
            "self": "/reports/site-reports/123/",
            "download": "/reports/export/?id=123&format=pdf",
            "regenerate": "/reports/pdf/generate/",
            "template": "/reports/site-reports/templates/45/"
        }
    }

DEPRECATION TIMELINE:
    - Legacy URLs active: Until Q2 2026
    - Deprecation notices: Start Q1 2026
    - Removal: Q2 2026 (HTTP 410 Gone)

For more information:
    - URL Standards: URL_STANDARDS.md
    - Migration Guide: URL_MIGRATION_GUIDE.md
    - API Documentation: /api/schema/redoc/
    - Support: #backend-dev on Slack
"""
