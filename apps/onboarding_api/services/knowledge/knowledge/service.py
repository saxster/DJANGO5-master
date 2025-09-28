import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from django.db.models import Q

from apps.onboarding.models import AuthoritativeKnowledge
from ..base import VectorStore

logger = logging.getLogger(__name__)


class KnowledgeService:
    """
    Service for managing authoritative knowledge and performing semantic search
    """

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.model = AuthoritativeKnowledge

    def add_knowledge(self, source_org: str, title: str, content_summary: str,
                     authority_level: str = 'medium', version: str = '',
                     publication_date: Optional[datetime] = None) -> str:
        """Add new knowledge item"""
        knowledge = self.model.objects.create(
            source_organization=source_org,
            document_title=title,
            document_version=version,
            authority_level=authority_level,
            content_summary=content_summary,
            publication_date=publication_date or datetime.now(),
            is_current=True
        )

        logger.info(f"Added knowledge: {title} from {source_org}")
        return str(knowledge.knowledge_id)

    def update_knowledge_vector(self, knowledge_id: str, vector: List[float]) -> bool:
        """Update vector embedding for knowledge item"""
        return self.vector_store.store_embedding(
            knowledge_id, vector, {'updated_at': datetime.now().isoformat()}
        )

    def search_knowledge(self, query: str, top_k: int = 5, authority_filter: Optional[List[str]] = None) -> List[Dict]:
        """Search knowledge using text query"""
        query_filters = Q(content_summary__icontains=query) | Q(document_title__icontains=query)

        if authority_filter:
            query_filters &= Q(authority_level__in=authority_filter)

        knowledge_items = self.model.objects.filter(
            query_filters,
            is_current=True
        ).order_by('-authority_level', '-publication_date')[:top_k]

        results = []
        for knowledge in knowledge_items:
            results.append({
                'knowledge_id': str(knowledge.knowledge_id),
                'source_organization': knowledge.source_organization,
                'document_title': knowledge.document_title,
                'authority_level': knowledge.authority_level,
                'content_summary': knowledge.content_summary,
                'publication_date': knowledge.publication_date.isoformat(),
                'relevance_score': self._calculate_text_relevance(query, knowledge.content_summary)
            })

        return results

    def search_similar_knowledge(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict]:
        """Search knowledge using vector similarity"""
        return self.vector_store.search_similar(query_vector, top_k, threshold)

    def get_authoritative_sources(self, topic: str, authority_level: str = 'high') -> List[Dict]:
        """Get authoritative sources for a specific topic"""
        authority_levels = ['high', 'official'] if authority_level == 'high' else [authority_level]

        sources = self.model.objects.filter(
            Q(content_summary__icontains=topic) | Q(document_title__icontains=topic),
            authority_level__in=authority_levels,
            is_current=True
        ).order_by('-authority_level', '-publication_date')

        return [
            {
                'knowledge_id': str(source.knowledge_id),
                'source_organization': source.source_organization,
                'document_title': source.document_title,
                'authority_level': source.authority_level,
                'content_summary': source.content_summary[:200] + '...' if len(source.content_summary) > 200 else source.content_summary,
                'publication_date': source.publication_date.isoformat()
            }
            for source in sources[:10]
        ]

    def validate_recommendation_against_knowledge(self, recommendation: Dict, context: Dict) -> Dict:
        """Validate a recommendation against authoritative knowledge"""
        validation_result = {
            'is_valid': True,
            'confidence_score': 0.8,
            'supporting_sources': [],
            'potential_conflicts': [],
            'recommendations': []
        }

        topics = self._extract_topics_from_recommendation(recommendation)

        for topic in topics:
            sources = self.get_authoritative_sources(topic, 'high')

            if sources:
                validation_result['supporting_sources'].extend(sources[:2])

            potential_conflicts = self._check_for_conflicts(recommendation, sources)
            validation_result['potential_conflicts'].extend(potential_conflicts)

        if validation_result['potential_conflicts']:
            validation_result['confidence_score'] *= 0.7
            validation_result['is_valid'] = False

        return validation_result

    def get_knowledge_stats(self) -> Dict:
        """Get comprehensive knowledge base statistics"""
        base_stats = self.vector_store.get_embedding_stats()

        authority_breakdown = {}
        for level in ['low', 'medium', 'high', 'official']:
            count = self.model.objects.filter(authority_level=level, is_current=True).count()
            authority_breakdown[level] = count

        recent_additions = self.model.objects.filter(
            cdtz__gte=datetime.now() - timedelta(days=30),
            is_current=True
        ).count()

        base_stats.update({
            'authority_level_breakdown': authority_breakdown,
            'recent_additions_30_days': recent_additions,
        })

        return base_stats

    def _calculate_text_relevance(self, query: str, content: str) -> float:
        """Simple text relevance calculation"""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        intersection = query_words.intersection(content_words)
        return len(intersection) / len(query_words)

    def _extract_topics_from_recommendation(self, recommendation: Dict) -> List[str]:
        """Extract key topics from recommendation for validation"""
        topics = []

        if 'business_unit_config' in recommendation:
            topics.append('business unit')
            bu_config = recommendation['business_unit_config']
            if 'bu_type' in bu_config:
                topics.append(bu_config['bu_type'].lower())

        if 'security_settings' in recommendation:
            topics.extend(['security', 'authentication', 'access control'])

        if 'suggested_shifts' in recommendation:
            topics.extend(['shift management', 'scheduling'])

        return topics

    def _check_for_conflicts(self, recommendation: Dict, sources: List[Dict]) -> List[Dict]:
        """Check for potential conflicts between recommendation and sources"""
        conflicts = []

        for source in sources:
            if 'security' in source['content_summary'].lower():
                if recommendation.get('security_settings', {}).get('enable_gps', False):
                    if 'gps not recommended' in source['content_summary'].lower():
                        conflicts.append({
                            'type': 'policy_conflict',
                            'source': source['document_title'],
                            'description': 'Recommendation enables GPS but source advises against it'
                        })

        return conflicts