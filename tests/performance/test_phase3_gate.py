"""
Phase 3 Performance Gate: Verify article auto-generation performance.

PASS CRITERIA:
- Task completes in < 10 minutes (106+ articles)
- Memory footprint < 200MB
- Task executes without critical failures

FAIL ACTION: Keep ENABLE_ARTICLE_AUTO_GENERATION feature flag disabled

Following CLAUDE.md:
- Performance thresholds enforced
- Comprehensive logging
- Graceful handling of data quality issues
"""

import pytest
import psutil
import time
from apps.help_center.tasks import sync_ontology_articles_task


@pytest.mark.django_db(transaction=True)
def test_article_sync_completes_within_time_limit(test_tenant):
    """
    Article sync should complete in < 10 minutes.

    Note: Some articles may fail due to ontology data quality issues
    (e.g., missing qualified_name from Task 3.2). Focus is on performance
    (time/memory), not success rate.
    """
    start = time.time()

    result = sync_ontology_articles_task(
        dry_run=False,
        criticality='high'
    )

    elapsed = time.time() - start
    elapsed_minutes = elapsed / 60

    print(f"\n=== Phase 3 Performance Gate Results ===")
    print(f"Duration: {elapsed_minutes:.2f} minutes (limit: 10 minutes)")
    print(f"Total components: {result.get('total_components', 0)}")
    print(f"Articles created: {result.get('articles_created', 0)}")
    print(f"Articles updated: {result.get('articles_updated', 0)}")
    print(f"Errors: {result.get('errors', 0)}")
    print(f"Success: {result.get('success', False)}")

    # Performance gate: Time threshold
    assert elapsed_minutes < 10.0, (
        f"Sync took {elapsed_minutes:.2f} minutes (limit: 10 minutes)"
    )

    # Basic sanity check: Task should return success=True
    # (even if some individual articles failed due to data quality)
    assert result.get('success') is True, (
        f"Task reported failure: {result.get('error', 'unknown error')}"
    )


@pytest.mark.django_db(transaction=True)
def test_article_sync_memory_footprint(test_tenant):
    """
    Article sync memory footprint should be < 200MB.

    Measures memory delta from task execution. Acceptable even if
    some articles fail due to data quality issues.
    """
    process = psutil.Process()

    # Measure initial memory
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Run sync
    result = sync_ontology_articles_task(dry_run=False, criticality='high')

    # Measure final memory
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_delta = final_memory - initial_memory

    print(f"\n=== Memory Footprint ===")
    print(f"Initial memory: {initial_memory:.2f} MB")
    print(f"Final memory: {final_memory:.2f} MB")
    print(f"Memory delta: {memory_delta:.2f} MB (limit: 200 MB)")
    print(f"Articles processed: {result.get('total_components', 0)}")
    print(f"Success: {result.get('success', False)}")

    # Performance gate: Memory threshold
    assert memory_delta < 200.0, (
        f"Memory footprint {memory_delta:.2f}MB exceeds 200MB threshold"
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("criticality", ["high"])
def test_article_sync_graceful_error_handling(test_tenant, criticality):
    """
    Verify task handles errors gracefully without crashing.

    Task should:
    - Continue processing after individual article failures
    - Return success=True with error count
    - Not raise unhandled exceptions
    """
    from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
    from django.core.exceptions import ValidationError

    try:
        result = sync_ontology_articles_task(
            dry_run=False,
            criticality=criticality
        )

        print(f"\n=== Error Handling Test ({criticality}) ===")
        print(f"Total components: {result.get('total_components', 0)}")
        print(f"Articles created: {result.get('articles_created', 0)}")
        print(f"Errors encountered: {result.get('errors', 0)}")
        print(f"Task success: {result.get('success', False)}")

        # Task should complete successfully even with individual errors
        assert result.get('success') is True, (
            "Task should return success=True even with individual article failures"
        )

        # Task should process at least some components
        assert result.get('total_components', 0) > 0, (
            "Task should find components to process"
        )

        # If errors occurred, they should be counted and logged
        error_count = result.get('errors', 0)
        if error_count > 0:
            print(f"Note: {error_count} articles failed (likely data quality issues)")
            # This is acceptable - errors are tracked, not fatal
            assert error_count < result.get('total_components', 0), (
                "Not all articles should fail"
            )

    except (DATABASE_EXCEPTIONS, ValidationError, ValueError, TypeError, KeyError) as e:
        pytest.fail(
            f"Task raised unhandled exception (should handle gracefully): {e}"
        )
