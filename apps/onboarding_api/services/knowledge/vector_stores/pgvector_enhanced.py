import logging
import time
from typing import List, Dict, Any
from django.conf import settings
from django.db import connection, DatabaseError

from .pgvector_base import PgVectorBackend

logger = logging.getLogger(__name__)


class EnhancedPgVectorBackend(PgVectorBackend):
    """
    Enhanced pgvector backend with production optimizations,
    chunk-level caching, and advanced similarity search
    """

    def __init__(self, chunk_model=None):
        super().__init__(chunk_model)
        self.cache_timeout = getattr(settings, 'PGVECTOR_CACHE_TIMEOUT', 3600)
        self.enable_index_optimization = getattr(settings, 'PGVECTOR_ENABLE_INDEX_OPTIMIZATION', True)
        self.similarity_threshold = getattr(settings, 'PGVECTOR_SIMILARITY_THRESHOLD', 0.7)

    def ensure_pgvector_indexes(self):
        """Ensure optimal pgvector indexes exist for performance"""
        if not self._pgvector_available:
            return False

        try:
            index_sql = """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS auth_knowledge_chunk_vector_hnsw_idx
            ON authoritative_knowledge_chunk
            USING hnsw (content_vector vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """

            with connection.cursor() as cursor:
                cursor.execute(index_sql)

            logger.info("pgvector HNSW index ensured for optimal performance")
            return True

        except DatabaseError as e:
            logger.warning(f"Could not create pgvector indexes: {str(e)}")
            return False

    def search_similar_with_caching(
        self,
        query_vector: List[float],
        top_k: int = 5,
        threshold: float = 0.7,
        cache_key: str = None
    ) -> List[Dict]:
        """Enhanced similarity search with chunk-level caching"""
        if cache_key:
            from django.core.cache import cache
            cached_results = cache.get(cache_key)
            if cached_results:
                logger.debug(f"Cache hit for similarity search: {cache_key}")
                return cached_results

        results = self.search_similar(query_vector, top_k, threshold)

        if cache_key and results:
            from django.core.cache import cache
            cache.set(cache_key, results, self.cache_timeout)

        return results

    def batch_similarity_search(
        self,
        query_vectors: List[List[float]],
        top_k: int = 5,
        threshold: float = 0.7
    ) -> List[List[Dict]]:
        """Batch similarity search for multiple query vectors"""
        if not self._pgvector_available:
            return [self.search_similar(qv, top_k, threshold) for qv in query_vectors]

        try:
            batch_sql = """
            WITH query_vectors AS (
                SELECT unnest(%s::vector[]) as query_vec, generate_subscripts(%s::vector[], 1) as query_id
            )
            SELECT
                qv.query_id,
                akc.chunk_id,
                akc.knowledge_id,
                akc.content_text,
                akc.chunk_index,
                1 - (akc.content_vector <=> qv.query_vec) as similarity,
                ak.document_title,
                ak.source_organization,
                ak.authority_level,
                akc.tags
            FROM query_vectors qv
            CROSS JOIN LATERAL (
                SELECT akc.*, ak.document_title, ak.source_organization, ak.authority_level
                FROM authoritative_knowledge_chunk akc
                JOIN authoritative_knowledge ak ON akc.knowledge_id = ak.knowledge_id
                WHERE akc.content_vector IS NOT NULL
                AND akc.is_current = true
                AND 1 - (akc.content_vector <=> qv.query_vec) >= %s
                ORDER BY akc.content_vector <=> qv.query_vec
                LIMIT %s
            ) akc
            ORDER BY qv.query_id, similarity DESC;
            """

            vector_strings = ['[' + ','.join(map(str, vec)) + ']' for vec in query_vectors]

            with connection.cursor() as cursor:
                cursor.execute(batch_sql, [vector_strings, vector_strings, threshold, top_k])
                rows = cursor.fetchall()

                results_by_query = {}
                for row in rows:
                    query_id = row[0] - 1
                    if query_id not in results_by_query:
                        results_by_query[query_id] = []

                    results_by_query[query_id].append({
                        'chunk_id': str(row[1]),
                        'knowledge_id': str(row[2]),
                        'content_text': row[3],
                        'chunk_index': row[4],
                        'similarity': float(row[5]),
                        'metadata': {
                            'document_title': row[6],
                            'source_organization': row[7],
                            'authority_level': row[8],
                            'chunk_tags': row[9] or {}
                        }
                    })

                ordered_results = []
                for i in range(len(query_vectors)):
                    ordered_results.append(results_by_query.get(i, []))

                logger.info(f"pgvector batch search completed for {len(query_vectors)} queries")
                return ordered_results

        except DatabaseError as e:
            logger.error(f"Database error in batch search: {str(e)}")
            return [self.search_similar(qv, top_k, threshold) for qv in query_vectors]

    def get_advanced_stats(self) -> Dict[str, Any]:
        """Get advanced statistics for pgvector backend"""
        stats = self.get_embedding_stats()

        if self._pgvector_available:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
                        FROM pg_stat_user_indexes
                        WHERE tablename = 'authoritative_knowledge_chunk'
                        AND indexname LIKE '%vector%'
                    """)
                    index_stats = cursor.fetchall()

                    cursor.execute("""
                        SELECT array_length(content_vector, 1) as dimension, COUNT(*) as count
                        FROM authoritative_knowledge_chunk
                        WHERE content_vector IS NOT NULL
                        GROUP BY array_length(content_vector, 1)
                        ORDER BY count DESC
                    """)
                    dimension_stats = cursor.fetchall()

                stats.update({
                    'pgvector_specific': {
                        'index_statistics': [
                            {'index_name': row[2], 'tuples_read': row[3], 'tuples_fetched': row[4]}
                            for row in index_stats
                        ],
                        'dimension_distribution': [
                            {'dimension': row[0], 'count': row[1]}
                            for row in dimension_stats
                        ]
                    }
                })

            except DatabaseError as e:
                logger.warning(f"Could not get pgvector-specific stats: {str(e)}")

        return stats

    def optimize_for_production(self) -> Dict[str, Any]:
        """Optimize pgvector backend for production use"""
        optimization_results = {
            'indexes_created': False,
            'statistics_updated': False,
            'cache_warmed': False,
            'performance_baseline': None
        }

        try:
            if self.ensure_pgvector_indexes():
                optimization_results['indexes_created'] = True

            with connection.cursor() as cursor:
                cursor.execute("ANALYZE authoritative_knowledge_chunk;")
                optimization_results['statistics_updated'] = True

            if self._warm_up_cache():
                optimization_results['cache_warmed'] = True

            optimization_results['performance_baseline'] = self._run_performance_baseline()

            logger.info("pgvector backend optimized for production")

        except DatabaseError as e:
            logger.error(f"Database error optimizing pgvector: {str(e)}")

        return optimization_results

    def _warm_up_cache(self) -> bool:
        """Warm up cache with common similarity searches"""
        try:
            sample_chunks = self.chunk_model.objects.filter(
                content_vector__isnull=False,
                is_current=True
            ).order_by('-chunk_id')[:5]

            for chunk in sample_chunks:
                if chunk.content_vector:
                    self.search_similar(chunk.content_vector, top_k=10, threshold=0.5)

            return True

        except DatabaseError as e:
            logger.warning(f"Cache warm-up failed: {str(e)}")
            return False

    def _run_performance_baseline(self) -> Dict[str, Any]:
        """Run performance baseline tests"""
        baseline = {
            'single_search_avg_ms': 0.0,
            'batch_search_avg_ms': 0.0,
            'index_performance': 'unknown'
        }

        try:
            test_vector = [0.1] * 384
            search_times = []

            for _ in range(5):
                start_time = time.time()
                self.search_similar(test_vector, top_k=10, threshold=0.6)
                end_time = time.time()
                search_times.append((end_time - start_time) * 1000)

            baseline['single_search_avg_ms'] = sum(search_times) / len(search_times)

            test_vectors = [[0.1 + i*0.01] * 384 for i in range(3)]
            start_time = time.time()
            self.batch_similarity_search(test_vectors, top_k=5, threshold=0.6)
            end_time = time.time()

            baseline['batch_search_avg_ms'] = ((end_time - start_time) * 1000) / len(test_vectors)

            if baseline['single_search_avg_ms'] < 100:
                baseline['index_performance'] = 'excellent'
            elif baseline['single_search_avg_ms'] < 500:
                baseline['index_performance'] = 'good'
            elif baseline['single_search_avg_ms'] < 1000:
                baseline['index_performance'] = 'acceptable'
            else:
                baseline['index_performance'] = 'needs_optimization'

        except (DatabaseError, ValueError) as e:
            logger.warning(f"Performance baseline failed: {str(e)}")

        return baseline