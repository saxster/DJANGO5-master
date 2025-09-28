"""
Base utilities for query operations.

Provides shared helper classes used across all query repositories.
"""

from typing import List, Dict
from django.db.models import Count
import logging

logger = logging.getLogger(__name__)


class TreeTraversal:
    """
    Simple and efficient tree traversal utilities.

    Replaces complex recursive CTEs with simple Python loops.
    Much faster for typical hierarchical data (< 10k nodes).
    """

    @staticmethod
    def build_tree(
        nodes: List,
        root_id: int,
        id_field: str = 'id',
        code_field: str = 'code',
        parent_field: str = 'parent_id'
    ) -> List[Dict]:
        """
        Build a hierarchical tree from flat data.

        Args:
            nodes: List of objects/dicts containing hierarchical data
            root_id: ID of the root node to start traversal
            id_field: Name of the ID field
            code_field: Name of the code field (for path building)
            parent_field: Name of the parent ID field

        Returns:
            List of dicts with tree structure including depth and path
        """
        if not nodes:
            return []

        node_dict = {}
        children_dict = {}

        for node in nodes:
            node_id = getattr(node, id_field) if hasattr(node, id_field) else node[id_field]
            node_dict[node_id] = node

            parent_id = getattr(node, parent_field) if hasattr(node, parent_field) else node[parent_field]
            if parent_id:
                children_dict.setdefault(parent_id, []).append(node)

        def build_subtree(node_id: int, depth: int = 1, path: str = '', xpath: str = '') -> List[Dict]:
            results = []
            node = node_dict.get(node_id)
            if not node:
                return results

            code = getattr(node, code_field) if hasattr(node, code_field) else node[code_field]
            current_path = code if not path else f"{path}->{code}"
            current_xpath = str(node_id) if not xpath else f"{xpath}>{node_id}{depth}"

            result = {
                'id': node_id,
                code_field: code,
                parent_field: getattr(node, parent_field) if hasattr(node, parent_field) else node[parent_field],
                'depth': depth,
                'path': current_path,
                'xpath': current_xpath
            }

            for field in ['capsname', 'cfor', 'butree', 'buname']:
                if hasattr(node, field):
                    result[field] = getattr(node, field)
                elif isinstance(node, dict) and field in node:
                    result[field] = node[field]

            results.append(result)

            for child in children_dict.get(node_id, []):
                child_id = getattr(child, id_field) if hasattr(child, id_field) else child[id_field]
                results.extend(
                    build_subtree(child_id, depth + 1, current_path, current_xpath)
                )

            return results

        return build_subtree(root_id)


class AttachmentHelper:
    """Helper class for attachment-related operations."""

    @staticmethod
    def get_attachment_counts(uuids: List[str]) -> Dict[str, int]:
        """
        Get attachment counts for a list of UUIDs.

        Args:
            uuids: List of UUID strings

        Returns:
            Dict mapping UUID to attachment count
        """
        from apps.activity.models.attachment_model import Attachment

        if not uuids:
            return {}

        counts = (Attachment.objects
                 .filter(owner__in=uuids)
                 .values('owner')
                 .annotate(count=Count('id')))

        return {item['owner']: item['count'] for item in counts}