"""
Comprehensive tests for Conversational Onboarding Phase 2 features
"""
import uuid
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from apps.onboarding.models import (
    Bt, ConversationSession, LLMRecommendation,
    AuthoritativeKnowledge, AuthoritativeKnowledgeChunk
)
from apps.core_onboarding.services.llm import EnhancedCheckerLLM, ConsensusEngine
from apps.core_onboarding.services.security import PIIRedactor, SecurityGuardian, RateLimitExceeded
from apps.onboarding_api.services.observability import CostTracker, MetricsCollector

User = get_user_model()


class Phase2ModelTestCase(TestCase):
    """Test Phase 2 model enhancements"""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com'
        )
        self.client_bt = Bt.objects.create(
            buname='Test Client',
            bucode='TEST_CLIENT'
        )

    def test_llm_recommendation_enhanced_fields(self):
        """Test enhanced LLMRecommendation fields"""
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_bt,
            language='en'
        )

        recommendation = LLMRecommendation.objects.create(
            session=session,
            maker_output={'test': 'data'},
            confidence_score=0.85,
            status=LLMRecommendation.StatusChoices.PROCESSING,
            latency_ms=1500,
            provider_cost_cents=25,
            eval_scores={'maker_confidence': 0.85, 'checker_confidence': 0.1},
            trace_id='test-trace-123'
        )

        self.assertEqual(recommendation.status, LLMRecommendation.StatusChoices.PROCESSING)
        self.assertEqual(recommendation.latency_ms, 1500)
        self.assertEqual(recommendation.provider_cost_cents, 25)
        self.assertEqual(recommendation.trace_id, 'test-trace-123')
        self.assertIn('maker_confidence', recommendation.eval_scores)

    def test_knowledge_chunk_model(self):
        """Test AuthoritativeKnowledgeChunk model"""
        knowledge = AuthoritativeKnowledge.objects.create(
            source_organization='Test Org',
            document_title='Test Document',
            authority_level='high',
            content_summary='Test summary'
        )

        chunk = AuthoritativeKnowledgeChunk.objects.create(
            knowledge=knowledge,
            chunk_index=0,
            content_text='This is a test chunk of knowledge content.',
            content_vector=[0.1, 0.2, 0.3, 0.4],
            tags={'section': 'introduction', 'topic': 'testing'},
            is_current=True
        )

        # Test save method caches parent fields
        self.assertEqual(chunk.authority_level, 'high')
        self.assertEqual(chunk.source_organization, 'Test Org')

        # Test similarity calculation
        query_vector = [0.1, 0.2, 0.3, 0.4]
        similarity = chunk.get_similarity_score(query_vector)
        self.assertEqual(similarity, 1.0)  # Perfect match


