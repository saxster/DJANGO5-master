import logging
from datetime import datetime
from typing import List, Dict, Optional
from django.core.exceptions import ObjectDoesNotExist

from .service import KnowledgeService
from ..vector_stores.legacy import ChunkedVectorStore
from ..document_processing.chunker import DocumentChunker

logger = logging.getLogger(__name__)


class EnhancedKnowledgeService(KnowledgeService):
    """
    Phase 2 Enhanced Knowledge Service with RAG and chunking
    """

    def __init__(self, vector_store: ChunkedVectorStore, embedding_generator=None):
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