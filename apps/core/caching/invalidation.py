"""
Intelligent cache invalidation system with dependency mapping
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.db import models
from django.apps import apps

from .utils import clear_cache_pattern, get_tenant_cache_key

logger = logging.getLogger(__name__)


class CacheInvalidationManager:
    """
    Central manager for cache invalidation with dependency mapping
    """

    def __init__(self):
        self.model_dependencies: Dict[str, Set[str]] = {}
        self.cache_patterns: Dict[str, List[str]] = {}
        self._initialize_dependencies()

    def _initialize_dependencies(self):
        """
        Initialize model-to-cache-pattern dependency mappings
        """
        # Core model dependencies
        self.model_dependencies = {
            'People': {
                'dropdown:people',
                'dashboard:metrics',
                'user:prefs',
                'attendance:summary'
            },
            'Asset': {
                'dropdown:asset',
                'dashboard:metrics',
                'asset:status',
                'form:choices'
            },
            'Location': {
                'dropdown:location',
                'form:choices',
                'asset:status'
            },
            'PeopleEventlog': {
                'dashboard:metrics',
                'attendance:summary',
                'trends:monthly'
            },
            'Job': {
                'dashboard:metrics',
                'schedhuler:jobs',
                'form:choices'
            },
            'TypeAssist': {
                'dropdown:typeassist',
                'form:choices',
                'ticket:categories'
            },
            'Pgroup': {
                'dropdown:pgroup',
                'form:choices',
                'schedhuler:groups'
            },
            'BusinessUnit': {
                'dropdown:*',  # Affects all dropdowns
                'dashboard:*',  # Affects all dashboard data
                'form:*'       # Affects all form data
            }
        }

        # Cache pattern to tenant awareness mapping
        self.cache_patterns = {
            'dropdown': ['tenant:*:dropdown:*'],
            'dashboard': ['tenant:*:dashboard:*'],
            'user': ['tenant:*:user:*'],
            'attendance': ['tenant:*:attendance:*'],
            'asset': ['tenant:*:asset:*'],
            'form': ['tenant:*:form:*'],
            'schedhuler': ['tenant:*:schedhuler:*'],
            'trends': ['tenant:*:trends:*'],
            'ticket': ['tenant:*:ticket:*']
        }

    def register_dependency(self, model_name: str, cache_patterns: List[str]):
        """
        Register cache patterns that depend on a model

        Args:
            model_name: Name of the model
            cache_patterns: List of cache patterns that should be invalidated
        """
        if model_name not in self.model_dependencies:
            self.model_dependencies[model_name] = set()

        self.model_dependencies[model_name].update(cache_patterns)
        logger.info(f"Registered cache dependency: {model_name} -> {cache_patterns}")

    def get_patterns_for_model(self, model_name: str) -> Set[str]:
        """
        Get all cache patterns that should be invalidated for a model

        Args:
            model_name: Name of the model

        Returns:
            Set of cache patterns to invalidate
        """
        return self.model_dependencies.get(model_name, set())

    def invalidate_for_model(
        self,
        model_instance: models.Model,
        operation: str = 'update'
    ) -> Dict[str, Any]:
        """
        Invalidate all cache patterns associated with a model instance

        Args:
            model_instance: The model instance that was modified
            operation: Type of operation ('create', 'update', 'delete')

        Returns:
            Invalidation results
        """
        model_name = model_instance.__class__.__name__
        patterns = self.get_patterns_for_model(model_name)

        if not patterns:
            logger.debug(f"No cache patterns registered for model: {model_name}")
            return {'model': model_name, 'patterns_cleared': 0}

        results = {
            'model': model_name,
            'operation': operation,
            'instance_id': getattr(model_instance, 'pk', None),
            'patterns_cleared': 0,
            'errors': []
        }

        # Get tenant context from model instance
        tenant_id = getattr(model_instance, 'tenant_id', None)
        client_id = getattr(model_instance, 'client_id', None)
        bu_id = getattr(model_instance, 'bu_id', None)

        for pattern in patterns:
            try:
                # Handle wildcard patterns
                if pattern.endswith('*'):
                    base_pattern = pattern[:-1]
                    if tenant_id:
                        # Clear tenant-specific caches
                        tenant_pattern = f"tenant:{tenant_id}:*{base_pattern}*"
                    else:
                        # Clear all tenant caches for this pattern
                        tenant_pattern = f"tenant:*:*{base_pattern}*"
                else:
                    if tenant_id:
                        # Clear specific tenant cache
                        tenant_pattern = f"tenant:{tenant_id}:*{pattern}*"
                    else:
                        # Clear all tenant caches for this specific pattern
                        tenant_pattern = f"tenant:*:*{pattern}*"

                clear_result = clear_cache_pattern(tenant_pattern)
                if clear_result['success']:
                    results['patterns_cleared'] += clear_result['keys_cleared']
                    logger.info(
                        f"Invalidated {clear_result['keys_cleared']} cache keys "
                        f"for model {model_name} with pattern {tenant_pattern}"
                    )
                else:
                    results['errors'].append(f"Failed to clear pattern {tenant_pattern}")

            except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
                error_msg = f"Error invalidating pattern {pattern}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)

        return results

    def invalidate_related_caches(
        self,
        model_instance: models.Model,
        related_models: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Invalidate caches for related models (e.g., when People changes, invalidate Pgroup caches)

        Args:
            model_instance: The model instance that was modified
            related_models: List of related model names to also invalidate

        Returns:
            Combined invalidation results
        """
        results = {
            'primary_model': model_instance.__class__.__name__,
            'invalidation_results': [],
            'total_patterns_cleared': 0
        }

        # Invalidate primary model caches
        primary_result = self.invalidate_for_model(model_instance)
        results['invalidation_results'].append(primary_result)
        results['total_patterns_cleared'] += primary_result['patterns_cleared']

        # Invalidate related model caches
        if related_models:
            for related_model_name in related_models:
                try:
                    # Create a dummy instance for pattern lookup
                    related_patterns = self.get_patterns_for_model(related_model_name)
                    if related_patterns:
                        related_result = {
                            'model': related_model_name,
                            'operation': 'related_invalidation',
                            'patterns_cleared': 0,
                            'errors': []
                        }

                        for pattern in related_patterns:
                            clear_result = clear_cache_pattern(f"tenant:*:*{pattern}*")
                            if clear_result['success']:
                                related_result['patterns_cleared'] += clear_result['keys_cleared']

                        results['invalidation_results'].append(related_result)
                        results['total_patterns_cleared'] += related_result['patterns_cleared']

                except (TypeError, ValidationError, ValueError) as e:
                    logger.error(f"Error invalidating related model {related_model_name}: {e}")

        return results


