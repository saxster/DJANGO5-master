"""
Frontend-Friendly ViewSet Mixins
Enhanced DRF viewsets optimized for modern frontend consumption
Includes standardized responses, error handling, and performance optimization
"""

import time
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
from django.http import Http404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from apps.core.serializers.frontend_serializers import FrontendPagination, FrontendResponseMixin


class FrontendViewMixin(FrontendResponseMixin):
    """
    Base mixin for frontend-friendly API views
    """
    pagination_class = FrontendPagination

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._request_start_time = time.time()

    def dispatch(self, request, *args, **kwargs):
        """
        Enhanced dispatch with performance tracking
        """
        self._request_start_time = time.time()
        response = super().dispatch(request, *args, **kwargs)

        # Add performance headers
        processing_time = time.time() - self._request_start_time
        response['X-Processing-Time'] = f"{processing_time:.3f}s"

        return response

    def get_serializer_context(self):
        """
        Enhanced serializer context with frontend optimizations
        """
        context = super().get_serializer_context()
        context.update({
            'include_metadata': self.should_include_metadata(),
            'include_performance': self.should_include_performance(),
            'use_cache': self.should_use_cache(),
        })
        return context

    def should_include_metadata(self):
        """
        Determine if metadata should be included in response
        """
        return self.request.query_params.get('include_meta', 'true').lower() == 'true'

    def should_include_performance(self):
        """
        Determine if performance metrics should be included
        """
        return (
            self.request.query_params.get('debug', 'false').lower() == 'true' or
            getattr(self.request.user, 'is_staff', False)
        )

    def should_use_cache(self):
        """
        Determine if caching should be used
        """
        return self.request.method == 'GET' and not self.request.query_params.get('no_cache')

    def get_performance_metadata(self):
        """
        Get performance metadata for response
        """
        return {
            'request_time_ms': round((time.time() - self._request_start_time) * 1000, 2),
            'cache_enabled': self.should_use_cache(),
        }

    def handle_exception(self, exc):
        """
        Enhanced exception handling with frontend-friendly errors
        """
        if isinstance(exc, ValidationError):
            return self.handle_validation_error(exc)
        elif isinstance(exc, Http404):
            return self.handle_not_found_error(exc)
        else:
            return self.handle_generic_error(exc)

    def handle_validation_error(self, exc):
        """
        Handle validation errors with field-specific context
        """
        error_details = []

        if hasattr(exc, 'detail'):
            if isinstance(exc.detail, dict):
                for field, errors in exc.detail.items():
                    if isinstance(errors, list):
                        for error in errors:
                            error_details.append({
                                'field': field,
                                'code': getattr(error, 'code', 'invalid'),
                                'message': str(error),
                                'type': 'validation'
                            })
            elif isinstance(exc.detail, list):
                for error in exc.detail:
                    error_details.append({
                        'field': None,
                        'code': getattr(error, 'code', 'invalid'),
                        'message': str(error),
                        'type': 'validation'
                    })

        envelope = self.get_response_envelope(
            data=None,
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Validation failed",
            errors=error_details,
            error_code='VALIDATION_ERROR',
            request=self.request,
            performance=self.get_performance_metadata()
        )

        return Response(envelope, status=status.HTTP_400_BAD_REQUEST)

    def handle_not_found_error(self, exc):
        """
        Handle 404 errors with helpful context
        """
        envelope = self.get_response_envelope(
            data=None,
            status_code=status.HTTP_404_NOT_FOUND,
            message="The requested resource was not found",
            errors=[{
                'type': 'not_found',
                'code': 'RESOURCE_NOT_FOUND',
                'message': str(exc),
                'help': 'Check the resource ID and try again'
            }],
            error_code='NOT_FOUND',
            request=self.request,
            performance=self.get_performance_metadata()
        )

        return Response(envelope, status=status.HTTP_404_NOT_FOUND)

    def handle_generic_error(self, exc):
        """
        Handle generic errors with safe error reporting
        """
        # Log full error details for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"API Error: {exc}", exc_info=True)

        # Return safe error message to frontend
        envelope = self.get_response_envelope(
            data=None,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An unexpected error occurred",
            errors=[{
                'type': 'server_error',
                'code': 'INTERNAL_ERROR',
                'message': 'Please try again later or contact support',
                'help': 'If this problem persists, please report it to the system administrator'
            }],
            error_code='INTERNAL_ERROR',
            request=self.request,
            performance=self.get_performance_metadata()
        )

        return Response(envelope, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SearchableMixin:
    """
    Mixin to add search functionality to viewsets
    """

    search_fields = []  # Override in subclasses
    search_param = 'search'

    def get_queryset(self):
        """
        Enhanced queryset with search functionality
        """
        queryset = super().get_queryset()
        search_query = self.request.query_params.get(self.search_param)

        if search_query and self.search_fields:
            search_filter = Q()
            for field in self.search_fields:
                search_filter |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(search_filter)

        return queryset

    @action(detail=False, methods=['get'])
    def search_suggestions(self, request):
        """
        Get search suggestions for autocomplete
        """
        query = request.query_params.get('q', '').strip()

        if len(query) < 2:
            return Response(self.get_response_envelope(
                data=[],
                message="Query too short for suggestions"
            ))

        # Get suggestions based on search fields
        suggestions = []
        queryset = self.get_queryset()

        for field in self.search_fields[:3]:  # Limit to first 3 search fields
            field_suggestions = (
                queryset.filter(**{f"{field}__icontains": query})
                .values_list(field, flat=True)
                .distinct()[:5]
            )
            suggestions.extend([
                {'value': suggestion, 'field': field}
                for suggestion in field_suggestions
            ])

        return Response(self.get_response_envelope(
            data=suggestions[:10],  # Limit total suggestions
            message=f"Found {len(suggestions)} suggestions"
        ))


class FilterableMixin:
    """
    Mixin to add advanced filtering to viewsets
    """

    filter_fields = {}  # Override in subclasses: {'field_name': 'filter_type'}
    date_range_fields = []  # Fields that support date range filtering

    def get_queryset(self):
        """
        Enhanced queryset with filtering
        """
        queryset = super().get_queryset()
        queryset = self.apply_filters(queryset)
        return queryset

    def apply_filters(self, queryset):
        """
        Apply filters based on query parameters
        """
        for field_name, filter_type in self.filter_fields.items():
            param_value = self.request.query_params.get(field_name)
            if param_value:
                queryset = self.apply_field_filter(queryset, field_name, param_value, filter_type)

        # Apply date range filters
        for field_name in self.date_range_fields:
            queryset = self.apply_date_range_filter(queryset, field_name)

        return queryset

    def apply_field_filter(self, queryset, field_name, value, filter_type):
        """
        Apply specific field filter
        """
        if filter_type == 'exact':
            return queryset.filter(**{field_name: value})
        elif filter_type == 'icontains':
            return queryset.filter(**{f"{field_name}__icontains": value})
        elif filter_type == 'in':
            values = value.split(',')
            return queryset.filter(**{f"{field_name}__in": values})
        elif filter_type == 'boolean':
            bool_value = value.lower() in ('true', '1', 'yes')
            return queryset.filter(**{field_name: bool_value})

        return queryset

    def apply_date_range_filter(self, queryset, field_name):
        """
        Apply date range filter
        """
        start_date = self.request.query_params.get(f"{field_name}_start")
        end_date = self.request.query_params.get(f"{field_name}_end")

        if start_date:
            queryset = queryset.filter(**{f"{field_name}__gte": start_date})
        if end_date:
            queryset = queryset.filter(**{f"{field_name}__lte": end_date})

        return queryset

    @action(detail=False, methods=['get'])
    def filter_options(self, request):
        """
        Get available filter options for frontend filter UI
        """
        options = {}

        for field_name, filter_type in self.filter_fields.items():
            if filter_type == 'in':
                # Get distinct values for multi-select filters
                distinct_values = (
                    self.get_queryset()
                    .values_list(field_name, flat=True)
                    .distinct()
                    .order_by(field_name)
                )
                options[field_name] = [
                    {'value': val, 'label': str(val)}
                    for val in distinct_values if val
                ]

        return Response(self.get_response_envelope(
            data=options,
            message="Filter options retrieved"
        ))


class BulkActionsMixin:
    """
    Mixin to add bulk actions to viewsets
    """

    bulk_actions = []  # Override in subclasses

    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """
        Perform bulk actions on multiple objects
        """
        action_type = request.data.get('action')
        object_ids = request.data.get('ids', [])

        if not action_type or not object_ids:
            return Response(
                self.get_response_envelope(
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Action type and object IDs are required",
                    error_code='MISSING_PARAMETERS'
                ),
                status=status.HTTP_400_BAD_REQUEST
            )

        if action_type not in self.bulk_actions:
            return Response(
                self.get_response_envelope(
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=f"Invalid action: {action_type}",
                    error_code='INVALID_ACTION'
                ),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Perform bulk action
        queryset = self.get_queryset().filter(id__in=object_ids)
        success_count, error_count, errors = self.perform_bulk_action(action_type, queryset, request.data)

        return Response(self.get_response_envelope(
            data={
                'action': action_type,
                'total_requested': len(object_ids),
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors
            },
            message=f"Bulk {action_type} completed: {success_count} successful, {error_count} failed"
        ))

    def perform_bulk_action(self, action_type, queryset, request_data):
        """
        Perform the actual bulk action
        Override in subclasses for specific actions
        """
        success_count = 0
        error_count = 0
        errors = []

        for obj in queryset:
            try:
                if action_type == 'delete':
                    obj.delete()
                elif action_type == 'activate':
                    if hasattr(obj, 'enable'):
                        obj.enable = True
                        obj.save()
                elif action_type == 'deactivate':
                    if hasattr(obj, 'enable'):
                        obj.enable = False
                        obj.save()

                success_count += 1

            except Exception as e:
                error_count += 1
                errors.append({
                    'object_id': obj.id,
                    'error': str(e)
                })

        return success_count, error_count, errors


class ExportMixin:
    """
    Mixin to add export functionality to viewsets
    """

    export_formats = ['csv', 'excel', 'json']  # Override in subclasses

    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Export data in various formats
        """
        export_format = request.query_params.get('format', 'csv').lower()

        if export_format not in self.export_formats:
            return Response(
                self.get_response_envelope(
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=f"Unsupported export format: {export_format}",
                    error_code='INVALID_FORMAT'
                ),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Limit export size for performance
        max_export_size = getattr(self, 'max_export_size', 10000)
        if queryset.count() > max_export_size:
            return Response(
                self.get_response_envelope(
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=f"Export too large. Maximum {max_export_size} records allowed.",
                    error_code='EXPORT_TOO_LARGE'
                ),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate export
        export_data = self.generate_export_data(queryset, export_format)

        return Response(self.get_response_envelope(
            data={
                'download_url': export_data['url'],
                'file_name': export_data['filename'],
                'format': export_format,
                'record_count': queryset.count(),
                'expires_at': (timezone.now() + timezone.timedelta(hours=1)).isoformat()
            },
            message=f"Export prepared in {export_format.upper()} format"
        ))

    def generate_export_data(self, queryset, export_format):
        """
        Generate export data - override in subclasses
        """
        # This would integrate with your export service
        return {
            'url': f'/api/exports/download/{export_format}/',
            'filename': f'export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.{export_format}'
        }


class FormSchemaMixin:
    """
    Mixin to provide form schemas for dynamic frontend forms
    """

    @action(detail=False, methods=['get'])
    def form_schema(self, request):
        """
        Get form schema for dynamic form generation
        """
        serializer = self.get_serializer()

        if hasattr(serializer, 'get_form_schema'):
            schema = serializer.get_form_schema()
        else:
            schema = self.generate_basic_schema(serializer)

        return Response(self.get_response_envelope(
            data=schema,
            message="Form schema generated"
        ))

    def generate_basic_schema(self, serializer):
        """
        Generate basic schema from serializer fields
        """
        schema = {
            'fields': {},
            'required': [],
            'field_order': []
        }

        for field_name, field in serializer.fields.items():
            if getattr(field, 'write_only', False):
                continue

            schema['fields'][field_name] = {
                'type': self.get_field_type(field),
                'label': getattr(field, 'label', field_name.replace('_', ' ').title()),
                'required': getattr(field, 'required', False),
                'help_text': getattr(field, 'help_text', ''),
            }

            if getattr(field, 'required', False):
                schema['required'].append(field_name)

            schema['field_order'].append(field_name)

        return schema

    def get_field_type(self, field):
        """
        Map DRF field to form field type
        """
        from rest_framework import serializers

        type_mapping = {
            serializers.CharField: 'text',
            serializers.EmailField: 'email',
            serializers.URLField: 'url',
            serializers.IntegerField: 'number',
            serializers.BooleanField: 'checkbox',
            serializers.DateField: 'date',
            serializers.DateTimeField: 'datetime-local',
            serializers.ChoiceField: 'select',
            serializers.FileField: 'file',
        }

        for field_class, field_type in type_mapping.items():
            if isinstance(field, field_class):
                return field_type

        return 'text'


class FrontendModelViewSet(
    FrontendViewMixin,
    SearchableMixin,
    FilterableMixin,
    BulkActionsMixin,
    ExportMixin,
    FormSchemaMixin,
    viewsets.ModelViewSet
):
    """
    Complete frontend-optimized ModelViewSet
    """

    def list(self, request, *args, **kwargs):
        """
        Enhanced list view with metadata
        """
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(self.get_response_envelope(
            data=serializer.data,
            message=f"Retrieved {len(serializer.data)} records",
            request=request,
            performance=self.get_performance_metadata()
        ))

    def retrieve(self, request, *args, **kwargs):
        """
        Enhanced retrieve view with metadata
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return Response(self.get_response_envelope(
            data=serializer.data,
            message="Record retrieved successfully",
            request=request,
            performance=self.get_performance_metadata()
        ))

    def create(self, request, *args, **kwargs):
        """
        Enhanced create view with better error handling
        """
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            instance = self.perform_create(serializer)
            return Response(
                self.get_response_envelope(
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED,
                    message="Record created successfully",
                    request=request,
                    performance=self.get_performance_metadata()
                ),
                status=status.HTTP_201_CREATED
            )
        else:
            return self.handle_validation_error(ValidationError(serializer.errors))

    def update(self, request, *args, **kwargs):
        """
        Enhanced update view
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if serializer.is_valid():
            instance = self.perform_update(serializer)
            return Response(self.get_response_envelope(
                data=serializer.data,
                message="Record updated successfully",
                request=request,
                performance=self.get_performance_metadata()
            ))
        else:
            return self.handle_validation_error(ValidationError(serializer.errors))

    def destroy(self, request, *args, **kwargs):
        """
        Enhanced delete view with confirmation
        """
        instance = self.get_object()
        instance_display = str(instance)

        self.perform_destroy(instance)

        return Response(self.get_response_envelope(
            data={'deleted_object': instance_display},
            message=f"'{instance_display}' deleted successfully",
            request=request,
            performance=self.get_performance_metadata()
        ))

    @action(detail=True, methods=['get'])
    def audit_log(self, request, pk=None):
        """
        Get audit log for object (if available)
        """
        instance = self.get_object()

        # This would integrate with your audit logging system
        audit_entries = []

        return Response(self.get_response_envelope(
            data=audit_entries,
            message="Audit log retrieved"
        ))


# Example enhanced viewset for People
class EnhancedPeopleViewSet(FrontendModelViewSet):
    """
    Example enhanced People viewset
    """
    from apps.core.serializers.enhanced_serializers import EnhancedPeopleSerializer
    from apps.peoples.models import People

    queryset = People.objects.all()
    serializer_class = EnhancedPeopleSerializer

    # Search configuration
    search_fields = ['peoplename', 'loginid', 'email', 'peoplecode']

    # Filter configuration
    filter_fields = {
        'enable': 'boolean',
        'isadmin': 'boolean',
        'isverified': 'boolean',
        'bu': 'exact',
        'department': 'exact',
    }

    date_range_fields = ['cdtz', 'mdtz']

    # Bulk actions
    bulk_actions = ['activate', 'deactivate', 'delete']

    # Export settings
    export_formats = ['csv', 'excel']
    max_export_size = 5000

    def get_queryset(self):
        """
        Optimized queryset for People
        """
        return self.serializer_class.setup_eager_loading(
            super().get_queryset()
        )

    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        """
        Change user password with enhanced validation
        """
        user = self.get_object()
        new_password = request.data.get('password')

        if not new_password:
            return Response(
                self.get_response_envelope(
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Password is required",
                    error_code='MISSING_PASSWORD'
                ),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate password strength
        if len(new_password) < 8:
            return Response(
                self.get_response_envelope(
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Password must be at least 8 characters long",
                    error_code='WEAK_PASSWORD'
                ),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Set new password
        user.set_password(new_password)
        user.save()

        return Response(self.get_response_envelope(
            data={'success': True},
            message="Password changed successfully"
        ))

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get People statistics for dashboard
        """
        queryset = self.get_queryset()

        stats = {
            'total': queryset.count(),
            'active': queryset.filter(enable=True).count(),
            'verified': queryset.filter(isverified=True).count(),
            'admins': queryset.filter(isadmin=True).count(),
            'recent_joins': queryset.filter(
                cdtz__gte=timezone.now() - timezone.timedelta(days=30)
            ).count()
        }

        return Response(self.get_response_envelope(
            data=stats,
            message="Statistics retrieved"
        ))