"""
Knowledge Base Suggester Service.

Suggests relevant help articles for tickets using TF-IDF similarity matching.
Part of Phase 3: AI & Intelligence Features.

Target: 70%+ relevant suggestion rate.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 50 lines
- Rule #11: Specific exception handling

@ontology(
    domain="helpdesk",
    purpose="Suggest relevant help articles for tickets using TF-IDF similarity",
    algorithm="TF-IDF + cosine similarity",
    business_value="Reduce ticket resolution time via knowledge base guidance",
    criticality="medium",
    tags=["helpdesk", "ml", "tfidf", "knowledge-base", "suggestions"]
)
"""

import logging
from typing import List, Dict, Any, Optional
from django.core.cache import cache
from django.db.models import Q
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, PARSING_EXCEPTIONS

logger = logging.getLogger('helpdesk.kb_suggester')

__all__ = ['KBSuggester']


class KBSuggester:
    """
    Suggest relevant help articles for tickets.

    Uses TF-IDF vectorization + cosine similarity to match tickets with
    published help articles based on title+description text.

    Features:
    - Redis caching of TF-IDF vectors (1 hour TTL)
    - Minimum confidence threshold (0.3)
    - Fallback to category matching if no good matches
    - Top 5 results with confidence scores
    """

    CONFIDENCE_THRESHOLD = 0.3
    CACHE_TTL = 3600  # 1 hour
    MAX_SUGGESTIONS = 5

    @classmethod
    def suggest_articles(cls, ticket, user=None) -> List[Dict[str, Any]]:
        """
        Suggest top 5 relevant help articles for a ticket.

        Args:
            ticket: Ticket instance
            user: Optional People instance for role-based filtering

        Returns:
            List of dicts: [
                {
                    'article_id': int,
                    'title': str,
                    'confidence': float,
                    'category': str,
                    'url': str
                },
                ...
            ]

        Raises:
            ValueError: If ticket is invalid
        """
        from apps.help_center.models.article import HelpArticle

        if not ticket or not ticket.ticketdesc:
            raise ValueError("Ticket must have description")

        query_text = f"{ticket.ticketdesc}"
        if hasattr(ticket, 'ticketcategory') and ticket.ticketcategory:
            query_text = f"{ticket.ticketcategory.name} {query_text}"

        # Get published articles for tenant
        articles_qs = HelpArticle.objects.filter(
            tenant=ticket.tenant,
            status='PUBLISHED'
        ).select_related('category')

        # Filter by role if user provided
        if user and hasattr(user, 'groups'):
            user_groups = list(user.groups.values_list('name', flat=True))
            articles_qs = articles_qs.filter(
                Q(target_roles__contains=user_groups) | Q(target_roles=[])
            )

        articles = list(articles_qs)
        if not articles:
            logger.warning(f"No published articles for tenant {ticket.tenant}")
            return []

        # Try TF-IDF matching first
        try:
            suggestions = cls._tfidf_match(query_text, articles, ticket.tenant.id)
            if suggestions:
                return suggestions
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error during TF-IDF matching: {e}",
                exc_info=True,
                extra={'ticket_id': ticket.id, 'tenant': ticket.tenant.id}
            )
        except (ValueError, AttributeError, KeyError) as e:
            logger.error(
                f"Data error during TF-IDF matching: {e}",
                exc_info=True,
                extra={'ticket_id': ticket.id}
            )

        # Fallback to category matching
        return cls._category_match(ticket, articles)

    @classmethod
    def _tfidf_match(cls, query_text: str, articles: List, tenant_id: int) -> List[Dict[str, Any]]:
        """
        Match using TF-IDF vectorization and cosine similarity.

        Args:
            query_text: Combined ticket text
            articles: List of HelpArticle instances
            tenant_id: Tenant ID for cache key

        Returns:
            Top 5 articles with confidence >0.3
        """
        cache_key = f"kb_tfidf_vectors_{tenant_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            tfidf_matrix = cached_data['tfidf_matrix']
            vectorizer = cached_data['vectorizer']
            article_ids = cached_data['article_ids']
        else:
            # Build corpus from articles
            corpus = [
                f"{a.title} {a.summary} {a.content}"
                for a in articles
            ]

            # Compute TF-IDF
            vectorizer = TfidfVectorizer(
                max_features=500,
                stop_words='english',
                ngram_range=(1, 2)
            )
            tfidf_matrix = vectorizer.fit_transform(corpus)
            article_ids = [a.id for a in articles]

            # Cache for 1 hour
            cache.set(cache_key, {
                'tfidf_matrix': tfidf_matrix,
                'vectorizer': vectorizer,
                'article_ids': article_ids
            }, cls.CACHE_TTL)

        # Vectorize query
        query_vector = vectorizer.transform([query_text])

        # Calculate cosine similarity
        similarities = cosine_similarity(query_vector, tfidf_matrix)[0]

        # Get top matches above threshold
        top_indices = np.argsort(similarities)[::-1][:cls.MAX_SUGGESTIONS]
        suggestions = []

        article_map = {a.id: a for a in articles}

        for idx in top_indices:
            confidence = float(similarities[idx])
            if confidence < cls.CONFIDENCE_THRESHOLD:
                continue

            article_id = article_ids[idx]
            article = article_map.get(article_id)
            if not article:
                continue

            suggestions.append({
                'article_id': article.id,
                'title': article.title,
                'confidence': round(confidence, 3),
                'category': article.category.name if article.category else 'General',
                'url': f"/help-center/articles/{article.slug}/"
            })

        logger.info(
            f"TF-IDF matched {len(suggestions)} articles",
            extra={'tenant': tenant_id, 'query_length': len(query_text)}
        )

        return suggestions

    @classmethod
    def _category_match(cls, ticket, articles: List) -> List[Dict[str, Any]]:
        """
        Fallback: Match by category + sort by popularity.

        Args:
            ticket: Ticket instance
            articles: List of HelpArticle instances

        Returns:
            Top 5 articles from same category, sorted by view count
        """
        category_name = getattr(ticket.ticketcategory, 'name', None) if hasattr(ticket, 'ticketcategory') else None

        if category_name:
            category_articles = [
                a for a in articles
                if a.category and category_name.lower() in a.category.name.lower()
            ]
        else:
            category_articles = articles

        # Sort by popularity
        sorted_articles = sorted(
            category_articles,
            key=lambda a: a.view_count,
            reverse=True
        )[:cls.MAX_SUGGESTIONS]

        suggestions = [
            {
                'article_id': a.id,
                'title': a.title,
                'confidence': 0.5,  # Medium confidence for category match
                'category': a.category.name if a.category else 'General',
                'url': f"/help-center/articles/{a.slug}/"
            }
            for a in sorted_articles
        ]

        logger.info(
            f"Category matched {len(suggestions)} articles",
            extra={'category': category_name}
        )

        return suggestions
