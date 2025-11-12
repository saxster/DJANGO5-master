"""
Query Optimization Utilities

Provides optimization suggestions for Django ORM queries.

Usage:
    from apps.core.utils_new.performance import QueryOptimizer

    optimizer = QueryOptimizer()
    suggestions = optimizer.analyze_queryset(MyModel.objects.all())
"""

import logging
from typing import Dict, List, Any
from django.db import models
from django.db.models import (
    QuerySet, ForeignKey, OneToOneField, ManyToManyField,
    ForeignObjectRel
)
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .n_plus_one import NPlusOneDetector

logger = logging.getLogger('query_optimizer')


class QueryOptimizer:
    """Provides optimization suggestions for Django ORM queries."""

    def __init__(self):
        """Initialize query optimizer."""
        self.detector = NPlusOneDetector()

    def analyze_queryset(self, queryset: QuerySet) -> Dict[str, Any]:
        """
        Analyze a queryset for optimization opportunities.

        Args:
            queryset: Django QuerySet to analyze

        Returns:
            Dict: Analysis with optimization suggestions
        """
        model = queryset.model
        suggestions = {
            'model': model.__name__,
            'current_query': str(queryset.query),
            'optimizations': [],
            'prefetch_suggestions': [],
            'index_suggestions': []
        }

        # Analyze relationships
        relationships = self._get_model_relationships(model)

        # Suggest select_related for forward relationships
        forward_relations = [
            rel for rel in relationships
            if rel['type'] in ['ForeignKey', 'OneToOneField']
        ]
        if forward_relations:
            suggestions['optimizations'].append({
                'type': 'select_related',
                'description': (
                    'Use select_related() for forward relationships '
                    'to reduce queries'
                ),
                'fields': [rel['field'] for rel in forward_relations],
                'example': (
                    f".select_related("
                    f"{', '.join(repr(rel['field']) for rel in forward_relations[:3])})"
                )
            })

        # Suggest prefetch_related for reverse/m2m relationships
        reverse_relations = [
            rel for rel in relationships
            if rel['type'] in ['ManyToManyField', 'reverse']
        ]
        if reverse_relations:
            prefetch_fields = []
            for rel in reverse_relations:
                prefetch_fields.append(rel['field'])
                suggestions['prefetch_suggestions'].append({
                    'field': rel['field'],
                    'type': rel['type'],
                    'description': (
                        f"Prefetch {rel['field']} to avoid N+1 queries"
                    )
                })

            if prefetch_fields:
                suggestions['optimizations'].append({
                    'type': 'prefetch_related',
                    'description': (
                        'Use prefetch_related() for reverse and '
                        'many-to-many relationships'
                    ),
                    'fields': prefetch_fields,
                    'example': (
                        f".prefetch_related("
                        f"{', '.join(repr(field) for field in prefetch_fields[:3])})"
                    )
                })

        # Suggest field selection optimizations
        all_fields = [
            f.name for f in model._meta.get_fields() if hasattr(f, 'name')
        ]
        text_fields = [
            f.name for f in model._meta.get_fields()
            if hasattr(f, 'name') and getattr(f, 'max_length', 0) > 500
        ]

        if text_fields:
            suggestions['optimizations'].append({
                'type': 'defer_large_fields',
                'description': 'Defer large text fields unless needed',
                'fields': text_fields,
                'example': f".defer({', '.join(repr(field) for field in text_fields)})"
            })

        # Suggest using only() for specific field access
        essential_fields = ['id', 'name', 'title', 'created_at', 'updated_at']
        available_essential = [f for f in essential_fields if f in all_fields]

        suggestions['optimizations'].append({
            'type': 'only_specific_fields',
            'description': 'Use only() when accessing specific fields',
            'fields': available_essential,
            'example': (
                f".only({', '.join(repr(field) for field in available_essential)})"
            )
        })

        return suggestions

    def _get_model_relationships(self, model) -> List[Dict[str, Any]]:
        """
        Get all relationships for a model.

        Args:
            model: Django model class

        Returns:
            List: Relationships with metadata
        """
        relationships = []

        # Forward relationships (ForeignKey, OneToOneField)
        for field in model._meta.get_fields():
            if isinstance(field, (ForeignKey, OneToOneField)):
                relationships.append({
                    'field': field.name,
                    'type': field.__class__.__name__,
                    'related_model': field.related_model.__name__,
                    'direction': 'forward'
                })
            elif isinstance(field, ManyToManyField):
                relationships.append({
                    'field': field.name,
                    'type': 'ManyToManyField',
                    'related_model': field.related_model.__name__,
                    'direction': 'forward'
                })

        # Reverse relationships
        for field in model._meta.get_fields():
            if isinstance(field, ForeignObjectRel):
                relationships.append({
                    'field': field.get_accessor_name(),
                    'type': 'reverse',
                    'related_model': field.related_model.__name__,
                    'direction': 'reverse'
                })

        return relationships

    def generate_prefetch_objects(
        self, model, depth: int = 2
    ) -> List[str]:
        """
        Generate optimized Prefetch objects for a model.

        Args:
            model: Django model class
            depth: Prefetch depth level

        Returns:
            List: Prefetch suggestions
        """
        relationships = self._get_model_relationships(model)
        prefetch_suggestions = []

        for rel in relationships:
            if rel['direction'] == 'reverse' or rel['type'] == 'ManyToManyField':
                # Basic prefetch
                prefetch_suggestions.append(f"'{rel['field']}'")

                # Nested prefetch with optimization
                if depth > 1:
                    try:
                        related_model = (
                            model._meta.get_field(rel['field']).related_model
                        )
                        related_relationships = (
                            self._get_model_relationships(related_model)
                        )

                        # Find important fields to select_related in prefetch
                        select_related_fields = [
                            r['field'] for r in related_relationships
                            if r['direction'] == 'forward'
                        ][:2]

                        if select_related_fields:
                            prefetch_obj = (
                                f"Prefetch('{rel['field']}', "
                                f"queryset={related_model.__name__}.objects"
                                f".select_related("
                                f"{', '.join(repr(f) for f in select_related_fields)}))"
                            )
                            prefetch_suggestions.append(prefetch_obj)
                    except (DatabaseError, IntegrityError, ObjectDoesNotExist):
                        pass

        return prefetch_suggestions


def suggest_optimizations(model_or_queryset) -> Dict[str, Any]:
    """
    Quick function to get optimization suggestions for a model or queryset.

    Args:
        model_or_queryset: Django Model class or QuerySet

    Returns:
        Dict: Optimization suggestions

    Usage:
        suggestions = suggest_optimizations(MyModel)
        # or
        suggestions = suggest_optimizations(MyModel.objects.all())
    """
    optimizer = QueryOptimizer()

    if isinstance(model_or_queryset, QuerySet):
        return optimizer.analyze_queryset(model_or_queryset)
    else:
        # Assume it's a model class
        queryset = model_or_queryset.objects.all()
        return optimizer.analyze_queryset(queryset)
