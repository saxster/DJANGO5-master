"""
Unit Tests for RankingService

Tests ranking algorithm components
"""

import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from apps.search.services.ranking_service import RankingService


class TestRankingService:
    """Test ranking algorithm"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test service"""
        self.service = RankingService()

    def test_rank_results_by_score(self):
        """Test results are ranked by score"""

        results = [
            {'title': 'Low relevance', 'rank': 0.2},
            {'title': 'High relevance', 'rank': 0.9},
            {'title': 'Medium relevance', 'rank': 0.5},
        ]

        ranked = self.service.rank_results(results, 'test query')

        assert ranked[0]['title'] == 'High relevance'
        assert ranked[-1]['title'] == 'Low relevance'
        assert all('score' in r for r in ranked)

    def test_recency_boost_recent_items(self):
        """Test recent items get higher recency score"""

        recent_result = {
            'title': 'Recent item',
            'metadata': {
                'created_at': timezone.now().isoformat()
            }
        }

        old_result = {
            'title': 'Old item',
            'metadata': {
                'created_at': (timezone.now() - timedelta(days=400)).isoformat()
            }
        }

        recent_score = self.service._calculate_recency_boost(recent_result)
        old_score = self.service._calculate_recency_boost(old_result)

        assert recent_score > old_score

    def test_activity_boost_overdue_items(self):
        """Test overdue items get high activity score"""

        overdue_result = {
            'metadata': {'is_overdue': True}
        }

        normal_result = {
            'metadata': {'is_overdue': False}
        }

        overdue_score = self.service._calculate_activity_boost(overdue_result)
        normal_score = self.service._calculate_activity_boost(normal_result)

        assert overdue_score > normal_score

    def test_priority_affects_activity_score(self):
        """Test priority affects activity score"""

        high_priority = {
            'metadata': {'priority': 'HIGH'}
        }

        low_priority = {
            'metadata': {'priority': 'LOW'}
        }

        high_score = self.service._calculate_activity_boost(high_priority)
        low_score = self.service._calculate_activity_boost(low_priority)

        assert high_score > low_score

    def test_ownership_boost_own_items(self):
        """Test owned items get higher score"""

        owned = {
            'metadata': {'is_owner': True}
        }

        not_owned = {
            'metadata': {'is_owner': False}
        }

        owned_score = self.service._calculate_ownership_boost(owned)
        not_owned_score = self.service._calculate_ownership_boost(not_owned)

        assert owned_score > not_owned_score

    def test_trigram_similarity_exact_match(self):
        """Test trigram similarity for exact match"""

        score = self.service._calculate_trigram_similarity(
            'Test Title',
            'Test Title'
        )

        assert score == 1.0

    def test_trigram_similarity_partial_match(self):
        """Test trigram similarity for partial match"""

        score = self.service._calculate_trigram_similarity(
            'Test Title',
            'Title'
        )

        assert 0 < score < 1.0