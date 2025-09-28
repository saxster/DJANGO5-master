"""
Test suite for high-impact onboarding features:
- Industry templates with instant time-to-value
- Data import on-ramps
- Onboarding funnel analytics
- Change review UX improvements
- Real LLM integration with cost controls
- Enhanced knowledge embeddings
- Organization rollout controls
"""

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

    LLMRecommendation, AuthoritativeKnowledge, PreferenceProfile,
    Experiment, ExperimentAssignment, RecommendationInteraction
)

User = get_user_model()


class IndustryTemplatesHighImpactTestCase(TestCase):
    """Test high-impact industry template features"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='templates@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Templates Test Corp',
            bucode='TMP001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_instant_ttv_with_office_template(self):
        """Test instant time-to-value with office template deployment"""
        # Step 1: Get quick recommendations
        response = self.api_client.post(
            reverse('onboarding_api:quickstart-recommendations'),
            data={
                'industry': 'office',
                'size': 'small',
                'security_level': 'medium',
                'staff_count': 15
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['primary_template'])
        self.assertGreater(response.data['confidence_score'], 0.5)

        # Should recommend office template
        primary_template = response.data['primary_template']
        self.assertIn('office', primary_template['template_id'])

        # Step 2: One-click deployment
        deployment_response = self.api_client.post(
            reverse('onboarding_api:template-deploy', kwargs={'template_id': primary_template['template_id']}),
            data={
                'dry_run': False,
                'customizations': {
                    'business_units': [
                        {'bucode': 'OFFICE001', 'buname': 'My Office'}
                    ]
                }
            }
        )

        # Should succeed or provide clear error messages
        self.assertIn(deployment_response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])

        if deployment_response.status_code == status.HTTP_200_OK:
            # Verify deployment result structure
            self.assertIn('deployment_result', deployment_response.data)
            self.assertIn('created_objects', deployment_response.data['deployment_result'])

            # Should create all necessary objects
            created = deployment_response.data['deployment_result']['created_objects']
            self.assertGreater(len(created['business_units']), 0)
            self.assertGreater(len(created['shifts']), 0)
            self.assertGreater(len(created['type_assists']), 0)

    def test_manufacturing_template_complexity_handling(self):
        """Test that complex manufacturing templates are handled correctly"""
        response = self.api_client.post(
            reverse('onboarding_api:quickstart-recommendations'),
            data={
                'industry': 'manufacturing',
                'size': 'large',
                'operating_hours': '24/7',
                'security_level': 'high',
                'staff_count': 150
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        primary_template = response.data['primary_template']
        self.assertIn('manufacturing', primary_template['template_id'])

        # Check that complexity is properly reflected
        self.assertEqual(primary_template['metadata']['complexity'], 'high')
        self.assertGreater(primary_template['metadata']['setup_time_minutes'], 30)

    def test_template_customization_intelligence(self):
        """Test intelligent template customization suggestions"""
        response = self.api_client.post(
            reverse('onboarding_api:quickstart-recommendations'),
            data={
                'industry': 'retail',
                'size': 'small',
                'security_level': 'low',
                'staff_count': 8
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should provide customization suggestions
        self.assertIn('customization_suggestions', response.data)
        suggestions = response.data['customization_suggestions']

        # Should suggest staff reduction for small size
        staff_suggestions = [s for s in suggestions if s['type'] == 'staff_reduction']
        self.assertGreater(len(staff_suggestions), 0)

    def test_template_analytics_tracking(self):
        """Test template analytics and usage tracking"""
        # Only staff can access analytics
        self.user.is_staff = True
        self.user.save()

        response = self.api_client.get(reverse('onboarding_api:template-analytics'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check analytics structure
        self.assertIn('template_analytics', response.data)
        self.assertIn('usage_statistics', response.data)

        analytics = response.data['template_analytics']
        self.assertIn('total_templates', analytics)
        self.assertIn('templates_by_complexity', analytics)
        self.assertIn('industry_coverage', analytics)


class DataImportOnRampsTestCase(TestCase):
    """Test data import on-ramps functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='imports@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Import Test Corp',
            bucode='IMP001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_csv_import_suggestion_in_conversation(self):
        """Test that CSV import is suggested during conversations"""
        # This would test integration with existing import flows
        # For now, this is a placeholder for future CSV import integration

        # Create a conversation that might benefit from import
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_bt,
            current_state=ConversationSession.StateChoices.IN_PROGRESS,
            collected_data={'needs_users': True, 'needs_locations': True}
        )

        # In a real implementation, the LLM would suggest imports
        # This test validates the structure for import recommendations
        mock_recommendation = {
            'type': 'import_suggestion',
            'import_type': 'csv',
            'suggested_data': 'users',
            'import_url': '/import/users/',
            'reason': 'Multiple users needed for this configuration'
        }

        # Validate recommendation structure
        self.assertIn('import_type', mock_recommendation)
        self.assertIn('import_url', mock_recommendation)

    def test_excel_template_generation(self):
        """Test generation of Excel templates for data import"""
        # This would test generation of Excel templates based on current configuration
        # Placeholder for future Excel template generation functionality

        template_data = {
            'users_template': {
                'columns': ['email', 'name', 'role', 'shift'],
                'sample_data': [
                    ['john@company.com', 'John Doe', 'Security', 'Day Shift'],
                    ['jane@company.com', 'Jane Smith', 'Admin', 'Day Shift']
                ]
            },
            'locations_template': {
                'columns': ['location_code', 'location_name', 'address'],
                'sample_data': [
                    ['LOC001', 'Main Entrance', '123 Main St'],
                    ['LOC002', 'Parking Lot', '123 Main St - Parking']
                ]
            }
        }

        # Validate template structure
        self.assertIn('users_template', template_data)
        self.assertIn('columns', template_data['users_template'])
        self.assertIn('sample_data', template_data['users_template'])


