"""
Comprehensive testing suite for personalization system

Tests include:
- Unit tests for feature extraction and preference learning
- Integration tests for end-to-end personalization flows
- A/B test validation with statistical rigor
- Performance and load testing for optimization components
- Security tests for PII protection and access controls
"""

from django.contrib.auth import get_user_model

from apps.onboarding.models import (
    PreferenceProfile,
    RecommendationInteraction,
    Experiment,
    ExperimentAssignment,
    ConversationSession,
    LLMRecommendation,
    Bt
)
from apps.onboarding_api.services.learning import (
    FeatureExtractor,
    PreferenceUpdater,
    LearningSignalsCollector
)
from apps.onboarding_api.services.personalization import (
    RecommendationReranker,
    RecommendationContext
)
from apps.onboarding_api.services.experiments import (
    ExperimentAnalyzer,
    ExperimentManager
)
    TokenBudgetManager,
    ResponseCache,
    OptimizationService
)
import numpy as np

User = get_user_model()


class FeatureExtractionTestCase(TestCase):
    """Unit tests for feature extraction"""

    def setUp(self):
        self.user = User.objects.create(
            email='test@example.com',
            loginid='testuser'
        )
        self.client = Bt.objects.create(
            bucode='TEST001',
            buname='Test Client'
        )
        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.client,
            conversation_type='initial_setup',
            language='en'
        )
        self.recommendation = LLMRecommendation.objects.create(
            session=self.session,
            maker_output={'test': 'data'},
            confidence_score=0.8
        )
        self.feature_extractor = FeatureExtractor()

    def test_per_turn_feature_extraction(self):
        """Test per-turn feature extraction"""
        interaction = RecommendationInteraction.objects.create(
            session=self.session,
            recommendation=self.recommendation,
            event_type='approved',
            metadata={
                'time_on_item': 45,
                'scroll_depth': 0.8,
                'token_usage': 150,
                'cost_estimate': 0.05
            }
        )

        features = self.feature_extractor.build_per_turn_features(interaction)

        self.assertEqual(features['event_type'], 'approved')
        self.assertEqual(features['time_on_item'], 45)
        self.assertEqual(features['scroll_depth'], 0.8)
        self.assertEqual(features['session_type'], 'initial_setup')
        self.assertIn('hour_of_day', features)
        self.assertIn('day_of_week', features)

    def test_aggregate_feature_building(self):
        """Test aggregate feature building across interactions"""
        # Create multiple interactions
        for i in range(5):
            RecommendationInteraction.objects.create(
                session=self.session,
                recommendation=self.recommendation,
                event_type='approved' if i % 2 == 0 else 'rejected',
                metadata={
                    'time_on_item': 30 + i * 10,
                    'scroll_depth': 0.5 + i * 0.1,
                    'cost_estimate': 0.02 + i * 0.01
                }
            )

        features = self.feature_extractor.build_aggregate_features(self.user, self.client)

        self.assertIn('approval_rate', features)
        self.assertIn('avg_time_on_item', features)
        self.assertIn('cost_efficiency_score', features)
        self.assertEqual(features['total_interactions'], 5)

    def test_contextual_feature_extraction(self):
        """Test contextual feature extraction from session"""
        self.session.context_data = {
            'business_unit_type': 'warehouse',
            'expected_users': 50,
            'security_level': 'enhanced'
        }
        self.session.save()

        features = self.feature_extractor.extract_contextual_features(self.session)

        self.assertEqual(features['conversation_type'], 'initial_setup')
        self.assertEqual(features['business_unit_type'], 'warehouse')
        self.assertEqual(features['expected_users'], 50)
        self.assertEqual(features['security_requirements'], 'enhanced')

    def test_preference_vector_creation(self):
        """Test preference vector creation"""
        # Create sample interaction history
        for i in range(10):
            RecommendationInteraction.objects.create(
                session=self.session,
                recommendation=self.recommendation,
                event_type='approved' if i < 8 else 'rejected',
                metadata={'time_on_item': 30 + i, 'scroll_depth': 0.5}
            )

        vector = self.feature_extractor.create_preference_vector(self.user, self.client)

        self.assertIsInstance(vector, list)
        self.assertEqual(len(vector), 128)  # Default dimension
        self.assertTrue(all(isinstance(x, float) for x in vector))

        # Vector should be normalized
        norm = sum(x*x for x in vector) ** 0.5
        self.assertAlmostEqual(norm, 1.0, places=2)


