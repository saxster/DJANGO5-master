"""
Capability and Business Territory hierarchy queries.

Handles web capabilities, business territory trees, and hierarchical data.
"""

from typing import List, Dict
from .base import TreeTraversal
import logging

logger = logging.getLogger(__name__)


class CapabilityQueries:
    """Query repository for capability and BT hierarchy operations."""

    @staticmethod
    def get_web_caps_for_client() -> List[Dict]:
        """
        Get web capabilities hierarchy.

        Replaces the recursive CTE with simple Python tree traversal.
        Much faster and more maintainable for typical capability trees.
        """
        from apps.peoples.models import Capability

        capabilities = list(
            Capability.objects
            .filter(cfor='WEB', enable=True)
            .select_related('parent')
            .order_by('id')
        )

        if not capabilities:
            return []

        result = TreeTraversal.build_tree(
            capabilities,
            root_id=1,
            id_field='id',
            code_field='capscode',
            parent_field='parent_id'
        )

        return result

    @staticmethod
    def get_childrens_of_bt(bt_id: int) -> List[Dict]:
        """
        Get all children of a business territory.

        Replaces recursive CTE with simple tree traversal.
        """
        from apps.client_onboarding.models import Bt

        business_units = list(
            Bt.objects
            .filter(enable=True)
            .select_related('parent', 'identifier')
            .order_by('id')
        )

        if not business_units:
            return []

        result = TreeTraversal.build_tree(
            business_units,
            root_id=bt_id,
            id_field='id',
            code_field='bucode',
            parent_field='parent_id'
        )

        result.sort(key=lambda x: x['xpath'])

        return result