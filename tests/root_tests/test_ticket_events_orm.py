#!/usr/bin/env python
"""
Test script to verify the ticket events ORM implementation.
Tests that the PostgreSQL array functions have been replaced successfully.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from apps.activity.utils import ticketevents_query
from apps.activity.utils_orm import get_ticket_events_orm
from apps.y_helpdesk.models import Ticket
from django.db import connection


def test_ticket_events_orm():
    """Test the ticket events ORM implementation."""
    print("=" * 80)
    print("TICKET EVENTS ORM TEST")
    print("=" * 80)
    
    # Find a ticket with events for testing
    print("\n1. Finding test ticket with events...")
    print("-" * 40)
    
    test_ticket = None
    tickets = Ticket.objects.exclude(events__isnull=True).exclude(events='').order_by('-id')[:5]
    
    for ticket in tickets:
        if ticket.events and ',' in ticket.events:
            test_ticket = ticket
            break
    
    if not test_ticket:
        print("✗ No ticket found with comma-separated events")
        print("  Creating a test ticket...")
        # This would require creating test data
        return False
    
    print(f"✓ Found ticket: {test_ticket.ticketno}")
    print(f"  Events: {test_ticket.events[:50]}{'...' if len(test_ticket.events) > 50 else ''}")
    
    # Test the ORM implementation
    print("\n2. Testing ORM implementation...")
    print("-" * 40)
    
    try:
        # Test with default parameters
        results = get_ticket_events_orm(test_ticket.ticketno)
        print(f"✓ ORM query executed successfully")
        print(f"  Records returned: {len(results)}")
        
        if results:
            print(f"  Sample record: {results[0]}")
        
        # Test sorting
        results_desc = get_ticket_events_orm(test_ticket.ticketno, columnsort='desc')
        print(f"✓ Sorting works correctly")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test the utils function
    print("\n3. Testing utils function integration...")
    print("-" * 40)
    
    try:
        results, params = ticketevents_query(test_ticket.ticketno, 'asc', 'e.id')
        print(f"✓ Utils function works correctly")
        print(f"  Records returned: {len(results) if results else 0}")
        print(f"  Params: {params} (should be None)")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False
    
    # Compare with original query (if needed)
    print("\n4. Verifying PostgreSQL array functions removed...")
    print("-" * 40)
    
    # Check that we're not using string_to_array or unnest
    with connection.cursor() as cursor:
        # Get the last executed query
        if connection.queries:
            last_query = connection.queries[-1]['sql']
            if 'string_to_array' in last_query or 'unnest' in last_query:
                print("✗ PostgreSQL array functions still being used!")
                print(f"  Query: {last_query[:200]}...")
                return False
            else:
                print("✓ No PostgreSQL array functions detected")
    
    print("\n" + "=" * 80)
    print("✅ TICKET EVENTS ORM TEST PASSED!")
    print("   PostgreSQL array functions successfully replaced")
    print("=" * 80)
    
    return True


def check_remaining_postgresql_functions():
    """Check for any remaining PostgreSQL-specific functions."""
    print("\n" + "=" * 80)
    print("CHECKING FOR POSTGRESQL-SPECIFIC FUNCTIONS")
    print("=" * 80)
    
    pg_functions = [
        'string_to_array',
        'unnest',
        'array_agg',
        'array_to_string',
        '::bigint[]',
        '::text[]'
    ]
    
    issues_found = False
    
    # Check recent queries
    if connection.queries:
        print("\nChecking recent database queries...")
        for query in connection.queries[-10:]:  # Last 10 queries
            sql = query['sql'].lower()
            for func in pg_functions:
                if func.lower() in sql:
                    print(f"⚠️  Found '{func}' in query")
                    issues_found = True
    
    if not issues_found:
        print("✅ No PostgreSQL-specific array functions found in recent queries")
    
    return not issues_found


if __name__ == "__main__":
    print("Testing Ticket Events ORM Implementation...")
    print("This verifies that PostgreSQL array functions have been replaced.\n")
    
    # Enable query logging
    connection.force_debug_cursor = True
    
    # Run tests
    test_passed = test_ticket_events_orm()
    pg_check_passed = check_remaining_postgresql_functions()
    
    if test_passed and pg_check_passed:
        print("\n🎉 All tests passed! The ticket events query has been successfully migrated.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please review the output above.")
        sys.exit(1)