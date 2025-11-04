"""
Business Unit cache management utilities.

Contains cache clearing logic for Bt model hierarchy.
"""


def clear_bu_cache_for_instance(bt_instance, old_parent_id=None):
    """
    Clear BU tree cache for affected clients.

    Args:
        bt_instance: The Bt instance to clear cache for
        old_parent_id: Previous parent ID if parent changed
    """
    from django.core.cache import cache
    import logging

    logger = logging.getLogger(__name__)

    if bt_instance.parent_id:
        clear_cache_for_bu_tree(bt_instance.parent_id)

    if old_parent_id and old_parent_id != bt_instance.parent_id:
        clear_cache_for_bu_tree(old_parent_id)

    clear_cache_for_bu_tree(bt_instance.id)
    logger.info(f"Cache cleared for BU {bt_instance.bucode} (ID: {bt_instance.id})")


def clear_cache_for_bu_tree(bu_id):
    """Clear all cache keys related to a BU tree."""
    from django.core.cache import cache

    cache_patterns = [
        f"bulist_{bu_id}_True_True_array",
        f"bulist_{bu_id}_True_True_text",
        f"bulist_{bu_id}_True_True_jsonb",
        f"bulist_{bu_id}_True_False_array",
        f"bulist_{bu_id}_True_False_text",
        f"bulist_{bu_id}_True_False_jsonb",
        f"bulist_{bu_id}_False_True_array",
        f"bulist_{bu_id}_False_True_text",
        f"bulist_{bu_id}_False_True_jsonb",
        f"bulist_{bu_id}_False_False_array",
        f"bulist_{bu_id}_False_False_text",
        f"bulist_{bu_id}_False_False_jsonb",
        f"bulist_idnf_{bu_id}_True_True",
        f"bulist_idnf_{bu_id}_True_False",
        f"bulist_idnf_{bu_id}_False_True",
        f"bulist_idnf_{bu_id}_False_False",
    ]

    for pattern in cache_patterns:
        cache.delete(pattern)
