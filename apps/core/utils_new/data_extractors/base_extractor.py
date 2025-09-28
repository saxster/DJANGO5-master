"""
Base Data Extractor - Abstract base class for all data extractors.

This class provides common functionality used by all concrete extractors:
- Site ID extraction from session
- Query optimization with select_related/prefetch_related
- Error handling and logging
- Type safety with type hints

Compliance: .claude/rules.md Rule #7 (Single Responsibility Principle)
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
import logging

logger = logging.getLogger("django")


class BaseDataExtractor(ABC):
    """
    Abstract base class for data extraction strategies.

    Each concrete extractor implements the extract() method to handle
    one specific entity type (TypeAssist, BU, Location, etc.).

    This follows the Strategy design pattern to replace the monolithic
    get_type_data() function with focused, testable implementations.
    """

    @abstractmethod
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        """
        Extract data for this entity type from database.

        Args:
            session_data: Session context containing:
                - client_id: Current client identifier
                - assignedsites: List of accessible site IDs
                - is_admin: Boolean indicating admin access level

        Returns:
            List of tuples containing extracted data rows

        Raises:
            ValueError: If required session data is missing
            DatabaseError: If database query fails
        """
        pass

    def _get_site_ids(self, session_data: Dict[str, Any]) -> List[int]:
        """
        Extract site IDs from session data.

        Args:
            session_data: Session context dictionary

        Returns:
            List of site IDs, ensuring list format

        Raises:
            ValueError: If site IDs are missing or invalid
        """
        site_ids = session_data.get("assignedsites", [])

        if not site_ids:
            logger.warning(
                "No assigned sites in session data",
                extra={'session_keys': list(session_data.keys())}
            )
            return []

        if not isinstance(site_ids, (list, tuple)):
            site_ids = [site_ids]

        if isinstance(site_ids, (int, str)):
            site_ids = [site_ids]

        return site_ids

    def _validate_session_data(self, session_data: Dict[str, Any]) -> None:
        """
        Validate that required session data is present.

        Args:
            session_data: Session context dictionary

        Raises:
            ValueError: If required keys are missing
        """
        required_keys = ['client_id']
        missing_keys = [key for key in required_keys if key not in session_data]

        if missing_keys:
            raise ValueError(
                f"Missing required session data: {', '.join(missing_keys)}"
            )

    def _apply_query_optimization(self, queryset, related_fields: List[str] = None, prefetch_fields: List[str] = None):
        """
        Apply Django ORM optimization to queryset.

        Uses select_related() for FK/OneToOne and prefetch_related() for M2M.
        Complies with Rule #12 from .claude/rules.md

        Args:
            queryset: Django QuerySet to optimize
            related_fields: List of field names for select_related()
            prefetch_fields: List of field names for prefetch_related()

        Returns:
            Optimized queryset
        """
        if related_fields:
            queryset = queryset.select_related(*related_fields)

        if prefetch_fields:
            queryset = queryset.prefetch_related(*prefetch_fields)

        return queryset

    def get_entity_name(self) -> str:
        """
        Get the entity type name handled by this extractor.

        Returns:
            String identifier for the entity type
        """
        return self.__class__.__name__.replace('Extractor', '').upper()


__all__ = ['BaseDataExtractor']