"""
Unit Tests for Baseline Threshold Update Task.

Tests Gap #6 implementation - dynamic threshold tuning based on false positive rates.

@ontology(
    domain="noc",
    purpose="Unit tests for baseline threshold update task",
    test_coverage=[
        "False positive rate calculation",
        "Threshold adjustment logic based on FP rate",
        "Task execution and statistics"
    ],
    criticality="high",
    tags=["testing", "celery", "anomaly-detection", "baseline"]
)
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from apps.noc.tasks.baseline_tasks import UpdateBaselineThresholdsTask
from apps.noc.security_intelligence.models import BaselineProfile
from apps.noc.models import NOCAlertEvent
from apps.peoples.models import People
from apps.client_onboarding.models import Bt
from apps.tenants.models import Tenant


@pytest.mark.django_db
class TestUpdateBaselineThresholdsTask:
    """Test suite for UpdateBaselineThresholdsTask."""

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        tenant, _ = Tenant.objects.get_or_create(
            schema_name='test_tenant',
            defaults={'name': 'Test Tenant'}
        )
        return tenant

    @pytest.fixture
    def site(self, tenant):
        """Create test site."""
        site = Bt.objects.create(
            tenant=tenant,
            buname='Test Site',
            is_client=True
        )
        return site

    @pytest.fixture
    def baseline_profile(self, tenant, site):
        """Create stable baseline profile."""
        baseline = BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='phone_events',
            hour_of_week=42,  # Wednesday 18:00
            mean=100.0,
            std_dev=15.0,
            sample_count=150,  # Stable baseline
            is_stable=True,
            false_positive_rate=0.0,
            dynamic_threshold=3.0
        )
        return baseline

    @pytest.fixture
    def user(self, tenant):
        """Create test user."""
        user = People.objects.create(
            tenant=tenant,
            peoplename='Test User',
            email='test@example.com'
        )
        return user

    def test_fp_rate_calculation(self, tenant, site, baseline_profile, user):
        """
        Test false positive rate calculation.

        Verifies that FP rate is correctly calculated from alert resolutions.
        """
        # Create 10 alerts linked to this baseline (via metadata)
        alerts = []
        for i in range(10):
            alert = NOCAlertEvent.objects.create(
                tenant=tenant,
                client=site,
                bu=site,
                alert_type='ANOMALY_DETECTED',
                severity='MEDIUM',
                status='RESOLVED',
                message=f'Test alert {i}',
                entity_type='baseline',
                entity_id=baseline_profile.id,
                dedup_key=f'test_alert_{i}',
                metadata={'baseline_id': baseline_profile.id}  # Link to baseline
            )
            alerts.append(alert)

        # Mark 3 alerts as false positives (30% FP rate)
        for i in range(3):
            alerts[i].metadata['false_positive'] = True
            alerts[i].save(update_fields=['metadata'])

        # Run task
        task = UpdateBaselineThresholdsTask()
        result = task.run()

        # Verify FP rate calculation
        baseline_profile.refresh_from_db()
        assert baseline_profile.false_positive_rate == 0.3, \
            f"Expected FP rate 0.3, got {baseline_profile.false_positive_rate}"

        # Verify statistics
        assert result['updated'] == 1
        assert result['total_checked'] == 1

    def test_threshold_adjustment_high_fp_rate(self, tenant, site, baseline_profile, user):
        """
        Test threshold adjustment for high false positive rate.

        When FP rate > BASELINE_FP_THRESHOLD (0.3), should use conservative threshold (4.0).
        """
        config = settings.NOC_CONFIG

        # Create 10 alerts with 4 false positives (40% FP rate - above threshold)
        for i in range(10):
            is_fp = i < 4  # First 4 are FPs
            NOCAlertEvent.objects.create(
                tenant=tenant,
                client=site,
                bu=site,
                alert_type='ANOMALY_DETECTED',
                severity='MEDIUM',
                status='RESOLVED',
                message=f'Test alert {i}',
                entity_type='baseline',
                entity_id=baseline_profile.id,
                dedup_key=f'test_alert_{i}',
                metadata={
                    'baseline_id': baseline_profile.id,
                    'false_positive': is_fp
                }
            )

        # Run task
        task = UpdateBaselineThresholdsTask()
        result = task.run()

        # Verify conservative threshold applied
        baseline_profile.refresh_from_db()
        assert baseline_profile.false_positive_rate == 0.4
        assert baseline_profile.dynamic_threshold == config['BASELINE_CONSERVATIVE_THRESHOLD'], \
            f"Expected conservative threshold {config['BASELINE_CONSERVATIVE_THRESHOLD']}, " \
            f"got {baseline_profile.dynamic_threshold}"

    def test_threshold_adjustment_stable_baseline(self, tenant, site, user):
        """
        Test threshold adjustment for stable baseline with low FP rate.

        When sample_count > BASELINE_STABLE_SAMPLE_COUNT (100) and low FP rate,
        should use sensitive threshold (2.5).
        """
        config = settings.NOC_CONFIG

        # Create baseline with high sample count (stable)
        baseline = BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='tour_checkpoints',
            hour_of_week=24,
            mean=50.0,
            std_dev=8.0,
            sample_count=200,  # Well above stable threshold
            is_stable=True,
            false_positive_rate=0.0,
            dynamic_threshold=3.0
        )

        # Create 10 alerts with only 1 false positive (10% FP rate - low)
        for i in range(10):
            is_fp = (i == 0)  # Only first one is FP
            NOCAlertEvent.objects.create(
                tenant=tenant,
                client=site,
                bu=site,
                alert_type='ANOMALY_DETECTED',
                severity='LOW',
                status='RESOLVED',
                message=f'Test alert {i}',
                entity_type='baseline',
                entity_id=baseline.id,
                dedup_key=f'test_alert_stable_{i}',
                metadata={
                    'baseline_id': baseline.id,
                    'false_positive': is_fp
                }
            )

        # Run task
        task = UpdateBaselineThresholdsTask()
        result = task.run()

        # Verify sensitive threshold applied (stable baseline with low FP rate)
        baseline.refresh_from_db()
        assert baseline.false_positive_rate == 0.1
        assert baseline.dynamic_threshold == config['BASELINE_SENSITIVE_THRESHOLD'], \
            f"Expected sensitive threshold {config['BASELINE_SENSITIVE_THRESHOLD']}, " \
            f"got {baseline.dynamic_threshold}"

    def test_task_execution_statistics(self, tenant, site, user):
        """
        Test task execution and statistics reporting.

        Verifies:
        - Multiple baselines processed correctly
        - Baselines without alerts are skipped
        - Statistics accurately reported
        """
        # Create 3 baselines
        baseline1 = BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='phone_events',
            hour_of_week=10,
            mean=100.0,
            std_dev=15.0,
            sample_count=80,
            is_stable=True
        )

        baseline2 = BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='location_updates',
            hour_of_week=20,
            mean=200.0,
            std_dev=25.0,
            sample_count=90,
            is_stable=True
        )

        baseline3 = BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='tasks_completed',
            hour_of_week=30,
            mean=50.0,
            std_dev=10.0,
            sample_count=120,
            is_stable=True
        )

        # Create alerts only for baseline1 and baseline2 (baseline3 has none)
        for i in range(5):
            NOCAlertEvent.objects.create(
                tenant=tenant,
                client=site,
                bu=site,
                alert_type='ANOMALY_DETECTED',
                severity='MEDIUM',
                status='RESOLVED',
                message=f'Alert for baseline1 - {i}',
                entity_type='baseline',
                entity_id=baseline1.id,
                dedup_key=f'b1_alert_{i}',
                metadata={'baseline_id': baseline1.id, 'false_positive': i < 2}
            )

        for i in range(8):
            NOCAlertEvent.objects.create(
                tenant=tenant,
                client=site,
                bu=site,
                alert_type='ANOMALY_DETECTED',
                severity='HIGH',
                status='RESOLVED',
                message=f'Alert for baseline2 - {i}',
                entity_type='baseline',
                entity_id=baseline2.id,
                dedup_key=f'b2_alert_{i}',
                metadata={'baseline_id': baseline2.id, 'false_positive': i < 1}
            )

        # Run task
        task = UpdateBaselineThresholdsTask()
        result = task.run()

        # Verify statistics
        assert result['total_checked'] == 3, "Should check all 3 stable baselines"
        assert result['updated'] == 2, "Should update 2 baselines with alerts"
        assert result['skipped'] == 1, "Should skip 1 baseline without alerts"

        # Verify updates applied correctly
        baseline1.refresh_from_db()
        baseline2.refresh_from_db()
        baseline3.refresh_from_db()

        assert baseline1.false_positive_rate == 0.4  # 2/5 = 40%
        assert baseline2.false_positive_rate == 0.125  # 1/8 = 12.5%
        assert baseline3.false_positive_rate == 0.0  # No change (no alerts)

        # Verify last_threshold_update is set for updated baselines
        assert baseline1.last_threshold_update is not None
        assert baseline2.last_threshold_update is not None
        assert baseline3.last_threshold_update is None  # Not updated

    def test_only_processes_stable_baselines(self, tenant, site):
        """
        Test that only stable baselines are processed.

        Unstable baselines (is_stable=False) should be skipped entirely.
        """
        # Create unstable baseline
        unstable_baseline = BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='phone_events',
            hour_of_week=15,
            mean=50.0,
            std_dev=10.0,
            sample_count=10,  # Too few samples
            is_stable=False  # Not stable
        )

        # Create stable baseline
        stable_baseline = BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='location_updates',
            hour_of_week=25,
            mean=100.0,
            std_dev=20.0,
            sample_count=150,
            is_stable=True
        )

        # Create alerts for both
        for baseline_id, prefix in [(unstable_baseline.id, 'unstable'), (stable_baseline.id, 'stable')]:
            NOCAlertEvent.objects.create(
                tenant=tenant,
                client=site,
                bu=site,
                alert_type='ANOMALY_DETECTED',
                severity='MEDIUM',
                status='RESOLVED',
                message=f'Test alert for {prefix}',
                entity_type='baseline',
                entity_id=baseline_id,
                dedup_key=f'{prefix}_alert',
                metadata={'baseline_id': baseline_id}
            )

        # Run task
        task = UpdateBaselineThresholdsTask()
        result = task.run()

        # Should only process stable baseline
        assert result['total_checked'] == 1
        assert result['updated'] == 1

        # Verify unstable baseline not updated
        unstable_baseline.refresh_from_db()
        assert unstable_baseline.last_threshold_update is None

        # Verify stable baseline updated
        stable_baseline.refresh_from_db()
        assert stable_baseline.last_threshold_update is not None

    def test_30_day_window_filtering(self, tenant, site, baseline_profile):
        """
        Test that only alerts within 30-day window are considered.

        Older alerts should be ignored for FP rate calculation.
        """
        now = timezone.now()

        # Create old alert (35 days ago) - should be ignored
        old_alert = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=site,
            bu=site,
            alert_type='ANOMALY_DETECTED',
            severity='MEDIUM',
            status='RESOLVED',
            message='Old alert',
            entity_type='baseline',
            entity_id=baseline_profile.id,
            dedup_key='old_alert',
            metadata={'baseline_id': baseline_profile.id, 'false_positive': True}
        )
        # Manually set created_at to 35 days ago
        NOCAlertEvent.objects.filter(id=old_alert.id).update(
            created_at=now - timedelta(days=35)
        )

        # Create recent alert (10 days ago) - should be counted
        recent_alert = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=site,
            bu=site,
            alert_type='ANOMALY_DETECTED',
            severity='MEDIUM',
            status='RESOLVED',
            message='Recent alert',
            entity_type='baseline',
            entity_id=baseline_profile.id,
            dedup_key='recent_alert',
            metadata={'baseline_id': baseline_profile.id, 'false_positive': False}
        )

        # Run task
        task = UpdateBaselineThresholdsTask()
        result = task.run()

        # Verify only recent alert counted (FP rate = 0/1 = 0%)
        baseline_profile.refresh_from_db()
        assert baseline_profile.false_positive_rate == 0.0, \
            f"Expected FP rate 0.0 (old alert ignored), got {baseline_profile.false_positive_rate}"
