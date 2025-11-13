#!/usr/bin/env python
"""
Analyze Phase 1-3 metrics to decide on Phase 4 Unified Service.

Decision Criteria (from plan):
- Memory delta < 8.0 MB → PROCEED
- HelpBot P95 < 400.0 ms → PROCEED
- help_center P95 < 150.0 ms → PROCEED

If ALL three criteria met → PROCEED to Phase 4
If ANY threshold exceeded → DEFER Phase 4
"""

import json
import os
import sys


def load_baseline():
    """Load performance baseline metrics."""
    baseline_path = os.path.join(
        os.path.dirname(__file__),
        '../performance_baseline.json'
    )

    if not os.path.exists(baseline_path):
        print("❌ ERROR: performance_baseline.json not found")
        print(f"   Expected location: {baseline_path}")
        return None

    with open(baseline_path) as f:
        return json.load(f)


def analyze_metrics():
    """Analyze Phase 1-3 metrics to decide on Phase 4."""

    print("=" * 70)
    print("Phase 4 Decision Analysis: Unified Knowledge Service")
    print("=" * 70)
    print()

    # Load performance data
    baseline = load_baseline()

    if baseline is None:
        print("Cannot proceed without baseline metrics.")
        return False

    print("📊 Performance Metrics from Phases 1-3:")
    print("-" * 70)

    # Extract metrics
    memory_delta_mb = baseline['memory']['delta_mb']
    helpbot_p95_ms = baseline['mock_benchmarks']['helpbot']['p95']
    help_center_p95_ms = baseline['mock_benchmarks']['help_center']['p95']

    # Decision thresholds
    MEMORY_THRESHOLD = 8.0  # MB
    HELPBOT_LATENCY_THRESHOLD = 400.0  # ms
    HELP_CENTER_LATENCY_THRESHOLD = 150.0  # ms

    # Evaluate each criterion
    memory_check = memory_delta_mb < MEMORY_THRESHOLD
    helpbot_check = helpbot_p95_ms < HELPBOT_LATENCY_THRESHOLD
    help_center_check = help_center_p95_ms < HELP_CENTER_LATENCY_THRESHOLD

    # Display results
    print(f"1. Memory Delta:")
    print(f"   Current:   {memory_delta_mb:.2f} MB")
    print(f"   Threshold: {MEMORY_THRESHOLD:.2f} MB")
    print(f"   Status:    {'✅ PASS' if memory_check else '❌ FAIL'}")
    print()

    print(f"2. HelpBot P95 Latency:")
    print(f"   Current:   {helpbot_p95_ms:.4f} ms")
    print(f"   Threshold: {HELPBOT_LATENCY_THRESHOLD:.2f} ms")
    print(f"   Status:    {'✅ PASS' if helpbot_check else '❌ FAIL'}")
    print()

    print(f"3. help_center P95 Latency:")
    print(f"   Current:   {help_center_p95_ms:.6f} ms")
    print(f"   Threshold: {HELP_CENTER_LATENCY_THRESHOLD:.2f} ms")
    print(f"   Status:    {'✅ PASS' if help_center_check else '❌ FAIL'}")
    print()

    print("-" * 70)

    # Final decision
    all_pass = memory_check and helpbot_check and help_center_check

    print()
    print("=" * 70)
    if all_pass:
        print("✅ DECISION: PROCEED to Phase 4")
        print()
        print("All performance criteria met. Phase 4 Unified Knowledge Service")
        print("implementation can proceed with confidence.")
        print()
        print("Next Steps:")
        print("  1. Review docs/decisions/phase4-unified-service-decision.md")
        print("  2. Implement UnifiedKnowledgeService with aggressive caching")
        print("  3. A/B test with 10% traffic initially")
        print("  4. Monitor performance closely during rollout")
    else:
        print("❌ DECISION: DEFER Phase 4")
        print()
        print("One or more performance criteria not met. Phase 4 should be")
        print("deferred until further optimization of Phases 1-3.")
        print()
        print("Recommendations:")
        if not memory_check:
            print(f"  • Investigate memory delta ({memory_delta_mb:.2f}MB > {MEMORY_THRESHOLD}MB)")
            print("    - Profile memory usage with py-spy")
            print("    - Review ontology registry caching strategy")
        if not helpbot_check:
            print(f"  • Optimize HelpBot latency ({helpbot_p95_ms:.2f}ms > {HELPBOT_LATENCY_THRESHOLD}ms)")
            print("    - Review ontology query caching effectiveness")
            print("    - Consider async query execution")
        if not help_center_check:
            print(f"  • Optimize help_center latency ({help_center_p95_ms:.6f}ms > {HELP_CENTER_LATENCY_THRESHOLD}ms)")
            print("    - Profile search query execution")
            print("    - Review database indexing")
        print()
        print("  • Re-evaluate Phase 4 in Q1 2026 after optimization")

    print("=" * 70)
    print()

    return all_pass


def main():
    """Main entry point."""
    proceed = analyze_metrics()

    # Exit with appropriate code
    sys.exit(0 if proceed else 1)


if __name__ == '__main__':
    main()
