"""
Caching and Performance Aware Serializers
Provides intelligent caching, performance tracking, and custom field types
"""

import time
from django.core.cache import cache
from django.utils import timezone
from rest_framework import serializers
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


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


class BaseFrontendSerializer(
    serializers.ModelSerializer
):
    """
    Base serializer with enhanced database error handling
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
