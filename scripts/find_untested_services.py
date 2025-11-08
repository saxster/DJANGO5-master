#!/usr/bin/env python3
"""
Find untested service files in the codebase.
Compares service files against existing test files.
"""
import os
from pathlib import Path
from collections import defaultdict

def find_services():
    """Find all service files in the apps directory."""
    services = []
    base_path = Path("apps")
    
    for service_file in base_path.rglob("*service*.py"):
        if "__init__" in service_file.name or "test_" in service_file.name:
            continue
        services.append(service_file)
    
    return services

def find_tests():
    """Find all test files."""
    tests = set()
    test_paths = [Path("tests"), Path("testing")]
    
    for test_path in test_paths:
        if test_path.exists():
            for test_file in test_path.rglob("test_*.py"):
                tests.add(test_file.stem)
    
    # Also check for tests in apps
    for test_file in Path("apps").rglob("test_*.py"):
        tests.add(test_file.stem)
    
    return tests

def main():
    services = find_services()
    existing_tests = find_tests()
    
    untested = []
    tested = []
    
    print("=" * 80)
    print("SERVICE TEST COVERAGE ANALYSIS")
    print("=" * 80)
    
    for service in sorted(services):
        # Generate expected test filename
        service_name = service.stem
        expected_test = f"test_{service_name}"
        
        if expected_test in existing_tests:
            tested.append(service)
        else:
            untested.append(service)
    
    # Print results
    print(f"\nTotal Services: {len(services)}")
    print(f"Tested: {len(tested)} ({len(tested)/len(services)*100:.1f}%)")
    print(f"Untested: {len(untested)} ({len(untested)/len(services)*100:.1f}%)")
    
    # Group by priority
    priority_services = [
        "device_trust_service",
        "login_throttling_service",
        "user_capability_service",
        "attendance_location_service",
        "work_order_security_service",
        "secure_file_download_service",
        "secure_file_upload_service",
        "gps_spoofing_detector",
        "fraud_detection_orchestrator",
        "sql_injection_monitor",
        "sql_injection_scanner",
    ]
    
    print("\n" + "=" * 80)
    print("PRIORITY SECURITY SERVICES (UNTESTED)")
    print("=" * 80)
    
    priority_untested = []
    for service in untested:
        if any(p in service.stem for p in priority_services):
            priority_untested.append(service)
            print(f"🔴 {service}")
    
    print("\n" + "=" * 80)
    print("ALL UNTESTED SERVICES BY APP")
    print("=" * 80)
    
    # Group by app
    by_app = defaultdict(list)
    for service in untested:
        app_name = service.parts[1] if len(service.parts) > 1 else "unknown"
        by_app[app_name].append(service)
    
    for app_name in sorted(by_app.keys()):
        print(f"\n{app_name.upper()} ({len(by_app[app_name])} untested):")
        for service in sorted(by_app[app_name]):
            print(f"  - {service}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Priority security services untested: {len(priority_untested)}")
    print(f"Total untested services: {len(untested)}")
    print(f"Apps with untested services: {len(by_app)}")
    
    return untested

if __name__ == "__main__":
    main()
