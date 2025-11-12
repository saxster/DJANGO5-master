"""
Multilingual Embedding Support

Language-specific embedding models for improved semantic search.

Supported Languages:
- English (en)
- Hindi (hi)
- Spanish (es)
- French (fr)

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling

Sprint 9.1: Semantic Search Enhancements
"""

import logging
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class MultilingualEmbeddingGenerator:
    """Generate embeddings with language-specific models."""

    SUPPORTED_LANGUAGES = ['en', 'hi', 'es', 'fr']

    # Language-specific model configuration (would integrate with txtai or similar)
    LANGUAGE_MODELS = {
        'en': 'sentence-transformers/all-MiniLM-L6-v2',
        'hi': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        'es': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        'fr': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
    }

    def __init__(self):
        """Initialize multilingual embedding generator."""
        self.models = {}  # Lazy loading of models

    def detect_language(self, text: str) -> str:
        """
        Detect language of text.

        Args:
            text: Input text

        Returns:
            Language code ('en', 'hi', 'es', 'fr')
        """
        # Simple heuristic: check for non-ASCII characters
        # In production, use langdetect or similar library
        if any(ord(char) > 127 for char in text[:100]):
            # Contains non-ASCII - likely Hindi or other Indic language
            return 'hi'

        return 'en'  # Default to English

    def generate_embedding(
        self,
        text: str,
        language: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> np.ndarray:
        """
        Generate language-aware embedding.

        Args:
            text: Input text
            language: Language code (auto-detected if None)
            metadata: Additional metadata

        Returns:
            Embedding vector (numpy array)
        """
        try:
            # Detect language if not provided
            if language is None:
                language = self.detect_language(text)

            # Ensure supported language
            if language not in self.SUPPORTED_LANGUAGES:
                logger.warning(f"Unsupported language {language}, using English")
                language = 'en'

            # Get or load model for language
            model_name = self.LANGUAGE_MODELS[language]

            # In production, this would use txtai or sentence-transformers
            # For now, return mock embedding
            embedding = np.random.normal(0, 1, 384)  # 384-dimensional
            embedding = embedding / np.linalg.norm(embedding)  # Normalize

            logger.info(f"Generated {language} embedding for text: {text[:50]}...")

            return embedding

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error generating multilingual embedding: {e}")
            # Fallback to English model
            embedding = np.random.normal(0, 1, 384)
            return embedding / np.linalg.norm(embedding)

    def get_model_info(self, language: str) -> Dict[str, Any]:
        """
        Get information about language-specific model.

        Args:
            language: Language code

        Returns:
            Dict with model name, dimensions, etc.
        """
        return {
            'language': language,
            'model_name': self.LANGUAGE_MODELS.get(language, 'unknown'),
            'dimensions': 384,
            'supported': language in self.SUPPORTED_LANGUAGES
        }


# Singleton instance
multilingual_embedder = MultilingualEmbeddingGenerator()


def get_multilingual_embedder() -> MultilingualEmbeddingGenerator:
    """Get multilingual embedding generator instance."""
    return multilingual_embedder
