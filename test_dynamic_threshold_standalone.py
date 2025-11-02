#!/usr/bin/env python
"""
Standalone test for dynamic threshold logic.
Tests the is_anomalous() method directly without Django test infrastructure.
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings_test')
sys.path.insert(0, '/Users/amar/Desktop/MyCode/DJANGO5-master')

django.setup()

from apps.noc.security_intelligence.models import BaselineProfile


class MockTenant:
    """Mock tenant object for testing."""
    id = 1


class MockSite:
    """Mock site object for testing."""
    id = 1
    buname = "Test Site"
    tenant = MockTenant()


def test_stable_baseline_uses_sensitive_threshold():
    """Test stable baseline (sample_count > 100) uses threshold 2.5."""
    print("\n=== Test 1: Stable Baseline Uses Sensitive Threshold (2.5) ===")

    # Create mock baseline
    baseline = BaselineProfile()
    baseline.tenant = MockTenant()
    baseline.site = MockSite()
    baseline.metric_type = 'phone_events'
    baseline.hour_of_week = 10
    baseline.mean = 100.0
    baseline.std_dev = 10.0
    baseline.sample_count = 150  # > 100 for stable baseline
    baseline.is_stable = True
    baseline.dynamic_threshold = 3.0
    baseline.false_positive_rate = 0.1  # Low FP rate

    # Observed value 3 std devs above mean
    # mean=100, std_dev=10, so 130 = 3.0 z-score
    observed_value = 130.0

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  Sample count: {baseline.sample_count}")
    print(f"  FP rate: {baseline.false_positive_rate}")
    print(f"  Dynamic threshold: {baseline.dynamic_threshold}")
    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    # Verify
    assert threshold == 2.5, f"FAIL: Expected threshold 2.5 for stable baseline, got {threshold}"
    assert abs(z_score - 3.0) < 0.01, f"FAIL: Expected z_score ~3.0, got {z_score}"
    assert is_anomalous is True, "FAIL: Value with z_score 3.0 should be anomalous with threshold 2.5"
    print("  ✅ PASS")


def test_high_fp_baseline_uses_conservative_threshold():
    """Test high FP rate baseline (FP > 0.3) uses threshold 4.0."""
    print("\n=== Test 2: High FP Baseline Uses Conservative Threshold (4.0) ===")

    baseline = BaselineProfile()
    baseline.tenant = MockTenant()
    baseline.site = MockSite()
    baseline.metric_type = 'location_updates'
    baseline.hour_of_week = 20
    baseline.mean = 50.0
    baseline.std_dev = 5.0
    baseline.sample_count = 80  # < 100
    baseline.is_stable = True
    baseline.dynamic_threshold = 3.0
    baseline.false_positive_rate = 0.4  # > 0.3 for high FP rate

    # Observed value 3.5 std devs above mean
    # mean=50, std_dev=5, so 67.5 = 3.5 z-score
    observed_value = 67.5

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  Sample count: {baseline.sample_count}")
    print(f"  FP rate: {baseline.false_positive_rate}")
    print(f"  Dynamic threshold: {baseline.dynamic_threshold}")
    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    # Verify
    assert threshold == 4.0, f"FAIL: Expected threshold 4.0 for high FP baseline, got {threshold}"
    assert abs(z_score - 3.5) < 0.01, f"FAIL: Expected z_score ~3.5, got {z_score}"
    assert is_anomalous is False, "FAIL: Value with z_score 3.5 should NOT be anomalous with threshold 4.0"
    print("  ✅ PASS")


def test_normal_baseline_uses_dynamic_threshold():
    """Test normal baseline uses configured dynamic_threshold value."""
    print("\n=== Test 3: Normal Baseline Uses Dynamic Threshold ===")

    baseline = BaselineProfile()
    baseline.tenant = MockTenant()
    baseline.site = MockSite()
    baseline.metric_type = 'tasks_completed'
    baseline.hour_of_week = 30
    baseline.mean = 25.0
    baseline.std_dev = 3.0
    baseline.sample_count = 60  # < 100
    baseline.is_stable = True
    baseline.dynamic_threshold = 3.5
    baseline.false_positive_rate = 0.15  # < 0.3

    # Observed value 3.2 std devs above mean
    # mean=25, std_dev=3, so 34.6 = 3.2 z-score
    observed_value = 34.6

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  Sample count: {baseline.sample_count}")
    print(f"  FP rate: {baseline.false_positive_rate}")
    print(f"  Dynamic threshold: {baseline.dynamic_threshold}")
    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    # Verify
    assert threshold == 3.5, f"FAIL: Expected threshold 3.5 (dynamic_threshold), got {threshold}"
    assert abs(z_score - 3.2) < 0.01, f"FAIL: Expected z_score ~3.2, got {z_score}"
    assert is_anomalous is False, "FAIL: Value with z_score 3.2 should NOT be anomalous with threshold 3.5"
    print("  ✅ PASS")


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("DYNAMIC THRESHOLD LOGIC TEST SUITE")
    print("Testing Gap #6 Implementation")
    print("=" * 70)

    try:
        test_stable_baseline_uses_sensitive_threshold()
        test_high_fp_baseline_uses_conservative_threshold()
        test_normal_baseline_uses_dynamic_threshold()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\nSummary:")
        print("  • Test 1: Stable baselines (sample_count > 100) use threshold 2.5 ✅")
        print("  • Test 2: High FP baselines (FP > 0.3) use threshold 4.0 ✅")
        print("  • Test 3: Normal baselines use configured dynamic_threshold ✅")
        print()
        sys.exit(0)

    except AssertionError as e:
        print("\n" + "=" * 70)
        print("❌ TEST FAILED")
        print("=" * 70)
        print(f"\nError: {e}")
        print()
        sys.exit(1)

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ ERROR RUNNING TESTS")
        print("=" * 70)
        print(f"\nException: {e}")
        import traceback
        traceback.print_exc()
        print()
        sys.exit(1)
