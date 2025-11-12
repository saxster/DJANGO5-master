#!/usr/bin/env python
"""
Benchmark Predictive Tasks Performance.

Compares old vs new implementation to verify 60-70% query reduction.

Usage:
    python scripts/benchmark_predictive_tasks.py
"""

import os
import sys
import django
import time
from collections import defaultdict

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.db import connection, reset_queries
from django.test.utils import override_settings
from apps.tenants.models import Tenant


def reset_query_log():
    """Reset Django query log."""
    reset_queries()
    connection.queries_log.clear()


def get_query_count():
    """Get current query count."""
    return len(connection.queries)


def benchmark_old_approach():
    """
    Benchmark OLD approach: tenant loop with individual queries.
    
    Returns:
        (query_count, execution_time)
    """
    from apps.y_helpdesk.models import Ticket
    
    reset_query_log()
    
    tenants = Tenant.objects.filter(isactive=True)
    
    start_time = time.time()
    results = {}
    
    # OLD APPROACH: Loop through tenants (N+1 queries)
    for tenant in tenants:
        tickets = Ticket.objects.filter(
            tenant=tenant,
            status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS']
        )
        results[tenant.id] = tickets.count()
    
    execution_time = time.time() - start_time
    query_count = get_query_count()
    
    return query_count, execution_time, results


def benchmark_new_approach():
    """
    Benchmark NEW approach: bulk query with select_related.
    
    Returns:
        (query_count, execution_time)
    """
    from apps.y_helpdesk.models import Ticket
    
    reset_query_log()
    
    start_time = time.time()
    
    # NEW APPROACH: Single bulk query
    all_tickets = Ticket.objects.filter(
        status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS'],
        tenant__isactive=True
    ).select_related('tenant', 'client', 'bu')
    
    # Group by tenant in memory (no additional queries)
    tickets_by_tenant = defaultdict(list)
    for ticket in all_tickets:
        tickets_by_tenant[ticket.tenant_id].append(ticket)
    
    results = {tenant_id: len(tickets) for tenant_id, tickets in tickets_by_tenant.items()}
    
    execution_time = time.time() - start_time
    query_count = get_query_count()
    
    return query_count, execution_time, results


def print_benchmark_results():
    """Run benchmarks and print comparison."""
    print("\n" + "="*70)
    print("PREDICTIVE TASKS PERFORMANCE BENCHMARK")
    print("="*70)
    
    # Get tenant count
    tenant_count = Tenant.objects.filter(isactive=True).count()
    print(f"\nActive Tenants: {tenant_count}")
    
    if tenant_count == 0:
        print("\n⚠️  No active tenants found. Skipping benchmark.")
        return
    
    # Benchmark old approach
    print("\n📊 OLD APPROACH (Tenant Loop):")
    print("-" * 70)
    old_queries, old_time, old_results = benchmark_old_approach()
    print(f"   Query Count:     {old_queries}")
    print(f"   Execution Time:  {old_time:.4f}s")
    print(f"   Queries/Tenant:  {old_queries/tenant_count:.2f}")
    
    # Benchmark new approach
    print("\n✅ NEW APPROACH (Bulk Query):")
    print("-" * 70)
    new_queries, new_time, new_results = benchmark_new_approach()
    print(f"   Query Count:     {new_queries}")
    print(f"   Execution Time:  {new_time:.4f}s")
    print(f"   Queries/Tenant:  {new_queries/tenant_count:.2f}")
    
    # Calculate improvements
    print("\n🚀 PERFORMANCE IMPROVEMENT:")
    print("-" * 70)
    
    query_reduction = ((old_queries - new_queries) / old_queries * 100) if old_queries > 0 else 0
    time_reduction = ((old_time - new_time) / old_time * 100) if old_time > 0 else 0
    
    print(f"   Query Reduction:  {query_reduction:.1f}% ({old_queries} → {new_queries})")
    print(f"   Time Reduction:   {time_reduction:.1f}% ({old_time:.4f}s → {new_time:.4f}s)")
    
    # Verify results match
    if old_results == new_results:
        print(f"   Results Match:    ✅ Both approaches produced identical results")
    else:
        print(f"   Results Match:    ⚠️  Results differ (old: {len(old_results)}, new: {len(new_results)})")
    
    # Success criteria
    print("\n📋 SUCCESS CRITERIA:")
    print("-" * 70)
    
    criteria = [
        ("Query reduction ≥60%", query_reduction >= 60.0),
        ("New approach uses ≤2 queries", new_queries <= 2),
        ("Results are identical", old_results == new_results),
        ("Execution time improved", new_time <= old_time),
    ]
    
    for criterion, passed in criteria:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}  {criterion}")
    
    all_passed = all(passed for _, passed in criteria)
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL BENCHMARKS PASSED - Optimization successful!")
    else:
        print("⚠️  SOME BENCHMARKS FAILED - Review optimization")
    print("="*70 + "\n")


if __name__ == '__main__':
    with override_settings(DEBUG=True):  # Enable query logging
        print_benchmark_results()
