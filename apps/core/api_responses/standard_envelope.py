"""
Standard API Response Envelopes

Provides consistent, type-safe response structures for all API surfaces.

Compliance with .claude/rules.md:
- Rule #7: Classes < 150 lines
- Rule #10: Comprehensive validation
- Type-safe Generic types for Kotlin codegen

For Kotlin codegen:
    data class APIResponse<T>(
        val success: Boolean,
        val data: T?,
        val errors: List<APIError>?,
        val meta: APIMeta
    )
"""

from pydantic import BaseModel, Field, field_validator
from typing import Generic, TypeVar, Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID, uuid4
from django.utils import timezone


# Type variable for generic response data
T = TypeVar('T')


# ============================================================================
# ERROR MODELS
# ============================================================================

class APIError(BaseModel):
    """
    Standard error detail structure.

    Provides detailed validation/business error information.

    Maps to Kotlin:
        data class APIError(
            val field: String,
            val message: String,
            val code: String,
            val details: Map<String, Any>?
        )
    """
    field: str = Field(..., description="Field that caused the error (or '__all__' for general errors)")
    message: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code (VALIDATION_ERROR, REQUIRED, etc.)")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")

    @field_validator('code')
    @classmethod
    def validate_code_format(cls, v: str) -> str:
        """Validate error code is uppercase with underscores."""
        return v.upper()


# ============================================================================
# METADATA MODELS
# ============================================================================

class PaginationMeta(BaseModel):
    """
    Pagination metadata for list responses.

    Maps to Kotlin: data class PaginationMeta
    """
    total_count: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(default=False, description="Whether next page exists")
    has_previous: bool = Field(default=False, description="Whether previous page exists")
    next_page: Optional[int] = Field(None, description="Next page number")
    previous_page: Optional[int] = Field(None, description="Previous page number")


class APIMeta(BaseModel):
    """
    Standard metadata for all API responses.

    Provides request tracking and debugging information.

    Maps to Kotlin: data class APIMeta
    """
    request_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique request ID (UUID)")
    timestamp: datetime = Field(default_factory=timezone.now, description="Server processing timestamp")
    version: str = Field(default='1.0', description="API version")
    pagination: Optional[PaginationMeta] = Field(None, description="Pagination metadata (for list responses)")
    execution_time_ms: Optional[float] = Field(None, ge=0, description="Request execution time in milliseconds")


# ============================================================================
# RESPONSE ENVELOPE (GENERIC)
# ============================================================================

class APIResponse(BaseModel, Generic[T]):
    """
    Standard envelope for ALL API responses (REST, legacy API, WebSocket).

    Provides consistent structure for success and error responses.

    Type-safe with generics for Kotlin/Swift codegen:
        APIResponse<VoiceSyncResponse>
        APIResponse<TaskListResponse>

    Maps to Kotlin:
        data class APIResponse<T>(
            val success: Boolean,
            val data: T?,
            val errors: List<APIError>?,
            val meta: APIMeta
        )

    Example Success:
        {
          "success": true,
          "data": { "id": 123, "name": "Task 1" },
          "errors": null,
          "meta": { "request_id": "abc-123", "timestamp": "2025-10-05T12:00:00Z" }
        }

    Example Error:
        {
          "success": false,
          "data": null,
          "errors": [
            { "field": "device_id", "message": "Required field", "code": "REQUIRED" }
          ],
          "meta": { "request_id": "abc-456", "timestamp": "2025-10-05T12:01:00Z" }
        }
    """
    success: bool = Field(..., description="Whether the request succeeded")
    data: Optional[T] = Field(None, description="Response data (null for errors)")
    errors: Optional[List[APIError]] = Field(None, description="Error details (null for success)")
    meta: APIMeta = Field(default_factory=APIMeta, description="Request metadata")

    @field_validator('errors')
    @classmethod
    def validate_errors_with_success(cls, v: Optional[List[APIError]], info) -> Optional[List[APIError]]:
        """Ensure errors is None when success=True."""
        if info.data.get('success') and v:
            raise ValueError("errors must be None when success=True")
        return v

    @field_validator('data')
    @classmethod
    def validate_data_with_errors(cls, v: Optional[T], info) -> Optional[T]:
        """Ensure data is None when success=False."""
        if not info.data.get('success') and v is not None:
            raise ValueError("data must be None when success=False")
        return v


