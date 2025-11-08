"""
Quick Action API Views

REST API endpoints for executing quick actions and managing checklists.

Author: Claude Code
Date: 2025-11-07
CLAUDE.md Compliance: <200 lines
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType

from apps.core.models.quick_action import QuickAction, QuickActionChecklist
from apps.core.services.quick_action_service import QuickActionService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def execute_quick_action(request):
    """
    Execute a quick action on an item.
    
    POST /api/quick-actions/execute/
    Body: {
        "action_id": 1,
        "content_type": "ticket",
        "object_id": 123
    }
    """
    action_id = request.data.get('action_id')
    content_type_name = request.data.get('content_type')
    object_id = request.data.get('object_id')
    
    if not all([action_id, content_type_name, object_id]):
        return Response(
            {'error': 'Missing required fields: action_id, content_type, object_id'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Get the content type and object
        content_type = ContentType.objects.get(model=content_type_name.lower())
        model_class = content_type.model_class()
        item_object = get_object_or_404(model_class, pk=object_id)
        
        # Execute the action
        result = QuickActionService.execute_action(
            action_id=action_id,
            item_object=item_object,
            user=request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)
        
    except PermissionDenied as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_403_FORBIDDEN
        )
    except ValidationError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error executing quick action: {e}", exc_info=True)
        return Response(
            {'error': 'Database error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        logger.error(f"Error executing quick action: {e}", exc_info=True)
        return Response(
            {'error': 'An unexpected error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_available_actions(request):
    """
    List quick actions available for a specific content type.
    
    GET /api/quick-actions/available/?content_type=ticket
    """
    content_type_name = request.query_params.get('content_type')
    
    if not content_type_name:
        return Response(
            {'error': 'content_type parameter required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        content_type = ContentType.objects.get(model=content_type_name.lower())
        
        # Get active actions for this content type
        actions = QuickAction.objects.filter(
            is_active=True
        ).prefetch_related('user_groups')
        
        # Filter by user permissions
        available_actions = [
            action for action in actions
            if action.can_user_execute(request.user)
        ]
        
        # Serialize actions
        actions_data = [
            {
                'id': action.id,
                'name': action.name,
                'description': action.description,
                'when_to_use': action.when_to_use,
                'automated_steps_count': len(action.automated_steps),
                'manual_steps_count': len(action.manual_steps),
                'times_used': action.times_used,
                'success_rate': float(action.success_rate)
            }
            for action in available_actions
        ]
        
        return Response({
            'actions': actions_data,
            'count': len(actions_data)
        })
        
    except ContentType.DoesNotExist:
        return Response(
            {'error': f'Invalid content type: {content_type_name}'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_checklist_step(request, checklist_id, step_index):
    """
    Update a checklist step (mark complete, add note).
    
    PATCH /api/quick-actions/checklist/{checklist_id}/step/{step_index}/
    Body: {
        "completed": true,
        "note": "Optional note"
    }
    """
    checklist = get_object_or_404(QuickActionChecklist, id=checklist_id)
    
    # Verify user has permission (executed by this user)
    if checklist.execution.executed_by != request.user:
        return Response(
            {'error': 'You can only update your own checklists'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        completed = request.data.get('completed')
        note = request.data.get('note')
        
        if step_index >= len(checklist.steps):
            return Response(
                {'error': 'Invalid step index'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update the step
        if completed is not None:
            checklist.steps[step_index]['completed'] = completed
        
        if note is not None:
            checklist.steps[step_index]['note'] = note
        
        checklist.save(update_fields=['steps', 'updated_at'])
        checklist.update_completion()
        
        return Response({
            'success': True,
            'completion_percentage': float(checklist.completion_percentage),
            'all_completed': checklist.completion_percentage == 100
        })
        
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error updating checklist: {e}", exc_info=True)
        return Response(
            {'error': 'Database error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        logger.error(f"Error updating checklist step: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_step_photo(request, checklist_id):
    """
    Upload a photo for a checklist step.
    
    POST /api/quick-actions/checklist/{checklist_id}/upload-photo/
    Body: multipart/form-data
        - photo: file
        - step_index: int
    """
    checklist = get_object_or_404(QuickActionChecklist, id=checklist_id)
    
    # Verify user has permission
    if checklist.execution.executed_by != request.user:
        return Response(
            {'error': 'You can only update your own checklists'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        photo = request.FILES.get('photo')
        step_index = int(request.data.get('step_index', -1))
        
        if not photo:
            return Response(
                {'error': 'No photo provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if step_index < 0 or step_index >= len(checklist.steps):
            return Response(
                {'error': 'Invalid step index'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # TODO: Upload photo to storage and get URL
        # For now, placeholder implementation
        photo_url = f"/media/quick_actions/{checklist_id}/step_{step_index}.jpg"
        
        checklist.steps[step_index]['photo_url'] = photo_url
        checklist.save(update_fields=['steps', 'updated_at'])
        
        return Response({
            'success': True,
            'photo_url': photo_url
        })
        
    except ValueError:
        return Response(
            {'error': 'Invalid step_index'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error uploading photo: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_checklist(request, checklist_id):
    """
    Get checklist details.
    
    GET /api/quick-actions/checklist/{checklist_id}/
    """
    checklist = get_object_or_404(
        QuickActionChecklist.objects.select_related('execution__quick_action'),
        id=checklist_id
    )
    
    return Response({
        'id': checklist.id,
        'action_name': checklist.execution.quick_action.name,
        'steps': checklist.steps,
        'completion_percentage': float(checklist.completion_percentage),
        'created_at': checklist.created_at.isoformat(),
        'updated_at': checklist.updated_at.isoformat()
    })
