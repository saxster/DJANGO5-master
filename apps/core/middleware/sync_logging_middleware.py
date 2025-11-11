"""
Sync Logging Middleware for ML Conflict Prediction

Instruments all sync operations (POST/PUT/PATCH) to create SyncLog entries
for ML-based conflict prediction and detection.

Architecture:
- Captures sync operations from mobile/web clients
- Records field changes with old/new values
- Generates sync session IDs
- Triggers conflict detection asynchronously

Created: November 2025 (Ultrathink Phase 4 - ML Conflict Prediction)
"""

import json
import logging
import uuid
from typing import Optional, Dict, Any
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError

from apps.core.models.sync_tracking import SyncLog
from apps.core.services.conflict_detector import ConflictDetector

logger = logging.getLogger(__name__)


class SyncLoggingMiddleware:
    """
    Middleware to log all sync operations for ML conflict prediction.

    Tracks:
    - Task sync operations (create/update/delete)
    - WorkOrder sync operations
    - Asset sync operations
    - Other configured entity types

    Purpose:
    - ML training data collection
    - Real-time conflict detection
    - Sync pattern analysis
    """

    # Entity types to track for conflict prediction
    TRACKED_ENTITIES = {
        'Task': 'apps.activity.models.Task',
        'WorkOrder': 'apps.work_order_management.models.WorkOrder',
        'Asset': 'apps.inventory.models.Asset',
        'Attendance': 'apps.attendance.models.Attendance',
    }

    # API endpoints that represent sync operations
    SYNC_ENDPOINTS = [
        '/api/v2/tasks/',
        '/api/v2/work-orders/',
        '/api/v2/assets/',
        '/api/v2/attendance/',
        # Legacy V1 endpoints still used by mobile
        '/api/v1/tasks/',
        '/api/v1/work-orders/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and log sync operations.

        Args:
            request: HTTP request

        Returns:
            HTTP response
        """
        # Process request
        response = self.get_response(request)

        # Log sync operation if applicable
        if self._is_sync_operation(request, response):
            try:
                self._log_sync_operation(request, response)
            except Exception as e:
                # Don't break request flow for logging failures
                self.logger.error(
                    f"Failed to log sync operation: {e}",
                    exc_info=True,
                    extra={
                        'path': request.path,
                        'method': request.method,
                        'user_id': getattr(request.user, 'id', None)
                    }
                )

        return response

    def _is_sync_operation(self, request: HttpRequest, response: HttpResponse) -> bool:
        """
        Determine if request is a sync operation to track.

        Args:
            request: HTTP request
            response: HTTP response

        Returns:
            True if this is a trackable sync operation
        """
        # Only track authenticated requests
        if not request.user or not request.user.is_authenticated:
            return False

        # Only track write operations
        if request.method not in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return False

        # Only track successful operations
        if not (200 <= response.status_code < 300):
            return False

        # Check if path matches sync endpoints
        for endpoint in self.SYNC_ENDPOINTS:
            if request.path.startswith(endpoint):
                return True

        return False

    def _log_sync_operation(self, request: HttpRequest, response: HttpResponse):
        """
        Create SyncLog entry for this operation.

        Args:
            request: HTTP request
            response: HTTP response
        """
        # Extract entity info from request
        entity_info = self._extract_entity_info(request, response)
        if not entity_info:
            return

        # Determine operation type
        operation = self._determine_operation(request.method)

        # Extract field changes
        field_changes = self._extract_field_changes(request, entity_info)

        # Get or create sync session ID
        sync_session_id = self._get_sync_session_id(request)

        # Extract device metadata
        device_metadata = self._extract_device_metadata(request)

        try:
            # Create SyncLog entry
            sync_log = SyncLog.objects.create(
                tenant=request.user.tenant,
                user=request.user,
                entity_type=entity_info['entity_type'],
                entity_id=entity_info['entity_id'],
                operation=operation,
                field_changes=field_changes,
                timestamp=timezone.now(),
                device_id=device_metadata.get('device_id', ''),
                sync_session_id=sync_session_id,
                app_version=device_metadata.get('app_version', ''),
                network_type=device_metadata.get('network_type', 'unknown')
            )

            self.logger.info(
                f"Sync operation logged: {entity_info['entity_type']}:{entity_info['entity_id']}",
                extra={
                    'sync_log_id': sync_log.id,
                    'operation': operation,
                    'user_id': request.user.id,
                    'entity_type': entity_info['entity_type'],
                    'entity_id': entity_info['entity_id']
                }
            )

            # Trigger asynchronous conflict detection
            self._trigger_conflict_detection(sync_log)

        except (DatabaseError, Exception) as e:
            self.logger.error(
                f"Failed to create SyncLog: {e}",
                exc_info=True,
                extra={'entity_info': entity_info}
            )

    def _extract_entity_info(self, request: HttpRequest, response: HttpResponse) -> Optional[Dict[str, Any]]:
        """
        Extract entity type and ID from request/response.

        Args:
            request: HTTP request
            response: HTTP response

        Returns:
            Dict with entity_type and entity_id, or None
        """
        # Try to extract from response body (create/update operations)
        try:
            if hasattr(response, 'data'):
                response_data = response.data
                if isinstance(response_data, dict) and 'id' in response_data:
                    entity_id = response_data['id']
                    entity_type = self._determine_entity_type(request.path)
                    if entity_type and entity_id:
                        return {'entity_type': entity_type, 'entity_id': entity_id}
        except Exception:
            pass

        # Try to extract from URL path (update/delete operations)
        try:
            path_parts = request.path.strip('/').split('/')
            if len(path_parts) >= 3:
                # Pattern: /api/v2/tasks/123/
                entity_id_str = path_parts[-1] if path_parts[-1] else path_parts[-2]
                if entity_id_str.isdigit():
                    entity_id = int(entity_id_str)
                    entity_type = self._determine_entity_type(request.path)
                    if entity_type and entity_id:
                        return {'entity_type': entity_type, 'entity_id': entity_id}
        except Exception:
            pass

        return None

    def _determine_entity_type(self, path: str) -> Optional[str]:
        """
        Determine entity type from API path.

        Args:
            path: Request path

        Returns:
            Entity type name or None
        """
        path_lower = path.lower()

        if '/tasks/' in path_lower:
            return 'Task'
        elif '/work-orders/' in path_lower:
            return 'WorkOrder'
        elif '/assets/' in path_lower:
            return 'Asset'
        elif '/attendance/' in path_lower:
            return 'Attendance'

        return None

    def _determine_operation(self, method: str) -> str:
        """
        Map HTTP method to operation type.

        Args:
            method: HTTP method

        Returns:
            Operation type (create/update/delete)
        """
        if method == 'POST':
            return 'create'
        elif method in ['PUT', 'PATCH']:
            return 'update'
        elif method == 'DELETE':
            return 'delete'
        return 'update'  # Default

    def _extract_field_changes(self, request: HttpRequest, entity_info: Dict[str, Any]) -> Dict[str, Dict]:
        """
        Extract field changes from request body.

        Args:
            request: HTTP request
            entity_info: Entity information

        Returns:
            Dict mapping field names to {old, new} values
        """
        field_changes = {}

        try:
            # Parse request body
            if request.body:
                request_data = json.loads(request.body)

                # For updates, fetch current values
                if entity_info and request.method in ['PUT', 'PATCH']:
                    old_values = self._fetch_current_values(
                        entity_info['entity_type'],
                        entity_info['entity_id'],
                        list(request_data.keys())
                    )
                else:
                    old_values = {}

                # Build field changes
                for field, new_value in request_data.items():
                    field_changes[field] = {
                        'old': old_values.get(field),
                        'new': new_value
                    }

        except (json.JSONDecodeError, Exception) as e:
            self.logger.debug(f"Could not extract field changes: {e}")

        return field_changes

    def _fetch_current_values(self, entity_type: str, entity_id: int, fields: list) -> Dict:
        """
        Fetch current field values from database.

        Args:
            entity_type: Entity type name
            entity_id: Entity ID
            fields: List of field names

        Returns:
            Dict of current field values
        """
        try:
            from django.apps import apps

            # Get model class
            model_class = None
            for tracked_entity, model_path in self.TRACKED_ENTITIES.items():
                if tracked_entity == entity_type:
                    app_label, model_name = model_path.rsplit('.', 1)
                    model_class = apps.get_model(app_label.replace('apps.', '').replace('.models', ''), model_name)
                    break

            if not model_class:
                return {}

            # Fetch instance
            instance = model_class.objects.get(pk=entity_id)

            # Extract field values
            values = {}
            for field in fields:
                try:
                    values[field] = getattr(instance, field, None)
                    # Convert to JSON-serializable format
                    if hasattr(values[field], 'isoformat'):
                        values[field] = values[field].isoformat()
                except AttributeError:
                    pass

            return values

        except (ObjectDoesNotExist, Exception):
            return {}

    def _get_sync_session_id(self, request: HttpRequest) -> uuid.UUID:
        """
        Get or generate sync session ID.

        Args:
            request: HTTP request

        Returns:
            Sync session UUID
        """
        # Check for session ID in headers (mobile apps should send this)
        session_id_header = request.headers.get('X-Sync-Session-ID')
        if session_id_header:
            try:
                return uuid.UUID(session_id_header)
            except ValueError:
                pass

        # Generate new session ID
        return uuid.uuid4()

    def _extract_device_metadata(self, request: HttpRequest) -> Dict[str, str]:
        """
        Extract device metadata from request headers.

        Args:
            request: HTTP request

        Returns:
            Dict with device metadata
        """
        return {
            'device_id': request.headers.get('X-Device-ID', ''),
            'app_version': request.headers.get('X-App-Version', ''),
            'network_type': request.headers.get('X-Network-Type', 'unknown')
        }

    def _trigger_conflict_detection(self, sync_log: SyncLog):
        """
        Trigger asynchronous conflict detection for this sync operation.

        Args:
            sync_log: SyncLog instance
        """
        try:
            # Check for concurrent edits
            ConflictDetector.detect_concurrent_edits(sync_log)
        except Exception as e:
            self.logger.error(
                f"Conflict detection failed for sync_log {sync_log.id}: {e}",
                exc_info=True
            )
