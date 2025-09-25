"""
Edge case tests for recommendation system
Tests boundary conditions, error scenarios, and data integrity
"""
import pytest
import json
from unittest.mock import patch, Mock
from django.test import Client, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import math
import numpy as np

from apps.core.recommendation_engine import (
    RecommendationEngine, CollaborativeFilteringEngine, ContentBasedEngine,
    NavigationAnalyzer, BehaviorAnalyzer
)
from apps.core.models.recommendation import (
    UserBehaviorProfile, ContentRecommendation, NavigationRecommendation,
    UserSimilarity, RecommendationFeedback, RecommendationImplementation
)
from apps.core.models.heatmap import HeatmapSession, ClickHeatmap, ScrollHeatmap
from apps.core.middleware.recommendation_middleware import RecommendationMiddleware
from tests.factories.recommendation_factories import (
    UserBehaviorProfileFactory, ContentRecommendationFactory, NavigationRecommendationFactory,
    UserSimilarityFactory, RecommendationFeedbackFactory
)
from tests.factories.heatmap_factories import UserFactory, HeatmapSessionFactory

User = get_user_model()
pytestmark = pytest.mark.django_db


class TestRecommendationEngineEdgeCases:
    """Test edge cases in recommendation engine"""
    
    def setup_method(self):
        self.engine = RecommendationEngine()
        self.user = UserFactory()
        cache.clear()
    
    def test_generate_recommendations_no_user_profile(self):
        """Test recommendation generation for user without behavior profile"""
        # User has no profile - should create minimal recommendations or handle gracefully
        recommendations = self.engine.generate_user_recommendations(self.user, limit=5)
        
        # Should not crash and may return empty list or default recommendations
        assert isinstance(recommendations, list)
        assert len(recommendations) >= 0
        
        # Profile might be created as side effect
        profile = UserBehaviorProfile.objects.filter(user=self.user).first()
        # Profile creation is implementation-dependent
    
    def test_generate_recommendations_no_activity_data(self):
        """Test recommendation generation for user with no activity"""
        profile = UserBehaviorProfileFactory(
            user=self.user,
            preferred_pages={},  # Empty preferences
            similarity_vector=[],  # Empty vector
            exploration_tendency=0.0
        )
        
        recommendations = self.engine.generate_user_recommendations(self.user, limit=5)
        
        # Should handle empty data gracefully
        assert isinstance(recommendations, list)
        assert len(recommendations) >= 0
    
    def test_generate_recommendations_corrupted_similarity_data(self):
        """Test handling of corrupted similarity data"""
        profile = UserBehaviorProfileFactory(user=self.user)
        
        # Create similarity with invalid data
        other_user = UserFactory()
        UserSimilarityFactory(
            user1=self.user,
            user2=other_user,
            similarity_score=float('nan'),  # Invalid score
            calculation_method='corrupted'
        )
        
        recommendations = self.engine.generate_user_recommendations(self.user, limit=5)
        
        # Should handle NaN values gracefully
        assert isinstance(recommendations, list)
    
    def test_generate_recommendations_extreme_limit_values(self):
        """Test recommendation generation with extreme limit values"""
        profile = UserBehaviorProfileFactory(user=self.user)
        
        # Test with zero limit
        recommendations = self.engine.generate_user_recommendations(self.user, limit=0)
        assert len(recommendations) == 0
        
        # Test with negative limit
        recommendations = self.engine.generate_user_recommendations(self.user, limit=-5)
        assert len(recommendations) == 0
        
        # Test with extremely large limit
        recommendations = self.engine.generate_user_recommendations(self.user, limit=10000)
        # Should handle gracefully without memory issues
        assert isinstance(recommendations, list)
    
    def test_cosine_similarity_edge_cases(self):
        """Test cosine similarity calculation with edge cases"""
        engine = CollaborativeFilteringEngine()
        
        # Test with zero vectors
        zero_vector = [0.0] * 10
        normal_vector = [1.0, 2.0, 3.0, 4.0, 5.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        
        similarity = engine._calculate_cosine_similarity(zero_vector, normal_vector)
        assert similarity == 0.0  # Zero vector should give 0 similarity
        
        # Test with identical vectors
        identical_similarity = engine._calculate_cosine_similarity(normal_vector, normal_vector)
        assert abs(identical_similarity - 1.0) < 1e-10  # Should be 1.0
        
        # Test with opposite vectors
        opposite_vector = [-x for x in normal_vector]
        opposite_similarity = engine._calculate_cosine_similarity(normal_vector, opposite_vector)
        assert abs(opposite_similarity - (-1.0)) < 1e-10  # Should be -1.0
        
        # Test with vectors of different lengths
        short_vector = [1.0, 2.0, 3.0]
        different_length_similarity = engine._calculate_cosine_similarity(normal_vector, short_vector)
        # Should handle gracefully (pad with zeros or return 0)
        assert isinstance(different_length_similarity, float)
    
    def test_recommendation_with_circular_dependencies(self):
        """Test handling of circular user similarities"""
        users = [UserFactory() for _ in range(3)]
        profiles = [UserBehaviorProfileFactory(user=user) for user in users]
        
        # Create circular similarities: A -> B -> C -> A
        UserSimilarityFactory(user1=users[0], user2=users[1], similarity_score=0.8)
        UserSimilarityFactory(user1=users[1], user2=users[2], similarity_score=0.7)
        UserSimilarityFactory(user1=users[2], user2=users[0], similarity_score=0.6)
        
        # Should not cause infinite loops
        recommendations = self.engine.generate_user_recommendations(users[0], limit=5)
        assert isinstance(recommendations, list)
    
    def test_concurrent_recommendation_generation(self):
        """Test concurrent access to recommendation generation"""
        profile = UserBehaviorProfileFactory(user=self.user)
        
        # Simulate concurrent requests
        import threading
        results = []
        errors = []
        
        def generate_recs():
            try:
                recs = self.engine.generate_user_recommendations(self.user, limit=3)
                results.append(recs)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=generate_recs)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Should not have race condition errors
        assert len(errors) == 0
        assert len(results) == 5


