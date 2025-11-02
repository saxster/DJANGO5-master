#!/usr/bin/env python
"""
Simple standalone test for dynamic threshold logic.
Tests the logic directly without any Django dependencies.
"""


class MockBaseline:
    """Mock baseline object for testing the is_anomalous logic."""

    def __init__(self, mean, std_dev, sample_count, is_stable, dynamic_threshold, false_positive_rate):
        self.mean = mean
        self.std_dev = std_dev
        self.sample_count = sample_count
        self.is_stable = is_stable
        self.dynamic_threshold = dynamic_threshold
        self.false_positive_rate = false_positive_rate

    def is_anomalous(self, observed_value):
        """
        Determine if observed value is anomalous using dynamic thresholds.

        This is the EXACT implementation from BaselineProfile model.
        """
        if not self.is_stable or self.std_dev == 0:
            return False, 0.0, 0.0

        # Use dynamic threshold (was: fixed threshold from sensitivity map)
        z_threshold = self.dynamic_threshold

        # More sensitive for stable baselines (sample_count > 100)
        if self.sample_count > 100:
            z_threshold = 2.5

        # Less sensitive for high false positive rate (> 0.3)
        if self.false_positive_rate > 0.3:
            z_threshold = 4.0

        z_score = (observed_value - self.mean) / self.std_dev
        is_anomalous = abs(z_score) > z_threshold

        return is_anomalous, z_score, z_threshold


def test_stable_baseline_uses_sensitive_threshold():
    """Test stable baseline (sample_count > 100) uses threshold 2.5."""
    print("\n=== Test 1: Stable Baseline Uses Sensitive Threshold (2.5) ===")

    baseline = MockBaseline(
        mean=100.0,
        std_dev=10.0,
        sample_count=150,  # > 100 for stable baseline
        is_stable=True,
        dynamic_threshold=3.0,
        false_positive_rate=0.1  # Low FP rate
    )

    # Observed value 3 std devs above mean
    # mean=100, std_dev=10, so 130 = 3.0 z-score
    observed_value = 130.0

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  Sample count: {baseline.sample_count}")
    print(f"  FP rate: {baseline.false_positive_rate}")
    print(f"  Dynamic threshold: {baseline.dynamic_threshold}")
    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score:.2f}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    # Verify
    assert threshold == 2.5, f"FAIL: Expected threshold 2.5 for stable baseline, got {threshold}"
    assert abs(z_score - 3.0) < 0.01, f"FAIL: Expected z_score ~3.0, got {z_score}"
    assert is_anomalous is True, "FAIL: Value with z_score 3.0 should be anomalous with threshold 2.5"
    print("  ✅ PASS")
    return True


def test_high_fp_baseline_uses_conservative_threshold():
    """Test high FP rate baseline (FP > 0.3) uses threshold 4.0."""
    print("\n=== Test 2: High FP Baseline Uses Conservative Threshold (4.0) ===")

    baseline = MockBaseline(
        mean=50.0,
        std_dev=5.0,
        sample_count=80,  # < 100
        is_stable=True,
        dynamic_threshold=3.0,
        false_positive_rate=0.4  # > 0.3 for high FP rate
    )

    # Observed value 3.5 std devs above mean
    # mean=50, std_dev=5, so 67.5 = 3.5 z-score
    observed_value = 67.5

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  Sample count: {baseline.sample_count}")
    print(f"  FP rate: {baseline.false_positive_rate}")
    print(f"  Dynamic threshold: {baseline.dynamic_threshold}")
    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score:.2f}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    # Verify
    assert threshold == 4.0, f"FAIL: Expected threshold 4.0 for high FP baseline, got {threshold}"
    assert abs(z_score - 3.5) < 0.01, f"FAIL: Expected z_score ~3.5, got {z_score}"
    assert is_anomalous is False, "FAIL: Value with z_score 3.5 should NOT be anomalous with threshold 4.0"
    print("  ✅ PASS")
    return True


def test_normal_baseline_uses_dynamic_threshold():
    """Test normal baseline uses configured dynamic_threshold value."""
    print("\n=== Test 3: Normal Baseline Uses Dynamic Threshold ===")

    baseline = MockBaseline(
        mean=25.0,
        std_dev=3.0,
        sample_count=60,  # < 100
        is_stable=True,
        dynamic_threshold=3.5,
        false_positive_rate=0.15  # < 0.3
    )

    # Observed value 3.2 std devs above mean
    # mean=25, std_dev=3, so 34.6 = 3.2 z-score
    observed_value = 34.6

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  Sample count: {baseline.sample_count}")
    print(f"  FP rate: {baseline.false_positive_rate}")
    print(f"  Dynamic threshold: {baseline.dynamic_threshold}")
    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score:.2f}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    # Verify
    assert threshold == 3.5, f"FAIL: Expected threshold 3.5 (dynamic_threshold), got {threshold}"
    assert abs(z_score - 3.2) < 0.01, f"FAIL: Expected z_score ~3.2, got {z_score}"
    assert is_anomalous is False, "FAIL: Value with z_score 3.2 should NOT be anomalous with threshold 3.5"
    print("  ✅ PASS")
    return True


