import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from apps.core_onboarding.models import AuthoritativeKnowledge, AuthoritativeKnowledgeChunk
from ..base import VectorStore

logger = logging.getLogger(__name__)


class PostgresArrayBackend(VectorStore):
    """
    Production-grade PostgreSQL ArrayField vector store (default backend)
    Optimized for reliability and simplicity without external dependencies
    """

    def __init__(self, chunk_model=None):
        self.knowledge_model = AuthoritativeKnowledge
        self.chunk_model = chunk_model or AuthoritativeKnowledgeChunk

    def store_embedding(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Store vector embedding for document"""
        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)
            knowledge.content_vector = vector
            knowledge.save()
            logger.info(f"Stored vector for knowledge {knowledge_id} ({len(vector)} dims)")
            return True
        except ObjectDoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found")
            return False
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid vector data: {str(e)}")
            return False

    def store_chunk_embeddings(self, knowledge_id: str, chunk_embeddings: List[Dict]) -> bool:
        """Store embeddings for multiple chunks"""
        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)

            for chunk_data in chunk_embeddings:
                chunk_id = chunk_data.get('chunk_id')
                vector = chunk_data.get('vector')

                if chunk_id and vector:
                    try:
                        chunk = self.chunk_model.objects.get(chunk_id=chunk_id, knowledge=knowledge)
                        chunk.content_vector = vector
                        chunk.save()
                    except ObjectDoesNotExist:
                        logger.warning(f"Chunk {chunk_id} not found for knowledge {knowledge_id}")

            logger.info(f"Stored embeddings for {len(chunk_embeddings)} chunks")
            return True

        except ObjectDoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found")
            return False
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Invalid chunk embedding data: {str(e)}")
            return False

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Search similar vectors using PostgreSQL array operations"""
        return self._search_similar_chunks(query_vector, top_k, threshold)

    def _search_similar_chunks(
        self,
        query_vector: List[float],
        top_k: int = 10,
        threshold: float = 0.6,
        authority_filter: Optional[List[str]] = None,
        jurisdiction_filter: Optional[List[str]] = None,
        industry_filter: Optional[List[str]] = None,
        language_filter: Optional[str] = None
    ) -> List[Dict]:
        """Enhanced chunk search with filtering"""
        results = []
        query_vector_np = np.array(query_vector)

        filters = Q(content_vector__isnull=False, is_current=True)

        if authority_filter:
            filters &= Q(authority_level__in=authority_filter)
        if jurisdiction_filter:
            filters &= Q(knowledge__jurisdiction__in=jurisdiction_filter)
        if industry_filter:
            filters &= Q(knowledge__industry__in=industry_filter)
        if language_filter:
            filters &= Q(knowledge__language=language_filter)

        chunks = self.chunk_model.objects.filter(filters).select_related('knowledge')

        for chunk in chunks:
            if chunk.content_vector:
                try:
                    similarity = self._cosine_similarity(query_vector_np, np.array(chunk.content_vector))
                    if similarity >= threshold:
                        results.append({
                            'chunk_id': str(chunk.chunk_id),
                            'knowledge_id': str(chunk.knowledge.knowledge_id),
                            'similarity': float(similarity),
                            'content_text': chunk.content_text,
                            'chunk_index': chunk.chunk_index,
                            'metadata': {
                                'document_title': chunk.knowledge.document_title,
                                'source_organization': chunk.knowledge.source_organization,
                                'authority_level': chunk.knowledge.authority_level,
                                'jurisdiction': chunk.knowledge.jurisdiction,
                                'industry': chunk.knowledge.industry,
                                'language': chunk.knowledge.language,
                                'publication_date': chunk.knowledge.publication_date.isoformat(),
                                'chunk_tags': chunk.tags,
                                'page_start': chunk.tags.get('page_start'),
                                'page_end': chunk.tags.get('page_end'),
                                'section_heading': chunk.tags.get('section_title', '')
                            }
                        })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid vector for chunk {chunk.chunk_id}: {str(e)}")
                    continue

        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]

    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete embeddings for knowledge and its chunks"""
        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)

            chunk_count = self.chunk_model.objects.filter(knowledge=knowledge).update(content_vector=None)

            knowledge.content_vector = None
            knowledge.save()

            logger.info(f"Deleted embeddings for knowledge {knowledge_id} and {chunk_count} chunks")
            return True

        except ObjectDoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found")
            return False

    def get_embedding_stats(self) -> Dict:
        """Get comprehensive embedding statistics"""
        total_docs = self.knowledge_model.objects.count()
        docs_with_vectors = self.knowledge_model.objects.filter(content_vector__isnull=False).count()

        total_chunks = self.chunk_model.objects.count()
        chunks_with_vectors = self.chunk_model.objects.filter(content_vector__isnull=False).count()
        current_chunks = self.chunk_model.objects.filter(is_current=True).count()

        authority_stats = {}
        for authority in ['low', 'medium', 'high', 'official']:
            count = self.chunk_model.objects.filter(
                authority_level=authority,
                is_current=True,
                content_vector__isnull=False
            ).count()
            authority_stats[authority] = count

        return {
            'backend_type': 'postgres_array',
            'total_documents': total_docs,
            'documents_with_vectors': docs_with_vectors,
            'total_chunks': total_chunks,
            'chunks_with_vectors': chunks_with_vectors,
            'current_chunks': current_chunks,
            'authority_breakdown': authority_stats,
            'vector_coverage_docs': (docs_with_vectors / total_docs) * 100 if total_docs > 0 else 0,
            'vector_coverage_chunks': (chunks_with_vectors / total_chunks) * 100 if total_chunks > 0 else 0,
            'last_updated': datetime.now().isoformat()
        }

    def store_document_chunks(self, knowledge_id: str, chunk_embeddings: List[Dict]) -> bool:
        """
        Backward compatibility wrapper for store_chunk_embeddings()
        Used by EnhancedKnowledgeService for chunked document storage
        """
        return self.store_chunk_embeddings(knowledge_id, chunk_embeddings)

    def search_similar_chunks(
        self,
        query_vector: List[float],
        top_k: int = 10,
        threshold: float = 0.6,
        authority_filter: Optional[List[str]] = None,
        source_filter: Optional[List[str]] = None,
        **kwargs
    ) -> List[Dict]:
        """
        Backward compatibility wrapper for _search_similar_chunks()
        Used by EnhancedKnowledgeService for RAG context retrieval
        """
        # Map source_filter to jurisdiction_filter if provided
        jurisdiction_filter = source_filter

        return self._search_similar_chunks(
            query_vector=query_vector,
            top_k=top_k,
            threshold=threshold,
            authority_filter=authority_filter,
            jurisdiction_filter=jurisdiction_filter
        )

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
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0