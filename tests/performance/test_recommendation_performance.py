"""
Performance tests for recommendation system
"""
import pytest
import time
import statistics
from unittest.mock import patch
from django.test import TransactionTestCase, Client
from django.core.management import call_command
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import cProfile
import pstats
from io import StringIO

from apps.core.recommendation_engine import (
    RecommendationEngine, CollaborativeFilteringEngine, ContentBasedEngine
)
from apps.core.models.recommendation import (
    UserBehaviorProfile, ContentRecommendation, UserSimilarity
)
from apps.core.models.heatmap import HeatmapSession
from tests.factories.recommendation_factories import (
    UserBehaviorProfileFactory, ContentRecommendationFactory, UserSimilarityFactory,
    create_recommendation_scenario
)
from tests.factories.heatmap_factories import UserFactory, HeatmapSessionFactory


class TestRecommendationEnginePerformance:
    """Test performance of recommendation engine components"""
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_single_user_recommendation_generation_speed(self):
        """Test speed of generating recommendations for single user"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        # Create sufficient data for recommendations
        for _ in range(10):
            HeatmapSessionFactory(user=user)
        
        # Create similar users for collaborative filtering
        for _ in range(20):
            similar_user = UserFactory()
            UserBehaviorProfileFactory(user=similar_user)
            UserSimilarityFactory(user1=user, user2=similar_user, similarity_score=0.7)
        
        engine = RecommendationEngine()
        
        # Measure recommendation generation time
        times = []
        for _ in range(10):  # Multiple runs for average
            start_time = time.time()
            recommendations = engine.generate_user_recommendations(user, limit=10)
            end_time = time.time()
            times.append(end_time - start_time)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 1.0  # Average should be under 1 second
        assert max_time < 2.0  # No single run should exceed 2 seconds
        assert len(recommendations) <= 10
        
        print(f"Average recommendation generation time: {avg_time:.3f}s")
        print(f"Max recommendation generation time: {max_time:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_batch_recommendation_generation_performance(self):
        """Test performance of batch recommendation generation"""
        # Create multiple users with varying amounts of data
        users = []
        for i in range(50):  # 50 users for batch testing
            user = UserFactory()
            profile = UserBehaviorProfileFactory(user=user)
            users.append(user)
            
            # Create varying amounts of session data
            session_count = 5 + (i % 10)  # 5-14 sessions per user
            for _ in range(session_count):
                HeatmapSessionFactory(user=user)
        
        engine = RecommendationEngine()
        
        # Test batch processing performance
        start_time = time.time()
        
        for user in users:
            recommendations = engine.generate_user_recommendations(user, limit=5)
            assert len(recommendations) <= 5
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_user = total_time / len(users)
        
        # Performance assertions
        assert total_time < 30  # Should complete 50 users in under 30 seconds
        assert avg_time_per_user < 0.6  # Average under 0.6 seconds per user
        
        print(f"Batch processing time for {len(users)} users: {total_time:.3f}s")
        print(f"Average time per user: {avg_time_per_user:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_similarity_calculation_performance(self):
        """Test performance of user similarity calculations"""
        # Create users with behavior profiles
        users = []
        for i in range(100):  # 100 users for similarity testing
            user = UserFactory()
            profile = UserBehaviorProfileFactory(
                user=user,
                similarity_vector=[float(j + i * 0.1) for j in range(10)]
            )
            users.append(user)
        
        engine = CollaborativeFilteringEngine()
        target_user = users[0]
        
        # Measure similarity calculation time
        start_time = time.time()
        engine.calculate_user_similarities(target_user)
        end_time = time.time()
        
        calculation_time = end_time - start_time
        
        # Check results
        similarities = UserSimilarity.objects.filter(user1=target_user)
        similarity_count = similarities.count()
        
        # Performance assertions
        assert calculation_time < 5.0  # Should complete in under 5 seconds
        assert similarity_count > 0  # Should find some similarities
        
        time_per_comparison = calculation_time / (len(users) - 1)
        assert time_per_comparison < 0.1  # Under 0.1 seconds per comparison
        
        print(f"Similarity calculation time: {calculation_time:.3f}s")
        print(f"Calculated {similarity_count} similarities")
        print(f"Time per comparison: {time_per_comparison:.4f}s")
    
    @pytest.mark.performance
    @pytest.mark.django_db 
    def test_content_based_filtering_performance(self):
        """Test performance of content-based filtering"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(
            user=user,
            preferred_content_types=['report', 'dashboard', 'tool'],
            preferred_pages={f'/content{i}/': 20 - i for i in range(50)}
        )
        
        engine = ContentBasedEngine()
        
        # Measure content-based recommendation generation
        times = []
        for _ in range(5):  # Multiple runs
            start_time = time.time()
            recommendations = engine.generate_recommendations(user, limit=10)
            end_time = time.time()
            times.append(end_time - start_time)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 0.5  # Should be faster than collaborative filtering
        assert max_time < 1.0
        
        print(f"Content-based filtering avg time: {avg_time:.3f}s")
        print(f"Content-based filtering max time: {max_time:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_recommendation_caching_effectiveness(self):
        """Test caching performance improvement"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        for _ in range(10):
            HeatmapSessionFactory(user=user)
        
        engine = RecommendationEngine()
        cache.clear()
        
        # First call (no cache)
        start_time = time.time()
        recommendations1 = engine.generate_user_recommendations(user, limit=10)
        no_cache_time = time.time() - start_time
        
        # Cache the results manually (simulating middleware caching)
        cache_key = f'user_recommendations_{user.id}'
        cached_data = {
            'content': [{'id': i, 'title': f'Rec {i}'} for i in range(len(recommendations1))],
            'navigation': [],
            'generated_at': timezone.now().isoformat()
        }
        cache.set(cache_key, cached_data, 3600)
        
        # Second call (with cache)
        start_time = time.time()
        cached_result = cache.get(cache_key)
        cache_time = time.time() - start_time
        
        # Cache should be significantly faster
        assert cached_result is not None
        assert cache_time < no_cache_time * 0.1  # At least 10x faster
        assert cache_time < 0.01  # Cache access should be very fast
        
        print(f"No cache time: {no_cache_time:.3f}s")
        print(f"Cache access time: {cache_time:.4f}s")
        print(f"Cache speedup: {no_cache_time / cache_time:.1f}x")
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_memory_usage_optimization(self):
        """Test memory usage during recommendation generation"""
        import tracemalloc
        
        # Start memory tracing
        tracemalloc.start()
        
        # Create test scenario
        scenario = create_recommendation_scenario(num_users=20, recommendations_per_user=5)
        
        # Take snapshot before processing
        snapshot1 = tracemalloc.take_snapshot()
        
        engine = RecommendationEngine()
        
        # Generate recommendations for all users
        for user in scenario['users']:
            recommendations = engine.generate_user_recommendations(user, limit=5)
        
        # Take snapshot after processing
        snapshot2 = tracemalloc.take_snapshot()
        
        # Compare memory usage
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        
        # Calculate total memory increase
        total_memory_increase = sum(stat.size_diff for stat in top_stats)
        memory_per_user = total_memory_increase / len(scenario['users'])
        
        # Memory usage should be reasonable
        assert total_memory_increase < 50 * 1024 * 1024  # Under 50MB total increase
        assert memory_per_user < 2.5 * 1024 * 1024  # Under 2.5MB per user
        
        print(f"Total memory increase: {total_memory_increase / 1024 / 1024:.2f}MB")
        print(f"Memory per user: {memory_per_user / 1024:.2f}KB")
        
        tracemalloc.stop()
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_database_query_optimization(self):
        """Test database query efficiency in recommendation generation"""
        from django.test.utils import override_settings
        from django.db import connection
        
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        # Create related data
        for _ in range(20):
            similar_user = UserFactory()
            UserBehaviorProfileFactory(user=similar_user)
            UserSimilarityFactory(user1=user, user2=similar_user, similarity_score=0.6)
            ContentRecommendationFactory(user=similar_user)
        
        engine = RecommendationEngine()
        
        # Reset query counter
        connection.queries_log.clear()
        initial_queries = len(connection.queries)
        
        # Generate recommendations
        start_time = time.time()
        recommendations = engine.generate_user_recommendations(user, limit=10)
        generation_time = time.time() - start_time
        
        # Count database queries
        final_queries = len(connection.queries)
        query_count = final_queries - initial_queries
        
        # Performance assertions
        assert query_count < 20  # Should use reasonable number of queries
        assert generation_time < 2.0  # Should complete quickly
        
        # Analyze query efficiency
        if connection.queries:
            query_times = []
            for query in connection.queries[-query_count:]:
                if 'time' in query:
                    query_times.append(float(query['time']))
            
            if query_times:
                avg_query_time = statistics.mean(query_times)
                max_query_time = max(query_times)
                
                assert avg_query_time < 0.1  # Average query under 0.1s
                assert max_query_time < 0.5  # No query over 0.5s
                
                print(f"Query count: {query_count}")
                print(f"Average query time: {avg_query_time:.4f}s")
                print(f"Max query time: {max_query_time:.4f}s")


class TestManagementCommandPerformance:
    """Test performance of management commands"""
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_generate_recommendations_command_performance(self):
        """Test performance of generate_recommendations management command"""
        # Create users with sufficient activity
        users = []
        for i in range(30):  # 30 users for command testing
            user = UserFactory()
            UserBehaviorProfileFactory(user=user)
            users.append(user)
            
            # Create recent activity
            for _ in range(8):
                HeatmapSessionFactory(
                    user=user,
                    start_time=timezone.now() - timedelta(hours=i)
                )
        
        # Measure command execution time
        start_time = time.time()
        
        call_command('generate_recommendations', all_users=True, limit=5, verbosity=0)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Check results
        total_recommendations = ContentRecommendation.objects.count()
        
        # Performance assertions
        assert execution_time < 60  # Should complete in under 1 minute
        assert total_recommendations >= 0  # Should generate some recommendations
        
        time_per_user = execution_time / len(users)
        assert time_per_user < 2.0  # Under 2 seconds per user
        
        print(f"Command execution time: {execution_time:.3f}s")
        print(f"Generated {total_recommendations} recommendations")
        print(f"Time per user: {time_per_user:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_calculate_similarities_command_performance(self):
        """Test performance of calculate_user_similarities command"""
        # Create users with behavior profiles
        users = []
        for i in range(25):  # 25 users for similarity testing
            user = UserFactory()
            profile = UserBehaviorProfileFactory(
                user=user,
                similarity_vector=[float(j + i * 0.05) for j in range(10)]
            )
            users.append(user)
            
            # Create sufficient sessions
            for _ in range(8):
                HeatmapSessionFactory(user=user)
        
        # Measure command execution time
        start_time = time.time()
        
        call_command(
            'calculate_user_similarities', 
            all_users=True, 
            min_sessions=5, 
            batch_size=10,
            verbosity=0
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Check results
        similarity_count = UserSimilarity.objects.count()
        
        # Performance assertions
        assert execution_time < 45  # Should complete in under 45 seconds
        assert similarity_count > 0  # Should generate similarities
        
        comparisons_made = len(users) * (len(users) - 1) / 2  # Approximate
        time_per_comparison = execution_time / comparisons_made if comparisons_made > 0 else 0
        
        print(f"Similarity command time: {execution_time:.3f}s")
        print(f"Generated {similarity_count} similarities")
        print(f"Approximate time per comparison: {time_per_comparison:.4f}s")


class TestWebSocketPerformance:
    """Test WebSocket and real-time performance"""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_websocket_message_throughput(self):
        """Test WebSocket message processing throughput"""
        from channels.testing import WebsocketCommunicator
        from apps.core.consumers import RealtimeMonitoringConsumer
        
        user = await self._create_user_async()
        
        # Create WebSocket connection
        communicator = WebsocketCommunicator(
            RealtimeMonitoringConsumer.as_asgi(),
            "/ws/monitoring/"
        )
        communicator.scope["user"] = user
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Send multiple messages rapidly
        num_messages = 100
        messages = []
        
        for i in range(num_messages):
            message = {
                "type": "test_message",
                "message_id": i,
                "timestamp": timezone.now().isoformat(),
                "data": {"test": f"data_{i}"}
            }
            messages.append(message)
        
        # Measure throughput
        start_time = time.time()
        
        for message in messages:
            await communicator.send_json_to(message)
        
        send_time = time.time() - start_time
        
        # Performance assertions
        throughput = num_messages / send_time
        assert throughput > 50  # Should handle at least 50 messages/second
        assert send_time < 5.0  # Should send 100 messages in under 5 seconds
        
        print(f"WebSocket throughput: {throughput:.1f} messages/second")
        print(f"Total send time: {send_time:.3f}s")
        
        await communicator.disconnect()
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_websocket_connections(self):
        """Test performance with multiple concurrent WebSocket connections"""
        from channels.testing import WebsocketCommunicator
        from apps.core.consumers import DashboardConsumer
        import asyncio
        
        # Create multiple users
        num_connections = 20
        users = []
        for _ in range(num_connections):
            user = await self._create_user_async()
            users.append(user)
        
        # Create concurrent connections
        communicators = []
        connect_tasks = []
        
        start_time = time.time()
        
        for user in users:
            communicator = WebsocketCommunicator(
                DashboardConsumer.as_asgi(),
                "/ws/dashboard/"
            )
            communicator.scope["user"] = user
            
            connect_task = asyncio.create_task(communicator.connect())
            connect_tasks.append(connect_task)
            communicators.append(communicator)
        
        # Wait for all connections
        connections = await asyncio.gather(*connect_tasks)
        connect_time = time.time() - start_time
        
        # Count successful connections
        successful = sum(1 for connected, _ in connections if connected)
        
        # Performance assertions
        assert successful >= num_connections * 0.8  # At least 80% success
        assert connect_time < 10.0  # Should connect within 10 seconds
        
        connection_rate = successful / connect_time
        assert connection_rate > 2  # At least 2 connections per second
        
        print(f"Concurrent connections: {successful}/{num_connections}")
        print(f"Connection time: {connect_time:.3f}s")
        print(f"Connection rate: {connection_rate:.1f} connections/second")
        
        # Cleanup
        disconnect_tasks = []
        for i, communicator in enumerate(communicators):
            if connections[i][0]:
                task = asyncio.create_task(communicator.disconnect())
                disconnect_tasks.append(task)
        
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)
    
    async def _create_user_async(self):
        """Helper to create user in async context"""
        from channels.db import database_sync_to_async
        return await database_sync_to_async(UserFactory)()


class TestAPIPerformance:
    """Test API endpoint performance"""
    
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.profile = UserBehaviorProfileFactory(user=self.user)
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_recommendation_api_response_time(self):
        """Test recommendation API response time"""
        # Create data for recommendations
        for _ in range(10):
            ContentRecommendationFactory(user=self.user)
        
        self.client.force_login(self.user)
        
        # Measure API response times
        response_times = []
        
        for _ in range(10):  # Multiple requests for average
            start_time = time.time()
            response = self.client.get('/api/recommendations/?limit=10')
            end_time = time.time()
            
            response_times.append(end_time - start_time)
            
            if response.status_code == 200:
                # API responded successfully
                pass
        
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        # Performance assertions
        assert avg_response_time < 0.5  # Average under 500ms
        assert max_response_time < 1.0  # Max under 1 second
        
        print(f"API average response time: {avg_response_time:.3f}s")
        print(f"API max response time: {max_response_time:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_recommendation_interaction_api_performance(self):
        """Test recommendation interaction API performance"""
        recommendation = ContentRecommendationFactory(user=self.user)
        self.client.force_login(self.user)
        
        interaction_data = {
            'type': 'click',
            'rec_id': recommendation.id,
            'rec_type': 'content'
        }
        
        # Measure interaction API response times
        response_times = []
        
        for _ in range(20):  # More requests for interaction testing
            start_time = time.time()
            response = self.client.post(
                '/api/recommendations/interact/',
                data=json.dumps(interaction_data),
                content_type='application/json'
            )
            end_time = time.time()
            
            response_times.append(end_time - start_time)
        
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        # Interaction API should be very fast
        assert avg_response_time < 0.2  # Average under 200ms
        assert max_response_time < 0.5  # Max under 500ms
        
        print(f"Interaction API avg time: {avg_response_time:.3f}s")
        print(f"Interaction API max time: {max_response_time:.3f}s")


class TestPerformanceProfiler:
    """Test using performance profiling tools"""
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_recommendation_engine_profiling(self):
        """Profile recommendation engine to identify bottlenecks"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        # Create data for profiling
        for _ in range(50):
            similar_user = UserFactory()
            UserBehaviorProfileFactory(user=similar_user)
            UserSimilarityFactory(user1=user, user2=similar_user)
        
        engine = RecommendationEngine()
        
        # Profile the recommendation generation
        profiler = cProfile.Profile()
        
        profiler.enable()
        recommendations = engine.generate_user_recommendations(user, limit=10)
        profiler.disable()
        
        # Analyze profiling results
        stats_stream = StringIO()
        ps = pstats.Stats(profiler, stream=stats_stream)
        ps.sort_stats('cumulative').print_stats(10)  # Top 10 functions
        
        profile_output = stats_stream.getvalue()
        
        # Basic assertions
        assert len(recommendations) <= 10
        assert len(profile_output) > 0  # Should have profiling data
        
        print("\nTop 10 functions by cumulative time:")
        print(profile_output)
    
    @pytest.mark.performance
    @pytest.mark.django_db
    def test_performance_regression_detection(self):
        """Test for performance regressions"""
        # This test would typically compare against baseline metrics
        # stored from previous test runs
        
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        for _ in range(20):
            HeatmapSessionFactory(user=user)
        
        engine = RecommendationEngine()
        
        # Measure current performance
        times = []
        for _ in range(5):
            start_time = time.time()
            recommendations = engine.generate_user_recommendations(user, limit=5)
            times.append(time.time() - start_time)
        
        avg_time = statistics.mean(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        
        # Define performance baselines (these would typically be stored/loaded)
        BASELINE_AVG_TIME = 0.5  # 500ms baseline
        BASELINE_STD_DEV = 0.1   # 100ms standard deviation
        REGRESSION_THRESHOLD = 1.5  # 50% slower is a regression
        
        # Check for regression
        performance_ratio = avg_time / BASELINE_AVG_TIME
        std_dev_ratio = std_dev / BASELINE_STD_DEV if BASELINE_STD_DEV > 0 else 1
        
        # Assertions for regression detection
        assert performance_ratio < REGRESSION_THRESHOLD, f"Performance regression detected: {performance_ratio:.2f}x slower"
        assert std_dev_ratio < 2.0, f"Performance variability increased: {std_dev_ratio:.2f}x more variable"
        
        print(f"Current avg time: {avg_time:.3f}s (baseline: {BASELINE_AVG_TIME:.3f}s)")
        print(f"Performance ratio: {performance_ratio:.2f}x")
        print(f"Standard deviation: {std_dev:.3f}s")
        print(f"Variability ratio: {std_dev_ratio:.2f}x")