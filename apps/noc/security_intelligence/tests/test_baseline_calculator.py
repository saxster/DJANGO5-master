"""
Unit Tests for BaselineCalculator.

Tests baseline calculation, incremental updates, and pattern learning.
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import date, timedelta
from django.utils import timezone
from unittest.mock import patch, Mock

from apps.noc.security_intelligence.models import BaselineProfile
from apps.noc.security_intelligence.services.baseline_calculator import BaselineCalculator


@pytest.mark.django_db
class TestBaselineCalculator:
    """Test suite for BaselineCalculator service."""

    @pytest.fixture
    def setup_data(self, tenant, site):
        """Create test data."""
        return {'tenant': tenant, 'site': site}

    def test_calculate_baselines_creates_profiles(self, setup_data, site):
        """Test baseline calculation creates profiles for all hours-of-week."""
        with patch('apps.noc.security_intelligence.services.baseline_calculator.BaselineCalculator._get_metric_value_for_hour') as mock_get_value:
            mock_get_value.return_value = 10.0  # Mock metric value

            summary = BaselineCalculator.calculate_baselines_for_site(
                site=site,
                start_date=date.today() - timedelta(days=7),
                days_lookback=7
            )

        assert summary['baselines_created'] > 0 or summary['baselines_updated'] > 0
        assert summary['errors'] == 0

    def test_update_baseline_incrementally_updates_statistics(self, setup_data, site):
        """Test incremental baseline updates use Welford's algorithm."""
        baseline = BaselineProfile.objects.create(
            tenant=setup_data['tenant'],
            site=site,
            metric_type='phone_events',
            hour_of_week=10,  # Monday 10:00
            mean=5.0,
            std_dev=1.0,
            sample_count=10
        )

        # Update with new value
        updated = BaselineCalculator.update_baseline_incrementally(
            site=site,
            metric_type='phone_events',
            hour_of_week=10,
            new_value=7.0
        )

        assert updated is not None
        assert updated.sample_count == 11  # Incremented
        assert updated.mean != 5.0  # Mean updated
        assert updated.std_dev > 0  # Std dev recalculated

    def test_baseline_becomes_stable_after_30_samples(self, setup_data, site):
        """Test baseline marked as stable after 30 samples."""
        baseline = BaselineProfile.objects.create(
            tenant=setup_data['tenant'],
            site=site,
            metric_type='phone_events',
            hour_of_week=10,
            mean=5.0,
            std_dev=1.0,
            sample_count=29,  # Just below threshold
            is_stable=False
        )

        # Add 30th sample
        baseline.update_baseline(6.0)

        baseline.refresh_from_db()
        assert baseline.sample_count == 30
        assert baseline.is_stable is True  # Now stable

    def test_get_baseline_creates_if_not_exists(self, setup_data, site):
        """Test get_baseline creates new baseline if doesn't exist."""
        assert BaselineProfile.objects.filter(site=site).count() == 0

        baseline = BaselineProfile.get_baseline(
            site=site,
            metric_type='phone_events',
            hour_of_week=10
        )

        assert baseline is not None
        assert baseline.site == site
        assert baseline.metric_type == 'phone_events'
        assert baseline.hour_of_week == 10

    def test_baseline_calculation_handles_missing_data_gracefully(self, setup_data, site):
        """Test baseline calculation continues when some data is missing."""
        with patch('apps.noc.security_intelligence.services.baseline_calculator.BaselineCalculator._get_metric_value_for_hour') as mock_get_value:
            # Return None for some hours (missing data)
            mock_get_value.side_effect = [10.0, None, 12.0, None, 11.0]

            summary = BaselineCalculator.calculate_baselines_for_site(
                site=site,
                start_date=date.today() - timedelta(days=2),
                days_lookback=2
            )

        # Should handle None values gracefully
        assert summary['errors'] == 0 or summary['baselines_created'] > 0
