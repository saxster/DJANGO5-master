"""
Voice recognition signals for cache management.

Ensures voice embedding caches stay in sync with database updates.
"""

import logging

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import VoiceEmbedding

logger = logging.getLogger(__name__)


def _invalidate_voiceprint_cache(user_id: int):
    """Best-effort cache invalidation helper."""
    cache_key = f"voice_embeddings:{user_id}"
    cache.delete(cache_key)
    logger.debug("Voice embedding cache invalidated", extra={'user_id': user_id})


@receiver(post_save, sender=VoiceEmbedding)
def invalidate_voiceprint_cache_on_save(sender, instance: VoiceEmbedding, **kwargs):
    """Invalidate cached embeddings when a record is created or updated."""
    _invalidate_voiceprint_cache(instance.user_id)


@receiver(post_delete, sender=VoiceEmbedding)
def invalidate_voiceprint_cache_on_delete(sender, instance: VoiceEmbedding, **kwargs):
    """Invalidate cached embeddings after deletion."""
    _invalidate_voiceprint_cache(instance.user_id)
