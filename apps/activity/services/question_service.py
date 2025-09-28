"""
Business logic service for Question management.
Separates complex business logic from views for better maintainability and testing.

Following .claude/rules.md:
- Service layer pattern (Rule 8)
- Specific exception handling (Rule 11)
- Database query optimization (Rule 12)
"""

import logging
from typing import Dict, Any, List, Union
from django.db import transaction, IntegrityError
from django.http import QueryDict

from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging
from apps.activity.forms.question_form import QuestionForm, QuestionSetForm
from apps.core.services.base_service import BaseService
from apps.core.error_handling import ErrorHandler
from apps.core.utils_new.db_utils import get_current_db_name
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


class QuestionService(BaseService):
    """
    Service class for Question-related business logic.
    """

    def get_service_name(self) -> str:
        return "QuestionService"

    @BaseService.monitor_performance("get_questions_list")
    def get_questions_list(self, request, fields: List[str], related: List[str]) -> List[Dict[str, Any]]:
        """
        Get formatted questions list for display.

        Args:
            request: HTTP request object
            fields: Fields to include in response
            related: Related fields to prefetch

        Returns:
            List of question dictionaries
        """
        try:
            return list(Question.objects.questions_listview(request, fields, related))
        except (ValueError, TypeError) as e:
            ErrorHandler.handle_exception(
                e,
                context={'method': 'get_questions_list', 'fields': fields, 'related': related}
            )
            return []

    @BaseService.monitor_performance("create_question")
    def create_question(self, form_data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Create a new question with proper validation.

        Args:
            form_data: Cleaned form data
            request: HTTP request object

        Returns:
            Dictionary with success status and data
        """
        try:
            with transaction.atomic():
                form = QuestionForm(form_data, request=request)

                if not form.is_valid():
                    return {
                        'success': False,
                        'errors': form.errors,
                        'message': 'Form validation failed'
                    }

                # Save the question
                question = form.save()
                question = putils.save_userinfo(question, request.user, request.session, create=True)

                # Get the formatted row data for response
                row_data = Question.objects.filter(id=question.id).values(
                    "id", "quesname", "answertype", "unit__tacode", "isworkflow"
                ).first()

                logger.info(f"Question '{question.quesname}' created successfully")

                return {
                    'success': True,
                    'message': f"Question '{question.quesname}' saved successfully",
                    'row': row_data,
                    'question_id': question.id
                }

        except IntegrityError as e:
            return {
                'success': False,
                'message': 'Question with similar details already exists',
                'error_type': 'integrity_error'
            }
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'method': 'create_question', 'form_data_keys': list(form_data.keys())}
            )
            return {
                'success': False,
                'message': 'Failed to create question',
                'correlation_id': correlation_id,
                'error_type': 'general_error'
            }

    @BaseService.monitor_performance("update_question")
    def update_question(self, question_id: int, form_data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Update an existing question.

        Args:
            question_id: ID of question to update
            form_data: Cleaned form data
            request: HTTP request object

        Returns:
            Dictionary with success status and data
        """
        try:
            with transaction.atomic():
                try:
                    question = Question.objects.get(id=question_id)
                except Question.DoesNotExist:
                    return {
                        'success': False,
                        'message': f'Question with ID {question_id} not found',
                        'error_type': 'not_found'
                    }

                form = QuestionForm(form_data, instance=question, request=request)

                if not form.is_valid():
                    return {
                        'success': False,
                        'errors': form.errors,
                        'message': 'Form validation failed'
                    }

                # Update the question
                question = form.save()
                question = putils.save_userinfo(question, request.user, request.session, create=False)

                # Get the formatted row data for response
                row_data = Question.objects.filter(id=question.id).values(
                    "id", "quesname", "answertype", "unit__tacode", "isworkflow"
                ).first()

                logger.info(f"Question '{question.quesname}' updated successfully")

                return {
                    'success': True,
                    'message': f"Question '{question.quesname}' updated successfully",
                    'row': row_data,
                    'question_id': question.id
                }

        except IntegrityError as e:
            return {
                'success': False,
                'message': 'Question with similar details already exists',
                'error_type': 'integrity_error'
            }
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'method': 'update_question', 'question_id': question_id, 'form_data_keys': list(form_data.keys())}
            )
            return {
                'success': False,
                'message': 'Failed to update question',
                'correlation_id': correlation_id,
                'error_type': 'general_error'
            }

    @BaseService.monitor_performance("delete_question")
    def delete_question(self, question_id: int) -> Dict[str, Any]:
        """
        Delete a question if it's not in use.

        Args:
            question_id: ID of question to delete

        Returns:
            Dictionary with success status and message
        """
        try:
            with transaction.atomic():
                try:
                    question = Question.objects.get(id=question_id)
                except Question.DoesNotExist:
                    return {
                        'success': False,
                        'message': f'Question with ID {question_id} not found',
                        'error_type': 'not_found'
                    }

                # Check if question is in use
                if QuestionSetBelonging.objects.filter(question=question).exists():
                    return {
                        'success': False,
                        'message': 'Cannot delete question as it is being used in question sets',
                        'error_type': 'in_use'
                    }

                question_name = question.quesname
                question.delete()

                logger.info(f"Question '{question_name}' deleted successfully")

                return {
                    'success': True,
                    'message': f"Question '{question_name}' deleted successfully"
                }

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'method': 'delete_question', 'question_id': question_id}
            )
            return {
                'success': False,
                'message': 'Failed to delete question',
                'correlation_id': correlation_id,
                'error_type': 'general_error'
            }


