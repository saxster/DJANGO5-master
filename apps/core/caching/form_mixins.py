"""
Form mixins for intelligent dropdown caching
Reduces database queries by caching static dropdown data
"""

import logging
from typing import Any, Dict, Optional
from django import forms
from django.core.cache import cache
from django.db.models import QuerySet

from .utils import get_tenant_cache_key, CACHE_TIMEOUTS
from .decorators import method_cache

logger = logging.getLogger(__name__)


class CachedDropdownMixin:
    """
    Mixin for forms that provides cached dropdown data
    Dramatically reduces database queries for static dropdown options
    """

    # Cache configuration
    dropdown_cache_timeout = CACHE_TIMEOUTS['DROPDOWN_DATA']
    cache_prefix = 'form:dropdown'

    def __init__(self, *args, **kwargs):
        self.request = kwargs.get('request')
        super().__init__(*args, **kwargs)
        self._setup_cached_dropdowns()

    def _setup_cached_dropdowns(self):
        """
        Setup cached dropdown fields during form initialization
        """
        if not hasattr(self, 'cached_dropdown_fields'):
            return

        for field_name, config in self.cached_dropdown_fields.items():
            if field_name in self.fields:
                try:
                    cached_queryset = self._get_cached_dropdown_data(field_name, config)
                    if cached_queryset is not None:
                        self.fields[field_name].queryset = cached_queryset
                        logger.debug(f"Applied cached queryset to field: {field_name}")

                except (ValueError, TypeError) as e:
                    logger.error(f"Error setting up cached dropdown for {field_name}: {e}")
                    # Fallback to original queryset if caching fails

    def _get_cached_dropdown_data(self, field_name: str, config: Dict[str, Any]) -> Optional[QuerySet]:
        """
        Get cached dropdown data for a specific field

        Args:
            field_name: Name of the form field
            config: Configuration dictionary with model, filter_method, etc.

        Returns:
            Cached QuerySet or None if cache miss
        """
        # Generate cache key
        cache_key_parts = [
            self.cache_prefix,
            self.__class__.__name__,
            field_name,
            config.get('version', '1')
        ]

        # Add tenant context if available
        if self.request:
            cache_key = get_tenant_cache_key(':'.join(cache_key_parts), self.request)
        else:
            cache_key = ':'.join(cache_key_parts)

        # Try to get from cache
        try:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                logger.debug(f"Cache HIT for dropdown field: {field_name}")
                return cached_data

        except (ConnectionError, ValueError) as e:
            logger.error(f"Cache get error for field {field_name}: {e}")

        # Cache miss - generate data
        logger.debug(f"Cache MISS for dropdown field: {field_name}")
        queryset = self._generate_dropdown_data(field_name, config)

        if queryset is not None:
            try:
                # Cache the queryset (Note: This might serialize the QuerySet)
                # For better performance, consider caching the data and recreating QuerySet
                cache.set(cache_key, queryset, self.dropdown_cache_timeout)
                logger.debug(f"Cached dropdown data for field: {field_name}")

            except (ConnectionError, ValueError) as e:
                logger.error(f"Cache set error for field {field_name}: {e}")

        return queryset

    def _generate_dropdown_data(self, field_name: str, config: Dict[str, Any]) -> Optional[QuerySet]:
        """
        Generate dropdown data using the configured method

        Args:
            field_name: Name of the form field
            config: Configuration with model and filter method

        Returns:
            QuerySet for the dropdown
        """
        try:
            model = config.get('model')
            filter_method = config.get('filter_method')

            if not model or not filter_method:
                logger.error(f"Missing model or filter_method for field {field_name}")
                return None

            # Call the filter method with request context
            if hasattr(model.objects, filter_method):
                method = getattr(model.objects, filter_method)
                if self.request:
                    return method(self.request, sitewise=config.get('sitewise', True))
                else:
                    return method()

            else:
                logger.error(f"Filter method {filter_method} not found on {model}")
                return None

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error generating dropdown data for {field_name}: {e}")
            return None

    def invalidate_dropdown_cache(self, field_name: Optional[str] = None):
        """
        Invalidate cached dropdown data

        Args:
            field_name: Specific field to invalidate, or None for all fields
        """
        if field_name and hasattr(self, 'cached_dropdown_fields'):
            # Invalidate specific field
            config = self.cached_dropdown_fields.get(field_name, {})
            cache_key_parts = [
                self.cache_prefix,
                self.__class__.__name__,
                field_name,
                config.get('version', '1')
            ]

            if self.request:
                cache_key = get_tenant_cache_key(':'.join(cache_key_parts), self.request)
            else:
                cache_key = ':'.join(cache_key_parts)

            try:
                cache.delete(cache_key)
                logger.info(f"Invalidated cache for dropdown field: {field_name}")
            except (ConnectionError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Error invalidating cache for field {field_name}: {e}")

        else:
            # Invalidate all dropdowns for this form
            pattern = f"*{self.cache_prefix}:{self.__class__.__name__}:*"
            try:
                # This would require a more sophisticated cache clearing mechanism
                logger.info(f"Would invalidate all dropdown caches for form: {self.__class__.__name__}")
            except (ConnectionError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Error invalidating all dropdown caches: {e}")


class OptimizedDropdownForm(CachedDropdownMixin, forms.Form):
    """
    Base form class with optimized dropdown caching
    """

    def __init__(self, *args, **kwargs):
        # Extract request before passing to parent
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)


class OptimizedModelForm(CachedDropdownMixin, forms.ModelForm):
    """
    Base ModelForm class with optimized dropdown caching
    """

    def __init__(self, *args, **kwargs):
        # Extract request before passing to parent
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)


