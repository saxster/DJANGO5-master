"""
Knowledge service with vector store for Conversational Onboarding (Phase 1 MVP)
"""
from abc import ABC, abstractmethod
from django.conf import settings
from django.db.models import Q
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
import logging
import numpy as np
import requests
import hashlib
from datetime import datetime, timedelta
from urllib.robotparser import RobotFileParser
from typing import List, Dict, Optional, Any
import time
import re

from apps.core.exceptions import (
    LLMServiceException,
    IntegrationException,
    DatabaseException,
    OnboardingException
)
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """
    Abstract base class for vector storage and similarity search
    """

    @abstractmethod
    def store_embedding(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Store vector embedding with metadata"""
        pass

    @abstractmethod
    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Find similar vectors and return with metadata"""
        pass

    @abstractmethod
    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete embedding by knowledge ID"""
        pass

    @abstractmethod
    def get_embedding_stats(self) -> Dict:
        """Get statistics about stored embeddings"""
        pass


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
        except self.model.DoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found for vector storage")
            return False
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid vector data for {knowledge_id}: {str(e)}")
            return False
        except (DatabaseError, IntegrityError) as e:
            correlation_id = ErrorHandler.handle_exception(e, context={'knowledge_id': knowledge_id}, level='error')
            logger.error(f"Database error storing vector (ID: {correlation_id}): {str(e)}", exc_info=True)
            return False

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Find similar vectors using PostgreSQL array operations"""
        # For MVP, we'll use a simple approach
        # In production, consider using pgvector extension for better performance

        results = []
        query_vector_np = np.array(query_vector)

        # Get all knowledge with vectors
        knowledge_items = self.model.objects.filter(
            content_vector__isnull=False,
            is_current=True
        ).order_by('-authority_level', '-publication_date')

        for knowledge in knowledge_items:
            if knowledge.content_vector:
                try:
                    stored_vector = np.array(knowledge.content_vector)

                    # Calculate cosine similarity
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
                except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
                    logger.warning(f"Error calculating similarity for {knowledge.knowledge_id}: {str(e)}")
                    continue

        # Sort by similarity and return top_k
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
        except self.model.DoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found for vector deletion")
            return False
        except (ValueError, TypeError) as e:
            logger.error(f"Error deleting vector for {knowledge_id}: {str(e)}")
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
        except (ValueError, TypeError) as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0


class KnowledgeService:
    """
    Service for managing authoritative knowledge and performing semantic search
    """

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.model = AuthoritativeKnowledge

    def add_knowledge(self, source_org: str, title: str, content_summary: str,
                     authority_level: str = 'medium', version: str = '',
                     publication_date: Optional[datetime] = None) -> str:
        """Add new knowledge item"""
        knowledge = self.model.objects.create(
            source_organization=source_org,
            document_title=title,
            document_version=version,
            authority_level=authority_level,
            content_summary=content_summary,
            publication_date=publication_date or datetime.now(),
            is_current=True
        )

        logger.info(f"Added knowledge: {title} from {source_org}")
        return str(knowledge.knowledge_id)

    def update_knowledge_vector(self, knowledge_id: str, vector: List[float]) -> bool:
        """Update vector embedding for knowledge item"""
        return self.vector_store.store_embedding(
            knowledge_id, vector, {'updated_at': datetime.now().isoformat()}
        )

    def search_knowledge(self, query: str, top_k: int = 5, authority_filter: Optional[List[str]] = None) -> List[Dict]:
        """Search knowledge using text query"""
        # For MVP, we'll use a simple text-based search
        # Later phases can integrate with actual embedding generation

        query_filters = Q(content_summary__icontains=query) | Q(document_title__icontains=query)

        if authority_filter:
            query_filters &= Q(authority_level__in=authority_filter)

        knowledge_items = self.model.objects.filter(
            query_filters,
            is_current=True
        ).order_by('-authority_level', '-publication_date')[:top_k]

        results = []
        for knowledge in knowledge_items:
            results.append({
                'knowledge_id': str(knowledge.knowledge_id),
                'source_organization': knowledge.source_organization,
                'document_title': knowledge.document_title,
                'authority_level': knowledge.authority_level,
                'content_summary': knowledge.content_summary,
                'publication_date': knowledge.publication_date.isoformat(),
                'relevance_score': self._calculate_text_relevance(query, knowledge.content_summary)
            })

        return results

    def search_similar_knowledge(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Search knowledge using vector similarity"""
        return self.vector_store.search_similar(query_vector, top_k, threshold)

    def get_authoritative_sources(self, topic: str, authority_level: str = 'high') -> List[Dict]:
        """Get authoritative sources for a specific topic"""
        authority_levels = ['high', 'official'] if authority_level == 'high' else [authority_level]

        sources = self.model.objects.filter(
            Q(content_summary__icontains=topic) | Q(document_title__icontains=topic),
            authority_level__in=authority_levels,
            is_current=True
        ).order_by('-authority_level', '-publication_date')

        return [
            {
                'knowledge_id': str(source.knowledge_id),
                'source_organization': source.source_organization,
                'document_title': source.document_title,
                'authority_level': source.authority_level,
                'content_summary': source.content_summary[:200] + '...' if len(source.content_summary) > 200 else source.content_summary,
                'publication_date': source.publication_date.isoformat()
            }
            for source in sources[:10]
        ]

    def validate_recommendation_against_knowledge(self, recommendation: Dict, context: Dict) -> Dict:
        """Validate a recommendation against authoritative knowledge"""
        validation_result = {
            'is_valid': True,
            'confidence_score': 0.8,
            'supporting_sources': [],
            'potential_conflicts': [],
            'recommendations': []
        }

        # Extract key topics from recommendation
        topics = self._extract_topics_from_recommendation(recommendation)

        for topic in topics:
            # Search for authoritative sources
            sources = self.get_authoritative_sources(topic, 'high')

            if sources:
                validation_result['supporting_sources'].extend(sources[:2])

            # Simple validation logic for MVP
            # Real implementation would use semantic analysis
            potential_conflicts = self._check_for_conflicts(recommendation, sources)
            validation_result['potential_conflicts'].extend(potential_conflicts)

        # Adjust confidence based on findings
        if validation_result['potential_conflicts']:
            validation_result['confidence_score'] *= 0.7
            validation_result['is_valid'] = False

        return validation_result

    def get_knowledge_stats(self) -> Dict:
        """Get comprehensive knowledge base statistics"""
        base_stats = self.vector_store.get_embedding_stats()

        # Add additional statistics
        authority_breakdown = {}
        for level in ['low', 'medium', 'high', 'official']:
            count = self.model.objects.filter(authority_level=level, is_current=True).count()
            authority_breakdown[level] = count

        recent_additions = self.model.objects.filter(
            cdtz__gte=datetime.now() - timedelta(days=30),
            is_current=True
        ).count()

        base_stats.update({
            'authority_level_breakdown': authority_breakdown,
            'recent_additions_30_days': recent_additions,
            'oldest_knowledge': self.model.objects.filter(is_current=True).order_by('publication_date').first(),
            'newest_knowledge': self.model.objects.filter(is_current=True).order_by('-publication_date').first()
        })

        return base_stats

    def _calculate_text_relevance(self, query: str, content: str) -> float:
        """Simple text relevance calculation"""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        intersection = query_words.intersection(content_words)
        return len(intersection) / len(query_words)

    def _extract_topics_from_recommendation(self, recommendation: Dict) -> List[str]:
        """Extract key topics from recommendation for validation"""
        topics = []

        # Simple keyword extraction for MVP
        if 'business_unit_config' in recommendation:
            topics.append('business unit')
            bu_config = recommendation['business_unit_config']
            if 'bu_type' in bu_config:
                topics.append(bu_config['bu_type'].lower())

        if 'security_settings' in recommendation:
            topics.extend(['security', 'authentication', 'access control'])

        if 'suggested_shifts' in recommendation:
            topics.extend(['shift management', 'scheduling'])

        return topics

    def _check_for_conflicts(self, recommendation: Dict, sources: List[Dict]) -> List[Dict]:
        """Check for potential conflicts between recommendation and sources"""
        conflicts = []

        # Simple conflict detection for MVP
        # Real implementation would use semantic analysis

        for source in sources:
            # Check for contradictory information
            if 'security' in source['content_summary'].lower():
                if recommendation.get('security_settings', {}).get('enable_gps', False):
                    if 'gps not recommended' in source['content_summary'].lower():
                        conflicts.append({
                            'type': 'policy_conflict',
                            'source': source['document_title'],
                            'description': 'Recommendation enables GPS but source advises against it'
                        })

        return conflicts


# =============================================================================
# DUMMY IMPLEMENTATIONS FOR MVP
# =============================================================================


class DummyEmbeddingGenerator:
    """
    Dummy embedding generator for MVP
    Generates random vectors for testing purposes
    """

    @staticmethod
    def generate_embedding(text: str, model: str = 'dummy') -> List[float]:
        """Generate dummy embedding vector"""
        # Simple hash-based approach for consistent dummy vectors
        import hashlib

        # Create a hash of the text
        text_hash = hashlib.md5(text.encode()).hexdigest()

        # Generate vector from hash (384 dimensions for consistency)
        vector = []
        for i in range(0, len(text_hash), 2):
            byte_val = int(text_hash[i:i+2], 16)
            # Normalize to [-1, 1] range
            normalized = (byte_val / 255.0) * 2 - 1
            vector.append(float(normalized))

        # Pad or truncate to desired dimension (384)
        target_dim = 384
        while len(vector) < target_dim:
            vector.extend(vector[:min(len(vector), target_dim - len(vector))])

        return vector[:target_dim]


# =============================================================================
# PHASE 2: ENHANCED RAG RETRIEVAL WITH CHUNKING
# =============================================================================


class ChunkedVectorStore(VectorStore):
    """
    Phase 2 Enhanced vector store with chunking support
    """

    def __init__(self):
        from apps.onboarding.models import AuthoritativeKnowledge, AuthoritativeKnowledgeChunk
        self.knowledge_model = AuthoritativeKnowledge
        self.chunk_model = AuthoritativeKnowledgeChunk

    def store_document_chunks(self, knowledge_id: str, chunks: List[Dict]) -> bool:
        """Store multiple document chunks with vectors"""
        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)

            # Delete existing chunks
            self.chunk_model.objects.filter(knowledge=knowledge).delete()

            # Create new chunks
            for i, chunk_data in enumerate(chunks):
                self.chunk_model.objects.create(
                    knowledge=knowledge,
                    chunk_index=i,
                    content_text=chunk_data['text'],
                    content_vector=chunk_data.get('vector'),
                    tags=chunk_data.get('tags', {}),
                    is_current=True
                )

            logger.info(f"Stored {len(chunks)} chunks for knowledge {knowledge_id}")
            return True

        except (ValueError, TypeError) as e:
            logger.error(f"Error storing chunks for {knowledge_id}: {str(e)}")
            return False

    def search_similar_chunks(
        self,
        query_vector: List[float],
        top_k: int = 10,
        threshold: float = 0.6,
        authority_filter: Optional[List[str]] = None,
        source_filter: Optional[List[str]] = None,
        tags_filter: Optional[Dict] = None
    ) -> List[Dict]:
        """Search similar chunks with advanced filtering"""

        # Build query filters
        filters = Q(content_vector__isnull=False, is_current=True)

        if authority_filter:
            filters &= Q(authority_level__in=authority_filter)

        if source_filter:
            filters &= Q(source_organization__in=source_filter)

        if tags_filter:
            for key, value in tags_filter.items():
                filters &= Q(tags__contains={key: value})

        # Get chunks with pre-filtering
        chunks = self.chunk_model.objects.filter(filters).select_related('knowledge')

        # Calculate similarities and sort
        results = []
        query_vector_np = np.array(query_vector)

        for chunk in chunks:
            if chunk.content_vector:
                similarity = chunk.get_similarity_score(query_vector)
                if similarity >= threshold:
                    results.append({
                        'chunk_id': str(chunk.chunk_id),
                        'knowledge_id': str(chunk.knowledge.knowledge_id),
                        'similarity': similarity,
                        'chunk_index': chunk.chunk_index,
                        'content_text': chunk.content_text,
                        'metadata': {
                            'document_title': chunk.knowledge.document_title,
                            'source_organization': chunk.knowledge.source_organization,
                            'authority_level': chunk.knowledge.authority_level,
                            'publication_date': chunk.knowledge.publication_date.isoformat(),
                            'chunk_tags': chunk.tags
                        }
                    })

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]

    def store_embedding(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Legacy compatibility - redirects to document-level storage"""
        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)
            knowledge.content_vector = vector
            knowledge.save()
            return True
        except (ValueError, TypeError) as e:
            logger.error(f"Error storing embedding: {str(e)}")
            return False

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Legacy compatibility - redirects to chunk search"""
        chunk_results = self.search_similar_chunks(query_vector, top_k * 2, threshold)

        # Group by document and take best chunk per document
        doc_results = {}
        for chunk in chunk_results:
            doc_id = chunk['knowledge_id']
            if doc_id not in doc_results or chunk['similarity'] > doc_results[doc_id]['similarity']:
                doc_results[doc_id] = {
                    'knowledge_id': doc_id,
                    'similarity': chunk['similarity'],
                    'metadata': chunk['metadata']
                }

        return list(doc_results.values())[:top_k]

    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete all chunks for a knowledge document"""
        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)
            deleted_count = self.chunk_model.objects.filter(knowledge=knowledge).delete()[0]
            logger.info(f"Deleted {deleted_count} chunks for knowledge {knowledge_id}")
            return True
        except (ValueError, TypeError) as e:
            logger.error(f"Error deleting chunks: {str(e)}")
            return False

    def get_embedding_stats(self) -> Dict:
        """Get enhanced statistics including chunk information"""
        total_knowledge = self.knowledge_model.objects.count()
        total_chunks = self.chunk_model.objects.count()
        chunks_with_vectors = self.chunk_model.objects.filter(content_vector__isnull=False).count()
        current_chunks = self.chunk_model.objects.filter(is_current=True).count()

        return {
            'total_knowledge_items': total_knowledge,
            'total_chunks': total_chunks,
            'chunks_with_vectors': chunks_with_vectors,
            'current_chunks': current_chunks,
            'avg_chunks_per_doc': total_chunks / max(1, total_knowledge),
            'vector_coverage': (chunks_with_vectors / total_chunks) * 100 if total_chunks > 0 else 0,
            'last_updated': datetime.now().isoformat()
        }