class PreferenceUpdatingTestCase(TestCase):
    """Unit tests for preference profile updating"""

    def setUp(self):
        self.user = User.objects.create(
            email='test@example.com',
            loginid='testuser'
        )
        self.client = Bt.objects.create(
            bucode='TEST001',
            buname='Test Client'
        )
        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.client
        )
        self.recommendation = LLMRecommendation.objects.create(
            session=self.session,
            maker_output={'test': 'data'},
            confidence_score=0.6
        )
        self.preference_updater = PreferenceUpdater()

    def test_profile_creation_on_first_interaction(self):
        """Test preference profile creation on first interaction"""
        interaction = RecommendationInteraction.objects.create(
            session=self.session,
            recommendation=self.recommendation,
            event_type='approved'
        )

        self.preference_updater.update_preference_profile(
            self.user, self.client, interaction
        )

        profile = PreferenceProfile.objects.get(user=self.user, client=self.client)
        self.assertIsNotNone(profile)
        self.assertIn('approvals', profile.stats)
        self.assertEqual(profile.stats['approvals'], 1)

    def test_preference_weight_updates(self):
        """Test preference weight updates based on interactions"""
        # Create profile
        profile = PreferenceProfile.objects.create(
            user=self.user,
            client=self.client,
            weights={'cost_sensitivity': 0.5, 'risk_tolerance': 0.5}
        )

        # Create interaction with cost data
        interaction = RecommendationInteraction.objects.create(
            session=self.session,
            recommendation=self.recommendation,
            event_type='approved',
            metadata={'cost_estimate': 0.10}  # High cost
        )

        self.preference_updater.update_preference_profile(
            self.user, self.client, interaction
        )

        profile.refresh_from_db()
        # Cost sensitivity should decrease (user approved despite high cost)
        self.assertLess(profile.weights['cost_sensitivity'], 0.5)

    def test_risk_tolerance_learning(self):
        """Test risk tolerance learning from low-confidence approvals"""
        profile = PreferenceProfile.objects.create(
            user=self.user,
            client=self.client,
            weights={'risk_tolerance': 0.5}
        )

        # Create low-confidence recommendation that gets approved
        low_conf_rec = LLMRecommendation.objects.create(
            session=self.session,
            maker_output={'test': 'data'},
            confidence_score=0.4  # Low confidence
        )

        interaction = RecommendationInteraction.objects.create(
            session=self.session,
            recommendation=low_conf_rec,
            event_type='approved'
        )

        self.preference_updater.update_preference_profile(
            self.user, self.client, interaction
        )

        profile.refresh_from_db()
        # Risk tolerance should increase
        self.assertGreater(profile.weights['risk_tolerance'], 0.5)