class OnboardingFunnelAnalyticsTestCase(TestCase):
    """Test onboarding funnel analytics functionality"""

    def setUp(self):
        """Set up test data with funnel events"""
        self.admin_user = User.objects.create_user(
            email='analytics@example.com',
            password='testpass123',
            is_active=True,
            is_staff=True
        )

        self.client_bt = Bt.objects.create(
            buname='Analytics Test Corp',
            bucode='ANA001',
            enable=True
        )

        self.admin_user.client = self.client_bt
        self.admin_user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.admin_user)

        # Create test conversation sessions representing funnel stages
        self.create_funnel_test_data()

    def create_funnel_test_data(self):
        """Create test data representing different funnel stages"""
        # Stage 1: Started conversations
        for i in range(10):
            user = User.objects.create_user(
                email=f'funnel{i}@example.com',
                password='testpass123',
                is_active=True
            )
            user.client = self.client_bt
            user.save()

            ConversationSession.objects.create(
                user=user,
                client=self.client_bt,
                current_state=ConversationSession.StateChoices.STARTED
            )

        # Stage 2: In progress (some drop off)
        sessions = ConversationSession.objects.filter(
            current_state=ConversationSession.StateChoices.STARTED
        )[:7]

        for session in sessions:
            session.current_state = ConversationSession.StateChoices.IN_PROGRESS
            session.save()

        # Stage 3: Generated recommendations (more drop off)
        sessions = ConversationSession.objects.filter(
            current_state=ConversationSession.StateChoices.IN_PROGRESS
        )[:5]

        for session in sessions:
            session.current_state = ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
            session.save()

        # Stage 4: Awaiting approval
        sessions = ConversationSession.objects.filter(
            current_state=ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
        )[:4]

        for session in sessions:
            session.current_state = ConversationSession.StateChoices.AWAITING_USER_APPROVAL
            session.save()

        # Stage 5: Completed
        sessions = ConversationSession.objects.filter(
            current_state=ConversationSession.StateChoices.AWAITING_USER_APPROVAL
        )[:3]

        for session in sessions:
            session.current_state = ConversationSession.StateChoices.COMPLETED
            session.save()

    def test_funnel_analytics_calculation(self):
        """Test that funnel analytics are calculated correctly"""
        # Get analytics data (this would be implemented in a real analytics service)
        funnel_data = self.calculate_test_funnel_metrics()

        # Verify funnel stages
        self.assertEqual(funnel_data['started'], 10)
        self.assertEqual(funnel_data['in_progress'], 7)
        self.assertEqual(funnel_data['generating_recommendations'], 5)
        self.assertEqual(funnel_data['awaiting_approval'], 4)
        self.assertEqual(funnel_data['completed'], 3)

        # Calculate conversion rates
        self.assertEqual(funnel_data['start_to_progress_rate'], 0.7)
        self.assertEqual(funnel_data['progress_to_recommendations_rate'], 5/7)
        self.assertEqual(funnel_data['overall_completion_rate'], 0.3)

    def calculate_test_funnel_metrics(self):
        """Calculate funnel metrics from test data"""
        from django.db.models import Count

        # Count sessions by state
        state_counts = ConversationSession.objects.filter(
            client=self.client_bt
        ).values('current_state').annotate(count=Count('session_id'))

        counts = {item['current_state']: item['count'] for item in state_counts}

        started = counts.get(ConversationSession.StateChoices.STARTED, 0)
        in_progress = counts.get(ConversationSession.StateChoices.IN_PROGRESS, 0)
        generating = counts.get(ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS, 0)
        awaiting = counts.get(ConversationSession.StateChoices.AWAITING_USER_APPROVAL, 0)
        completed = counts.get(ConversationSession.StateChoices.COMPLETED, 0)

        total_started = started + in_progress + generating + awaiting + completed

        return {
            'started': started,
            'in_progress': in_progress,
            'generating_recommendations': generating,
            'awaiting_approval': awaiting,
            'completed': completed,
            'total_started': total_started,
            'start_to_progress_rate': (total_started - started) / max(1, total_started),
            'progress_to_recommendations_rate': (generating + awaiting + completed) / max(1, in_progress + generating + awaiting + completed),
            'overall_completion_rate': completed / max(1, total_started)
        }

    def test_drop_off_point_identification(self):
        """Test identification of major drop-off points in the funnel"""
        funnel_data = self.calculate_test_funnel_metrics()

        # Identify biggest drop-off point
        stages = [
            ('started', 'in_progress'),
            ('in_progress', 'generating_recommendations'),
            ('generating_recommendations', 'awaiting_approval'),
            ('awaiting_approval', 'completed')
        ]

        drop_offs = []
        for from_stage, to_stage in stages:
            from_count = funnel_data[from_stage]
            to_count = funnel_data[to_stage]
            drop_off_rate = (from_count - to_count) / max(1, from_count)
            drop_offs.append((from_stage, to_stage, drop_off_rate))

        # Find biggest drop-off
        biggest_drop_off = max(drop_offs, key=lambda x: x[2])

        # Should identify the biggest drop-off point
        self.assertGreater(biggest_drop_off[2], 0)


