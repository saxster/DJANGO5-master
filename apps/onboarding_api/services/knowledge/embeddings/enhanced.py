import logging
from typing import List
from django.conf import settings
from django.core.cache import cache

from .dummy import DummyEmbeddingGenerator

logger = logging.getLogger(__name__)


class EnhancedEmbeddingGenerator:
    """
    Phase 2 Enhanced embedding generator with caching and fallbacks
    """

    def __init__(self):
        self.cache = cache
        self.cache_timeout = getattr(settings, 'EMBEDDING_CACHE_TIMEOUT', 3600)

    def generate_embedding(self, text: str, model: str = 'dummy') -> List[float]:
        """Generate embedding with caching"""
        if not text:
            return [0.0] * 384

        cache_key = f"embedding:{hash(text)}:{model}"

        cached_embedding = self.cache.get(cache_key)
        if cached_embedding:
            return cached_embedding

        if model == 'dummy':
            embedding = DummyEmbeddingGenerator.generate_embedding(text, model)
        else:
            embedding = DummyEmbeddingGenerator.generate_embedding(text, model)

        self.cache.set(cache_key, embedding, self.cache_timeout)

        return embedding

    def generate_batch_embeddings(self, texts: List[str], model: str = 'dummy') -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently"""
        embeddings = []
        for text in texts:
            embedding = self.generate_embedding(text, model)
            embeddings.append(embedding)
        return embeddings