# =============================================================================
# PRODUCTION-GRADE VECTOR STORE BACKENDS
# =============================================================================


class PostgresArrayBackend(VectorStore):
    """
    Production-grade PostgreSQL ArrayField vector store (default backend)
    Optimized for reliability and simplicity without external dependencies
    """

    def __init__(self, chunk_model=None):
        from apps.onboarding.models import AuthoritativeKnowledge, AuthoritativeKnowledgeChunk
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
        except self.knowledge_model.DoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found")
            return False
        except (ValueError, TypeError) as e:
            logger.error(f"Error storing vector: {str(e)}")
            return False

    def store_chunk_embeddings(self, knowledge_id: str, chunk_embeddings: List[Dict]) -> bool:
        """Store embeddings for multiple chunks"""
        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)

            # Update chunks with embeddings
            for chunk_data in chunk_embeddings:
                chunk_id = chunk_data.get('chunk_id')
                vector = chunk_data.get('vector')

                if chunk_id and vector:
                    try:
                        chunk = self.chunk_model.objects.get(chunk_id=chunk_id, knowledge=knowledge)
                        chunk.content_vector = vector
                        chunk.save()
                    except self.chunk_model.DoesNotExist:
                        logger.warning(f"Chunk {chunk_id} not found for knowledge {knowledge_id}")

            logger.info(f"Stored embeddings for {len(chunk_embeddings)} chunks")
            return True

        except (ValueError, TypeError) as e:
            logger.error(f"Error storing chunk embeddings: {str(e)}")
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

        # Build query filters
        filters = Q(content_vector__isnull=False, is_current=True)

        if authority_filter:
            filters &= Q(authority_level__in=authority_filter)
        if jurisdiction_filter:
            filters &= Q(knowledge__jurisdiction__in=jurisdiction_filter)
        if industry_filter:
            filters &= Q(knowledge__industry__in=industry_filter)
        if language_filter:
            filters &= Q(knowledge__language=language_filter)

        # Get chunks with filtering
        chunks = self.chunk_model.objects.filter(filters).select_related('knowledge')

        # Calculate similarities
        for chunk in chunks:
            if chunk.content_vector:
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

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]

    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete embeddings for knowledge and its chunks"""
        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)

            # Delete chunk embeddings
            chunk_count = self.chunk_model.objects.filter(knowledge=knowledge).update(content_vector=None)

            # Delete document embedding
            knowledge.content_vector = None
            knowledge.save()

            logger.info(f"Deleted embeddings for knowledge {knowledge_id} and {chunk_count} chunks")
            return True

        except (ValueError, TypeError) as e:
            logger.error(f"Error deleting embeddings: {str(e)}")
            return False

    def get_embedding_stats(self) -> Dict:
        """Get comprehensive embedding statistics"""
        total_docs = self.knowledge_model.objects.count()
        docs_with_vectors = self.knowledge_model.objects.filter(content_vector__isnull=False).count()

        total_chunks = self.chunk_model.objects.count()
        chunks_with_vectors = self.chunk_model.objects.filter(content_vector__isnull=False).count()
        current_chunks = self.chunk_model.objects.filter(is_current=True).count()

        # Authority level breakdown
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

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except (ValueError, TypeError) as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0


class PgVectorBackend(VectorStore):
    """
    High-performance PostgreSQL pgvector backend (optional)
    Requires pgvector extension to be installed
    """

    def __init__(self, chunk_model=None):
        from apps.onboarding.models import AuthoritativeKnowledge, AuthoritativeKnowledgeChunk
        self.knowledge_model = AuthoritativeKnowledge
        self.chunk_model = chunk_model or AuthoritativeKnowledgeChunk
        self._check_pgvector_availability()

    def _check_pgvector_availability(self):
        """Check if pgvector extension is available"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
                if not cursor.fetchone():
                    logger.warning("pgvector extension not found, falling back to array operations")
                    self._pgvector_available = False
                else:
                    self._pgvector_available = True
                    logger.info("pgvector extension detected and available")
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not check pgvector availability: {str(e)}")
            self._pgvector_available = False

    def store_embedding(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Store vector using pgvector if available"""
        if not self._pgvector_available:
            # Fallback to array storage
            return self._store_as_array(knowledge_id, vector, metadata)

        try:
            knowledge = self.knowledge_model.objects.get(knowledge_id=knowledge_id)
            knowledge.content_vector = vector
            knowledge.save()
            logger.info(f"Stored vector with pgvector for knowledge {knowledge_id}")
            return True
        except (ValueError, TypeError) as e:
            logger.error(f"Error storing with pgvector: {str(e)}")
            return False

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Search using pgvector cosine similarity if available"""
        if not self._pgvector_available:
            return self._search_with_arrays(query_vector, top_k, threshold)

        try:
            from django.db import connection

            # Use raw SQL with pgvector operators for optimal performance
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

        except (ValueError, TypeError) as e:
            logger.error(f"pgvector search failed, falling back: {str(e)}")
            return self._search_with_arrays(query_vector, top_k, threshold)

    def _store_as_array(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Fallback to array storage"""
        postgres_backend = PostgresArrayBackend(self.chunk_model)
        return postgres_backend.store_embedding(knowledge_id, vector, metadata)

    def _search_with_arrays(self, query_vector: List[float], top_k: int, threshold: float) -> List[Dict]:
        """Fallback to array-based search"""
        postgres_backend = PostgresArrayBackend(self.chunk_model)
        return postgres_backend._search_similar_chunks(query_vector, top_k, threshold)

    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete embeddings"""
        postgres_backend = PostgresArrayBackend(self.chunk_model)
        return postgres_backend.delete_embedding(knowledge_id)

    def get_embedding_stats(self) -> Dict:
        """Get embedding statistics"""
        stats = PostgresArrayBackend(self.chunk_model).get_embedding_stats()
        stats['backend_type'] = 'pgvector' if self._pgvector_available else 'pgvector_fallback'
        stats['pgvector_available'] = self._pgvector_available
        return stats


class ChromaBackend(VectorStore):
    """
    ChromaDB vector backend (optional)
    For specialized vector workloads and research
    """

    def __init__(self, collection_name: str = "intelliwiz_knowledge"):
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._initialize_chroma()

    def _initialize_chroma(self):
        """Initialize ChromaDB client and collection"""
        try:
            import chromadb
            from chromadb.config import Settings

            # Configure ChromaDB client
            chroma_host = getattr(settings, 'CHROMA_HOST', 'localhost')
            chroma_port = getattr(settings, 'CHROMA_PORT', 8000)

            self._client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=False
                )
            )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "IntelliWiz authoritative knowledge base"}
            )

            logger.info(f"ChromaDB initialized: collection '{self.collection_name}'")

        except ImportError:
            logger.error("ChromaDB not installed. Install with: pip install chromadb")
            raise
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to initialize ChromaDB: {str(e)}")
            raise

    def store_embedding(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Store embedding in ChromaDB"""
        try:
            # Store document-level embedding
            self._collection.upsert(
                ids=[knowledge_id],
                embeddings=[vector],
                metadatas=[{
                    'type': 'document',
                    'knowledge_id': knowledge_id,
                    **metadata
                }]
            )

            logger.info(f"Stored document embedding in ChromaDB: {knowledge_id}")
            return True

        except (ValueError, TypeError) as e:
            logger.error(f"Error storing in ChromaDB: {str(e)}")
            return False

    def store_chunk_embeddings(self, knowledge_id: str, chunk_embeddings: List[Dict]) -> bool:
        """Store chunk embeddings in ChromaDB"""
        try:
            ids = []
            embeddings = []
            metadatas = []

            for chunk_data in chunk_embeddings:
                chunk_id = chunk_data.get('chunk_id', f"{knowledge_id}_chunk_{len(ids)}")
                vector = chunk_data.get('vector')
                chunk_metadata = chunk_data.get('metadata', {})

                if vector:
                    ids.append(chunk_id)
                    embeddings.append(vector)
                    metadatas.append({
                        'type': 'chunk',
                        'knowledge_id': knowledge_id,
                        'chunk_id': chunk_id,
                        **chunk_metadata
                    })

            if ids:
                self._collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas
                )

                logger.info(f"Stored {len(ids)} chunk embeddings in ChromaDB")
                return True

            return False

        except (ValueError, TypeError) as e:
            logger.error(f"Error storing chunk embeddings in ChromaDB: {str(e)}")
            return False

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Search similar vectors in ChromaDB"""
        try:
            results = self._collection.query(
                query_embeddings=[query_vector],
                n_results=min(top_k, 100),  # ChromaDB limit
                include=['metadatas', 'documents', 'distances']
            )

            formatted_results = []

            if results['ids'] and results['ids'][0]:
                for i, (id_, metadata, distance) in enumerate(zip(
                    results['ids'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # Convert distance to similarity (ChromaDB returns squared L2 distance)
                    similarity = 1.0 / (1.0 + distance)

                    if similarity >= threshold:
                        formatted_results.append({
                            'chunk_id': metadata.get('chunk_id', id_),
                            'knowledge_id': metadata.get('knowledge_id'),
                            'similarity': float(similarity),
                            'content_text': results.get('documents', [[]])[0][i] if results.get('documents') else '',
                            'metadata': metadata
                        })

            logger.info(f"ChromaDB search returned {len(formatted_results)} results")
            return formatted_results

        except (ValueError, TypeError) as e:
            logger.error(f"ChromaDB search error: {str(e)}")
            return []

    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete embeddings from ChromaDB"""
        try:
            # Query for all items with this knowledge_id
            results = self._collection.get(
                where={"knowledge_id": knowledge_id},
                include=['metadatas']
            )

            if results['ids']:
                self._collection.delete(ids=results['ids'])
                logger.info(f"Deleted {len(results['ids'])} embeddings for {knowledge_id}")
                return True

            return False

        except (ValueError, TypeError) as e:
            logger.error(f"Error deleting from ChromaDB: {str(e)}")
            return False

    def get_embedding_stats(self) -> Dict:
        """Get ChromaDB collection statistics"""
        try:
            collection_count = self._collection.count()

            # Get type breakdown
            doc_results = self._collection.get(where={"type": "document"})
            chunk_results = self._collection.get(where={"type": "chunk"})

            return {
                'backend_type': 'chromadb',
                'collection_name': self.collection_name,
                'total_embeddings': collection_count,
                'document_embeddings': len(doc_results['ids']) if doc_results['ids'] else 0,
                'chunk_embeddings': len(chunk_results['ids']) if chunk_results['ids'] else 0,
                'chroma_available': True,
                'last_updated': datetime.now().isoformat()
            }

        except (ValueError, TypeError) as e:
            logger.error(f"Error getting ChromaDB stats: {str(e)}")
            return {
                'backend_type': 'chromadb',
                'chroma_available': False,
                'error': str(e)
            }


class DocumentChunker:
    """
    Production-grade chunker service with heading/page awareness and token budgeting
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, max_tokens: int = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_tokens = max_tokens or getattr(settings, 'KB_MAX_CHUNK_TOKENS', 512)

        # Heading detection patterns
        self.heading_patterns = [
            r'^#+\s+(.+)$',  # Markdown headings (# ## ###)
            r'^(.+)\n={3,}$',  # Underlined with =
            r'^(.+)\n-{3,}$',  # Underlined with -
            r'^\d+\.\s+(.+)$',  # Numbered sections (1. 2.)
            r'^([A-Z][A-Z\s]{2,})\s*$',  # ALL CAPS headings
            r'^\s*([A-Z][a-z\s]+):\s*$',  # Title case with colon
        ]

        # Page break patterns
        self.page_break_patterns = [
            r'^\s*page\s+\d+\s*$',
            r'^\s*-+\s*page\s+\d+\s*-+\s*$',
            r'\f',  # Form feed character
            r'^\s*\[page\s+\d+\]\s*$',
        ]

    def chunk_text(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """Basic text chunking with boundary detection"""
        if not text:
            return []

        # Try smart chunking if we have structured content
        if self._has_structure(text):
            return self.chunk_with_structure(text, metadata)

        # Fall back to simple overlapping chunks
        return self._chunk_simple_overlap(text, metadata)

    def chunk_with_structure(self, text: str, metadata: Optional[Dict] = None, parsed_data: Dict = None) -> List[Dict]:
        """
        Chunk text with heading and page awareness

        Args:
            text: Full text content
            metadata: Basic metadata
            parsed_data: Additional structured data from DocumentParser
        """
        if not text:
            return []

        chunks = []

        # Extract structural elements
        headings = self._extract_headings(text, parsed_data)
        page_breaks = self._extract_page_breaks(text, parsed_data)

        # Create sections based on headings
        sections = self._create_sections(text, headings, page_breaks)

        # Chunk each section
        for section in sections:
            section_chunks = self._chunk_section(section, metadata)
            chunks.extend(section_chunks)

        # Post-process chunks to ensure token limits and add sequential metadata
        processed_chunks = self._post_process_chunks(chunks)

        logger.info(f"Created {len(processed_chunks)} chunks from {len(sections)} sections")
        return processed_chunks

    def chunk_document(self, document_content: str, document_metadata: Dict, parsed_data: Dict = None) -> List[Dict]:
        """Chunk a full document with enhanced metadata and structure awareness"""

        # Use structured chunking with parsed data from DocumentParser
        base_chunks = self.chunk_with_structure(document_content, document_metadata, parsed_data)

        # Enhance chunks with document-level metadata
        enhanced_chunks = []
        for i, chunk in enumerate(base_chunks):
            enhanced_chunk = chunk.copy()
            enhanced_chunk['tags'].update({
                'document_title': document_metadata.get('title', ''),
                'source_org': document_metadata.get('organization', ''),
                'authority': document_metadata.get('authority_level', 'medium'),
                'chunk_position': f"{i+1}/{len(base_chunks)}",
                'is_first_chunk': i == 0,
                'is_last_chunk': i == len(base_chunks) - 1,
                'total_chunks': len(base_chunks)
            })
            enhanced_chunks.append(enhanced_chunk)

        return enhanced_chunks

    def _has_structure(self, text: str) -> bool:
        """Check if text has detectable structure (headings, sections, etc.)"""
        lines = text.split('\n')[:50]  # Check first 50 lines

        structure_indicators = 0
        for line in lines:
            if any(re.match(pattern, line.strip(), re.IGNORECASE) for pattern in self.heading_patterns):
                structure_indicators += 1
            if structure_indicators >= 3:  # Found multiple headings
                return True

        return False

    def _extract_headings(self, text: str, parsed_data: Dict = None) -> List[Dict]:
        """Extract headings from text and parsed data"""
        headings = []

        # Use parsed headings if available (from HTML/structured parsing)
        if parsed_data and 'headings' in parsed_data:
            for heading in parsed_data['headings']:
                # Find position in text
                heading_text = heading.get('text', '').strip()
                if heading_text:
                    pos = text.find(heading_text)
                    if pos != -1:
                        headings.append({
                            'text': heading_text,
                            'level': self._normalize_heading_level(heading.get('level', 'h2')),
                            'position': pos,
                            'source': 'parsed'
                        })

        # Extract headings from text patterns
        lines = text.split('\n')
        current_pos = 0

        for line in lines:
            line_stripped = line.strip()
            if line_stripped:
                for i, pattern in enumerate(self.heading_patterns):
                    match = re.match(pattern, line_stripped, re.IGNORECASE)
                    if match:
                        heading_text = match.group(1).strip()
                        headings.append({
                            'text': heading_text,
                            'level': i + 1,  # Pattern order determines level
                            'position': current_pos + text[current_pos:].find(line_stripped),
                            'source': 'pattern'
                        })
                        break
            current_pos += len(line) + 1

        # Sort by position and remove duplicates
        headings = sorted(headings, key=lambda x: x['position'])
        unique_headings = []
        seen_positions = set()

        for heading in headings:
            if heading['position'] not in seen_positions:
                unique_headings.append(heading)
                seen_positions.add(heading['position'])

        return unique_headings

    def _extract_page_breaks(self, text: str, parsed_data: Dict = None) -> List[Dict]:
        """Extract page break positions"""
        page_breaks = []

        # Use page data from parsed content if available
        if parsed_data and 'page_texts' in parsed_data:
            current_pos = 0
            for i, page_text in enumerate(parsed_data['page_texts']):
                if i > 0:  # Skip first page (no break before it)
                    page_breaks.append({
                        'position': current_pos,
                        'page_number': i + 1,
                        'source': 'parsed'
                    })
                current_pos += len(page_text) + 2  # +2 for assumed page break chars

        # Look for page break patterns in text
        for pattern in self.page_break_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                page_breaks.append({
                    'position': match.start(),
                    'page_number': None,  # Will be inferred
                    'source': 'pattern'
                })

        return sorted(page_breaks, key=lambda x: x['position'])

    def _create_sections(self, text: str, headings: List[Dict], page_breaks: List[Dict]) -> List[Dict]:
        """Create logical sections based on headings and page breaks"""
        sections = []

        # Combine headings and page breaks to create section boundaries
        boundaries = []

        for heading in headings:
            boundaries.append({
                'position': heading['position'],
                'type': 'heading',
                'data': heading
            })

        for page_break in page_breaks:
            boundaries.append({
                'position': page_break['position'],
                'type': 'page_break',
                'data': page_break
            })

        # Sort boundaries by position
        boundaries = sorted(boundaries, key=lambda x: x['position'])

        # Create sections
        current_section = {
            'start': 0,
            'heading': None,
            'page_start': 1,
            'content_start': 0
        }

        for i, boundary in enumerate(boundaries):
            if boundary['type'] == 'heading':
                # End current section and start new one
                if current_section['start'] < boundary['position']:
                    current_section['end'] = boundary['position']
                    current_section['content'] = text[current_section['content_start']:boundary['position']].strip()
                    if current_section['content']:
                        sections.append(current_section)

                # Start new section
                current_section = {
                    'start': boundary['position'],
                    'heading': boundary['data'],
                    'page_start': self._infer_page_number(boundary['position'], page_breaks),
                    'content_start': boundary['position']
                }

            elif boundary['type'] == 'page_break':
                # Update page information for current section
                current_section['page_end'] = boundary['data'].get('page_number',
                    self._infer_page_number(boundary['position'], page_breaks))

        # Add final section
        current_section['end'] = len(text)
        current_section['content'] = text[current_section['content_start']:].strip()
        if current_section['content']:
            sections.append(current_section)

        # Ensure we have at least one section
        if not sections:
            sections.append({
                'start': 0,
                'end': len(text),
                'content': text,
                'heading': None,
                'page_start': 1,
                'page_end': 1
            })

        return sections

    def _chunk_section(self, section: Dict, metadata: Optional[Dict] = None) -> List[Dict]:
        """Chunk a single section with respect for boundaries"""
        content = section['content']
        if not content or len(content.strip()) == 0:
            return []

        chunks = []

        # If section is small enough, keep as single chunk
        if len(content) <= self.chunk_size:
            chunk = {
                'text': content.strip(),
                'start_idx': section['start'],
                'end_idx': section['end'],
                'section_heading': section.get('heading', {}).get('text', ''),
                'page_start': section.get('page_start'),
                'page_end': section.get('page_end', section.get('page_start')),
                'tags': self._create_chunk_tags(section, metadata)
            }
            chunks.append(chunk)
            return chunks

        # Split large sections with overlap, respecting sentence boundaries
        start = 0
        content_length = len(content)

        while start < content_length:
            end = min(start + self.chunk_size, content_length)

            # Find good break point
            if end < content_length:
                # Look for sentence boundary
                sentence_end = content.rfind('.', start, end)
                if sentence_end > start + self.chunk_size * 0.7:
                    end = sentence_end + 1
                else:
                    # Look for paragraph break
                    para_end = content.rfind('\n\n', start, end)
                    if para_end > start + self.chunk_size * 0.6:
                        end = para_end
                    else:
                        # Look for word boundary
                        word_end = content.rfind(' ', start, end)
                        if word_end > start + self.chunk_size * 0.8:
                            end = word_end

            chunk_text = content[start:end].strip()
            if chunk_text:
                chunk = {
                    'text': chunk_text,
                    'start_idx': section['start'] + start,
                    'end_idx': section['start'] + end,
                    'section_heading': section.get('heading', {}).get('text', ''),
                    'page_start': section.get('page_start'),
                    'page_end': section.get('page_end', section.get('page_start')),
                    'tags': self._create_chunk_tags(section, metadata, start, end)
                }
                chunks.append(chunk)

            # Move to next chunk with overlap
            start = max(start + 1, end - self.chunk_overlap)

        return chunks

    def _chunk_simple_overlap(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """Fallback simple overlapping chunks"""
        chunks = []
        text_length = len(text)

        if text_length <= self.chunk_size:
            return [{
                'text': text,
                'start_idx': 0,
                'end_idx': text_length,
                'tags': metadata or {}
            }]

        start = 0
        chunk_index = 0

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            # Find good break point
            if end < text_length:
                sentence_end = text.rfind('.', start, end)
                if sentence_end > start + self.chunk_size * 0.7:
                    end = sentence_end + 1
                else:
                    word_end = text.rfind(' ', start, end)
                    if word_end > start + self.chunk_size * 0.8:
                        end = word_end

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_tags = (metadata or {}).copy()
                chunk_tags.update({
                    'chunk_start': start,
                    'chunk_end': end,
                    'chunk_length': len(chunk_text)
                })

                chunks.append({
                    'text': chunk_text,
                    'start_idx': start,
                    'end_idx': end,
                    'tags': chunk_tags
                })

            start = max(start + 1, end - self.chunk_overlap)
            chunk_index += 1

            if chunk_index > 1000:
                logger.warning("Breaking chunking loop after 1000 chunks")
                break

        return chunks

    def _create_chunk_tags(self, section: Dict, metadata: Optional[Dict] = None, start: int = 0, end: int = None) -> Dict:
        """Create comprehensive tags for a chunk"""
        tags = (metadata or {}).copy()

        # Section-level information
        if section.get('heading'):
            tags.update({
                'section_title': section['heading']['text'],
                'section_level': section['heading']['level'],
                'heading_source': section['heading']['source']
            })

        # Page information
        if section.get('page_start'):
            tags['page_start'] = section['page_start']
        if section.get('page_end'):
            tags['page_end'] = section['page_end']

        # Position information
        tags.update({
            'section_start': start,
            'section_end': end or len(section.get('content', '')),
            'has_heading': bool(section.get('heading'))
        })

        return tags

    def _normalize_heading_level(self, level: str) -> int:
        """Convert heading level to numeric"""
        if isinstance(level, int):
            return level
        if level.startswith('h'):
            try:
                return int(level[1:])
            except:
                return 2
        return 2

    def _infer_page_number(self, position: int, page_breaks: List[Dict]) -> int:
        """Infer page number for a given text position"""
        page_num = 1
        for page_break in page_breaks:
            if page_break['position'] <= position:
                if page_break.get('page_number'):
                    page_num = page_break['page_number']
                else:
                    page_num += 1
            else:
                break
        return page_num

    def _post_process_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Post-process chunks to ensure quality and token limits"""
        processed_chunks = []

        for i, chunk in enumerate(chunks):
            # Estimate token count (rough approximation: 1 token ≈ 4 characters)
            estimated_tokens = len(chunk['text']) // 4

            if estimated_tokens > self.max_tokens:
                # Split oversized chunks
                sub_chunks = self._split_oversized_chunk(chunk)
                processed_chunks.extend(sub_chunks)
            else:
                # Add chunk metadata
                chunk['chunk_index'] = i
                chunk['estimated_tokens'] = estimated_tokens
                chunk['chunk_checksum'] = hashlib.md5(chunk['text'].encode()).hexdigest()[:16]
                processed_chunks.append(chunk)

        return processed_chunks

    def _split_oversized_chunk(self, chunk: Dict) -> List[Dict]:
        """Split a chunk that exceeds token limits"""
        text = chunk['text']
        max_chars = self.max_tokens * 4  # Rough conversion

        if len(text) <= max_chars:
            return [chunk]

        # Split at sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sub_chunks = []
        current_text = ""

        for sentence in sentences:
            if len(current_text) + len(sentence) <= max_chars:
                current_text += sentence + " "
            else:
                if current_text.strip():
                    sub_chunk = chunk.copy()
                    sub_chunk['text'] = current_text.strip()
                    sub_chunk['estimated_tokens'] = len(current_text) // 4
                    sub_chunks.append(sub_chunk)
                current_text = sentence + " "

        # Add remaining text
        if current_text.strip():
            sub_chunk = chunk.copy()
            sub_chunk['text'] = current_text.strip()
            sub_chunk['estimated_tokens'] = len(current_text) // 4
            sub_chunks.append(sub_chunk)

        return sub_chunks


class EnhancedKnowledgeService(KnowledgeService):
    """
    Phase 2 Enhanced Knowledge Service with RAG and chunking
    """

    def __init__(self, vector_store: ChunkedVectorStore):
        super().__init__(vector_store)
        self.chunker = DocumentChunker()
        self.embedding_generator = get_embedding_generator()

    def add_document_with_chunking(
        self,
        source_org: str,
        title: str,
        content_summary: str,
        full_content: str,
        authority_level: str = 'medium',
        version: str = '',
        publication_date: Optional[datetime] = None,
        tags: Optional[Dict] = None
    ) -> str:
        """Add document with automatic chunking and embedding"""

        # Create knowledge document
        knowledge = self.model.objects.create(
            source_organization=source_org,
            document_title=title,
            document_version=version,
            authority_level=authority_level,
            content_summary=content_summary,
            publication_date=publication_date or datetime.now(),
            is_current=True
        )

        # Chunk the full content
        document_metadata = {
            'title': title,
            'organization': source_org,
            'authority_level': authority_level,
            'version': version,
            **{tags or {}}
        }

        chunks = self.chunker.chunk_document(full_content, document_metadata)

        # Generate embeddings for chunks
        enhanced_chunks = []
        for chunk in chunks:
            try:
                embedding_result = self.embedding_generator.generate_embedding(chunk['text'])

                # Handle both old and new embedding generator interfaces
                if hasattr(embedding_result, 'embedding'):
                    # New ProductionEmbeddingService returns EmbeddingResult object
                    chunk['vector'] = embedding_result.embedding
                    chunk['embedding_metadata'] = {
                        'provider': embedding_result.provider,
                        'model': embedding_result.model,
                        'cost_cents': embedding_result.cost_cents,
                        'token_count': embedding_result.token_count,
                        'cached': embedding_result.cached
                    }
                else:
                    # Old EnhancedEmbeddingGenerator returns List[float] directly
                    chunk['vector'] = embedding_result
                    chunk['embedding_metadata'] = {'provider': 'legacy', 'cached': False}

                enhanced_chunks.append(chunk)
            except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
                logger.error(f"Error generating embedding for chunk: {str(e)}")
                chunk['vector'] = None
                chunk['embedding_metadata'] = {'provider': 'error', 'error': str(e)}
                enhanced_chunks.append(chunk)

        # Store chunks
        success = self.vector_store.store_document_chunks(
            str(knowledge.knowledge_id), enhanced_chunks
        )

        if success:
            logger.info(f"Added document with {len(enhanced_chunks)} chunks: {title}")
        else:
            logger.error(f"Failed to store chunks for document: {title}")

        return str(knowledge.knowledge_id)

    def retrieve_grounded_context(
        self,
        query: str,
        top_k: int = 5,
        authority_filter: Optional[List[str]] = None,
        source_filter: Optional[List[str]] = None,
        include_chunk_text: bool = True
    ) -> List[Dict]:
        """Retrieve context chunks for RAG grounding"""

        # Generate query embedding
        query_embedding_result = self.embedding_generator.generate_embedding(query)

        # Handle both old and new embedding generator interfaces
        if hasattr(query_embedding_result, 'embedding'):
            query_embedding = query_embedding_result.embedding
        else:
            query_embedding = query_embedding_result

        # Search for similar chunks
        chunk_results = self.vector_store.search_similar_chunks(
            query_vector=query_embedding,
            top_k=top_k,
            threshold=0.5,  # Lower threshold for broader retrieval
            authority_filter=authority_filter,
            source_filter=source_filter
        )

        # Format results for grounding
        grounded_context = []
        for chunk in chunk_results:
            context_item = {
                'source_id': chunk['chunk_id'],
                'document_title': chunk['metadata']['document_title'],
                'source_organization': chunk['metadata']['source_organization'],
                'authority_level': chunk['metadata']['authority_level'],
                'similarity_score': chunk['similarity'],
                'chunk_position': chunk['chunk_index'],
                'publication_date': chunk['metadata']['publication_date']
            }

            if include_chunk_text:
                context_item['content'] = chunk['content_text']

            grounded_context.append(context_item)

        return grounded_context

    def embed_existing_knowledge(self, knowledge_id: str, full_content: str) -> bool:
        """Embed existing knowledge document with chunking"""
        try:
            knowledge = self.model.objects.get(knowledge_id=knowledge_id)

            document_metadata = {
                'title': knowledge.document_title,
                'organization': knowledge.source_organization,
                'authority_level': knowledge.authority_level,
                'version': knowledge.document_version
            }

            chunks = self.chunker.chunk_document(full_content, document_metadata)

            # Generate embeddings
            enhanced_chunks = []
            for chunk in chunks:
                embedding_result = self.embedding_generator.generate_embedding(chunk['text'])

                # Handle both old and new embedding generator interfaces
                if hasattr(embedding_result, 'embedding'):
                    chunk['vector'] = embedding_result.embedding
                    chunk['embedding_metadata'] = {
                        'provider': embedding_result.provider,
                        'model': embedding_result.model,
                        'cost_cents': embedding_result.cost_cents,
                        'cached': embedding_result.cached
                    }
                else:
                    chunk['vector'] = embedding_result
                    chunk['embedding_metadata'] = {'provider': 'legacy', 'cached': False}

                enhanced_chunks.append(chunk)

            # Store chunks
            return self.vector_store.store_document_chunks(knowledge_id, enhanced_chunks)

        except (ValueError, TypeError) as e:
            logger.error(f"Error embedding knowledge {knowledge_id}: {str(e)}")
            return False

    def search_with_reranking(
        self,
        query: str,
        top_k: int = 5,
        rerank_top_k: int = 20,
        authority_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """Search with semantic re-ranking for better relevance"""

        # First pass: retrieve more candidates
        initial_results = self.retrieve_grounded_context(
            query=query,
            top_k=rerank_top_k,
            authority_filter=authority_filter,
            include_chunk_text=True
        )

        if not initial_results:
            return []

        # Second pass: re-rank based on query relevance and authority
        scored_results = []
        query_words = set(query.lower().split())

        for result in initial_results:
            content = result.get('content', '').lower()
            content_words = set(content.split())

            # Calculate text overlap score
            overlap_score = len(query_words.intersection(content_words)) / max(1, len(query_words))

            # Authority weight
            authority_weights = {'official': 1.0, 'high': 0.8, 'medium': 0.6, 'low': 0.4}
            authority_weight = authority_weights.get(result['authority_level'], 0.5)

            # Combined score
            combined_score = (
                result['similarity_score'] * 0.7 +
                overlap_score * 0.2 +
                authority_weight * 0.1
            )

            result['rerank_score'] = combined_score
            scored_results.append(result)

        # Sort by combined score and return top_k
        scored_results.sort(key=lambda x: x['rerank_score'], reverse=True)
        return scored_results[:top_k]


# =============================================================================
# ENHANCED EMBEDDING GENERATOR
# =============================================================================


class EnhancedEmbeddingGenerator:
    """
    Phase 2 Enhanced embedding generator with caching and fallbacks
    """

    def __init__(self):
        from django.core.cache import cache
        self.cache = cache
        self.cache_timeout = getattr(settings, 'EMBEDDING_CACHE_TIMEOUT', 3600)  # 1 hour

    def generate_embedding(self, text: str, model: str = 'dummy') -> List[float]:
        """Generate embedding with caching"""
        if not text:
            return [0.0] * 384

        # Create cache key
        cache_key = f"embedding:{hash(text)}:{model}"

        # Check cache first
        cached_embedding = self.cache.get(cache_key)
        if cached_embedding:
            return cached_embedding

        # Generate new embedding
        if model == 'dummy':
            embedding = DummyEmbeddingGenerator.generate_embedding(text, model)
        else:
            # Future: Add real embedding providers here
            embedding = DummyEmbeddingGenerator.generate_embedding(text, model)

        # Cache the result
        self.cache.set(cache_key, embedding, self.cache_timeout)

        return embedding

    def generate_batch_embeddings(self, texts: List[str], model: str = 'dummy') -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently"""
        embeddings = []
        for text in texts:
            embedding = self.generate_embedding(text, model)
            embeddings.append(embedding)
        return embeddings


# =============================================================================
# PRODUCTION-GRADE DOCUMENT INGESTION SERVICES
# =============================================================================


class DocumentFetcher:
    """
    Secure document fetcher with allowlist validation and content verification
    """

    def __init__(self):
        # Load allowlisted domains from settings
        self.allowed_domains = getattr(settings, 'KB_ALLOWED_SOURCES', [
            'iso.org',
            'nist.gov',
            'asis.org',
            'wikipedia.org',  # For testing
            'example.com'     # For testing
        ])

        # Security configuration
        self.max_file_size = getattr(settings, 'KB_MAX_FILE_SIZE', 50 * 1024 * 1024)  # 50MB
        self.request_timeout = getattr(settings, 'KB_FETCH_TIMEOUT', 30)
        self.user_agent = f"IntelliWiz-KB-Fetcher/1.0 (+https://{getattr(settings, 'ALLOWED_HOSTS', ['localhost'])[0]}/kb/about)"

        # Rate limiting
        self.rate_limit_delay = getattr(settings, 'KB_RATE_LIMIT_DELAY', 1.0)  # 1 second between requests
        self._last_fetch_time = {}

        # Content type filtering
        self.allowed_content_types = {
            'application/pdf',
            'text/html',
            'text/plain',
            'application/json',
            'application/xml',
            'text/xml'
        }

    def fetch_document(self, source_url: str, knowledge_source: KnowledgeSource) -> Dict[str, any]:
        """
        Fetch document with security validation and content verification

        Args:
            source_url: URL to fetch
            knowledge_source: KnowledgeSource instance for configuration

        Returns:
            Dict containing fetched content and metadata
        """
        logger.info(f"Starting document fetch from {source_url}")

        try:
            # Security validation
            self._validate_url_security(source_url)

            # Rate limiting
            self._enforce_rate_limit(source_url)

            # Check robots.txt if applicable
            if not self._check_robots_txt(source_url):
                raise SecurityError(f"Robots.txt disallows fetching from {source_url}")

            # Prepare request headers
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/pdf,text/plain,application/json,application/xml',
                'Accept-Language': 'en-US,en;q=0.9',
            }

            # Add authentication if configured
            if knowledge_source.auth_config:
                headers.update(self._prepare_auth_headers(knowledge_source.auth_config))

            # Fetch document
            response = requests.get(
                source_url,
                headers=headers,
                timeout=self.request_timeout,
                stream=True,
                verify=True  # Always verify SSL certificates
            )
            response.raise_for_status()

            # Validate response
            self._validate_response(response, source_url)

            # Read content with size limit
            content = self._read_content_safely(response)

            # Calculate checksum
            content_hash = hashlib.sha256(content).hexdigest()

            # Extract metadata
            metadata = self._extract_metadata(response, source_url)

            logger.info(f"Successfully fetched document from {source_url} ({len(content)} bytes)")

            return {
                'content': content,
                'content_hash': content_hash,
                'content_type': response.headers.get('content-type', 'unknown'),
                'metadata': metadata,
                'fetch_timestamp': datetime.now(),
                'source_url': source_url,
                'status_code': response.status_code
            }

        except (ValueError, TypeError) as e:
            logger.error(f"Error fetching document from {source_url}: {str(e)}")
            raise DocumentFetchError(f"Failed to fetch document: {str(e)}")

    def _validate_url_security(self, url: str):
        """Validate URL against security constraints"""
        parsed = urlparse(url)

        # Check protocol
        if parsed.scheme not in ['https', 'http']:
            raise SecurityError(f"Unsupported protocol: {parsed.scheme}")

        # Prefer HTTPS for sensitive sources
        if parsed.scheme == 'http' and any(domain in parsed.netloc for domain in ['nist.gov', 'iso.org']):
            logger.warning(f"Using HTTP for sensitive source: {url}")

        # Check domain allowlist
        domain = parsed.netloc.lower()
        if not any(allowed_domain in domain for allowed_domain in self.allowed_domains):
            raise SecurityError(f"Domain {domain} not in allowlist: {self.allowed_domains}")

        # Check for suspicious patterns
        if any(pattern in url.lower() for pattern in ['.exe', '.bat', '.sh', 'javascript:', 'data:']):
            raise SecurityError(f"Suspicious URL pattern detected: {url}")

    def _enforce_rate_limit(self, url: str):
        """Enforce rate limiting per domain"""
        domain = urlparse(url).netloc
        now = time.time()

        if domain in self._last_fetch_time:
            time_since_last = now - self._last_fetch_time[domain]
            if time_since_last < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last
                logger.info(f"Rate limiting: sleeping {sleep_time:.1f}s for {domain}")
                time.sleep(sleep_time)

        self._last_fetch_time[domain] = now

    def _check_robots_txt(self, url: str) -> bool:
        """Check robots.txt compliance (optional)"""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()

            return rp.can_fetch(self.user_agent, url)
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not check robots.txt for {url}: {str(e)}")
            return True  # Allow by default if robots.txt check fails

    def _prepare_auth_headers(self, auth_config: Dict) -> Dict[str, str]:
        """Prepare authentication headers from configuration"""
        headers = {}

        if auth_config.get('type') == 'bearer_token':
            headers['Authorization'] = f"Bearer {auth_config.get('token')}"
        elif auth_config.get('type') == 'api_key':
            key_header = auth_config.get('header', 'X-API-Key')
            headers[key_header] = auth_config.get('key')
        elif auth_config.get('type') == 'basic_auth':
            import base64
            credentials = f"{auth_config.get('username')}:{auth_config.get('password')}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded}"

        return headers

    def _validate_response(self, response: requests.Response, url: str):
        """Validate HTTP response for security and content"""
        # Check content type
        content_type = response.headers.get('content-type', '').split(';')[0].lower()
        if content_type not in self.allowed_content_types:
            raise SecurityError(f"Disallowed content type: {content_type}")

        # Check content length
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > self.max_file_size:
            raise SecurityError(f"Content too large: {content_length} bytes (max: {self.max_file_size})")

    def _read_content_safely(self, response: requests.Response) -> bytes:
        """Read response content with size limits"""
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > self.max_file_size:
                raise SecurityError(f"Content exceeds size limit: {len(content)} bytes")
        return content

    def _extract_metadata(self, response: requests.Response, url: str) -> Dict[str, any]:
        """Extract metadata from HTTP response"""
        return {
            'last_modified': response.headers.get('last-modified'),
            'etag': response.headers.get('etag'),
            'content_encoding': response.headers.get('content-encoding'),
            'server': response.headers.get('server'),
            'cache_control': response.headers.get('cache-control'),
            'content_language': response.headers.get('content-language'),
            'final_url': response.url,
            'response_headers': dict(response.headers)
        }


class DocumentParser:
    """
    Multi-format document parser supporting PDF, HTML, and text formats
    """

    def __init__(self):
        # Configure parsing options
        self.max_text_length = getattr(settings, 'KB_MAX_TEXT_LENGTH', 1_000_000)  # 1MB of text
        self.preserve_formatting = getattr(settings, 'KB_PRESERVE_FORMATTING', True)

    def parse_document(self, content: bytes, content_type: str, metadata: Dict = None) -> Dict[str, any]:
        """
        Parse document content based on content type

        Args:
            content: Raw document bytes
            content_type: MIME content type
            metadata: Additional metadata from fetcher

        Returns:
            Dict containing parsed text and extracted metadata
        """
        logger.info(f"Parsing document of type {content_type} ({len(content)} bytes)")

        try:
            # Route to appropriate parser
            if content_type.startswith('application/pdf'):
                return self._parse_pdf(content, metadata)
            elif content_type.startswith('text/html'):
                return self._parse_html(content, metadata)
            elif content_type.startswith('text/plain'):
                return self._parse_text(content, metadata)
            elif content_type.startswith('application/json'):
                return self._parse_json(content, metadata)
            elif content_type.startswith(('application/xml', 'text/xml')):
                return self._parse_xml(content, metadata)
            else:
                raise UnsupportedFormatError(f"Unsupported content type: {content_type}")

        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing document: {str(e)}")
            raise DocumentParseError(f"Failed to parse document: {str(e)}")

    def _parse_pdf(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse PDF document"""
        try:
            import PyPDF2
            from io import BytesIO

            pdf_reader = PyPDF2.PdfReader(BytesIO(content))

            # Extract text from all pages
            full_text = ""
            page_texts = []

            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                page_texts.append(page_text)
                full_text += page_text + "\n\n"

                if len(full_text) > self.max_text_length:
                    logger.warning(f"PDF text exceeds limit, truncating at page {page_num}")
                    break

            # Extract metadata
            pdf_info = pdf_reader.metadata or {}

            return {
                'full_text': full_text.strip(),
                'page_texts': page_texts,
                'page_count': len(pdf_reader.pages),
                'document_info': {
                    'title': pdf_info.get('/Title'),
                    'author': pdf_info.get('/Author'),
                    'subject': pdf_info.get('/Subject'),
                    'creator': pdf_info.get('/Creator'),
                    'creation_date': pdf_info.get('/CreationDate'),
                    'modification_date': pdf_info.get('/ModDate')
                },
                'parser_metadata': {
                    'parser': 'PyPDF2',
                    'pages_processed': len(page_texts),
                    'total_chars': len(full_text)
                }
            }

        except ImportError:
            logger.warning("PyPDF2 not installed, falling back to basic text extraction")
            # Fallback: treat as binary and extract what we can
            text = content.decode('utf-8', errors='ignore')
            return {
                'full_text': text[:self.max_text_length],
                'page_texts': [text],
                'page_count': 1,
                'document_info': {},
                'parser_metadata': {'parser': 'fallback_binary', 'fallback': True}
            }
        except (ValueError, TypeError) as e:
            logger.error(f"PDF parsing failed: {str(e)}")
            raise DocumentParseError(f"PDF parsing error: {str(e)}")

    def _parse_html(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse HTML document"""
        try:
            from bs4 import BeautifulSoup

            # Decode content
            text_content = content.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(text_content, 'html.parser')

            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()

            # Extract title
            title = soup.find('title')
            title_text = title.get_text().strip() if title else ""

            # Extract main content
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            if main_content:
                full_text = main_content.get_text(separator='\n', strip=True)
            else:
                full_text = soup.get_text(separator='\n', strip=True)

            # Limit text length
            if len(full_text) > self.max_text_length:
                full_text = full_text[:self.max_text_length]
                logger.warning("HTML text truncated due to size limit")

            # Extract headings for structure
            headings = []
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                headings.append({
                    'level': heading.name,
                    'text': heading.get_text().strip()
                })

            return {
                'full_text': full_text,
                'title': title_text,
                'headings': headings,
                'document_info': {
                    'title': title_text,
                    'language': soup.get('lang'),
                    'description': self._extract_meta_content(soup, 'description'),
                    'keywords': self._extract_meta_content(soup, 'keywords'),
                    'author': self._extract_meta_content(soup, 'author')
                },
                'parser_metadata': {
                    'parser': 'BeautifulSoup',
                    'total_chars': len(full_text),
                    'headings_count': len(headings)
                }
            }

        except ImportError:
            logger.warning("BeautifulSoup not installed, using basic HTML parsing")
            # Fallback: strip HTML tags with regex
            text = content.decode('utf-8', errors='ignore')
            clean_text = re.sub(r'<[^>]+>', '', text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            return {
                'full_text': clean_text[:self.max_text_length],
                'title': "",
                'headings': [],
                'document_info': {},
                'parser_metadata': {'parser': 'regex_fallback', 'fallback': True}
            }
        except (ValueError, TypeError) as e:
            logger.error(f"HTML parsing failed: {str(e)}")
            raise DocumentParseError(f"HTML parsing error: {str(e)}")

    def _parse_text(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse plain text document"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'utf-16', 'iso-8859-1', 'cp1252']:
                try:
                    text = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Fallback with error replacement
                text = content.decode('utf-8', errors='replace')

            # Limit text length
            if len(text) > self.max_text_length:
                text = text[:self.max_text_length]
                logger.warning("Text content truncated due to size limit")

            # Basic structure extraction
            lines = text.split('\n')
            potential_headings = []

            for i, line in enumerate(lines[:100]):  # Check first 100 lines
                line = line.strip()
                if line and (line.isupper() or line.endswith(':') or len(line) < 80):
                    potential_headings.append({
                        'line_number': i,
                        'text': line
                    })

            return {
                'full_text': text,
                'line_count': len(lines),
                'potential_headings': potential_headings,
                'document_info': {},
                'parser_metadata': {
                    'parser': 'plain_text',
                    'encoding_used': encoding if 'encoding' in locals() else 'utf-8',
                    'total_chars': len(text),
                    'line_count': len(lines)
                }
            }

        except (ValueError, TypeError) as e:
            logger.error(f"Text parsing failed: {str(e)}")
            raise DocumentParseError(f"Text parsing error: {str(e)}")

    def _parse_json(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse JSON document"""
        try:
            import json

            text_content = content.decode('utf-8', errors='ignore')
            data = json.loads(text_content)

            # Convert JSON to readable text format
            if isinstance(data, dict):
                full_text = self._json_to_text(data)
            elif isinstance(data, list):
                full_text = "\n".join(self._json_to_text(item) if isinstance(item, dict) else str(item) for item in data)
            else:
                full_text = str(data)

            return {
                'full_text': full_text[:self.max_text_length],
                'json_data': data,
                'document_info': {
                    'title': data.get('title') if isinstance(data, dict) else None,
                    'version': data.get('version') if isinstance(data, dict) else None
                },
                'parser_metadata': {
                    'parser': 'json',
                    'data_type': type(data).__name__,
                    'total_chars': len(full_text)
                }
            }

        except (ValueError, TypeError) as e:
            logger.error(f"JSON parsing failed: {str(e)}")
            raise DocumentParseError(f"JSON parsing error: {str(e)}")

    def _parse_xml(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse XML document"""
        try:
            import xml.etree.ElementTree as ET

            text_content = content.decode('utf-8', errors='ignore')
            root = ET.fromstring(text_content)

            # Extract text content from XML
            full_text = self._xml_to_text(root)

            # Extract document info
            title = root.find('.//title')
            version = root.find('.//version')

            return {
                'full_text': full_text[:self.max_text_length],
                'root_tag': root.tag,
                'document_info': {
                    'title': title.text if title is not None else None,
                    'version': version.text if version is not None else None
                },
                'parser_metadata': {
                    'parser': 'xml_etree',
                    'root_element': root.tag,
                    'total_chars': len(full_text)
                }
            }

        except (ValueError, TypeError) as e:
            logger.error(f"XML parsing failed: {str(e)}")
            raise DocumentParseError(f"XML parsing error: {str(e)}")

    def _extract_meta_content(self, soup, name: str) -> Optional[str]:
        """Extract content from HTML meta tags"""
        meta = soup.find('meta', attrs={'name': name}) or soup.find('meta', attrs={'property': f'og:{name}'})
        return meta.get('content') if meta else None

    def _json_to_text(self, data: Dict, prefix: str = "") -> str:
        """Convert JSON dictionary to readable text"""
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._json_to_text(value, prefix + "  "))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}: [{len(value)} items]")
                for i, item in enumerate(value[:5]):  # Limit to first 5 items
                    if isinstance(item, dict):
                        lines.append(f"{prefix}  {i+1}:")
                        lines.append(self._json_to_text(item, prefix + "    "))
                    else:
                        lines.append(f"{prefix}  {i+1}: {str(item)}")
            else:
                lines.append(f"{prefix}{key}: {str(value)}")
        return "\n".join(lines)

    def _xml_to_text(self, element, level: int = 0) -> str:
        """Convert XML element to readable text"""
        lines = []
        indent = "  " * level

        # Add element tag and text
        if element.text and element.text.strip():
            lines.append(f"{indent}{element.tag}: {element.text.strip()}")
        else:
            lines.append(f"{indent}{element.tag}:")

        # Add attributes
        if element.attrib:
            for key, value in element.attrib.items():
                lines.append(f"{indent}  @{key}: {value}")

        # Process child elements
        for child in element:
            lines.append(self._xml_to_text(child, level + 1))

        return "\n".join(lines)


# Custom exceptions
class SecurityError(Exception):
    """Raised when security validation fails"""
    pass


class DocumentFetchError(Exception):
    """Raised when document fetching fails"""
    pass


class DocumentParseError(Exception):
    """Raised when document parsing fails"""
    pass


class UnsupportedFormatError(Exception):
    """Raised when document format is not supported"""
    pass


# =============================================================================
# SERVICE FACTORY (Updated for Phase 2)
# =============================================================================


def get_vector_store() -> VectorStore:
    """
    Factory function to get vector store backend based on configuration

    Supported backends:
    - postgres_array (default): PostgreSQL ArrayField backend
    - pgvector: PostgreSQL pgvector extension backend (recommended for production)
    - chroma: ChromaDB backend
    """
    backend_name = getattr(settings, 'ONBOARDING_VECTOR_BACKEND', 'postgres_array')

    try:
        if backend_name == 'postgres_array':
            return PostgresArrayBackend()

        elif backend_name == 'pgvector':
            try:
                # Enhanced pgvector backend with better error handling and performance
                return EnhancedPgVectorBackend()
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to initialize pgvector backend: {str(e)}, falling back to postgres_array")
                return PostgresArrayBackend()

        elif backend_name == 'chroma':
            try:
                collection_name = getattr(settings, 'CHROMA_COLLECTION_NAME', 'intelliwiz_knowledge')
                return ChromaBackend(collection_name)
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to initialize ChromaDB backend: {str(e)}, falling back to postgres_array")
                return PostgresArrayBackend()

        else:
            logger.warning(f"Unknown vector backend '{backend_name}', falling back to postgres_array")
            return PostgresArrayBackend()

    except (ValueError, TypeError) as e:
        logger.error(f"Error initializing vector store backend '{backend_name}': {str(e)}")
        logger.info("Falling back to default postgres_array backend")
        return PostgresArrayBackend()


class EnhancedPgVectorBackend(PgVectorBackend):
    """
    Enhanced pgvector backend with production optimizations,
    chunk-level caching, and advanced similarity search
    """

    def __init__(self, chunk_model=None):
        super().__init__(chunk_model)
        self.cache_timeout = getattr(settings, 'PGVECTOR_CACHE_TIMEOUT', 3600)  # 1 hour
        self.enable_index_optimization = getattr(settings, 'PGVECTOR_ENABLE_INDEX_OPTIMIZATION', True)
        self.similarity_threshold = getattr(settings, 'PGVECTOR_SIMILARITY_THRESHOLD', 0.7)

    def ensure_pgvector_indexes(self):
        """Ensure optimal pgvector indexes exist for performance"""
        if not self._pgvector_available:
            return False

        try:
            from django.db import connection

            # SQL to create HNSW index for better performance
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

        except (ValueError, TypeError, AttributeError) as e:
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
            # Check cache first
            from django.core.cache import cache
            cached_results = cache.get(cache_key)
            if cached_results:
                logger.debug(f"Cache hit for similarity search: {cache_key}")
                return cached_results

        # Perform search
        results = self.search_similar(query_vector, top_k, threshold)

        # Cache results if cache_key provided
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
            # Fall back to individual searches
            return [self.search_similar(qv, top_k, threshold) for qv in query_vectors]

        try:
            from django.db import connection
            import json

            # Use advanced pgvector batch query
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

            # Convert vectors to PostgreSQL array format
            vector_strings = [
                '[' + ','.join(map(str, vec)) + ']'
                for vec in query_vectors
            ]

            with connection.cursor() as cursor:
                cursor.execute(batch_sql, [vector_strings, vector_strings, threshold, top_k])
                rows = cursor.fetchall()

                # Group results by query_id
                results_by_query = {}
                for row in rows:
                    query_id = row[0] - 1  # Convert to 0-based index
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

                # Return results in order of input queries
                ordered_results = []
                for i in range(len(query_vectors)):
                    ordered_results.append(results_by_query.get(i, []))

                logger.info(f"pgvector batch search completed for {len(query_vectors)} queries")
                return ordered_results

        except (AttributeError, ConnectionError, TypeError, ValueError) as e:
            logger.error(f"pgvector batch search failed: {str(e)}")
            # Fall back to individual searches
            return [self.search_similar(qv, top_k, threshold) for qv in query_vectors]

    def get_advanced_stats(self) -> Dict[str, Any]:
        """Get advanced statistics for pgvector backend"""
        stats = self.get_embedding_stats()

        if self._pgvector_available:
            try:
                from django.db import connection

                # Get pgvector-specific statistics
                with connection.cursor() as cursor:
                    # Check index usage
                    cursor.execute("""
                        SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
                        FROM pg_stat_user_indexes
                        WHERE tablename = 'authoritative_knowledge_chunk'
                        AND indexname LIKE '%vector%'
                    """)
                    index_stats = cursor.fetchall()

                    # Get vector dimension distribution
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
                            {
                                'index_name': row[2],
                                'tuples_read': row[3],
                                'tuples_fetched': row[4]
                            }
                            for row in index_stats
                        ],
                        'dimension_distribution': [
                            {'dimension': row[0], 'count': row[1]}
                            for row in dimension_stats
                        ]
                    }
                })

            except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
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
            # Create optimal indexes
            if self.ensure_pgvector_indexes():
                optimization_results['indexes_created'] = True

            # Update table statistics
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("ANALYZE authoritative_knowledge_chunk;")
                optimization_results['statistics_updated'] = True

            # Warm up cache with common queries
            if self._warm_up_cache():
                optimization_results['cache_warmed'] = True

            # Run performance baseline
            optimization_results['performance_baseline'] = self._run_performance_baseline()

            logger.info("pgvector backend optimized for production")

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error optimizing pgvector backend: {str(e)}")

        return optimization_results

    def _warm_up_cache(self) -> bool:
        """Warm up cache with common similarity searches"""
        try:
            # Get some sample vectors for cache warming
            sample_chunks = self.chunk_model.objects.filter(
                content_vector__isnull=False,
                is_current=True
            ).order_by('-chunk_id')[:5]

            for chunk in sample_chunks:
                if chunk.content_vector:
                    # Perform similarity search to warm up indexes
                    self.search_similar(chunk.content_vector, top_k=10, threshold=0.5)

            return True

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.warning(f"Cache warm-up failed: {str(e)}")
            return False

    def _run_performance_baseline(self) -> Dict[str, Any]:
        """Run performance baseline tests"""
        import time

        baseline = {
            'single_search_avg_ms': 0.0,
            'batch_search_avg_ms': 0.0,
            'index_performance': 'unknown'
        }

        try:
            # Test single search performance
            test_vector = [0.1] * 384
            search_times = []

            for _ in range(5):
                start_time = time.time()
                self.search_similar(test_vector, top_k=10, threshold=0.6)
                end_time = time.time()
                search_times.append((end_time - start_time) * 1000)

            baseline['single_search_avg_ms'] = sum(search_times) / len(search_times)

            # Test batch search performance
            test_vectors = [[0.1 + i*0.01] * 384 for i in range(3)]
            start_time = time.time()
            self.batch_similarity_search(test_vectors, top_k=5, threshold=0.6)
            end_time = time.time()

            baseline['batch_search_avg_ms'] = ((end_time - start_time) * 1000) / len(test_vectors)

            # Assess performance
            if baseline['single_search_avg_ms'] < 100:
                baseline['index_performance'] = 'excellent'
            elif baseline['single_search_avg_ms'] < 500:
                baseline['index_performance'] = 'good'
            elif baseline['single_search_avg_ms'] < 1000:
                baseline['index_performance'] = 'acceptable'
            else:
                baseline['index_performance'] = 'needs_optimization'

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.warning(f"Performance baseline failed: {str(e)}")

        return baseline


def get_knowledge_service() -> EnhancedKnowledgeService:
    """Factory function to get enhanced knowledge service with configured backend"""
    vector_store = get_vector_store()
    return EnhancedKnowledgeService(vector_store)


def get_embedding_generator():
    """Factory function to get embedding generator"""
    # Check if production embeddings are enabled
    if getattr(settings, 'ENABLE_PRODUCTION_EMBEDDINGS', False):
        from .production_embeddings import get_production_embedding_service
        return get_production_embedding_service()
    else:
        # Phase 2: Enhanced generator with caching (fallback)
        return EnhancedEmbeddingGenerator()


def get_document_chunker(chunk_size: int = 1000, chunk_overlap: int = 200) -> DocumentChunker:
    """Factory function to get document chunker"""
    return DocumentChunker(chunk_size, chunk_overlap)


def get_document_fetcher() -> DocumentFetcher:
    """Factory function to get document fetcher"""
    return DocumentFetcher()


def get_document_parser() -> DocumentParser:
    """Factory function to get document parser"""
    return DocumentParser()