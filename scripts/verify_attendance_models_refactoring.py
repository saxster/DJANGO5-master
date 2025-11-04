#!/usr/bin/env python
"""
Verify attendance models refactoring.

Tests that all models can be imported from apps.attendance.models
and that backward compatibility is maintained.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.base')

try:
    import django
    django.setup()
except Exception as e:
    print(f"Warning: Django setup failed: {e}")
    print("This is expected if dependencies are not installed.")
    print("Continuing with import verification...")

def test_core_models():
    """Test core attendance models can be imported."""
    print("Testing core attendance models...")
    try:
        from apps.attendance.models import PeopleEventlog, Geofence, Tracking, TestGeo
        print("✅ Core models imported successfully")
        print(f"  - PeopleEventlog: {PeopleEventlog.__name__}")
        print(f"  - Geofence: {Geofence.__name__}")
        print(f"  - Tracking: {Tracking.__name__}")
        print(f"  - TestGeo: {TestGeo.__name__}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import core models: {e}")
        return False

def test_helper_types():
    """Test helper types can be imported."""
    print("\nTesting helper types...")
    try:
        from apps.attendance.models import PEventLogExtras, PELGeoJson
        print("✅ Helper types imported successfully")
        print(f"  - PEventLogExtras: {PEventLogExtras.__name__}")
        print(f"  - PELGeoJson: {PELGeoJson.__name__}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import helper types: {e}")
        return False

def test_helper_functions():
    """Test helper functions can be imported."""
    print("\nTesting helper functions...")
    try:
        from apps.attendance.models import peventlog_json, pel_geojson
        print("✅ Helper functions imported successfully")

        # Test they work
        result1 = peventlog_json()
        result2 = pel_geojson()
        print(f"  - peventlog_json() returns: {type(result1).__name__}")
        print(f"  - pel_geojson() returns: {type(result2).__name__}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import helper functions: {e}")
        return False

def test_audit_models():
    """Test audit & compliance models."""
    print("\nTesting audit & compliance models...")
    try:
        from apps.attendance.models import AttendanceAccessLog, AuditLogRetentionPolicy
        print("✅ Audit models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import audit models: {e}")
        return False

def test_consent_models():
    """Test consent management models."""
    print("\nTesting consent management models...")
    try:
        from apps.attendance.models import ConsentPolicy, EmployeeConsentLog, ConsentRequirement
        print("✅ Consent models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import consent models: {e}")
        return False

def test_post_models():
    """Test post assignment models."""
    print("\nTesting post assignment models...")
    try:
        from apps.attendance.models import Post, PostAssignment, PostOrderAcknowledgement
        print("✅ Post models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import post models: {e}")
        return False

def test_workflow_models():
    """Test approval workflow models."""
    print("\nTesting approval workflow models...")
    try:
        from apps.attendance.models import ApprovalRequest, ApprovalAction, AutoApprovalRule
        print("✅ Workflow models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import workflow models: {e}")
        return False

def test_alert_models():
    """Test alert & monitoring models."""
    print("\nTesting alert & monitoring models...")
    try:
        from apps.attendance.models import AlertRule, AttendanceAlert, AlertEscalation
        print("✅ Alert models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import alert models: {e}")
        return False

def test_fraud_models():
    """Test fraud detection models."""
    print("\nTesting fraud detection models...")
    try:
        from apps.attendance.models import FraudAlert, UserBehaviorProfile
        print("✅ Fraud models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import fraud models: {e}")
        return False

def test_photo_models():
    """Test photo capture models."""
    print("\nTesting photo capture models...")
    try:
        from apps.attendance.models import AttendancePhoto
        print("✅ Photo models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import photo models: {e}")
        return False

def test_sync_models():
    """Test conflict resolution models."""
    print("\nTesting conflict resolution models...")
    try:
        from apps.attendance.models import SyncConflict
        print("✅ Sync models imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import sync models: {e}")
        return False

def test_all_exports():
    """Test that __all__ exports match actual available models."""
    print("\nTesting __all__ exports...")
    try:
        from apps.attendance import models

        all_exports = models.__all__
        print(f"✅ Found {len(all_exports)} exports in __all__")

        # Verify each export is accessible
        missing = []
        for export_name in all_exports:
            if not hasattr(models, export_name):
                missing.append(export_name)

        if missing:
            print(f"❌ Missing exports: {missing}")
            return False
        else:
            print("✅ All exports accessible")
            return True
    except ImportError as e:
        print(f"❌ Failed to test exports: {e}")
        return False

def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Attendance Models Refactoring Verification")
    print("=" * 60)

    tests = [
        test_core_models,
        test_helper_types,
        test_helper_functions,
        test_audit_models,
        test_consent_models,
        test_post_models,
        test_workflow_models,
        test_alert_models,
        test_fraud_models,
        test_photo_models,
        test_sync_models,
        test_all_exports,
    ]

    results = [test() for test in tests]

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"Tests Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - Refactoring successful!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed - Please review")
        return 1

if __name__ == '__main__':
    sys.exit(main())
