"""
REST API Views for Help Center.

Provides 7 API endpoints:
1. POST /api/v2/help-center/search/ - Hybrid search
2. GET /api/v2/help-center/search/suggestions/ - Autocomplete
3. GET /api/v2/help-center/articles/{id}/ - Article detail
4. POST /api/v2/help-center/articles/{id}/vote/ - Vote helpful/not
5. GET /api/v2/help-center/contextual/?url= - Page-specific help
6. POST /api/v2/help-center/analytics/event/ - Track interactions
7. GET /api/v2/help-center/categories/ - Category list

Following CLAUDE.md:
- Rule #7: View methods <30 lines (delegate to services)
- Rule #11: Specific exception handling
- DRF best practices with permissions
"""

import uuid
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Count, Q
from apps.help_center.models import HelpArticle, HelpCategory, HelpArticleInteraction
from apps.help_center.serializers import (
    HelpTagSerializer,
    HelpCategorySerializer,
    HelpArticleListSerializer,
    HelpArticleDetailSerializer,
    HelpSearchRequestSerializer,
    HelpSearchResponseSerializer,
    HelpVoteSerializer,
    HelpAnalyticsEventSerializer,
)
from apps.help_center.services.search_service import SearchService
from apps.help_center.services.analytics_service import AnalyticsService
from apps.help_center.gamification_service import GamificationService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class HelpArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for help articles.

    - list: GET /api/v2/help-center/articles/
    - retrieve: GET /api/v2/help-center/articles/{id}/
    - search: POST /api/v2/help-center/search/
    - vote: POST /api/v2/help-center/articles/{id}/vote/
    """

    permission_classes = [IsAuthenticated]
    serializer_class = HelpArticleDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        """
        Filter published articles by user's tenant and roles.

        Query optimization:
        - select_related for category, authors
        - prefetch_related for tags
        """
        user = self.request.user
        qs = HelpArticle.objects.filter(
            tenant=user.tenant,
            status=HelpArticle.Status.PUBLISHED
        ).select_related(
            'category',
            'created_by',
            'last_updated_by'
        ).prefetch_related('tags')

        user_roles = list(user.groups.values_list('name', flat=True))
        qs = qs.filter(
            Q(target_roles__contains=user_roles) |
            Q(target_roles__contains=['all'])
        )

        return qs.order_by('-published_date')

    def get_serializer_class(self):
        """Use list serializer for list action, detail for retrieve."""
        if self.action == 'list':
            return HelpArticleListSerializer
        return HelpArticleDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        """Get article detail and increment view count."""
        article = self.get_object()

        article.view_count += 1
        article.save(update_fields=['view_count', 'updated_at'])

        if 'session_id' in request.query_params:
            try:
                session_id = uuid.UUID(request.query_params['session_id'])
                HelpArticleInteraction.record_view(
                    article=article,
                    user=request.user,
                    session_id=session_id,
                    referrer_url=request.META.get('HTTP_REFERER', '')
                )
                try:
                    GamificationService.award_points(request.user, 'article_view')
                except Exception as exc:  # Best-effort gamification
                    logger.debug(
                        "gamification_view_award_failed",
                        extra={'user': request.user.username, 'error': str(exc)}
                    )
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid session_id: {e}")

        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='search')
    def search(self, request):
        """
        Hybrid search endpoint.

        POST /api/v2/help-center/search/
        Body: {"query": "work order", "limit": 20, "role_filter": true}
        """
        serializer = HelpSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            search_results = SearchService.hybrid_search(
                tenant=request.user.tenant,
                user=request.user,
                query=serializer.validated_data['query'],
                limit=serializer.validated_data.get('limit', 20),
                role_filter=serializer.validated_data.get('role_filter', True)
            )

            return Response(search_results, status=status.HTTP_200_OK)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return Response(
                {'error': 'Search failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='vote')
    def vote(self, request, id=None):
        """
        Vote on article helpfulness.

        POST /api/v2/help-center/articles/{id}/vote/
        Body: {"is_helpful": true, "comment": "Great!"}
        """
        article = self.get_object()
        serializer = HelpVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            session_id = uuid.uuid4()
            if 'session_id' in request.query_params:
                try:
                    session_id = uuid.UUID(request.query_params['session_id'])
                except (ValueError, TypeError):
                    pass

            HelpArticleInteraction.record_vote(
                article=article,
                user=request.user,
                is_helpful=serializer.validated_data['is_helpful'],
                comment=serializer.validated_data.get('comment', ''),
                session_id=session_id
            )

            try:
                GamificationService.award_points(request.user, 'article_feedback')
            except Exception as exc:
                logger.debug(
                    "gamification_vote_award_failed",
                    extra={'user': request.user.username, 'error': str(exc)}
                )

            article.refresh_from_db()

            return Response({
                'success': True,
                'helpful_ratio': article.helpful_ratio,
                'message': 'Thank you for your feedback!'
            }, status=status.HTTP_200_OK)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Vote error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to record vote'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='contextual')
    def contextual_help(self, request):
        """
        Get contextual help for specific page.

        GET /api/v2/help-center/contextual/?url=/work-orders/create/
        """
        url_path = request.query_params.get('url', '')
        articles = self._get_contextual_articles(request.user, url_path)
        serializer = HelpArticleListSerializer(articles, many=True)

        return Response({
            'url': url_path,
            'articles': serializer.data,
            'message': 'Contextual help suggestions'
        }, status=status.HTTP_200_OK)

    def _get_contextual_articles(self, user, url_path: str):
        from urllib.parse import urlparse
        from apps.help_center.models import HelpArticleInteraction

        parsed_path = urlparse(url_path).path or '/'
        segments = [segment for segment in parsed_path.split('/') if segment]

        interaction_ids = list(
            HelpArticleInteraction.objects.filter(
                tenant=user.tenant,
                referrer_url__icontains=parsed_path
            )
            .values('article')
            .annotate(total=Count('id'))
            .order_by('-total')
            .values_list('article', flat=True)[:5]
        )

        queryset = self.get_queryset()
        if interaction_ids:
            articles = list(queryset.filter(id__in=interaction_ids))
            articles.sort(key=lambda article: interaction_ids.index(article.id))
            return articles

        if segments:
            query = Q()
            for segment in segments:
                query |= Q(slug__icontains=segment) | Q(title__icontains=segment) | Q(summary__icontains=segment)
            articles = list(queryset.filter(query)[:5])
            if articles:
                return articles

        return list(queryset[:5])


class HelpCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for help categories.

    - list: GET /api/v2/help-center/categories/
    - retrieve: GET /api/v2/help-center/categories/{id}/
    """

    permission_classes = [IsAuthenticated]
    serializer_class = HelpCategorySerializer

    def get_queryset(self):
        """Filter categories by user's tenant."""
        return HelpCategory.objects.filter(
            tenant=self.request.user.tenant,
            is_active=True
        ).select_related('parent').order_by('display_order', 'name')


