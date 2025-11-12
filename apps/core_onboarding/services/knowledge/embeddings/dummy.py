import hashlib
from typing import List


class DummyEmbeddingGenerator:
    """
    Dummy embedding generator for MVP
    Generates hash-based vectors for testing purposes
    """

    @staticmethod
    def generate_embedding(text: str, model: str = 'dummy') -> List[float]:
        """Generate dummy embedding vector"""
        text_hash = hashlib.md5(text.encode()).hexdigest()

        vector = []
        for i in range(0, len(text_hash), 2):
            byte_val = int(text_hash[i:i+2], 16)
            normalized = (byte_val / 255.0) * 2 - 1
            vector.append(float(normalized))

        target_dim = 384
        while len(vector) < target_dim:
            vector.extend(vector[:min(len(vector), target_dim - len(vector))])

        return vector[:target_dim]