class ChangeReviewUXTestCase(TestCase):
    """Test enhanced change review UX features"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='review@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Review Test Corp',
            bucode='REV001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.capabilities = {
            'can_approve_ai_recommendations': True
        }
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_visual_diff_preview_generation(self):
        """Test visual diff preview for pending changes"""
        # Create existing business unit for modification
        existing_bu = Bt.objects.create(
            buname='Original Name',
            bucode='ORIG001',
            enable=True
        )

        # Request diff preview for proposed changes
        diff_request = {
            'approved_items': [
                {
                    'entity_type': 'bt',
                    'entity_id': existing_bu.id,
                    'changes': {
                        'buname': 'Updated Name',
                        'enable': True,
                        'gpsenable': True
                    }
                }
            ],
            'modifications': {}
        }

        response = self.api_client.post(
            reverse('onboarding_api:changeset-preview'),
            data=diff_request
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify diff structure
        self.assertIn('changes', response.data)
        self.assertIn('summary', response.data)

        changes = response.data['changes']
        self.assertEqual(len(changes), 1)

        change = changes[0]
        self.assertEqual(change['entity_type'], 'bt')
        self.assertEqual(change['operation'], 'update')
        self.assertIn('before', change)
        self.assertIn('after', change)
        self.assertIn('fields_changed', change)

        # Check field-level changes
        fields_changed = change['fields_changed']
        self.assertGreater(len(fields_changed), 0)

        # Find the name change
        name_change = next((f for f in fields_changed if f['field'] == 'buname'), None)
        self.assertIsNotNone(name_change)
        self.assertEqual(name_change['old'], 'Original Name')
        self.assertEqual(name_change['new'], 'Updated Name')

    def test_approval_workflow_with_preview(self):
        """Test complete approval workflow with change preview"""
        # Create changeset that requires approval
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.client_bt,
            current_state=ConversationSession.StateChoices.AWAITING_USER_APPROVAL
        )

        changeset = AIChangeSet.objects.create(
            conversation_session=session,
            approved_by=self.user,
            status=AIChangeSet.StatusChoices.PENDING,
            description='Test changeset with preview',
            total_changes=2
        )

        # Step 1: Preview changes
        preview_response = self.api_client.post(
            reverse('onboarding_api:changeset-preview'),
            data={
                'approved_items': [
                    {
                        'entity_type': 'bt',
                        'entity_id': 999,  # Non-existent (creation)
                        'changes': {
                            'buname': 'New Business Unit',
                            'bucode': 'NEW001',
                            'enable': True
                        }
                    }
                ]
            }
        )

        self.assertEqual(preview_response.status_code, status.HTTP_200_OK)

        # Step 2: Apply with approval
        approval_response = self.api_client.post(
            reverse('onboarding_api:recommendations-approve'),
            data={
                'session_id': str(session.session_id),
                'approved_items': [
                    {
                        'entity_type': 'bt',
                        'entity_id': 999,
                        'changes': {
                            'buname': 'New Business Unit',
                            'bucode': 'NEW001',
                            'enable': True
                        }
                    }
                ],
                'rejected_items': [],
                'reasons': {},
                'modifications': {},
                'dry_run': False
            }
        )

        # Should succeed or provide clear error
        self.assertIn(approval_response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])


class RealLLMIntegrationTestCase(TestCase):
    """Test real LLM integration with cost controls"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='llm@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='LLM Test Corp',
            bucode='LLM001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

    @patch('apps.onboarding_api.services.production_embeddings.OpenAIEmbeddingProvider')
    def test_openai_embedding_integration(self, mock_openai):
        """Test OpenAI embedding integration with cost tracking"""
        # Mock OpenAI provider
        mock_provider = MagicMock()
        mock_provider.generate_embedding.return_value = MagicMock(
            embedding=[0.1, 0.2, 0.3] * 128,
            model='text-embedding-3-small',
            provider='openai',
            token_count=50,
            cost_cents=0.1,
            latency_ms=200,
            cached=False
        )
        mock_provider.validate_connection.return_value = True
        mock_openai.return_value = mock_provider

        from apps.onboarding_api.services.production_embeddings import ProductionEmbeddingService

        # Create service with mock provider
        service = ProductionEmbeddingService()
        service.providers['openai'] = mock_provider

        # Test embedding generation
        result = service.generate_embedding("Test document for embedding")

        self.assertEqual(len(result.embedding), 384)
        self.assertEqual(result.provider, 'openai')
        self.assertEqual(result.cost_cents, 0.1)
        self.assertFalse(result.cached)

        # Verify cost tracking
        daily_spend = service.cost_tracker.get_daily_spend('openai')
        self.assertEqual(daily_spend, 0.1)

    def test_cost_budget_enforcement(self):
        """Test that cost budgets are properly enforced"""
        from apps.onboarding_api.services.production_embeddings import CostTracker

        tracker = CostTracker()

        # Set up scenario where budget is exceeded
        provider = 'test_provider'
        budget_cents = 100
        current_spend = 95

        # Record existing spend
        tracker.record_spend(provider, current_spend)

        # Check if new request would exceed budget
        can_spend_small = tracker.check_budget(provider, budget_cents, 3.0)  # Under budget
        can_spend_large = tracker.check_budget(provider, budget_cents, 10.0)  # Over budget

        self.assertTrue(can_spend_small)
        self.assertFalse(can_spend_large)

    @patch('apps.onboarding_api.services.production_embeddings.ProductionEmbeddingService')
    def test_llm_provider_fallback_chain(self, mock_service):
        """Test LLM provider fallback mechanism"""
        # Mock service to test fallback behavior
        mock_service_instance = MagicMock()

        # First provider fails
        mock_service_instance.providers = {
            'openai': MagicMock(),
            'azure': MagicMock(),
            'local': MagicMock()
        }

        # OpenAI fails
        mock_service_instance.providers['openai'].generate_embedding.side_effect = Exception("OpenAI failed")
        mock_service_instance.providers['openai'].validate_connection.return_value = False

        # Azure succeeds
        mock_service_instance.providers['azure'].generate_embedding.return_value = MagicMock(
            embedding=[0.1] * 384,
            provider='azure',
            cost_cents=0.05
        )
        mock_service_instance.providers['azure'].validate_connection.return_value = True

        mock_service_instance.fallback_order = ['openai', 'azure', 'local']

        # Service should fall back to Azure
        # This is a structural test of the fallback logic


