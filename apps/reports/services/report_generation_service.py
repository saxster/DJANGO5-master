"""
Report Generation Service

Handles report generation workflows including validation, processing,
and response generation. Extracted from fat views to improve maintainability.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from apps.core.decorators import rate_limit
from background_tasks.tasks import create_save_report_async
from apps.core.exceptions.patterns import CELERY_EXCEPTIONS

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import FILE_EXCEPTIONS


logger = logging.getLogger("django")


class ReportGenerationService:
    """
    Service class for handling report generation workflows.

    Provides centralized logic for report processing, validation,
    and asynchronous task management.
    """

    @staticmethod
    def validate_report_request(form_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate report generation request parameters.

        Args:
            form_data: Dictionary containing form data from request

        Returns:
            Tuple containing (is_valid, error_message)
        """
        try:
            required_fields = ['report_type', 'date_from', 'date_to']

            for field in required_fields:
                if not form_data.get(field):
                    return False, f"Missing required field: {field}"

            # Validate date range
            try:
                date_from = datetime.strptime(str(form_data['date_from']), '%Y-%m-%d')
                date_to = datetime.strptime(str(form_data['date_to']), '%Y-%m-%d')

                if date_from > date_to:
                    return False, "Date from cannot be later than date to"

                # Check reasonable date range (e.g., not more than 1 year)
                if (date_to - date_from).days > 365:
                    return False, "Date range cannot exceed 365 days"

            except (ValueError, TypeError) as e:
                return False, f"Invalid date format: {str(e)}"

            # Validate report type
            valid_report_types = [
                'SITE_REPORT', 'INCIDENT_REPORT', 'ATTENDANCE_REPORT',
                'ASSET_REPORT', 'MAINTENANCE_REPORT'
            ]

            if form_data['report_type'] not in valid_report_types:
                return False, f"Invalid report type: {form_data['report_type']}"

            logger.debug(f"Report request validation passed for type: {form_data['report_type']}")
            return True, None

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error validating report request: {str(e)}", exc_info=True)
            return False, "Validation error occurred"

    @staticmethod
    def process_report_form(form, request, create_mode: bool = True) -> Tuple[JsonResponse, Optional[str]]:
        """
        Process report form submission with proper error handling.

        Args:
            form: Django form instance
            request: Django request object
            create_mode: Whether this is creating a new report or updating

        Returns:
            Tuple containing (json_response, error_message)
        """
        try:
            if not form.is_valid():
                error_details = {}
                for field, errors in form.errors.items():
                    error_details[field] = [str(error) for error in errors]

                logger.warning(f"Form validation failed: {error_details}")
                return JsonResponse({
                    "success": False,
                    "errors": error_details,
                    "message": "Form validation failed"
                }, status=400), "Form validation failed"

            # Extract and validate form data
            form_data = form.cleaned_data
            is_valid, validation_error = ReportGenerationService.validate_report_request(form_data)

            if not is_valid:
                return JsonResponse({
                    "success": False,
                    "message": validation_error
                }, status=400), validation_error

            # Process the validated form
            report_instance = form.save(commit=False)

            # Add metadata
            report_instance.created_by = request.user
            report_instance.client_id = request.session.get('client_id')
            report_instance.bu_id = request.session.get('bu_id')

            # Save with user information
            from apps.peoples import utils as putils
            report_instance = putils.save_userinfo(
                report_instance, request.user, request.session, create=create_mode
            )

            response_data = {
                "success": True,
                "message": f"Report {'created' if create_mode else 'updated'} successfully",
                "report_id": report_instance.id,
                "redirect_url": reverse("reports:report_detail", kwargs={"pk": report_instance.id})
            }

            logger.info(f"Successfully processed report form for user {request.user.id}")
            return JsonResponse(response_data, status=200), None

        except ValidationError as e:
            logger.warning(f"Report form validation error: {str(e)}")
            return JsonResponse({
                "success": False,
                "message": f"Validation error: {str(e)}"
            }, status=400), str(e)

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error processing report form: {str(e)}", exc_info=True)
            return JsonResponse({
                "success": False,
                "message": "An error occurred while processing the report"
            }, status=500), str(e)

    @staticmethod
    @rate_limit(max_requests=10, window_seconds=300)  # Limit report generation requests
    def initiate_async_report_generation(form_data: Dict, session_data: Dict, user_email: str, user_id: int) -> Tuple[Any, Optional[str]]:
        """
        Initiate asynchronous report generation with rate limiting.

        Args:
            form_data: Cleaned form data for report generation
            session_data: User session data
            user_email: User's email address
            user_id: User's ID

        Returns:
            Tuple containing (task_instance, error_message)
        """
        try:
            # Validate required session data
            if not session_data.get('client_id'):
                raise ValidationError("Client ID not found in session")

            # Validate user data
            if not user_email or not user_id:
                raise ValidationError("User information incomplete")

            # Start asynchronous task
            task = create_save_report_async.delay(
                form_data,
                session_data.get('client_id'),
                user_email,
                user_id
            )

            logger.info(f"Initiated async report generation task {task.id} for user {user_id}")
            return task, None

        except ValidationError as e:
            logger.warning(f"Report generation validation error: {str(e)}")
            return None, str(e)
        except CELERY_EXCEPTIONS as e:
            logger.error(f"Error initiating async report generation: {str(e)}", exc_info=True)
            return None, "Failed to start report generation"

    @staticmethod
    def generate_pdf_response(html_content: str, filename: str = "report.pdf") -> Tuple[Any, Optional[str]]:
        """
        Generate PDF response from HTML content.

        Args:
            html_content: HTML string to convert to PDF
            filename: Name for the PDF file

        Returns:
            Tuple containing (http_response, error_message)
        """
        try:
            from django.http import HttpResponse
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            import os

            # Validate inputs
            if not html_content:
                raise ValidationError("HTML content cannot be empty")

            if not filename.endswith('.pdf'):
                filename += '.pdf'

            # Generate PDF with proper CSS
            css_path = "frontend/static/assets/css/local/reports.css"
            font_config = FontConfiguration()

            html = HTML(string=html_content)
            css = CSS(filename=css_path) if os.path.exists(css_path) else None

            stylesheets = [css] if css else []
            pdf_content = html.write_pdf(stylesheets=stylesheets, font_config=font_config)

            # Create HTTP response
            response = HttpResponse(pdf_content, content_type="application/pdf")
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            logger.info(f"Successfully generated PDF: {filename}")
            return response, None

        except ValidationError as e:
            logger.warning(f"PDF generation validation error: {str(e)}")
            return None, str(e)
        except ImportError as e:
            logger.error(f"Missing PDF generation dependencies: {str(e)}")
            return None, "PDF generation not available - missing dependencies"
        except FILE_EXCEPTIONS as e:
            logger.error(f"Error generating PDF: {str(e)}", exc_info=True)
            return None, "Failed to generate PDF"

    @staticmethod
    def render_report_template(template_name: str, context_data: Dict[str, Any], request=None) -> Tuple[str, Optional[str]]:
        """
        Render report template with sanitized context data.

        Security Features:
        - Automatic input sanitization against XSS
        - Sensitive field detection and redaction
        - HTML tag filtering with whitelist
        - Comprehensive security logging

        Args:
            template_name: Name of the template to render
            context_data: Context data for template rendering
            request: Optional Django request object

        Returns:
            Tuple containing (rendered_html, error_message)
        """
        try:
            from apps.reports.services.template_sanitization_service import sanitize_template_context

            # Validate inputs
            if not template_name:
                raise ValidationError("Template name cannot be empty")

            if not isinstance(context_data, dict):
                raise ValidationError("Context data must be a dictionary")

            # SECURITY: Sanitize user-provided context data
            # Uses strict mode for PDF generation (no HTML allowed)
            sanitized_context = sanitize_template_context(
                context_data,
                strict_mode=True  # PDF templates don't need HTML
            )

            # Add default context variables (trusted, no sanitization needed)
            default_context = {
                'timestamp': datetime.now(),
                'generated_by': request.user.get_full_name() if request and hasattr(request, 'user') else 'System'
            }
            default_context.update(sanitized_context)

            # Render template
            html_content = render_to_string(template_name, default_context, request=request)

            logger.debug(
                "Successfully rendered template with sanitization",
                extra={
                    'template': template_name,
                    'context_fields': len(context_data)
                }
            )
            return html_content, None

        except ValidationError as e:
            logger.warning(f"Template rendering validation error: {str(e)}")
            return "", str(e)
        except (ImportError, OSError) as e:
            logger.error(f"Template rendering dependency error: {str(e)}", exc_info=True)
            return "", "Template rendering failed - missing dependencies"
        except (KeyError, AttributeError, TypeError) as e:
            logger.error(f"Template context error: {str(e)}", exc_info=True)
            return "", "Invalid template context data"

    @staticmethod
    def get_report_behavior_config(report_name: str) -> Dict[str, Any]:
        """
        Get behavior configuration for a specific report type.

        Args:
            report_name: Name of the report type

        Returns:
            Dictionary containing behavior configuration
        """
        try:
            from apps.reports import utils as rutils

            report_essentials = rutils.ReportEssentials(report_name=report_name)
            behavior_config = getattr(report_essentials, 'behaviour_json', {})

            logger.debug(f"Retrieved behavior config for report: {report_name}")
            return behavior_config

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Error getting report behavior config for {report_name}: {str(e)}")
            return {}  # Return empty config as fallback