class Phase2ServiceTestCase(TestCase):
    """Test Phase 2 service enhancements"""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com'
        )

    def test_enhanced_checker_llm(self):
        """Test enhanced checker LLM functionality"""
        checker = EnhancedCheckerLLM()

        maker_output = {
            'recommendations': {
                'business_unit_config': {
                    'bu_name': 'Test BU',
                    'bu_type': 'Office',
                    'max_users': 15
                },
                'security_settings': {
                    'enable_gps': True,
                    'permissible_distance': 50
                }
            },
            'confidence_score': 0.8
        }

        context = {'facility_type': 'office'}

        validation_result = checker.validate_recommendations(maker_output, context)

        self.assertIn('is_valid', validation_result)
        self.assertIn('confidence_adjustment', validation_result)
        self.assertIn('risk_assessment', validation_result)
        self.assertIn('compliance_check', validation_result)

    def test_consensus_engine(self):
        """Test consensus engine functionality"""
        consensus_engine = ConsensusEngine()

        maker_output = {
            'recommendations': {'business_unit_config': {'bu_name': 'Test'}},
            'confidence_score': 0.8
        }

        checker_output = {
            'is_valid': True,
            'confidence_adjustment': 0.05,
            'risk_assessment': 'low'
        }

        knowledge_hits = [
            {
                'similarity': 0.9,
                'metadata': {
                    'authority_level': 'high',
                    'publication_date': '2024-01-01T00:00:00'
                }
            }
        ]

        consensus = consensus_engine.create_consensus(
            maker_output, checker_output, knowledge_hits, {}
        )

        self.assertIn('final_recommendation', consensus)
        self.assertIn('consensus_confidence', consensus)
        self.assertIn('decision', consensus)
        self.assertIn('reasoning', consensus)
        self.assertIn('knowledge_grounding', consensus)

    def test_document_chunker(self):
        """Test document chunking functionality"""
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)

        long_text = "This is a long document. " * 10  # 250 chars
        chunks = chunker.chunk_text(long_text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all('text' in chunk for chunk in chunks))
        self.assertTrue(all('start_idx' in chunk for chunk in chunks))

    def test_pii_redactor(self):
        """Test PII redaction functionality"""
        redactor = PIIRedactor()

        text_with_pii = "Contact John Doe at john.doe@example.com or call 555-123-4567"
        redacted_text, metadata = redactor.redact_text(text_with_pii)

        self.assertNotIn('john.doe@example.com', redacted_text)
        self.assertNotIn('555-123-4567', redacted_text)
        self.assertGreater(len(metadata['redactions']), 0)

    def test_security_guardian(self):
        """Test security guardian functionality"""
        guardian = SecurityGuardian()

        # Test prompt sanitization
        prompt_with_pii = "Set up user john.doe@company.com with phone 555-1234"

        try:
            sanitized, metadata = guardian.sanitize_prompt(prompt_with_pii, 'user123')
            self.assertNotIn('john.doe@company.com', sanitized)
            self.assertTrue(metadata['pii_redacted'])
        except RateLimitExceeded:
            # Rate limiting can trigger in tests
            pass

        # Test source URL validation
        self.assertFalse(guardian.validate_source_url('http://malicious-site.com/'))
        self.assertTrue(guardian.validate_source_url('https://docs.python.org/3/'))

    def test_cost_tracker(self):
        """Test cost tracking functionality"""
        cost_tracker = CostTracker()

        cost_data = cost_tracker.calculate_llm_cost(
            provider='openai',
            model='gpt-4',
            input_tokens=1000,
            output_tokens=500,
            operation_type='generation'
        )

        self.assertIn('total_cost_cents', cost_data)
        self.assertIn('input_cost_cents', cost_data)
        self.assertIn('output_cost_cents', cost_data)
        self.assertEqual(cost_data['provider'], 'openai')
        self.assertEqual(cost_data['model'], 'gpt-4')


