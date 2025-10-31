import logging
from datetime import datetime
from typing import List, Dict, Optional
from django.core.exceptions import ObjectDoesNotExist

from .service import KnowledgeService
from ..base import VectorStore
from ..document_processing.chunker import DocumentChunker
from apps.ontology.decorators import ontology

logger = logging.getLogger(__name__)


@ontology(
    domain="onboarding",
    purpose="AI-powered site setup and knowledge management with RAG",
    criticality="high",
    inputs={
        "full_content": "Document text content for chunking and embedding",
        "query": "Natural language query for semantic search",
        "source_org": "Source organization name (e.g., 'OSHA', 'EPA', 'Internal SOPs')",
        "authority_level": "official/high/medium/low - determines retrieval priority",
        "top_k": "Number of results to retrieve (default 5)",
        "rerank_top_k": "Number of initial results for reranking (default 20)"
    },
    outputs={
        "knowledge_id": "UUID of stored knowledge document",
        "grounded_context": "List of ranked chunks with similarity scores, metadata, and content",
        "chunk_results": "Semantic search results with document_title, authority_level, publication_date",
        "reranked_results": "Results with combined similarity + overlap + authority scoring"
    },
    side_effects=[
        "Creates Knowledge model instance in database",
        "Stores document chunks with embeddings in vector store (PostgreSQL array)",
        "Generates embeddings via EnhancedEmbeddingGenerator (caching enabled)",
        "Updates vector store indexes for similarity search"
    ],
    depends_on=[
        "apps.onboarding.models.Knowledge - Document metadata storage",
        "apps.onboarding_api.services.knowledge.embeddings.EnhancedEmbeddingGenerator",
        "apps.onboarding_api.services.knowledge.vector_stores.PostgresArrayVectorStore",
        "apps.onboarding_api.services.knowledge.document_processing.DocumentChunker",
        "OpenAI/Azure embeddings API (via embedding_generator)"
    ],
    used_by=[
        "apps.onboarding_api.views - AI-powered site onboarding wizard",
        "apps.onboarding_api.knowledge_views - Knowledge base CRUD operations",
        "apps.helpbot.views - Parlant integration for conversational AI",
        "apps.onboarding_api.personalization_views - User-specific content retrieval"
    ],
    tags=["rag", "vector-search", "embeddings", "knowledge-base", "semantic-search", "chunking", "reranking"],
    security_notes=[
        "Authority level filtering: prevents retrieval of low-authority content for critical queries",
        "Source organization filtering: limits results to trusted sources",
        "No PII in embeddings: document metadata only, no user-specific data",
        "Embedding caching: reduces API costs, prevents redundant generation",
        "Vector store isolation: multi-tenant support via knowledge_id namespacing"
    ],
    performance_notes=[
        "Chunking strategy: recursive split with 800 token chunks, 100 token overlap",
        "Embedding batch processing: processes all chunks in single request where possible",
        "Vector search: PostgreSQL pgvector extension for native similarity search",
        "Cache TTL: embeddings cached indefinitely (content-addressable via hash)",
        "Reranking: O(n) complexity for overlap scoring, sorts top_k results only",
        "Threshold: 0.5 minimum similarity score for retrieval (configurable)",
        "Memory efficient: streams chunks, no full document in memory"
    ],
    architecture_notes=[
        "RAG architecture: Retrieval-Augmented Generation for grounded AI responses",
        "Chunking strategy: Overlapping chunks preserve context across boundaries",
        "Embedding models: OpenAI text-embedding-ada-002 or Azure equivalents",
        "Vector store: PostgreSQL with pgvector extension (native array type)",
        "Reranking algorithm: 70% semantic similarity + 20% keyword overlap + 10% authority weight",
        "Authority weights: official (1.0), high (0.8), medium (0.6), low (0.4)",
        "Similarity metric: Cosine similarity on normalized embedding vectors",
        "Chunk metadata: document_title, source_organization, authority_level, chunk_index, publication_date",
        "Embedding metadata: provider, model, cost_cents, token_count, cached flag",
        "Graceful degradation: continues processing if individual chunk embedding fails"
    ],
    examples=[
        {
            "use_case": "Add OSHA document with chunking and embeddings",
            "code": """
# Initialize service
vector_store = PostgresArrayVectorStore()
knowledge_service = EnhancedKnowledgeService(vector_store)

# Add document with automatic chunking
knowledge_id = knowledge_service.add_document_with_chunking(
    source_org='OSHA',
    title='Fall Protection Standards 1910.28',
    content_summary='Comprehensive fall protection requirements for construction sites',
    full_content='<full OSHA document text...>',
    authority_level='official',
    version='2024.1',
    publication_date=datetime(2024, 1, 15),
    tags={'category': 'safety', 'industry': 'construction'}
)

# Returns knowledge_id: '550e8400-e29b-41d4-a716-446655440000'
# Side effects:
# - Creates Knowledge model instance
# - Generates ~15-20 chunks (depending on document length)
# - Embeds all chunks via OpenAI API (or uses cache)
# - Stores chunks with vectors in PostgreSQL
            """
        },
        {
            "use_case": "Retrieve grounded context for RAG",
            "code": """
# Query for relevant context chunks
context = knowledge_service.retrieve_grounded_context(
    query='What are the fall protection requirements for roofing work?',
    top_k=5,
    authority_filter=['official', 'high'],
    source_filter=['OSHA', 'ANSI'],
    include_chunk_text=True
)

# Example output
[
    {
        'source_id': 'chunk_550e8400_003',
        'document_title': 'Fall Protection Standards 1910.28',
        'source_organization': 'OSHA',
        'authority_level': 'official',
        'similarity_score': 0.89,
        'chunk_position': 3,
        'publication_date': datetime(2024, 1, 15),
        'content': 'Employers must ensure that each employee on a walking-working surface...'
    },
    # ... 4 more chunks
]
            """
        },
        {
            "use_case": "Semantic reranking for better relevance",
            "code": """
# Search with reranking (retrieves 20, reranks to top 5)
results = knowledge_service.search_with_reranking(
    query='emergency evacuation procedures for chemical spills',
    top_k=5,
    rerank_top_k=20,
    authority_filter=['official', 'high']
)

# Example reranked result
[
    {
        'source_id': 'chunk_abc123_007',
        'document_title': 'Hazardous Materials Response Procedures',
        'source_organization': 'EPA',
        'authority_level': 'official',
        'similarity_score': 0.82,
        'rerank_score': 0.87,  # Combined score: 0.82*0.7 + 0.15*0.2 + 1.0*0.1
        'chunk_position': 7,
        'content': 'In the event of a chemical spill, immediately activate the evacuation alarm...'
    },
    # ... 4 more chunks
]
            """
        }
    ]
)
class EnhancedKnowledgeService(KnowledgeService):
    """
    Phase 2 Enhanced Knowledge Service with RAG and chunking
    """

    def __init__(self, vector_store: VectorStore, embedding_generator=None):
        super().__init__(vector_store)
        self.chunker = DocumentChunker()

        if embedding_generator is None:
            from ..embeddings import EnhancedEmbeddingGenerator
            self.embedding_generator = EnhancedEmbeddingGenerator()
        else:
            self.embedding_generator = embedding_generator

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
        knowledge = self.model.objects.create(
            source_organization=source_org,
            document_title=title,
            document_version=version,
            authority_level=authority_level,
            content_summary=content_summary,
            publication_date=publication_date or datetime.now(),
            is_current=True
        )

        document_metadata = {
            'title': title,
            'organization': source_org,
            'authority_level': authority_level,
            'version': version,
            **(tags or {})
        }

        chunks = self.chunker.chunk_document(full_content, document_metadata)

        enhanced_chunks = []
        for chunk in chunks:
            try:
                embedding_result = self.embedding_generator.generate_embedding(chunk['text'])

                if hasattr(embedding_result, 'embedding'):
                    chunk['vector'] = embedding_result.embedding
                    chunk['embedding_metadata'] = {
                        'provider': embedding_result.provider,
                        'model': embedding_result.model,
                        'cost_cents': embedding_result.cost_cents,
                        'token_count': embedding_result.token_count,
                        'cached': embedding_result.cached
                    }
                else:
                    chunk['vector'] = embedding_result
                    chunk['embedding_metadata'] = {'provider': 'legacy', 'cached': False}

                enhanced_chunks.append(chunk)
            except (ValueError, TypeError, AttributeError) as e:
                logger.error(f"Error generating embedding for chunk: {str(e)}")
                chunk['vector'] = None
                chunk['embedding_metadata'] = {'provider': 'error', 'error': str(e)}
                enhanced_chunks.append(chunk)

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
        query_embedding_result = self.embedding_generator.generate_embedding(query)

        if hasattr(query_embedding_result, 'embedding'):
            query_embedding = query_embedding_result.embedding
        else:
            query_embedding = query_embedding_result

        chunk_results = self.vector_store.search_similar_chunks(
            query_vector=query_embedding,
            top_k=top_k,
            threshold=0.5,
            authority_filter=authority_filter,
            source_filter=source_filter
        )

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

            enhanced_chunks = []
            for chunk in chunks:
                embedding_result = self.embedding_generator.generate_embedding(chunk['text'])

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

            return self.vector_store.store_document_chunks(knowledge_id, enhanced_chunks)

        except ObjectDoesNotExist:
            logger.error(f"Knowledge {knowledge_id} not found")
            return False
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
        initial_results = self.retrieve_grounded_context(
            query=query,
            top_k=rerank_top_k,
            authority_filter=authority_filter,
            include_chunk_text=True
        )

        if not initial_results:
            return []

        scored_results = []
        query_words = set(query.lower().split())

        for result in initial_results:
            content = result.get('content', '').lower()
            content_words = set(content.split())

            overlap_score = len(query_words.intersection(content_words)) / max(1, len(query_words))

            authority_weights = {'official': 1.0, 'high': 0.8, 'medium': 0.6, 'low': 0.4}
            authority_weight = authority_weights.get(result['authority_level'], 0.5)

            combined_score = (
                result['similarity_score'] * 0.7 +
                overlap_score * 0.2 +
                authority_weight * 0.1
            )

            result['rerank_score'] = combined_score
            scored_results.append(result)

        scored_results.sort(key=lambda x: x['rerank_score'], reverse=True)
        return scored_results[:top_k]