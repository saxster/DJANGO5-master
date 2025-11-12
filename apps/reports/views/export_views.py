"""
Report Export Views

Views for exporting and downloading reports with async processing.

Extracted from apps/reports/views/generation_views.py
Date: 2025-10-10
"""
from .base import (
    rp,
    render,
    redirect,
    json,
    utils,
    log,
    debug_log,
    IntegrationException,
    MasterReportForm,
    ValidationError,
    LoginRequiredMixin,
    View,
    rp_forms,
    rutils,
    on_core,
    Asset,
    QuestionSet,
    messages,
    IntegrityError,
    DatabaseError,
    ObjectDoesNotExist,
    asyncio,
    create_save_report_async,
    AsyncResult,
    pformat,
    login_required,
)


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
                on_core.TypeAssist.objects.filter(
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
    """
    Check async report generation status and download if ready.
    
    SECURITY: Uses SecureFileDownloadService for path validation and permission checks.
    Complies with Rule #14 from .claude/rules.md - File Download Security
    """
    if request.method == "GET":
        from apps.core.services.secure_file_download_service import SecureFileDownloadService
        from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
        from django.http import Http404
        
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
                try:
                    # SECURITY: Use SecureFileDownloadService for comprehensive validation
                    response = SecureFileDownloadService.validate_and_serve_file(
                        filepath=result["filepath"],
                        filename=result.get("filename", "report.pdf"),
                        user=request.user,
                        owner_id=None  # Report files are user-specific, validated via staff check
                    )
                    
                    # Schedule file cleanup after download completes (async)
                    from apps.reports.tasks import schedule_report_cleanup
                    schedule_report_cleanup.apply_async(
                        args=[result["filepath"]],
                        countdown=300  # Delete after 5 minutes (enough time for download)
                    )
                    
                    log.info(
                        "Report file download initiated",
                        extra={
                            'user_id': request.user.id,
                            'task_id': R["task_id"],
                            'filename': result.get("filename")
                        }
                    )
                    
                    return response
                    
                except (PermissionDenied, SuspiciousFileOperation) as e:
                    log.error(
                        "Security violation during report download",
                        extra={
                            'user_id': request.user.id,
                            'task_id': R["task_id"],
                            'error': str(e)
                        },
                        exc_info=True
                    )
                    messages.error(
                        request,
                        "Access denied: Security validation failed",
                        "alert-danger"
                    )
                    return render(request, template, cxt)
                    
                except Http404:
                    messages.error(
                        request, "Report file not found on server", "alert-danger"
                    )
                    return render(request, template, cxt)
                    
                except (OSError, IOError, FileNotFoundError) as e:
                    log.error(
                        "File system error during report download",
                        extra={
                            'user_id': request.user.id,
                            'task_id': R["task_id"],
                            'error': str(e)
                        },
                        exc_info=True
                    )
                    messages.error(
                        request, "Error accessing report file", "alert-danger"
                    )
                    return render(request, template, cxt)
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