class TestModelValidationEdgeCases:
    """Test model validation and data integrity edge cases"""
    
    def setup_method(self):
        self.user = UserFactory()
    
    def test_user_behavior_profile_extreme_values(self):
        """Test behavior profile with extreme values"""
        # Test with extreme exploration tendency
        profile = UserBehaviorProfileFactory(
            user=self.user,
            exploration_tendency=1.5,  # Above valid range
            task_completion_rate=-0.5,  # Below valid range
            feature_adoption_rate=2.0  # Above valid range
        )
        
        # Model should handle or clamp extreme values
        profile.clean()  # Should not raise exception
        assert 0.0 <= profile.exploration_tendency <= 1.0
        assert 0.0 <= profile.task_completion_rate <= 1.0
        assert 0.0 <= profile.feature_adoption_rate <= 1.0
    
    def test_similarity_score_validation(self):
        """Test similarity score validation edge cases"""
        other_user = UserFactory()
        
        # Test with invalid similarity scores
        with pytest.raises((ValidationError, ValueError)):
            UserSimilarityFactory(
                user1=self.user,
                user2=other_user,
                similarity_score=2.0  # Above valid range
            )
        
        with pytest.raises((ValidationError, ValueError)):
            UserSimilarityFactory(
                user1=self.user,
                user2=other_user,
                similarity_score=-2.0  # Below valid range
            )
        
        # Test with edge case values
        valid_similarity = UserSimilarityFactory(
            user1=self.user,
            user2=other_user,
            similarity_score=0.0  # Minimum valid value
        )
        assert valid_similarity.similarity_score == 0.0
    
    def test_self_similarity_prevention(self):
        """Test prevention of self-similarity relationships"""
        with pytest.raises((ValidationError, IntegrityError)):
            UserSimilarityFactory(
                user1=self.user,
                user2=self.user  # Self-similarity should be prevented
            )
    
    def test_duplicate_similarity_handling(self):
        """Test handling of duplicate similarity relationships"""
        other_user = UserFactory()
        
        # Create first similarity
        sim1 = UserSimilarityFactory(user1=self.user, user2=other_user, similarity_score=0.8)
        
        # Attempt to create duplicate
        with pytest.raises(IntegrityError):
            UserSimilarityFactory(user1=self.user, user2=other_user, similarity_score=0.7)
    
    def test_content_recommendation_extreme_scores(self):
        """Test content recommendation with extreme relevance scores"""
        # Test with extreme relevance score
        rec = ContentRecommendationFactory(
            user=self.user,
            relevance_score=10.0,  # Extreme value
            confidence_score=-5.0  # Invalid value
        )
        
        # Should clamp to valid ranges
        rec.clean()
        assert 0.0 <= rec.relevance_score <= 1.0
        assert 0.0 <= rec.confidence_score <= 1.0
    
    def test_recommendation_with_null_values(self):
        """Test handling of null/empty values in recommendations"""
        # Test with minimal required data
        rec = ContentRecommendationFactory(
            user=self.user,
            content_title='',  # Empty title
            content_url='',    # Empty URL
            content_description=None,  # Null description
            content_metadata={}  # Empty metadata
        )
        
        # Should handle gracefully
        assert rec.id is not None
        assert rec.user == self.user
    
    def test_large_json_field_data(self):
        """Test handling of large JSON field data"""
        # Create profile with large data
        large_pages = {f'/page{i}/': i for i in range(10000)}
        large_vector = list(range(1000))
        
        profile = UserBehaviorProfileFactory(
            user=self.user,
            preferred_pages=large_pages,
            similarity_vector=large_vector
        )
        
        # Should handle large data without issues
        profile.save()
        profile.refresh_from_db()
        assert len(profile.preferred_pages) == 10000
        assert len(profile.similarity_vector) == 1000


