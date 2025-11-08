#!/usr/bin/env python
"""
Team Dashboard Validation Script

Validates that all Team Dashboard components are properly installed.
Run after migration to verify setup.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.db import connection
from django.contrib.auth import get_user_model
from apps.core.services.team_dashboard_service import TeamDashboardService
from apps.core.services.quick_actions import QuickActionsService


def check_database_view():
    """Verify database view exists and works."""
    print("✓ Checking database view...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM v_team_dashboard LIMIT 1;")
            result = cursor.fetchone()
            print(f"  ✅ Database view exists (returns: {result[0]} items)")
            return True
    except Exception as e:
        print(f"  ❌ Database view error: {e}")
        return False


def check_indexes():
    """Verify performance indexes exist."""
    print("✓ Checking indexes...")
    try:
        with connection.cursor() as cursor:
            # Check ticket index
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'ticket' 
                AND indexname = 'idx_ticket_dashboard';
            """)
            ticket_idx = cursor.fetchone()
            
            # Check incident index
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'noc_incident' 
                AND indexname = 'idx_incident_dashboard';
            """)
            incident_idx = cursor.fetchone()
            
            # Check job index
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'job' 
                AND indexname = 'idx_job_dashboard';
            """)
            job_idx = cursor.fetchone()
            
            if ticket_idx and incident_idx and job_idx:
                print(f"  ✅ All indexes created")
                return True
            else:
                print(f"  ⚠️  Some indexes missing:")
                if not ticket_idx:
                    print("    - idx_ticket_dashboard")
                if not incident_idx:
                    print("    - idx_incident_dashboard")
                if not job_idx:
                    print("    - idx_job_dashboard")
                return False
    except Exception as e:
        print(f"  ❌ Index check error: {e}")
        return False


def check_services():
    """Verify service classes are importable."""
    print("✓ Checking services...")
    try:
        # Test service instantiation
        User = get_user_model()
        user = User.objects.filter(is_active=True).first()
        
        if user:
            # Test TeamDashboardService
            stats = TeamDashboardService.get_dashboard_stats(
                tenant_id=user.tenant.id,
                user_id=user.id
            )
            print(f"  ✅ TeamDashboardService works (found {stats['total_items']} items)")
            
            # QuickActionsService is importable
            print(f"  ✅ QuickActionsService importable")
            return True
        else:
            print(f"  ⚠️  No active user found to test with")
            return True
    except Exception as e:
        print(f"  ❌ Service error: {e}")
        return False


def check_urls():
    """Verify URLs are configured."""
    print("✓ Checking URLs...")
    try:
        from django.urls import reverse
        
        dashboard_url = reverse('admin_team_dashboard')
        api_url = reverse('admin_team_dashboard_api')
        
        print(f"  ✅ Dashboard URL: {dashboard_url}")
        print(f"  ✅ API URL: {api_url}")
        return True
    except Exception as e:
        print(f"  ❌ URL error: {e}")
        return False


def check_templates():
    """Verify template exists."""
    print("✓ Checking templates...")
    try:
        from django.template.loader import get_template
        
        template = get_template('admin/core/team_dashboard.html')
        print(f"  ✅ Template found: admin/core/team_dashboard.html")
        return True
    except Exception as e:
        print(f"  ❌ Template error: {e}")
        return False


def check_sample_data():
    """Show sample data from view."""
    print("✓ Fetching sample data...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    item_type,
                    item_number,
                    title,
                    priority,
                    status,
                    urgency_badge
                FROM v_team_dashboard
                LIMIT 5;
            """)
            rows = cursor.fetchall()
            
            if rows:
                print(f"  ✅ Sample data (showing {len(rows)} items):")
                for row in rows:
                    print(f"    - {row[0]}: {row[1]} - {row[2][:50]}... [{row[3]}/{row[5]}]")
            else:
                print(f"  ⚠️  No data in view (this is OK if you have no active tasks)")
            return True
    except Exception as e:
        print(f"  ❌ Sample data error: {e}")
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("Team Dashboard Validation")
    print("=" * 60)
    print()
    
    checks = [
        check_database_view,
        check_indexes,
        check_services,
        check_urls,
        check_templates,
        check_sample_data,
    ]
    
    results = []
    for check in checks:
        result = check()
        results.append(result)
        print()
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ ALL CHECKS PASSED ({passed}/{total})")
        print()
        print("🎉 Team Dashboard is ready to use!")
        print("   Access at: /admin/dashboard/team/")
        sys.exit(0)
    else:
        print(f"⚠️  SOME CHECKS FAILED ({passed}/{total} passed)")
        print()
        print("Please review the errors above and fix before using.")
        sys.exit(1)


if __name__ == '__main__':
    main()
