"""
Frontend-Friendly Serializers
Enhanced DRF serializers optimized for modern frontend consumption
Includes response standardization, metadata, and UX improvements
"""

import time
from typing import Dict, Any, Optional, List, Union
from django.core.cache import cache
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AnonymousUser
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.fields import empty
from apps.core.utils_new.permission_helpers import user_has_permission
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS



class FrontendResponseMixin:
    """
    Mixin to standardize API responses for frontend consumption
    Includes metadata, performance metrics, and error context
    """

    def get_response_envelope(self, data, status_code=200, message=None, **kwargs):
        """
        Create standardized response envelope
        """
        envelope = {
            'success': 200 <= status_code < 300,
            'status_code': status_code,
            'message': message,
            'data': data,
            'meta': self.get_response_metadata(**kwargs),
            'timestamp': timezone.now().isoformat(),
        }

        # Add error details for non-success responses
        if not envelope['success']:
            envelope['errors'] = kwargs.get('errors', [])
            envelope['error_code'] = kwargs.get('error_code')

        return envelope

    def get_response_metadata(self, **kwargs):
        """
        Generate response metadata for frontend use
        """
        request = kwargs.get('request')
        user = getattr(request, 'user', AnonymousUser())

        meta = {
            'version': '2.0',
            'request_id': getattr(request, 'id', None),
            'user': {
                'id': user.id if user.is_authenticated else None,
                'is_authenticated': user.is_authenticated,
                'is_staff': getattr(user, 'is_staff', False),
                'permissions': self.get_user_permissions(user),
            },
            'pagination': kwargs.get('pagination'),
            'performance': kwargs.get('performance', {}),
            'caching': kwargs.get('caching', {}),
        }

        return {k: v for k, v in meta.items() if v is not None}

    def get_user_permissions(self, user):
        """
        Get user permissions relevant to current context
        """
        if not user.is_authenticated:
            return []

        permissions = []
        if hasattr(user, 'isadmin') and user.isadmin:
            permissions.append('admin')
        if hasattr(user, 'is_staff') and user.is_staff:
            permissions.append('staff')

        return permissions