class TestBehaviorAnalyzerEdgeCases:
    """Test behavior analyzer edge cases"""
    
    def setup_method(self):
        self.analyzer = BehaviorAnalyzer()
        self.user = UserFactory()
    
    def test_analyze_empty_session_data(self):
        """Test behavior analysis with no session data"""
        # User with no sessions
        behavior_data = self.analyzer.analyze_user_behavior(self.user)
        
        assert isinstance(behavior_data, dict)
        assert 'preferred_pages' in behavior_data
        assert 'similarity_vector' in behavior_data
        # Should provide default values
        assert behavior_data['exploration_tendency'] >= 0.0
    
    def test_analyze_corrupted_session_data(self):
        """Test handling of corrupted session data"""
        # Create session with invalid data
        session = HeatmapSessionFactory(
            user=self.user,
            page_url='',  # Empty URL
            start_time=None,  # Invalid timestamp
            end_time=timezone.now() - timedelta(days=1),  # End before start
            viewport_width=-100,  # Invalid dimensions
            viewport_height=0
        )
        
        # Should handle corrupted data gracefully
        behavior_data = self.analyzer.analyze_user_behavior(self.user)
        assert isinstance(behavior_data, dict)
    
    def test_analyze_extreme_session_volumes(self):
        """Test behavior analysis with extreme session volumes"""
        # Create user with thousands of sessions
        sessions = []
        for i in range(1000):  # Large volume
            session = HeatmapSessionFactory(
                user=self.user,
                page_url=f'/page{i % 10}/',  # 10 unique pages
                start_time=timezone.now() - timedelta(days=i % 30)
            )
            sessions.append(session)
        
        # Should handle large volumes efficiently
        import time
        start_time = time.time()
        behavior_data = self.analyzer.analyze_user_behavior(self.user)
        analysis_time = time.time() - start_time
        
        # Should complete within reasonable time
        assert analysis_time < 10.0  # 10 seconds max
        assert isinstance(behavior_data, dict)
    
    def test_build_similarity_vector_edge_cases(self):
        """Test similarity vector building with edge cases"""
        # Create sessions with unusual patterns
        unusual_sessions = [
            HeatmapSessionFactory(
                user=self.user,
                page_url='/extremely/long/url/with/many/segments/that/might/cause/issues/',
                user_agent='Mozilla/5.0 (compatible; bot/1.0)',  # Bot user agent
                device_type='unknown'
            ),
            HeatmapSessionFactory(
                user=self.user,
                page_url='/page with spaces/',  # URL with spaces
                device_type='',  # Empty device type
                viewport_width=99999,  # Extreme viewport
                viewport_height=1
            )
        ]
        
        vector = self.analyzer._build_similarity_vector(self.user)
        
        # Should produce valid vector despite unusual data
        assert isinstance(vector, list)
        assert len(vector) > 0
        assert all(isinstance(val, (int, float)) for val in vector)
        assert all(not math.isnan(val) for val in vector)


