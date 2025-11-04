"""
Changeset Management Views

Handles changeset operations: rollback, listing, diff previews.

Migrated from: apps/onboarding_api/views.py (lines 909-1352)
Date: 2025-09-30
Refactoring: Phase 3 - God File Elimination
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import CanApproveAIRecommendations
from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import AIChangeSet, TypeAssist
import logging

logger = logging.getLogger(__name__)


class ChangeSetRollbackView(APIView):
    """Rollback a previously applied AI changeset"""
    permission_classes = [CanApproveAIRecommendations]

    def post(self, request, changeset_id):
        """Execute changeset rollback operation"""
        from ..permissions import security_logger

        try:
            changeset = get_object_or_404(AIChangeSet, changeset_id=changeset_id)

            if not changeset.can_rollback():
                security_logger.log_security_violation(
                    request.user,
                    'changeset_rollback',
                    f'rollback_not_available: {changeset.status}'
                )
                return Response(
                    {
                        "error": "Changeset cannot be rolled back",
                        "status": changeset.status,
                        "rolled_back_at": changeset.rolled_back_at
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            rollback_reason = request.data.get('reason', 'Manual rollback requested')

            from ..integration.mapper import IntegrationAdapter
            adapter = IntegrationAdapter()

            result = adapter.rollback_changeset(
                changeset=changeset,
                rollback_reason=rollback_reason,
                rollback_user=request.user
            )

            security_logger.log_application_result(
                request.user,
                changeset.conversation_session.session_id,
                result.get('rollback_operations', []),
                success=result.get('success', False),
                error=result.get('error')
            )

            if result.get('success', False):
                return Response({
                    "message": "Changeset rolled back successfully",
                    "changeset_id": str(changeset.changeset_id),
                    "rolled_back_changes": result.get('rolled_back_count', 0),
                    "failed_rollbacks": result.get('failed_count', 0),
                    "rollback_complexity": changeset.get_rollback_complexity()
                })
            else:
                return Response(
                    {
                        "error": "Rollback failed",
                        "details": result.get('error'),
                        "partial_success": result.get('partial_success', False)
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"Changeset rollback error: {str(e)}")
            return Response(
                {"error": "Rollback operation failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChangeSetListView(APIView):
    """List changesets with filtering and rollback capabilities"""
    permission_classes = [CanApproveAIRecommendations]

    def get(self, request):
        """Retrieve changeset list with filters"""
        queryset = AIChangeSet.objects.all().order_by('-cdtz')

        # Apply filters
        queryset = self._apply_filters(request, queryset)

        # Pagination
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        page = int(request.query_params.get('page', 1))

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        # Serialize results
        changesets = self._serialize_changesets(page_obj.object_list)

        return Response({
            "changesets": changesets,
            "pagination": self._build_pagination_metadata(paginator, page, page_size, page_obj)
        })

    def _apply_filters(self, request, queryset):
        """Apply query filters"""
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        conversation_id = request.query_params.get('conversation_id')
        if conversation_id:
            queryset = queryset.filter(conversation_session__session_id=conversation_id)

        can_rollback_filter = request.query_params.get('can_rollback')
        if can_rollback_filter == 'true':
            queryset = queryset.filter(
                status__in=[AIChangeSet.StatusChoices.APPLIED, AIChangeSet.StatusChoices.PARTIALLY_APPLIED],
                rolled_back_at__isnull=True
            )

        return queryset

    def _serialize_changesets(self, changesets):
        """Serialize changeset data"""
        return [{
            "changeset_id": str(cs.changeset_id),
            "conversation_session_id": str(cs.conversation_session.session_id),
            "status": cs.status,
            "description": cs.description,
            "total_changes": cs.total_changes,
            "successful_changes": cs.successful_changes,
            "failed_changes": cs.failed_changes,
            "applied_at": cs.applied_at,
            "approved_by": cs.approved_by.email if cs.approved_by else None,
            "can_rollback": cs.can_rollback(),
            "rollback_complexity": cs.get_rollback_complexity(),
            "rolled_back_at": cs.rolled_back_at,
            "rolled_back_by": cs.rolled_back_by.email if cs.rolled_back_by else None
        } for cs in changesets]

    def _build_pagination_metadata(self, paginator, page, page_size, page_obj):
        """Build pagination metadata"""
        return {
            "page": page,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "total_count": paginator.count,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous()
        }


class ChangeSetDiffPreviewView(APIView):
    """Generate preview of changes that would be applied"""
    permission_classes = [CanApproveAIRecommendations]

    def post(self, request):
        """Generate diff preview for proposed changes"""
        from ..integration.mapper import IntegrationAdapter

        approved_items = request.data.get('approved_items', [])
        modifications = request.data.get('modifications', {})

        if not approved_items:
            return Response(
                {"error": "No items to preview"},
                status=status.HTTP_400_BAD_REQUEST
            )

        adapter = IntegrationAdapter()
        diff_preview = {
            'changes': [],
            'summary': {
                'total_changes': 0,
                'fields_modified': 0,
                'entities_affected': set()
            }
        }

        try:
            for item in approved_items:
                diff_entry = self._generate_diff_entry(item, modifications)
                diff_preview['changes'].append(diff_entry)
                diff_preview['summary']['entities_affected'].add(item.get('entity_type'))
                diff_preview['summary']['total_changes'] += 1
                diff_preview['summary']['fields_modified'] += len(diff_entry['fields_changed'])

        except Exception as e:
            logger.error(f"Error generating diff preview: {str(e)}")
            return Response(
                {"error": f"Failed to generate preview: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Convert set to list for JSON
        diff_preview['summary']['entities_affected'] = list(diff_preview['summary']['entities_affected'])

        return Response(diff_preview)

    def _generate_diff_entry(self, item, modifications):
        """Generate diff entry for single item"""
        entity_type = item.get('entity_type')
        entity_id = item.get('entity_id')
        changes = item.get('changes', {})

        # Apply user modifications
        if str(entity_id) in modifications:
            changes.update(modifications[str(entity_id)])

        # Get current state
        current_state = self._get_current_state(entity_type, entity_id)

        # Create diff entry
        diff_entry = {
            'entity_type': entity_type,
            'entity_id': entity_id,
            'operation': 'create' if current_state is None else 'update',
            'before': current_state,
            'after': changes,
            'fields_changed': self._calculate_field_changes(current_state, changes)
        }

        return diff_entry

    def _get_current_state(self, entity_type, entity_id):
        """Get current state of entity"""
        try:
            if entity_type == 'bt':
                bt = Bt.objects.get(id=entity_id)
                return {
                    'buname': bt.buname,
                    'bucode': bt.bucode,
                    'bupreferences': bt.bupreferences,
                    'enable': bt.enable
                }
            elif entity_type == 'shift':
                shift = Shift.objects.get(id=entity_id)
                return {
                    'shiftname': shift.shiftname,
                    'starttime': str(shift.starttime) if shift.starttime else None,
                    'endtime': str(shift.endtime) if shift.endtime else None,
                    'peoplecount': shift.peoplecount,
                    'captchafreq': shift.captchafreq
                }
            elif entity_type == 'typeassist':
                ta = TypeAssist.objects.get(id=entity_id)
                return {
                    'taname': ta.taname,
                    'tacode': ta.tacode,
                    'tatype': ta.tatype.id if ta.tatype else None,
                    'enable': ta.enable
                }
        except ObjectDoesNotExist:
            return None

        return None

    def _calculate_field_changes(self, current_state, changes):
        """Calculate field-level changes"""
        if current_state:
            return [
                {'field': field, 'old': current_state.get(field), 'new': new_value}
                for field, new_value in changes.items()
                if current_state.get(field) != new_value
            ]
        else:
            return [
                {'field': k, 'old': None, 'new': v}
                for k, v in changes.items()
            ]
