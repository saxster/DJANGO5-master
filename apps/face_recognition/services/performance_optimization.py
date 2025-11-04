"""
Performance Optimization Service for Biometric Verification (Sprint 5.5)

Provides performance optimizations including:
- Model caching in Redis
- Batch embedding extraction
- Query optimization
- Connection pooling

Author: Development Team
Date: October 2025
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor
from apps.core.exceptions.patterns import PARSING_EXCEPTIONS

logger = logging.getLogger(__name__)


class BiometricPerformanceOptimizer:
    """
    Service for optimizing biometric verification performance.

    Implements caching, batching, and query optimization strategies.
    """

    def __init__(self):
        """Initialize performance optimizer."""
        # Cache TTLs (seconds)
        self.embedding_cache_ttl = 86400 * 30  # 30 days
        self.verification_result_cache_ttl = 86400  # 24 hours
        self.model_cache_ttl = 86400 * 7  # 7 days

        # Batch processing
        self.max_workers = 4
        self.batch_size = 10

    def cache_embedding(
        self,
        user_id: int,
        model_name: str,
        embedding: np.ndarray
    ) -> bool:
        """
        Cache face or voice embedding in Redis.

        Args:
            user_id: User ID
            model_name: Model name (FaceNet512, Resemblyzer, etc.)
            embedding: Embedding vector

        Returns:
            Boolean indicating cache success
        """
        try:
            cache_key = f"biometric:embedding:{model_name}:{user_id}"
            cache.set(
                cache_key,
                embedding.tolist(),
                timeout=self.embedding_cache_ttl
            )
            logger.debug(f"Cached embedding for user {user_id}, model {model_name}")
            return True

        except Exception as e:
            logger.error(f"Error caching embedding: {e}")
            return False

    def get_cached_embedding(
        self,
        user_id: int,
        model_name: str
    ) -> Optional[np.ndarray]:
        """
        Retrieve cached embedding from Redis.

        Args:
            user_id: User ID
            model_name: Model name

        Returns:
            Embedding vector or None if not cached
        """
        try:
            cache_key = f"biometric:embedding:{model_name}:{user_id}"
            cached_data = cache.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for user {user_id}, model {model_name}")
                return np.array(cached_data)
            else:
                logger.debug(f"Cache miss for user {user_id}, model {model_name}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving cached embedding: {e}")
            return None

    def invalidate_user_cache(self, user_id: int):
        """
        Invalidate all cached data for a user.

        Args:
            user_id: User ID
        """
        try:
            # Clear all embedding caches for user
            models = ['FaceNet512', 'ArcFace', 'InsightFace', 'Resemblyzer']
            for model_name in models:
                cache_key = f"biometric:embedding:{model_name}:{user_id}"
                cache.delete(cache_key)

            logger.info(f"Invalidated all caches for user {user_id}")

        except Exception as e:
            logger.error(f"Error invalidating user cache: {e}")

    def batch_extract_embeddings(
        self,
        image_paths: List[str],
        model
    ) -> List[Optional[np.ndarray]]:
        """
        Extract embeddings from multiple images in parallel.

        Args:
            image_paths: List of image file paths
            model: Face recognition model instance

        Returns:
            List of embeddings (same order as input)
        """
        try:
            if len(image_paths) <= 1:
                # No benefit from batching
                return [model.extract_features(image_paths[0])] if image_paths else []

            # Use ThreadPoolExecutor for parallel extraction
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                embeddings = list(executor.map(model.extract_features, image_paths))

            logger.info(f"Batch extracted {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Error in batch embedding extraction: {e}")
            return [None] * len(image_paths)

    def optimize_embedding_queries(self, user_ids: List[int], model_name: str):
        """
        Optimize database queries for embeddings using select_related.

        Args:
            user_ids: List of user IDs
            model_name: Model name to filter

        Returns:
            QuerySet optimized for bulk access
        """
        try:
            from apps.face_recognition.models import FaceEmbedding

            # Optimized query with select_related
            embeddings = FaceEmbedding.objects.filter(
                user_id__in=user_ids,
                model_name=model_name,
                is_active=True
            ).select_related('user').only(
                'id', 'embedding_vector', 'user_id', 'quality_score'
            )

            return embeddings

        except Exception as e:
            logger.error(f"Error optimizing embedding queries: {e}")
            return []

    def warm_cache_for_users(
        self,
        user_ids: List[int],
        model_names: List[str] = None
    ) -> int:
        """
        Pre-warm cache for list of users.

        Useful for anticipated verification sessions.

        Args:
            user_ids: List of user IDs
            model_names: List of model names (default: all models)

        Returns:
            Number of embeddings cached
        """
        try:
            if model_names is None:
                model_names = ['FaceNet512', 'ArcFace', 'InsightFace']

            cached_count = 0

            for model_name in model_names:
                embeddings = self.optimize_embedding_queries(user_ids, model_name)

                for embedding_obj in embeddings:
                    embedding_array = np.array(embedding_obj.embedding_vector)
                    success = self.cache_embedding(
                        embedding_obj.user_id,
                        model_name,
                        embedding_array
                    )
                    if success:
                        cached_count += 1

            logger.info(f"Cache warmed: {cached_count} embeddings for {len(user_ids)} users")
            return cached_count

        except Exception as e:
            logger.error(f"Error warming cache: {e}")
            return 0

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics.

        Returns:
            Dictionary with performance metrics
        """
        try:
            # Database connection stats
            db_stats = {
                'queries_executed': len(connection.queries) if connection.queries else 0,
            }

            # Cache stats (if available)
            cache_stats = {}
            try:
                # Try to get cache stats (Redis-specific)
                cache_info = cache._cache.get_stats() if hasattr(cache, '_cache') else {}
                cache_stats = cache_info
            except PARSING_EXCEPTIONS:
                cache_stats = {'note': 'Cache stats not available'}

            return {
                'database': db_stats,
                'cache': cache_stats,
                'timestamp': timezone.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {}
