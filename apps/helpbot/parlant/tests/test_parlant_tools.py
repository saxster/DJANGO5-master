"""
Comprehensive Tests for Parlant Tools.

Tests all async tools for scorecard operations, violations, escalation, and SOPs.
Follows .claude/rules.md Rule #11 (specific exception handling).
"""

import pytest
from datetime import date
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase

from apps.tenants.models import Tenant
from apps.peoples.models import People
from apps.onboarding.models import Bt


@pytest.mark.django_db
@pytest.mark.asyncio
class TestParlantTools(TestCase):
    """Test suite for Parlant async tools."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            schema_name="test_tenant",
            domain_url="test.example.com"
        )

        # Create test user
        self.user = People.objects.create(
            loginid="testuser",
            peoplename="Test User",
            email="test@example.com",
            tenant=self.tenant
        )

        # Create test client
        self.client = Bt.objects.create(
            buname="Test Client",
            bucode="TC001",
            tenant=self.tenant,
            cuser=self.user,
            isactive=True
        )

        # Mock Parlant ToolContext
        self.mock_context = Mock()
        self.mock_context.session_data = {
            'tenant': self.tenant,
            'client': self.client,
            'user': self.user,
        }

    async def test_get_scorecard_tool(self):
        """Test get_scorecard tool returns valid scorecard data."""
        from apps.helpbot.parlant.tools.scorecard_tools import get_scorecard

        # Mock NonNegotiablesService
        with patch('apps.helpbot.parlant.tools.scorecard_tools.NonNegotiablesService') as MockService:
            mock_scorecard = Mock()
            mock_scorecard.check_date = date.today()
            mock_scorecard.overall_health_status = 'GREEN'
            mock_scorecard.overall_health_score = 95
            mock_scorecard.total_violations = 0
            mock_scorecard.critical_violations = 0
            mock_scorecard.pillar_1_score = 100
            mock_scorecard.pillar_2_score = 90
            mock_scorecard.violations_detail = {}
            mock_scorecard.recommendations = []

            MockService.return_value.generate_scorecard.return_value = mock_scorecard

            result = await get_scorecard(self.mock_context)

            self.assertTrue(result.success)
            self.assertEqual(result.data['overall_health_status'], 'GREEN')
            self.assertEqual(result.data['overall_health_score'], 95)

    async def test_get_pillar_violations_tool(self):
        """Test get_pillar_violations returns violations for specific pillar."""
        from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_violations

        # Mock get_scorecard to return scorecard with violations
        with patch('apps.helpbot.parlant.tools.scorecard_tools.get_scorecard') as mock_get_scorecard:
            mock_result = Mock()
            mock_result.success = True
            mock_result.data = {
                'violations_detail': {
                    'pillar_2': [
                        {
                            'type': 'TOUR_OVERDUE',
                            'severity': 'HIGH',
                            'description': 'Tour overdue by 45 minutes'
                        }
                    ]
                },
                'pillar_scores': {'2': 70}
            }
            mock_get_scorecard.return_value = mock_result

            result = await get_pillar_violations(self.mock_context, pillar_id=2)

            self.assertTrue(result.success)
            self.assertEqual(result.data['pillar_id'], 2)
            self.assertEqual(result.data['violation_count'], 1)
            self.assertEqual(result.data['pillar_score'], 70)

    async def test_escalate_violation_creates_alert(self):
        """Test escalate_violation creates NOC alert."""
        from apps.helpbot.parlant.tools.scorecard_tools import escalate_violation

        with patch('apps.helpbot.parlant.tools.scorecard_tools.AlertCorrelationService') as MockAlertService:
            mock_alert = Mock()
            mock_alert.id = 12345
            MockAlertService.process_alert.return_value = mock_alert

            result = await escalate_violation(
                self.mock_context,
                pillar_id=2,
                violation_type='TOUR_OVERDUE',
                description='Tour overdue by 45 minutes',
                severity='CRITICAL'
            )

            self.assertTrue(result.data['success'])
            self.assertEqual(result.data['alert_id'], 12345)
            MockAlertService.process_alert.assert_called_once()

    async def test_explain_pillar_returns_requirements(self):
        """Test explain_pillar returns pillar requirements and criteria."""
        from apps.helpbot.parlant.tools.scorecard_tools import explain_pillar

        result = await explain_pillar(self.mock_context, pillar_id=7)

        self.assertTrue(result.success)
        self.assertEqual(result.data['name'], 'Respond to Emergencies')
        self.assertIn('requirement', result.data)
        self.assertIn('sla', result.data)
        self.assertIn('green_criteria', result.data)

    async def test_get_critical_violations_filters_correctly(self):
        """Test get_critical_violations returns only CRITICAL severity."""
        from apps.helpbot.parlant.tools.scorecard_tools import get_critical_violations

        with patch('apps.helpbot.parlant.tools.scorecard_tools.get_scorecard') as mock_get_scorecard:
            mock_result = Mock()
            mock_result.success = True
            mock_result.data = {
                'violations_detail': {
                    'pillar_2': [
                        {'severity': 'CRITICAL', 'type': 'TOUR_OVERDUE'},
                        {'severity': 'MEDIUM', 'type': 'CHECKPOINT_LOW'},
                    ],
                    'pillar_7': [
                        {'severity': 'CRITICAL', 'type': 'EMERGENCY_DELAYED'},
                    ]
                }
            }
            mock_get_scorecard.return_value = mock_result

            result = await get_critical_violations(self.mock_context)

            self.assertTrue(result.success)
            self.assertEqual(result.data['critical_count'], 2)  # Only 2 CRITICAL
            self.assertTrue(result.data['requires_immediate_action'])
