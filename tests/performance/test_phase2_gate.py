"""
Phase 2 Performance Gate: Verify HelpBot ontology integration performance.

PASS CRITERIA:
- HelpBot P95 latency < 500ms (with ontology enabled)
- Error rate < 0.1% during load test (1000 queries)

FAIL ACTION: Disable HELPBOT_USE_ONTOLOGY feature flag

Run with: pytest tests/performance/test_phase2_gate.py -v -s --ds=intelliwiz_config.settings.performance_test
"""

import pytest
import time


@pytest.fixture
def helpbot_service(django_settings):
    """Initialize HelpBot service with ontology enabled."""
    django_settings.FEATURES = {'HELPBOT_USE_ONTOLOGY': True}

    from apps.helpbot.services.knowledge_service import HelpBotKnowledgeService
    return HelpBotKnowledgeService()


def test_helpbot_latency_with_ontology(helpbot_service):
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

    latencies = []
    error_count = 0

    for query in queries:
        for i in range(250):  # 1000 total queries
            try:
                start = time.perf_counter()
                result = helpbot_service.search_knowledge(query, limit=5)
                end = time.perf_counter()
                latencies.append((end - start) * 1000)  # Convert to ms
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Only print first 5 errors
                    print(f"Error on query '{query}' iteration {i}: {e}")

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

    # Assert against threshold
    assert p95 < 500.0, (
        f"P95 latency {p95:.2f}ms exceeds 500ms threshold. "
        f"Ontology integration is too slow. RECOMMENDATION: Keep HELPBOT_USE_ONTOLOGY=False"
    )

    print("✅ Phase 2 Latency Gate: PASSED")


def test_helpbot_error_rate(helpbot_service):
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

    latencies = []
    error_count = 0

    for query in queries:
        for i in range(iterations_per_query):
            try:
                start = time.perf_counter()
                result = helpbot_service.search_knowledge(query, limit=5)
                end = time.perf_counter()
                latencies.append((end - start) * 1000)
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Only print first 5 errors
                    print(f"Error on query '{query}' iteration {i}: {e}")

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

    # Assert against threshold
    assert error_rate < 0.001, (
        f"Error rate {error_rate*100:.2f}% exceeds 0.1% threshold. "
        f"Ontology integration is unstable. RECOMMENDATION: Keep HELPBOT_USE_ONTOLOGY=False"
    )

    print("✅ Phase 2 Error Rate Gate: PASSED")
