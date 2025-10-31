"""
Query Expansion with Synonyms

Expands search queries with domain-specific synonyms.

Synonym Categories:
- Security terminology
- Facility management
- Guard operations
- Equipment names

Following CLAUDE.md:
- Rule #7: <150 lines
- Domain knowledge integration

Sprint 9.2: Semantic Search Enhancements
"""

import logging
from typing import List, Set

logger = logging.getLogger(__name__)


class QueryExpander:
    """Expand search queries with synonyms."""

    # Domain-specific synonym dictionary
    SYNONYMS = {
        # Security Personnel
        'security': ['guard', 'officer', 'personnel', 'staff'],
        'guard': ['security', 'officer', 'watchman', 'personnel'],
        'officer': ['guard', 'security', 'personnel'],

        # Operations
        'patrol': ['tour', 'round', 'inspection', 'check'],
        'tour': ['patrol', 'round', 'inspection'],
        'inspection': ['check', 'audit', 'review', 'patrol'],

        # Facilities
        'site': ['location', 'facility', 'premises', 'property'],
        'facility': ['site', 'location', 'premises', 'building'],
        'premises': ['site', 'facility', 'location', 'property'],

        # Equipment
        'camera': ['cctv', 'surveillance', 'monitor'],
        'cctv': ['camera', 'surveillance', 'monitor'],

        # Incidents
        'incident': ['event', 'occurrence', 'issue', 'problem'],
        'emergency': ['crisis', 'urgent', 'critical'],

        # Access Control
        'access': ['entry', 'ingress', 'admission'],
        'entry': ['access', 'ingress', 'gate'],
        'exit': ['egress', 'departure', 'gate'],

        # Reports
        'report': ['log', 'record', 'document'],
        'log': ['report', 'record', 'entry'],
    }

    def __init__(self):
        """Initialize query expander."""
        pass

    def expand_query(self, query: str, max_expansions: int = 3) -> List[str]:
        """
        Expand query with synonyms.

        Args:
            query: Original query text
            max_expansions: Maximum synonyms to add per term

        Returns:
            List of expanded query terms (includes original)
        """
        terms = query.lower().split()
        expanded = set(terms)  # Start with original terms

        for term in terms:
            if term in self.SYNONYMS:
                synonyms = self.SYNONYMS[term][:max_expansions]
                expanded.update(synonyms)

        logger.debug(f"Expanded query '{query}' to {len(expanded)} terms: {expanded}")

        return list(expanded)

    def get_weighted_terms(self, query: str) -> Dict[str, float]:
        """
        Get query terms with weights (original terms weighted higher).

        Args:
            query: Original query

        Returns:
            Dict of {term: weight}
        """
        original_terms = set(query.lower().split())
        expanded_terms = self.expand_query(query)

        weighted = {}
        for term in expanded_terms:
            if term in original_terms:
                weighted[term] = 1.0  # Original terms full weight
            else:
                weighted[term] = 0.5  # Synonyms half weight

        return weighted

    def add_synonym(self, term: str, synonyms: List[str]):
        """
        Add custom synonym mapping.

        Args:
            term: Base term
            synonyms: List of synonyms
        """
        if term not in self.SYNONYMS:
            self.SYNONYMS[term] = []

        self.SYNONYMS[term].extend(synonyms)
        logger.info(f"Added {len(synonyms)} synonyms for '{term}'")

    def get_all_synonyms(self, term: str) -> List[str]:
        """Get all synonyms for a term."""
        return self.SYNONYMS.get(term.lower(), [])


# Singleton instance
query_expander = QueryExpander()


def get_query_expander() -> QueryExpander:
    """Get query expander instance."""
    return query_expander
