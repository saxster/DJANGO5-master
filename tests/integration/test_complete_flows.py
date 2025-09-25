"""
Integration and End-to-End tests for complete user flows
"""
import pytest
import json
import time
from unittest.mock import patch, MagicMock
from django.test import Client, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

from apps.core.models.heatmap import (
    HeatmapSession, ClickHeatmap, ScrollHeatmap, AttentionHeatmap, 
    ElementInteraction, HeatmapAggregation
)
from apps.core.models.monitoring import (
    PageView, NavigationClick, ErrorLog, NavigationPath
)
from apps.ab_testing.models import (
    Experiment, Variant, Assignment, Conversion, ExperimentResult
)
from apps.ab_testing.analytics import ABTestingEngine, ExperimentAnalyzer
from tests.factories.ab_testing_factories import (
    ExperimentFactory, VariantFactory, create_complete_experiment
)
from tests.factories.heatmap_factories import UserFactory, create_complete_session_with_data

User = get_user_model()


class IntegrationTestCase(TransactionTestCase):
    """Base class for integration tests that need database transactions"""
    
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.staff_user = UserFactory(is_staff=True)
        self.regular_user = UserFactory(is_staff=False)
        cache.clear()


@pytest.mark.integration
class TestCompleteHeatmapFlow(IntegrationTestCase):
    """Test complete heatmap tracking and visualization flow"""
    
    def test_end_to_end_heatmap_workflow(self):
        """Test complete heatmap workflow from data collection to visualization"""
        # Step 1: Initialize heatmap session (simulating frontend)
        session_data = {
            'sessionId': 'e2e-heatmap-session',
            'pageUrl': '/test-heatmap-page/',
            'pageTitle': 'Test Heatmap Page',
            'viewport': {'width': 1920, 'height': 1080},
            'screen': {'width': 1920, 'height': 1080},
            'deviceType': 'desktop'
        }
        
        self.client.force_login(self.regular_user)
        
        init_response = self.client.post(
            '/api/heatmap/session/init/',
            data=json.dumps(session_data),
            content_type='application/json'
        )
        
        self.assertEqual(init_response.status_code, 200)
        
        # Verify session was created
        session = HeatmapSession.objects.get(session_id='e2e-heatmap-session')
        self.assertEqual(session.user, self.regular_user)
        self.assertEqual(session.page_url, '/test-heatmap-page/')
        
        # Step 2: Track user interactions
        interaction_data = {
            'sessionId': 'e2e-heatmap-session',
            'clicks': [
                {
                    'x': 0.5, 'y': 0.3, 'absoluteX': 960, 'absoluteY': 324,
                    'element': {
                        'tagName': 'button', 'id': 'cta-button', 'className': 'btn-primary',
                        'text': 'Get Started', 'isNavigation': False
                    },
                    'timeSinceLoad': 2500, 'clickType': 'left'
                },
                {
                    'x': 0.7, 'y': 0.8, 'absoluteX': 1344, 'absoluteY': 864,
                    'element': {
                        'tagName': 'a', 'id': 'footer-link', 'className': 'footer-nav',
                        'text': 'Contact Us', 'isNavigation': True
                    },
                    'timeSinceLoad': 5000, 'clickType': 'left'
                }
            ],
            'scrolls': [
                {'scrollDepthPixels': 500, 'scrollDepthPercentage': 46.3, 'velocity': 120},
                {'scrollDepthPixels': 800, 'scrollDepthPercentage': 74.1, 'velocity': 200},
                {'scrollDepthPixels': 1080, 'scrollDepthPercentage': 100.0, 'velocity': 80}
            ],
            'interactions': [
                {
                    'element': {
                        'selector': '#email-input', 'tagName': 'input', 'id': 'email-input',
                        'className': 'form-control', 'text': ''
                    },
                    'interactionType': 'focus', 'duration': 1.5
                },
                {
                    'element': {
                        'selector': '#email-input', 'tagName': 'input', 'id': 'email-input',
                        'className': 'form-control', 'text': 'user@example.com'
                    },
                    'interactionType': 'blur', 'duration': 8.5
                }
            ],
            'attention': [
                {
                    'x_start': 0.2, 'y_start': 0.1, 'x_end': 0.8, 'y_end': 0.4,
                    'duration': 12.5
                },
                {
                    'x_start': 0.1, 'y_start': 0.6, 'x_end': 0.9, 'y_end': 0.9,
                    'duration': 8.2
                }
            ]
        }
        
        track_response = self.client.post(
            '/api/heatmap/track/',
            data=json.dumps(interaction_data),
            content_type='application/json'
        )
        
        self.assertEqual(track_response.status_code, 200)
        
        # Verify data was recorded
        session.refresh_from_db()
        self.assertEqual(session.data_points_collected, 7)  # 2 clicks + 3 scrolls + 2 interactions
        
        clicks = ClickHeatmap.objects.filter(session=session)
        self.assertEqual(clicks.count(), 2)
        
        # Verify specific click data
        cta_click = clicks.filter(element_id='cta-button').first()
        self.assertIsNotNone(cta_click)
        self.assertEqual(cta_click.x_position, 0.5)
        self.assertEqual(cta_click.element_text, 'Get Started')
        self.assertFalse(cta_click.is_navigation)
        
        nav_click = clicks.filter(element_id='footer-link').first()
        self.assertIsNotNone(nav_click)
        self.assertTrue(nav_click.is_navigation)
        
        # Verify scroll data
        scrolls = ScrollHeatmap.objects.filter(session=session)
        self.assertEqual(scrolls.count(), 3)
        
        max_scroll = scrolls.order_by('-scroll_depth_percentage').first()
        self.assertEqual(max_scroll.scroll_depth_percentage, 100.0)
        
        # Verify interaction data
        interactions = ElementInteraction.objects.filter(session=session)
        self.assertEqual(interactions.count(), 2)
        
        focus_interaction = interactions.filter(interaction_type='focus').first()
        self.assertIsNotNone(focus_interaction)
        self.assertEqual(focus_interaction.element_selector, '#email-input')
        
        # Verify attention zones
        attention_zones = AttentionHeatmap.objects.filter(session=session)
        self.assertEqual(attention_zones.count(), 2)
        
        # Step 3: End session
        end_response = self.client.post(
            '/api/heatmap/session/end/',
            data=json.dumps({'sessionId': 'e2e-heatmap-session'}),
            content_type='application/json'
        )
        
        self.assertEqual(end_response.status_code, 200)
        
        session.refresh_from_db()
        self.assertFalse(session.is_active)
        self.assertIsNotNone(session.end_time)
        self.assertIsNotNone(session.duration_seconds)
        
        # Step 4: Access visualization dashboard (requires staff permissions)
        self.client.force_login(self.staff_user)
        
        dashboard_response = self.client.get('/heatmap/dashboard/')
        self.assertEqual(dashboard_response.status_code, 200)
        
        # Step 5: Retrieve heatmap data via API
        api_response = self.client.get(
            '/api/heatmap/data/?page_url=/test-heatmap-page/&type=click'
        )
        self.assertEqual(api_response.status_code, 200)
        
        api_data = json.loads(api_response.content)
        self.assertEqual(api_data['type'], 'click')
        self.assertEqual(api_data['session_count'], 1)
        self.assertEqual(api_data['total_clicks'], 2)
        self.assertIn('click_points', api_data)
        self.assertIn('heatmap_matrix', api_data)
        
        # Step 6: Export heatmap data
        export_response = self.client.get(
            '/api/heatmap/export/?page_url=/test-heatmap-page/&format=json'
        )
        self.assertEqual(export_response.status_code, 200)
        
        export_data = json.loads(export_response.content)
        self.assertEqual(export_data['session_count'], 1)
        self.assertIn('sessions', export_data)
        self.assertIn('summary', export_data)
    
    def test_heatmap_aggregation_workflow(self):
        """Test heatmap data aggregation workflow"""
        page_url = '/aggregation-test-page/'
        
        # Create multiple sessions with data
        sessions = []
        for i in range(15):  # Create enough to trigger aggregation
            session = create_complete_session_with_data(
                page_url=page_url,
                device_type='desktop' if i % 2 == 0 else 'mobile',
                num_clicks=5,
                num_scrolls=3,
                num_interactions=2
            )
            sessions.append(session)
        
        # Manually trigger aggregation
        end_date = timezone.now()
        start_date = end_date - timedelta(hours=1)
        
        aggregation = HeatmapAggregation.generate_aggregation(
            page_url=page_url,
            start_date=start_date,
            end_date=end_date,
            device_type='all'
        )
        
        self.assertIsNotNone(aggregation)
        self.assertEqual(aggregation.page_url, page_url)
        self.assertEqual(aggregation.session_count, 15)
        self.assertGreater(aggregation.total_clicks, 0)
        self.assertGreater(aggregation.total_scrolls, 0)
        self.assertGreater(aggregation.total_interactions, 0)
        
        # Verify aggregation data structure
        self.assertIn('grid_size', aggregation.click_heatmap_data)
        self.assertIn('matrix', aggregation.click_heatmap_data)
        self.assertIsInstance(aggregation.scroll_depth_distribution, dict)
        self.assertIn('top_elements', aggregation.interaction_summary)
    
    def test_cross_device_heatmap_comparison(self):
        """Test cross-device heatmap comparison"""
        page_url = '/cross-device-test/'
        
        # Create sessions for different devices
        desktop_session = create_complete_session_with_data(
            page_url=page_url, device_type='desktop', num_clicks=8
        )
        mobile_session = create_complete_session_with_data(
            page_url=page_url, device_type='mobile', num_clicks=5
        )
        tablet_session = create_complete_session_with_data(
            page_url=page_url, device_type='tablet', num_clicks=6
        )
        
        self.client.force_login(self.staff_user)
        
        # Get comparison data
        comparison_response = self.client.get(
            f'/api/heatmap/comparison/?page_url={page_url}&comparison=device'
        )
        
        self.assertEqual(comparison_response.status_code, 200)
        comparison_data = json.loads(comparison_response.content)
        
        self.assertEqual(comparison_data['type'], 'device_comparison')
        self.assertIn('desktop', comparison_data['data'])
        self.assertIn('mobile', comparison_data['data'])
        self.assertIn('tablet', comparison_data['data'])
        
        # Verify session counts
        self.assertEqual(comparison_data['data']['desktop']['session_count'], 1)
        self.assertEqual(comparison_data['data']['mobile']['session_count'], 1)
        self.assertEqual(comparison_data['data']['tablet']['session_count'], 1)


