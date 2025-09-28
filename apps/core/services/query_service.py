"""
Optimized query service to prevent N+1 queries and improve database performance.
Provides centralized query optimization patterns.
"""

import logging
from django.core.cache import cache
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """
    Service class for optimizing database queries and preventing N+1 problems.
    """

    @staticmethod
    def optimize_people_queries(queryset: QuerySet) -> QuerySet:
        """
        Optimize People model queries with proper select_related and prefetch_related.

        Args:
            queryset: Base People queryset

        Returns:
            Optimized queryset
        """
        return (
            queryset
            .select_related(
                'department',
                'designation',
                'peopletype',
                'worktype',
                'client',
                'bu',
                'reportto',
                'location'
            )
            .prefetch_related(
                'pgbelongs_peoples__pgroup',
                'pgbelongs_peoples__assignsites',
                Prefetch(
                    'children',
                    queryset=queryset.model.objects.filter(enable=True)
                    .select_related('department', 'designation')
                )
            )
        )

    @staticmethod
    def optimize_question_queries(queryset: QuerySet) -> QuerySet:
        """
        Optimize Question model queries.

        Args:
            queryset: Base Question queryset

        Returns:
            Optimized queryset
        """
        return (
            queryset
            .select_related('unit', 'client', 'bu')
            .prefetch_related(
                Prefetch(
                    'questionsetbelonging_set',
                    queryset=queryset.model._meta.get_field(
                        'questionsetbelonging_set'
                    ).related_model.objects.select_related('qset')
                )
            )
        )

    @staticmethod
    def optimize_questionset_queries(queryset: QuerySet) -> QuerySet:
        """
        Optimize QuestionSet model queries.

        Args:
            queryset: Base QuestionSet queryset

        Returns:
            Optimized queryset
        """
        from apps.activity.models.question_model import QuestionSetBelonging

        return (
            queryset
            .select_related('unit', 'bu', 'client')
            .prefetch_related(
                Prefetch(
                    'questionsetbelonging_set',
                    queryset=QuestionSetBelonging.objects.select_related('question')
                    .order_by('seqno')
                )
            )
            .annotate(
                question_count=Count('questionsetbelonging'),
                mandatory_count=Count(
                    'questionsetbelonging',
                    filter=Q(questionsetbelonging__ismandatory=True)
                )
            )
        )

    @staticmethod
    def optimize_asset_queries(queryset: QuerySet) -> QuerySet:
        """
        Optimize Asset model queries.

        Args:
            queryset: Base Asset queryset

        Returns:
            Optimized queryset
        """
        return (
            queryset
            .select_related('parent', 'type', 'bu', 'location', 'client')
            .prefetch_related(
                Prefetch(
                    'children',
                    queryset=queryset.model.objects.filter(enable=True)
                    .select_related('type', 'location')
                )
            )
        )

    @staticmethod
    def get_optimized_list_queryset(
        model_class: Type[Model],
        filters: Optional[Dict[str, Any]] = None,
        search_fields: Optional[List[str]] = None,
        search_term: Optional[str] = None,
        ordering: Optional[List[str]] = None
    ) -> QuerySet:
        """
        Get an optimized queryset for list views with common patterns.

        Args:
            model_class: Django model class
            filters: Filter conditions
            search_fields: Fields to search in
            search_term: Search term
            ordering: Ordering fields

        Returns:
            Optimized queryset
        """
        try:
            # Start with base queryset
            queryset = model_class.objects.all()

            # Apply model-specific optimizations
            if hasattr(model_class, '_meta'):
                model_name = model_class._meta.model_name

                if model_name == 'people':
                    queryset = QueryOptimizer.optimize_people_queries(queryset)
                elif model_name == 'question':
                    queryset = QueryOptimizer.optimize_question_queries(queryset)
                elif model_name == 'questionset':
                    queryset = QueryOptimizer.optimize_questionset_queries(queryset)
                elif model_name == 'asset':
                    queryset = QueryOptimizer.optimize_asset_queries(queryset)

            # Apply filters
            if filters:
                queryset = queryset.filter(**filters)

            # Apply search
            if search_term and search_fields:
                search_q = Q()
                for field in search_fields:
                    search_q |= Q(**{f"{field}__icontains": search_term})
                queryset = queryset.filter(search_q)

            # Apply ordering
            if ordering:
                queryset = queryset.order_by(*ordering)
            elif hasattr(model_class._meta, 'ordering') and model_class._meta.ordering:
                queryset = queryset.order_by(*model_class._meta.ordering)

            return queryset

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            ErrorHandler.handle_exception(
                e,
                context={
                    'method': 'get_optimized_list_queryset',
                    'model': model_class.__name__ if model_class else None,
                    'filters': filters,
                    'search_fields': search_fields
                }
            )
            return model_class.objects.none()


