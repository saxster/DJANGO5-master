"""
Admin Help Service - Intelligent Help System for Django Admin

Provides contextual, AI-powered help for admin users with personalized
recommendations and semantic search.

Following .claude/rules.md:
- Rule #8: Utility functions <50 lines (atomic, testable)
- Rule #11: Specific exception handling
"""

import logging
from typing import List, Optional, Dict, Any
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Q, F
from django.core.cache import cache
from django.utils import timezone

from apps.core.services.base_service import BaseService
from apps.core.models.admin_help import AdminHelpTopic
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class AdminHelpService(BaseService):
    """
    Service layer for intelligent admin help functionality.
    
    Features:
    - Contextual help based on current admin page
    - Semantic search using PostgreSQL full-text search
    - Personalized tips based on user role/experience
    - Usage analytics and tracking
    """
    
    CACHE_TIMEOUT = 3600  # 1 hour
    
    @classmethod
    def get_contextual_help(
        cls,
        user,
        page_url: str,
        category: Optional[str] = None
    ) -> List[AdminHelpTopic]:
        """
        Get contextual help topics for the current admin page.
        
        Args:
            user: Current user requesting help
            page_url: Current admin page URL
            category: Optional category filter
            
        Returns:
            List of relevant help topics
        """
        cache_key = f"admin_help:contextual:{user.pk}:{page_url}:{category}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            cls.metrics.record_cache_hit()
            return cached_result
        
        cls.metrics.record_cache_miss()
        
        try:
            # Extract category from URL if not provided
            if not category:
                category = cls._extract_category_from_url(page_url)
            
            # Get active help topics for the category
            queryset = AdminHelpTopic.objects.filter(
                is_active=True
            ).select_related('tenant')
            
            if category:
                queryset = queryset.filter(category=category)
            
            # Order by popularity and difficulty
            topics = list(
                queryset.order_by(
                    '-helpful_count',
                    'difficulty_level',
                    '-view_count'
                )[:5]
            )
            
            cache.set(cache_key, topics, cls.CACHE_TIMEOUT)
            return topics
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error getting contextual help: {e}", exc_info=True)
            return []
    
    @classmethod
    def search_help(cls, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Semantic search across help topics using PostgreSQL full-text search.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of help topics with relevance ranking
        """
        if not query or len(query.strip()) < 2:
            return []
        
        try:
            search_query = SearchQuery(query, search_type='websearch')
            
            results = (
                AdminHelpTopic.objects
                .filter(is_active=True)
                .annotate(rank=SearchRank(F('search_vector'), search_query))
                .filter(rank__gte=0.1)
                .order_by('-rank', '-helpful_count')
                .select_related('tenant')
                [:limit]
            )
            
            # Convert to dict for easier consumption
            return [
                {
                    'id': topic.pk,
                    'category': topic.get_category_display(),
                    'feature_name': topic.feature_name,
                    'short_description': topic.short_description,
                    'difficulty': topic.get_difficulty_level_display(),
                    'rank': float(topic.rank),
                    'view_count': topic.view_count,
                }
                for topic in results
            ]
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error during help search: {e}", exc_info=True)
            return []
    
    @classmethod
    def get_quick_tips(cls, user, limit: int = 3) -> List[AdminHelpTopic]:
        """
        Get personalized quick tips based on user role and experience.
        
        Args:
            user: Current user
            limit: Number of tips to return
            
        Returns:
            List of relevant help topics
        """
        cache_key = f"admin_help:quick_tips:{user.pk}:{limit}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            cls.metrics.record_cache_hit()
            return cached_result
        
        cls.metrics.record_cache_miss()
        
        try:
            # Determine user's experience level
            difficulty = cls._determine_user_difficulty(user)
            
            # Get topics matching user's level that they haven't seen
            topics = list(
                AdminHelpTopic.objects
                .filter(is_active=True, difficulty_level=difficulty)
                .order_by('?')  # Random selection
                .select_related('tenant')
                [:limit]
            )
            
            # Fall back to beginner if no topics found
            if not topics:
                topics = list(
                    AdminHelpTopic.objects
                    .filter(is_active=True, difficulty_level='beginner')
                    .order_by('-helpful_count')
                    .select_related('tenant')
                    [:limit]
                )
            
            cache.set(cache_key, topics, cls.CACHE_TIMEOUT // 2)  # 30 min cache
            return topics
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error getting quick tips: {e}", exc_info=True)
            return []
    
    @classmethod
    def track_help_usage(
        cls,
        user,
        topic: AdminHelpTopic,
        action: str = 'view'
    ) -> bool:
        """
        Track help topic usage for analytics.
        
        Args:
            user: User who accessed the help
            topic: Help topic that was accessed
            action: Type of action (view, helpful, not_helpful)
            
        Returns:
            True if tracking succeeded, False otherwise
        """
        try:
            if action == 'view':
                topic.increment_view_count()
            elif action == 'helpful':
                topic.mark_as_helpful()
            
            logger.info(
                f"Help usage tracked: {action}",
                extra={
                    'user_id': user.pk,
                    'topic_id': topic.pk,
                    'topic_name': topic.feature_name,
                    'action': action,
                }
            )
            return True
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error tracking help usage: {e}", exc_info=True)
            return False
    
    @classmethod
    def get_popular_topics(cls, limit: int = 5) -> List[AdminHelpTopic]:
        """Get most popular help topics."""
        cache_key = f"admin_help:popular:{limit}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            topics = list(
                AdminHelpTopic.objects
                .filter(is_active=True)
                .order_by('-view_count', '-helpful_count')
                .select_related('tenant')
                [:limit]
            )
            
            cache.set(cache_key, topics, cls.CACHE_TIMEOUT)
            return topics
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error getting popular topics: {e}", exc_info=True)
            return []
    
    # Helper methods
    
    @staticmethod
    def _extract_category_from_url(page_url: str) -> Optional[str]:
        """Extract category from admin URL."""
        url_lower = page_url.lower()
        
        category_mapping = {
            'command': 'command_center',
            'workflow': 'workflows',
            'approval': 'approvals',
            'view': 'views',
            'report': 'reports',
            'notification': 'notifications',
            'alert': 'notifications',
            'schedule': 'scheduling',
            'team': 'team',
            'setting': 'settings',
        }
        
        for keyword, category in category_mapping.items():
            if keyword in url_lower:
                return category
        
        return None
    
    @staticmethod
    def _determine_user_difficulty(user) -> str:
        """Determine appropriate difficulty level for user."""
        # Simple heuristic: superusers = advanced, staff = intermediate, others = beginner
        if user.is_superuser:
            return 'advanced'
        elif user.is_staff:
            return 'intermediate'
        else:
            return 'beginner'
