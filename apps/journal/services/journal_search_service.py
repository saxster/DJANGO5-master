"""
Journal Search Service

Handles search and filtering logic for journal entries.
Extracted from views.py to separate search concerns.
"""

import time

from django.db.models import Avg, Count, Q
from apps.journal.logging import get_journal_logger

logger = get_journal_logger(__name__)


class JournalSearchService:
    """Service for journal entry search and filtering"""

    def execute_database_search(self, user, search_params, result_serializer):
        """
        Execute search using database (placeholder for Elasticsearch)

        Args:
            user: User object
            search_params: Validated search parameters
            result_serializer: Serializer for results

        Returns:
            dict: Search results with facets and suggestions
        """
        from apps.journal.models import JournalEntry

        query_text = search_params['query']
        start = time.perf_counter()

        base_queryset = JournalEntry.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_deleted=False
        )
        queryset = self.build_privacy_aware_queryset(user, base_queryset)

        # Apply text search
        queryset = self._apply_text_search(queryset, query_text)

        # Apply filters
        queryset = self._apply_filters(queryset, search_params)

        total_results = queryset.count()

        # Apply sorting
        queryset = self._apply_sorting(queryset, search_params.get('sort_by', 'timestamp'))

        # Serialize results (limit to 50)
        limited_queryset = list(queryset[:50])
        results = result_serializer(limited_queryset, many=True, context={'request': None}).data

        facets = self._build_facets(queryset)
        suggestions = self._build_suggestions(limited_queryset, query_text)
        search_time_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            'results': results,
            'total_results': total_results,
            'search_time_ms': search_time_ms,
            'facets': facets,
            'search_suggestions': suggestions
        }

    def _apply_text_search(self, queryset, query_text):
        """Apply text search to queryset"""
        if query_text:
            return queryset.filter(
                Q(title__icontains=query_text) |
                Q(content__icontains=query_text) |
                Q(subtitle__icontains=query_text)
            )
        return queryset

    def _apply_filters(self, queryset, params):
        """Apply various filters to queryset"""
        # Entry type filter
        entry_types = params.get('entry_types')
        if entry_types:
            queryset = queryset.filter(entry_type__in=entry_types)

        # Date range filter
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if date_from and date_to:
            queryset = queryset.filter(timestamp__range=[date_from, date_to])

        # Mood filter
        if params.get('mood_min') and params.get('mood_max'):
            queryset = queryset.filter(
                mood_rating__range=[params['mood_min'], params['mood_max']]
            )

        # Stress filter
        if params.get('stress_min') and params.get('stress_max'):
            queryset = queryset.filter(
                stress_level__range=[params['stress_min'], params['stress_max']]
            )

        # Location filter
        location = params.get('location')
        if location:
            queryset = queryset.filter(location_site_name__icontains=location)

        # Tag filtering
        tags = params.get('tags', [])
        for tag in tags:
            queryset = queryset.filter(tags__contains=[tag])

        return queryset

    def _apply_sorting(self, queryset, sort_by):
        """Apply sorting to queryset"""
        if sort_by == 'relevance':
            # For database search, fall back to timestamp
            sort_by = '-timestamp'

        return queryset.order_by(sort_by)

    def track_search_interaction(self, user, search_params):
        """
        Track search interaction for analytics

        Args:
            user: User object
            search_params: Search parameters
        """
        try:
            logger.info(
                "journal_search",
                extra={'user_id': user.id, 'query': search_params['query']}
            )
        except (AttributeError, TypeError, KeyError) as e:
            logger.error(f"Failed to track search interaction: {e}", exc_info=True)

    def _build_facets(self, queryset):
        entry_type_counts = list(
            queryset.values('entry_type').annotate(total=Count('id')).order_by('-total')
        )
        mood_stats = queryset.aggregate(
            average_mood=Avg('mood_rating'),
            average_stress=Avg('stress_level'),
        )
        return {
            'entry_types': entry_type_counts,
            'wellbeing': mood_stats,
        }

    def _build_suggestions(self, entries, original_query):
        suggestions = set()
        normalized = (original_query or '').lower()
        for entry in entries:
            tags = entry.tags if isinstance(entry.tags, list) else []
            for tag in tags:
                if tag and normalized not in tag.lower():
                    suggestions.add(tag)
        return list(suggestions)[:5]

    def build_privacy_aware_queryset(self, user, base_queryset):
        """
        Build privacy-aware queryset

        Args:
            user: User object
            base_queryset: Base queryset to filter

        Returns:
            QuerySet: Privacy-filtered queryset
        """
        if user.is_superuser:
            return base_queryset

        # Users can only see their own entries or entries shared with them
        privacy_filter = Q(user=user) | Q(
            privacy_scope__in=['shared', 'team', 'manager'],
            sharing_permissions__contains=user.id
        )

        return base_queryset.filter(privacy_filter)

    def apply_query_parameters(self, queryset, query_params):
        """
        Apply query parameters to queryset

        Args:
            queryset: Base queryset
            query_params: Django request query_params

        Returns:
            QuerySet: Filtered queryset
        """
        # Entry types filter
        entry_types = query_params.getlist('entry_types')
        if entry_types:
            queryset = queryset.filter(entry_type__in=entry_types)

        # Date range filter
        date_from = query_params.get('date_from')
        date_to = query_params.get('date_to')
        if date_from and date_to:
            queryset = queryset.filter(timestamp__range=[date_from, date_to])

        # Wellbeing filters
        mood_min = query_params.get('mood_min')
        mood_max = query_params.get('mood_max')
        if mood_min and mood_max:
            queryset = queryset.filter(mood_rating__range=[mood_min, mood_max])

        stress_min = query_params.get('stress_min')
        stress_max = query_params.get('stress_max')
        if stress_min and stress_max:
            queryset = queryset.filter(stress_level__range=[stress_min, stress_max])

        # Location filtering
        location = query_params.get('location')
        if location:
            queryset = queryset.filter(location_site_name__icontains=location)

        # Tag filtering
        tags = query_params.getlist('tags')
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__contains=[tag])

        return queryset
