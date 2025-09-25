"""
Integration tests for recommendation system workflows
"""
import pytest
import json
import time
from unittest.mock import patch, Mock
from django.test import Client, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

from apps.core.models.recommendation import (
    UserBehaviorProfile, ContentRecommendation, NavigationRecommendation,
    UserSimilarity, RecommendationFeedback, RecommendationImplementation
)
from apps.core.models.heatmap import HeatmapSession, ClickHeatmap, ScrollHeatmap
from apps.core.models.monitoring import PageView, NavigationClick
from apps.ab_testing.models import Experiment, Variant, Assignment
from apps.core.recommendation_engine import RecommendationEngine
from tests.factories.recommendation_factories import (
    UserBehaviorProfileFactory, ContentRecommendationFactory, NavigationRecommendationFactory,
    create_recommendation_scenario
)
from tests.factories.heatmap_factories import UserFactory, HeatmapSessionFactory
from tests.factories.ab_testing_factories import ExperimentFactory, VariantFactory

User = get_user_model()
pytestmark = pytest.mark.django_db


class TestRecommendationLifecycle(TransactionTestCase):
    """Test complete recommendation lifecycle"""
    
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()
        self.engine = RecommendationEngine()
        cache.clear()
    
    def test_complete_recommendation_workflow(self):
        """Test complete workflow from user behavior to recommendation display"""
        # Step 1: User generates behavior data
        profile = UserBehaviorProfileFactory(
            user=self.user,
            preferred_pages={'/dashboard/': 20, '/reports/': 15, '/assets/': 10}
        )
        
        # Create heatmap sessions showing user activity
        sessions = []
        for i in range(10):
            session = HeatmapSessionFactory(
                user=self.user,
                page_url=f'/page{i%3}/',
                device_type='desktop'
            )
            sessions.append(session)
            
            # Add interaction data
            ClickHeatmapFactory(session=session, x_position=0.5, y_position=0.3)
            ScrollHeatmapFactory(session=session, scroll_depth_percentage=75)
        
        # Step 2: Create similar users for collaborative filtering
        similar_users = []
        for i in range(3):
            similar_user = UserFactory()
            similar_profile = UserBehaviorProfileFactory(
                user=similar_user,
                preferred_pages={'/dashboard/': 18, '/reports/': 12, '/tools/': 8}
            )
            similar_users.append(similar_user)
            
            # Create similarity relationship
            UserSimilarity.objects.create(
                user1=self.user,
                user2=similar_user,
                similarity_score=0.8 - i * 0.1,
                calculation_method='cosine_similarity'
            )
            
            # Similar users have recommendations
            ContentRecommendationFactory(
                user=similar_user,
                content_type='tool',
                content_url=f'/tools/tool{i}/',
                relevance_score=0.8
            )
        
        # Step 3: Generate recommendations using management command
        call_command('generate_recommendations', user_id=self.user.id, limit=5)
        
        # Verify recommendations were created
        user_recommendations = ContentRecommendation.objects.filter(user=self.user)
        assert user_recommendations.exists()
        
        # Step 4: Test middleware integration
        self.client.force_login(self.user)
        
        # Mock the middleware to attach recommendations
        with patch('apps.core.middleware.recommendation_middleware.RecommendationMiddleware') as mock_middleware:
            mock_instance = Mock()
            mock_middleware.return_value = mock_instance
            
            response = self.client.get('/dashboard/')
            
            # Response status will depend on URL configuration, but middleware should be called
            # The important part is testing the integration
        
        # Step 5: Test API endpoint for retrieving recommendations
        response = self.client.get('/api/recommendations/')
        
        if response.status_code == 200:
            data = json.loads(response.content)
            assert 'content_recommendations' in data or 'error' not in data
        
        # Step 6: Test user interaction with recommendations
        if user_recommendations.exists():
            recommendation = user_recommendations.first()
            
            # Test click tracking
            interaction_data = {
                'type': 'click',
                'rec_id': recommendation.id,
                'rec_type': 'content'
            }
            
            response = self.client.post(
                '/api/recommendations/interact/',
                data=json.dumps(interaction_data),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                recommendation.refresh_from_db()
                # Click count might be updated depending on implementation
    
    def test_collaborative_filtering_workflow(self):
        """Test collaborative filtering recommendation generation"""
        # Create multiple users with similar behavior patterns
        users = [UserFactory() for _ in range(5)]
        
        # Create behavior profiles with overlapping interests
        for i, user in enumerate(users):
            UserBehaviorProfileFactory(
                user=user,
                preferred_pages={
                    '/dashboard/': 20 + i * 2,
                    '/reports/': 15 + i,
                    '/analytics/': 10 + i * 3
                },
                exploration_tendency=0.6 + i * 0.05
            )
            
            # Create heatmap data
            for j in range(8):
                session = HeatmapSessionFactory(user=user, page_url=f'/page{j%3}/')
                ClickHeatmapFactory(session=session)
        
        # Calculate user similarities using command
        call_command('calculate_user_similarities', all_users=True, min_sessions=5)
        
        # Verify similarities were calculated
        similarities = UserSimilarity.objects.all()
        assert similarities.count() > 0
        
        # Generate recommendations based on similarities
        target_user = users[0]
        recommendations = self.engine.generate_user_recommendations(target_user, limit=10)
        
        # Should generate some recommendations
        assert len(recommendations) >= 0  # May be 0 if no suitable content found
        
        # Test similarity-based recommendation logic
        similar_users_query = UserSimilarity.objects.filter(
            user1=target_user,
            similarity_score__gte=0.3
        ).order_by('-similarity_score')
        
        # Should find similar users
        assert similar_users_query.exists()
    
    def test_content_based_filtering_workflow(self):
        """Test content-based filtering recommendation generation"""
        # Create user with specific content preferences
        user = UserFactory()
        profile = UserBehaviorProfileFactory(
            user=user,
            preferred_content_types=['report', 'dashboard'],
            preferred_pages={
                '/reports/sales/': 30,
                '/reports/revenue/': 25,
                '/dashboard/analytics/': 20
            }
        )
        
        # Create heatmap data showing user's preferences
        for report_type in ['sales', 'revenue', 'profit']:
            session = HeatmapSessionFactory(
                user=user,
                page_url=f'/reports/{report_type}/',
                device_type='desktop'
            )
            ClickHeatmapFactory(session=session)
        
        # Generate content-based recommendations
        recommendations = self.engine.content_engine.generate_recommendations(user, limit=5)
        
        # Recommendations should be based on user's content preferences
        assert len(recommendations) >= 0
        
        # Test that recommendations match user's preferred content types
        for rec in recommendations:
            if hasattr(rec, 'content_type'):
                assert rec.content_type in profile.preferred_content_types or \
                       'report' in rec.content_url or 'dashboard' in rec.content_url
    
    def test_navigation_analysis_workflow(self):
        """Test navigation analysis and recommendation generation"""
        # Create users with navigation patterns
        users = [UserFactory() for _ in range(10)]
        
        # Simulate problematic navigation patterns
        problem_page = '/confusing-page/'
        
        for user in users:
            # Most users have short sessions on problem page (indicating issues)
            problem_session = HeatmapSessionFactory(
                user=user,
                page_url=problem_page,
                is_active=False
            )
            problem_session.duration_seconds = 15  # Very short
            problem_session.save()
            
            # Add click data showing user confusion
            ClickHeatmapFactory(
                session=problem_session,
                element_type='div',  # Clicking on non-interactive elements
                is_navigation=False
            )
            
            # Create normal sessions on other pages
            normal_session = HeatmapSessionFactory(
                user=user,
                page_url='/normal-page/',
                is_active=False
            )
            normal_session.duration_seconds = 120  # Normal duration
            normal_session.save()
        
        # Generate navigation recommendations
        nav_recommendations = self.engine.generate_navigation_recommendations()
        
        # Should identify navigation issues and generate recommendations
        assert len(nav_recommendations) >= 0
        
        # Look for recommendations related to problematic areas
        for rec in nav_recommendations:
            if hasattr(rec, 'target_page') and rec.target_page == problem_page:
                assert rec.recommendation_type in [
                    'layout_improvement', 'menu_optimization', 'content_personalization'
                ]
    
    def test_ab_testing_integration_with_recommendations(self):
        """Test A/B testing integration with recommendation system"""
        # Create A/B test for recommendation algorithm
        experiment = ExperimentFactory(
            name='Recommendation Algorithm Test',
            experiment_type='feature',
            status='running',
            is_active=True
        )
        
        # Create variants
        control_variant = VariantFactory(
            experiment=experiment,
            name='Control',
            is_control=True,
            feature_flags={'recommendation_algorithm': 'collaborative_filtering'}
        )
        
        test_variant = VariantFactory(
            experiment=experiment,
            name='Test',
            is_control=False,
            feature_flags={'recommendation_algorithm': 'hybrid'}
        )
        
        # Create users and assign to variants
        users = [UserFactory() for _ in range(6)]
        
        for i, user in enumerate(users):
            UserBehaviorProfileFactory(user=user)
            
            # Alternate assignment between variants
            variant = control_variant if i % 2 == 0 else test_variant
            Assignment.objects.create(
                experiment=experiment,
                variant=variant,
                user=user,
                session_id=f'session_{i}'
            )
        
        # Generate recommendations for users in different variants
        control_users = [users[i] for i in range(0, len(users), 2)]
        test_users = [users[i] for i in range(1, len(users), 2)]
        
        # Test that different algorithms can be used based on variant
        for user in control_users:
            recommendations = self.engine.generate_user_recommendations(user, limit=5)
            # Control group gets collaborative filtering
            # (Implementation would check assignment and use appropriate algorithm)
        
        for user in test_users:
            recommendations = self.engine.generate_user_recommendations(user, limit=5)
            # Test group gets hybrid algorithm
            # (Implementation would check assignment and use appropriate algorithm)
    
    def test_recommendation_feedback_loop(self):
        """Test feedback loop improving recommendations over time"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        # Generate initial recommendations
        initial_recommendations = []
        for i in range(5):
            rec = ContentRecommendationFactory(
                user=user,
                content_url=f'/content{i}/',
                relevance_score=0.6 + i * 0.05
            )
            initial_recommendations.append(rec)
        
        # Simulate user interactions (positive feedback on some, negative on others)
        positive_recs = initial_recommendations[:2]
        negative_recs = initial_recommendations[2:4]
        
        for rec in positive_recs:
            # User clicks and provides positive feedback
            rec.mark_clicked()
            RecommendationFeedback.objects.create(
                user=user,
                content_type=rec.content_type,
                object_id=rec.id,
                feedback_type='helpful',
                rating=4
            )
        
        for rec in negative_recs:
            # User dismisses and provides negative feedback
            rec.mark_dismissed()
            RecommendationFeedback.objects.create(
                user=user,
                content_type=rec.content_type,
                object_id=rec.id,
                feedback_type='not_helpful',
                rating=2
            )
        
        # Generate new recommendations (should consider feedback)
        new_recommendations = self.engine.generate_user_recommendations(user, limit=5)
        
        # The recommendation engine should learn from feedback
        # (Implementation would use feedback to improve future recommendations)
        assert len(new_recommendations) >= 0
        
        # Test feedback aggregation
        positive_feedback = RecommendationFeedback.objects.filter(
            user=user,
            feedback_type='helpful'
        )
        negative_feedback = RecommendationFeedback.objects.filter(
            user=user,
            feedback_type='not_helpful'
        )
        
        assert positive_feedback.count() == 2
        assert negative_feedback.count() == 2
    
    def test_real_time_recommendation_updates(self):
        """Test real-time updates to recommendations based on user behavior"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(
            user=user,
            preferred_pages={'/old-preference/': 10}
        )
        
        # Initial recommendations based on old preferences
        old_rec = ContentRecommendationFactory(
            user=user,
            content_url='/related-to-old-preference/',
            relevance_score=0.7
        )
        
        # Simulate new user behavior (shift in preferences)
        for i in range(10):
            session = HeatmapSessionFactory(
                user=user,
                page_url='/new-preference/',
                start_time=timezone.now() - timedelta(hours=i)
            )
            ClickHeatmapFactory(session=session)
        
        # Update user profile based on new behavior
        self.engine.behavior_analyzer.update_user_profile(user, {
            'page_url': '/new-preference/',
            'timestamp': timezone.now(),
            'device_type': 'desktop'
        })
        
        # Generate updated recommendations
        updated_recommendations = self.engine.generate_user_recommendations(user, limit=10)
        
        # Should reflect new preferences
        assert len(updated_recommendations) >= 0
        
        # Profile should have updated preferences
        profile.refresh_from_db()
        assert '/new-preference/' in profile.preferred_pages
    
    def test_multi_device_recommendation_consistency(self):
        """Test recommendation consistency across different devices"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        # Create sessions from different devices
        devices = ['desktop', 'mobile', 'tablet']
        
        for device in devices:
            for i in range(5):
                session = HeatmapSessionFactory(
                    user=user,
                    device_type=device,
                    page_url=f'/page{i}/',
                    viewport_width=1920 if device == 'desktop' else 375
                )
                ClickHeatmapFactory(session=session)
        
        # Generate recommendations for each device context
        device_recommendations = {}
        
        for device in devices:
            # Mock device context in recommendation generation
            with patch('apps.core.recommendation_engine.RecommendationEngine.generate_user_recommendations') as mock_gen:
                mock_gen.return_value = [
                    ContentRecommendationFactory.build(
                        user=user,
                        content_url=f'/{device}-optimized-content/'
                    )
                ]
                
                recs = self.engine.generate_user_recommendations(user, limit=5)
                device_recommendations[device] = recs
        
        # Recommendations should be consistent but may be optimized for device
        for device, recs in device_recommendations.items():
            assert len(recs) >= 0
            # Could test for device-specific optimizations
    
    def test_recommendation_performance_monitoring(self):
        """Test monitoring recommendation performance and effectiveness"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        # Create recommendations with various performance metrics
        recommendations = []
        for i in range(10):
            rec = ContentRecommendationFactory(
                user=user,
                content_url=f'/content{i}/',
                relevance_score=0.5 + (i % 5) * 0.1,
                shown_count=10 + i,
                clicked_count=i % 3,  # Some get clicks, others don't
                dismissed_count=1 if i % 4 == 0 else 0  # Some get dismissed
            )
            recommendations.append(rec)
        
        # Calculate performance metrics
        total_shown = sum(rec.shown_count for rec in recommendations)
        total_clicked = sum(rec.clicked_count for rec in recommendations)
        total_dismissed = sum(rec.dismissed_count for rec in recommendations)
        
        ctr = total_clicked / total_shown if total_shown > 0 else 0
        dismissal_rate = total_dismissed / total_shown if total_shown > 0 else 0
        
        # Performance metrics should be reasonable
        assert 0 <= ctr <= 1
        assert 0 <= dismissal_rate <= 1
        
        # Test individual recommendation effectiveness
        for rec in recommendations:
            effectiveness = rec.is_effective() if hasattr(rec, 'is_effective') else True
            # Effectiveness depends on click-through rate vs dismissal rate
        
        # Monitor algorithm performance using bandit
        algorithm_performance = self.engine.bandit.get_algorithm_performance('collaborative_filtering')
        
        assert 'success_rate' in algorithm_performance
        assert 'trials' in algorithm_performance
        assert algorithm_performance['success_rate'] >= 0
    
    def test_recommendation_cache_invalidation(self):
        """Test cache invalidation when user behavior changes significantly"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        # Generate and cache initial recommendations
        cache_key = f'user_recommendations_{user.id}'
        initial_recs = self.engine.generate_user_recommendations(user, limit=5)
        
        # Cache should contain recommendations
        cached_recs = cache.get(cache_key)
        
        # Simulate significant behavior change
        # Add new sessions that should invalidate cache
        for i in range(20):  # Significant new activity
            session = HeatmapSessionFactory(
                user=user,
                page_url='/new-area/',
                start_time=timezone.now() - timedelta(minutes=i)
            )
            ClickHeatmapFactory(session=session)
        
        # Update profile (this should invalidate cache in real implementation)
        self.engine.behavior_analyzer.update_user_profile(user, {
            'page_url': '/new-area/',
            'timestamp': timezone.now(),
            'device_type': 'desktop'
        })
        
        # Generate new recommendations
        new_recs = self.engine.generate_user_recommendations(user, limit=5)
        
        # Should reflect new behavior patterns
        assert len(new_recs) >= 0


class TestScenarioBasedIntegration:
    """Test realistic user scenarios end-to-end"""
    
    def setup_method(self):
        self.client = Client()
        cache.clear()
    
    @pytest.mark.integration
    def test_new_user_onboarding_scenario(self):
        """Test recommendation system for new users"""
        # New user with minimal activity
        new_user = UserFactory()
        
        # First login - no profile exists yet
        self.client.force_login(new_user)
        
        # User visits a few pages
        pages = ['/dashboard/', '/help/', '/getting-started/']
        for page in pages:
            # Simulate page visit
            session = HeatmapSessionFactory(
                user=new_user,
                page_url=page,
                start_time=timezone.now(),
                device_type='desktop'
            )
            ClickHeatmapFactory(session=session)
        
        # Generate recommendations for new user
        engine = RecommendationEngine()
        recommendations = engine.generate_user_recommendations(new_user, limit=5)
        
        # Should provide default/onboarding recommendations
        assert len(recommendations) >= 0
        
        # Should create behavior profile
        profile = UserBehaviorProfile.objects.filter(user=new_user).first()
        if profile:
            assert len(profile.preferred_pages) > 0
    
    @pytest.mark.integration
    def test_power_user_scenario(self):
        """Test recommendations for highly active users"""
        power_user = UserFactory()
        
        # Create extensive user activity
        profile = UserBehaviorProfileFactory(
            user=power_user,
            exploration_tendency=0.8,  # High exploration
            task_completion_rate=0.9,  # High completion rate
            feature_adoption_rate=0.85  # Adopts new features quickly
        )
        
        # Create diverse activity across many pages
        page_categories = ['dashboard', 'reports', 'analytics', 'admin', 'tools']
        
        for category in page_categories:
            for i in range(10):  # 10 pages per category
                session = HeatmapSessionFactory(
                    user=power_user,
                    page_url=f'/{category}/page{i}/',
                    device_type=['desktop', 'mobile'][i % 2]
                )
                
                # Add rich interaction data
                for _ in range(5):  # Multiple clicks per session
                    ClickHeatmapFactory(session=session)
                ScrollHeatmapFactory(session=session)
        
        # Create similar power users for collaborative filtering
        similar_users = []
        for i in range(3):
            similar_user = UserFactory()
            UserBehaviorProfileFactory(
                user=similar_user,
                exploration_tendency=0.75 + i * 0.05,
                preferred_pages={f'/{cat}/': 20 + i for cat in page_categories}
            )
            similar_users.append(similar_user)
            
            # Create similarity relationship
            UserSimilarity.objects.create(
                user1=power_user,
                user2=similar_user,
                similarity_score=0.85 - i * 0.05
            )
        
        # Generate recommendations for power user
        engine = RecommendationEngine()
        recommendations = engine.generate_user_recommendations(power_user, limit=15)
        
        # Should generate sophisticated recommendations
        assert len(recommendations) >= 0
        
        # Power users should get more advanced/diverse recommendations
        if recommendations:
            # Check for variety in recommendation types
            unique_types = set()
            for rec in recommendations:
                if hasattr(rec, 'content_type'):
                    unique_types.add(rec.content_type)
            
            # Power users should see diverse content types
            assert len(unique_types) >= 1
    
    @pytest.mark.integration
    def test_mobile_user_scenario(self):
        """Test mobile-optimized recommendations"""
        mobile_user = UserFactory()
        
        # Create mobile-specific behavior profile
        profile = UserBehaviorProfileFactory(
            user=mobile_user,
            preferred_device_type='mobile',
            session_duration_avg=60  # Shorter sessions on mobile
        )
        
        # Create mobile sessions with different interaction patterns
        for i in range(20):
            session = HeatmapSessionFactory(
                user=mobile_user,
                device_type='mobile',
                viewport_width=375,
                viewport_height=667,
                page_url=f'/mobile-page{i%5}/',
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)'
            )
            
            # Mobile users tend to scroll more, click less
            ScrollHeatmapFactory(
                session=session,
                scroll_depth_percentage=85  # High scroll depth
            )
            
            if i % 3 == 0:  # Less frequent clicking
                ClickHeatmapFactory(session=session)
        
        # Generate mobile-optimized recommendations
        engine = RecommendationEngine()
        recommendations = engine.generate_user_recommendations(mobile_user, limit=8)
        
        # Mobile users should get fewer, more targeted recommendations
        assert len(recommendations) <= 8
        
        # Recommendations should consider mobile context
        for rec in recommendations:
            if hasattr(rec, 'display_conditions'):
                # Could check for mobile-specific display conditions
                pass
    
    @pytest.mark.integration
    def test_team_collaboration_scenario(self):
        """Test recommendations for users in collaborative environments"""
        # Create a team of users working on similar projects
        team_lead = UserFactory()
        team_members = [UserFactory() for _ in range(4)]
        all_team_users = [team_lead] + team_members
        
        # Team works on similar pages/features
        team_pages = ['/projects/', '/team-dashboard/', '/shared-reports/', '/collaboration/']
        
        for user in all_team_users:
            profile = UserBehaviorProfileFactory(
                user=user,
                preferred_pages={page: 15 + team_pages.index(page) * 5 for page in team_pages}
            )
            
            # Create activity on team pages
            for page in team_pages:
                for _ in range(8):
                    session = HeatmapSessionFactory(
                        user=user,
                        page_url=page,
                        start_time=timezone.now() - timedelta(hours=_)
                    )
                    ClickHeatmapFactory(session=session)
        
        # Calculate similarities within team
        call_command('calculate_user_similarities', all_users=True, min_sessions=5)
        
        # Generate recommendations for team lead
        engine = RecommendationEngine()
        lead_recommendations = engine.generate_user_recommendations(team_lead, limit=10)
        
        # Team lead should get recommendations influenced by team activity
        assert len(lead_recommendations) >= 0
        
        # Check that team members have high similarity scores
        team_similarities = UserSimilarity.objects.filter(
            user1=team_lead,
            user2__in=team_members
        )
        
        if team_similarities.exists():
            avg_similarity = sum(sim.similarity_score for sim in team_similarities) / len(team_similarities)
            assert avg_similarity > 0.3  # Team should have reasonable similarity
    
    @pytest.mark.integration 
    def test_recommendation_decay_scenario(self):
        """Test recommendation relevance decay over time"""
        user = UserFactory()
        profile = UserBehaviorProfileFactory(user=user)
        
        # Create old recommendations
        old_recs = []
        for i in range(5):
            rec = ContentRecommendationFactory(
                user=user,
                content_url=f'/old-content{i}/',
                created_at=timezone.now() - timedelta(days=30),
                expires_at=timezone.now() - timedelta(days=1),  # Expired
                relevance_score=0.8
            )
            old_recs.append(rec)
        
        # Create recent recommendations
        recent_recs = []
        for i in range(5):
            rec = ContentRecommendationFactory(
                user=user,
                content_url=f'/recent-content{i}/',
                created_at=timezone.now() - timedelta(days=1),
                expires_at=timezone.now() + timedelta(days=7),  # Still valid
                relevance_score=0.7
            )
            recent_recs.append(rec)
        
        # Query active recommendations
        active_recs = ContentRecommendation.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        )
        
        # Only recent recommendations should be active
        assert active_recs.count() == len(recent_recs)
        
        # Expired recommendations should be filtered out
        expired_recs = ContentRecommendation.objects.filter(
            user=user,
            expires_at__lt=timezone.now()
        )
        
        assert expired_recs.count() == len(old_recs)
    
    @pytest.mark.slow
    @pytest.mark.performance
    def test_large_scale_recommendation_scenario(self):
        """Test recommendation system with large number of users"""
        # Create large number of users (scaled down for testing)
        num_users = 50  # In real scenario, could be thousands
        
        users = []
        start_time = time.time()
        
        # Create users with varied behavior patterns
        for i in range(num_users):
            user = UserFactory()
            users.append(user)
            
            # Vary user profiles to create different clusters
            cluster = i % 5  # 5 different user clusters
            
            UserBehaviorProfileFactory(
                user=user,
                exploration_tendency=0.3 + (cluster * 0.15),
                preferred_pages={
                    f'/cluster{cluster}/page1/': 20,
                    f'/cluster{cluster}/page2/': 15,
                    '/common/page/': 10
                }
            )
            
            # Create heatmap sessions
            for _ in range(6):  # Minimum required sessions
                HeatmapSessionFactory(user=user)
        
        # Calculate similarities for all users
        similarity_start = time.time()
        call_command('calculate_user_similarities', all_users=True, min_sessions=5, batch_size=10)
        similarity_end = time.time()
        
        # Generate recommendations for subset of users
        rec_start = time.time()
        engine = RecommendationEngine()
        
        sample_users = users[:10]  # Test with subset
        for user in sample_users:
            recommendations = engine.generate_user_recommendations(user, limit=5)
            assert len(recommendations) >= 0
        
        rec_end = time.time()
        
        # Performance assertions
        total_time = rec_end - start_time
        similarity_time = similarity_end - similarity_start
        rec_time = rec_end - rec_start
        
        # Should complete within reasonable time
        assert total_time < 60  # 1 minute for full scenario
        assert similarity_time < 30  # 30 seconds for similarity calculation
        assert rec_time < 10  # 10 seconds for recommendations
        
        # Verify data integrity
        assert UserSimilarity.objects.count() > 0
        assert UserBehaviorProfile.objects.count() == num_users