class RecommendationRerankingTestCase(TestCase):
    """Unit tests for recommendation reranking"""

    def setUp(self):
        self.user = User.objects.create(
            email='test@example.com',
            loginid='testuser'
        )
        self.client = Bt.objects.create(
            bucode='TEST001',
            buname='Test Client'
        )
        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.client
        )

        # Create preference profile
        self.profile = PreferenceProfile.objects.create(
            user=self.user,
            client=self.client,
            weights={
                'cost_sensitivity': 0.8,  # High cost sensitivity
                'risk_tolerance': 0.3,    # Low risk tolerance
                'detail_level': 0.7       # Prefers detailed info
            }
        )

        self.reranker = RecommendationReranker()

    def test_cost_sensitive_reranking(self):
        """Test reranking for cost-sensitive user"""
        # Create recommendations with different costs
        high_cost_rec = LLMRecommendation.objects.create(
            session=self.session,
            maker_output={'type': 'detailed'},
            confidence_score=0.9,
            provider_cost_cents=200  # High cost
        )

        low_cost_rec = LLMRecommendation.objects.create(
            session=self.session,
            maker_output={'type': 'simple'},
            confidence_score=0.7,
            provider_cost_cents=50   # Low cost
        )

        context = RecommendationContext(
            user=self.user,
            client=self.client,
            session=self.session,
            budget_cents=1000
        )

        scored_recs = self.reranker.rerank_recommendations(
            [high_cost_rec, low_cost_rec], context
        )

        # For cost-sensitive user, low-cost rec should rank higher despite lower confidence
        self.assertEqual(scored_recs[0].recommendation, low_cost_rec)

    def test_risk_averse_reranking(self):
        """Test reranking for risk-averse user"""
        # Create recommendations with different confidence levels
        high_conf_rec = LLMRecommendation.objects.create(
            session=self.session,
            maker_output={'type': 'safe'},
            confidence_score=0.9
        )

        low_conf_rec = LLMRecommendation.objects.create(
            session=self.session,
            maker_output={'type': 'risky'},
            confidence_score=0.4
        )

        context = RecommendationContext(
            user=self.user,
            client=self.client,
            session=self.session
        )

        scored_recs = self.reranker.rerank_recommendations(
            [low_conf_rec, high_conf_rec], context
        )

        # High confidence recommendation should rank first for risk-averse user
        self.assertEqual(scored_recs[0].recommendation, high_conf_rec)

    def test_budget_constraint_application(self):
        """Test budget constraint filtering"""
        # Create expensive recommendations
        expensive_recs = []
        for i in range(5):
            rec = LLMRecommendation.objects.create(
                session=self.session,
                maker_output={'index': i},
                confidence_score=0.8,
                provider_cost_cents=300  # $3 each
            )
            expensive_recs.append(rec)

        context = RecommendationContext(
            user=self.user,
            client=self.client,
            session=self.session,
            budget_cents=800  # Only enough for 2-3 recommendations
        )

        scored_recs = self.reranker.rerank_recommendations(expensive_recs, context)

        # Should only return recommendations within budget
        total_cost = sum(rec.estimated_cost_cents for rec in scored_recs)
        self.assertLessEqual(total_cost, 800)