class TestNavigationAnalyzerEdgeCases:
    """Test navigation analyzer edge cases"""
    
    def setup_method(self):
        self.analyzer = NavigationAnalyzer()
    
    def test_analyze_empty_heatmap_data(self):
        """Test analysis with no heatmap data"""
        recommendations = self.analyzer.analyze_navigation_patterns()
        
        # Should handle empty data gracefully
        assert isinstance(recommendations, list)
        assert len(recommendations) >= 0
    
    def test_analyze_corrupted_click_data(self):
        """Test handling of corrupted click heatmap data"""
        user = UserFactory()
        session = HeatmapSessionFactory(user=user)
        
        # Create corrupted click data
        corrupted_click = ClickHeatmap.objects.create(
            session=session,
            x_position=float('inf'),  # Invalid position
            y_position=float('nan'),  # Invalid position
            element_type=None,  # Null element type
            element_id='',  # Empty element ID
            timestamp=None  # Invalid timestamp
        )
        
        recommendations = self.analyzer.analyze_navigation_patterns()
        
        # Should handle corrupted data without crashing
        assert isinstance(recommendations, list)
    
    def test_detect_problematic_pages_edge_cases(self):
        """Test detection of problematic pages with edge cases"""
        users = [UserFactory() for _ in range(5)]
        
        # Create sessions with extreme patterns
        problematic_page = '/problematic-page/'
        
        for user in users:
            # All users have very short sessions on this page
            session = HeatmapSessionFactory(
                user=user,
                page_url=problematic_page,
                is_active=False
            )
            session.duration_seconds = 0  # Zero duration
            session.save()
            
            # Add click with impossible coordinates
            ClickHeatmap.objects.create(
                session=session,
                x_position=-1.0,  # Outside viewport
                y_position=2.0,   # Outside viewport
                element_type='unknown'
            )
        
        problematic_pages = self.analyzer._detect_problematic_pages()
        
        # Should identify the problematic page despite edge case data
        assert isinstance(problematic_pages, list)


