"""
Unit Tests for Site Audit API (Phase C).

Comprehensive test coverage for all site audit endpoints including:
- Session management
- Observation capture
- Guidance and coverage
- Zone and asset management
- Analysis and planning
- Reporting

Following testing best practices:
- Isolated unit tests
- Mocked external services
- Comprehensive assertions
- Transaction rollback
"""

import json
import uuid
from decimal import Decimal
from datetime import time as datetime_time
from unittest.mock import patch, MagicMock
from io import BytesIO

from django.test import TestCase, TransactionTestCase
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
    Asset,
    MeterPoint,
    SOP,
    CoveragePlan
)
from apps.client_onboarding.models.business_unit import Bt

User = get_user_model()


class SiteAuditSessionTests(TransactionTestCase):
    """Test suite for session management APIs."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            loginid='test_auditor',
            email='auditor@test.com',
            peoplename='Test Auditor',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create business unit
        self.business_unit = Bt.objects.create(
            buname='Test Branch',
            bucode='TB001'
        )

    def test_start_audit_session_success(self):
        """Test successful audit session creation."""
        data = {
            'business_unit_id': str(self.business_unit.buuid),
            'site_type': 'bank_branch',
            'language': 'en',
            'operating_hours': {
                'start': '09:00',
                'end': '17:00'
            },
            'gps_location': {
                'latitude': 19.0760,
                'longitude': 72.8777
            }
        }

        response = self.client.post(
            '/api/v1/onboarding/site-audit/start/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('audit_session_id', response.data)
        self.assertIn('site_id', response.data)
        self.assertIn('zones', response.data)
        self.assertIn('checklist', response.data)
        self.assertIn('suggested_route', response.data)

        # Verify database records
        self.assertTrue(
            ConversationSession.objects.filter(
                session_id=response.data['audit_session_id']
            ).exists()
        )
        self.assertTrue(
            OnboardingSite.objects.filter(
                site_id=response.data['site_id']
            ).exists()
        )

    def test_start_audit_session_invalid_business_unit(self):
        """Test audit start with non-existent business unit."""
        data = {
            'business_unit_id': str(uuid.uuid4()),
            'site_type': 'bank_branch',
            'language': 'en'
        }

        response = self.client.post(
            '/api/v1/onboarding/site-audit/start/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_start_audit_session_invalid_operating_hours(self):
        """Test validation of operating hours format."""
        data = {
            'business_unit_id': str(self.business_unit.buuid),
            'site_type': 'bank_branch',
            'operating_hours': {
                'start': '25:00',  # Invalid hour
                'end': '17:00'
            }
        }

        response = self.client.post(
            '/api/v1/onboarding/site-audit/start/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_audit_status(self):
        """Test getting audit session status."""
        # Create session
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.business_unit,
            current_state=ConversationSession.StateChoices.IN_PROGRESS
        )

        site = OnboardingSite.objects.create(
            business_unit=self.business_unit,
            conversation_session=session,
            site_type='bank_branch'
        )

        # Create some zones
        for i in range(3):
            OnboardingZone.objects.create(
                site=site,
                zone_type='gate' if i == 0 else 'vault',
                zone_name=f'Zone {i}',
                importance_level='critical' if i == 0 else 'high'
            )

        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{session.session_id}/status/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('state', response.data)
        self.assertIn('progress_percentage', response.data)
        self.assertIn('coverage', response.data)
        self.assertEqual(response.data['coverage']['total_zones'], 3)


class ObservationCaptureTests(TransactionTestCase):
    """Test suite for observation capture APIs."""

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
            client=self.business_unit,
            current_state=ConversationSession.StateChoices.IN_PROGRESS
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
    @patch('apps.onboarding_api.views.site_audit_views.get_image_analysis_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_multimodal_fusion_service')
    def test_capture_observation_text_only(
        self,
        mock_fusion,
        mock_image,
        mock_speech
    ):
        """Test capturing observation with text input only."""
        # Mock fusion service
        mock_fusion_instance = MagicMock()
        mock_fusion.return_value = mock_fusion_instance
        mock_fusion_instance.correlate_observation.return_value = {
            'unified_observation': {
                'transcript': 'Two cameras at entrance',
                'modalities': ['text']
            },
            'confidence_score': Decimal('0.90'),
            'identified_zone': self.zone,
            'inconsistencies': []
        }

        data = {
            'text_input': 'Two cameras at entrance',
            'gps_latitude': 19.0760,
            'gps_longitude': 72.8777
        }

        response = self.client.post(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/observation/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('observation_id', response.data)
        self.assertIn('confidence', response.data)
        self.assertGreater(response.data['confidence'], 0.8)

        # Verify observation created
        self.assertTrue(
            Observation.objects.filter(
                observation_id=response.data['observation_id']
            ).exists()
        )

    def test_capture_observation_no_input(self):
        """Test that at least one input modality is required."""
        data = {
            'gps_latitude': 19.0760,
            'gps_longitude': 72.8777
        }

        response = self.client.post(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/observation/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('at least one input required', str(response.data).lower())

    def test_capture_observation_invalid_gps(self):
        """Test GPS validation."""
        data = {
            'text_input': 'Test observation',
            'gps_latitude': 95.0,  # Invalid latitude
            'gps_longitude': 72.8777
        }

        response = self.client.post(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/observation/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_observations(self):
        """Test listing observations with filtering."""
        # Create test observations
        for i in range(5):
            Observation.objects.create(
                site=self.site,
                zone=self.zone,
                transcript_english=f'Observation {i}',
                severity='critical' if i < 2 else 'medium',
                confidence_score=Decimal('0.85'),
                gps_at_capture=Point(72.8777, 19.0760, srid=4326),
                captured_by=self.user
            )

        # Test without filters
        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/observations/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 5)

        # Test with severity filter
        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/observations/',
            {'severity': 'critical'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)


class GuidanceCoverageTests(TransactionTestCase):
    """Test suite for guidance and coverage APIs."""

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

        # Create zones
        self.zones = []
        for i in range(5):
            zone = OnboardingZone.objects.create(
                site=self.site,
                zone_type='vault' if i == 0 else 'gate',
                zone_name=f'Zone {i}',
                importance_level='critical' if i < 2 else 'medium'
            )
            self.zones.append(zone)

    @patch('apps.onboarding_api.views.site_audit_views.BankingSecurityExpertise')
    def test_get_next_questions(self, mock_expertise):
        """Test getting next recommended questions."""
        # Mock domain expertise
        mock_expertise_instance = MagicMock()
        mock_expertise.return_value = mock_expertise_instance
        mock_expertise_instance.get_zone_questions.return_value = [
            {
                'question': 'Is dual custody maintained?',
                'type': 'boolean',
                'importance': 'critical'
            }
        ]

        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/next-questions/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('questions', response.data)
        self.assertIn('completion_percentage', response.data)
        self.assertIn('critical_gaps', response.data)

    def test_get_coverage_map(self):
        """Test getting coverage map."""
        # Add observations to some zones
        for i in range(2):
            Observation.objects.create(
                site=self.site,
                zone=self.zones[i],
                transcript_english=f'Observation in zone {i}',
                confidence_score=Decimal('0.85'),
                gps_at_capture=Point(72.8777, 19.0760, srid=4326),
                captured_by=self.user
            )

        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/coverage/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('coverage_map', response.data)
        self.assertIn('zones', response.data)
        self.assertIn('critical_gaps', response.data)

        # Check coverage calculation
        coverage = response.data['coverage_map']
        self.assertEqual(coverage['total_zones'], 5)
        self.assertEqual(coverage['visited'], 2)
        self.assertEqual(coverage['percentage'], 40.0)

    def test_coverage_identifies_critical_gaps(self):
        """Test that critical gaps are properly identified."""
        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/coverage/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        critical_gaps = response.data['critical_gaps']

        # Should have 2 critical zones unvisited
        self.assertGreater(len(critical_gaps), 0)


class ZoneAssetManagementTests(TransactionTestCase):
    """Test suite for zone and asset management APIs."""

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

        session = ConversationSession.objects.create(
            user=self.user,
            client=self.business_unit
        )

        self.site = OnboardingSite.objects.create(
            business_unit=self.business_unit,
            conversation_session=session,
            site_type='bank_branch'
        )

    def test_create_zones_bulk(self):
        """Test bulk zone creation."""
        data = {
            'zones': [
                {
                    'zone_type': 'vault',
                    'zone_name': 'Main Vault',
                    'importance_level': 'critical',
                    'risk_level': 'high',
                    'coverage_required': True
                },
                {
                    'zone_type': 'gate',
                    'zone_name': 'Main Entrance',
                    'importance_level': 'high',
                    'risk_level': 'moderate'
                }
            ]
        }

        response = self.client.post(
            f'/api/v1/onboarding/site/{self.site.site_id}/zones/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['zones_created'], 2)

        # Verify zones created
        self.assertEqual(self.site.zones.count(), 2)

    def test_create_assets_bulk(self):
        """Test bulk asset creation."""
        # Create zone first
        zone = OnboardingZone.objects.create(
            site=self.site,
            zone_type='vault',
            zone_name='Main Vault',
            importance_level='critical'
        )

        data = {
            'assets': [
                {
                    'zone_id': str(zone.zone_id),
                    'asset_type': 'camera',
                    'asset_name': 'Vault Camera 1',
                    'status': 'operational'
                },
                {
                    'zone_id': str(zone.zone_id),
                    'asset_type': 'alarm_system',
                    'asset_name': 'Vault Alarm',
                    'status': 'operational'
                }
            ]
        }

        response = self.client.post(
            f'/api/v1/onboarding/site/{self.site.site_id}/assets/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['assets_created'], 2)

        # Verify assets created
        self.assertEqual(Asset.objects.filter(zone=zone).count(), 2)

    def test_create_meter_points_bulk(self):
        """Test bulk meter point creation."""
        zone = OnboardingZone.objects.create(
            site=self.site,
            zone_type='control_room',
            zone_name='Control Room',
            importance_level='high'
        )

        data = {
            'meter_points': [
                {
                    'zone_id': str(zone.zone_id),
                    'meter_type': 'electricity',
                    'meter_name': 'Main Meter',
                    'reading_frequency': 'daily'
                },
                {
                    'zone_id': str(zone.zone_id),
                    'meter_type': 'generator_hours',
                    'meter_name': 'Generator Meter',
                    'reading_frequency': 'daily'
                }
            ]
        }

        response = self.client.post(
            f'/api/v1/onboarding/site/{self.site.site_id}/meter-points/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['meter_points_created'], 2)

        # Verify meter points created
        self.assertEqual(MeterPoint.objects.filter(zone=zone).count(), 2)


class AnalysisPlanningTests(TransactionTestCase):
    """Test suite for analysis and planning APIs."""

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

        # Create zones and observations
        for i in range(3):
            zone = OnboardingZone.objects.create(
                site=self.site,
                zone_type='vault' if i == 0 else 'gate',
                zone_name=f'Zone {i}',
                importance_level='critical'
            )

            Observation.objects.create(
                site=self.site,
                zone=zone,
                transcript_english=f'Observation {i}',
                confidence_score=Decimal('0.85'),
                gps_at_capture=Point(72.8777, 19.0760, srid=4326),
                captured_by=self.user
            )

    @patch('apps.onboarding_api.views.site_audit_views.get_llm_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_checker_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_consensus_engine')
    @patch('apps.onboarding_api.views.site_audit_views.get_knowledge_service')
    def test_trigger_analysis_sync(
        self,
        mock_knowledge,
        mock_consensus,
        mock_checker,
        mock_llm
    ):
        """Test triggering synchronous analysis."""
        # Mock services
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.analyze_site_audit.return_value = {
            'recommendations': ['Install additional cameras']
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
            'recommendations': ['Install additional cameras']
        }

        mock_knowledge_instance = MagicMock()
        mock_knowledge.return_value = mock_knowledge_instance
        mock_knowledge_instance.retrieve_grounded_context.return_value = []

        data = {
            'include_recommendations': True,
            'include_sops': False,
            'include_coverage_plan': False
        }

        response = self.client.post(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/analyze/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('analysis_id', response.data)
        self.assertIn('consensus', response.data)
        self.assertIn('processing_time_ms', response.data)

        # Verify recommendation created
        self.assertTrue(
            LLMRecommendation.objects.filter(
                recommendation_id=response.data['analysis_id']
            ).exists()
        )

    def test_get_coverage_plan(self):
        """Test getting coverage plan after analysis."""
        # Create coverage plan
        CoveragePlan.objects.create(
            site=self.site,
            guard_posts=[{'post_id': 'POST-001', 'zone': 'Gate'}],
            shift_assignments=[{'shift_name': 'Morning', 'start_time': '06:00'}],
            patrol_routes=[],
            risk_windows=[]
        )

        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/coverage-plan/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('guard_posts', response.data)
        self.assertIn('shift_assignments', response.data)

    def test_list_sops(self):
        """Test listing generated SOPs."""
        zone = self.site.zones.first()

        # Create SOPs
        for i in range(3):
            SOP.objects.create(
                site=self.site,
                zone=zone,
                sop_title=f'SOP {i}',
                purpose='Test purpose',
                steps=[],
                staffing_required={},
                frequency='daily'
            )

        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/sops/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)


class ReportingTests(TransactionTestCase):
    """Test suite for reporting APIs."""

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

    @patch('apps.onboarding_api.views.site_audit_views.get_reporting_service')
    @patch('apps.onboarding_api.views.site_audit_views.get_knowledge_service')
    def test_generate_report(self, mock_knowledge, mock_reporting):
        """Test report generation."""
        # Mock services
        mock_reporting_instance = MagicMock()
        mock_reporting.return_value = mock_reporting_instance
        mock_reporting_instance.generate_site_audit_report.return_value = {
            'report_html': '<html>Report</html>',
            'summary': 'Test report',
            'compliance_score': 0.85
        }

        mock_knowledge_instance = MagicMock()
        mock_knowledge.return_value = mock_knowledge_instance
        mock_knowledge_instance.add_document_with_chunking.return_value = uuid.uuid4()

        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/report/',
            {'lang': 'en', 'save_to_kb': 'true', 'format': 'html'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('report_html', response.data)
        self.assertIn('knowledge_id', response.data)
        self.assertIn('summary', response.data)


class AuthenticationTests(TestCase):
    """Test suite for authentication and permissions."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

    def test_unauthenticated_request_denied(self):
        """Test that unauthenticated requests are denied."""
        response = self.client.post('/api/v1/onboarding/site-audit/start/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_request_allowed(self):
        """Test that authenticated requests are allowed."""
        user = User.objects.create_user(
            loginid='test_user',
            email='test@test.com',
            peoplename='Test User',
            password='testpass123'
        )
        self.client.force_authenticate(user=user)

        # Request should at least not return 401
        response = self.client.post('/api/v1/onboarding/site-audit/start/')

        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)