class QuestionSetService(BaseService):
    """
    Service class for QuestionSet-related business logic.
    """

    def get_service_name(self) -> str:
        return "QuestionSetService"

    @BaseService.monitor_performance("get_questionsets_list")
    def get_questionsets_list(self, request, fields: List[str], related: List[str]) -> List[Dict[str, Any]]:
        """
        Get formatted question sets list for display.

        Args:
            request: HTTP request object
            fields: Fields to include in response
            related: Related fields to prefetch

        Returns:
            List of question set dictionaries
        """
        try:
            return list(QuestionSet.objects.checklist_listview(request, fields, related))
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            ErrorHandler.handle_exception(
                e,
                context={'method': 'get_questionsets_list', 'fields': fields, 'related': related}
            )
            return []

    @BaseService.monitor_performance("create_questionset")
    def create_questionset(self, form_data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Create a new question set with proper validation.

        Args:
            form_data: Cleaned form data
            request: HTTP request object

        Returns:
            Dictionary with success status and data
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                form = QuestionSetForm(form_data, request=request)

                if not form.is_valid():
                    return {
                        'success': False,
                        'errors': form.errors,
                        'message': 'Form validation failed'
                    }

                # Save the question set
                qset = form.save()
                putils.save_userinfo(qset, request.user, request.session, create=True)

                logger.info(f"QuestionSet '{qset.qsetname}' created successfully")

                return {
                    'success': True,
                    'message': 'Record has been saved successfully',
                    'parent_id': qset.id,
                    'qset_name': qset.qsetname
                }

        except IntegrityError as e:
            return {
                'success': False,
                'message': 'Question Set with similar details already exists',
                'error_type': 'integrity_error'
            }
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'method': 'create_questionset', 'form_data_keys': list(form_data.keys())}
            )
            return {
                'success': False,
                'message': 'Failed to create question set',
                'correlation_id': correlation_id,
                'error_type': 'general_error'
            }

    @BaseService.monitor_performance("get_questions_for_qset")
    def get_questions_for_qset(self, qset_id: int) -> List[Dict[str, Any]]:
        """
        Get questions for a specific question set with their configuration.

        Args:
            qset_id: ID of the question set

        Returns:
            List of question configuration dictionaries
        """
        try:
            questions = list(
                QuestionSetBelonging.objects.select_related("question")
                .filter(qset_id=qset_id)
                .values(
                    "ismandatory",
                    "seqno",
                    "max",
                    "min",
                    "alerton",
                    "isavpt",
                    "avpttype",
                    "options",
                    "question__quesname",
                    "answertype",
                    "question__id",
                    "display_conditions",
                )
            )
            return questions
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            ErrorHandler.handle_exception(
                e,
                context={'method': 'get_questions_for_qset', 'qset_id': qset_id}
            )
            return []