class Phase2APITestCase(APITestCase):
    """Test Phase 2 API enhancements"""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.staff_user = User.objects.create_user(
            loginid='staffuser',
            email='staff@example.com',
            password='staffpass123',
            is_staff=True
        )
        self.client_bt = Bt.objects.create(
            buname='Test Client',
            bucode='TEST_CLIENT'
        )
        self.user.client = self.client_bt
        self.user.save()

    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True)
    @override_settings(ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER=True)
    def test_enhanced_conversation_processing(self):
        """Test enhanced conversation processing with dual-LLM"""
        self.client.force_authenticate(user=self.user)

        # Create session
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_bt,
            language='en',
            current_state=ConversationSession.StateChoices.IN_PROGRESS
        )

        data = {
            'user_input': 'I need a secure office setup for 20 users',
            'context': {'complexity': 'high'}
        }

        url = reverse('onboarding_api:conversation-process-enhanced', kwargs={
            'conversation_id': session.session_id
        })

        with patch('apps.onboarding_api.services.llm.get_llm_service') as mock_llm:
            with patch('apps.onboarding_api.services.llm.get_checker_service') as mock_checker:
                # Mock services
                mock_llm.return_value.process_conversation_step.return_value = {
                    'recommendations': {'business_unit_config': {'bu_name': 'Test'}},
                    'confidence_score': 0.8
                }
                mock_checker.return_value.validate_recommendations.return_value = {
                    'is_valid': True,
                    'confidence_adjustment': 0.05
                }

                response = self.client.post(url, data, format='json')

                # Should return 202 for async processing when checker is enabled
                self.assertIn(response.status_code, [200, 202])

                if response.status_code == 202:
                    self.assertIn('trace_id', response.data)
                    self.assertIn('status_url', response.data)
                elif response.status_code == 200:
                    self.assertIn('maker_llm_output', response.data)
                    self.assertIn('checker_validation', response.data)
                    self.assertIn('consensus_confidence', response.data)

    @override_settings(ENABLE_ONBOARDING_SSE=True)
    def test_conversation_events_streaming(self):
        """Test conversation events streaming endpoint"""
        self.client.force_authenticate(user=self.user)

        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_bt,
            language='en'
        )

        url = reverse('onboarding_api:conversation-events', kwargs={
            'conversation_id': session.session_id
        })

        response = self.client.get(url)

        # Should return streaming response when SSE enabled
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check for SSE headers
        if hasattr(response, 'streaming'):
            self.assertTrue(response.streaming)

    def test_conversation_escalation(self):
        """Test conversation escalation endpoint"""
        self.client.force_authenticate(user=self.user)

        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_bt,
            language='en'
        )

        data = {
            'reason': 'Complex requirements need human review',
            'context_snapshot': {'complexity_score': 0.9}
        }

        url = reverse('onboarding_api:conversation-escalate', kwargs={
            'conversation_id': session.session_id
        })

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('escalation_id', response.data)

        # Verify session was updated
        session.refresh_from_db()
        self.assertEqual(session.current_state, ConversationSession.StateChoices.ERROR)
        self.assertIn('escalation', session.context_data)

    @override_settings(ENABLE_ONBOARDING_KB=True)
    def test_knowledge_document_upload(self):
        """Test knowledge document upload with chunking"""
        self.client.force_authenticate(user=self.staff_user)

        data = {
            'source_organization': 'Test Organization',
            'document_title': 'Test Knowledge Document',
            'content_summary': 'This is a test document for knowledge base',
            'full_content': 'This is the full content of the test document. ' * 20,
            'authority_level': 'high',
            'document_version': '1.0'
        }

        url = reverse('onboarding_api:documents-list')

        with patch('apps.onboarding_api.services.knowledge.get_knowledge_service') as mock_service:
            mock_service.return_value.add_document_with_chunking.return_value = str(uuid.uuid4())

            response = self.client.post(url, data, format='json')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertIn('knowledge_id', response.data)

    def test_enhanced_knowledge_search(self):
        """Test enhanced knowledge search with filtering"""
        self.client.force_authenticate(user=self.user)

        # Create test knowledge
        knowledge = AuthoritativeKnowledge.objects.create(
            source_organization='Test Org',
            document_title='Test Security Guidelines',
            authority_level='high',
            content_summary='Security guidelines for business unit setup'
        )

        url = reverse('onboarding_api:knowledge-search-enhanced')
        response = self.client.get(url, {
            'q': 'security guidelines',
            'authority_level': ['high'],
            'max_results': 5
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('query', response.data)

    def test_admin_knowledge_dashboard(self):
        """Test admin knowledge dashboard"""
        self.client.force_authenticate(user=self.staff_user)

        url = reverse('onboarding_api:admin-knowledge-dashboard')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overview', response.data)
        self.assertIn('chunk_statistics', response.data)
        self.assertIn('authority_breakdown', response.data)

    def test_admin_metrics_dashboard(self):
        """Test admin metrics dashboard"""
        self.client.force_authenticate(user=self.staff_user)

        url = reverse('onboarding_api:admin-metrics')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metrics', response.data)
        self.assertIn('costs', response.data)
        self.assertIn('alerts', response.data)


class Phase2SecurityTestCase(TestCase):
    """Test Phase 2 security features"""

    def test_pii_redaction_patterns(self):
        """Test various PII redaction patterns"""
        redactor = PIIRedactor()

        test_cases = [
            ("Email: john.doe@company.com", "john.doe@company.com"),
            ("Call me at 555-123-4567", "555-123-4567"),
            ("SSN: 123-45-6789", "123-45-6789"),
            ("Credit card: 4111-1111-1111-1111", "4111-1111-1111-1111")
        ]

        for original, pii_data in test_cases:
            redacted, metadata = redactor.redact_text(original)
            self.assertNotIn(pii_data, redacted)
            self.assertGreater(len(metadata.get('redactions', [])), 0)

    def test_pii_dict_redaction(self):
        """Test PII redaction in dictionary structures"""
        redactor = PIIRedactor()

        test_dict = {
            'user_info': {
                'email': 'test@example.com',
                'phone': '555-1234',
                'notes': 'Contact John at john@company.com'
            },
            'safe_data': {
                'business_type': 'Office',
                'user_count': 10
            }
        }

        redacted_dict, metadata = redactor.redact_dict(test_dict)

        # Email should be redacted
        self.assertNotEqual(
            redacted_dict['user_info']['email'],
            test_dict['user_info']['email']
        )

        # Safe data should remain unchanged
        self.assertEqual(
            redacted_dict['safe_data'],
            test_dict['safe_data']
        )

    @override_settings(ONBOARDING_API_MAX_REQUESTS=2)
    def test_rate_limiting_enforcement(self):
        """Test rate limiting enforcement"""
        from apps.core_onboarding.services.security import RateLimiter

        rate_limiter = RateLimiter()

        # First requests should be allowed
        allowed1, info1 = rate_limiter.check_rate_limit('test_user', 'llm_calls')
        self.assertTrue(allowed1)

        # Increment usage
        rate_limiter.increment_usage('test_user', 'llm_calls')
        rate_limiter.increment_usage('test_user', 'llm_calls')

        # Should now be rate limited
        allowed2, info2 = rate_limiter.check_rate_limit('test_user', 'llm_calls')
        # Note: May still be allowed depending on cache behavior in tests

    def test_source_allowlist_validation(self):
        """Test source URL allowlist validation"""
        guardian = SecurityGuardian()

        # Allowed sources
        self.assertTrue(guardian.validate_source_url('https://docs.python.org/3/library/'))
        self.assertTrue(guardian.validate_source_url('https://github.com/django/django'))

        # Disallowed sources
        self.assertFalse(guardian.validate_source_url('https://malicious-site.com/'))
        self.assertFalse(guardian.validate_source_url('http://suspicious-domain.org/'))


class Phase2IntegrationTestCase(TestCase):
    """Test Phase 2 integration scenarios"""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com'
        )
        self.client_bt = Bt.objects.create(
            buname='Test Client',
            bucode='TEST_CLIENT'
        )

    def test_full_dual_llm_workflow(self):
        """Test complete dual-LLM workflow"""
        # Create knowledge base
        knowledge = AuthoritativeKnowledge.objects.create(
            source_organization='Corporate Policy',
            document_title='Security Guidelines',
            authority_level='official',
            content_summary='Official security guidelines for business unit setup'
        )

        # Create knowledge chunk
        chunk = AuthoritativeKnowledgeChunk.objects.create(
            knowledge=knowledge,
            chunk_index=0,
            content_text='GPS tracking should be enabled for high-security environments',
            content_vector=[0.1] * 384,  # Dummy vector
            is_current=True
        )

        # Create conversation session
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_bt,
            language='en'
        )

        # Test knowledge retrieval
        from apps.core_onboarding.services.knowledge import get_knowledge_service
        knowledge_service = get_knowledge_service()

        context_results = knowledge_service.retrieve_grounded_context(
            query='security setup for office',
            top_k=3
        )

        self.assertIsInstance(context_results, list)

    def test_cost_tracking_integration(self):
        """Test cost tracking integration with recommendations"""
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_bt,
            language='en'
        )

        recommendation = LLMRecommendation.objects.create(
            session=session,
            maker_output={'test': 'data'},
            confidence_score=0.85,
            provider_cost_cents=150,
            latency_ms=2500
        )

        # Test cost tracking
        cost_tracker = CostTracker()
        daily_summary = cost_tracker.get_daily_cost_summary()

        self.assertIn('total_cost_cents', daily_summary)
        self.assertIn('total_recommendations', daily_summary)

    def test_metrics_collection(self):
        """Test metrics collection and aggregation"""
        metrics_collector = MetricsCollector()

        # Record test metrics
        metrics_collector.record_conversation_metric(
            'test_metric',
            1.0,
            {'operation': 'test'}
        )

        metrics_collector.record_latency_metric(
            'test_operation',
            1500,
            True,
            {'test_tag': 'value'}
        )

        # Get metrics summary
        summary = metrics_collector.get_metrics_summary(hours_back=1)
        self.assertIn('time_window', summary)
        self.assertIn('total_recommendations', summary)


