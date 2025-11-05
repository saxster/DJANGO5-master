"""
Journal Entry Views

CRUD operations for journal entries with privacy controls.
Refactored from views.py - each method < 30 lines, business logic in services.
"""

from rest_framework import viewsets, status
from apps.ontology.decorators import ontology
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from apps.journal.models import JournalEntry
from apps.journal.serializers import (
    JournalEntryListSerializer, JournalEntryDetailSerializer,
    JournalEntryCreateSerializer, JournalEntryUpdateSerializer
)
from apps.journal.services.journal_entry_service import JournalEntryService
from apps.journal.services.journal_search_service import JournalSearchService
from apps.journal.logging import get_journal_logger
from .permissions import JournalPermission

logger = get_journal_logger(__name__)


@ontology(
    domain="wellness",
    purpose="REST API for journal/wellness entries with privacy controls, pattern analysis, mobile sync, and ML-powered insights",
    api_endpoint=True,
    http_methods=["GET", "POST", "PATCH", "DELETE"],
    authentication_required=True,
    permissions=["JournalPermission (privacy-aware)"],
    rate_limit="200/minute",
    request_schema="JournalEntryCreateSerializer|JournalEntryUpdateSerializer",
    response_schema="JournalEntryListSerializer|JournalEntryDetailSerializer",
    error_codes=[400, 401, 403, 404, 500],
    criticality="high",
    tags=["api", "rest", "journal", "wellness", "privacy", "mobile", "ml", "analytics"],
    security_notes="Privacy scope filtering (private/shared/team). Tenant isolation. PII redaction in logs. Privacy consent tracking",
    endpoints={
        "list": "GET /api/journal/ - List journal entries (privacy-filtered)",
        "create": "POST /api/journal/ - Create entry with pattern analysis",
        "retrieve": "GET /api/journal/{id}/ - Get entry details",
        "update": "PATCH /api/journal/{id}/ - Update entry with reanalysis",
        "delete": "DELETE /api/journal/{id}/ - Soft delete entry",
        "bulk_create": "POST /api/journal/bulk-create/ - Bulk create for mobile sync",
        "analytics_summary": "GET /api/journal/analytics-summary/ - User wellbeing analytics",
        "bookmark": "POST /api/journal/{id}/bookmark/ - Toggle bookmark",
        "related_wellness_content": "GET /api/journal/{id}/related-wellness-content/ - Get wellness content"
    },
    examples=[
        "curl -X POST https://api.example.com/api/journal/ -H 'Authorization: Bearer <token>' -d '{\"title\":\"Daily Reflection\",\"mood_rating\":8,\"stress_level\":3}'"
    ]
)
class JournalEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for journal entries with privacy controls

    Provides CRUD operations, bulk operations, and analytics.
    All business logic delegated to services.
    """

    permission_classes = [JournalPermission]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry_service = JournalEntryService()
        self.search_service = JournalSearchService()

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        serializer_map = {
            'list': JournalEntryListSerializer,
            'create': JournalEntryCreateSerializer,
            'update': JournalEntryUpdateSerializer,
            'partial_update': JournalEntryUpdateSerializer,
        }
        return serializer_map.get(self.action, JournalEntryDetailSerializer)

    def get_queryset(self):
        """Optimized privacy-filtered queryset with tenant isolation"""
        if self._is_swagger_view():
            return JournalEntry.objects.none()

        queryset = self._build_base_queryset()
        queryset = self.search_service.build_privacy_aware_queryset(self.request.user, queryset)
        queryset = self.search_service.apply_query_parameters(queryset, self.request.query_params)

        return queryset.order_by('-timestamp').distinct()

    def _is_swagger_view(self):
        """Check if this is a swagger fake view"""
        return (getattr(self, 'swagger_fake_view', False) or
                getattr(self.request, 'swagger_fake_view', False))

    def _build_base_queryset(self):
        """Build base queryset with optimizations"""
        user = self.request.user
        return JournalEntry.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_deleted=False
        ).select_related(
            'user', 'tenant', 'wellbeing_metrics', 'work_context', 'sync_data'
        ).prefetch_related('media_attachments')

    def perform_create(self, serializer):
        """Create journal entry using service"""
        result = self.entry_service.create_entry_with_analysis(
            self.request.user,
            serializer.validated_data
        )
        if not result['success']:
            logger.error(f"Entry creation failed: {result.get('error')}")

    def perform_update(self, serializer):
        """Update journal entry using service"""
        result = self.entry_service.update_entry_with_reanalysis(
            self.get_object(),
            serializer.validated_data
        )
        if not result['success']:
            logger.error(f"Entry update failed: {result.get('error')}")

    def destroy(self, request, *args, **kwargs):
        """Soft delete journal entry"""
        instance = self.get_object()
        self.entry_service.soft_delete_entry(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create journal entries for mobile sync"""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        entries_data = request.data.get('entries', [])
        created_entries = []
        errors = []

        for entry_data in entries_data:
            try:
                serializer = JournalEntryCreateSerializer(
                    data=entry_data,
                    context={'request': request}
                )
                if serializer.is_valid():
                    result = self.entry_service.create_entry_with_analysis(
                        request.user,
                        serializer.validated_data
                    )
                    if result['success']:
                        created_entries.append(
                            JournalEntryDetailSerializer(result['journal_entry']).data
                        )
                else:
                    errors.append({'entry_data': entry_data, 'errors': serializer.errors})
            except DATABASE_EXCEPTIONS as e:
                errors.append({'entry_data': entry_data, 'errors': str(e)})

        return Response({
            'created_count': len(created_entries),
            'error_count': len(errors),
            'created_entries': created_entries,
            'errors': errors
        })

    @action(detail=False, methods=['get'])
    def analytics_summary(self, request):
        """Get analytics summary for user's journal entries"""
        user = request.user
        days = int(request.query_params.get('days', 30))

        try:
            from apps.journal.services.analytics_service import JournalAnalyticsService
            analytics_service = JournalAnalyticsService()
            analytics = analytics_service.generate_comprehensive_analytics(user, days)

            if analytics.get('insufficient_data'):
                return Response({
                    'has_data': False,
                    'message': analytics.get('message', 'Insufficient data'),
                    'current_entries': analytics.get('current_entries', 0)
                })

            return Response(analytics)

        except ImportError:
            # Fallback to basic analytics
            since_date = timezone.now() - timedelta(days=days)
            entries = self.get_queryset().filter(timestamp__gte=since_date, user=user)

            if not entries.exists():
                return Response({'has_data': False, 'message': 'No journal entries found'})

            analytics = self.entry_service.calculate_basic_analytics(entries)
            return Response(analytics)

    @action(detail=True, methods=['post'])
    def bookmark(self, request, pk=None):
        """Toggle bookmark status of journal entry"""
        entry = self.get_object()
        result = self.entry_service.toggle_bookmark(entry)
        return Response(result)

    @action(detail=True, methods=['get'])
    def related_wellness_content(self, request, pk=None):
        """Get wellness content related to this journal entry"""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        try:
            # TODO: Integration with wellness content system
            return Response({
                'triggered_content': [],
                'contextual_content': [],
                'message': 'Wellness content integration pending implementation'
            })
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to get related wellness content: {e}")
            return Response(
                {'error': 'Failed to retrieve wellness content'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