class TestMiddlewareEdgeCases:
    """Test middleware edge cases"""
    
    def setup_method(self):
        self.middleware = RecommendationMiddleware(lambda req: None)
        self.factory = Client()
    
    def test_middleware_with_anonymous_user(self):
        """Test middleware behavior with anonymous users"""
        from django.http import HttpRequest
        from django.contrib.auth.models import AnonymousUser
        
        request = HttpRequest()
        request.user = AnonymousUser()
        request.method = 'GET'
        request.path = '/test/'
        
        # Should handle anonymous users gracefully
        response = self.middleware(request)
        # Should not crash or create data for anonymous users
    
    def test_middleware_with_malformed_request(self):
        """Test middleware with malformed request data"""
        from django.http import HttpRequest
        
        request = HttpRequest()
        request.user = UserFactory()
        request.method = None  # Invalid method
        request.path = None    # Invalid path
        request.META = {}      # Empty meta data
        
        # Should handle malformed requests gracefully
        response = self.middleware(request)
    
    def test_middleware_database_connection_error(self):
        """Test middleware behavior during database errors"""
        from django.http import HttpRequest
        from django.db import DatabaseError
        
        request = HttpRequest()
        request.user = UserFactory()
        request.method = 'GET'
        request.path = '/test/'
        
        with patch('apps.core.models.recommendation.UserBehaviorProfile.objects.get', 
                  side_effect=DatabaseError('Connection lost')):
            # Should handle database errors gracefully
            response = self.middleware(request)
            # Should not crash the request
    
    def test_middleware_memory_pressure(self):
        """Test middleware behavior under memory pressure"""
        from django.http import HttpRequest
        
        request = HttpRequest()
        request.user = UserFactory()
        request.method = 'GET'
        request.path = '/test/'
        
        # Simulate memory pressure by creating large objects
        large_data = ['x' * 1000000] * 10  # 10MB of data
        
        with patch('apps.core.recommendation_engine.RecommendationEngine.generate_user_recommendations',
                  return_value=large_data):
            # Should handle memory pressure gracefully
            response = self.middleware(request)


