"""
Query optimization utilities for improving database performance.

This module provides mixins, utilities, and patterns for optimizing Django ORM queries
to reduce N+1 query problems and memory usage.
"""

from django.db import models
from django.core.paginator import Paginator
import logging

logger = logging.getLogger(__name__)


__all__ = [
    'QueryOptimizationMixin',
    'OptimizedQueryset',
    'OptimizedManager',
    'QueryAnalyzer',
    'CommonOptimizations',
]


class QueryOptimizationMixin:
    """
    Mixin for Django models and managers to provide optimized query methods.

    Usage:
        class MyModel(QueryOptimizationMixin, models.Model):
            # model fields...
            pass

        # In views or managers:
        optimized_queryset = MyModel.objects.with_optimizations()
    """

    @classmethod
    def get_select_related_fields(cls):
        """
        Override this method to define ForeignKey fields that should be select_related.

        Returns:
            list: List of field names for select_related optimization
        """
        return []

    @classmethod
    def get_prefetch_related_fields(cls):
        """
        Override this method to define Many-to-Many or reverse ForeignKey fields
        that should be prefetch_related.

        Returns:
            list: List of field names or Prefetch objects for prefetch_related optimization
        """
        return []


class OptimizedQueryset(models.QuerySet):
    """
    Custom queryset with built-in query optimizations.
    """

    def with_select_related(self, *fields):
        """
        Apply select_related with logging for debugging.
        """
        if fields:
            logger.debug(f"Applying select_related: {fields}")
            return self.select_related(*fields)
        return self

    def with_prefetch_related(self, *lookups):
        """
        Apply prefetch_related with logging for debugging.
        """
        if lookups:
            logger.debug(f"Applying prefetch_related: {lookups}")
            return self.prefetch_related(*lookups)
        return self

    def with_optimizations(self):
        """
        Apply all available optimizations for this model.
        """
        queryset = self

        # Apply select_related if model has the mixin
        if hasattr(self.model, 'get_select_related_fields'):
            select_fields = self.model.get_select_related_fields()
            if select_fields:
                queryset = queryset.with_select_related(*select_fields)

        # Apply prefetch_related if model has the mixin
        if hasattr(self.model, 'get_prefetch_related_fields'):
            prefetch_fields = self.model.get_prefetch_related_fields()
            if prefetch_fields:
                queryset = queryset.with_prefetch_related(*prefetch_fields)

        return queryset

    def paginate_efficiently(self, page_number, page_size=25, max_page_size=100):
        """
        Paginate queryset efficiently with bounds checking.

        Args:
            page_number: Page number to retrieve
            page_size: Number of items per page
            max_page_size: Maximum allowed page size for security

        Returns:
            Page object with optimized queryset
        """
        # Enforce maximum page size for security
        if page_size > max_page_size:
            logger.warning(f"Requested page size {page_size} exceeds maximum {max_page_size}")
            page_size = max_page_size

        # Apply optimizations before pagination
        optimized_queryset = self.with_optimizations()

        paginator = Paginator(optimized_queryset, page_size)

        # Handle invalid page numbers gracefully
        try:
            page_number = int(page_number)
            if page_number < 1:
                page_number = 1
            elif page_number > paginator.num_pages:
                page_number = paginator.num_pages
        except (ValueError, TypeError):
            page_number = 1

        return paginator.page(page_number)


class OptimizedManager(models.Manager):
    """
    Custom manager that returns OptimizedQueryset.
    """

    def get_queryset(self):
        return OptimizedQueryset(self.model, using=self._db)

    def with_optimizations(self):
        """
        Get all objects with optimizations applied.
        """
        return self.get_queryset().with_optimizations()


class QueryAnalyzer:
    """
    Utility class for analyzing and optimizing queries during development.
    """

    @staticmethod
    def analyze_queryset(queryset, operation_name="query"):
        """
        Log query analysis information for debugging.

        Args:
            queryset: Django queryset to analyze
            operation_name: Name of the operation for logging
        """
        from django.db import connection

        if logger.isEnabledFor(logging.DEBUG):
            # Count queries before execution
            queries_before = len(connection.queries)

            # Force evaluation
            list(queryset)

            # Count queries after execution
            queries_after = len(connection.queries)
            query_count = queries_after - queries_before

            logger.debug(
                f"Query analysis for {operation_name}: {query_count} queries executed"
            )

            # Log the actual queries in development
            if query_count > 1:
                logger.debug(f"Potential N+1 query issue detected in {operation_name}")
                for query in connection.queries[queries_before:queries_after]:
                    logger.debug(f"SQL: {query['sql']}")

    @staticmethod
    def check_n_plus_one(queryset, related_field, operation_name="query"):
        """
        Check for N+1 query problems when accessing related fields.

        Args:
            queryset: Django queryset to check
            related_field: Related field name to check
            operation_name: Name of the operation for logging
        """
        from django.db import connection

        queries_before = len(connection.queries)

        # Simulate accessing related field
        for obj in queryset:
            getattr(obj, related_field, None)

        queries_after = len(connection.queries)
        query_count = queries_after - queries_before

        if query_count > len(queryset):
            logger.warning(
                f"N+1 query detected in {operation_name} for field '{related_field}': "
                f"{query_count} queries for {len(queryset)} objects"
            )


# Common optimization patterns
class CommonOptimizations:
    """
    Collection of common query optimization patterns.
    """

    @staticmethod
    def optimize_user_queries(queryset):
        """
        Common optimizations for user-related queries.
        """
        return queryset.select_related('user', 'created_by', 'modified_by')

    @staticmethod
    def optimize_business_unit_queries(queryset):
        """
        Common optimizations for business unit related queries.
        """
        return queryset.select_related('bu', 'client', 'site')

    @staticmethod
    def optimize_ticket_queries(queryset):
        """
        Common optimizations for ticket-related queries.
        """
        return queryset.select_related(
            'assignedtopeople',
            'assignedtogroup',
            'ticketcategory',
            'bu'
        ).prefetch_related('attachments', 'history')

    @staticmethod
    def optimize_job_queries(queryset):
        """
        Common optimizations for job-related queries.
        """
        return queryset.select_related(
            'asset',
            'people',
            'pgroup',
            'cuser',
            'muser'
        ).prefetch_related('jobneeddetails_set', 'attachments')


# Usage examples and documentation
"""
Usage Examples:

1. Using the OptimizedManager:

    class MyModel(models.Model):
        name = models.CharField(max_length=100)
        category = models.ForeignKey(Category, on_delete=models.CASCADE)

        # Use the optimized manager
        objects = OptimizedManager()

        @classmethod
        def get_select_related_fields(cls):
            return ['category']

    # In views:
    optimized_items = MyModel.objects.with_optimizations()

2. Using QueryOptimizationMixin:

    class Ticket(QueryOptimizationMixin, models.Model):
        title = models.CharField(max_length=200)
        assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)
        category = models.ForeignKey(Category, on_delete=models.CASCADE)

        @classmethod
        def get_select_related_fields(cls):
            return ['assigned_to', 'category']

        @classmethod
        def get_prefetch_related_fields(cls):
            return ['attachments', 'comments']

3. Using pagination:

    from django.core.paginator import Paginator

    queryset = MyModel.objects.with_optimizations()
    page = queryset.paginate_efficiently(page_number=1, page_size=25)

4. Query analysis during development:

    from django.conf import settings

    if settings.DEBUG:
        QueryAnalyzer.analyze_queryset(
            queryset=MyModel.objects.all(),
            operation_name="my_view_query"
        )
"""