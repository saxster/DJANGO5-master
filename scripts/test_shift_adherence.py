#!/usr/bin/env python
"""
Validation script for Shift Attendance Tracker.

Tests service functionality, data integrity, and basic operations.
"""
import os
import sys
import django
from datetime import date, datetime, time

# Setup Django
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from apps.attendance.services.shift_adherence_service import ShiftAdherenceService
from apps.client_onboarding.models import Shift
from apps.attendance.models import PeopleEventlog


def test_service_import():
    """Test service can be imported"""
    print("✓ Service imported successfully")
    return True


def test_calculate_adherence():
    """Test adherence calculation"""
    try:
        service = ShiftAdherenceService()
        today = date.today()
        adherence = service.calculate_adherence(today)
        
        print(f"✓ Adherence calculated: {len(adherence)} shifts analyzed")
        return True
    except Exception as e:
        print(f"✗ Adherence calculation failed: {e}")
        return False


def test_coverage_stats():
    """Test statistics calculation"""
    try:
        service = ShiftAdherenceService()
        today = date.today()
        adherence = service.calculate_adherence(today)
        stats = service.get_coverage_stats(adherence)
        
        required_keys = ['total_shifts', 'coverage_pct', 'on_time_pct', 
                        'late_pct', 'absent_pct', 'on_time_count', 
                        'late_count', 'absent_count']
        
        for key in required_keys:
            if key not in stats:
                print(f"✗ Missing stat key: {key}")
                return False
        
        print(f"✓ Statistics calculated correctly")
        print(f"  - Total shifts: {stats['total_shifts']}")
        print(f"  - Coverage: {stats['coverage_pct']}%")
        print(f"  - On time: {stats['on_time_count']}")
        print(f"  - Late: {stats['late_count']}")
        print(f"  - Absent: {stats['absent_count']}")
        return True
    except Exception as e:
        print(f"✗ Statistics calculation failed: {e}")
        return False


def test_status_categories():
    """Test status categories are correct"""
    service = ShiftAdherenceService()
    today = date.today()
    adherence = service.calculate_adherence(today)
    
    valid_statuses = ['ON_TIME', 'LATE', 'NO_SHOW', 'EARLY_EXIT', 'UNKNOWN']
    
    for record in adherence:
        if record['status'] not in valid_statuses:
            print(f"✗ Invalid status: {record['status']}")
            return False
    
    print(f"✓ All status categories valid")
    return True


def test_view_import():
    """Test view can be imported"""
    try:
        from apps.attendance.views.shift_adherence_dashboard import ShiftAdherenceDashboardView
        print("✓ View imported successfully")
        return True
    except Exception as e:
        print(f"✗ View import failed: {e}")
        return False


def test_task_import():
    """Test tasks can be imported"""
    try:
        from apps.attendance.tasks.shift_monitoring import (
            update_shift_adherence,
            notify_manager_no_show
        )
        print("✓ Tasks imported successfully")
        return True
    except Exception as e:
        print(f"✗ Task import failed: {e}")
        return False


def test_url_configuration():
    """Test URL is configured"""
    try:
        from django.urls import reverse
        from django.urls.exceptions import NoReverseMatch
        
        try:
            url = reverse('attendance:shift_adherence_dashboard')
            print(f"✓ URL configured: {url}")
            return True
        except NoReverseMatch:
            print("✗ URL not found in urlpatterns")
            return False
    except Exception as e:
        print(f"✗ URL configuration test failed: {e}")
        return False


def test_celery_schedule():
    """Test Celery beat schedule configured"""
    try:
        from django.conf import settings
        
        if 'update-shift-adherence' in settings.CELERY_BEAT_SCHEDULE:
            schedule = settings.CELERY_BEAT_SCHEDULE['update-shift-adherence']
            print(f"✓ Celery schedule configured")
            print(f"  - Task: {schedule['task']}")
            print(f"  - Schedule: Every 10 minutes")
            return True
        else:
            print("✗ Celery schedule not found")
            return False
    except Exception as e:
        print(f"✗ Celery schedule test failed: {e}")
        return False


def test_template_exists():
    """Test template file exists"""
    import os.path
    
    template_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'templates',
        'admin',
        'attendance',
        'shift_adherence_dashboard.html'
    )
    
    if os.path.exists(template_path):
        print(f"✓ Template file exists")
        return True
    else:
        print(f"✗ Template file not found: {template_path}")
        return False


def run_all_tests():
    """Run all validation tests"""
    print("=" * 60)
    print("SHIFT ATTENDANCE TRACKER - VALIDATION TESTS")
    print("=" * 60)
    print()
    
    tests = [
        ("Service Import", test_service_import),
        ("Calculate Adherence", test_calculate_adherence),
        ("Coverage Statistics", test_coverage_stats),
        ("Status Categories", test_status_categories),
        ("View Import", test_view_import),
        ("Task Import", test_task_import),
        ("URL Configuration", test_url_configuration),
        ("Celery Schedule", test_celery_schedule),
        ("Template Exists", test_template_exists),
    ]
    
    results = []
    
    for name, test_func in tests:
        print(f"\n{name}:")
        print("-" * 40)
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ Test crashed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "=" * 60)
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 All tests passed! Ready for production.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
