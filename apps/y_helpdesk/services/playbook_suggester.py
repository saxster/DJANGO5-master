"""
Playbook Suggester Service.

Suggests relevant automated playbooks for tickets using similarity matching.
Part of Phase 3: AI & Intelligence Features.

Target: 60%+ SOAR automation rate.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 50 lines
- Rule #11: Specific exception handling

@ontology(
    domain="helpdesk",
    purpose="Suggest relevant automated playbooks for tickets",
    algorithm="TF-IDF + severity/type matching",
    business_value="Enable SOAR-lite automation for common ticket types",
    criticality="medium",
    tags=["helpdesk", "soar", "automation", "playbooks", "suggestions"]
)
"""

import logging
from typing import List, Dict, Any
from django.core.cache import cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, PARSING_EXCEPTIONS

logger = logging.getLogger('helpdesk.playbook_suggester')

__all__ = ['PlaybookSuggester']


class PlaybookSuggester:
    """
    Suggest relevant automated playbooks for tickets.

    Uses TF-IDF + severity/type matching to recommend playbooks that
    could automate ticket resolution.

    Features:
    - Redis caching of playbook vectors (1 hour TTL)
    - Severity-based filtering
    - Confidence scoring (0.0-1.0)
    - Top 5 results
    """

    CONFIDENCE_THRESHOLD = 0.3
    CACHE_TTL = 3600  # 1 hour
    MAX_SUGGESTIONS = 5

    @classmethod
    def suggest_playbooks(cls, ticket) -> List[Dict[str, Any]]:
        """
        Suggest top 5 relevant playbooks for a ticket.

        Args:
            ticket: Ticket instance

        Returns:
            List of dicts: [
                {
                    'playbook_id': str (UUID),
                    'name': str,
                    'confidence': float,
                    'auto_execute': bool,
                    'success_rate': float,
                    'description': str
                },
                ...
            ]

        Raises:
            ValueError: If ticket is invalid
        """
        from apps.noc.models.executable_playbook import ExecutablePlaybook

        if not ticket or not ticket.ticketdesc:
            raise ValueError("Ticket must have description")

        # Get active playbooks for tenant
        playbooks = list(
            ExecutablePlaybook.objects.filter(
                tenant=ticket.tenant,
                is_active=True
            ).order_by('-success_rate')
        )

        if not playbooks:
            logger.info(f"No active playbooks for tenant {ticket.tenant}")
            return []

        query_text = f"{ticket.ticketdesc}"
        ticket_severity = cls._normalize_priority(ticket.priority)

        # Filter by severity first
        severity_filtered = cls._filter_by_severity(playbooks, ticket_severity)
        if not severity_filtered:
            severity_filtered = playbooks  # Fall back to all if none match

        # Try TF-IDF matching
        try:
            suggestions = cls._tfidf_match(query_text, severity_filtered, ticket.tenant.id)
            if suggestions:
                return suggestions
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error during playbook TF-IDF matching: {e}",
                exc_info=True,
                extra={'ticket_id': ticket.id, 'tenant': ticket.tenant.id}
            )
        except (ValueError, AttributeError, KeyError) as e:
            logger.error(
                f"Data error during playbook TF-IDF matching: {e}",
                exc_info=True,
                extra={'ticket_id': ticket.id}
            )

        # Fallback to highest success rate playbooks
        return cls._fallback_match(severity_filtered)

    @classmethod
    def _normalize_priority(cls, priority: str) -> str:
        """Convert ticket priority to playbook severity level."""
        priority_map = {
            'LOW': 'LOW',
            'MEDIUM': 'MEDIUM',
            'HIGH': 'HIGH',
            'CRITICAL': 'CRITICAL'
        }
        return priority_map.get(priority, 'MEDIUM')

    @classmethod
    def _filter_by_severity(cls, playbooks: List, severity: str) -> List:
        """Filter playbooks by severity threshold."""
        severity_order = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        severity_level = severity_order.index(severity) if severity in severity_order else 1

        return [
            p for p in playbooks
            if severity_order.index(p.severity_threshold) <= severity_level
        ]

    @classmethod
    def _tfidf_match(cls, query_text: str, playbooks: List, tenant_id: int) -> List[Dict[str, Any]]:
        """
        Match using TF-IDF vectorization and cosine similarity.

        Args:
            query_text: Ticket description
            playbooks: List of ExecutablePlaybook instances
            tenant_id: Tenant ID for cache key

        Returns:
            Top 5 playbooks with confidence >0.3
        """
        cache_key = f"playbook_tfidf_vectors_{tenant_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            tfidf_matrix = cached_data['tfidf_matrix']
            vectorizer = cached_data['vectorizer']
            playbook_ids = cached_data['playbook_ids']
        else:
            # Build corpus from playbooks
            corpus = [
                f"{p.name} {p.description} {' '.join(p.finding_types)}"
                for p in playbooks
            ]

            # Compute TF-IDF
            vectorizer = TfidfVectorizer(
                max_features=300,
                stop_words='english',
                ngram_range=(1, 2)
            )
            tfidf_matrix = vectorizer.fit_transform(corpus)
            playbook_ids = [str(p.playbook_id) for p in playbooks]

            # Cache for 1 hour
            cache.set(cache_key, {
                'tfidf_matrix': tfidf_matrix,
                'vectorizer': vectorizer,
                'playbook_ids': playbook_ids
            }, cls.CACHE_TTL)

        # Vectorize query
        query_vector = vectorizer.transform([query_text])

        # Calculate cosine similarity
        similarities = cosine_similarity(query_vector, tfidf_matrix)[0]

        # Get top matches above threshold
        top_indices = np.argsort(similarities)[::-1][:cls.MAX_SUGGESTIONS]
        suggestions = []

        playbook_map = {str(p.playbook_id): p for p in playbooks}

        for idx in top_indices:
            confidence = float(similarities[idx])
            if confidence < cls.CONFIDENCE_THRESHOLD:
                continue

            playbook_id = playbook_ids[idx]
            playbook = playbook_map.get(playbook_id)
            if not playbook:
                continue

            suggestions.append({
                'playbook_id': playbook_id,
                'name': playbook.name,
                'confidence': round(confidence, 3),
                'auto_execute': playbook.auto_execute,
                'success_rate': playbook.success_rate,
                'description': playbook.description[:200]
            })

        logger.info(
            f"TF-IDF matched {len(suggestions)} playbooks",
            extra={'tenant': tenant_id}
        )

        return suggestions

    @classmethod
    def _fallback_match(cls, playbooks: List) -> List[Dict[str, Any]]:
        """
        Fallback: Return highest success rate playbooks.

        Args:
            playbooks: List of ExecutablePlaybook instances

        Returns:
            Top 5 playbooks by success rate
        """
        sorted_playbooks = sorted(
            playbooks,
            key=lambda p: (p.success_rate, p.total_executions),
            reverse=True
        )[:cls.MAX_SUGGESTIONS]

        suggestions = [
            {
                'playbook_id': str(p.playbook_id),
                'name': p.name,
                'confidence': 0.5,  # Medium confidence for fallback
                'auto_execute': p.auto_execute,
                'success_rate': p.success_rate,
                'description': p.description[:200]
            }
            for p in sorted_playbooks
        ]

        logger.info(f"Fallback matched {len(suggestions)} playbooks")

        return suggestions
