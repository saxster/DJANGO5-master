from abc import ABC, abstractmethod
from typing import List, Dict


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