class CachedQueryService:
    """
    Service for cached queries to improve performance.
    """

    @staticmethod
    def get_cached_choices(
        cache_key: str,
        model_class: Type[Model],
        value_field: str = 'id',
        label_field: str = 'name',
        filters: Optional[Dict[str, Any]] = None,
        timeout: int = 3600
    ) -> List[Dict[str, Any]]:
        """
        Get cached choices for dropdowns and selects.

        Args:
            cache_key: Unique cache key
            model_class: Django model class
            value_field: Field to use as value
            label_field: Field to use as label
            filters: Optional filters
            timeout: Cache timeout in seconds

        Returns:
            List of choice dictionaries
        """
        try:
            # Try to get from cache first
            choices = cache.get(cache_key)
            if choices is not None:
                return choices

            # Generate choices
            queryset = model_class.objects.all()

            if filters:
                queryset = queryset.filter(**filters)

            # Optimize for commonly accessed fields
            if hasattr(model_class._meta.get_field(label_field), 'related_model'):
                # If label_field is a foreign key, select_related
                queryset = queryset.select_related(label_field.split('__')[0])

            choices = list(
                queryset.values(value_field, label_field)
                .order_by(label_field)
            )

            # Cache the results
            cache.set(cache_key, choices, timeout)
            return choices

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            ErrorHandler.handle_exception(
                e,
                context={
                    'method': 'get_cached_choices',
                    'cache_key': cache_key,
                    'model': model_class.__name__ if model_class else None
                }
            )
            return []

    @staticmethod
    def invalidate_related_caches(model_instance: Model) -> None:
        """
        Invalidate caches related to a model instance.

        Args:
            model_instance: Model instance that was updated
        """
        try:
            model_name = model_instance._meta.model_name
            app_label = model_instance._meta.app_label

            # Common cache patterns to invalidate
            cache_patterns = [
                f"{app_label}_{model_name}_choices",
                f"{app_label}_{model_name}_list",
                f"{model_name}_dropdown",
                f"{model_name}_select",
            ]

            # Add tenant-specific caches if applicable
            if hasattr(model_instance, 'client_id') and model_instance.client_id:
                cache_patterns.extend([
                    f"{pattern}_client_{model_instance.client_id}"
                    for pattern in cache_patterns
                ])

            if hasattr(model_instance, 'bu_id') and model_instance.bu_id:
                cache_patterns.extend([
                    f"{pattern}_bu_{model_instance.bu_id}"
                    for pattern in cache_patterns
                ])

            # Delete cache entries
            cache.delete_many(cache_patterns)

            logger.info(
                f"Invalidated caches for {model_name}",
                extra={'patterns': cache_patterns}
            )

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            ErrorHandler.handle_exception(
                e,
                context={
                    'method': 'invalidate_related_caches',
                    'model': model_instance.__class__.__name__ if model_instance else None
                }
            )


