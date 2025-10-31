"""
Unified Sync Operation Interface - Common interface for REST sync endpoints

Provides a single service interface with adapter pattern for sync operations.

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling

MIGRATION NOTE (Oct 2025): Legacy query support removed. REST API only.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Protocol
from dataclasses import dataclass
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.utils import timezone

from .sync_engine_service import sync_engine
from .idempotency_service import IdempotencyService

logger = logging.getLogger(__name__)


@dataclass
class SyncRequest:
    """Standardized sync request structure."""
    user_id: str
    device_id: str
    idempotency_key: str
    data: Union[List[Dict], Dict]
    operation_type: str  # 'voice', 'behavioral', 'session', 'metrics', 'batch'
    endpoint: str
    metadata: Optional[Dict] = None


@dataclass
class SyncResponse:
    """Standardized sync response structure."""
    success: bool
    synced_items: int
    failed_items: int
    conflicts: List[Dict]
    errors: List[Dict]
    metrics: Dict[str, Any]
    server_timestamp: str
    idempotency_key: str
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SyncRequestValidator:
    """Validates sync requests for security and data integrity."""

    MAX_BATCH_SIZE = 1000
    MAX_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10MB

    @classmethod
    def validate_request(cls, request: SyncRequest) -> None:
        """
        Validate sync request for security and integrity.

        Args:
            request: Sync request to validate

        Raises:
            ValidationError: If request is invalid
        """
        # Validate required fields
        if not request.user_id or not request.device_id or not request.idempotency_key:
            raise ValidationError("Missing required fields: user_id, device_id, idempotency_key")

        # Validate data payload
        if not request.data:
            raise ValidationError("Empty sync data provided")

        # Check batch size limits
        if isinstance(request.data, list) and len(request.data) > cls.MAX_BATCH_SIZE:
            raise ValidationError(f"Batch size too large (max {cls.MAX_BATCH_SIZE} items)")

        # Check payload size limits (rough estimate)
        payload_str = str(request.data)
        if len(payload_str.encode('utf-8')) > cls.MAX_PAYLOAD_SIZE:
            raise ValidationError(f"Payload too large (max {cls.MAX_PAYLOAD_SIZE // (1024*1024)}MB)")

        # Validate operation type
        valid_operations = {'voice', 'behavioral', 'session', 'metrics', 'batch', 'domain'}
        if request.operation_type not in valid_operations:
            raise ValidationError(f"Invalid operation type: {request.operation_type}")


class SyncResponseFormatter:
    """Formats sync responses for different API types."""

    @staticmethod
    def format_for_rest(response: SyncResponse) -> Dict[str, Any]:
        """Format response for REST API."""
        return {
            'success': response.success,
            'synced_items': response.synced_items,
            'failed_items': response.failed_items,
            'conflicts': response.conflicts,
            'errors': response.errors,
            'metrics': response.metrics,
            'server_timestamp': response.server_timestamp,
            'idempotency_key': response.idempotency_key,
            'warnings': response.warnings,
        }

class SyncOperationInterface:
    """
    Unified interface for all sync operations.

    Provides single entry point for REST APIs.

    MIGRATION NOTE (Oct 2025): Legacy query layer removed - now REST-only interface.
    """

    def __init__(self):
        """Initialize sync operation interface."""
        self.validator = SyncRequestValidator()
        self.formatter = SyncResponseFormatter()

    def execute_sync_operation(
        self,
        request: SyncRequest,
        api_type: str = 'rest'
    ) -> Dict[str, Any]:
        """
        Execute sync operation with unified logic.

        Args:
            request: Standardized sync request
            api_type: API type for response formatting (default: 'rest').
                Non-'rest' values are treated as 'rest' for backward compatibility.

        Returns:
            Formatted sync response
        """
        start_time = time.time()

        if api_type != 'rest':
            logger.warning("Deprecated api_type '%s' supplied to execute_sync_operation; using REST format.", api_type)
            api_type = 'rest'

        try:
            # Step 1: Validate request
            self.validator.validate_request(request)

            # Step 2: Check idempotency
            cached_response = IdempotencyService.check_duplicate(request.idempotency_key)
            if cached_response:
                logger.info(f"Cache hit for {api_type}: {request.idempotency_key[:16]}...")
                return self._format_cached_response(cached_response, api_type)

            # Step 3: Execute operation based on type
            result = self._dispatch_operation(request)

            # Step 4: Calculate metrics
            duration_ms = (time.time() - start_time) * 1000

            # Step 5: Create standardized response
            response = SyncResponse(
                success=result.get('failed_items', 0) == 0,
                synced_items=result.get('synced_items', 0),
                failed_items=result.get('failed_items', 0),
                conflicts=result.get('conflicts', []),
                errors=result.get('errors', []),
                metrics={
                    'total_items': self._count_total_items(request.data),
                    'synced_items': result.get('synced_items', 0),
                    'failed_items': result.get('failed_items', 0),
                    'duration_ms': duration_ms,
                },
                server_timestamp=timezone.now().isoformat(),
                idempotency_key=request.idempotency_key,
                warnings=result.get('warnings', [])
            )

            # Step 6: Cache response
            formatted_response = self._format_response(response, api_type)
            self._cache_response(request, formatted_response)

            logger.info(
                f"{api_type.upper()} sync {request.operation_type}: "
                f"{response.synced_items} items, {duration_ms:.1f}ms"
            )

            return formatted_response

        except ValidationError as e:
            logger.warning(f"{api_type.upper()} sync validation error: {e}")
            return self._create_error_response(request, str(e), api_type)

        except DatabaseError as e:
            logger.error(f"{api_type.upper()} sync database error: {e}", exc_info=True)
            return self._create_error_response(request, "Database temporarily unavailable", api_type)

        except Exception as e:
            logger.error(f"{api_type.upper()} sync unexpected error: {e}", exc_info=True)
            return self._create_error_response(request, "Internal server error", api_type)

    def _dispatch_operation(self, request: SyncRequest) -> Dict[str, Any]:
        """
        Dispatch operation to appropriate sync engine method.

        Args:
            request: Sync request to process

        Returns:
            Raw sync engine result
        """
        payload_data = {'data': request.data}

        if request.operation_type == 'voice':
            return sync_engine.sync_voice_data(
                user_id=request.user_id,
                payload={'voice_data': request.data},
                device_id=request.device_id
            )

        elif request.operation_type == 'behavioral':
            return sync_engine.sync_behavioral_data(
                user_id=request.user_id,
                payload={'behavioral_data': request.data},
                device_id=request.device_id
            )

        elif request.operation_type == 'session':
            return sync_engine.sync_session_data(
                user_id=request.user_id,
                payload={'sessions': request.data},
                device_id=request.device_id
            )

        elif request.operation_type == 'metrics':
            return sync_engine.sync_metrics_data(
                user_id=request.user_id,
                payload={'metrics': request.data},
                device_id=request.device_id
            )

        elif request.operation_type == 'batch':
            return self._handle_batch_operation(request)

        elif request.operation_type == 'domain':
            return self._handle_domain_operation(request)

        else:
            raise ValidationError(f"Unsupported operation type: {request.operation_type}")

    def _handle_batch_operation(self, request: SyncRequest) -> Dict[str, Any]:
        """Handle batch sync operation containing multiple data types."""
        batch_data = request.data
        results = {}

        # Process each data type in the batch
        for data_type, items in batch_data.items():
            if data_type == 'voice_data' and items:
                results['voice_result'] = sync_engine.sync_voice_data(
                    user_id=request.user_id,
                    payload={'voice_data': items},
                    device_id=request.device_id
                )

            elif data_type == 'behavioral_data' and items:
                results['behavioral_result'] = sync_engine.sync_behavioral_data(
                    user_id=request.user_id,
                    payload={'behavioral_data': items},
                    device_id=request.device_id
                )

            elif data_type == 'session_data' and items:
                results['session_result'] = sync_engine.sync_session_data(
                    user_id=request.user_id,
                    payload={'sessions': items},
                    device_id=request.device_id
                )

        # Aggregate results
        total_synced = sum(r.get('synced_items', 0) for r in results.values())
        total_failed = sum(r.get('failed_items', 0) for r in results.values())

        return {
            'synced_items': total_synced,
            'failed_items': total_failed,
            'conflicts': [],
            'errors': [],
            'batch_results': results
        }

    def _handle_domain_operation(self, request: SyncRequest) -> Dict[str, Any]:
        """Handle domain-specific sync operation."""
        # This would integrate with domain sync services
        # For now, return basic structure
        return {
            'synced_items': 0,
            'failed_items': 0,
            'conflicts': [],
            'errors': [{'error': 'Domain sync not yet implemented'}]
        }

    def _count_total_items(self, data: Union[List, Dict]) -> int:
        """Count total items in sync request."""
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            # For batch operations, count items in all data types
            total = 0
            for value in data.values():
                if isinstance(value, list):
                    total += len(value)
            return total
        return 1

    def _format_response(self, response: SyncResponse, api_type: str) -> Dict[str, Any]:
        """Format response based on API type."""
        return self.formatter.format_for_rest(response)

    def _format_cached_response(self, cached_data: Dict, api_type: str) -> Dict[str, Any]:
        """Format cached response for API type."""
        return cached_data

    def _cache_response(self, request: SyncRequest, response: Dict[str, Any]) -> None:
        """Cache response for idempotency."""
        IdempotencyService.store_response(
            idempotency_key=request.idempotency_key,
            request_hash=request.idempotency_key,
            response_data=response,
            user_id=request.user_id,
            device_id=request.device_id,
            endpoint=request.endpoint,
            scope='batch'
        )

    def _create_error_response(self, request: SyncRequest, error_message: str, api_type: str) -> Dict[str, Any]:
        """Create standardized error response."""
        error_response = SyncResponse(
            success=False,
            synced_items=0,
            failed_items=self._count_total_items(request.data),
            conflicts=[],
            errors=[{
                'code': 'SYNC_ERROR',
                'message': error_message
            }],
            metrics={
                'total_items': self._count_total_items(request.data),
                'synced_items': 0,
                'failed_items': self._count_total_items(request.data),
                'duration_ms': 0,
            },
            server_timestamp=timezone.now().isoformat(),
            idempotency_key=request.idempotency_key
        )

        return self._format_response(error_response, api_type)


# Global instance
sync_operation_interface = SyncOperationInterface()
