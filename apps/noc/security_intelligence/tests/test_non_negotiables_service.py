"""
Comprehensive Tests for NonNegotiablesService.

Tests scorecard generation, pillar evaluation, and overall health calculation.
Follows .claude/rules.md Rule #11 (specific exception handling).
"""

import pytest
from datetime import date, timedelta
from django.utils import timezone
from django.test import TestCase
from unittest.mock import Mock, patch

from apps.noc.security_intelligence.services import NonNegotiablesService
from apps.noc.security_intelligence.models import NonNegotiablesScorecard
from apps.client_onboarding.models import Bt
from apps.tenants.models import Tenant
from apps.peoples.models import People


@pytest.mark.django_db
class TestNonNegotiablesService(TestCase):
    """Test suite for NonNegotiablesService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = NonNegotiablesService()

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

        # Create test client/BU
        self.client = Bt.objects.create(
            buname="Test Client",
            bucode="TC001",
            tenant=self.tenant,
            cuser=self.user
        )

    def test_generate_scorecard_creates_new_scorecard(self):
        """Test that generate_scorecard creates a new scorecard."""
        check_date = date.today()

        scorecard = self.service.generate_scorecard(
            tenant=self.tenant,
            client=self.client,
            check_date=check_date
        )

        self.assertIsNotNone(scorecard)
        self.assertEqual(scorecard.tenant, self.tenant)
        self.assertEqual(scorecard.client, self.client)
        self.assertEqual(scorecard.check_date, check_date)

    def test_generate_scorecard_updates_existing_scorecard(self):
        """Test that generate_scorecard updates existing scorecard for same date."""
        check_date = date.today()

        # Generate first scorecard
        scorecard1 = self.service.generate_scorecard(
            tenant=self.tenant,
            client=self.client,
            check_date=check_date
        )

        # Generate second scorecard for same date
        scorecard2 = self.service.generate_scorecard(
            tenant=self.tenant,
            client=self.client,
            check_date=check_date
        )

        # Should be same instance (update, not create)
        self.assertEqual(scorecard1.id, scorecard2.id)

        # Should only have one scorecard
        count = NonNegotiablesScorecard.objects.filter(
            tenant=self.tenant,
            client=self.client,
            check_date=check_date
        ).count()
        self.assertEqual(count, 1)

    def test_overall_health_calculation_all_green(self):
        """Test overall health when all pillars are GREEN."""
        check_date = date.today()

        # Mock all pillar evaluations to return GREEN with 100 score
        with patch.object(self.service, '_evaluate_pillar_1_guard_coverage') as mock_p1, \
             patch.object(self.service, '_evaluate_pillar_2_supervision') as mock_p2, \
             patch.object(self.service, '_evaluate_pillar_3_control_desk') as mock_p3, \
             patch.object(self.service, '_evaluate_pillar_4_legal_compliance') as mock_p4, \
             patch.object(self.service, '_evaluate_pillar_5_field_support') as mock_p5, \
             patch.object(self.service, '_evaluate_pillar_6_record_keeping') as mock_p6, \
             patch.object(self.service, '_evaluate_pillar_7_emergency_response') as mock_p7:

            from apps.noc.security_intelligence.services.non_negotiables_service import PillarEvaluation

            for mock in [mock_p1, mock_p2, mock_p3, mock_p4, mock_p5, mock_p6, mock_p7]:
                mock.return_value = PillarEvaluation(
                    pillar_id=1,
                    score=100,
                    status='GREEN',
                    violations=[],
                    recommendations=[]
                )

            scorecard = self.service.generate_scorecard(
                tenant=self.tenant,
                client=self.client,
                check_date=check_date
            )

            self.assertEqual(scorecard.overall_health_status, 'GREEN')
            self.assertEqual(scorecard.overall_health_score, 100)
            self.assertEqual(scorecard.total_violations, 0)
            self.assertEqual(scorecard.critical_violations, 0)

    def test_overall_health_calculation_one_red(self):
        """Test overall health when one pillar is RED."""
        check_date = date.today()

        with patch.object(self.service, '_evaluate_pillar_1_guard_coverage') as mock_p1, \
             patch.object(self.service, '_evaluate_pillar_2_supervision') as mock_p2, \
             patch.object(self.service, '_evaluate_pillar_3_control_desk') as mock_p3, \
             patch.object(self.service, '_evaluate_pillar_4_legal_compliance') as mock_p4, \
             patch.object(self.service, '_evaluate_pillar_5_field_support') as mock_p5, \
             patch.object(self.service, '_evaluate_pillar_6_record_keeping') as mock_p6, \
             patch.object(self.service, '_evaluate_pillar_7_emergency_response') as mock_p7:

            from apps.noc.security_intelligence.services.non_negotiables_service import PillarEvaluation

            # Pillar 1 is RED with violations
            mock_p1.return_value = PillarEvaluation(
                pillar_id=1,
                score=50,
                status='RED',
                violations=[
                    {'type': 'CRITICAL', 'severity': 'CRITICAL', 'description': 'Critical issue'}
                ],
                recommendations=['Fix critical issue']
            )

            # All other pillars are GREEN
            for mock in [mock_p2, mock_p3, mock_p4, mock_p5, mock_p6, mock_p7]:
                mock.return_value = PillarEvaluation(
                    pillar_id=2,
                    score=100,
                    status='GREEN',
                    violations=[],
                    recommendations=[]
                )

            scorecard = self.service.generate_scorecard(
                tenant=self.tenant,
                client=self.client,
                check_date=check_date
            )

            # Overall status should be RED if any pillar is RED
            self.assertEqual(scorecard.overall_health_status, 'RED')
            self.assertEqual(scorecard.total_violations, 1)
            self.assertEqual(scorecard.critical_violations, 1)

    def test_overall_health_calculation_mixed_amber_green(self):
        """Test overall health when pillars are mixed AMBER and GREEN."""
        check_date = date.today()

        with patch.object(self.service, '_evaluate_pillar_1_guard_coverage') as mock_p1, \
             patch.object(self.service, '_evaluate_pillar_2_supervision') as mock_p2, \
             patch.object(self.service, '_evaluate_pillar_3_control_desk') as mock_p3, \
             patch.object(self.service, '_evaluate_pillar_4_legal_compliance') as mock_p4, \
             patch.object(self.service, '_evaluate_pillar_5_field_support') as mock_p5, \
             patch.object(self.service, '_evaluate_pillar_6_record_keeping') as mock_p6, \
             patch.object(self.service, '_evaluate_pillar_7_emergency_response') as mock_p7:

            from apps.noc.security_intelligence.services.non_negotiables_service import PillarEvaluation

            # Pillar 1 is AMBER
            mock_p1.return_value = PillarEvaluation(
                pillar_id=1,
                score=75,
                status='AMBER',
                violations=[
                    {'type': 'WARNING', 'severity': 'MEDIUM', 'description': 'Medium issue'}
                ],
                recommendations=['Address medium issue']
            )

            # All other pillars are GREEN
            for mock in [mock_p2, mock_p3, mock_p4, mock_p5, mock_p6, mock_p7]:
                mock.return_value = PillarEvaluation(
                    pillar_id=2,
                    score=100,
                    status='GREEN',
                    violations=[],
                    recommendations=[]
                )

            scorecard = self.service.generate_scorecard(
                tenant=self.tenant,
                client=self.client,
                check_date=check_date
            )

            # Overall status should be AMBER if any pillar is AMBER (and none are RED)
            self.assertEqual(scorecard.overall_health_status, 'AMBER')
            self.assertEqual(scorecard.total_violations, 1)
            self.assertEqual(scorecard.critical_violations, 0)  # No CRITICAL violations

    def test_scorecard_recommendations_aggregation(self):
        """Test that recommendations from all pillars are aggregated."""
        check_date = date.today()

        with patch.object(self.service, '_evaluate_pillar_1_guard_coverage') as mock_p1, \
             patch.object(self.service, '_evaluate_pillar_2_supervision') as mock_p2, \
             patch.object(self.service, '_evaluate_pillar_3_control_desk') as mock_p3, \
             patch.object(self.service, '_evaluate_pillar_4_legal_compliance') as mock_p4, \
             patch.object(self.service, '_evaluate_pillar_5_field_support') as mock_p5, \
             patch.object(self.service, '_evaluate_pillar_6_record_keeping') as mock_p6, \
             patch.object(self.service, '_evaluate_pillar_7_emergency_response') as mock_p7:

            from apps.noc.security_intelligence.services.non_negotiables_service import PillarEvaluation

            mock_p1.return_value = PillarEvaluation(
                pillar_id=1, score=90, status='GREEN', violations=[],
                recommendations=['Recommendation from Pillar 1']
            )
            mock_p2.return_value = PillarEvaluation(
                pillar_id=2, score=85, status='GREEN', violations=[],
                recommendations=['Recommendation from Pillar 2']
            )

            for mock in [mock_p3, mock_p4, mock_p5, mock_p6, mock_p7]:
                mock.return_value = PillarEvaluation(
                    pillar_id=3, score=100, status='GREEN', violations=[], recommendations=[]
                )

            scorecard = self.service.generate_scorecard(
                tenant=self.tenant,
                client=self.client,
                check_date=check_date
            )

            self.assertIn('Recommendation from Pillar 1', scorecard.recommendations)
            self.assertIn('Recommendation from Pillar 2', scorecard.recommendations)

    def test_scorecard_unique_constraint(self):
        """Test that unique constraint works (one scorecard per tenant/client/date)."""
        check_date = date.today()

        # Generate first scorecard
        scorecard1 = self.service.generate_scorecard(
            tenant=self.tenant,
            client=self.client,
            check_date=check_date
        )

        # Generate second scorecard for same date (should update, not create)
        scorecard2 = self.service.generate_scorecard(
            tenant=self.tenant,
            client=self.client,
            check_date=check_date
        )

        # Should be same ID
        self.assertEqual(scorecard1.id, scorecard2.id)

        # Verify only one record exists
        count = NonNegotiablesScorecard.objects.filter(
            tenant=self.tenant,
            client=self.client,
            check_date=check_date
        ).count()
        self.assertEqual(count, 1)

    def test_scorecard_different_dates(self):
        """Test that different dates create separate scorecards."""
        date1 = date.today()
        date2 = date.today() - timedelta(days=1)

        scorecard1 = self.service.generate_scorecard(
            tenant=self.tenant,
            client=self.client,
            check_date=date1
        )

        scorecard2 = self.service.generate_scorecard(
            tenant=self.tenant,
            client=self.client,
            check_date=date2
        )

        # Should be different scorecards
        self.assertNotEqual(scorecard1.id, scorecard2.id)

        # Verify two records exist
        count = NonNegotiablesScorecard.objects.filter(
            tenant=self.tenant,
            client=self.client
        ).count()
        self.assertEqual(count, 2)
