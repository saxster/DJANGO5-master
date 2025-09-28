import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from apps.onboarding.models import AuthoritativeKnowledge
from ..base import VectorStore

logger = logging.getLogger(__name__)


class PostgresVectorStore(VectorStore):
    """
    PostgreSQL-based vector store using ArrayField(Float)
    Following the pattern used in apps/face_recognition/models.py
    """

    def __init__(self):
        self.model = AuthoritativeKnowledge

    def store_embedding(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Store vector in PostgreSQL ArrayField"""
        try:
            knowledge = self.model.objects.get(knowledge_id=knowledge_id)
            knowledge.content_vector = vector
            knowledge.save()
            logger.info(f"Stored vector for knowledge {knowledge_id}")
            return True
        except ObjectDoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found for vector storage")
            return False
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid vector data for {knowledge_id}: {str(e)}")
            return False

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Find similar vectors using PostgreSQL array operations"""
        results = []
        query_vector_np = np.array(query_vector)

        knowledge_items = self.model.objects.filter(
            content_vector__isnull=False,
            is_current=True
        ).order_by('-authority_level', '-publication_date')

        for knowledge in knowledge_items:
            if knowledge.content_vector:
                try:
                    stored_vector = np.array(knowledge.content_vector)
                    similarity = self._cosine_similarity(query_vector_np, stored_vector)

                    if similarity >= threshold:
                        results.append({
                            'knowledge_id': str(knowledge.knowledge_id),
                            'similarity': float(similarity),
                            'metadata': {
                                'source_organization': knowledge.source_organization,
                                'document_title': knowledge.document_title,
                                'authority_level': knowledge.authority_level,
                                'content_summary': knowledge.content_summary,
                                'publication_date': knowledge.publication_date.isoformat(),
                            }
                        })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid vector for {knowledge.knowledge_id}: {str(e)}")
                    continue

        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]

    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete vector by setting to None"""
        try:
            knowledge = self.model.objects.get(knowledge_id=knowledge_id)
            knowledge.content_vector = None
            knowledge.save()
            logger.info(f"Deleted vector for knowledge {knowledge_id}")
            return True
        except ObjectDoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found for vector deletion")
            return False

    def get_embedding_stats(self) -> Dict:
        """Get statistics about stored embeddings"""
        total_knowledge = self.model.objects.count()
        with_vectors = self.model.objects.filter(content_vector__isnull=False).count()
        current_knowledge = self.model.objects.filter(is_current=True).count()

        return {
            'total_knowledge_items': total_knowledge,
            'items_with_vectors': with_vectors,
            'current_items': current_knowledge,
            'vector_coverage': (with_vectors / total_knowledge) * 100 if total_knowledge > 0 else 0,
            'last_updated': datetime.now().isoformat()
        }

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except (ValueError, TypeError, np.linalg.LinAlgError) as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0


class ChunkedVectorStore(VectorStore):
    """
    Vector store supporting chunked documents - delegates to chunk-aware backends
    """

    def __init__(self):
        from apps.onboarding.models import AuthoritativeKnowledge, AuthoritativeKnowledgeChunk
        self.knowledge_model = AuthoritativeKnowledge
        self.chunk_model = AuthoritativeKnowledgeChunk

    def store_document_chunks(self, knowledge_id: str, chunks: List[Dict]) -> bool:
        """Store multiple chunks for a knowledge document"""
        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)
        except ObjectDoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found for chunk storage")
            return False

        try:
            for chunk_data in chunks:
                self.chunk_model.objects.create(
                    knowledge=knowledge,
                    chunk_index=chunk_data['index'],
                    content_text=chunk_data['text'],
                    content_vector=chunk_data.get('vector'),
                    tags=chunk_data.get('tags', {})
                )

            logger.info(f"Stored {len(chunks)} chunks for knowledge {knowledge_id}")
            return True
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Error storing chunks for {knowledge_id}: {str(e)}")
            return False

    def search_similar_chunks(
        self,
        query_vector: List[float],
        top_k: int = 5,
        threshold: float = 0.7,
        authority_filter: Optional[List[str]] = None,
        source_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """Search for similar chunks with filtering"""
        results = []
        query_vector_np = np.array(query_vector)

        query_filters = Q(content_vector__isnull=False, is_current=True)

        if authority_filter:
            query_filters &= Q(knowledge__authority_level__in=authority_filter)

        if source_filter:
            query_filters &= Q(knowledge__source_organization__in=source_filter)

        chunks = self.chunk_model.objects.filter(query_filters).select_related('knowledge')

        for chunk in chunks:
            if chunk.content_vector:
                try:
                    stored_vector = np.array(chunk.content_vector)
                    similarity = self._cosine_similarity(query_vector_np, stored_vector)

                    if similarity >= threshold:
                        results.append({
                            'chunk_id': str(chunk.chunk_id),
                            'knowledge_id': str(chunk.knowledge.knowledge_id),
                            'content_text': chunk.content_text,
                            'chunk_index': chunk.chunk_index,
                            'similarity': float(similarity),
                            'metadata': {
                                'document_title': chunk.knowledge.document_title,
                                'source_organization': chunk.knowledge.source_organization,
                                'authority_level': chunk.knowledge.authority_level,
                                'publication_date': chunk.knowledge.publication_date.isoformat(),
                                'chunk_tags': chunk.tags or {}
                            }
                        })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid vector for chunk {chunk.chunk_id}: {str(e)}")
                    continue

        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]

    def store_embedding(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Store single embedding - delegates to document-level storage"""
        logger.warning("ChunkedVectorStore.store_embedding called - use store_document_chunks instead")
        return False

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Search similar - delegates to chunk search"""
        chunk_results = self.search_similar_chunks(query_vector, top_k, threshold)
        return [{'knowledge_id': c['knowledge_id'], 'similarity': c['similarity'], 'metadata': c['metadata']}
                for c in chunk_results]

    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete all chunks for a knowledge document"""
        try:
            deleted_count, _ = self.chunk_model.objects.filter(
                knowledge__knowledge_id=knowledge_id
            ).delete()
            logger.info(f"Deleted {deleted_count} chunks for knowledge {knowledge_id}")
            return True
        except (ValueError, TypeError) as e:
            logger.error(f"Error deleting chunks for {knowledge_id}: {str(e)}")
            return False

    def get_embedding_stats(self) -> Dict:
        """Get statistics about chunk embeddings"""
        total_chunks = self.chunk_model.objects.count()
        with_vectors = self.chunk_model.objects.filter(content_vector__isnull=False).count()
        current_chunks = self.chunk_model.objects.filter(is_current=True).count()

        return {
            'total_chunks': total_chunks,
            'chunks_with_vectors': with_vectors,
            'current_chunks': current_chunks,
            'vector_coverage': (with_vectors / total_chunks) * 100 if total_chunks > 0 else 0,
            'last_updated': datetime.now().isoformat()
        }

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except (ValueError, TypeError, np.linalg.LinAlgError) as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0