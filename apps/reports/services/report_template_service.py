"""
Report Template Service

Handles report template management including creation, modification,
and configuration operations with proper validation.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.forms import modelform_factory
from apps.activity.models.question_model import QuestionSet, Question
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger("django")


class ReportTemplateService:
    """
    Service class for handling report template operations.

    Provides centralized logic for template management,
    validation, and configuration handling.
    """

    @staticmethod
    def validate_template_data(template_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate report template data.

        Args:
            template_data: Dictionary containing template data

        Returns:
            Tuple containing (is_valid, error_message)
        """
        try:
            required_fields = ['qsetname', 'type']

            for field in required_fields:
                if not template_data.get(field):
                    return False, f"Missing required field: {field}"

            # Validate template name
            qsetname = template_data.get('qsetname', '').strip()
            if len(qsetname) < 3:
                return False, "Template name must be at least 3 characters"

            if len(qsetname) > 100:
                return False, "Template name cannot exceed 100 characters"

            # Validate template type
            valid_types = [
                'SITEREPORTTEMPLATE', 'INCIDENTREPORTTEMPLATE',
                'WORKPERMITTEMPLATE', 'CHECKLIST', 'ASSETMAINTENANCE'
            ]

            template_type = template_data.get('type')
            if template_type not in valid_types:
                return False, f"Invalid template type: {template_type}"

            # Validate JSON fields if present
            json_fields = ['buincludes', 'site_grp_includes', 'site_type_includes', 'assetincludes']
            for field in json_fields:
                value = template_data.get(field)
                if value is not None:
                    try:
                        if isinstance(value, str):
                            json.loads(value)
                        elif not isinstance(value, (list, dict)):
                            return False, f"Invalid JSON format for field: {field}"
                    except json.JSONDecodeError:
                        return False, f"Invalid JSON format for field: {field}"

            logger.debug(f"Template data validation passed for: {qsetname}")
            return True, None

        except Exception as e:
            logger.error(f"Error validating template data: {str(e)}", exc_info=True)
            return False, "Validation error occurred"

    @staticmethod
    @transaction.atomic(using=get_current_db_name())
    def create_template(template_data: Dict[str, Any], user, session_data: Dict) -> Tuple[Optional[QuestionSet], Optional[str]]:
        """
        Create a new report template with transaction safety.

        Args:
            template_data: Dictionary containing template data
            user: User creating the template
            session_data: User session data

        Returns:
            Tuple containing (template_instance, error_message)
        """
        try:
            # Validate template data
            is_valid, validation_error = ReportTemplateService.validate_template_data(template_data)
            if not is_valid:
                return None, validation_error

            # Check for duplicate template names
            existing_template = QuestionSet.objects.filter(
                qsetname=template_data['qsetname'],
                type=template_data['type'],
                client_id=session_data.get('client_id'),
                enable=True
            ).first()

            if existing_template:
                return None, f"Template with name '{template_data['qsetname']}' already exists"

            # Create template instance
            template = QuestionSet()
            template.qsetname = template_data['qsetname']
            template.type = template_data['type']
            template.client_id = session_data.get('client_id')
            template.bu_id = session_data.get('bu_id')
            template.enable = True
            template.parent_id = template_data.get('parent_id', 1)

            # Handle JSON fields
            template.buincludes = json.dumps(template_data.get('buincludes', []))
            template.site_grp_includes = json.dumps(template_data.get('site_grp_includes', []))
            template.site_type_includes = json.dumps(template_data.get('site_type_includes', []))
            template.assetincludes = json.dumps(template_data.get('assetincludes', []))

            # Save template
            template.save()

            # Add user tracking
            from apps.peoples import utils as putils
            template = putils.save_userinfo(template, user, session_data, create=True)

            logger.info(f"Successfully created template {template.id}: {template.qsetname}")
            return template, None

        except ValidationError as e:
            logger.warning(f"Template creation validation error: {str(e)}")
            return None, str(e)
        except Exception as e:
            logger.error(f"Error creating template: {str(e)}", exc_info=True)
            return None, "Failed to create template"

    @staticmethod
    @transaction.atomic(using=get_current_db_name())
    def update_template(template_id: int, template_data: Dict[str, Any], user, session_data: Dict) -> Tuple[Optional[QuestionSet], Optional[str]]:
        """
        Update an existing report template.

        Args:
            template_id: ID of the template to update
            template_data: Dictionary containing updated template data
            user: User updating the template
            session_data: User session data

        Returns:
            Tuple containing (template_instance, error_message)
        """
        try:
            # Validate template data
            is_valid, validation_error = ReportTemplateService.validate_template_data(template_data)
            if not is_valid:
                return None, validation_error

            # Get existing template
            template = QuestionSet.objects.select_for_update().filter(
                id=template_id,
                client_id=session_data.get('client_id')
            ).first()

            if not template:
                return None, "Template not found or access denied"

            # Check for duplicate names (excluding current template)
            existing_template = QuestionSet.objects.filter(
                qsetname=template_data['qsetname'],
                type=template_data['type'],
                client_id=session_data.get('client_id'),
                enable=True
            ).exclude(id=template_id).first()

            if existing_template:
                return None, f"Template with name '{template_data['qsetname']}' already exists"

            # Update template fields
            template.qsetname = template_data['qsetname']
            template.type = template_data['type']
            template.parent_id = template_data.get('parent_id', template.parent_id)

            # Update JSON fields
            template.buincludes = json.dumps(template_data.get('buincludes', []))
            template.site_grp_includes = json.dumps(template_data.get('site_grp_includes', []))
            template.site_type_includes = json.dumps(template_data.get('site_type_includes', []))
            template.assetincludes = json.dumps(template_data.get('assetincludes', []))

            # Save updated template
            template.save()

            # Update user tracking
            from apps.peoples import utils as putils
            template = putils.save_userinfo(template, user, session_data, create=False)

            logger.info(f"Successfully updated template {template.id}: {template.qsetname}")
            return template, None

        except ValidationError as e:
            logger.warning(f"Template update validation error: {str(e)}")
            return None, str(e)
        except ObjectDoesNotExist:
            return None, "Template not found"
        except Exception as e:
            logger.error(f"Error updating template {template_id}: {str(e)}", exc_info=True)
            return None, "Failed to update template"

    @staticmethod
    def get_template_configuration(template_id: int, client_id: int) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get template configuration including related data.

        Args:
            template_id: ID of the template
            client_id: Client ID for access control

        Returns:
            Tuple containing (configuration_dict, error_message)
        """
        try:
            # Get template with related data
            template = QuestionSet.objects.select_related(
                'client', 'bu', 'parent'
            ).prefetch_related(
                'questions__question_type',
                'questions__answer_options'
            ).filter(
                id=template_id,
                client_id=client_id
            ).first()

            if not template:
                return None, "Template not found or access denied"

            # Build configuration dictionary
            config = {
                'id': template.id,
                'qsetname': template.qsetname,
                'type': template.type,
                'enable': template.enable,
                'parent_id': template.parent_id,
                'seqno': template.seqno,
                'client_id': template.client_id,
                'bu_id': template.bu_id,
                'buincludes': json.loads(template.buincludes or '[]'),
                'site_grp_includes': json.loads(template.site_grp_includes or '[]'),
                'site_type_includes': json.loads(template.site_type_includes or '[]'),
                'assetincludes': json.loads(template.assetincludes or '[]'),
                'questions': []
            }

            # Add questions data
            for question in template.questions.all():
                question_data = {
                    'id': question.id,
                    'question_text': question.question_text,
                    'question_type': question.question_type.name if question.question_type else None,
                    'required': question.required,
                    'seqno': question.seqno,
                    'answer_options': [opt.option_text for opt in question.answer_options.all()]
                }
                config['questions'].append(question_data)

            logger.debug(f"Retrieved configuration for template {template_id}")
            return config, None

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in template {template_id}: {str(e)}")
            return None, "Template configuration is corrupted"
        except Exception as e:
            logger.error(f"Error getting template configuration {template_id}: {str(e)}", exc_info=True)
            return None, "Failed to retrieve template configuration"

    @staticmethod
    def get_questions_for_template(client_id: int, filters: Dict[str, Any] = None) -> Tuple[List[Dict], Optional[str]]:
        """
        Get available questions for template configuration.

        Args:
            client_id: Client ID for filtering
            filters: Additional filters for question selection

        Returns:
            Tuple containing (questions_list, error_message)
        """
        try:
            # Build base query with optimization
            queryset = Question.objects.select_related(
                'question_type', 'client'
            ).filter(
                client_id=client_id,
                enable=True
            ).order_by('seqno', 'id')

            # Apply additional filters if provided
            if filters:
                if 'question_type' in filters:
                    queryset = queryset.filter(question_type__name=filters['question_type'])

                if 'category' in filters:
                    queryset = queryset.filter(category=filters['category'])

                if 'search' in filters and filters['search']:
                    queryset = queryset.filter(
                        question_text__icontains=filters['search']
                    )

            # Convert to list with proper structure
            questions = []
            for question in queryset.iterator():
                question_data = {
                    'id': question.id,
                    'question_text': question.question_text,
                    'question_type': question.question_type.name if question.question_type else None,
                    'required': question.required,
                    'category': getattr(question, 'category', ''),
                    'seqno': question.seqno
                }
                questions.append(question_data)

            logger.debug(f"Retrieved {len(questions)} questions for client {client_id}")
            return questions, None

        except Exception as e:
            logger.error(f"Error getting questions for template: {str(e)}", exc_info=True)
            return [], "Failed to retrieve questions"

    @staticmethod
    def duplicate_template(template_id: int, new_name: str, user, session_data: Dict) -> Tuple[Optional[QuestionSet], Optional[str]]:
        """
        Create a duplicate of an existing template.

        Args:
            template_id: ID of the template to duplicate
            new_name: Name for the new template
            user: User creating the duplicate
            session_data: User session data

        Returns:
            Tuple containing (new_template_instance, error_message)
        """
        try:
            # Get original template
            original_template = QuestionSet.objects.filter(
                id=template_id,
                client_id=session_data.get('client_id')
            ).first()

            if not original_template:
                return None, "Original template not found or access denied"

            # Prepare data for new template
            template_data = {
                'qsetname': new_name,
                'type': original_template.type,
                'parent_id': original_template.parent_id,
                'buincludes': json.loads(original_template.buincludes or '[]'),
                'site_grp_includes': json.loads(original_template.site_grp_includes or '[]'),
                'site_type_includes': json.loads(original_template.site_type_includes or '[]'),
                'assetincludes': json.loads(original_template.assetincludes or '[]')
            }

            # Create duplicate template
            new_template, error = ReportTemplateService.create_template(
                template_data, user, session_data
            )

            if error:
                return None, error

            logger.info(f"Successfully duplicated template {template_id} as {new_template.id}")
            return new_template, None

        except Exception as e:
            logger.error(f"Error duplicating template {template_id}: {str(e)}", exc_info=True)
            return None, "Failed to duplicate template"