class FrontendPagination(PageNumberPagination):
    """
    Enhanced pagination with frontend-friendly metadata
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """
        Return paginated response with enhanced metadata
        """
        pagination_meta = {
            'pagination': {
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'total_items': self.page.paginator.count,
                'page_size': self.get_page_size(self.request),
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
                'next_page': self.page.next_page_number() if self.page.has_next() else None,
                'previous_page': self.page.previous_page_number() if self.page.has_previous() else None,
                'start_index': self.page.start_index(),
                'end_index': self.page.end_index(),
            }
        }

        # Use response envelope if view supports it
        if hasattr(self.request, 'view') and hasattr(self.request.view, 'get_response_envelope'):
            return Response(self.request.view.get_response_envelope(
                data=data,
                request=self.request,
                **pagination_meta
            ))

        return Response({
            'results': data,
            **pagination_meta
        })


class MetadataSerializerMixin:
    """
    Mixin to add metadata fields to serializers
    Includes computed fields, permissions, and UI hints
    """

    def get_metadata_fields(self):
        """
        Define metadata fields to include in serialization
        """
        return {
            'display_name': self.get_display_name,
            'permissions': self.get_permissions,
            'ui_hints': self.get_ui_hints,
            'computed_fields': self.get_computed_fields,
        }

    def to_representation(self, instance):
        """
        Enhanced representation with metadata
        """
        data = super().to_representation(instance)

        # Add metadata if enabled
        if getattr(self, 'include_metadata', True):
            metadata = {}
            for field_name, method in self.get_metadata_fields().items():
                try:
                    metadata[field_name] = method(instance)
                except (ValueError, TypeError, AttributeError) as e:
                    # Log error but don't break serialization
                    metadata[field_name] = None

            if metadata:
                data['_meta'] = metadata

        return data

    def get_display_name(self, obj):
        """
        Get human-readable display name for object
        """
        if hasattr(obj, '__str__'):
            return str(obj)
        return getattr(obj, 'name', getattr(obj, 'title', 'Object'))

    def get_permissions(self, obj):
        """
        Get user permissions for this object
        """
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return {'can_view': True, 'can_edit': False, 'can_delete': False}

        user = request.user
        model_name = obj._meta.model_name

        return {
            'can_view': True,  # If they can see it, they can view it
            'can_edit': user_has_permission(user, f'{model_name}.change') or getattr(user, 'isadmin', False),
            'can_delete': user_has_permission(user, f'{model_name}.delete') or getattr(user, 'isadmin', False),
        }

    def get_ui_hints(self, obj):
        """
        Get UI hints for frontend rendering
        """
        hints = {
            'model': obj._meta.model_name,
            'app': obj._meta.app_label,
            'pk_field': obj._meta.pk.name,
        }

        # Add status-based hints
        if hasattr(obj, 'enable'):
            hints['status'] = 'active' if obj.enable else 'inactive'

        if hasattr(obj, 'is_verified'):
            hints['verified'] = obj.is_verified

        return hints

    def get_computed_fields(self, obj):
        """
        Get computed fields that frontend might need
        """
        computed = {}

        # Common computed fields
        if hasattr(obj, 'cdtz'):
            computed['created_ago'] = self.get_time_ago(obj.cdtz)

        if hasattr(obj, 'mdtz'):
            computed['modified_ago'] = self.get_time_ago(obj.mdtz)

        # Object-specific computed fields
        if hasattr(obj, 'peoplename') and hasattr(obj, 'loginid'):
            computed['full_identifier'] = f"{obj.peoplename} ({obj.loginid})"

        return computed

    def get_time_ago(self, datetime_obj):
        """
        Get human-readable time ago string
        """
        if not datetime_obj:
            return None

        now = timezone.now()
        diff = now - datetime_obj

        if diff.days > 365:
            return f"{diff.days // 365} year{'s' if diff.days // 365 != 1 else ''} ago"
        elif diff.days > 30:
            return f"{diff.days // 30} month{'s' if diff.days // 30 != 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"


class FormSchemaSerializerMixin:
    """
    Mixin to generate form schemas for dynamic frontend forms
    """

    def get_form_schema(self):
        """
        Generate JSON schema for frontend form generation
        """
        schema = {
            'fields': {},
            'required': [],
            'field_order': [],
            'validation_rules': {},
            'ui_schema': {},
        }

        for field_name, field in self.fields.items():
            if getattr(field, 'write_only', False):
                continue

            field_schema = self.get_field_schema(field_name, field)
            schema['fields'][field_name] = field_schema

            if getattr(field, 'required', False):
                schema['required'].append(field_name)

            schema['field_order'].append(field_name)

        return schema

    def get_field_schema(self, field_name, field):
        """
        Generate schema for individual field
        """
        field_type = self.get_field_type(field)
        schema = {
            'type': field_type,
            'label': getattr(field, 'label', field_name.replace('_', ' ').title()),
            'help_text': getattr(field, 'help_text', ''),
            'required': getattr(field, 'required', False),
            'read_only': getattr(field, 'read_only', False),
        }

        # Add field-specific properties
        if isinstance(field, serializers.CharField):
            schema.update({
                'max_length': getattr(field, 'max_length', None),
                'min_length': getattr(field, 'min_length', None),
            })

        elif isinstance(field, serializers.ChoiceField):
            schema.update({
                'choices': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in getattr(field, 'choices', [])
                ]
            })

        elif isinstance(field, (serializers.DateTimeField, serializers.DateField)):
            schema.update({
                'format': 'date-time' if isinstance(field, serializers.DateTimeField) else 'date'
            })

        elif isinstance(field, serializers.FileField):
            schema.update({
                'accept': getattr(field, 'allowed_extensions', []),
                'max_size': getattr(field, 'max_upload_size', None),
            })

        return schema

    def get_field_type(self, field):
        """
        Map DRF field types to frontend form types
        """
        type_mapping = {
            serializers.CharField: 'text',
            serializers.EmailField: 'email',
            serializers.URLField: 'url',
            serializers.IntegerField: 'number',
            serializers.FloatField: 'number',
            serializers.DecimalField: 'number',
            serializers.BooleanField: 'checkbox',
            serializers.DateField: 'date',
            serializers.DateTimeField: 'datetime-local',
            serializers.TimeField: 'time',
            serializers.ChoiceField: 'select',
            serializers.MultipleChoiceField: 'multiselect',
            serializers.FileField: 'file',
            serializers.ImageField: 'image',
        }

        for field_class, field_type in type_mapping.items():
            if isinstance(field, field_class):
                return field_type

        return 'text'


class PerformanceSerializerMixin:
    """
    Mixin to add performance tracking to serializers
    """

    def __init__(self, *args, **kwargs):
        self._start_time = time.time()
        super().__init__(*args, **kwargs)

    def to_representation(self, instance):
        """
        Add performance metrics to representation
        """
        start_time = time.time()
        data = super().to_representation(instance)
        serialization_time = time.time() - start_time

        # Add performance metadata if enabled
        if getattr(self, 'include_performance', False):
            if '_meta' not in data:
                data['_meta'] = {}

            data['_meta']['performance'] = {
                'serialization_time_ms': round(serialization_time * 1000, 2),
                'total_time_ms': round((time.time() - self._start_time) * 1000, 2),
            }

        return data


class CachingSerializerMixin:
    """
    Mixin to add intelligent caching to serializers
    """

    def get_cache_key(self, instance):
        """
        Generate cache key for instance
        """
        model_name = instance._meta.label_lower
        instance_id = instance.pk
        modified = getattr(instance, 'mdtz', None) or getattr(instance, 'updated_at', None)
        modified_timestamp = modified.timestamp() if modified else 'no-mod'

        return f"serializer:{model_name}:{instance_id}:{modified_timestamp}"

    def to_representation(self, instance):
        """
        Use cached representation if available
        """
        if not getattr(self, 'use_cache', False):
            return super().to_representation(instance)

        cache_key = self.get_cache_key(instance)
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            # Add cache hit metadata
            if '_meta' not in cached_data:
                cached_data['_meta'] = {}
            cached_data['_meta']['cache'] = {'hit': True}
            return cached_data

        # Generate fresh data
        data = super().to_representation(instance)

        # Add cache miss metadata
        if '_meta' not in data:
            data['_meta'] = {}
        data['_meta']['cache'] = {'hit': False}

        # Cache for future use (5 minutes default)
        cache_timeout = getattr(self, 'cache_timeout', 300)
        cache.set(cache_key, data, cache_timeout)

        return data


class BaseFrontendSerializer(
    FrontendResponseMixin,
    MetadataSerializerMixin,
    FormSchemaSerializerMixin,
    PerformanceSerializerMixin,
    CachingSerializerMixin,
    serializers.ModelSerializer
):
    """
    Base serializer with all frontend-friendly features
    """

    class Meta:
        abstract = True

    # Configuration flags
    include_metadata = True
    include_performance = False  # Enable for debugging
    use_cache = False  # Enable for performance-critical endpoints

    def __init__(self, *args, **kwargs):
        # Extract frontend-specific options
        self.include_metadata = kwargs.pop('include_metadata', self.include_metadata)
        self.include_performance = kwargs.pop('include_performance', self.include_performance)
        self.use_cache = kwargs.pop('use_cache', self.use_cache)

        super().__init__(*args, **kwargs)

    def create(self, validated_data):
        """
        Enhanced create with better error handling
        """
        try:
            instance = super().create(validated_data)
            return instance
        except DATABASE_EXCEPTIONS as e:
            self.add_creation_error(e)
            raise

    def update(self, instance, validated_data):
        """
        Enhanced update with better error handling
        """
        try:
            instance = super().update(instance, validated_data)
            return instance
        except DATABASE_EXCEPTIONS as e:
            self.add_update_error(e, instance)
            raise

    def add_creation_error(self, error):
        """
        Add context for creation errors
        """
        # This would be used by error handling middleware
        if hasattr(self, '_errors'):
            self._errors['_creation'] = str(error)

    def add_update_error(self, error, instance):
        """
        Add context for update errors
        """
        # This would be used by error handling middleware
        if hasattr(self, '_errors'):
            self._errors['_update'] = {
                'error': str(error),
                'instance_id': instance.pk if instance else None,
            }


class RelationshipEagerLoadingMixin:
    """
    Mixin to optimize database queries for relationships
    """

    def get_optimized_queryset(self, queryset):
        """
        Apply select_related and prefetch_related optimizations
        """
        if hasattr(self.Meta, 'select_related'):
            queryset = queryset.select_related(*self.Meta.select_related)

        if hasattr(self.Meta, 'prefetch_related'):
            queryset = queryset.prefetch_related(*self.Meta.prefetch_related)

        return queryset

    @classmethod
    def setup_eager_loading(cls, queryset):
        """
        Class method to set up eager loading for viewsets
        """
        serializer = cls()
        return serializer.get_optimized_queryset(queryset)


# Frontend-optimized field types
class ComputedField(serializers.Field):
    """
    Field for computed values that don't exist in the model
    """

    def __init__(self, compute_function, **kwargs):
        self.compute_function = compute_function
        kwargs['read_only'] = True
        super().__init__(**kwargs)

    def to_representation(self, obj):
        return self.compute_function(obj)


class HumanReadableDateTimeField(serializers.DateTimeField):
    """
    DateTime field with human-readable representation
    """

    def to_representation(self, value):
        if not value:
            return None

        iso_string = super().to_representation(value)
        return {
            'iso': iso_string,
            'human': self.get_human_readable(value),
            'timestamp': value.timestamp(),
        }

    def get_human_readable(self, value):
        """
        Convert datetime to human-readable format
        """
        now = timezone.now()
        diff = now - value

        if diff.days > 365:
            return value.strftime('%B %d, %Y')
        elif diff.days > 7:
            return value.strftime('%B %d')
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"


class FileFieldWithMetadata(serializers.FileField):
    """
    File field with additional metadata for frontend
    """

    def to_representation(self, value):
        if not value:
            return None

        request = self.context.get('request')
        url = value.url if value else None

        if url and request:
            url = request.build_absolute_uri(url)

        return {
            'url': url,
            'name': value.name if value else None,
            'size': value.size if value else None,
            'content_type': getattr(value, 'content_type', None),
        }