@pytest.mark.integration
class TestCompleteABTestingFlow(IntegrationTestCase):
    """Test complete A/B testing workflow"""
    
    def test_end_to_end_ab_testing_workflow(self):
        """Test complete A/B testing flow from creation to analysis"""
        # Step 1: Create A/B test experiment
        experiment = ExperimentFactory(
            name='E2E Test Experiment',
            status='running',
            is_active=True,
            target_percentage=100.0,
            primary_metric='signup',
            confidence_level=0.95
        )
        
        # Create control and test variants
        control = VariantFactory(
            experiment=experiment,
            name='Control',
            is_control=True,
            weight=50.0
        )
        
        test_variant = VariantFactory(
            experiment=experiment,
            name='Test Variant',
            is_control=False,
            weight=50.0,
            configuration={
                'button_color': 'green',
                'button_text': 'Sign Up Now!',
                'layout': 'centered'
            }
        )
        
        # Step 2: Initialize A/B testing engine
        engine = ABTestingEngine()
        
        # Step 3: Simulate user assignments and conversions
        users = [UserFactory() for _ in range(100)]
        assignments = []
        
        for user in users:
            assignment = engine.get_user_assignment(
                experiment=experiment,
                user=user,
                session_id=f'session_{user.id}'
            )
            
            self.assertIsNotNone(assignment)
            self.assertIn(assignment, [control, test_variant])
            
            assignments.append({
                'user': user,
                'variant': assignment
            })
            
            # Simulate conversions (test variant performs better)
            if assignment == test_variant and user.id % 3 == 0:  # 33% conversion
                success = engine.track_conversion(
                    user=user,
                    goal_type='signup',
                    goal_value=1.0,
                    metadata={'source': 'organic'}
                )
                self.assertTrue(success)
            elif assignment == control and user.id % 4 == 0:  # 25% conversion
                success = engine.track_conversion(
                    user=user,
                    goal_type='signup',
                    goal_value=1.0,
                    metadata={'source': 'organic'}
                )
                self.assertTrue(success)
        
        # Verify assignments were created
        total_assignments = Assignment.objects.filter(experiment=experiment).count()
        self.assertEqual(total_assignments, 100)
        
        # Verify conversions were tracked
        total_conversions = Conversion.objects.filter(
            assignment__experiment=experiment,
            goal_type='signup'
        ).count()
        self.assertGreater(total_conversions, 0)
        
        # Step 4: Analyze experiment results
        analyzer = ExperimentAnalyzer(experiment)
        results = analyzer.analyze()
        
        self.assertEqual(results['experiment'], 'E2E Test Experiment')
        self.assertEqual(results['status'], 'running')
        self.assertEqual(len(results['variants']), 2)
        
        # Verify variant data
        control_data = None
        test_data = None
        for variant_name, data in results['variants'].items():
            if data['is_control']:
                control_data = data
            else:
                test_data = data
        
        self.assertIsNotNone(control_data)
        self.assertIsNotNone(test_data)
        
        self.assertGreater(control_data['participants'], 0)
        self.assertGreater(test_data['participants'], 0)
        
        # Test variant should have higher conversion rate
        if test_data['conversions'] > 0 and control_data['conversions'] > 0:
            self.assertGreaterEqual(test_data['conversion_rate'], control_data['conversion_rate'])
        
        # Step 5: Check statistical analysis
        if results['statistical_analysis']:
            for variant_name, stats in results['statistical_analysis'].items():
                self.assertIn('p_value', stats)
                self.assertIn('lift_percentage', stats)
                self.assertIn('probability_better', stats)
        
        # Step 6: Verify result object was updated
        result_obj = ExperimentResult.objects.filter(experiment=experiment).first()
        self.assertIsNotNone(result_obj)
        self.assertGreater(result_obj.total_participants, 0)
        self.assertIsInstance(result_obj.variant_participants, dict)
        self.assertIsInstance(result_obj.variant_conversion_rates, dict)
        self.assertIsNotNone(result_obj.recommendation)
    
    def test_ab_testing_with_multiple_goals(self):
        """Test A/B testing with multiple conversion goals"""
        experiment = ExperimentFactory(
            status='running',
            is_active=True,
            primary_metric='purchase',
            secondary_metrics=['newsletter_signup', 'download']
        )
        
        control = VariantFactory(experiment=experiment, is_control=True, weight=50.0)
        test_variant = VariantFactory(experiment=experiment, is_control=False, weight=50.0)
        
        engine = ABTestingEngine()
        
        # Create users and assignments
        users = [UserFactory() for _ in range(50)]
        
        for user in users:
            variant = engine.get_user_assignment(
                experiment=experiment,
                user=user
            )
            
            # Track multiple types of conversions
            if user.id % 5 == 0:  # 20% purchase conversion
                engine.track_conversion(
                    user=user,
                    goal_type='purchase',
                    goal_value=99.99
                )
            
            if user.id % 3 == 0:  # 33% newsletter signup
                engine.track_conversion(
                    user=user,
                    goal_type='newsletter_signup'
                )
            
            if user.id % 4 == 0:  # 25% download
                engine.track_conversion(
                    user=user,
                    goal_type='download'
                )
        
        # Analyze results
        analyzer = ExperimentAnalyzer(experiment)
        results = analyzer.analyze()
        
        # Verify secondary metrics were analyzed
        self.assertIn('secondary_metrics', results)
        if results['secondary_metrics']:
            self.assertIn('newsletter_signup', results['secondary_metrics'])
            self.assertIn('download', results['secondary_metrics'])
    
    def test_ab_testing_user_exclusion_and_targeting(self):
        """Test A/B testing with user targeting and exclusion"""
        # Create experiment with user group targeting
        experiment = ExperimentFactory(
            status='running',
            is_active=True,
            target_percentage=50.0,  # Only 50% of users
            target_user_groups=['premium']
        )
        
        control = VariantFactory(experiment=experiment, is_control=True)
        test_variant = VariantFactory(experiment=experiment, is_control=False)
        
        # Create premium and basic users
        from django.contrib.auth.models import Group
        premium_group = Group.objects.create(name='premium')
        basic_group = Group.objects.create(name='basic')
        
        premium_users = [UserFactory() for _ in range(20)]
        basic_users = [UserFactory() for _ in range(20)]
        
        # Assign users to groups
        for user in premium_users:
            user.groups.add(premium_group)
        
        for user in basic_users:
            user.groups.add(basic_group)
        
        engine = ABTestingEngine()
        
        # Test assignments
        premium_assignments = 0
        basic_assignments = 0
        
        for user in premium_users:
            assignment = engine.get_user_assignment(experiment=experiment, user=user)
            if assignment:
                premium_assignments += 1
        
        for user in basic_users:
            assignment = engine.get_user_assignment(experiment=experiment, user=user)
            if assignment:
                basic_assignments += 1
        
        # Premium users should have assignments, basic users should not
        self.assertGreater(premium_assignments, 0)
        self.assertEqual(basic_assignments, 0)


