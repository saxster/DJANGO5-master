"""
Database Query Optimization Service.

This service provides comprehensive query optimization patterns to eliminate N+1 queries
and improve database performance through strategic use of select_related and prefetch_related.

CRITICAL: This addresses the performance vulnerability where 496 query patterns across
185 files were identified without proper optimization.
"""
import logging
from typing import Dict, Any, Type, List, Tuple, Optional
from django.db import models
from django.db.models import QuerySet, Prefetch
from apps.core.error_handling import ErrorHandler
from apps.core.middleware.logging_sanitization import sanitized_info, sanitized_warning

logger = logging.getLogger("query_optimization")


class QueryOptimizer:
    """
    Service class for optimizing Django ORM queries to prevent N+1 query problems.

    This service analyzes model relationships and applies appropriate select_related
    and prefetch_related optimizations automatically.
    """

    # Cache for model relationship analysis
    _relationship_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def optimize_queryset(cls, queryset: QuerySet, optimization_profile: str = 'default') -> QuerySet:
        """
        Optimize a queryset by automatically applying select_related and prefetch_related.

        Args:
            queryset: The queryset to optimize
            optimization_profile: Optimization profile ('default', 'aggressive', 'minimal')

        Returns:
            QuerySet: Optimized queryset with relationships preloaded
        """
        try:
            model = queryset.model
            model_key = f"{model._meta.app_label}.{model._meta.model_name}"

            # Get or analyze relationships
            if model_key not in cls._relationship_cache:
                cls._analyze_model_relationships(model)

            relationships = cls._relationship_cache[model_key]

            # Apply optimizations based on profile
            if optimization_profile == 'aggressive':
                return cls._apply_aggressive_optimization(queryset, relationships)
            elif optimization_profile == 'minimal':
                return cls._apply_minimal_optimization(queryset, relationships)
            else:
                return cls._apply_default_optimization(queryset, relationships)

        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'optimize_queryset',
                    'model': str(queryset.model),
                    'profile': optimization_profile
                }
            )
            sanitized_warning(
                logger,
                f"Query optimization failed, using original queryset (ID: {correlation_id})"
            )
            return queryset

    @classmethod
    def _analyze_model_relationships(cls, model: Type[models.Model]) -> None:
        """
        Analyze model relationships for optimization opportunities.

        Args:
            model: Django model class to analyze
        """
        model_key = f"{model._meta.app_label}.{model._meta.model_name}"

        relationships = {
            'foreign_keys': [],
            'one_to_one': [],
            'many_to_many': [],
            'reverse_foreign_keys': [],
            'reverse_many_to_many': []
        }

        try:
            # Analyze forward relationships
            for field in model._meta.get_fields():
                if field.is_relation:
                    if field.many_to_one or field.one_to_one:
                        # ForeignKey or OneToOneField
                        field_info = {
                            'name': field.name,
                            'related_model': field.related_model,
                            'nullable': getattr(field, 'null', False),
                            'performance_impact': cls._assess_performance_impact(field)
                        }

                        if field.one_to_one:
                            relationships['one_to_one'].append(field_info)
                        else:
                            relationships['foreign_keys'].append(field_info)

                    elif field.many_to_many:
                        # ManyToManyField
                        field_info = {
                            'name': field.name,
                            'related_model': field.related_model,
                            'through': getattr(field, 'through', None),
                            'performance_impact': cls._assess_performance_impact(field)
                        }
                        relationships['many_to_many'].append(field_info)

                    elif field.one_to_many:
                        # Reverse ForeignKey
                        field_info = {
                            'name': field.get_accessor_name(),
                            'related_model': field.related_model,
                            'related_name': field.related_name,
                            'performance_impact': cls._assess_performance_impact(field)
                        }
                        relationships['reverse_foreign_keys'].append(field_info)

            cls._relationship_cache[model_key] = relationships

            sanitized_info(
                logger,
                f"Analyzed relationships for model {model_key}",
                extra={
                    'foreign_keys_count': len(relationships['foreign_keys']),
                    'many_to_many_count': len(relationships['many_to_many']),
                    'reverse_relations_count': len(relationships['reverse_foreign_keys'])
                }
            )

        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'analyze_model_relationships', 'model': str(model)}
            )
            sanitized_warning(
                logger,
                f"Relationship analysis failed for model {model_key} (ID: {correlation_id})"
            )

    @classmethod
    def _assess_performance_impact(cls, field) -> str:
        """
        Assess the performance impact of a relationship field.

        Args:
            field: Django model field

        Returns:
            str: Performance impact level ('high', 'medium', 'low')
        """
        # High impact: Non-nullable foreign keys to commonly accessed models
        if hasattr(field, 'null') and not field.null:
            return 'high'

        # Medium impact: Nullable foreign keys and one-to-one relationships
        if field.many_to_one or field.one_to_one:
            return 'medium'

        # Low impact: Many-to-many and reverse relationships (prefetch candidates)
        return 'low'

    @classmethod
    def _apply_default_optimization(cls, queryset: QuerySet, relationships: Dict[str, Any]) -> QuerySet:
        """
        Apply default optimization strategy.

        Args:
            queryset: Queryset to optimize
            relationships: Analyzed relationships

        Returns:
            QuerySet: Optimized queryset
        """
        optimized = queryset

        # Select related for high-impact foreign keys
        select_related_fields = []
        for fk in relationships['foreign_keys']:
            if fk['performance_impact'] == 'high':
                select_related_fields.append(fk['name'])

        # Add high-impact one-to-one relationships
        for o2o in relationships['one_to_one']:
            if o2o['performance_impact'] in ['high', 'medium']:
                select_related_fields.append(o2o['name'])

        if select_related_fields:
            optimized = optimized.select_related(*select_related_fields)

        # Prefetch related for many-to-many and important reverse relationships
        prefetch_related_fields = []
        for m2m in relationships['many_to_many']:
            if m2m['performance_impact'] in ['high', 'medium']:
                prefetch_related_fields.append(m2m['name'])

        # Add some reverse foreign keys with medium/high impact
        for rfk in relationships['reverse_foreign_keys']:
            if rfk['performance_impact'] == 'high':
                prefetch_related_fields.append(rfk['name'])

        if prefetch_related_fields:
            optimized = optimized.prefetch_related(*prefetch_related_fields)

        return optimized

    @classmethod
    def _apply_aggressive_optimization(cls, queryset: QuerySet, relationships: Dict[str, Any]) -> QuerySet:
        """
        Apply aggressive optimization strategy (may over-fetch data).

        Args:
            queryset: Queryset to optimize
            relationships: Analyzed relationships

        Returns:
            QuerySet: Heavily optimized queryset
        """
        optimized = queryset

        # Select all foreign keys and one-to-one relationships
        select_related_fields = []
        for fk in relationships['foreign_keys']:
            select_related_fields.append(fk['name'])
        for o2o in relationships['one_to_one']:
            select_related_fields.append(o2o['name'])

        if select_related_fields:
            optimized = optimized.select_related(*select_related_fields)

        # Prefetch all many-to-many and reverse relationships
        prefetch_related_fields = []
        for m2m in relationships['many_to_many']:
            prefetch_related_fields.append(m2m['name'])
        for rfk in relationships['reverse_foreign_keys']:
            prefetch_related_fields.append(rfk['name'])

        if prefetch_related_fields:
            optimized = optimized.prefetch_related(*prefetch_related_fields)

        return optimized

    @classmethod
    def _apply_minimal_optimization(cls, queryset: QuerySet, relationships: Dict[str, Any]) -> QuerySet:
        """
        Apply minimal optimization strategy (only critical relationships).

        Args:
            queryset: Queryset to optimize
            relationships: Analyzed relationships

        Returns:
            QuerySet: Minimally optimized queryset
        """
        optimized = queryset

        # Only select related for absolutely critical foreign keys
        select_related_fields = []
        for fk in relationships['foreign_keys']:
            if fk['performance_impact'] == 'high' and not fk['nullable']:
                select_related_fields.append(fk['name'])

        if select_related_fields:
            optimized = optimized.select_related(*select_related_fields)

        return optimized

    @classmethod
    def optimize_people_queries(cls) -> QuerySet:
        """
        Optimized queryset for People model with common relationships.

        Returns:
            QuerySet: Optimized People queryset
        """
        from apps.peoples.models import People

        return People.objects.select_related(
            'shift',
            'bt',
            'geofences',
            'user'
        ).prefetch_related(
            'pgbelongs_peoples__pgroup',
            'groups',
            'user_permissions',
            'people_attachments'
        )

    @classmethod
    def optimize_activity_queries(cls) -> QuerySet:
        """
        Optimized queryset for Activity/Job related models.

        Returns:
            QuerySet: Optimized queryset for activity models
        """
        from apps.activity.models.job_model import Job

        return Job.objects.select_related(
            'jobneed',
            'asset',
            'asset__location',
            'asset__created_by',
            'people',
            'people__shift',
            'people__bt'
        ).prefetch_related(
            'job_attachments',
            'job_questions',
            'job_details'
        )

    @classmethod
    def create_optimized_prefetch(cls, related_name: str, queryset: Optional[QuerySet] = None,
                                 to_attr: Optional[str] = None) -> Prefetch:
        """
        Create an optimized Prefetch object for complex relationships.

        Args:
            related_name: Name of the related field
            queryset: Optional queryset to use for the prefetch
            to_attr: Optional attribute name to store results

        Returns:
            Prefetch: Optimized Prefetch object
        """
        if queryset is not None:
            # Apply optimization to the provided queryset
            optimized_qs = cls.optimize_queryset(queryset)
        else:
            optimized_qs = None

        return Prefetch(
            related_name,
            queryset=optimized_qs,
            to_attr=to_attr
        )

    @classmethod
    def analyze_query_performance(cls, queryset: QuerySet) -> Dict[str, Any]:
        """
        Analyze query performance and provide optimization recommendations.

        Args:
            queryset: Queryset to analyze

        Returns:
            dict: Performance analysis and recommendations
        """
        analysis = {
            'query_count_estimate': 1,  # Base query
            'optimization_opportunities': [],
            'current_optimizations': {
                'select_related': [],
                'prefetch_related': []
            },
            'recommendations': []
        }

        try:
            # Check current optimizations
            query = queryset.query

            # Analyze select_related usage
            if hasattr(query, 'select_related') and query.select_related:
                analysis['current_optimizations']['select_related'] = list(query.select_related.keys())

            # Analyze prefetch_related usage
            if hasattr(queryset, '_prefetch_related_lookups'):
                analysis['current_optimizations']['prefetch_related'] = list(queryset._prefetch_related_lookups)

            # Get model relationships
            model = queryset.model
            model_key = f"{model._meta.app_label}.{model._meta.model_name}"

            if model_key not in cls._relationship_cache:
                cls._analyze_model_relationships(model)

            relationships = cls._relationship_cache[model_key]

            # Estimate query count
            query_count = 1  # Base query

            # Add potential N+1 queries
            for fk in relationships['foreign_keys']:
                if fk['name'] not in analysis['current_optimizations']['select_related']:
                    query_count += 1  # Potential N+1
                    analysis['optimization_opportunities'].append({
                        'type': 'select_related',
                        'field': fk['name'],
                        'impact': fk['performance_impact']
                    })

            for m2m in relationships['many_to_many']:
                if m2m['name'] not in analysis['current_optimizations']['prefetch_related']:
                    query_count += 1  # Potential N+1
                    analysis['optimization_opportunities'].append({
                        'type': 'prefetch_related',
                        'field': m2m['name'],
                        'impact': m2m['performance_impact']
                    })

            analysis['query_count_estimate'] = query_count

            # Generate recommendations
            if analysis['optimization_opportunities']:
                high_impact_ops = [op for op in analysis['optimization_opportunities']
                                 if op['impact'] == 'high']
                if high_impact_ops:
                    analysis['recommendations'].append(
                        f"Apply {len(high_impact_ops)} high-impact optimizations immediately"
                    )

                analysis['recommendations'].append(
                    f"Consider using QueryOptimizer.optimize_queryset() for automatic optimization"
                )

        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'analyze_query_performance', 'model': str(queryset.model)}
            )
            analysis['error'] = f"Analysis failed (ID: {correlation_id})"

        return analysis

    @classmethod
    def clear_cache(cls):
        """Clear the relationship analysis cache."""
        cls._relationship_cache.clear()
        sanitized_info(logger, "Query optimization cache cleared")


# Convenience functions for common use cases
def get_optimized_people():
    """Get optimized People queryset."""
    return QueryOptimizer.optimize_people_queries()


def get_optimized_activities():
    """Get optimized Activity queryset."""
    return QueryOptimizer.optimize_activity_queries()


def optimize_queryset(queryset: QuerySet, profile: str = 'default') -> QuerySet:
    """
    Optimize any queryset using the QueryOptimizer.

    Args:
        queryset: Queryset to optimize
        profile: Optimization profile ('default', 'aggressive', 'minimal')

    Returns:
        QuerySet: Optimized queryset
    """
    return QueryOptimizer.optimize_queryset(queryset, profile)