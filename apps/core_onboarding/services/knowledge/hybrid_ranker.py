"""
Hybrid Search Ranking

Combines semantic (vector) and text (BM25) search with configurable weights.

Ranking Methods:
1. Reciprocal Rank Fusion (RRF)
2. Weighted linear combination
3. Authority-boosted ranking

Following CLAUDE.md:
- Rule #7: <150 lines
- Configurable weighting

Sprint 9.3: Semantic Search Enhancements
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class HybridRanker:
    """Combine semantic and text search with configurable ranking."""

    def __init__(self, alpha: float = 0.6):
        """
        Initialize hybrid ranker.

        Args:
            alpha: Weight for semantic search (0-1)
                   0.0 = pure text search
                   0.5 = equal weighting
                   1.0 = pure semantic search
        """
        self.alpha = max(0.0, min(1.0, alpha))  # Clamp to [0,1]

    def reciprocal_rank_fusion(
        self,
        semantic_results: List[Dict],
        text_results: List[Dict],
        k: int = 60
    ) -> List[Dict]:
        """
        Merge results using Reciprocal Rank Fusion.

        Args:
            semantic_results: Semantic search results (ordered)
            text_results: Text search results (ordered)
            k: RRF constant (default: 60)

        Returns:
            Merged and re-ranked results
        """
        # Build RRF scores
        rrf_scores = {}

        # Add semantic results
        for rank, result in enumerate(semantic_results, start=1):
            doc_id = result.get('knowledge_id', result.get('chunk_id'))
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (1 / (k + rank))
            if doc_id not in {r.get('knowledge_id', r.get('chunk_id')) for r in rrf_scores.get('_results', [])}:
                rrf_scores.setdefault('_results', {})[doc_id] = result

        # Add text results
        for rank, result in enumerate(text_results, start=1):
            doc_id = result.get('knowledge_id', result.get('chunk_id'))
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (1 / (k + rank))
            if doc_id not in rrf_scores.get('_results', {}):
                rrf_scores.setdefault('_results', {})[doc_id] = result

        # Sort by RRF score and return results
        results_dict = rrf_scores.pop('_results', {})
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        merged_results = []
        for doc_id in sorted_ids:
            result = results_dict.get(doc_id)
            if result:
                result['rrf_score'] = rrf_scores[doc_id]
                merged_results.append(result)

        logger.info(f"RRF merged {len(merged_results)} results from {len(semantic_results)}+{len(text_results)} inputs")

        return merged_results

    def weighted_combination(
        self,
        semantic_results: List[Dict],
        text_results: List[Dict]
    ) -> List[Dict]:
        """
        Merge using weighted linear combination.

        Formula: score = alpha * semantic_score + (1-alpha) * text_score

        Returns:
            Merged results with combined scores
        """
        combined = {}

        # Normalize and combine semantic results
        for result in semantic_results:
            doc_id = result.get('knowledge_id', result.get('chunk_id'))
            semantic_score = result.get('similarity_score', result.get('relevance_score', 0.0))
            combined[doc_id] = {
                'result': result,
                'semantic_score': semantic_score,
                'text_score': 0.0
            }

        # Add text results
        for result in text_results:
            doc_id = result.get('knowledge_id', result.get('chunk_id'))
            text_score = result.get('relevance_score', result.get('score', 0.0))

            if doc_id in combined:
                combined[doc_id]['text_score'] = text_score
            else:
                combined[doc_id] = {
                    'result': result,
                    'semantic_score': 0.0,
                    'text_score': text_score
                }

        # Calculate combined scores
        for doc_id, data in combined.items():
            combined_score = (
                self.alpha * data['semantic_score'] +
                (1 - self.alpha) * data['text_score']
            )
            data['result']['combined_score'] = combined_score

        # Sort by combined score
        sorted_results = sorted(
            [data['result'] for data in combined.values()],
            key=lambda x: x['combined_score'],
            reverse=True
        )

        logger.info(
            f"Weighted combination (alpha={self.alpha}) merged {len(sorted_results)} results"
        )

        return sorted_results

    def authority_boost(self, results: List[Dict], boost_weights: Dict[str, float] = None) -> List[Dict]:
        """
        Boost ranking based on authority level.

        Args:
            results: Search results
            boost_weights: Authority level weights

        Returns:
            Results with authority-boosted scores
        """
        if boost_weights is None:
            from django.conf import settings
            boost_weights = getattr(settings, 'KB_AUTHORITY_WEIGHTS', {
                'official': 1.0,
                'high': 0.9,
                'medium': 0.7,
                'low': 0.5
            })

        for result in results:
            authority = result.get('metadata', {}).get('authority_level', 'medium')
            boost = boost_weights.get(authority, 0.7)

            # Apply boost to existing score
            current_score = result.get('combined_score', result.get('similarity_score', 0.5))
            result['boosted_score'] = current_score * boost
            result['authority_boost'] = boost

        # Re-sort by boosted score
        results.sort(key=lambda x: x.get('boosted_score', 0), reverse=True)

        return results


# Singleton instance
hybrid_ranker = HybridRanker(alpha=0.6)


def get_hybrid_ranker(alpha: float = None) -> HybridRanker:
    """Get hybrid ranker instance."""
    if alpha is not None:
        return HybridRanker(alpha)
    return hybrid_ranker
