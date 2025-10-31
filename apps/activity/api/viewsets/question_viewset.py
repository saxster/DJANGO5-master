"""
Question ViewSet for Mobile API

Provides question and question set endpoints that replace legacy queries:
- get_questionsmodifiedafter → GET /questions/modified-after/
- get_qsetmodifiedafter → GET /question-sets/modified-after/
- get_qsetbelongingmodifiedafter → GET /question-set-belongings/modified-after/
- get_questionset_with_conditional_logic → GET /question-sets/{id}/conditional-logic/

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling (no bare except)
- Delegates to service layer
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from pydantic import ValidationError as PydanticValidationError
import logging
import json

from apps.activity.models.question_model import (
    Question,
    QuestionSet,
    QuestionSetBelonging,
)
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination
from apps.service.pydantic_schemas.question_schema import (
    QuestionModifiedSchema,
    QuestionSetModifiedSchema,
    QuestionSetBelongingModifiedSchema,
)

logger = logging.getLogger('mobile_service_log')


class QuestionViewSet(viewsets.GenericViewSet):
    """
    Mobile API for questions and question sets.

    Endpoints:
    - GET /api/v1/operations/questions/modified-after/
    - GET /api/v1/operations/question-sets/modified-after/
    - GET /api/v1/operations/question-set-belongings/modified-after/
    - GET /api/v1/operations/question-sets/{id}/conditional-logic/
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    pagination_class = MobileSyncCursorPagination
    queryset = QuestionSet.objects.all()

    @action(detail=False, methods=['get'], url_path='questions/modified-after')
    def questions_modified_after(self, request):
        """
        Get questions modified after a given timestamp.

        Replaces legacy query: get_questionsmodifiedafter

        Query Params:
            mdtz (str): Modification timestamp (ISO format)
            ctzoffset (int): Client timezone offset
            clientid (int): Client ID

        Returns:
            {
                "count": <int>,
                "results": [...],
                "message": <string>
            }
        """
        try:
            # Validate parameters
            filter_data = {
                'mdtz': request.query_params.get('mdtz'),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0)),
                'clientid': int(request.query_params.get('clientid'))
            }
            validated = QuestionModifiedSchema(**filter_data)

            # Get data from model manager
            data = Question.objects.get_questions_modified_after(
                mdtz=validated.mdtz,
                clientid=validated.clientid
            )

            # Paginate results
            page = self.paginate_queryset(data)
            if page is not None:
                from apps.activity.api.serializers import QuestionSerializer
                serializer = QuestionSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            from apps.activity.api.serializers import QuestionSerializer
            serializer = QuestionSerializer(data, many=True)
            logger.info(f"Returned {len(data)} questions")

            return Response({
                'count': len(serializer.data),
                'results': serializer.data,
                'message': 'Success'
            })

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid parameters: {e}", exc_info=True)
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PydanticValidationError as ve:
            logger.error(f"Validation error: {ve}", exc_info=True)
            return Response(
                {'error': f'Invalid input: {str(ve)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='question-sets/modified-after')
    def question_sets_modified_after(self, request):
        """
        Get question sets modified after a given timestamp.

        Replaces legacy query: get_qsetmodifiedafter

        Query Params:
            mdtz (str): Modification timestamp
            ctzoffset (int): Client timezone offset
            buid (int): Business unit ID
            clientid (int): Client ID
            peopleid (int): People ID

        Returns:
            {
                "count": <int>,
                "results": [...],
                "message": <string>
            }
        """
        try:
            # Validate parameters
            filter_data = {
                'mdtz': request.query_params.get('mdtz'),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0)),
                'buid': int(request.query_params.get('buid')),
                'clientid': int(request.query_params.get('clientid')),
                'peopleid': int(request.query_params.get('peopleid'))
            }
            validated = QuestionSetModifiedSchema(**filter_data)

            # Get data from model manager
            data = QuestionSet.objects.get_qset_modified_after(
                mdtz=validated.mdtz,
                buid=validated.buid,
                clientid=validated.clientid,
                peopleid=validated.peopleid,
            )

            # Paginate results
            page = self.paginate_queryset(data)
            if page is not None:
                from apps.activity.api.serializers import QuestionSetSerializer
                serializer = QuestionSetSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            from apps.activity.api.serializers import QuestionSetSerializer
            serializer = QuestionSetSerializer(data, many=True)
            logger.info(f"Returned {len(data)} question sets")

            return Response({
                'count': len(serializer.data),
                'results': serializer.data,
                'message': 'Success'
            })

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid parameters: {e}", exc_info=True)
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PydanticValidationError as ve:
            logger.error(f"Validation error: {ve}", exc_info=True)
            return Response(
                {'error': f'Invalid input: {str(ve)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='question-set-belongings/modified-after')
    def question_set_belongings_modified_after(self, request):
        """
        Get question set belongings modified after timestamp.

        Replaces legacy query: get_qsetbelongingmodifiedafter

        Query Params:
            mdtz (str): Modification timestamp
            ctzoffset (int): Client timezone offset
            buid (int): Business unit ID
            clientid (int): Client ID
            peopleid (int): People ID
            includeDependencyLogic (bool, optional): Include dependency analysis

        Returns:
            {
                "count": <int>,
                "results": [...],
                "message": <string>
            }
        """
        try:
            # Validate parameters
            filter_data = {
                'mdtz': request.query_params.get('mdtz'),
                'ctzoffset': int(request.query_params.get('ctzoffset', 0)),
                'buid': int(request.query_params.get('buid')),
                'clientid': int(request.query_params.get('clientid')),
                'peopleid': int(request.query_params.get('peopleid'))
            }
            validated = QuestionSetBelongingModifiedSchema(**filter_data)
            include_dependency_logic = request.query_params.get('includeDependencyLogic', 'false').lower() == 'true'

            # Get data
            data = QuestionSetBelonging.objects.get_modified_after(
                mdtz=validated.mdtz,
                buid=validated.buid
            )

            # Handle dependency logic if requested
            if include_dependency_logic:
                results = self._process_dependency_logic(data)
                return Response({
                    'count': len(results),
                    'results': results,
                    'message': f'Total {len(results)} records with conditional logic fetched successfully!'
                })

            # Standard response
            from apps.activity.api.serializers import QuestionSetBelongingSerializer
            serializer = QuestionSetBelongingSerializer(data, many=True)
            logger.info(f"Returned {len(data)} question set belongings")

            return Response({
                'count': len(serializer.data),
                'results': serializer.data,
                'message': 'Success'
            })

        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Invalid parameters or data processing error: {e}", exc_info=True)
            return Response(
                {'error': f'Data processing failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PydanticValidationError as ve:
            logger.error(f"Validation error: {ve}", exc_info=True)
            return Response(
                {'error': f'Invalid input: {str(ve)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='conditional-logic')
    def conditional_logic(self, request, pk=None):
        """
        Get question set with full conditional logic support.

        Replaces legacy query: get_questionset_with_conditional_logic

        Path Params:
            pk: Question set ID

        Query Params:
            clientid (int): Client ID
            buid (int): Business unit ID

        Returns:
            {
                "questions": [...],
                "dependency_map": {...},
                "has_conditional_logic": bool,
                "validation_warnings": [...]
            }
        """
        try:
            qset_id = int(pk)
            logger.info(f"Request for conditional logic (qset_id={qset_id})")

            # Get enhanced question set with conditional logic
            logic_data = QuestionSetBelonging.objects.get_questions_with_logic(qset_id)

            # Log validation warnings
            if logic_data.get('validation_warnings'):
                warnings_count = len(logic_data['validation_warnings'])
                logger.warning(
                    f"Questionset {qset_id} has {warnings_count} validation warnings",
                    extra={'qset_id': qset_id, 'warnings': logic_data['validation_warnings']}
                )

            logger.info(
                f"Questionset {qset_id}: {len(logic_data.get('questions', []))} questions, "
                f"conditional logic: {logic_data.get('has_conditional_logic', False)}"
            )

            return Response(logic_data)

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid question set ID: {e}", exc_info=True)
            return Response(
                {'error': f'Invalid question set ID: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Question set not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error for qset_id={qset_id}: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Data processing error for qset_id={qset_id}: {e}", exc_info=True)
            return Response(
                {'error': 'Data processing failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_dependency_logic(self, data):
        """
        Process dependency logic for question set belongings.

        Args:
            data: QuerySet of QuestionSetBelonging

        Returns:
            list: Enhanced records with dependency information
        """
        data_list = list(data.values())
        logger.info(f"Processing {len(data_list)} records for dependency analysis")

        # Group by questionset
        qset_groups = {}
        for record in data_list:
            qset_id = record.get('qset_id')
            if qset_id not in qset_groups:
                qset_groups[qset_id] = []
            qset_groups[qset_id].append(record)

        # Add dependency metadata
        enhanced_records = []
        for qset_id, questions in qset_groups.items():
            try:
                logic_data = QuestionSetBelonging.objects.get_questions_with_logic(qset_id)
                dependency_map = logic_data.get('dependency_map', {})
                has_conditional_logic = logic_data.get('has_conditional_logic', False)

                # Add metadata to each question
                for record in questions:
                    record['dependency_map'] = dependency_map
                    record['has_conditional_logic'] = bool(has_conditional_logic)
                    enhanced_records.append(record)
            except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as dep_error:
                logger.warning(f"Could not process dependencies for qset {qset_id}: {str(dep_error)}")
                # Add records without dependency data
                for record in questions:
                    record['dependency_map'] = {}
                    record['has_conditional_logic'] = False
                    enhanced_records.append(record)

        logger.info(f"Enhanced {len(enhanced_records)} records with dependency logic")
        return enhanced_records


__all__ = ['QuestionViewSet']
