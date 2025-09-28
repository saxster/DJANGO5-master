import logging
from django.conf import settings

from .base import VectorStore
from .vector_stores import PostgresArrayBackend, EnhancedPgVectorBackend, ChromaBackend
from .knowledge import EnhancedKnowledgeService
from .embeddings import EnhancedEmbeddingGenerator
from .document_processing import DocumentChunker, DocumentFetcher, DocumentParser

logger = logging.getLogger(__name__)


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


def get_knowledge_service() -> EnhancedKnowledgeService:
    """Factory function to get enhanced knowledge service with configured backend"""
    vector_store = get_vector_store()
    return EnhancedKnowledgeService(vector_store)


def get_embedding_generator():
    """Factory function to get embedding generator"""
    if getattr(settings, 'ENABLE_PRODUCTION_EMBEDDINGS', False):
        try:
            from ..production_embeddings import get_production_embedding_service
            return get_production_embedding_service()
        except ImportError:
            logger.warning("Production embeddings not available, using enhanced fallback")
            return EnhancedEmbeddingGenerator()
    else:
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