# Global cache invalidation manager instance
cache_invalidation_manager = CacheInvalidationManager()


def invalidate_cache_pattern(pattern: str, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Convenience function to invalidate cache patterns

    Args:
        pattern: Cache pattern to invalidate
        tenant_id: Optional tenant ID for scoped invalidation

    Returns:
        Invalidation results
    """
    if tenant_id:
        full_pattern = f"tenant:{tenant_id}:*{pattern}*"
    else:
        full_pattern = f"tenant:*:*{pattern}*"

    return clear_cache_pattern(full_pattern)


def invalidate_model_caches(model_name: str, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Convenience function to invalidate all caches for a model

    Args:
        model_name: Name of the model
        tenant_id: Optional tenant ID for scoped invalidation

    Returns:
        Invalidation results
    """
    patterns = cache_invalidation_manager.get_patterns_for_model(model_name)
    results = {
        'model': model_name,
        'patterns_processed': len(patterns),
        'total_cleared': 0,
        'errors': []
    }

    for pattern in patterns:
        try:
            result = invalidate_cache_pattern(pattern, tenant_id)
            if result['success']:
                results['total_cleared'] += result['keys_cleared']
            else:
                results['errors'].append(result.get('error', 'Unknown error'))
        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            results['errors'].append(str(e))

    return results


# Signal handlers for automatic cache invalidation
@receiver(post_save)
def handle_model_post_save(sender, instance, created, **kwargs):
    """
    Automatic cache invalidation on model save
    """
    operation = 'create' if created else 'update'

    try:
        result = cache_invalidation_manager.invalidate_for_model(instance, operation)
        if result['patterns_cleared'] > 0:
            logger.info(
                f"Auto-invalidated {result['patterns_cleared']} cache keys "
                f"after {operation} of {sender.__name__}"
            )
    except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error in post_save cache invalidation for {sender.__name__}: {e}")


@receiver(post_delete)
def handle_model_post_delete(sender, instance, **kwargs):
    """
    Automatic cache invalidation on model deletion
    """
    try:
        result = cache_invalidation_manager.invalidate_for_model(instance, 'delete')
        if result['patterns_cleared'] > 0:
            logger.info(
                f"Auto-invalidated {result['patterns_cleared']} cache keys "
                f"after deletion of {sender.__name__}"
            )
    except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error in post_delete cache invalidation for {sender.__name__}: {e}")


@receiver(m2m_changed)
def handle_m2m_changed(sender, instance, action, pk_set, **kwargs):
    """
    Automatic cache invalidation on many-to-many changes
    """
    if action in ('post_add', 'post_remove', 'post_clear'):
        try:
            result = cache_invalidation_manager.invalidate_for_model(instance, 'm2m_change')
            if result['patterns_cleared'] > 0:
                logger.info(
                    f"Auto-invalidated {result['patterns_cleared']} cache keys "
                    f"after M2M {action} on {instance.__class__.__name__}"
                )
        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error in m2m_changed cache invalidation: {e}")


def register_cache_invalidation_for_app(app_name: str):
    """
    Register cache invalidation for all models in an app

    Args:
        app_name: Name of the Django app
    """
    try:
        app_config = apps.get_app_config(app_name)
        for model in app_config.get_models():
            model_name = model.__name__

            # Auto-register common patterns based on model name
            patterns = {f"dropdown:{model_name.lower()}", f"form:{model_name.lower()}"}

            # Add specific patterns for key models
            if model_name in ['People', 'Asset', 'PeopleEventlog']:
                patterns.add("dashboard:metrics")

            cache_invalidation_manager.register_dependency(model_name, list(patterns))

        logger.info(f"Registered cache invalidation for app: {app_name}")

    except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error registering cache invalidation for app {app_name}: {e}")


# Utility functions for manual cache management
def warm_dropdown_caches(tenant_id: Optional[int] = None):
    """
    Warm dropdown caches for a tenant

    Args:
        tenant_id: Tenant ID to warm caches for
    """
    from apps.peoples.models import People
    from apps.onboarding.models import TypeAssist
    from apps.activity.models.asset_model import Asset

    # Implementation would go here to pre-populate dropdown caches
    logger.info(f"Warming dropdown caches for tenant: {tenant_id}")


def get_cache_invalidation_stats() -> Dict[str, Any]:
    """
    Get statistics about cache invalidation patterns

    Returns:
        Statistics about registered invalidation patterns
    """
    return {
        'registered_models': len(cache_invalidation_manager.model_dependencies),
        'total_patterns': sum(
            len(patterns) for patterns in cache_invalidation_manager.model_dependencies.values()
        ),
        'model_dependencies': {
            model: list(patterns)
            for model, patterns in cache_invalidation_manager.model_dependencies.items()
        }
    }