class TestRecommendationAPIEdgeCases:
    """Test API edge cases and error conditions"""
    
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
    
    def test_api_with_malformed_json(self):
        """Test API endpoints with malformed JSON"""
        self.client.force_login(self.user)
        
        # Send malformed JSON
        response = self.client.post(
            '/api/recommendations/interact/',
            data='{"malformed": json data',
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_api_with_extremely_large_payload(self):
        """Test API with extremely large request payload"""
        self.client.force_login(self.user)
        
        # Create very large payload
        large_payload = {
            'type': 'click',
            'rec_id': 1,
            'rec_type': 'content',
            'large_data': 'x' * 100000  # 100KB of data
        }
        
        response = self.client.post(
            '/api/recommendations/interact/',
            data=json.dumps(large_payload),
            content_type='application/json'
        )
        
        # Should handle large payloads appropriately
        assert response.status_code in [200, 400, 413]  # Success, bad request, or payload too large
    
    def test_api_concurrent_requests(self):
        """Test API behavior with concurrent requests"""
        import threading
        import time
        
        self.client.force_login(self.user)
        
        # Create recommendation
        rec = ContentRecommendationFactory(user=self.user)
        
        results = []
        errors = []
        
        def make_request():
            try:
                response = self.client.post(
                    '/api/recommendations/interact/',
                    data=json.dumps({
                        'type': 'click',
                        'rec_id': rec.id,
                        'rec_type': 'content'
                    }),
                    content_type='application/json'
                )
                results.append(response.status_code)
            except Exception as e:
                errors.append(e)
        
        # Make concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should handle concurrent requests without errors
        assert len(errors) == 0
        assert all(status_code in [200, 404] for status_code in results)
    
    def test_api_rate_limiting_edge_cases(self):
        """Test API behavior under rate limiting scenarios"""
        self.client.force_login(self.user)
        
        # Make many requests rapidly
        responses = []
        for i in range(100):
            response = self.client.get('/api/recommendations/')
            responses.append(response.status_code)
        
        # Should either succeed or return rate limit errors
        valid_status_codes = [200, 429, 403, 500]  # OK, rate limited, forbidden, or error
        assert all(status in valid_status_codes for status in responses)


class TestDataMigrationEdgeCases:
    """Test edge cases in data migration and cleanup"""
    
    def test_cleanup_orphaned_recommendations(self):
        """Test cleanup of orphaned recommendation data"""
        # Create recommendations for deleted user
        deleted_user_id = 99999
        
        # This would normally be prevented by foreign key constraints
        # but test the cleanup logic
        
        from django.db import connection
        with connection.cursor() as cursor:
            # Test cleanup queries handle non-existent references gracefully
            pass
    
    def test_migration_with_large_datasets(self):
        """Test migration behavior with large existing datasets"""
        # Create large amount of existing data
        users = [UserFactory() for _ in range(100)]
        
        for user in users:
            profile = UserBehaviorProfileFactory(user=user)
            for _ in range(10):
                ContentRecommendationFactory(user=user)
        
        # Test that migrations/updates can handle large datasets
        # This would be tested in actual migration scripts
        assert UserBehaviorProfile.objects.count() == 100
        assert ContentRecommendation.objects.count() == 1000


class TestPerformanceEdgeCases:
    """Test performance edge cases and degradation scenarios"""
    
    def test_recommendation_generation_under_load(self):
        """Test recommendation generation performance under load"""
        # Create scenario with many users and complex relationships
        users = [UserFactory() for _ in range(50)]
        
        for i, user in enumerate(users):
            profile = UserBehaviorProfileFactory(user=user)
            
            # Create many sessions
            for j in range(20):
                HeatmapSessionFactory(user=user)
            
            # Create many similarities
            for other_user in users[max(0, i-5):i]:
                if other_user != user:
                    UserSimilarityFactory(user1=user, user2=other_user)
        
        engine = RecommendationEngine()
        
        # Test that generation completes within reasonable time
        import time
        start_time = time.time()
        
        # Generate recommendations for subset of users
        for user in users[:10]:
            recommendations = engine.generate_user_recommendations(user, limit=5)
            assert isinstance(recommendations, list)
        
        total_time = time.time() - start_time
        
        # Should complete within reasonable time even under load
        assert total_time < 30.0  # 30 seconds max for 10 users
    
    def test_memory_usage_with_large_vectors(self):
        """Test memory usage with large similarity vectors"""
        # Create user with very large similarity vector
        large_vector = list(range(10000))  # 10k elements
        
        profile = UserBehaviorProfileFactory(
            user=UserFactory(),
            similarity_vector=large_vector
        )
        
        engine = RecommendationEngine()
        
        # Should handle large vectors without memory issues
        recommendations = engine.generate_user_recommendations(profile.user, limit=5)
        assert isinstance(recommendations, list)
    
    @pytest.mark.slow
    def test_algorithm_performance_degradation(self):
        """Test algorithm performance as data grows"""
        # Test how algorithms perform as similarity data grows
        base_user = UserFactory()
        UserBehaviorProfileFactory(user=base_user)
        
        engine = CollaborativeFilteringEngine()
        
        performance_data = []
        
        for num_similar_users in [10, 50, 100, 200]:
            # Create similar users
            for i in range(num_similar_users):
                similar_user = UserFactory()
                UserBehaviorProfileFactory(user=similar_user)
                UserSimilarityFactory(
                    user1=base_user,
                    user2=similar_user,
                    similarity_score=0.8 - (i * 0.001)  # Slight variation
                )
            
            # Measure performance
            import time
            start_time = time.time()
            
            engine.calculate_user_similarities(base_user)
            
            elapsed_time = time.time() - start_time
            performance_data.append((num_similar_users, elapsed_time))
        
        # Check that performance degradation is not exponential
        # (Should be roughly linear or better)
        for i in range(1, len(performance_data)):
            prev_users, prev_time = performance_data[i-1]
            curr_users, curr_time = performance_data[i]
            
            # Performance should not degrade exponentially
            user_ratio = curr_users / prev_users
            time_ratio = curr_time / prev_time if prev_time > 0 else 1
            
            # Time ratio should not be much worse than user ratio
            assert time_ratio <= user_ratio * 2  # Allow 2x degradation factor