def cache_dropdown_field(
    model,
    filter_method: str,
    timeout: Optional[int] = None,
    sitewise: bool = True,
    version: str = '1'
):
    """
    Decorator to mark a form field for dropdown caching

    Args:
        model: Django model class
        filter_method: Method name on the model manager
        timeout: Cache timeout in seconds
        sitewise: Whether to use sitewise filtering
        version: Cache version for invalidation

    Usage:
        class MyForm(OptimizedModelForm):
            @cache_dropdown_field(People, 'filter_for_dd_people_field')
            people = forms.ModelChoiceField(queryset=People.objects.none())
    """

    def decorator(field):
        # Store cache configuration on the field
        field._cache_config = {
            'model': model,
            'filter_method': filter_method,
            'timeout': timeout or CACHE_TIMEOUTS['DROPDOWN_DATA'],
            'sitewise': sitewise,
            'version': version
        }
        return field

    return decorator


class CachedSelect2Mixin:
    """
    Mixin for Select2 widgets with caching support
    Optimizes AJAX endpoints for dropdown data
    """

    def __init__(self, *args, **kwargs):
        self.cache_timeout = kwargs.pop('cache_timeout', CACHE_TIMEOUTS['DROPDOWN_DATA'])
        super().__init__(*args, **kwargs)

    def get_cache_key(self, request, term: str = '') -> str:
        """
        Generate cache key for Select2 AJAX requests

        Args:
            request: HTTP request
            term: Search term

        Returns:
            Cache key string
        """
        base_key = f"select2:{self.__class__.__name__}:{term}"
        return get_tenant_cache_key(base_key, request)

    def filter_queryset(self, request, queryset, term):
        """
        Override this method to provide caching for Select2 AJAX requests
        """
        cache_key = self.get_cache_key(request, term)

        try:
            cached_results = cache.get(cache_key)
            if cached_results is not None:
                logger.debug(f"Select2 cache HIT for term: {term}")
                return cached_results

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Select2 cache get error: {e}")

        # Cache miss - filter queryset
        logger.debug(f"Select2 cache MISS for term: {term}")
        results = super().filter_queryset(request, queryset, term)

        try:
            cache.set(cache_key, results, self.cache_timeout)
            logger.debug(f"Cached Select2 results for term: {term}")
        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Select2 cache set error: {e}")

        return results


# Utility functions for dropdown cache management
def warm_form_dropdown_caches(form_class, request=None):
    """
    Pre-warm dropdown caches for a form class

    Args:
        form_class: Form class to warm caches for
        request: Optional request for tenant context
    """
    try:
        if hasattr(form_class, 'cached_dropdown_fields'):
            form_instance = form_class(request=request)
            warmed_fields = []

            for field_name in form_class.cached_dropdown_fields.keys():
                if field_name in form_instance.fields:
                    warmed_fields.append(field_name)

            logger.info(
                f"Warmed dropdown caches for form {form_class.__name__}: {warmed_fields}"
            )

    except (ConnectionError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error warming dropdown caches for {form_class.__name__}: {e}")


def get_dropdown_cache_stats(form_class) -> Dict[str, Any]:
    """
    Get cache statistics for a form's dropdown fields

    Args:
        form_class: Form class to get stats for

    Returns:
        Dictionary with cache statistics
    """
    stats = {
        'form_class': form_class.__name__,
        'cached_fields': 0,
        'cache_hits': 0,
        'cache_misses': 0
    }

    if hasattr(form_class, 'cached_dropdown_fields'):
        stats['cached_fields'] = len(form_class.cached_dropdown_fields)

    # TODO: Implement hit/miss tracking with Redis statistics

    return stats