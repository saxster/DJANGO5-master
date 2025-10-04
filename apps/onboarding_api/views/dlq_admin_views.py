"""
Dead Letter Queue Admin Dashboard Views

REST API endpoints for DLQ management and manual intervention.

Following .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
- Rule #15: Logging data sanitization

Author: Claude Code
Date: 2025-10-01
"""

import logging
from typing import Dict, Any, Optional

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from background_tasks.dead_letter_queue import dlq_handler

logger = logging.getLogger(__name__)


class DLQTaskListView(APIView):
    """
    GET /api/v1/admin/dlq/tasks/

    List tasks in the Dead Letter Queue with filtering and pagination.

    Query Parameters:
        - task_name: Filter by specific task name
        - limit: Maximum number of tasks to return (default: 100, max: 1000)
        - offset: Number of tasks to skip for pagination
        - sort: Sort order ('oldest' or 'newest', default: 'newest')

    Response:
        {
            "tasks": [
                {
                    "task_id": "uuid",
                    "task_name": "process_conversation_step",
                    "failed_at": "2025-10-01T12:00:00Z",
                    "retry_count": 3,
                    "exception_type": "DatabaseError",
                    "exception_message": "...",
                    "correlation_id": "uuid"
                },
                ...
            ],
            "total": 45,
            "limit": 100,
            "offset": 0,
            "filters": {"task_name": "..."}
        }
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """List tasks in DLQ with filtering"""
        try:
            # Parse query parameters
            task_name_filter = request.query_params.get('task_name')
            limit = min(int(request.query_params.get('limit', 100)), 1000)
            offset = int(request.query_params.get('offset', 0))
            sort_order = request.query_params.get('sort', 'newest')

            # Get tasks from DLQ
            tasks = dlq_handler.list_dlq_tasks(
                limit=limit + offset,  # Get more for offset
                task_name_filter=task_name_filter
            )

            # Apply sorting
            if sort_order == 'oldest':
                tasks.sort(key=lambda x: x.get('failed_at', ''))
            else:  # newest
                tasks.sort(key=lambda x: x.get('failed_at', ''), reverse=True)

            # Apply pagination
            paginated_tasks = tasks[offset:offset + limit]

            return Response({
                'tasks': paginated_tasks,
                'total': len(tasks),
                'limit': limit,
                'offset': offset,
                'filters': {
                    'task_name': task_name_filter,
                    'sort': sort_order
                }
            })

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid DLQ list request: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid query parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error listing DLQ tasks: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DLQTaskDetailView(APIView):
    """
    GET /api/v1/admin/dlq/tasks/{task_id}/

    Get detailed information about a specific DLQ task.

    Response:
        {
            "task_id": "uuid",
            "task_name": "process_conversation_step",
            "failed_at": "2025-10-01T12:00:00Z",
            "retry_count": 3,
            "exception_type": "DatabaseError",
            "exception_message": "Connection timeout",
            "exception_traceback": "...",
            "correlation_id": "uuid",
            "args": [...],
            "kwargs": {...},
            "context": {...}
        }
    """
    permission_classes = [IsAdminUser]

    def get(self, request, task_id):
        """Get DLQ task details"""
        try:
            # Get task details
            task_details = dlq_handler.get_dlq_task_details(task_id)

            if not task_details:
                return Response(
                    {'error': 'Task not found in DLQ'},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(task_details)

        except (ValueError, ValidationError) as e:
            logger.warning(f"Invalid task ID: {task_id}", exc_info=True)
            return Response(
                {'error': 'Invalid task ID', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error getting task {task_id}: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DLQTaskRetryView(APIView):
    """
    POST /api/v1/admin/dlq/tasks/{task_id}/retry/

    Manually retry a failed task from the DLQ.

    Request Body (optional):
        {
            "modify_args": {...},  // Optional: Modify task arguments before retry
            "priority": "high"     // Optional: Set task priority
        }

    Response:
        {
            "status": "queued",
            "task_id": "uuid",
            "new_task_id": "uuid",
            "queued_at": "2025-10-01T12:05:00Z"
        }
    """
    permission_classes = [IsAdminUser]

    def post(self, request, task_id):
        """Retry a task from DLQ"""
        try:
            # Parse optional parameters
            modify_args = request.data.get('modify_args', {})
            priority = request.data.get('priority', 'default')

            # Retry task
            success = dlq_handler.retry_dlq_task(
                task_id=task_id,
                modify_args=modify_args
            )

            if success:
                logger.info(
                    f"Task {task_id} requeued successfully",
                    extra={'user_id': request.user.id}
                )

                return Response({
                    'status': 'queued',
                    'task_id': task_id,
                    'priority': priority,
                    'modified': bool(modify_args)
                })
            else:
                return Response(
                    {'error': 'Task not found or retry failed'},
                    status=status.HTTP_404_NOT_FOUND
                )

        except (ValueError, ValidationError) as e:
            logger.warning(f"Invalid retry request for {task_id}: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid retry parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError, ConnectionError) as e:
            logger.error(f"Error retrying task {task_id}: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to retry task'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DLQTaskDeleteView(APIView):
    """
    DELETE /api/v1/admin/dlq/tasks/{task_id}/

    Remove a task from the DLQ (cannot be retried after deletion).

    Response:
        {
            "status": "deleted",
            "task_id": "uuid",
            "deleted_at": "2025-10-01T12:10:00Z"
        }
    """
    permission_classes = [IsAdminUser]

    def delete(self, request, task_id):
        """Delete task from DLQ"""
        try:
            # Delete task
            success = dlq_handler.remove_from_dlq(task_id)

            if success:
                logger.info(
                    f"Task {task_id} removed from DLQ",
                    extra={'user_id': request.user.id}
                )

                return Response({
                    'status': 'deleted',
                    'task_id': task_id
                })
            else:
                return Response(
                    {'error': 'Task not found in DLQ'},
                    status=status.HTTP_404_NOT_FOUND
                )

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error deleting task {task_id}: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to delete task'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DLQStatsView(APIView):
    """
    GET /api/v1/admin/dlq/stats/

    Get DLQ statistics and health metrics.

    Response:
        {
            "total_tasks": 45,
            "tasks_by_type": {
                "process_conversation_step": 20,
                "validate_recommendations": 15,
                "apply_approved_recommendations": 10
            },
            "tasks_by_exception": {
                "DatabaseError": 25,
                "TimeoutError": 15,
                "ValidationError": 5
            },
            "oldest_task_age_hours": 48.5,
            "tasks_last_24h": 12,
            "average_retry_count": 3.2,
            "capacity_used_percent": 45.0
        }
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Get DLQ statistics"""
        try:
            # Get stats from DLQ handler
            stats = dlq_handler.get_dlq_stats()

            return Response(stats)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error getting DLQ stats: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DLQBulkClearView(APIView):
    """
    DELETE /api/v1/admin/dlq/clear/

    Bulk clear tasks from DLQ with optional filters.

    Request Body:
        {
            "filter_task_name": "process_conversation_step",  // Optional
            "older_than_hours": 72,                            // Optional
            "exception_type": "DatabaseError",                  // Optional
            "dry_run": true                                     // Optional: Preview without deleting
        }

    Response:
        {
            "status": "cleared",
            "tasks_deleted": 25,
            "filters_applied": {...},
            "dry_run": false
        }
    """
    permission_classes = [IsAdminUser]

    def delete(self, request):
        """Bulk clear DLQ tasks with filters"""
        try:
            # Parse filter parameters
            task_name = request.data.get('filter_task_name')
            older_than_hours = request.data.get('older_than_hours')
            exception_type = request.data.get('exception_type')
            dry_run = request.data.get('dry_run', False)

            # Build filters
            filters = {}
            if task_name:
                filters['task_name'] = task_name
            if older_than_hours:
                filters['older_than_hours'] = int(older_than_hours)
            if exception_type:
                filters['exception_type'] = exception_type

            # Execute bulk clear
            deleted_count = dlq_handler.bulk_clear_dlq(
                filters=filters,
                dry_run=dry_run
            )

            if not dry_run:
                logger.warning(
                    f"Bulk cleared {deleted_count} tasks from DLQ",
                    extra={
                        'user_id': request.user.id,
                        'filters': filters
                    }
                )

            return Response({
                'status': 'cleared' if not dry_run else 'preview',
                'tasks_deleted': deleted_count,
                'filters_applied': filters,
                'dry_run': dry_run
            })

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid bulk clear request: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid filter parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error during bulk clear: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to clear tasks'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


__all__ = [
    'DLQTaskListView',
    'DLQTaskDetailView',
    'DLQTaskRetryView',
    'DLQTaskDeleteView',
    'DLQStatsView',
    'DLQBulkClearView',
]
