#!/usr/bin/env python
"""
Quick check script to verify ORM migration is working.
Run this to ensure all queries are functioning properly.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

from django.db import connection
from apps.core.queries import QueryRepository, ReportQueryRepository
from datetime import datetime, timedelta
from django.utils import timezone


def check_queries():
    """Run basic checks on migrated queries"""
    print("Django ORM Migration Check")
    print("=" * 50)
    
    checks_passed = 0
    checks_failed = 0
    
    # Check 1: Capability queries
    try:
        print("\n1. Checking capability queries...")
        caps = QueryRepository.get_web_caps_for_client()
        print(f"   ✓ Found {len(caps)} web capabilities")
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        checks_failed += 1
    
    # Check 2: BT queries
    try:
        print("\n2. Checking BT queries...")
        # Try with a common parent ID
        children = QueryRepository.get_childrens_of_bt(1)
        print(f"   ✓ get_childrens_of_bt working")
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        checks_failed += 1
    
    # Check 3: Ticket queries
    try:
        print("\n3. Checking ticket queries...")
        tickets = QueryRepository.get_ticketlist_for_escalation()
        print(f"   ✓ Found {len(tickets)} tickets for escalation")
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        checks_failed += 1
    
    # Check 4: Report queries
    try:
        print("\n4. Checking report queries...")
        # Use safe test parameters
        data = ReportQueryRepository.tasksummary_report(
            timezone_str='UTC',
            siteids=[1],
            from_date=timezone.now() - timedelta(days=7),
            upto_date=timezone.now()
        )
        print(f"   ✓ Task summary report working")
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        checks_failed += 1
    
    # Check 5: Database connection
    try:
        print("\n5. Checking database connection...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            print(f"   ✓ Database: {connection.settings_dict['NAME']}")
        checks_passed += 1
    except Exception as e:
        print(f"   ✗ Database error: {str(e)}")
        checks_failed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"SUMMARY: {checks_passed} passed, {checks_failed} failed")
    
    if checks_failed == 0:
        print("\n✓ All checks passed! ORM migration is working correctly.")
        return 0
    else:
        print(f"\n✗ {checks_failed} checks failed. Please review the errors.")
        return 1


if __name__ == '__main__':
    sys.exit(check_queries())