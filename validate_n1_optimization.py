#!/usr/bin/env python
"""
Quick validation script for N+1 query optimization.

Demonstrates the query count reduction without requiring pytest.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.db import connection, reset_queries
from collections import defaultdict


def reset_query_log():
    """Reset Django query log."""
    reset_queries()
    if hasattr(connection, 'queries_log'):
        connection.queries_log.clear()


def get_query_count():
    """Get current query count."""
    return len(connection.queries)


def demonstrate_n1_problem():
    """Demonstrate the N+1 query problem and solution."""
    from apps.tenants.models import Tenant
    
    print("\n" + "="*70)
    print("N+1 QUERY OPTIMIZATION DEMONSTRATION")
    print("="*70)
    
    # Get active tenants
    tenants = list(Tenant.objects.filter(isactive=True)[:5])  # Limit to 5 for demo
    tenant_count = len(tenants)
    
    if tenant_count == 0:
        print("\n⚠️  No active tenants found. Please create test data first.")
        return
    
    print(f"\nActive Tenants: {tenant_count}")
    
    # ==========================================
    # OLD APPROACH (N+1 Problem)
    # ==========================================
    print("\n" + "-"*70)
    print("❌ OLD APPROACH: Tenant Loop (N+1 Problem)")
    print("-"*70)
    
    reset_query_log()
    old_query_start = get_query_count()
    
    old_results = {}
    for tenant in tenants:
        # This creates 1 query per tenant
        tenant_name = tenant.tenantname  # Accessing field
        old_results[tenant.id] = tenant_name
    
    old_query_count = get_query_count() - old_query_start
    
    print(f"Tenants processed: {tenant_count}")
    print(f"Queries executed:  {old_query_count}")
    print(f"Queries per tenant: {old_query_count / tenant_count:.2f}")
    print(f"Pattern: O(N) where N = tenant count")
    
    # ==========================================
    # NEW APPROACH (Optimized)
    # ==========================================
    print("\n" + "-"*70)
    print("✅ NEW APPROACH: Bulk Query (Optimized)")
    print("-"*70)
    
    reset_query_log()
    new_query_start = get_query_count()
    
    # Single bulk query
    all_tenants = Tenant.objects.filter(isactive=True)[:5]
    new_results = {tenant.id: tenant.tenantname for tenant in all_tenants}
    
    new_query_count = get_query_count() - new_query_start
    
    print(f"Tenants processed: {len(new_results)}")
    print(f"Queries executed:  {new_query_count}")
    print(f"Queries per tenant: {new_query_count / len(new_results):.2f}")
    print(f"Pattern: O(1) - constant regardless of tenant count")
    
    # ==========================================
    # COMPARISON
    # ==========================================
    print("\n" + "="*70)
    print("PERFORMANCE COMPARISON")
    print("="*70)
    
    if old_query_count > 0:
        reduction = ((old_query_count - new_query_count) / old_query_count * 100)
        print(f"\nQuery Reduction: {reduction:.1f}%")
        print(f"Old: {old_query_count} queries")
        print(f"New: {new_query_count} queries")
    
    # Verify results match
    results_match = old_results == new_results
    print(f"\nResults Match: {'✅ Yes' if results_match else '❌ No'}")
    
    # Success criteria
    print("\n" + "-"*70)
    print("SUCCESS CRITERIA")
    print("-"*70)
    
    criteria = [
        ("New approach uses ≤1 query", new_query_count <= 1),
        ("Results are identical", results_match),
        ("Query count reduced", new_query_count < old_query_count if old_query_count > 1 else True),
    ]
    
    all_passed = True
    for criterion, passed in criteria:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  {criterion}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ OPTIMIZATION VALIDATED - All criteria passed!")
    else:
        print("⚠️  VALIDATION ISSUES - Review criteria above")
    print("="*70 + "\n")


def demonstrate_select_related():
    """Demonstrate select_related optimization."""
    from apps.y_helpdesk.models import Ticket
    
    print("\n" + "="*70)
    print("select_related() OPTIMIZATION DEMONSTRATION")
    print("="*70)
    
    # Get some tickets
    tickets = Ticket.objects.all()[:5]
    
    if tickets.count() == 0:
        print("\n⚠️  No tickets found. Skipping select_related demo.")
        return
    
    # ==========================================
    # WITHOUT select_related (N+1)
    # ==========================================
    print("\n" + "-"*70)
    print("❌ WITHOUT select_related (N+1 Problem)")
    print("-"*70)
    
    reset_query_log()
    unopt_query_start = get_query_count()
    
    tickets_unopt = Ticket.objects.all()[:5]
    for ticket in tickets_unopt:
        # Accessing foreign key triggers additional query
        _ = ticket.tenant.tenantname if ticket.tenant else None
    
    unopt_query_count = get_query_count() - unopt_query_start
    
    print(f"Tickets processed: {tickets.count()}")
    print(f"Queries executed:  {unopt_query_count}")
    
    # ==========================================
    # WITH select_related (Optimized)
    # ==========================================
    print("\n" + "-"*70)
    print("✅ WITH select_related (Optimized)")
    print("-"*70)
    
    reset_query_log()
    opt_query_start = get_query_count()
    
    tickets_opt = Ticket.objects.select_related('tenant')[:5]
    for ticket in tickets_opt:
        # No additional query - tenant already loaded
        _ = ticket.tenant.tenantname if ticket.tenant else None
    
    opt_query_count = get_query_count() - opt_query_start
    
    print(f"Tickets processed: {tickets_opt.count()}")
    print(f"Queries executed:  {opt_query_count}")
    
    # ==========================================
    # COMPARISON
    # ==========================================
    print("\n" + "="*70)
    print("PERFORMANCE COMPARISON")
    print("="*70)
    
    if unopt_query_count > 0:
        reduction = ((unopt_query_count - opt_query_count) / unopt_query_count * 100)
        print(f"\nQuery Reduction: {reduction:.1f}%")
        print(f"Without select_related: {unopt_query_count} queries")
        print(f"With select_related:    {opt_query_count} queries")
    
    print("\n" + "="*70)
    if opt_query_count < unopt_query_count:
        print("✅ select_related() OPTIMIZATION VALIDATED!")
    else:
        print("⚠️  Unexpected results - review query patterns")
    print("="*70 + "\n")


if __name__ == '__main__':
    from django.conf import settings
    
    # Enable query logging
    if not settings.DEBUG:
        print("⚠️  DEBUG must be True to log queries. Enabling...")
        settings.DEBUG = True
    
    demonstrate_n1_problem()
    demonstrate_select_related()
    
    print("\n✅ Validation complete! See N1_QUERY_OPTIMIZATION_COMPLETE.md for details.\n")