class HelpAnalyticsViewSet(viewsets.ViewSet):
    """
    API endpoints for help analytics.

    - event: POST /api/v2/help-center/analytics/event/
    - dashboard: GET /api/v2/help-center/analytics/dashboard/
    """

    permission_classes = [IsAuthenticated]

    def create(self, request):
        """
        Track help interaction event.

        POST /api/v2/help-center/analytics/event/
        Body: {
            "event_type": "article_view",
            "article_id": 123,
            "session_id": "uuid",
            "time_spent_seconds": 45,
            "scroll_depth_percent": 80
        }
        """
        serializer = HelpAnalyticsEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event_data = serializer.validated_data

        event_type_map = {
            'article_view': HelpArticleInteraction.InteractionType.VIEW,
            'article_bookmark': HelpArticleInteraction.InteractionType.BOOKMARK,
            'article_share': HelpArticleInteraction.InteractionType.SHARE,
        }

        interaction_type = event_type_map.get(event_data['event_type'])

        if interaction_type and event_data.get('article_id'):
            try:
                article = HelpArticle.objects.get(
                    id=event_data['article_id'],
                    tenant=request.user.tenant
                )

                HelpArticleInteraction.objects.create(
                    article=article,
                    user=request.user,
                    interaction_type=interaction_type,
                    session_id=event_data['session_id'],
                    referrer_url=event_data.get('referrer_url', ''),
                    time_spent_seconds=event_data.get('time_spent_seconds'),
                    scroll_depth_percent=event_data.get('scroll_depth_percent'),
                    tenant=request.user.tenant
                )

                return Response({
                    'success': True,
                    'message': 'Event tracked successfully'
                }, status=status.HTTP_201_CREATED)

            except ObjectDoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Article not found'
                }, status=status.HTTP_404_NOT_FOUND)
            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Analytics event error: {e}", exc_info=True)
                return Response({
                    'success': False,
                    'message': 'Failed to track event'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'message': 'Event logged'
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """
        Get analytics dashboard data.

        GET /api/v2/help-center/analytics/dashboard/
        """
        from datetime import timedelta
        from django.utils import timezone

        date_from = timezone.now() - timedelta(days=30)
        date_to = timezone.now()

        try:
            metrics = AnalyticsService.get_effectiveness_dashboard(
                tenant=request.user.tenant,
                date_from=date_from,
                date_to=date_to
            )

            return Response(metrics, status=status.HTTP_200_OK)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Analytics dashboard error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to generate analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