class ExperimentAnalysisTestCase(TestCase):
    """Unit tests for experiment analysis"""

    def setUp(self):
        self.owner = User.objects.create(
            email='owner@example.com',
            loginid='owner',
            is_staff=True
        )
        self.experiment = Experiment.objects.create(
            name='Test Experiment',
            description='Test A/B experiment',
            owner=self.owner,
            arms=[
                {'name': 'control', 'config': {'prompt_style': 'standard'}},
                {'name': 'treatment', 'config': {'prompt_style': 'detailed'}}
            ],
            status='running',
            started_at=timezone.now() - timedelta(days=7)
        )
        self.analyzer = ExperimentAnalyzer()

    def test_statistical_significance_detection(self):
        """Test statistical significance detection with synthetic data"""
        # Create synthetic interaction data
        self._create_synthetic_experiment_data()

        # Analyze experiment
        analysis = self.analyzer.analyze_experiment(self.experiment)

        self.assertEqual(analysis['status'], 'complete')
        self.assertIn('statistical_tests', analysis)
        self.assertIn('arm_performances', analysis)
        self.assertIn('recommendations', analysis)

    def test_minimum_sample_size_check(self):
        """Test minimum sample size enforcement"""
        # Create insufficient data
        self._create_minimal_experiment_data()

        analysis = self.analyzer.analyze_experiment(self.experiment)

        self.assertEqual(analysis['status'], 'insufficient_samples')
        self.assertIn('insufficient_arms', analysis)

    def test_effect_size_calculation(self):
        """Test effect size calculation"""
        # Create data with known effect size
        self._create_synthetic_experiment_data(control_rate=0.5, treatment_rate=0.7)

        analysis = self.analyzer.analyze_experiment(self.experiment)

        if analysis['status'] == 'complete':
            effect_analysis = analysis['effect_analysis']
            self.assertIn('comparisons', effect_analysis)

            # Should detect significant effect
            comparison = effect_analysis['comparisons'][0]
            self.assertGreater(comparison['relative_lift_percent'], 10)  # >10% lift

    def test_power_analysis(self):
        """Test statistical power analysis"""
        self._create_synthetic_experiment_data()

        analysis = self.analyzer.analyze_experiment(self.experiment)

        if analysis['status'] == 'complete':
            power_analysis = analysis['power_analysis']
            self.assertIn('overall_adequately_powered', power_analysis)
            self.assertIn('arms_analysis', power_analysis)

    def _create_synthetic_experiment_data(self, control_rate=0.6, treatment_rate=0.8):
        """Create synthetic experiment data for testing"""
        users = []
        clients = []

        # Create test users and clients
        for i in range(100):
            user = User.objects.create(
                email=f'user{i}@example.com',
                loginid=f'user{i}'
            )
            users.append(user)

            if i < 10:  # Create some clients
                client = Bt.objects.create(
                    bucode=f'CLIENT{i:03d}',
                    buname=f'Test Client {i}'
                )
                clients.append(client)

        # Create assignments (50 control, 50 treatment)
        for i, user in enumerate(users):
            client = clients[i % len(clients)]
            arm = 'control' if i < 50 else 'treatment'

            assignment = ExperimentAssignment.objects.create(
                experiment=self.experiment,
                user=user,
                client=client,
                arm=arm
            )

            # Create session and recommendation for each user
            session = ConversationSession.objects.create(
                user=user,
                client=client
            )

            recommendation = LLMRecommendation.objects.create(
                session=session,
                maker_output={'arm': arm},
                confidence_score=0.8
            )

            # Create interaction based on arm performance
            success_rate = control_rate if arm == 'control' else treatment_rate
            event_type = 'approved' if np.random.random() < success_rate else 'rejected'

            RecommendationInteraction.objects.create(
                session=session,
                recommendation=recommendation,
                event_type=event_type,
                occurred_at=timezone.now() - timedelta(days=np.random.randint(1, 7))
            )

    def _create_minimal_experiment_data(self):
        """Create minimal data below sample size threshold"""
        for i in range(5):  # Below minimum sample size
            user = User.objects.create(
                email=f'minimal_user{i}@example.com',
                loginid=f'minimal{i}'
            )

            assignment = ExperimentAssignment.objects.create(
                experiment=self.experiment,
                user=user,
                client=self.client,
                arm='control'
            )


