#!/usr/bin/env python
"""
Phase 2 Performance Gate Runner

Standalone script to test HelpBot ontology integration performance without pytest complexity.

Usage:
    python scripts/run_phase2_gate.py
"""

import os
import sys
import time
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')

django.setup()

from django.conf import settings
from apps.helpbot.services.knowledge_service import HelpBotKnowledgeService


def benchmark_helpbot_with_ontology(queries, iterations_per_query=250):
    """
    Benchmark HelpBot knowledge service with ontology enabled.

    Args:
        queries: List of test queries
        iterations_per_query: Number of times to run each query

    Returns:
        Tuple of (latencies list, error count)
    """
    # Enable ontology feature flag
    settings.FEATURES = {'HELPBOT_USE_ONTOLOGY': True}

    service = HelpBotKnowledgeService()
    latencies = []
    error_count = 0

    print(f"Service initialized. Ontology integration: {service.ontology_service is not None}")

    for query_idx, query in enumerate(queries, 1):
        print(f"\nProcessing query {query_idx}/{len(queries)}: '{query}'", end='', flush=True)
        for i in range(iterations_per_query):
            try:
                start = time.perf_counter()
                result = service.search_knowledge(query, limit=5)
                end = time.perf_counter()
                latencies.append((end - start) * 1000)  # Convert to ms

                if (i + 1) % 50 == 0:
                    print('.', end='', flush=True)
            except (ValueError, TypeError, AttributeError, KeyError, ImportError, RuntimeError) as e:
                error_count += 1
                if error_count <= 3:  # Only print first 3 errors
                    print(f"\nError on iteration {i}: {e}")

        print(" Done!")

    return latencies, error_count


def test_helpbot_latency_with_ontology():
    """HelpBot with ontology should have P95 < 500ms."""
    queries = [
        "how do I authenticate",
        "what is SLA tracking",
        "troubleshoot GPS permissions",
        "explain secure file download"
    ]

    print(f"\n{'='*60}")
    print("Phase 2 Performance Gate: HelpBot Latency Test")
    print(f"{'='*60}")
    print(f"Running load test: {len(queries)} queries × 250 iterations = 1000 total queries")
    print(f"Feature flag: HELPBOT_USE_ONTOLOGY = True")
    print(f"{'='*60}\n")

    latencies, error_count = benchmark_helpbot_with_ontology(queries, iterations_per_query=250)

    if not latencies:
        print("\n❌ FATAL: No successful queries! Cannot proceed.")
        return False

    # Sort for percentile calculations
    latencies.sort()

    # Calculate statistics
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    mean = sum(latencies) / len(latencies)
    min_latency = latencies[0]
    max_latency = latencies[-1]

    print(f"\n{'='*60}")
    print("RESULTS: HelpBot with Ontology Performance")
    print(f"{'='*60}")
    print(f"Total queries: {len(latencies)}")
    print(f"Errors: {error_count}")
    print(f"\nLatency Statistics:")
    print(f"  Min:  {min_latency:7.2f} ms")
    print(f"  P50:  {p50:7.2f} ms")
    print(f"  Mean: {mean:7.2f} ms")
    print(f"  P95:  {p95:7.2f} ms  {'✅ PASS' if p95 < 500.0 else '❌ FAIL'} (threshold: < 500ms)")
    print(f"  P99:  {p99:7.2f} ms")
    print(f"  Max:  {max_latency:7.2f} ms")
    print(f"{'='*60}\n")

    # Check threshold
    if p95 >= 500.0:
        print(f"❌ FAIL: P95 latency {p95:.2f}ms exceeds 500ms threshold")
        print("RECOMMENDATION: Keep HELPBOT_USE_ONTOLOGY=False")
        return False

    print("✅ Phase 2 Latency Gate: PASSED")
    return True


def test_helpbot_error_rate():
    """No errors during load test - error rate must be < 0.1%."""
    queries = ["authentication", "SLA", "GPS", "download", "ticket"]
    total_count = 1000
    iterations_per_query = total_count // len(queries)

    print(f"\n{'='*60}")
    print("Phase 2 Performance Gate: HelpBot Error Rate Test")
    print(f"{'='*60}")
    print(f"Running load test: {len(queries)} queries × {iterations_per_query} iterations = {total_count} total queries")
    print(f"Feature flag: HELPBOT_USE_ONTOLOGY = True")
    print(f"{'='*60}\n")

    latencies, error_count = benchmark_helpbot_with_ontology(queries, iterations_per_query=iterations_per_query)

    actual_total = len(latencies) + error_count
    error_rate = error_count / actual_total if actual_total > 0 else 0

    print(f"\n{'='*60}")
    print("RESULTS: HelpBot Error Rate")
    print(f"{'='*60}")
    print(f"Total queries: {actual_total}")
    print(f"Successful:    {len(latencies)}")
    print(f"Errors:        {error_count}")
    print(f"Error rate:    {error_rate*100:.3f}%  {'✅ PASS' if error_rate < 0.001 else '❌ FAIL'} (threshold: < 0.1%)")
    print(f"{'='*60}\n")

    # Check threshold
    if error_rate >= 0.001:
        print(f"❌ FAIL: Error rate {error_rate*100:.2f}% exceeds 0.1% threshold")
        print("RECOMMENDATION: Keep HELPBOT_USE_ONTOLOGY=False")
        return False

    print("✅ Phase 2 Error Rate Gate: PASSED")
    return True


def main():
    """Run both performance gate tests."""
    print("\n" + "="*60)
    print("PHASE 2 PERFORMANCE GATE - HelpBot Ontology Integration")
    print("="*60)

    try:
        # Run latency test
        latency_passed = test_helpbot_latency_with_ontology()

        # Run error rate test
        error_rate_passed = test_helpbot_error_rate()

        # Final decision
        print("\n" + "="*60)
        if latency_passed and error_rate_passed:
            print("✅ ALL PHASE 2 PERFORMANCE GATES PASSED")
            print("="*60)
            print("\n🎉 DECISION: Enable HELPBOT_USE_ONTOLOGY feature flag")
            print("\nNext steps:")
            print("  1. Update intelliwiz_config/settings/features.py:")
            print("     FEATURES['HELPBOT_USE_ONTOLOGY'] = True")
            print("  2. Commit both gate test and feature flag update")
            print("  3. Proceed to Phase 3: Background Article Generation")
            return 0
        else:
            print("❌ PHASE 2 PERFORMANCE GATE FAILED")
            print("="*60)
            print("\n⚠️  DECISION: Keep HELPBOT_USE_ONTOLOGY=False")
            print("\nAction required:")
            print("  1. Keep feature flag disabled")
            print("  2. Investigate and optimize before enabling")
            print("  3. Consider ROLLBACK if already deployed")
            return 1
    except (ValueError, TypeError, AttributeError, KeyError, ImportError, RuntimeError, SystemError) as e:
        print("\n" + "="*60)
        print("❌ FATAL ERROR during performance gate")
        print("="*60)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        print("\nRECOMMENDATION: Keep HELPBOT_USE_ONTOLOGY=False")
        return 1


if __name__ == '__main__':
    sys.exit(main())