@pytest.mark.integration
class TestCombinedAnalyticsFlow(IntegrationTestCase):
    """Test combined heatmap and A/B testing analytics"""
    
    def test_integrated_analytics_workflow(self):
        """Test workflow combining heatmap tracking with A/B testing"""
        # Create A/B test experiment for navigation
        experiment = ExperimentFactory(
            name='Navigation A/B Test',
            status='running',
            is_active=True,
            experiment_type='navigation',
            primary_metric='click_through_rate'
        )
        
        control = VariantFactory(
            experiment=experiment,
            name='Original Navigation',
            is_control=True,
            navigation_config={
                'menu_style': 'horizontal',
                'menu_position': 'top',
                'items': [
                    {'label': 'Home', 'url': '/'},
                    {'label': 'Products', 'url': '/products/'},
                    {'label': 'About', 'url': '/about/'}
                ]
            }
        )
        
        test_variant = VariantFactory(
            experiment=experiment,
            name='Vertical Navigation',
            is_control=False,
            navigation_config={
                'menu_style': 'vertical',
                'menu_position': 'left',
                'items': [
                    {'label': 'Home', 'url': '/'},
                    {'label': 'Products', 'url': '/products/'},
                    {'label': 'About', 'url': '/about/'},
                    {'label': 'Contact', 'url': '/contact/'}
                ]
            }
        )
        
        engine = ABTestingEngine()
        
        # Create users and simulate combined workflow
        users = [UserFactory() for _ in range(30)]
        
        for user in users:
            # Step 1: Get A/B test assignment
            assigned_variant = engine.get_user_assignment(
                experiment=experiment,
                user=user
            )
            
            self.assertIsNotNone(assigned_variant)
            
            # Step 2: Create heatmap session based on variant
            page_url = '/landing-page/'
            device_type = 'desktop' if user.id % 2 == 0 else 'mobile'
            
            # Simulate different user behavior based on variant
            if assigned_variant == control:
                # Original navigation - users scroll more, click less
                session = create_complete_session_with_data(
                    user=user,
                    page_url=page_url,
                    device_type=device_type,
                    num_clicks=3,
                    num_scrolls=8,
                    num_interactions=2
                )
            else:
                # Vertical navigation - users click more, scroll less
                session = create_complete_session_with_data(
                    user=user,
                    page_url=page_url,
                    device_type=device_type,
                    num_clicks=6,
                    num_scrolls=4,
                    num_interactions=4
                )
            
            # Step 3: Track conversions based on behavior
            if assigned_variant == test_variant and user.id % 3 == 0:
                # Vertical nav has better conversion
                engine.track_conversion(
                    user=user,
                    goal_type='click_through_rate',
                    goal_value=1.0
                )
            elif assigned_variant == control and user.id % 5 == 0:
                # Original nav has lower conversion
                engine.track_conversion(
                    user=user,
                    goal_type='click_through_rate',
                    goal_value=1.0
                )
        
        # Analyze A/B test results
        analyzer = ExperimentAnalyzer(experiment)
        ab_results = analyzer.analyze()
        
        self.assertEqual(len(ab_results['variants']), 2)
        
        # Analyze heatmap data
        self.client.force_login(self.staff_user)
        
        heatmap_response = self.client.get(
            f'/api/heatmap/data/?page_url={page_url}&type=click'
        )
        self.assertEqual(heatmap_response.status_code, 200)
        
        heatmap_data = json.loads(heatmap_response.content)
        self.assertGreater(heatmap_data['session_count'], 0)
        self.assertGreater(heatmap_data['total_clicks'], 0)
        
        # Compare behavior across A/B test variants
        # This would typically involve more complex analysis
        # correlating A/B test assignments with heatmap behavior patterns
        
        # Verify both systems captured data for all users
        total_assignments = Assignment.objects.filter(experiment=experiment).count()
        total_sessions = HeatmapSession.objects.filter(page_url=page_url).count()
        
        self.assertEqual(total_assignments, 30)
        self.assertEqual(total_sessions, 30)


