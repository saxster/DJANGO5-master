#!/usr/bin/env python
"""
Validation script for N+1 query optimizations Part 2.

Checks that all critical N+1 patterns have been fixed in NOC and Reports apps.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.db import connection
from django.test.utils import override_settings
from apps.noc.models import NOCIncident, NOCAlertEvent
from apps.client_onboarding.models import Bt
from apps.peoples.models import People


class Colors:
    """Terminal colors."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_status(message, status='info'):
    """Print colored status message."""
    colors = {
        'success': Colors.GREEN,
        'error': Colors.RED,
        'warning': Colors.YELLOW,
        'info': Colors.BLUE
    }
    color = colors.get(status, '')
    print(f"{color}{message}{Colors.END}")


def validate_incident_manager():
    """Verify OptimizedIncidentManager exists and works."""
    print("\n" + "="*60)
    print("Validating NOC Incident Manager Optimizations")
    print("="*60)
    
    # Check manager exists
    if not hasattr(NOCIncident.objects, 'for_export'):
        print_status("❌ FAIL: OptimizedIncidentManager.for_export() not found", 'error')
        return False
    
    if not hasattr(NOCIncident.objects, 'with_counts'):
        print_status("❌ FAIL: OptimizedIncidentManager.with_counts() not found", 'error')
        return False
    
    if not hasattr(NOCIncident.objects, 'with_full_details'):
        print_status("❌ FAIL: OptimizedIncidentManager.with_full_details() not found", 'error')
        return False
    
    print_status("✅ PASS: All manager methods exist", 'success')
    
    # Test with_counts annotation
    try:
        with connection.cursor() as cursor:
            connection.queries_log.clear()
            
            incidents = NOCIncident.objects.with_counts()[:10]
            list(incidents)  # Force evaluation
            
            # Check alert_count is annotated
            if incidents.exists():
                first = incidents.first()
                if not hasattr(first, 'alert_count'):
                    print_status("❌ FAIL: alert_count not annotated", 'error')
                    return False
                print_status(f"✅ PASS: alert_count annotated (value: {first.alert_count})", 'success')
    except Exception as e:
        print_status(f"❌ FAIL: Manager test error: {e}", 'error')
        return False
    
    return True


def validate_export_view_optimization():
    """Verify export view uses annotated count."""
    print("\n" + "="*60)
    print("Validating NOC Export View Optimization")
    print("="*60)
    
    # Read export view file
    export_view_path = 'apps/noc/views/export_views.py'
    try:
        with open(export_view_path, 'r') as f:
            content = f.read()
            
        # Check for optimized pattern
        if 'for_export()' in content:
            print_status("✅ PASS: Uses for_export() manager method", 'success')
        else:
            print_status("❌ FAIL: for_export() not used in export view", 'error')
            return False
        
        if 'incident.alert_count' in content:
            print_status("✅ PASS: Uses annotated alert_count", 'success')
        else:
            print_status("⚠️  WARNING: May still use incident.alerts.count()", 'warning')
        
        # Check for removed N+1 pattern
        if 'incident.alerts.count()' in content:
            print_status("❌ FAIL: Still uses incident.alerts.count() in loop", 'error')
            return False
        else:
            print_status("✅ PASS: No incident.alerts.count() in loop", 'success')
    
    except FileNotFoundError:
        print_status(f"❌ FAIL: {export_view_path} not found", 'error')
        return False
    except Exception as e:
        print_status(f"❌ FAIL: Error reading file: {e}", 'error')
        return False
    
    return True