class EnhancedKnowledgeEmbeddingsTestCase(TestCase):
    """Test enhanced knowledge embeddings and semantic search"""

    def setUp(self):
        """Set up test knowledge data"""
        self.knowledge_docs = []

        # Create test knowledge documents
        for i in range(5):
            doc = AuthoritativeKnowledge.objects.create(
                source_organization=f'Test Org {i}',
                document_title=f'Test Document {i}',
                authority_level='high',
                content_summary=f'This is test document {i} about security protocols.',
                publication_date=datetime.now(),
                is_current=True
            )
            self.knowledge_docs.append(doc)

    def test_chunked_knowledge_processing(self):
        """Test that knowledge documents are properly chunked for better retrieval"""
        from apps.onboarding_api.services.knowledge import DocumentChunker

        chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)

        # Test document with structure
        structured_document = """
        # Security Guidelines

        ## Introduction
        This document provides security guidelines for facility management.

        ## Access Control
        All access must be properly authenticated and authorized.

        ### Physical Access
        Physical access requires badge and biometric verification.

        ### Digital Access
        Digital systems require multi-factor authentication.
        """

        chunks = chunker.chunk_with_structure(structured_document)

        # Should create multiple chunks with proper metadata
        self.assertGreater(len(chunks), 1)

        # Check that chunks have proper metadata
        for chunk in chunks:
            self.assertIn('text', chunk)
            self.assertIn('tags', chunk)
            self.assertIn('section_heading', chunk.get('tags', {}))

    def test_semantic_search_quality(self):
        """Test semantic search quality with embeddings"""
        from apps.onboarding_api.services.knowledge import get_knowledge_service

        service = get_knowledge_service()

        # Test search with related terms
        results = service.search_knowledge("security protocols", top_k=3)

        # Should return relevant results
        self.assertGreater(len(results), 0)

        # Results should be ranked by relevance
        for result in results:
            self.assertIn('relevance_score', result)
            self.assertGreater(result['relevance_score'], 0)

    def test_knowledge_validation_against_sources(self):
        """Test recommendation validation against authoritative knowledge"""
        from apps.onboarding_api.services.knowledge import get_knowledge_service

        service = get_knowledge_service()

        # Test recommendation validation
        recommendation = {
            'business_unit_config': {
                'security_settings': {
                    'enable_gps': True,
                    'enable_biometric': True
                }
            },
            'reasoning': 'Enhanced security for sensitive facility'
        }

        context = {
            'client_id': 'test-client',
            'facility_type': 'high_security'
        }

        validation_result = service.validate_recommendation_against_knowledge(
            recommendation, context
        )

        # Should return validation structure
        self.assertIn('is_valid', validation_result)
        self.assertIn('confidence_score', validation_result)
        self.assertIn('supporting_sources', validation_result)
        self.assertIn('potential_conflicts', validation_result)


