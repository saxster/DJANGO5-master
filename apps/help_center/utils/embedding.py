"""Utility functions for deterministic text embeddings."""

from __future__ import annotations

import hashlib
from typing import Iterable, List

import numpy as np

EMBEDDING_DIM = 192


def text_to_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    vector = np.zeros(dim, dtype=np.float32)
    tokens = _tokenize(text)
    for token in tokens:
        digest = hashlib.blake2b(token.encode('utf-8'), digest_size=32).digest()
        for idx in range(0, len(digest), 4):
            slot = int.from_bytes(digest[idx:idx + 2], 'little') % dim
            value = int.from_bytes(digest[idx:idx + 4], 'little') / 0xFFFFFFFF
            vector[slot] += value
    norm = np.linalg.norm(vector) or 1.0
    normalized = vector / norm
    return normalized.round(6).tolist()


def cosine_similarity(vec_a: Iterable[float], vec_b: Iterable[float]) -> float:
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    if a.size == 0 or b.size == 0:
        return 0.0
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8))


def _tokenize(text: str) -> List[str]:
    return [token.strip().lower() for token in text.split() if token]


__all__ = ['text_to_embedding', 'cosine_similarity', 'EMBEDDING_DIM']
