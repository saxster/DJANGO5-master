"""
Knowledge service with vector store for Conversational Onboarding
Refactored for maintainability and compliance with .claude/rules.md Rule 7
"""

from .base import VectorStore

from .vector_stores import (
    PostgresVectorStore,
    PostgresArrayBackend,
    PgVectorBackend,
    EnhancedPgVectorBackend,
    ChromaBackend,
    ChunkedVectorStore,
)

from .knowledge import (
    KnowledgeService,
    EnhancedKnowledgeService,
)

from .embeddings import (
    DummyEmbeddingGenerator,
    EnhancedEmbeddingGenerator,
)

from .document_processing import (
    DocumentChunker,
    DocumentFetcher,
    DocumentParser,
    PDFParser,
    HTMLParser,
    TextParser,
)

from .exceptions import (
    SecurityError,
    DocumentFetchError,
    DocumentParseError,
    UnsupportedFormatError,
)

from .factories import (
    get_vector_store,
    get_knowledge_service,
    get_embedding_generator,
    get_document_chunker,
    get_document_fetcher,
    get_document_parser,
)

__all__ = [
    'VectorStore',
    'PostgresVectorStore',
    'PostgresArrayBackend',
    'PgVectorBackend',
    'EnhancedPgVectorBackend',
    'ChromaBackend',
    'ChunkedVectorStore',
    'KnowledgeService',
    'EnhancedKnowledgeService',
    'DummyEmbeddingGenerator',
    'EnhancedEmbeddingGenerator',
    'DocumentChunker',
    'DocumentFetcher',
    'DocumentParser',
    'PDFParser',
    'HTMLParser',
    'TextParser',
    'SecurityError',
    'DocumentFetchError',
    'DocumentParseError',
    'UnsupportedFormatError',
    'get_vector_store',
    'get_knowledge_service',
    'get_embedding_generator',
    'get_document_chunker',
    'get_document_fetcher',
    'get_document_parser',
]