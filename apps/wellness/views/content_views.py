"""
Content Views - Wellness content listing, filtering, and interaction tracking

Provides:
- Read-only access to wellness content (list, detail)
- Content filtering by category, evidence level, workplace relevance
- Interaction tracking for content engagement
- Category browsing with content counts
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.wellness.models import WellnessContent
from apps.wellness.serializers import (
    WellnessContentListSerializer,
    WellnessContentDetailSerializer,
    WellnessContentInteractionCreateSerializer
)
from apps.wellness.logging import get_wellness_logger
from .permissions import WellnessPermission

logger = get_wellness_logger(__name__)


class WellnessContentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for wellness content with filtering and analytics"""

    permission_classes = [WellnessPermission]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return WellnessContentListSerializer
        else:
            return WellnessContentDetailSerializer

    def get_queryset(self):
        """Filtered queryset for wellness content"""
        user = self.request.user

        # Base queryset with tenant filtering
        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True
        ).select_related('created_by', 'tenant').prefetch_related('interactions')

        # Apply filters
        queryset = self._apply_filters(queryset)

        return queryset.order_by('-priority_score', '-created_at')

    def _apply_filters(self, queryset):
        """Apply query parameter filters to queryset"""
        filters = {
            'category': self.request.query_params.get('category'),
            'evidence_level': self.request.query_params.get('evidence_level'),
            'content_level': self.request.query_params.get('content_level'),
        }

        # Apply simple filters
        for field, value in filters.items():
            if value:
                queryset = queryset.filter(**{field: value})

        # Boolean filters
        if self.request.query_params.get('workplace_specific') == 'true':
            queryset = queryset.filter(workplace_specific=True)

        if self.request.query_params.get('field_worker_relevant') == 'true':
            queryset = queryset.filter(field_worker_relevant=True)

        if self.request.query_params.get('high_evidence') == 'true':
            queryset = queryset.filter(evidence_level__in=['who_cdc', 'peer_reviewed'])

        return queryset

    @action(detail=True, methods=['post'])
    def track_interaction(self, request, pk=None):
        """Track user interaction with wellness content"""
        content = self.get_object()

        serializer = WellnessContentInteractionCreateSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            interaction = serializer.save(content=content)

            logger.info(f"Wellness interaction tracked: {request.user.peoplename} "
                       f"{interaction.interaction_type} '{content.title}'")

            return Response({
                'interaction_id': interaction.id,
                'engagement_score': interaction.engagement_score,
                'message': 'Interaction tracked successfully'
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get wellness categories with content counts"""
        categories = []

        for category_code, category_name in WellnessContent.WellnessContentCategory.choices:
            content_count = WellnessContent.objects.filter(
                category=category_code,
                is_active=True,
                tenant=getattr(request.user, 'tenant', None)
            ).count()

            categories.append({
                'code': category_code,
                'name': category_name,
                'content_count': content_count
            })

        return Response({
            'categories': categories,
            'total_content': sum(cat['content_count'] for cat in categories)
        })