def test_priority_high_fp_overrides_stable():
    """Test that high FP threshold (4.0) takes priority when both conditions are met."""
    print("\n=== Test 4: High FP (4.0) Overrides Stable (2.5) ===")

    baseline = MockBaseline(
        mean=75.0,
        std_dev=8.0,
        sample_count=120,  # > 100 (triggers stable)
        is_stable=True,
        dynamic_threshold=3.0,
        false_positive_rate=0.35  # > 0.3 (triggers high FP)
    )

    # Observed value with z_score = 3.0
    observed_value = 99.0  # 75 + (3.0 * 8)

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  Sample count: {baseline.sample_count} (> 100, triggers stable)")
    print(f"  FP rate: {baseline.false_positive_rate} (> 0.3, triggers high FP)")
    print(f"  Dynamic threshold: {baseline.dynamic_threshold}")
    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score:.2f}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    # The implementation applies stable (2.5) first, then high FP (4.0) overwrites it
    assert threshold == 4.0, f"FAIL: Expected threshold 4.0 (high FP overrides stable), got {threshold}"
    assert abs(z_score - 3.0) < 0.01, f"FAIL: Expected z_score ~3.0, got {z_score}"
    assert is_anomalous is False, "FAIL: z_score 3.0 should NOT be anomalous with threshold 4.0"
    print("  ✅ PASS - High FP threshold correctly overrides stable threshold")
    return True


def test_unstable_baseline_returns_not_anomalous():
    """Test unstable baseline (is_stable=False) returns False."""
    print("\n=== Test 5: Unstable Baseline Returns Not Anomalous ===")

    baseline = MockBaseline(
        mean=100.0,
        std_dev=10.0,
        sample_count=20,  # < 30, so not stable
        is_stable=False,
        dynamic_threshold=3.0,
        false_positive_rate=0.1
    )

    # Even with extreme value
    observed_value = 200.0

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  is_stable: {baseline.is_stable}")
    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    assert is_anomalous is False, "FAIL: Unstable baseline should never return anomaly"
    assert z_score == 0.0, f"FAIL: Expected z_score 0.0, got {z_score}"
    assert threshold == 0.0, f"FAIL: Expected threshold 0.0, got {threshold}"
    print("  ✅ PASS")
    return True


def test_zero_std_dev_returns_not_anomalous():
    """Test baseline with zero std_dev returns False."""
    print("\n=== Test 6: Zero Std Dev Returns Not Anomalous ===")

    baseline = MockBaseline(
        mean=100.0,
        std_dev=0.0,  # Zero standard deviation
        sample_count=50,
        is_stable=True,
        dynamic_threshold=3.0,
        false_positive_rate=0.1
    )

    observed_value = 200.0

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  std_dev: {baseline.std_dev}")
    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    assert is_anomalous is False, "FAIL: Zero std_dev should prevent anomaly detection"
    assert z_score == 0.0, f"FAIL: Expected z_score 0.0, got {z_score}"
    assert threshold == 0.0, f"FAIL: Expected threshold 0.0, got {threshold}"
    print("  ✅ PASS")
    return True


def test_negative_z_score_detection():
    """Test that negative z-scores (below mean) are detected correctly."""
    print("\n=== Test 7: Negative Z-Score Detection ===")

    baseline = MockBaseline(
        mean=100.0,
        std_dev=10.0,
        sample_count=150,  # > 100 for stable baseline
        is_stable=True,
        dynamic_threshold=3.0,
        false_positive_rate=0.1
    )

    # Observed value 3 std devs BELOW mean
    # mean=100, std_dev=10, so 70 = -3.0 z-score
    observed_value = 70.0

    is_anomalous, z_score, threshold = baseline.is_anomalous(observed_value)

    print(f"  Observed value: {observed_value}")
    print(f"  Z-score: {z_score:.2f}")
    print(f"  Threshold used: {threshold}")
    print(f"  Is anomalous: {is_anomalous}")

    assert abs(z_score - (-3.0)) < 0.01, f"FAIL: Expected z_score ~-3.0, got {z_score}"
    assert is_anomalous is True, "FAIL: Negative z-score should be detected using abs()"
    assert threshold == 2.5, f"FAIL: Expected threshold 2.5 (stable baseline), got {threshold}"
    print("  ✅ PASS")
    return True


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("DYNAMIC THRESHOLD LOGIC TEST SUITE")
    print("Testing Gap #6 Implementation")
    print("=" * 70)

    tests = [
        test_stable_baseline_uses_sensitive_threshold,
        test_high_fp_baseline_uses_conservative_threshold,
        test_normal_baseline_uses_dynamic_threshold,
        test_priority_high_fp_overrides_stable,
        test_unstable_baseline_returns_not_anomalous,
        test_zero_std_dev_returns_not_anomalous,
        test_negative_z_score_detection,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"  ❌ FAIL: {e}")
        except Exception as e:
            failed += 1
            print(f"  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    if failed == 0:
        print(f"✅ ALL {passed} TESTS PASSED")
        print("=" * 70)
        print("\nImplementation Summary:")
        print("  • Stable baselines (sample_count > 100) use threshold 2.5 ✅")
        print("  • High FP baselines (FP > 0.3) use threshold 4.0 ✅")
        print("  • Normal baselines use configured dynamic_threshold ✅")
        print("  • High FP threshold takes priority over stable threshold ✅")
        print("  • Edge cases (unstable, zero std dev, negative z-scores) handled ✅")
        print()
        exit(0)
    else:
        print(f"❌ {failed} TEST(S) FAILED, {passed} PASSED")
        print("=" * 70)
        print()
        exit(1)
