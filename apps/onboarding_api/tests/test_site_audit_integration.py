"""
Integration Tests for Site Audit API (Phase C).

End-to-end integration tests covering complete workflows:
- Full audit lifecycle (start → observations → analysis → report)
- Multimodal processing pipeline
- Service integration
- Data flow validation

Following testing best practices:
- Real service integration (mocked external APIs only)
- Transaction rollback
- Comprehensive workflow validation
"""

import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock
from io import BytesIO

from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.core_onboarding.models import (
    Observation,
    ConversationSession,
    LLMRecommendation
)
from apps.site_onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    SitePhoto,
    SOP,
    CoveragePlan
)
from apps.client_onboarding.models.business_unit import Bt

User = get_user_model()


class CompleteAuditWorkflowTests(TransactionTestCase):
    """Test complete audit workflow from start to report."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_auditor',
            email='auditor@test.com',
            peoplename='Test Auditor',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.business_unit = Bt.objects.create(
            buname='Test Branch',
            bucode='TB001'
        )

    @patch('apps.onboarding_api.views.site_audit_views.BankingSecurityExpertise')
    @patch('apps.onboarding_api.views.site_audit_views.get_multimodal_fusion_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_llm_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_checker_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_consensus_engine')
    @patch('apps.onboarding_api.views.site_audit_views.get_knowledge_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_reporting_service')
    def test_complete_audit_workflow(
        self,
        mock_reporting,
        mock_knowledge,
        mock_consensus,
        mock_checker,
        mock_llm,
        mock_fusion,
        mock_expertise
    ):
        """Test complete workflow: start → observe → analyze → report."""

        # Mock domain expertise for zone generation
        mock_expertise_instance = MagicMock()
        mock_expertise.return_value = mock_expertise_instance
        mock_expertise_instance.get_zone_templates.return_value = [
            {
                'zone_type': 'gate',
                'zone_name': 'Main Entrance',
                'importance_level': 'critical',
                'risk_level': 'high',
                'coverage_required': True
            }
        ]
        mock_expertise_instance.get_audit_checklist.return_value = [
            {'item': 'Check cameras', 'critical': True}
        ]

        # Step 1: Start audit session
        start_data = {
            'business_unit_id': str(self.business_unit.buuid),
            'site_type': 'bank_branch',
            'language': 'en'
        }

        start_response = self.client.post(
            '/api/v1/onboarding/site-audit/start/',
            start_data,
            format='json'
        )

        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        session_id = start_response.data['audit_session_id']
        site_id = start_response.data['site_id']

        # Verify session and site created
        self.assertTrue(ConversationSession.objects.filter(session_id=session_id).exists())
        self.assertTrue(OnboardingSite.objects.filter(site_id=site_id).exists())

        # Step 2: Check initial status
        status_response = self.client.get(
            f'/api/v1/onboarding/site-audit/{session_id}/status/'
        )

        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertEqual(status_response.data['observations_count'], 0)

        # Step 3: Capture observations
        mock_fusion_instance = MagicMock()
        mock_fusion.return_value = mock_fusion_instance

        site = OnboardingSite.objects.get(site_id=site_id)
        zone = site.zones.first()

        mock_fusion_instance.correlate_observation.return_value = {
            'unified_observation': {
                'transcript': 'Two cameras at entrance',
                'modalities': ['text']
            },
            'confidence_score': Decimal('0.90'),
            'identified_zone': zone,
            'inconsistencies': [],
            'enhanced': {
                'risk_level': 'low',
                'entities': []
            }
        }

        obs_data = {
            'text_input': 'Two cameras at entrance',
            'gps_latitude': 19.0760,
            'gps_longitude': 72.8777
        }

        obs_response = self.client.post(
            f'/api/v1/onboarding/site-audit/{session_id}/observation/',
            obs_data,
            format='json'
        )

        self.assertEqual(obs_response.status_code, status.HTTP_201_CREATED)
        observation_id = obs_response.data['observation_id']

        # Verify observation created
        self.assertTrue(Observation.objects.filter(observation_id=observation_id).exists())

        # Step 4: Check updated status
        status_response = self.client.get(
            f'/api/v1/onboarding/site-audit/{session_id}/status/'
        )

        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertEqual(status_response.data['observations_count'], 1)
        self.assertGreater(status_response.data['progress_percentage'], 0)

        # Step 5: Trigger analysis
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.analyze_site_audit.return_value = {
            'recommendations': ['Install DVR system']
        }

        mock_checker_instance = MagicMock()
        mock_checker.return_value = mock_checker_instance
        mock_checker_instance.validate_site_audit_analysis.return_value = {
            'validated': True
        }

        mock_consensus_instance = MagicMock()
        mock_consensus.return_value = mock_consensus_instance
        mock_consensus_instance.create_consensus.return_value = {
            'consensus_confidence': 0.92,
            'recommendations': ['Install DVR system']
        }

        mock_knowledge_instance = MagicMock()
        mock_knowledge.return_value = mock_knowledge_instance
        mock_knowledge_instance.retrieve_grounded_context.return_value = []

        analysis_data = {
            'include_sops': True,
            'include_coverage_plan': True
        }

        analysis_response = self.client.post(
            f'/api/v1/onboarding/site-audit/{session_id}/analyze/',
            analysis_data,
            format='json'
        )

        self.assertEqual(analysis_response.status_code, status.HTTP_200_OK)
        self.assertIn('analysis_id', analysis_response.data)

        # Verify recommendation created
        self.assertTrue(
            LLMRecommendation.objects.filter(
                recommendation_id=analysis_response.data['analysis_id']
            ).exists()
        )

        # Step 6: Generate report
        mock_reporting_instance = MagicMock()
        mock_reporting.return_value = mock_reporting_instance
        mock_reporting_instance.generate_site_audit_report.return_value = {
            'report_html': '<html>Report</html>',
            'summary': 'Audit complete',
            'compliance_score': 0.85,
            'critical_issues': 0,
            'recommendations_count': 1
        }

        mock_knowledge_instance.add_document_with_chunking.return_value = uuid.uuid4()

        report_response = self.client.get(
            f'/api/v1/onboarding/site-audit/{session_id}/report/',
            {'lang': 'en', 'save_to_kb': 'true'}
        )

        self.assertEqual(report_response.status_code, status.HTTP_200_OK)
        self.assertIn('report_html', report_response.data)
        self.assertIn('knowledge_id', report_response.data)
        self.assertIn('summary', report_response.data)

        # Verify complete workflow
        site.refresh_from_db()
        self.assertIsNotNone(site.knowledge_base_id)
        self.assertIsNotNone(site.report_generated_at)


class MultimodalProcessingTests(TransactionTestCase):
    """Test multimodal processing pipeline integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_auditor',
            email='auditor@test.com',
            peoplename='Test Auditor',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.business_unit = Bt.objects.create(
            buname='Test Branch',
            bucode='TB001'
        )

        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.business_unit
        )

        self.site = OnboardingSite.objects.create(
            business_unit=self.business_unit,
            conversation_session=self.session,
            site_type='bank_branch'
        )

        self.zone = OnboardingZone.objects.create(
            site=self.site,
            zone_type='gate',
            zone_name='Main Entrance',
            importance_level='critical',
            gps_coordinates=Point(72.8777, 19.0760, srid=4326)
        )

    @patch('apps.onboarding_api.views.site_audit_views.OnboardingSpeechService')
    @patch('apps.onboarding_api.views.site_audit_views.get_conversation_translator')
    @patch('apps.onboarding_api.views.site_audit_views.get_image_analysis_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_ocr_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_multimodal_fusion_service')
    @patch('apps.onboarding_api.views.site_audit_views.BankingSecurityExpertise')
    def test_voice_photo_gps_fusion(
        self,
        mock_expertise,
        mock_fusion,
        mock_ocr,
        mock_image,
        mock_translator,
        mock_speech
    ):
        """Test full multimodal pipeline: voice + photo + GPS."""

        # Mock speech recognition
        mock_speech_instance = MagicMock()
        mock_speech.return_value = mock_speech_instance
        mock_speech_instance.transcribe_voice_input.return_value = {
            'success': True,
            'transcript': 'यहाँ दो कैमरे हैं',  # Hindi: There are two cameras here
            'confidence': 0.92
        }

        # Mock translation
        mock_translator_instance = MagicMock()
        mock_translator.return_value = mock_translator_instance
        mock_translator_instance.translate_text.return_value = 'There are two cameras here'

        # Mock image analysis
        mock_image_instance = MagicMock()
        mock_image.return_value = mock_image_instance
        mock_image_instance.analyze_security_scene.return_value = {
            'detected_objects': ['camera', 'door', 'metal_detector'],
            'security_equipment': ['camera'],
            'safety_concerns': [],
            'confidence': 0.88
        }

        # Mock OCR
        mock_ocr_instance = MagicMock()
        mock_ocr.return_value = mock_ocr_instance
        mock_ocr_instance.extract_text_from_image.return_value = {
            'text': 'CCTV Camera 01',
            'confidence': 0.95
        }

        # Mock fusion
        mock_fusion_instance = MagicMock()
        mock_fusion.return_value = mock_fusion_instance
        mock_fusion_instance.correlate_observation.return_value = {
            'unified_observation': {
                'transcript': 'There are two cameras here',
                'transcript_original': 'यहाँ दो कैमरे हैं',
                'detected_objects': ['camera', 'metal_detector'],
                'modalities': ['voice', 'photo', 'gps']
            },
            'confidence_score': Decimal('0.90'),
            'identified_zone': self.zone,
            'inconsistencies': [],
            'enhanced': {
                'risk_level': 'low',
                'entities': [{'type': 'asset', 'name': 'camera'}]
            }
        }

        # Mock domain enhancement
        mock_expertise_instance = MagicMock()
        mock_expertise.return_value = mock_expertise_instance
        mock_expertise_instance.enhance_observation.return_value = {
            'enhanced_text': 'Zone equipped with 2 CCTV cameras and metal detector',
            'risk_level': 'low',
            'compliance_issues': [],
            'recommended_actions': []
        }

        # Create test audio and photo files
        audio_content = BytesIO(b'fake audio data')
        audio_file = SimpleUploadedFile(
            'test_audio.wav',
            audio_content.read(),
            content_type='audio/wav'
        )

        image_content = BytesIO(b'fake image data')
        photo_file = SimpleUploadedFile(
            'test_photo.jpg',
            image_content.read(),
            content_type='image/jpeg'
        )

        data = {
            'audio': audio_file,
            'photo': photo_file,
            'gps_latitude': 19.0760,
            'gps_longitude': 72.8777,
            'zone_hint': 'entrance',
            'compass_direction': 180.0
        }

        response = self.client.post(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/observation/',
            data,
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('observation_id', response.data)
        self.assertGreater(response.data['confidence'], 0.8)

        # Verify multimodal processing
        observation = Observation.objects.get(observation_id=response.data['observation_id'])
        self.assertIsNotNone(observation.transcript_original)
        self.assertIsNotNone(observation.transcript_english)

        # Verify photo record created
        self.assertTrue(
            SitePhoto.objects.filter(
                site=self.site,
                zone=self.zone
            ).exists()
        )


class ServiceIntegrationTests(TransactionTestCase):
    """Test integration between different service layers."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_auditor',
            email='auditor@test.com',
            peoplename='Test Auditor',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.business_unit = Bt.objects.create(
            buname='Test Branch',
            bucode='TB001'
        )

        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.business_unit
        )

        self.site = OnboardingSite.objects.create(
            business_unit=self.business_unit,
            conversation_session=self.session,
            site_type='bank_branch'
        )

    @patch('apps.onboarding_api.views.site_audit_views.get_coverage_planner_service')
    @patch('apps.onboarding_api.views.site_audit_views.SOPGeneratorService')
    def test_coverage_and_sop_generation_integration(
        self,
        mock_sop_service,
        mock_coverage_service
    ):
        """Test integration between coverage planning and SOP generation."""

        # Create zones
        zones = []
        for i in range(3):
            zone = OnboardingZone.objects.create(
                site=self.site,
                zone_type='vault' if i == 0 else 'gate',
                zone_name=f'Zone {i}',
                importance_level='critical'
            )
            zones.append(zone)

            # Add observations
            Observation.objects.create(
                site=self.site,
                zone=zone,
                transcript_english=f'Observation {i}',
                confidence_score=Decimal('0.85'),
                gps_at_capture=Point(72.8777, 19.0760, srid=4326),
                captured_by=self.user
            )

        # Mock coverage service
        mock_coverage_instance = MagicMock()
        mock_coverage_service.return_value = mock_coverage_instance
        mock_coverage_instance.calculate_coverage_plan.return_value = {
            'guard_posts': [
                {
                    'post_id': 'POST-001',
                    'zone_id': str(zones[0].zone_id),
                    'position': 'Vault entrance',
                    'duties': ['Monitor vault access'],
                    'requires_24x7': True
                }
            ],
            'shift_assignments': [
                {
                    'shift_name': 'Morning',
                    'start_time': '06:00',
                    'end_time': '14:00',
                    'posts_covered': ['POST-001']
                }
            ],
            'patrol_routes': [],
            'risk_windows': [],
            'compliance_notes': 'Compliant with RBI guidelines'
        }

        # Mock SOP service
        mock_sop_instance = MagicMock()
        mock_sop_service.return_value = mock_sop_instance
        mock_sop_instance.generate_zone_sop.return_value = {
            'sop_title': 'Vault Security Procedure',
            'purpose': 'Ensure vault security',
            'steps': [
                {'step_number': 1, 'description': 'Verify dual custody'}
            ],
            'staffing_required': {'guards': 2},
            'compliance_references': ['RBI MD 2021'],
            'frequency': 'every_shift',
            'escalation_triggers': ['Unauthorized access attempt']
        }

        # Trigger analysis with both coverage and SOPs
        with patch('apps.onboarding_api.views.site_audit_views.get_llm_service'), \
             patch('apps.onboarding_api.views.site_audit_views.get_checker_service'), \
             patch('apps.onboarding_api.views.site_audit_views.get_consensus_engine'), \
             patch('apps.onboarding_api.views.site_audit_views.get_knowledge_service'):

            # Mock LLM services for analysis
            from apps.onboarding_api.views import site_audit_views

            with patch.object(site_audit_views, 'get_llm_service') as mock_llm:
                mock_llm_inst = MagicMock()
                mock_llm.return_value = mock_llm_inst
                mock_llm_inst.analyze_site_audit.return_value = {}

                with patch.object(site_audit_views, 'get_checker_service') as mock_checker:
                    mock_checker_inst = MagicMock()
                    mock_checker.return_value = mock_checker_inst
                    mock_checker_inst.validate_site_audit_analysis.return_value = {}

                    with patch.object(site_audit_views, 'get_consensus_engine') as mock_consensus:
                        mock_consensus_inst = MagicMock()
                        mock_consensus.return_value = mock_consensus_inst
                        mock_consensus_inst.create_consensus.return_value = {
                            'consensus_confidence': 0.92
                        }

                        with patch.object(site_audit_views, 'get_knowledge_service') as mock_knowledge:
                            mock_knowledge_inst = MagicMock()
                            mock_knowledge.return_value = mock_knowledge_inst
                            mock_knowledge_inst.retrieve_grounded_context.return_value = []

                            analysis_data = {
                                'include_sops': True,
                                'include_coverage_plan': True
                            }

                            response = self.client.post(
                                f'/api/v1/onboarding/site-audit/{self.session.session_id}/analyze/',
                                analysis_data,
                                format='json'
                            )

                            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify both coverage plan and SOPs created
        self.assertTrue(
            CoveragePlan.objects.filter(site=self.site).exists()
        )

        sop_count = SOP.objects.filter(site=self.site).count()
        self.assertGreater(sop_count, 0)