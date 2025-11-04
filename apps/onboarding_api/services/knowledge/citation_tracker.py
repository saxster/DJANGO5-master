"""
Citation Tracker with Knowledge Base Integration (Phase D).

Tracks and stores compliance citations with proper KB integration.
Ensures all site audit reports are ingested into knowledge base with:
- Structured citations
- Proper chunking
- Metadata tagging
- Retrieval optimization

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from django.core.cache import cache
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.site_onboarding.models import Observation
from apps.site_onboarding.models import OnboardingSite
from apps.onboarding_api.services.knowledge import get_knowledge_service
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


@dataclass
class CitationReference:
    """Citation reference for tracking."""
    citation_id: str
    observation_id: str
    standard: str
    section: str
    relevance_score: float
    context: str
    created_at: datetime


class CitationTracker:
    """
    Tracks compliance citations and integrates with knowledge base.

    Provides:
    - Citation storage and retrieval
    - Report ingestion into KB
    - Citation deduplication
    - Retrieval optimization
    """

    def __init__(self):
        """Initialize citation tracker with KB service."""
        self.knowledge_service = get_knowledge_service()
        self.citation_cache_timeout = 3600  # 1 hour

    def add_citation(
        self,
        observation_id: uuid.UUID,
        standard: str,
        section: str,
        context: str,
        relevance_score: float = 0.9,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CitationReference:
        """
        Add citation for an observation.

        Args:
            observation_id: UUID of observation
            standard: Standard name (RBI, ASIS, ISO27001)
            section: Section reference
            context: Citation context text
            relevance_score: Relevance score (0.0-1.0)
            metadata: Additional metadata

        Returns:
            CitationReference object
        """
        try:
            citation_id = str(uuid.uuid4())

            citation = CitationReference(
                citation_id=citation_id,
                observation_id=str(observation_id),
                standard=standard,
                section=section,
                relevance_score=relevance_score,
                context=context,
                created_at=datetime.now()
            )

            cache_key = f"citation_{observation_id}_{citation_id}"
            cache.set(cache_key, citation, timeout=self.citation_cache_timeout)

            logger.info(
                f"Added citation {citation_id} for observation {observation_id}",
                extra={
                    'citation_id': citation_id,
                    'observation_id': str(observation_id),
                    'standard': standard
                }
            )

            return citation

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to add citation: {str(e)}", exc_info=True)
            raise ValidationError(f"Invalid citation data: {str(e)}")

    def get_citations_for_observation(
        self,
        observation_id: uuid.UUID
    ) -> List[CitationReference]:
        """Get all citations for an observation."""
        citations = []

        cache_pattern = f"citation_{observation_id}_*"
        cache_keys = cache.keys(cache_pattern)

        for key in cache_keys:
            citation = cache.get(key)
            if citation:
                citations.append(citation)

        return citations

    def get_citations_for_report(
        self,
        site_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all citations for site audit report.

        Args:
            site_id: UUID of site

        Returns:
            List of citation dictionaries with:
            - standard, section, context
            - observation_id reference
            - relevance_score
            - grouped by standard
        """
        try:
            observations = Observation.objects.filter(
                site_id=site_id
            ).values_list('observation_id', flat=True)

            all_citations = []
            for obs_id in observations:
                citations = self.get_citations_for_observation(obs_id)
                all_citations.extend(citations)

            grouped_citations = self._group_citations_by_standard(all_citations)

            return grouped_citations

        except (ValueError, ValidationError) as e:
            logger.error(f"Failed to get citations for report: {str(e)}")
            return []

    def _group_citations_by_standard(
        self,
        citations: List[CitationReference]
    ) -> List[Dict[str, Any]]:
        """Group citations by standard for report generation."""
        grouped = {}

        for citation in citations:
            standard = citation.standard
            if standard not in grouped:
                grouped[standard] = {
                    'standard': standard,
                    'citations': [],
                    'count': 0
                }

            grouped[standard]['citations'].append({
                'section': citation.section,
                'context': citation.context,
                'relevance_score': citation.relevance_score,
                'observation_id': citation.observation_id
            })
            grouped[standard]['count'] += 1

        return list(grouped.values())

    def store_report_in_kb(
        self,
        site: OnboardingSite,
        report_content: str,
        citations: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store site audit report in knowledge base with citations.

        Uses add_document_with_chunking for proper indexing and retrieval.

        Args:
            site: OnboardingSite instance
            report_content: Full report text
            citations: List of citation dictionaries
            metadata: Additional metadata

        Returns:
            {
                'document_id': str,
                'chunks_created': int,
                'citations_stored': int,
                'success': bool
            }
        """
        result = {
            'document_id': None,
            'chunks_created': 0,
            'citations_stored': 0,
            'success': False,
            'error': None
        }

        try:
            with transaction.atomic(using=get_current_db_name()):
                enhanced_content = self._prepare_report_for_kb(
                    report_content,
                    citations
                )

                doc_metadata = {
                    'source': 'site_audit',
                    'site_id': str(site.site_id),
                    'business_unit': site.business_unit.buname,
                    'site_type': site.site_type,
                    'audit_completed_at': site.audit_completed_at.isoformat() if site.audit_completed_at else None,
                    'citation_count': len(citations),
                    'standards_cited': list(set(c['standard'] for c in citations)),
                    **(metadata or {})
                }

                kb_result = self.knowledge_service.add_document_with_chunking(
                    content=enhanced_content,
                    source_url=f"site_audit://{site.site_id}",
                    title=f"Site Audit: {site.business_unit.buname}",
                    metadata=doc_metadata
                )

                if kb_result.get('success'):
                    result['document_id'] = kb_result.get('document_id')
                    result['chunks_created'] = kb_result.get('chunks_created', 0)
                    result['citations_stored'] = len(citations)
                    result['success'] = True

                    site.knowledge_base_id = uuid.UUID(result['document_id'])
                    site.save(update_fields=['knowledge_base_id'])

                    logger.info(
                        f"Stored site audit report in KB: {result['document_id']}",
                        extra={
                            'site_id': str(site.site_id),
                            'chunks': result['chunks_created']
                        }
                    )
                else:
                    result['error'] = kb_result.get('error', 'Unknown error')
                    logger.error(f"Failed to store report in KB: {result['error']}")

        except (ValueError, ValidationError) as e:
            result['error'] = str(e)
            logger.error(f"Error storing report in KB: {str(e)}", exc_info=True)

        return result

    def _prepare_report_for_kb(
        self,
        report_content: str,
        citations: List[Dict[str, Any]]
    ) -> str:
        """Prepare report content for KB storage with citations."""
        enhanced_content = report_content

        if citations:
            citations_section = "\n\n## Compliance Citations\n\n"

            for citation_group in citations:
                standard = citation_group['standard']
                citations_section += f"\n### {standard}\n\n"

                for citation in citation_group['citations']:
                    citations_section += (
                        f"- **Section {citation['section']}**: {citation['context']}\n"
                        f"  *Relevance: {citation['relevance_score']:.2f}*\n\n"
                    )

            enhanced_content += citations_section

        return enhanced_content

    def deduplicate_citations(
        self,
        citations: List[CitationReference]
    ) -> List[CitationReference]:
        """
        Deduplicate citations based on standard + section.

        Keeps citation with highest relevance score.
        """
        seen = {}

        for citation in citations:
            key = f"{citation.standard}_{citation.section}"

            if key not in seen:
                seen[key] = citation
            else:
                if citation.relevance_score > seen[key].relevance_score:
                    seen[key] = citation

        return list(seen.values())

    def get_citation_statistics(
        self,
        site_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get citation statistics for site audit.

        Returns:
            {
                'total_citations': int,
                'by_standard': Dict[str, int],
                'average_relevance': float,
                'mandatory_requirements_count': int
            }
        """
        citations = self.get_citations_for_report(site_id)

        if not citations:
            return {
                'total_citations': 0,
                'by_standard': {},
                'average_relevance': 0.0,
                'mandatory_requirements_count': 0
            }

        total_citations = sum(c['count'] for c in citations)

        by_standard = {
            c['standard']: c['count']
            for c in citations
        }

        all_scores = [
            cit['relevance_score']
            for group in citations
            for cit in group['citations']
        ]

        average_relevance = sum(all_scores) / len(all_scores) if all_scores else 0.0

        return {
            'total_citations': total_citations,
            'by_standard': by_standard,
            'average_relevance': average_relevance,
            'mandatory_requirements_count': total_citations
        }

    def search_citations(
        self,
        query: str,
        standard: Optional[str] = None,
        min_relevance: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for citations matching query.

        Args:
            query: Search query
            standard: Optional standard filter
            min_relevance: Minimum relevance score

        Returns:
            List of matching citations
        """
        try:
            kb_results = self.knowledge_service.search(
                query=query,
                top_k=20,
                filters={'source': 'site_audit'}
            )

            if not kb_results.get('success'):
                return []

            results = kb_results.get('results', [])

            if standard:
                results = [
                    r for r in results
                    if r.get('metadata', {}).get('standards_cited', [])
                    and standard in r['metadata']['standards_cited']
                ]

            filtered_results = [
                r for r in results
                if r.get('score', 0.0) >= min_relevance
            ]

            return filtered_results

        except (ValueError, ValidationError) as e:
            logger.error(f"Citation search failed: {str(e)}")
            return []