@pytest.mark.integration
class TestSystemPerformanceAndScaling(IntegrationTestCase):
    """Test system performance under load"""
    
    def test_concurrent_heatmap_sessions(self):
        """Test system handling multiple concurrent heatmap sessions"""
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def create_heatmap_session(session_id, user_id):
            """Create heatmap session in thread"""
            try:
                user = UserFactory(username=f'user_{user_id}')
                client = Client()
                client.force_login(user)
                
                # Initialize session
                session_data = {
                    'sessionId': f'concurrent_session_{session_id}',
                    'pageUrl': '/concurrent-test/',
                    'pageTitle': 'Concurrent Test',
                    'viewport': {'width': 1920, 'height': 1080},
                    'screen': {'width': 1920, 'height': 1080},
                    'deviceType': 'desktop'
                }
                
                init_response = client.post(
                    '/api/heatmap/session/init/',
                    data=json.dumps(session_data),
                    content_type='application/json'
                )
                
                # Track data
                if init_response.status_code == 200:
                    track_data = {
                        'sessionId': f'concurrent_session_{session_id}',
                        'clicks': [{
                            'x': 0.5, 'y': 0.3, 'absoluteX': 960, 'absoluteY': 324,
                            'element': {
                                'tagName': 'button', 'id': f'btn_{session_id}',
                                'className': 'test-btn', 'text': 'Click me',
                                'isNavigation': False
                            },
                            'timeSinceLoad': 1000, 'clickType': 'left'
                        }]
                    }
                    
                    track_response = client.post(
                        '/api/heatmap/track/',
                        data=json.dumps(track_data),
                        content_type='application/json'
                    )
                    
                    results_queue.put({
                        'session_id': session_id,
                        'init_status': init_response.status_code,
                        'track_status': track_response.status_code
                    })
                else:
                    results_queue.put({
                        'session_id': session_id,
                        'init_status': init_response.status_code,
                        'track_status': None
                    })
                    
            except Exception as e:
                results_queue.put({
                    'session_id': session_id,
                    'error': str(e)
                })
        
        # Create multiple concurrent threads
        threads = []
        num_threads = 10
        
        start_time = time.time()
        
        for i in range(num_threads):
            thread = threading.Thread(
                target=create_heatmap_session,
                args=(i, i)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # Verify all sessions were processed successfully
        successful_sessions = [r for r in results if r.get('init_status') == 200]
        self.assertEqual(len(successful_sessions), num_threads)
        
        # Performance should be reasonable
        self.assertLess(total_time, 30)  # All should complete within 30 seconds
        
        # Verify data was actually stored
        concurrent_sessions = HeatmapSession.objects.filter(
            session_id__startswith='concurrent_session_'
        )
        self.assertEqual(concurrent_sessions.count(), num_threads)
    
    def test_large_dataset_processing(self):
        """Test system performance with large datasets"""
        # Create large dataset
        page_url = '/performance-test/'
        num_sessions = 50
        
        start_time = time.time()
        
        # Create sessions with substantial data
        for i in range(num_sessions):
            create_complete_session_with_data(
                page_url=page_url,
                num_clicks=20,
                num_scrolls=15,
                num_interactions=10
            )
        
        creation_time = time.time() - start_time
        
        # Test dashboard performance with large dataset
        self.client.force_login(self.staff_user)
        
        dashboard_start = time.time()
        dashboard_response = self.client.get('/heatmap/dashboard/')
        dashboard_time = time.time() - dashboard_start
        
        # Test API performance
        api_start = time.time()
        api_response = self.client.get(
            f'/api/heatmap/data/?page_url={page_url}&type=click'
        )
        api_time = time.time() - api_start
        
        # Performance assertions
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(api_response.status_code, 200)
        
        # Should handle large datasets reasonably fast
        self.assertLess(dashboard_time, 10)  # Dashboard should load within 10 seconds
        self.assertLess(api_time, 15)  # API should respond within 15 seconds
        
        # Verify data integrity
        api_data = json.loads(api_response.content)
        self.assertEqual(api_data['session_count'], num_sessions)
        self.assertEqual(api_data['total_clicks'], num_sessions * 20)


@pytest.mark.integration
class TestErrorRecoveryAndResilience(IntegrationTestCase):
    """Test system error recovery and resilience"""
    
    def test_database_error_recovery(self):
        """Test system recovery from database errors"""
        self.client.force_login(self.regular_user)
        
        # Simulate database error during session creation
        with patch('apps.core.models.heatmap.HeatmapSession.objects.create') as mock_create:
            mock_create.side_effect = Exception('Database connection failed')
            
            session_data = {
                'sessionId': 'error-test-session',
                'pageUrl': '/error-test/',
                'pageTitle': 'Error Test',
                'viewport': {'width': 1920, 'height': 1080},
                'screen': {'width': 1920, 'height': 1080},
                'deviceType': 'desktop'
            }
            
            response = self.client.post(
                '/api/heatmap/session/init/',
                data=json.dumps(session_data),
                content_type='application/json'
            )
            
            # Should handle error gracefully
            self.assertEqual(response.status_code, 500)
            error_data = json.loads(response.content)
            self.assertIn('error', error_data)
    
    def test_malformed_data_handling(self):
        """Test handling of malformed data"""
        self.client.force_login(self.regular_user)
        
        # Test malformed JSON
        malformed_requests = [
            ('{"incomplete": json', 'Invalid JSON'),
            ('{"sessionId": null}', 'Missing required fields'),
            ('[]', 'Wrong data structure'),
        ]
        
        for malformed_data, expected_error_type in malformed_requests:
            response = self.client.post(
                '/api/heatmap/session/init/',
                data=malformed_data,
                content_type='application/json'
            )
            
            # Should handle malformed data gracefully
            self.assertIn(response.status_code, [400, 500])
    
    def test_system_under_memory_pressure(self):
        """Test system behavior under memory pressure"""
        # This test simulates memory pressure by creating large objects
        large_sessions = []
        
        try:
            # Create sessions with very large datasets
            for i in range(5):
                session = HeatmapSession.objects.create(
                    session_id=f'memory_test_{i}',
                    page_url='/memory-test/',
                    viewport_width=1920,
                    viewport_height=1080,
                    screen_width=1920,
                    screen_height=1080,
                    device_type='desktop'
                )
                
                # Create large number of interactions per session
                for j in range(100):
                    ClickHeatmap.objects.create(
                        session=session,
                        x_position=0.5,
                        y_position=0.5,
                        absolute_x=960,
                        absolute_y=540,
                        element_type='div',
                        element_id=f'element_{j}',
                        element_text='x' * 1000,  # Large text field
                        timestamp=timezone.now()
                    )
                
                large_sessions.append(session)
            
            # Test that system still responds
            self.client.force_login(self.staff_user)
            response = self.client.get(
                '/api/heatmap/data/?page_url=/memory-test/&type=click'
            )
            
            # Should still work despite large dataset
            self.assertEqual(response.status_code, 200)
            
        finally:
            # Cleanup large test data
            HeatmapSession.objects.filter(
                session_id__startswith='memory_test_'
            ).delete()


@pytest.mark.e2e
class TestEndToEndUserJourneys(IntegrationTestCase):
    """End-to-end tests simulating real user journeys"""
    
    def test_complete_user_journey_new_visitor(self):
        """Test complete journey of a new visitor"""
        # Step 1: Anonymous user visits landing page
        response = self.client.get('/')
        # Status might be 404 since route may not exist, but middleware should still track
        
        # Step 2: User interacts with heatmap tracking
        session_data = {
            'sessionId': 'new-visitor-session',
            'pageUrl': '/',
            'pageTitle': 'Home',
            'viewport': {'width': 1366, 'height': 768},
            'screen': {'width': 1366, 'height': 768},
            'deviceType': 'desktop'
        }
        
        init_response = self.client.post(
            '/api/heatmap/session/init/',
            data=json.dumps(session_data),
            content_type='application/json'
        )
        
        if init_response.status_code == 200:
            # Step 3: User browses and interacts
            interaction_data = {
                'sessionId': 'new-visitor-session',
                'clicks': [
                    {
                        'x': 0.8, 'y': 0.1, 'absoluteX': 1093, 'absoluteY': 77,
                        'element': {
                            'tagName': 'a', 'id': 'signup-link', 'className': 'nav-link',
                            'text': 'Sign Up', 'isNavigation': True
                        },
                        'timeSinceLoad': 3000, 'clickType': 'left'
                    }
                ],
                'scrolls': [
                    {'scrollDepthPixels': 400, 'scrollDepthPercentage': 52.1, 'velocity': 150}
                ]
            }
            
            track_response = self.client.post(
                '/api/heatmap/track/',
                data=json.dumps(interaction_data),
                content_type='application/json'
            )
            
            self.assertEqual(track_response.status_code, 200)
            
            # Step 4: User signs up (conversion)
            # This would typically involve actual signup process
            # For test, we'll simulate the conversion tracking
            
            # Step 5: End heatmap session
            end_response = self.client.post(
                '/api/heatmap/session/end/',
                data=json.dumps({'sessionId': 'new-visitor-session'}),
                content_type='application/json'
            )
            
            self.assertEqual(end_response.status_code, 200)
            
            # Verify journey was captured
            session = HeatmapSession.objects.filter(
                session_id='new-visitor-session'
            ).first()
            
            if session:
                self.assertFalse(session.is_active)
                self.assertIsNone(session.user)  # Anonymous user
                clicks = ClickHeatmap.objects.filter(session=session)
                self.assertGreater(clicks.count(), 0)
                
                signup_click = clicks.filter(element_id='signup-link').first()
                self.assertIsNotNone(signup_click)
                self.assertTrue(signup_click.is_navigation)
    
    def test_returning_user_journey_with_ab_test(self):
        """Test returning user journey with A/B test participation"""
        # Step 1: Create user account
        user = UserFactory(username='returning_user')
        
        # Step 2: Create A/B test for returning users
        experiment = ExperimentFactory(
            name='Returning User Layout Test',
            status='running',
            is_active=True,
            primary_metric='engagement'
        )
        
        control = VariantFactory(experiment=experiment, is_control=True)
        test_variant = VariantFactory(experiment=experiment, is_control=False)
        
        # Step 3: User logs in and gets assigned to A/B test
        self.client.force_login(user)
        
        engine = ABTestingEngine()
        assigned_variant = engine.get_user_assignment(
            experiment=experiment,
            user=user
        )
        
        self.assertIsNotNone(assigned_variant)
        
        # Step 4: User interacts based on A/B test variant
        session_data = {
            'sessionId': f'returning-user-{user.id}',
            'pageUrl': '/dashboard/',
            'pageTitle': 'Dashboard',
            'viewport': {'width': 1920, 'height': 1080},
            'screen': {'width': 1920, 'height': 1080},
            'deviceType': 'desktop'
        }
        
        init_response = self.client.post(
            '/api/heatmap/session/init/',
            data=json.dumps(session_data),
            content_type='application/json'
        )
        
        if init_response.status_code == 200:
            # Different interaction patterns based on variant
            if assigned_variant == test_variant:
                # Test variant: more engaged behavior
                interactions = {
                    'sessionId': f'returning-user-{user.id}',
                    'clicks': [
                        {
                            'x': 0.3, 'y': 0.4, 'absoluteX': 576, 'absoluteY': 432,
                            'element': {
                                'tagName': 'button', 'id': 'feature-btn',
                                'className': 'btn-feature', 'text': 'Try Feature',
                                'isNavigation': False
                            },
                            'timeSinceLoad': 2000, 'clickType': 'left'
                        },
                        {
                            'x': 0.6, 'y': 0.7, 'absoluteX': 1152, 'absoluteY': 756,
                            'element': {
                                'tagName': 'a', 'id': 'explore-link',
                                'className': 'explore-more', 'text': 'Explore More',
                                'isNavigation': True
                            },
                            'timeSinceLoad': 5000, 'clickType': 'left'
                        }
                    ],
                    'interactions': [
                        {
                            'element': {
                                'selector': '#search-input', 'tagName': 'input',
                                'id': 'search-input', 'className': 'search-field',
                                'text': 'advanced features'
                            },
                            'interactionType': 'change', 'duration': 10.5
                        }
                    ]
                }
            else:
                # Control variant: standard behavior
                interactions = {
                    'sessionId': f'returning-user-{user.id}',
                    'clicks': [
                        {
                            'x': 0.2, 'y': 0.3, 'absoluteX': 384, 'absoluteY': 324,
                            'element': {
                                'tagName': 'a', 'id': 'home-link',
                                'className': 'nav-home', 'text': 'Home',
                                'isNavigation': True
                            },
                            'timeSinceLoad': 4000, 'clickType': 'left'
                        }
                    ]
                }
            
            track_response = self.client.post(
                '/api/heatmap/track/',
                data=json.dumps(interactions),
                content_type='application/json'
            )
            
            self.assertEqual(track_response.status_code, 200)
            
            # Step 5: Track conversion based on engagement
            if assigned_variant == test_variant and len(interactions['clicks']) > 1:
                success = engine.track_conversion(
                    user=user,
                    goal_type='engagement',
                    goal_value=1.0
                )
                self.assertTrue(success)
            
            # Step 6: End session
            end_response = self.client.post(
                '/api/heatmap/session/end/',
                data=json.dumps({'sessionId': f'returning-user-{user.id}'}),
                content_type='application/json'
            )
            
            # Verify complete journey data
            assignment = Assignment.objects.filter(
                experiment=experiment,
                user=user
            ).first()
            self.assertIsNotNone(assignment)
            
            session = HeatmapSession.objects.filter(
                session_id=f'returning-user-{user.id}'
            ).first()
            
            if session:
                self.assertEqual(session.user, user)
                self.assertFalse(session.is_active)
                
                # Verify different behavior patterns were captured
                clicks = ClickHeatmap.objects.filter(session=session)
                if assigned_variant == test_variant:
                    self.assertGreaterEqual(clicks.count(), 2)
                else:
                    self.assertEqual(clicks.count(), 1)
    
    def tearDown(self):
        """Clean up after tests"""
        super().tearDown()
        # Additional cleanup if needed
        cache.clear()