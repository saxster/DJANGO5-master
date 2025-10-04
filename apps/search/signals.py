"""
Signal handlers for automatic search index updates

Listens to model changes and updates SearchIndex accordingly
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.postgres.search import SearchVector
import logging

logger = logging.getLogger(__name__)


def update_search_index(model_instance, entity_type, delete=False):
    """
    Update or delete search index entry

    Called by signal handlers to keep index in sync
    """
    from apps.search.models import SearchIndex

    try:
        if delete:
            SearchIndex.objects.filter(
                tenant=model_instance.tenant,
                entity_type=entity_type,
                entity_id=str(model_instance.id)
            ).delete()
        else:
            search_vector = None
            if hasattr(model_instance, 'get_search_text'):
                search_text = model_instance.get_search_text()
                search_vector = SearchVector(search_text)

            SearchIndex.objects.update_or_create(
                tenant=model_instance.tenant,
                entity_type=entity_type,
                entity_id=str(model_instance.id),
                defaults={
                    'title': model_instance.get_search_title(),
                    'subtitle': model_instance.get_search_subtitle(),
                    'content': model_instance.get_search_content(),
                    'search_vector': search_vector,
                    'is_active': True
                }
            )

    except (AttributeError, ValueError) as e:
        logger.error(f"Failed to update search index: {e}")