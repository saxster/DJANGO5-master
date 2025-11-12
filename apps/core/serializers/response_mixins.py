"""
Response Formatting Mixins for Frontend Serializers
Provides standardized response envelopes, metadata, and UI hints
"""

from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from rest_framework import serializers


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
        app_label = obj._meta.app_label

        return {
            'can_view': True,  # If they can see it, they can view it
            'can_edit': user.has_perm(f'{app_label}.change_{model_name}') or getattr(user, 'isadmin', False),
            'can_delete': user.has_perm(f'{app_label}.delete_{model_name}') or getattr(user, 'isadmin', False),
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
