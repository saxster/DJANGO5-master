import logging
from datetime import datetime
from typing import List, Dict
from django.conf import settings

from ..base import VectorStore

logger = logging.getLogger(__name__)


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

            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "IntelliWiz authoritative knowledge base"}
            )

            logger.info(f"ChromaDB initialized: collection '{self.collection_name}'")

        except ImportError:
            logger.error("ChromaDB not installed. Install with: pip install chromadb")
            raise
        except (ValueError, TypeError, ConnectionError) as e:
            logger.error(f"Failed to initialize ChromaDB: {str(e)}")
            raise

    def store_embedding(self, knowledge_id: str, vector: List[float], metadata: Dict) -> bool:
        """Store embedding in ChromaDB"""
        try:
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

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Error storing chunk embeddings in ChromaDB: {str(e)}")
            return False

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Search similar vectors in ChromaDB"""
        try:
            results = self._collection.query(
                query_embeddings=[query_vector],
                n_results=min(top_k, 100),
                include=['metadatas', 'documents', 'distances']
            )

            formatted_results = []

            if results['ids'] and results['ids'][0]:
                for i, (id_, metadata, distance) in enumerate(zip(
                    results['ids'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
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

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"ChromaDB search error: {str(e)}")
            return []

    def delete_embedding(self, knowledge_id: str) -> bool:
        """Delete embeddings from ChromaDB"""
        try:
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
                'error': str(e),
                'chroma_available': False
            }