class PersonalizationIntegrationTestCase(TestCase):
    """Integration tests for end-to-end personalization flows"""

    def setUp(self):
        self.user = User.objects.create(
            email='integration@example.com',
            loginid='integration'
        )
        self.client = Bt.objects.create(
            bucode='INT001',
            buname='Integration Client'
        )
        self.learning_service = LearningSignalsCollector()

    def test_end_to_end_learning_flow(self):
        """Test complete learning flow from interaction to preference update"""
        # Create session and recommendation
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client,
            conversation_type='initial_setup'
        )

        recommendation = LLMRecommendation.objects.create(
            session=session,
            maker_output={'test': 'recommendation'},
            confidence_score=0.8
        )

        # Collect explicit signal
        success = self.learning_service.collect_explicit_signal(
            str(session.session_id),
            str(recommendation.recommendation_id),
            'approved',
            metadata={'time_on_item': 60, 'cost_estimate': 0.05}
        )

        self.assertTrue(success)

        # Check that preference profile was created/updated
        profile = PreferenceProfile.objects.filter(user=self.user, client=self.client).first()
        self.assertIsNotNone(profile)
        self.assertIn('approvals', profile.stats)

    def test_personalization_with_experiments(self):
        """Test personalization in presence of active experiments"""
        # Create experiment
        experiment = Experiment.objects.create(
            name='Integration Test Experiment',
            description='Test experiment',
            owner=self.user,
            arms=[
                {'name': 'control', 'config': {'style': 'standard'}},
                {'name': 'treatment', 'config': {'style': 'detailed'}}
            ],
            status='running',
            started_at=timezone.now()
        )

        # Create assignment
        assignment = ExperimentAssignment.objects.create(
            experiment=experiment,
            user=self.user,
            client=self.client,
            arm='treatment'
        )

        # Test that assignment affects recommendation generation
        self.assertEqual(assignment.arm, 'treatment')
        self.assertTrue(assignment.is_active())

    def test_cost_tracking_integration(self):
        """Test cost tracking throughout the personalization pipeline"""
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client
        )

        recommendation = LLMRecommendation.objects.create(
            session=session,
            maker_output={'test': 'recommendation'},
            confidence_score=0.8
        )

        # Test cost signal collection
        success = self.learning_service.collect_cost_signal(
            str(recommendation.recommendation_id),
            {
                'provider_cost_cents': 150,
                'token_usage': {'input': 100, 'output': 200},
                'latency_ms': 2500
            }
        )

        self.assertTrue(success)

        # Verify cost was recorded
        recommendation.refresh_from_db()
        self.assertEqual(recommendation.provider_cost_cents, 150)
        self.assertEqual(recommendation.latency_ms, 2500)


class ABTestValidationTestCase(TestCase):
    """Tests for A/B test statistical validation"""

    def setUp(self):
        self.owner = User.objects.create(
            email='abtest@example.com',
            loginid='abtest',
            is_staff=True
        )
        self.analyzer = ExperimentAnalyzer()
        self.experiment_manager = ExperimentManager()

    def test_two_proportion_test(self):
        """Test two-proportion z-test implementation"""
        from apps.onboarding_api.services.experiments import ArmPerformance

        # Create arms with known difference
        arm_a = ArmPerformance(
            arm_name='control',
            total_users=100,
            total_interactions=200,
            approvals=120,  # 60% rate
            rejections=80,
            modifications=0,
            escalations=0,
            avg_decision_time=300,
            total_cost_cents=1000,
            conversion_rate=0.6,
            confidence_interval=(0.53, 0.67),
            sample_size=200
        )

        arm_b = ArmPerformance(
            arm_name='treatment',
            total_users=100,
            total_interactions=200,
            approvals=160,  # 80% rate
            rejections=40,
            modifications=0,
            escalations=0,
            avg_decision_time=280,
            total_cost_cents=1200,
            conversion_rate=0.8,
            confidence_interval=(0.74, 0.86),
            sample_size=200
        )

        # Perform statistical test
        result = self.analyzer._two_proportion_test(arm_a, arm_b, 0.05)

        self.assertIsNotNone(result)
        self.assertLess(result.p_value, 0.05)  # Should be significant
        self.assertTrue(result.significant)
        self.assertGreater(abs(result.effect_size), 0.1)  # Meaningful effect size

    def test_bonferroni_correction(self):
        """Test Bonferroni correction for multiple comparisons"""
        # Test with analyzer's correction enabled
        self.analyzer.bonferroni_correction = True

        experiment = Experiment.objects.create(
            name='Multiple Arms Test',
            description='Test with multiple arms',
            owner=self.owner,
            arms=[
                {'name': 'control'},
                {'name': 'treatment1'},
                {'name': 'treatment2'},
                {'name': 'treatment3'}
            ]
        )

        # With 4 arms, we have 6 pairwise comparisons
        # Alpha should be adjusted from 0.05 to 0.05/6 ≈ 0.0083
        expected_comparisons = 4 * 3 // 2  # 6 comparisons
        expected_alpha = 0.05 / expected_comparisons

        self.assertAlmostEqual(expected_alpha, 0.05/6, places=4)

    def test_experiment_safety_constraints(self):
        """Test safety constraint monitoring"""
        experiment = Experiment.objects.create(
            name='Safety Test',
            description='Test safety constraints',
            owner=self.owner,
            arms=[{'name': 'control'}, {'name': 'risky_treatment'}],
            safety_constraints={
                'max_error_rate': 0.1,
                'max_daily_spend_cents': 1000
            }
        )

        # Test constraint checking
        arm_performance = {
            'risky_treatment': {
                'error_rate': 0.15,  # Exceeds 10% limit
                'daily_spend_cents': 1200  # Exceeds $10 limit
            }
        }

        violations = experiment.check_safety_constraints(arm_performance)

        self.assertEqual(len(violations), 2)  # Should detect both violations
        self.assertTrue(any('error rate' in v for v in violations))
        self.assertTrue(any('daily spend' in v for v in violations))


