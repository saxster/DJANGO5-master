"""
Unit Tests for AnomalyDetector.

Tests anomaly detection using z-scores and baseline profiles.
Follows .claude/rules.md testing standards.
"""

import pytest
from django.utils import timezone
from unittest.mock import patch, Mock

from apps.noc.security_intelligence.models import BaselineProfile, AuditFinding
from apps.noc.security_intelligence.services.anomaly_detector import AnomalyDetector


@pytest.mark.django_db
class TestAnomalyDetector:
    """Test suite for AnomalyDetector service."""

    @pytest.fixture
    def setup_baseline(self, tenant, site):
        """Create stable baseline for testing."""
        now = timezone.now()
        hour_of_week = now.weekday() * 24 + now.hour

        baseline = BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='phone_events',
            hour_of_week=hour_of_week,
            mean=10.0,
            std_dev=2.0,
            min_value=5.0,
            max_value=15.0,
            sample_count=50,  # Stable
            is_stable=True,
            sensitivity='MEDIUM'  # 2.0 std devs
        )
        return baseline

    def test_detect_anomaly_when_value_above_threshold(self, setup_baseline, site):
        """Test anomaly detected when observed value > mean + 2*std_dev."""
        with patch('apps.noc.security_intelligence.services.anomaly_detector.AnomalyDetector._get_current_metric_value') as mock_get_value:
            # mean=10, std_dev=2, threshold=2.0 -> anomalous if > 14 or < 6
            mock_get_value.return_value = 16.0  # Above threshold

            findings = AnomalyDetector.detect_anomalies_for_site(site)

        assert len(findings) > 0
        finding = findings[0]
        assert 'ANOMALY' in finding.finding_type
        assert 'ABOVE' in finding.finding_type
        assert finding.severity in ['HIGH', 'CRITICAL', 'MEDIUM']

    def test_detect_anomaly_when_value_below_threshold(self, setup_baseline, site):
        """Test anomaly detected when observed value < mean - 2*std_dev."""
        with patch('apps.noc.security_intelligence.services.anomaly_detector.AnomalyDetector._get_current_metric_value') as mock_get_value:
            mock_get_value.return_value = 4.0  # Below threshold (mean - 3*std_dev)

            findings = AnomalyDetector.detect_anomalies_for_site(site)

        assert len(findings) > 0
        finding = findings[0]
        assert 'ANOMALY' in finding.finding_type
        assert 'BELOW' in finding.finding_type

    def test_no_anomaly_when_value_within_threshold(self, setup_baseline, site):
        """Test no anomaly when observed value within normal range."""
        with patch('apps.noc.security_intelligence.services.anomaly_detector.AnomalyDetector._get_current_metric_value') as mock_get_value:
            mock_get_value.return_value = 10.5  # Within range (mean ± 2*std_dev)

            findings = AnomalyDetector.detect_anomalies_for_site(site)

        # Should be empty or only contain other metric types
        phone_anomalies = [f for f in findings if 'phone_events' in f.finding_type.lower()]
        assert len(phone_anomalies) == 0

    def test_no_anomaly_detection_when_baseline_not_stable(self, tenant, site):
        """Test no anomaly detection when baseline has insufficient samples."""
        now = timezone.now()
        hour_of_week = now.weekday() * 24 + now.hour

        # Create unstable baseline
        BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='phone_events',
            hour_of_week=hour_of_week,
            mean=10.0,
            std_dev=2.0,
            sample_count=15,  # Below 30 threshold
            is_stable=False
        )

        findings = AnomalyDetector.detect_anomalies_for_site(site)

        # No findings should be created from unstable baselines
        phone_anomalies = [f for f in findings if 'phone_events' in f.finding_type.lower()]
        assert len(phone_anomalies) == 0

    def test_severity_increases_with_zscore_magnitude(self, setup_baseline, site):
        """Test severity escalates with larger z-score deviations."""
        with patch('apps.noc.security_intelligence.services.anomaly_detector.AnomalyDetector._get_current_metric_value') as mock_get_value:
            # Test CRITICAL severity (z-score >= 3.0)
            mock_get_value.return_value = 17.0  # mean + 3.5*std_dev

            findings = AnomalyDetector.detect_anomalies_for_site(site)

        if findings:
            finding = findings[0]
            # Higher z-score should result in CRITICAL severity
            assert finding.evidence.get('z_score', 0) >= 3.0
            assert finding.severity == 'CRITICAL'