class FormDataService:
    """
    Service for handling complex form data parsing and validation.
    """

    @staticmethod
    def clean_question_form_data(raw_data: Union[QueryDict, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Clean and validate question form data, handling complex scenarios.

        Args:
            raw_data: Raw form data from request

        Returns:
            Cleaned form data dictionary
        """
        from apps.core.utils_new.http_utils import get_clean_form_data

        try:
            if isinstance(raw_data, QueryDict):
                data = get_clean_form_data(raw_data)
            else:
                data = raw_data.copy()

            # Handle checkbox values conversion
            checkbox_fields = ['isavpt', 'isworkflow']
            for field in checkbox_fields:
                if field in data:
                    value = data[field]
                    if value == 'on':
                        data[field] = True
                    elif value in ('off', ''):
                        data[field] = False

            # Handle options field (common issue with truncated data)
            if not data.get('options') and isinstance(raw_data, QueryDict):
                # Try to extract from formData if available
                form_data_raw = raw_data.get('formData', '')
                if form_data_raw and 'options=' in form_data_raw:
                    import urllib.parse
                    import re

                    # Parse options from formData
                    options_match = re.search(r'options=([^&]*)', form_data_raw)
                    if options_match:
                        options_value = urllib.parse.unquote(options_match.group(1))
                        data = data.copy()
                        data['options'] = options_value

            return data

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            ErrorHandler.handle_exception(
                e,
                context={'method': 'clean_question_form_data'}
            )
            return raw_data if isinstance(raw_data, dict) else {}

    @staticmethod
    def validate_question_data(data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Validate question data beyond basic form validation.

        Args:
            data: Form data dictionary

        Returns:
            Dictionary of validation errors
        """
        errors = {}

        try:
            # Validate answer type specific requirements
            answer_type = data.get('answertype', '')

            if answer_type == Question.AnswerType.DROPDOWN:
                options = data.get('options', '').strip()
                if not options:
                    errors['options'] = ['Options are required for dropdown questions']
                else:
                    # Validate options format (should be separated by | or ,)
                    option_separators = ['|', ',']
                    if not any(sep in options for sep in option_separators):
                        if len(options.split()) < 2:  # Single word is probably incomplete
                            errors['options'] = ['Multiple options should be separated by | or ,']

            elif answer_type in [Question.AnswerType.NUMBER, Question.AnswerType.RANGE]:
                # Validate min/max for numeric fields
                min_val = data.get('min')
                max_val = data.get('max')

                if min_val is not None and max_val is not None:
                    try:
                        min_num = float(min_val)
                        max_num = float(max_val)
                        if min_num >= max_num:
                            errors['max'] = ['Maximum value must be greater than minimum value']
                    except (ValueError, TypeError):
                        errors['min'] = ['Invalid numeric value']

            # Validate question name
            quesname = data.get('quesname', '').strip()
            if not quesname:
                errors['quesname'] = ['Question name is required']
            elif len(quesname) < 3:
                errors['quesname'] = ['Question name must be at least 3 characters long']

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            ErrorHandler.handle_exception(
                e,
                context={'method': 'validate_question_data', 'data_keys': list(data.keys())}
            )
            errors['__all__'] = ['Validation error occurred']

        return errors


QuestionManagementService = QuestionService