# ============================================================================
# CONVENIENCE TYPE ALIASES
# ============================================================================

class ErrorResponse(APIResponse[None]):
    """
    Convenience type for error responses (data is always None).

    Maps to Kotlin: typealias ErrorResponse = APIResponse<Nothing?>
    """
    success: Literal[False] = Field(default=False)
    data: Literal[None] = Field(default=None)
    errors: List[APIError] = Field(..., min_items=1)


class SuccessResponse(BaseModel, Generic[T]):
    """
    Convenience type for success responses (errors is always None).

    Maps to Kotlin: typealias SuccessResponse<T> = APIResponse<T>
    """
    success: Literal[True] = Field(default=True)
    data: T
    errors: Literal[None] = Field(default=None)
    meta: APIMeta = Field(default_factory=APIMeta)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_success_response(
    data: Any,
    meta: Optional[APIMeta] = None,
    execution_time_ms: Optional[float] = None
) -> Dict[str, Any]:
    """
    Create standard success response.

    Args:
        data: Response data
        meta: Custom metadata (optional)
        execution_time_ms: Request execution time

    Returns:
        Dictionary ready for DRF Response()

    Example:
        return Response(create_success_response(
            data={'id': 123, 'name': 'Test'},
            execution_time_ms=25.5
        ))
    """
    if meta is None:
        meta = APIMeta()

    if execution_time_ms is not None:
        meta.execution_time_ms = execution_time_ms

    response = APIResponse[Any](
        success=True,
        data=data,
        errors=None,
        meta=meta
    )

    return response.model_dump(exclude_none=True)


def create_error_response(
    errors: List[APIError],
    meta: Optional[APIMeta] = None,
    execution_time_ms: Optional[float] = None
) -> Dict[str, Any]:
    """
    Create standard error response.

    Args:
        errors: List of error details
        meta: Custom metadata (optional)
        execution_time_ms: Request execution time

    Returns:
        Dictionary ready for DRF Response()

    Example:
        return Response(
            create_error_response([
                APIError(field='device_id', message='Required', code='REQUIRED')
            ]),
            status=400
        )
    """
    if meta is None:
        meta = APIMeta()

    if execution_time_ms is not None:
        meta.execution_time_ms = execution_time_ms

    response = APIResponse[None](
        success=False,
        data=None,
        errors=errors,
        meta=meta
    )

    return response.model_dump(exclude_none=True)


def create_paginated_response(
    items: List[Any],
    total_count: int,
    page: int,
    page_size: int,
    execution_time_ms: Optional[float] = None
) -> Dict[str, Any]:
    """
    Create standard paginated response.

    Args:
        items: List of data items
        total_count: Total number of items (all pages)
        page: Current page number
        page_size: Items per page
        execution_time_ms: Request execution time

    Returns:
        Dictionary ready for DRF Response()
    """
    total_pages = (total_count + page_size - 1) // page_size
    has_next = page < total_pages
    has_previous = page > 1

    pagination = PaginationMeta(
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
        next_page=page + 1 if has_next else None,
        previous_page=page - 1 if has_previous else None,
    )

    meta = APIMeta(pagination=pagination)
    if execution_time_ms is not None:
        meta.execution_time_ms = execution_time_ms

    response = APIResponse[List[Any]](
        success=True,
        data=items,
        errors=None,
        meta=meta
    )

    return response.model_dump(exclude_none=True)


__all__ = [
    'APIError',
    'APIMeta',
    'PaginationMeta',
    'APIResponse',
    'ErrorResponse',
    'SuccessResponse',
    'create_success_response',
    'create_error_response',
    'create_paginated_response',
]
