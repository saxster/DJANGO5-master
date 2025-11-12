import logging
from typing import List, Dict, Optional
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, connection

from apps.core_onboarding.models import AuthoritativeKnowledge, AuthoritativeKnowledgeChunk
from ..base import VectorStore

logger = logging.getLogger(__name__)


class PgVectorBackend(VectorStore):
    """
    High-performance PostgreSQL pgvector backend (optional)
    Requires pgvector extension to be installed
    """

    def __init__(self, chunk_model=None):
        self.knowledge_model = AuthoritativeKnowledge
        self.chunk_model = chunk_model or AuthoritativeKnowledgeChunk
        self._check_pgvector_availability()

    def _check_pgvector_availability(self):
        """Check if pgvector extension is available"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
                if not cursor.fetchone():
                    logger.warning("pgvector extension not found, falling back to array operations")
                    self._pgvector_available = False
                else:
                    self._pgvector_available = True
                    logger.info("pgvector extension detected and available")
        except DatabaseError as e:
            logger.warning(f"Database error checking pgvector: {str(e)}")
            self._pgvector_available = False

    def store_embedding(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Store vector using pgvector if available"""
        if not self._pgvector_available:
            return self._store_as_array(knowledge_id, vector, metadata)

        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)
            knowledge.content_vector = vector
            knowledge.save()
            logger.info(f"Stored vector with pgvector for knowledge {knowledge_id}")
            return True
        except ObjectDoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found")
            return False
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid vector data: {str(e)}")
            return False
        except DatabaseError as e:
            logger.error(f"Database error storing vector: {str(e)}")
            return False

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Search using pgvector cosine similarity if available"""
        if not self._pgvector_available:
            return self._search_with_arrays(query_vector, top_k, threshold)

        try:
            sql = """
            SELECT
                chunk_id,
                knowledge_id,
                content_text,
                chunk_index,
                1 - (content_vector <=> %s::vector) as similarity,
                authority_level,
                source_organization,
                document_title,
                jurisdiction,
                industry,
                language,
                publication_date,
                tags
            FROM authoritative_knowledge_chunk akc
            JOIN authoritative_knowledge ak ON akc.knowledge_id = ak.knowledge_id
            WHERE content_vector IS NOT NULL
            AND is_current = true
            AND 1 - (content_vector <=> %s::vector) >= %s
            ORDER BY content_vector <=> %s::vector
            LIMIT %s
            """

            vector_str = '[' + ','.join(map(str, query_vector)) + ']'

            with connection.cursor() as cursor:
                cursor.execute(sql, [vector_str, vector_str, threshold, vector_str, top_k])
                rows = cursor.fetchall()

                results = []
                for row in rows:
                    results.append({
                        'chunk_id': str(row[0]),
                        'knowledge_id': str(row[1]),
                        'content_text': row[2],
                        'chunk_index': row[3],
                        'similarity': float(row[4]),
                        'metadata': {
                            'authority_level': row[5],
                            'source_organization': row[6],
                            'document_title': row[7],
                            'jurisdiction': row[8],
                            'industry': row[9],
                            'language': row[10],
                            'publication_date': row[11].isoformat() if row[11] else None,
                            'chunk_tags': row[12] or {}
                        }
                    })

                logger.info(f"pgvector search returned {len(results)} results")
                return results

        except DatabaseError as e:
            logger.error(f"Database error in pgvector search: {str(e)}")
            return self._search_with_arrays(query_vector, top_k, threshold)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid query vector: {str(e)}")
            return []

    def _store_as_array(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Fallback to array storage"""
        from .postgres_array import PostgresArrayBackend
        postgres_backend = PostgresArrayBackend(self.chunk_model)
        return postgres_backend.store_embedding(knowledge_id, vector, metadata)

    def _search_with_arrays(self, query_vector: List[float], top_k: int, threshold: float) -> List[Dict]:
        """Fallback to array-based search"""
        from .postgres_array import PostgresArrayBackend
        postgres_backend = PostgresArrayBackend(self.chunk_model)
        return postgres_backend._search_similar_chunks(query_vector, top_k, threshold)

    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete embeddings"""
        from .postgres_array import PostgresArrayBackend
        postgres_backend = PostgresArrayBackend(self.chunk_model)
        return postgres_backend.delete_embedding(knowledge_id)

    def get_embedding_stats(self) -> Dict:
        """Get embedding statistics"""
        from .postgres_array import PostgresArrayBackend
        stats = PostgresArrayBackend(self.chunk_model).get_embedding_stats()
        stats['backend_type'] = 'pgvector' if self._pgvector_available else 'pgvector_fallback'
        stats['pgvector_available'] = self._pgvector_available
        return stats