def validate_analytics_optimization():
    """Verify analytics view uses aggregated query."""
    print("\n" + "="*60)
    print("Validating NOC Analytics View Optimization")
    print("="*60)
    
    analytics_view_path = 'apps/noc/views/analytics_views.py'
    try:
        with open(analytics_view_path, 'r') as f:
            content = f.read()
        
        # Check for optimized pattern
        if 'values(' in content and '.annotate(' in content:
            print_status("✅ PASS: Uses values() + annotate() pattern", 'success')
        else:
            print_status("⚠️  WARNING: May not use aggregated query", 'warning')
        
        # Check MTTR function
        mttr_section = content[content.find('_calculate_mttr_by_client'):][:1000]
        
        if 'for client in clients' in mttr_section:
            print_status("❌ FAIL: Still loops over clients", 'error')
            return False
        else:
            print_status("✅ PASS: No client loop in MTTR calculation", 'success')
        
        if 'client__in=clients' in mttr_section:
            print_status("✅ PASS: Uses client__in filter", 'success')
        else:
            print_status("⚠️  WARNING: May not filter by clients correctly", 'warning')
    
    except FileNotFoundError:
        print_status(f"❌ FAIL: {analytics_view_path} not found", 'error')
        return False
    except Exception as e:
        print_status(f"❌ FAIL: Error reading file: {e}", 'error')
        return False
    
    return True


def validate_dar_service_optimization():
    """Verify DAR service uses database aggregation."""
    print("\n" + "="*60)
    print("Validating Reports DAR Service Optimization")
    print("="*60)
    
    dar_service_path = 'apps/reports/services/dar_service.py'
    try:
        with open(dar_service_path, 'r') as f:
            content = f.read()
        
        # Check for database aggregation
        if 'ExpressionWrapper' in content and 'Extract' in content:
            print_status("✅ PASS: Uses database-level duration calculation", 'success')
        else:
            print_status("⚠️  WARNING: May not use database aggregation", 'warning')
        
        # Check attendance section
        attendance_section = content[content.find('_get_attendance_stats'):][:2000]
        
        if 'for record in attendance_records' in attendance_section and \
           'duration = (' in attendance_section:
            print_status("❌ FAIL: Still has Python loop for duration calculation", 'error')
            return False
        else:
            print_status("✅ PASS: No Python loop for duration calculation", 'success')
        
        if 'Sum(' in attendance_section or 'aggregate(' in attendance_section:
            print_status("✅ PASS: Uses database aggregation", 'success')
        else:
            print_status("⚠️  WARNING: May not use Sum aggregation", 'warning')
    
    except FileNotFoundError:
        print_status(f"❌ FAIL: {dar_service_path} not found", 'error')
        return False
    except Exception as e:
        print_status(f"❌ FAIL: Error reading file: {e}", 'error')
        return False
    
    return True


def validate_performance_tests():
    """Check that performance tests exist."""
    print("\n" + "="*60)
    print("Validating Performance Tests")
    print("="*60)
    
    test_files = [
        'apps/noc/tests/test_performance/test_n1_optimizations.py',
        'apps/reports/tests/test_performance/test_dar_service.py'
    ]
    
    all_exist = True
    for test_file in test_files:
        if os.path.exists(test_file):
            print_status(f"✅ PASS: {test_file} exists", 'success')
            
            # Check test content
            with open(test_file, 'r') as f:
                content = f.read()
                test_count = content.count('def test_')
                print_status(f"   Contains {test_count} test methods", 'info')
        else:
            print_status(f"❌ FAIL: {test_file} not found", 'error')
            all_exist = False
    
    return all_exist


def main():
    """Run all validations."""
    print_status("\n" + "="*60, 'info')
    print_status("N+1 Query Optimization Part 2 - Validation", 'info')
    print_status("="*60 + "\n", 'info')
    
    results = {
        'Incident Manager': validate_incident_manager(),
        'Export View': validate_export_view_optimization(),
        'Analytics View': validate_analytics_optimization(),
        'DAR Service': validate_dar_service_optimization(),
        'Performance Tests': validate_performance_tests()
    }
    
    # Summary
    print("\n" + "="*60)
    print("Validation Summary")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        color = 'success' if result else 'error'
        print_status(f"{status}: {name}", color)
    
    print("\n" + "="*60)
    print_status(f"Results: {passed}/{total} validations passed", 
                'success' if passed == total else 'warning')
    print("="*60 + "\n")
    
    if passed == total:
        print_status("🎉 All optimizations validated successfully!", 'success')
        return 0
    else:
        print_status("⚠️  Some validations failed - review output above", 'warning')
        return 1


if __name__ == '__main__':
    sys.exit(main())