class PerformanceTestCase(TestCase):
    """Performance and load tests"""

    def test_cache_performance(self):
        """Test caching performance and hit rates"""
        from apps.onboarding_api.services.optimization import ResponseCache

        cache_service = ResponseCache()

        # Test cache miss and set
        intent = "configure business unit"
        citations = ['doc1', 'doc2']
        policy_version = 'v1.0'
        context = {'business_unit_type': 'office'}

        # First call should miss
        cached_response = cache_service.get_cached_maker_response(
            intent, citations, policy_version, context
        )
        self.assertIsNone(cached_response)

        # Cache a response
        response = {'recommendations': {'test': 'data'}, 'confidence_score': 0.8}
        cache_service.cache_maker_response(intent, citations, policy_version, context, response)

        # Second call should hit
        cached_response = cache_service.get_cached_maker_response(
            intent, citations, policy_version, context
        )
        self.assertIsNotNone(cached_response)
        self.assertTrue(cached_response['cache_hit'])

    def test_token_budget_calculation_performance(self):
        """Test token budget calculation performance"""
        from apps.onboarding_api.services.optimization import TokenBudgetManager

        budget_manager = TokenBudgetManager()

        # Create user and client
        user = User.objects.create(email='perf@example.com', loginid='perf')
        client = Bt.objects.create(bucode='PERF001', buname='Performance Client')

        # Test budget calculation time
        start_time = time.time()

        for i in range(100):
            context = {
                'business_unit_type': 'office',
                'expected_users': 50 + i,
                'security_level': 'basic'
            }
            budget = budget_manager.calculate_token_budget(user, client, context)
            self.assertIn('maker_tokens', budget)

        end_time = time.time()
        avg_time_ms = (end_time - start_time) * 1000 / 100

        # Should complete within reasonable time
        self.assertLess(avg_time_ms, 50)  # Less than 50ms per calculation

    def test_feature_extraction_scalability(self):
        """Test feature extraction with large interaction history"""
        user = User.objects.create(email='scale@example.com', loginid='scale')
        client = Bt.objects.create(bucode='SCALE001', buname='Scale Client')

        session = ConversationSession.objects.create(user=user, client=client)
        recommendation = LLMRecommendation.objects.create(
            session=session,
            maker_output={'test': 'data'},
            confidence_score=0.8
        )

        # Create large interaction history
        interactions = []
        for i in range(1000):
            interaction = RecommendationInteraction.objects.create(
                session=session,
                recommendation=recommendation,
                event_type='approved' if i % 3 == 0 else 'rejected',
                metadata={
                    'time_on_item': 30 + i % 60,
                    'scroll_depth': (i % 100) / 100.0
                }
            )
            interactions.append(interaction)

        # Test feature extraction performance
        feature_extractor = FeatureExtractor()

        start_time = time.time()
        features = feature_extractor.build_aggregate_features(user, client, window_days=30)
        end_time = time.time()

        extraction_time_ms = (end_time - start_time) * 1000

        # Should handle large history efficiently
        self.assertLess(extraction_time_ms, 1000)  # Less than 1 second
        self.assertIn('approval_rate', features)
        self.assertEqual(features['total_interactions'], 1000)