class PaginationService:
    """
    Optimized pagination service.
    """

    @staticmethod
    def paginate_queryset(
        queryset: QuerySet,
        page: int = 1,
        page_size: int = 25,
        max_page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Paginate queryset efficiently.

        Args:
            queryset: QuerySet to paginate
            page: Page number (1-based)
            page_size: Number of items per page
            max_page_size: Maximum allowed page size

        Returns:
            Dictionary with paginated data and metadata
        """
        try:
            # Validate and limit page size
            page_size = min(page_size, max_page_size)
            page = max(page, 1)

            # Use efficient count for large datasets
            total_count = queryset.count()

            if total_count == 0:
                return {
                    'items': [],
                    'total_count': 0,
                    'page': 1,
                    'page_size': page_size,
                    'total_pages': 0,
                    'has_next': False,
                    'has_previous': False
                }

            paginator = Paginator(queryset, page_size)
            total_pages = paginator.num_pages

            # Ensure page is within range
            page = min(page, total_pages)

            page_obj = paginator.get_page(page)

            return {
                'items': list(page_obj),
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            ErrorHandler.handle_exception(
                e,
                context={
                    'method': 'paginate_queryset',
                    'page': page,
                    'page_size': page_size
                }
            )
            return {
                'items': [],
                'total_count': 0,
                'page': 1,
                'page_size': page_size,
                'total_pages': 0,
                'has_next': False,
                'has_previous': False
            }


class BulkOperationService:
    """
    Service for efficient bulk database operations.
    """

    @staticmethod
    def bulk_create_with_validation(
        model_class: Type[Model],
        data_list: List[Dict[str, Any]],
        batch_size: int = 1000,
        ignore_conflicts: bool = False
    ) -> Dict[str, Any]:
        """
        Perform bulk create with proper validation and error handling.

        Args:
            model_class: Django model class
            data_list: List of data dictionaries
            batch_size: Number of objects to create per batch
            ignore_conflicts: Whether to ignore conflicts

        Returns:
            Dictionary with operation results
        """
        try:
            created_objects = []
            errors = []

            for i in range(0, len(data_list), batch_size):
                batch = data_list[i:i + batch_size]

                try:
                    # Create model instances
                    instances = []
                    for data in batch:
                        try:
                            instance = model_class(**data)
                            instance.full_clean()  # Validate
                            instances.append(instance)
                        except (TypeError, ValidationError, ValueError) as e:
                            errors.append({
                                'data': data,
                                'error': str(e)
                            })

                    # Bulk create valid instances
                    if instances:
                        created = model_class.objects.bulk_create(
                            instances,
                            ignore_conflicts=ignore_conflicts
                        )
                        created_objects.extend(created)

                except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
                    ErrorHandler.handle_exception(
                        e,
                        context={
                            'method': 'bulk_create_with_validation',
                            'model': model_class.__name__,
                            'batch_start': i
                        }
                    )
                    errors.append({
                        'batch_start': i,
                        'error': str(e)
                    })

            return {
                'success': True,
                'created_count': len(created_objects),
                'error_count': len(errors),
                'errors': errors
            }

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'method': 'bulk_create_with_validation',
                    'model': model_class.__name__,
                    'data_count': len(data_list)
                }
            )
            return {
                'success': False,
                'message': 'Bulk create operation failed',
                'correlation_id': correlation_id
            }

    @staticmethod
    def bulk_update_with_validation(
        queryset: QuerySet,
        updates: Dict[str, Any],
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Perform bulk update with proper validation.

        Args:
            queryset: QuerySet of objects to update
            updates: Fields and values to update
            batch_size: Number of objects to update per batch

        Returns:
            Dictionary with operation results
        """
        try:
            total_updated = 0

            # Process in batches to avoid memory issues
            while True:
                batch_ids = list(
                    queryset.values_list('id', flat=True)[:batch_size]
                )

                if not batch_ids:
                    break

                updated_count = (
                    queryset.model.objects
                    .filter(id__in=batch_ids)
                    .update(**updates)
                )

                total_updated += updated_count

                # If we got fewer than batch_size, we're done
                if len(batch_ids) < batch_size:
                    break

            return {
                'success': True,
                'updated_count': total_updated
            }

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'method': 'bulk_update_with_validation',
                    'updates': list(updates.keys())
                }
            )
            return {
                'success': False,
                'message': 'Bulk update operation failed',
                'correlation_id': correlation_id
            }