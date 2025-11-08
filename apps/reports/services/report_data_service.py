"""
Report Data Service

Handles data retrieval and processing for reports with proper query optimization
and error handling. Extracted from fat views to follow single responsibility principle.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db.models import QuerySet
from apps.activity.models.job_model import Jobneed
from apps.activity.models.question_model import QuestionSet
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.json_utils import safe_json_parse_params
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger("django")


class ReportDataService:
    """
    Service class for handling report data operations.

    Provides optimized database queries with proper error handling
    and follows Django best practices for data access.
    """

    @staticmethod
    def get_site_reports(request) -> Tuple[List[Dict], Optional[str]]:
        """
        Retrieve site reports with optimized database queries.

        Args:
            request: Django request object containing user session and parameters

        Returns:
            Tuple containing (report_data_list, error_message)

        Raises:
            ValidationError: If request parameters are invalid
        """
        try:
            # Use select_related to prevent N+1 queries
            objs = Jobneed.objects.select_related(
                'bu', 'client', 'people', 'shift'
            ).get_sitereportlist(request)

            # Convert to list efficiently
            report_data = list(objs.iterator()) if hasattr(objs, 'iterator') else list(objs)

            logger.info(f"Retrieved {len(report_data)} site reports for user {request.user.id}")
            return report_data, None

        except ValidationError as e:
            logger.warning(f"Invalid parameters for site reports: {str(e)}")
            return [], f"Invalid parameters: {str(e)}"
        except ObjectDoesNotExist as e:
            logger.warning(f"Required objects not found for site reports: {str(e)}", exc_info=True)
            return [], "Required data not found"
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error retrieving site reports: {str(e)}", exc_info=True)
            return [], "An error occurred while retrieving reports"
        except (AttributeError, TypeError) as e:
            logger.error(f"Data structure error retrieving site reports: {str(e)}", exc_info=True)
            return [], "An error occurred while retrieving reports"

    @staticmethod
    def get_incident_reports(request) -> Tuple[List[Dict], List[Dict], Optional[str]]:
        """
        Retrieve incident reports with associated attachments.

        Args:
            request: Django request object

        Returns:
            Tuple containing (reports_list, attachments_list, error_message)
        """
        try:
            # Use select_related and prefetch_related for optimization
            objs, atts = Jobneed.objects.select_related(
                'bu', 'client', 'people', 'shift'
            ).prefetch_related(
                'attachments'
            ).get_incidentreportlist(request)

            reports_data = list(objs.iterator()) if hasattr(objs, 'iterator') else list(objs)
            attachments_data = list(atts.iterator()) if hasattr(atts, 'iterator') else list(atts)

            logger.info(f"Retrieved {len(reports_data)} incident reports with {len(attachments_data)} attachments")
            return reports_data, attachments_data, None

        except ValidationError as e:
            logger.warning(f"Invalid parameters for incident reports: {str(e)}")
            return [], [], f"Invalid parameters: {str(e)}"
        except ObjectDoesNotExist as e:
            logger.warning(f"Required objects not found for incident reports: {str(e)}", exc_info=True)
            return [], [], "Required data not found"
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error retrieving incident reports: {str(e)}", exc_info=True)
            return [], [], "An error occurred while retrieving reports"
        except (AttributeError, TypeError) as e:
            logger.error(f"Data structure error retrieving incident reports: {str(e)}", exc_info=True)
            return [], [], "An error occurred while retrieving reports"

    @staticmethod
    def get_master_report_templates(request_params: Dict, fields: List[str]) -> Tuple[Dict, Optional[str]]:
        """
        Retrieve master report templates with pagination and filtering.

        Args:
            request_params: Dictionary containing request parameters
            fields: List of fields to select

        Returns:
            Tuple containing (response_data_dict, error_message)
        """
        try:
            from apps.core import utils

            # Optimize query with specific field selection and indexing
            objects = QuestionSet.objects.select_related(
                'client', 'bu'
            ).filter(
                type="SITEREPORT",
                enable=True
            ).values(*fields).order_by('-modified_date')

            count = objects.count()
            filtered_count = count

            if count > 0:
                # Apply pagination efficiently
                objects, filtered_count = utils.get_paginated_results(
                    request_params, objects, count, fields, [], QuestionSet
                )

            # Use iterator for memory efficiency
            data_list = list(objects.iterator()) if hasattr(objects, 'iterator') else list(objects)

            response_data = {
                "draw": request_params.get("draw", 1),
                "recordsTotal": count,
                "data": data_list,
                "recordsFiltered": filtered_count,
            }

            logger.debug(f"Retrieved {len(data_list)} master report templates")
            return response_data, None

        except ValidationError as e:
            logger.warning(f"Invalid parameters for master report templates: {str(e)}", exc_info=True)
            return {}, f"Invalid parameters: {str(e)}"
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error retrieving master report templates: {str(e)}", exc_info=True)
            return {}, "An error occurred while retrieving templates"
        except (AttributeError, TypeError, KeyError) as e:
            logger.error(f"Data structure error retrieving master report templates: {str(e)}", exc_info=True)
            return {}, "An error occurred while retrieving templates"

    @staticmethod
    def get_configured_templates(request, template_type: str, fields: List[str]) -> Tuple[List[Dict], Optional[str]]:
        """
        Retrieve configured templates for a specific type.

        Args:
            request: Django request object
            template_type: Type of template to retrieve
            fields: Fields to select

        Returns:
            Tuple containing (templates_list, error_message)
        """
        try:
            # Use optimized query with proper relationships
            templates = QuestionSet.objects.select_related(
                'client', 'bu', 'parent'
            ).get_configured_sitereporttemplates(
                request, [], fields, template_type
            )

            templates_data = list(templates.iterator()) if hasattr(templates, 'iterator') else list(templates)

            logger.info(f"Retrieved {len(templates_data)} configured templates of type {template_type}")
            return templates_data, None

        except ValidationError as e:
            logger.warning(f"Invalid template type {template_type}: {str(e)}")
            return [], f"Invalid template type: {str(e)}"
        except ObjectDoesNotExist as e:
            logger.warning(f"Template type {template_type} not found: {str(e)}", exc_info=True)
            return [], "Template type not found"
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error retrieving configured templates: {str(e)}", exc_info=True)
            return [], "An error occurred while retrieving templates"
        except (AttributeError, TypeError) as e:
            logger.error(f"Data structure error retrieving configured templates: {str(e)}", exc_info=True)
            return [], "An error occurred while retrieving templates"

    @staticmethod
    def get_template_sections(parent_id: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Retrieve template sections with question counts.

        Args:
            parent_id: ID of the parent template

        Returns:
            Tuple containing (sections_list, error_message)
        """
        try:
            # Convert and validate parent_id
            try:
                parent_id_int = 0 if parent_id == "undefined" else int(parent_id)
            except (ValueError, TypeError):
                raise ValidationError(f"Invalid parent_id: {parent_id}")

            # Use optimized query with question counts
            sections = QuestionSet.objects.select_related(
                'client', 'bu'
            ).prefetch_related(
                'questions'
            ).get_qset_with_questionscount(parent_id_int)

            sections_data = list(sections.iterator()) if hasattr(sections, 'iterator') else list(sections)

            logger.info(f"Retrieved {len(sections_data)} sections for parent {parent_id}")
            return sections_data, None

        except ValidationError as e:
            logger.warning(f"Invalid parent_id for sections: {str(e)}", exc_info=True)
            return [], str(e)
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error retrieving template sections: {str(e)}", exc_info=True)
            return [], "An error occurred while retrieving sections"
        except (AttributeError, TypeError) as e:
            logger.error(f"Data structure error retrieving template sections: {str(e)}", exc_info=True)
            return [], "An error occurred while retrieving sections"

    @staticmethod
    @transaction.atomic(using=get_current_db_name())
    def save_template_with_transaction(template_instance, user, session) -> Tuple[Any, Optional[str]]:
        """
        Save template instance within a database transaction.

        Args:
            template_instance: Template model instance to save
            user: User performing the save operation
            session: User session data

        Returns:
            Tuple containing (saved_template, error_message)
        """
        try:
            from apps.peoples import utils as putils

            # Save the template
            template_instance.save()

            # Add user tracking information
            template_instance = putils.save_userinfo(template_instance, user, session)

            logger.info(f"Successfully saved template {template_instance.id} by user {user.id}")
            return template_instance, None

        except ValidationError as e:
            logger.warning(f"Validation error saving template: {str(e)}", exc_info=True)
            return None, f"Validation error: {str(e)}"
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error saving template: {str(e)}", exc_info=True)
            return None, "An error occurred while saving the template"
        except (AttributeError, TypeError) as e:
            logger.error(f"Data structure error saving template: {str(e)}", exc_info=True)
            return None, "An error occurred while saving the template"

    @staticmethod
    def delete_template(template_id: str) -> Tuple[bool, Optional[str]]:
        """
        Soft delete a template by setting enable=False.

        Args:
            template_id: ID of the template to delete

        Returns:
            Tuple containing (success_boolean, error_message)
        """
        try:
            # Validate template_id
            try:
                template_id_int = int(template_id)
            except (ValueError, TypeError):
                raise ValidationError(f"Invalid template_id: {template_id}")

            if template_id_int <= 0:
                raise ValidationError("Template ID must be positive")

            # Perform soft delete
            updated_count = QuestionSet.objects.filter(
                id=template_id_int
            ).update(enable=False)

            if updated_count == 0:
                logger.warning(f"Template {template_id} not found for deletion")
                return False, "Template not found"

            logger.info(f"Successfully deleted template {template_id}")
            return True, None

        except ValidationError as e:
            logger.warning(f"Invalid template_id for deletion: {str(e)}", exc_info=True)
            return False, str(e)
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error deleting template {template_id}: {str(e)}", exc_info=True)
            return False, "An error occurred while deleting the template"