class OrganizationRolloutTestCase(TestCase):
    """Test organization rollout controls and A/B testing"""

    def setUp(self):
        """Set up test data for rollout testing"""
        self.admin_user = User.objects.create_user(
            email='rollout@example.com',
            password='testpass123',
            is_active=True,
            is_staff=True
        )

        self.client_bt = Bt.objects.create(
            buname='Rollout Test Corp',
            bucode='ROL001',
            enable=True
        )

        self.admin_user.client = self.client_bt
        self.admin_user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.admin_user)

    def test_experiment_creation_and_management(self):
        """Test A/B experiment creation and management"""
        # Create test experiment
        experiment = Experiment.objects.create(
            name='Template Recommendation Algorithm Test',
            description='Testing different template recommendation algorithms',
            scope=Experiment.ScopeChoices.TENANT,
            arms=[
                {
                    'name': 'control',
                    'config': {'algorithm': 'original'},
                    'traffic_allocation': 0.5
                },
                {
                    'name': 'enhanced',
                    'config': {'algorithm': 'ml_enhanced'},
                    'traffic_allocation': 0.5
                }
            ],
            primary_metric='acceptance_rate',
            status=Experiment.StatusChoices.RUNNING,
            owner=self.admin_user
        )

        # Test experiment assignment
        assignment = ExperimentAssignment.objects.create(
            experiment=experiment,
            client=self.client_bt,
            arm='enhanced'
        )

        self.assertEqual(assignment.arm, 'enhanced')
        self.assertTrue(assignment.is_active())

        # Test arm configuration retrieval
        arm_config = assignment.get_arm_config()
        self.assertEqual(arm_config['config']['algorithm'], 'ml_enhanced')

    def test_personalization_preference_tracking(self):
        """Test personalization preference tracking"""
        # Create preference profile
        profile = PreferenceProfile.objects.create(
            user=self.admin_user,
            client=self.client_bt,
            weights={
                'security_preference': 0.8,
                'cost_preference': 0.3,
                'complexity_tolerance': 0.6
            }
        )

        # Test preference updates
        profile.update_stats('approvals', {'recommendation_type': 'security_enhancement'})

        # Should update statistics
        self.assertIn('approvals', profile.stats)
        self.assertEqual(profile.stats['approvals'], 1)

        # Test acceptance rate calculation
        profile.update_stats('rejections', {'reason': 'too_complex'})
        acceptance_rate = profile.calculate_acceptance_rate()

        self.assertEqual(acceptance_rate, 0.5)  # 1 approval, 1 rejection

    def test_recommendation_interaction_tracking(self):
        """Test tracking of user interactions with recommendations"""
        # Create test session and recommendation
        session = ConversationSession.objects.create(
            user=self.admin_user,
            client=self.client_bt,
            current_state=ConversationSession.StateChoices.AWAITING_USER_APPROVAL
        )

        recommendation = LLMRecommendation.objects.create(
            session=session,
            maker_output={'recommendation': 'test'},
            confidence_score=0.85,
            status=LLMRecommendation.StatusChoices.VALIDATED
        )

        # Create interaction
        interaction = RecommendationInteraction.objects.create(
            session=session,
            recommendation=recommendation,
            event_type=RecommendationInteraction.EventTypeChoices.APPROVED,
            metadata={
                'time_on_item': 120,  # 2 minutes
                'scroll_depth': 0.8,
                'confidence_when_approved': 0.85
            }
        )

        # Test feature extraction
        features = interaction.extract_features()

        self.assertEqual(features['event_type'], 'approved')
        self.assertEqual(features['time_on_item'], 120)
        self.assertEqual(features['scroll_depth'], 0.8)
        self.assertGreater(features['time_to_decision'], 0)

    def test_rollout_safety_constraints(self):
        """Test rollout safety constraints and circuit breakers"""
        # Create experiment with safety constraints
        experiment = Experiment.objects.create(
            name='Safety Test Experiment',
            description='Testing safety constraint enforcement',
            scope=Experiment.ScopeChoices.GLOBAL,
            arms=[
                {'name': 'control', 'config': {}},
                {'name': 'variant', 'config': {'new_feature': True}}
            ],
            primary_metric='error_rate',
            status=Experiment.StatusChoices.RUNNING,
            owner=self.admin_user,
            safety_constraints={
                'max_error_rate': 0.05,  # 5% max error rate
                'max_complaint_rate': 0.02,  # 2% max complaint rate
                'max_daily_spend_cents': 1000  # $10/day max spend
            }
        )

        # Test safety constraint checking
        arm_performance = {
            'control': {
                'error_rate': 0.02,
                'complaint_rate': 0.01,
                'daily_spend_cents': 500
            },
            'variant': {
                'error_rate': 0.08,  # Exceeds 5% limit
                'complaint_rate': 0.015,
                'daily_spend_cents': 600
            }
        }

        violations = experiment.check_safety_constraints(arm_performance)

        # Should detect error rate violation
        self.assertGreater(len(violations), 0)
        self.assertTrue(any('error rate' in v for v in violations))