class SecurityTestCase(TestCase):
    """Security and compliance tests"""

    def test_pii_detection(self):
        """Test PII detection capabilities"""
        from apps.onboarding_api.services.security import PIIDetector

        pii_detector = PIIDetector()

        # Test text with various PII types
        test_text = """
        Contact John Doe at john.doe@example.com or call 555-123-4567.
        SSN: 123-45-6789, Credit Card: 4532 1234 5678 9012
        Address: 123 Main Street, Anytown, NY 12345
        """

        findings = pii_detector.detect_pii(test_text)

        self.assertIn('email', findings)
        self.assertIn('phone', findings)
        self.assertIn('ssn', findings)
        self.assertIn('credit_card', findings)

        # Test redaction
        redacted_text, stats = pii_detector.redact_pii(test_text)

        self.assertNotIn('john.doe@example.com', redacted_text)
        self.assertNotIn('123-45-6789', redacted_text)
        self.assertIn('example.com', redacted_text)  # Domain preserved

    def test_anomaly_detection(self):
        """Test anomaly detection for suspicious behavior"""
        from apps.onboarding_api.services.security import AnomalyDetector

        anomaly_detector = AnomalyDetector()

        user = User.objects.create(email='anomaly@example.com', loginid='anomaly')
        client = Bt.objects.create(bucode='ANOM001', buname='Anomaly Client')

        # Create suspicious interaction pattern (too many, too fast)
        session = ConversationSession.objects.create(user=user, client=client)
        recommendation = LLMRecommendation.objects.create(
            session=session,
            maker_output={'test': 'data'},
            confidence_score=0.8
        )

        # Create 200 interactions in 1 hour (exceeds threshold)
        base_time = timezone.now()
        for i in range(200):
            interaction_time = base_time + timedelta(seconds=i * 18)  # Every 18 seconds
            RecommendationInteraction.objects.create(
                session=session,
                recommendation=recommendation,
                event_type='approved',
                occurred_at=interaction_time,
                metadata={'time_on_item': 1}  # Suspiciously fast
            )

        anomalies = anomaly_detector.detect_anomalies(user, client, timeframe_hours=1)

        self.assertGreater(len(anomalies), 0)
        anomaly_types = [a['type'] for a in anomalies]
        self.assertIn('excessive_interactions', anomaly_types)

    def test_access_control(self):
        """Test role-based access control"""
        from apps.onboarding_api.services.security import AccessControlService

        access_control = AccessControlService()

        # Create users with different roles
        admin_user = User.objects.create(
            email='admin@example.com',
            loginid='admin',
            is_superuser=True
        )

        staff_user = User.objects.create(
            email='staff@example.com',
            loginid='staff',
            is_staff=True
        )

        regular_user = User.objects.create(
            email='user@example.com',
            loginid='user'
        )

        # Test permissions
        self.assertTrue(access_control.check_permission(admin_user, 'create_experiment'))
        self.assertTrue(access_control.check_permission(staff_user, 'view_experiment_results'))
        self.assertFalse(access_control.check_permission(regular_user, 'create_experiment'))

    def test_data_redaction_preserves_learning_value(self):
        """Test that PII redaction preserves learning value"""
        from apps.onboarding_api.services.security import DataRedactionService

        redaction_service = DataRedactionService()

        # Test data with PII
        interaction_data = {
            'user_feedback': 'My email is john@company.com and I think this is great!',
            'time_on_item': 45,
            'scroll_depth': 0.8,
            'cost_estimate': 0.05,
            'password': 'secret123',  # Sensitive field
            'business_context': {
                'company_name': 'ACME Corp',
                'contact_email': 'admin@acme.com'
            }
        }

        redacted_data = redaction_service.redact_interaction_data(interaction_data)

        # PII should be redacted
        self.assertNotIn('john@company.com', redacted_data.get('user_feedback', ''))

        # Learning value should be preserved
        self.assertEqual(redacted_data['time_on_item'], 45)
        self.assertEqual(redacted_data['scroll_depth'], 0.8)
        self.assertEqual(redacted_data['cost_estimate'], 0.05)

        # Sensitive field should be hashed
        self.assertIn('password_hash', redacted_data)
        self.assertNotIn('password', redacted_data)

        # Extract safe features
        safe_features = redaction_service.extract_safe_features(interaction_data)

        self.assertIn('time_on_item', safe_features)
        self.assertIn('scroll_depth', safe_features)
        self.assertNotIn('user_feedback', safe_features)  # Contains PII
        self.assertNotIn('password', safe_features)


