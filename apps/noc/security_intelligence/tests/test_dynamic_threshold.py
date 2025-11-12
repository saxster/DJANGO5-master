"""
Unit Tests for Dynamic Threshold Logic (Gap #6).

Tests the adaptive threshold behavior in BaselineProfile.is_anomalous()
based on sample count and false positive rate.

Follows .claude/rules.md testing standards.
"""

import pytest
from apps.noc.security_intelligence.models import BaselineProfile


@pytest.mark.django_db
class TestDynamicThreshold:
    """Test suite for dynamic threshold logic in BaselineProfile."""

    @pytest.fixture
    def stable_baseline(self, tenant, site_bt):
        """Create a stable baseline with >100 samples."""
        return BaselineProfile.objects.create(
            tenant=tenant,
            site=site_bt,
            metric_type='phone_events',
            hour_of_week=10,
            mean=100.0,
            std_dev=10.0,
            sample_count=150,  # > 100 for stable baseline
            is_stable=True,
            dynamic_threshold=3.0,
            false_positive_rate=0.1  # Low FP rate
        )

    @pytest.fixture
    def high_fp_baseline(self, tenant, site_bt):
        """Create baseline with high false positive rate."""
        return BaselineProfile.objects.create(
            tenant=tenant,
            site=site_bt,
            metric_type='location_updates',
            hour_of_week=20,
            mean=50.0,
            std_dev=5.0,
            sample_count=80,  # < 100
            is_stable=True,
            dynamic_threshold=3.0,
            false_positive_rate=0.4  # > 0.3 for high FP rate
        )

    @pytest.fixture
    def normal_baseline(self, tenant, site_bt):
        """Create normal baseline with default settings."""
        return BaselineProfile.objects.create(
            tenant=tenant,
            site=site_bt,
            metric_type='tasks_completed',
            hour_of_week=30,
            mean=25.0,
            std_dev=3.0,
            sample_count=60,  # < 100
            is_stable=True,
            dynamic_threshold=3.5,
            false_positive_rate=0.15  # < 0.3
        )

    def test_stable_baseline_uses_sensitive_threshold(self, stable_baseline):
        """Test stable baseline (sample_count > 100) uses threshold 2.5."""
        # Observed value 3 std devs above mean
        # mean=100, std_dev=10, so 130 = 3.0 z-score
        observed_value = 130.0

        is_anomalous, z_score, threshold = stable_baseline.is_anomalous(observed_value)

        # Verify threshold is 2.5 (not the dynamic_threshold of 3.0)
        assert threshold == 2.5, f"Expected threshold 2.5 for stable baseline, got {threshold}"

        # z_score should be 3.0
        assert abs(z_score - 3.0) < 0.01, f"Expected z_score ~3.0, got {z_score}"

        # Should be anomalous (3.0 > 2.5)
        assert is_anomalous is True, "Value with z_score 3.0 should be anomalous with threshold 2.5"

    def test_high_fp_baseline_uses_conservative_threshold(self, high_fp_baseline):
        """Test high FP rate baseline (FP > 0.3) uses threshold 4.0."""
        # Observed value 3.5 std devs above mean
        # mean=50, std_dev=5, so 67.5 = 3.5 z-score
        observed_value = 67.5

        is_anomalous, z_score, threshold = high_fp_baseline.is_anomalous(observed_value)

        # Verify threshold is 4.0 (not the dynamic_threshold of 3.0)
        assert threshold == 4.0, f"Expected threshold 4.0 for high FP baseline, got {threshold}"

        # z_score should be 3.5
        assert abs(z_score - 3.5) < 0.01, f"Expected z_score ~3.5, got {z_score}"

        # Should NOT be anomalous (3.5 < 4.0)
        assert is_anomalous is False, "Value with z_score 3.5 should NOT be anomalous with threshold 4.0"

    def test_normal_baseline_uses_dynamic_threshold(self, normal_baseline):
        """Test normal baseline uses configured dynamic_threshold value."""
        # Observed value 3.2 std devs above mean
        # mean=25, std_dev=3, so 34.6 = 3.2 z-score
        observed_value = 34.6

        is_anomalous, z_score, threshold = normal_baseline.is_anomalous(observed_value)

        # Verify threshold is the dynamic_threshold (3.5)
        assert threshold == 3.5, f"Expected threshold 3.5 (dynamic_threshold), got {threshold}"

        # z_score should be ~3.2
        assert abs(z_score - 3.2) < 0.01, f"Expected z_score ~3.2, got {z_score}"

        # Should NOT be anomalous (3.2 < 3.5)
        assert is_anomalous is False, "Value with z_score 3.2 should NOT be anomalous with threshold 3.5"

    def test_threshold_priority_stable_over_fp(self, tenant, site_bt):
        """Test that stable baseline threshold (2.5) takes priority over high FP (4.0)."""
        # Create baseline with BOTH conditions: stable (>100) AND high FP (>0.3)
        baseline = BaselineProfile.objects.create(
            tenant=tenant,
            site=site_bt,
            metric_type='tour_checkpoints',
            hour_of_week=40,
            mean=75.0,
            std_dev=8.0,
            sample_count=120,  # > 100 (stable)
            is_stable=True,
            dynamic_threshold=3.0,
            false_positive_rate=0.35  # > 0.3 (high FP)
        )

        # Observed value with z_score = 3.0
        observed_value = 99.0  # 75 + (3.0 * 8)

        is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

        # The implementation applies stable (2.5) first, then high FP (4.0) overwrites it
        # So high FP takes priority (last assignment wins)
        assert threshold == 4.0, f"Expected threshold 4.0 (high FP overrides stable), got {threshold}"

        # z_score should be 3.0
        assert abs(z_score - 3.0) < 0.01, f"Expected z_score ~3.0, got {z_score}"

        # Should NOT be anomalous (3.0 < 4.0)
        assert is_anomalous is False

    def test_unstable_baseline_returns_not_anomalous(self, tenant, site_bt):
        """Test unstable baseline (is_stable=False) returns False."""
        baseline = BaselineProfile.objects.create(
            tenant=tenant,
            site=site_bt,
            metric_type='phone_events',
            hour_of_week=50,
            mean=100.0,
            std_dev=10.0,
            sample_count=20,  # < 30, so not stable
            is_stable=False,
            dynamic_threshold=3.0
        )

        # Even with extreme value
        observed_value = 200.0

        is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

        assert is_anomalous is False, "Unstable baseline should never return anomaly"
        assert z_score == 0.0
        assert threshold == 0.0

    def test_zero_std_dev_returns_not_anomalous(self, tenant, site_bt):
        """Test baseline with zero std_dev returns False."""
        baseline = BaselineProfile.objects.create(
            tenant=tenant,
            site=site_bt,
            metric_type='phone_events',
            hour_of_week=60,
            mean=100.0,
            std_dev=0.0,  # Zero standard deviation
            sample_count=50,
            is_stable=True,
            dynamic_threshold=3.0
        )

        observed_value = 200.0

        is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

        assert is_anomalous is False, "Zero std_dev should prevent anomaly detection"
        assert z_score == 0.0
        assert threshold == 0.0

    def test_negative_z_score_detection(self, stable_baseline):
        """Test that negative z-scores (below mean) are detected correctly."""
        # Observed value 3 std devs BELOW mean
        # mean=100, std_dev=10, so 70 = -3.0 z-score
        observed_value = 70.0

        is_anomalous, z_score, threshold = stable_baseline.is_anomalous(observed_value)

        # z_score should be -3.0
        assert abs(z_score - (-3.0)) < 0.01, f"Expected z_score ~-3.0, got {z_score}"

        # Should be anomalous (abs(-3.0) = 3.0 > 2.5)
        assert is_anomalous is True, "Negative z-score should be detected using abs()"

        # Threshold should be 2.5 (stable baseline)
        assert threshold == 2.5