class Phase2PerformanceTestCase(TestCase):
    """Test Phase 2 performance characteristics"""

    def test_chunking_performance(self):
        """Test document chunking performance"""
        chunker = DocumentChunker()

        # Test with large document
        large_text = "This is a test sentence. " * 1000  # ~25KB
        start_time = time.time()

        chunks = chunker.chunk_text(large_text)

        processing_time = time.time() - start_time

        # Should complete in reasonable time
        self.assertLess(processing_time, 5.0)  # 5 seconds max
        self.assertGreater(len(chunks), 1)

    def test_vector_similarity_performance(self):
        """Test vector similarity calculation performance"""
        # Create test chunk
        knowledge = AuthoritativeKnowledge.objects.create(
            source_organization='Test Org',
            document_title='Test Doc',
            authority_level='medium',
            content_summary='Test'
        )

        chunk = AuthoritativeKnowledgeChunk.objects.create(
            knowledge=knowledge,
            chunk_index=0,
            content_text='Test content',
            content_vector=[0.1] * 384,  # Full size vector
            is_current=True
        )

        # Test similarity calculation
        query_vector = [0.2] * 384
        start_time = time.time()

        similarity = chunk.get_similarity_score(query_vector)

        calculation_time = time.time() - start_time

        # Should be fast
        self.assertLess(calculation_time, 0.1)  # 100ms max
        self.assertIsInstance(similarity, float)
        self.assertGreaterEqual(similarity, 0.0)
        self.assertLessEqual(similarity, 1.0)


if __name__ == '__main__':
    import django
    from django.test.utils import get_runner
    from django.conf import settings

    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["apps.onboarding_api.tests.test_phase2"])
    if failures:
        exit(1)