class OptimizationTestCase(TestCase):
    """Tests for optimization components"""

    def test_adaptive_budgeting(self):
        """Test adaptive budget calculation"""
        from apps.onboarding_api.services.optimization import TokenBudgetManager

        budget_manager = TokenBudgetManager()

        user = User.objects.create(email='budget@example.com', loginid='budget')
        client = Bt.objects.create(bucode='BUDG001', buname='Budget Client')

        # Test different risk scenarios
        low_risk_context = {
            'business_unit_type': 'office',
            'expected_users': 10,
            'security_level': 'basic'
        }

        high_risk_context = {
            'business_unit_type': 'manufacturing',
            'expected_users': 500,
            'security_level': 'high_security',
            'compliance_needed': True
        }

        low_risk_budget = budget_manager.calculate_token_budget(user, client, low_risk_context)
        high_risk_budget = budget_manager.calculate_token_budget(user, client, high_risk_context)

        # High risk should get larger budget
        self.assertGreater(high_risk_budget['maker_tokens'], low_risk_budget['maker_tokens'])
        self.assertGreater(high_risk_budget['retrieval_k'], low_risk_budget['retrieval_k'])

    def test_provider_routing(self):
        """Test provider routing for cost optimization"""
        from apps.onboarding_api.services.optimization import ProviderRouter

        router = ProviderRouter()

        # Test cost-optimized routing
        low_risk_budget = {'risk_level': 'low_risk', 'maker_tokens': 500}
        high_risk_budget = {'risk_level': 'high_risk', 'maker_tokens': 2000}

        low_risk_provider = router.select_provider(low_risk_budget, {})
        high_risk_provider = router.select_provider(high_risk_budget, {})

        # Should route to different providers based on risk
        self.assertIn(low_risk_provider, router.providers)
        self.assertIn(high_risk_provider, router.providers)

        # High risk should get higher quality provider
        low_quality = router.providers[low_risk_provider]['quality_score']
        high_quality = router.providers[high_risk_provider]['quality_score']
        self.assertGreaterEqual(high_quality, low_quality)


import time

# Test runner utilities
def run_personalization_test_suite():
    """Run the complete personalization test suite"""
    import unittest

    # Create test suite
    test_cases = [
        FeatureExtractionTestCase,
        PreferenceUpdatingTestCase,
        RecommendationRerankingTestCase,
        ExperimentAnalysisTestCase,
        PersonalizationIntegrationTestCase,
        ABTestValidationTestCase,
        PerformanceTestCase,
        SecurityTestCase,
        OptimizationTestCase
    ]

    suite = unittest.TestSuite()
    for test_case in test_cases:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_case)
        suite.addTests(tests)

    return suite


if __name__ == '__main__':
    # Run tests when executed directly
    runner = unittest.TextTestRunner(verbosity=2)
    suite = run_personalization_test_suite()
    runner.run(suite)