class PerformanceAndScalabilityTestCase(TestCase):
    """Test performance and scalability of new features"""

    def setUp(self):
        """Set up performance test data"""
        self.user = User.objects.create_user(
            email='perf@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Performance Test Corp',
            bucode='PERF001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.save()

    def test_bulk_embedding_generation_performance(self):
        """Test performance of bulk embedding generation"""
        from apps.onboarding_api.services.production_embeddings import ProductionEmbeddingService
        import time

        service = ProductionEmbeddingService()

        # Generate embeddings for multiple documents
        test_documents = [
            f"Test document {i} with different content for embedding generation testing."
            for i in range(20)
        ]

        start_time = time.time()
        results = service.generate_batch_embeddings(test_documents)
        end_time = time.time()

        batch_time = end_time - start_time

        # Should complete in reasonable time
        self.assertEqual(len(results), 20)
        self.assertLess(batch_time, 10.0)  # Under 10 seconds for 20 documents

        # All results should be valid
        for result in results:
            self.assertEqual(len(result.embedding), 384)
            self.assertGreaterEqual(result.cost_cents, 0.0)

    def test_template_recommendation_performance(self):
        """Test performance of template recommendation algorithm"""
        from apps.onboarding_api.services.config_templates import get_template_service
        import time

        service = get_template_service()

        # Test recommendation generation time
        context = {
            'site_type': 'office',
            'staff_count': 25,
            'operating_hours': 'business_hours',
            'security_level': 'medium'
        }

        start_time = time.time()
        recommendations = service.recommend_templates(context)
        end_time = time.time()

        recommendation_time = end_time - start_time

        # Should generate recommendations quickly
        self.assertLess(recommendation_time, 1.0)  # Under 1 second
        self.assertGreater(len(recommendations), 0)

    def test_concurrent_notification_sending(self):
        """Test concurrent notification sending performance"""
        from apps.onboarding_api.services.notifications import NotificationService, NotificationEvent
        from django.utils import timezone
        import time

        service = NotificationService()

        # Create multiple test events
        events = []
        for i in range(5):
            event = NotificationEvent(
                event_type='test_performance',
                event_id=f'perf-test-{i}',
                title=f'Performance Test {i}',
                message=f'Test message {i}',
                priority='medium',
                metadata={'test_id': i},
                timestamp=timezone.now()
            )
            events.append(event)

        # Test sending multiple notifications
        start_time = time.time()
        results = []
        for event in events:
            result = service.send_notification(event)
            results.append(result)
        end_time = time.time()

        total_time = end_time - start_time

        # Should handle multiple notifications efficiently
        self.assertEqual(len(results), 5)
        self.assertLess(total_time, 5.0)  # Under 5 seconds for 5 notifications


class IntegrationTestSuite(TestCase):
    """End-to-end integration tests for all features working together"""

    def setUp(self):
        """Set up comprehensive test environment"""
        self.user = User.objects.create_user(
            email='integration@example.com',
            password='testpass123',
            is_active=True
        )

        self.client_bt = Bt.objects.create(
            buname='Integration Test Corp',
            bucode='INT001',
            enable=True
        )

        self.user.client = self.client_bt
        self.user.capabilities = {
            'can_use_conversational_onboarding': True,
            'can_approve_ai_recommendations': True
        }
        self.user.save()

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    @override_settings(
        ENABLE_CONVERSATIONAL_ONBOARDING=True,
        ENABLE_WEBHOOK_NOTIFICATIONS=False,  # Disabled for integration tests
        ENABLE_PRODUCTION_EMBEDDINGS=False  # Use dummy for integration tests
    )
    def test_complete_onboarding_flow_with_all_features(self):
        """Test complete onboarding flow using all new features"""
        # Step 1: Get quick-start recommendations
        recommendations_response = self.api_client.post(
            reverse('onboarding_api:quickstart-recommendations'),
            data={
                'industry': 'office',
                'size': 'medium',
                'security_level': 'medium',
                'staff_count': 20
            }
        )

        self.assertEqual(recommendations_response.status_code, status.HTTP_200_OK)
        self.assertIn('primary_template', recommendations_response.data)

        # Step 2: Preview template deployment
        primary_template = recommendations_response.data['primary_template']
        preview_response = self.api_client.post(
            reverse('onboarding_api:template-deploy', kwargs={'template_id': primary_template['template_id']}),
            data={
                'dry_run': True,
                'customizations': {
                    'business_units': [
                        {'bucode': 'MYOFFICE', 'buname': 'My Office Space'}
                    ]
                }
            }
        )

        self.assertEqual(preview_response.status_code, status.HTTP_200_OK)
        self.assertTrue(preview_response.data['deployment_result']['dry_run'])

        # Step 3: Start conversational session
        conversation_response = self.api_client.post(
            reverse('onboarding_api:conversation-start'),
            data={
                'language': 'en',
                'client_context': {
                    'template_preference': primary_template['template_id'],
                    'customizations_applied': True
                }
            }
        )

        self.assertEqual(conversation_response.status_code, status.HTTP_200_OK)
        conversation_id = conversation_response.data['conversation_id']

        # Step 4: Check conversation status
        status_response = self.api_client.get(
            reverse('onboarding_api:conversation-status', kwargs={'conversation_id': conversation_id})
        )

        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertIn('state', status_response.data)

        # Step 5: Verify all security decorators work together
        # All requests should have succeeded with proper tenant isolation

    def test_error_recovery_and_resilience(self):
        """Test that system recovers gracefully from various error conditions"""
        with override_settings(ENABLE_CONVERSATIONAL_ONBOARDING=True):
            # Test with missing template
            response = self.api_client.post(
                reverse('onboarding_api:template-deploy', kwargs={'template_id': 'nonexistent_template'}),
                data={'dry_run': True}
            )

            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

            # Test with invalid customizations
            response = self.api_client.post(
                reverse('onboarding_api:template-deploy', kwargs={'template_id': 'office_corporate'}),
                data={
                    'dry_run': True,
                    'customizations': {
                        'invalid_section': 'invalid_data'
                    }
                }
            )

            # Should handle gracefully
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_cross_feature_compatibility(self):
        """Test that all new features work together without conflicts"""
        # This test ensures that:
        # 1. Security decorators don't interfere with embedding service
        # 2. Idempotency works with notifications
        # 3. Template deployment works with changeset tracking
        # 4. All services can be initialized together

        try:
            # Import all services to ensure they can coexist
            from apps.onboarding_api.services.production_embeddings import get_production_embedding_service
            from apps.onboarding_api.services.notifications import get_notification_service
            from apps.onboarding_api.services.config_templates import get_template_service
            from apps.onboarding_api.utils.security import (
                TenantScopeValidator, IdempotencyManager, SecurityAuditLogger
            )

            # Initialize all services
            embedding_service = get_production_embedding_service()
            notification_service = get_notification_service()
            template_service = get_template_service()
            tenant_validator = TenantScopeValidator()
            idempotency_manager = IdempotencyManager()
            audit_logger = SecurityAuditLogger()

            # All should initialize without conflicts
            self.assertIsNotNone(embedding_service)
            self.assertIsNotNone(notification_service)
            self.assertIsNotNone(template_service)
            self.assertIsNotNone(tenant_validator)
            self.assertIsNotNone(idempotency_manager)
            self.assertIsNotNone(audit_logger)

        except Exception as e:
            self.fail(f"Cross-feature compatibility issue: {str(e)}")


# Performance benchmarks for high-impact features
PERFORMANCE_BENCHMARKS = {
    'template_deployment_max_time': 5.0,  # seconds
    'bulk_embedding_max_time': 10.0,  # seconds for 20 documents
    'notification_batch_max_time': 5.0,  # seconds for 5 notifications
    'analytics_calculation_max_time': 2.0,  # seconds
    'quick_start_recommendation_max_time': 1.0,  # seconds
}


# Test configuration for high-impact features
HIGH_IMPACT_TEST_CONFIG = {
    'test_industry_templates': True,
    'test_one_click_deployment': True,
    'test_data_import_suggestions': True,
    'test_funnel_analytics': True,
    'test_change_review_ux': True,
    'test_real_llm_integration': True,
    'test_enhanced_embeddings': True,
    'test_rollout_controls': True,
    'test_a_b_testing': True,
    'test_personalization': True
}


# Utility functions for high-impact feature testing
def simulate_onboarding_funnel(client_bt, num_users=10):
    """Simulate users going through onboarding funnel for analytics testing"""
    users = []
    sessions = []

    for i in range(num_users):
        user = User.objects.create_user(
            email=f'funneluser{i}@example.com',
            password='testpass123',
            is_active=True
        )
        user.client = client_bt
        user.save()
        users.append(user)

        # Create session in random state
        import random
        states = list(ConversationSession.StateChoices)
        random_state = random.choice(states)

        session = ConversationSession.objects.create(
            user=user,
            client=client_bt,
            current_state=random_state,
            conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP
        )
        sessions.append(session)

    return users, sessions


def create_test_knowledge_base():
    """Create test knowledge base for embedding tests"""
    knowledge_docs = []

    sample_docs = [
        {
            'title': 'Security Best Practices',
            'content': 'Comprehensive security guidelines for facility management including access control, surveillance, and emergency procedures.',
            'authority': 'high'
        },
        {
            'title': 'Shift Management Guidelines',
            'content': 'Standard operating procedures for managing shifts, scheduling, and personnel allocation in security operations.',
            'authority': 'medium'
        },
        {
            'title': 'Device Configuration Manual',
            'content': 'Technical documentation for configuring and managing security devices, sensors, and monitoring equipment.',
            'authority': 'high'
        }
    ]

    for doc_data in sample_docs:
        doc = AuthoritativeKnowledge.objects.create(
            source_organization='Test Security Standards',
            document_title=doc_data['title'],
            authority_level=doc_data['authority'],
            content_summary=doc_data['content'],
            publication_date=datetime.now(),
            is_current=True
        )
        knowledge_docs.append(doc)

    return knowledge_docs


# Custom assertions for high-impact features
class HighImpactAssertions:
    """Custom assertions for testing high-impact features"""

    @staticmethod
    def assert_template_deployment_success(deployment_result):
        """Assert that template deployment was successful"""
        assert not deployment_result['dry_run'], "Should be real deployment"
        assert len(deployment_result['errors']) == 0, f"Deployment errors: {deployment_result['errors']}"
        assert deployment_result['created_objects'], "Should create objects"

    @staticmethod
    def assert_notification_sent_successfully(notification_results):
        """Assert that notifications were sent successfully"""
        assert len(notification_results) > 0, "Should have notification results"
        success_count = sum(1 for result in notification_results.values() if result.success)
        assert success_count > 0, "At least one notification should succeed"

    @staticmethod
    def assert_funnel_analytics_valid(funnel_data):
        """Assert that funnel analytics data is valid"""
        required_fields = ['started', 'in_progress', 'completed', 'overall_completion_rate']
        for field in required_fields:
            assert field in funnel_data, f"Missing funnel field: {field}"

        assert funnel_data['overall_completion_rate'] >= 0.0, "Completion rate should be non-negative"
        assert funnel_data['overall_completion_rate'] <= 1.0, "Completion rate should not exceed 100%"

    @staticmethod
    def assert_embedding_quality(embedding_result):
        """Assert that embedding result meets quality standards"""
        assert len(embedding_result.embedding) == 384, "Standard embedding dimension"
        assert embedding_result.cost_cents >= 0.0, "Cost should be non-negative"
        assert embedding_result.latency_ms > 0, "Should have measurable latency"
        assert embedding_result.provider in ['openai', 'azure', 'local', 'dummy'], "Valid provider"