#!/usr/bin/env python3
"""
Stream Testbench Test Suite Runner
Comprehensive test runner for all Stream Testbench components
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def run_command(command, description, timeout=300):
    """Run a command with timeout and error handling"""
    print(f"🔧 {description}...")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout:
                print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ {description} failed (exit code: {result.returncode})")
            if result.stderr:
                print(f"   Error: {result.stderr.strip()}")
            return False

    except subprocess.TimeoutExpired:
        print(f"⏰ {description} timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"💥 {description} crashed: {e}")
        return False


def main():
    """Main test runner"""
    print("🚀 Stream Testbench - Comprehensive Test Suite")
    print("=" * 60)

    # Check if we're in the right directory
    if not Path('manage.py').exists():
        print("❌ Please run this script from the Django project root")
        sys.exit(1)

    test_results = {}
    overall_success = True

    # 1. Unit Tests
    print("\n📋 Phase 1: Unit Tests")
    print("-" * 30)

    unit_test_commands = [
        (
            "python -m pytest apps/streamlab/tests/test_pii_redactor.py -v",
            "PII Redactor Tests"
        ),
        (
            "python -m pytest apps/streamlab/tests/test_event_capture.py -v",
            "Event Capture Tests"
        ),
        (
            "python -m pytest apps/issue_tracker/tests/test_anomaly_detection.py -v",
            "Anomaly Detection Tests"
        ),
        (
            "python -m pytest apps/streamlab/tests/test_security.py -v",
            "Security Tests"
        )
    ]

    for command, description in unit_test_commands:
        success = run_command(command, description)
        test_results[description] = success
        overall_success &= success

    # 2. Integration Tests
    print("\n🔗 Phase 2: Integration Tests")
    print("-" * 30)

    integration_commands = [
        (
            "python -m pytest apps/streamlab/tests/test_websocket_integration.py -v",
            "WebSocket Integration Tests"
        ),
        (
            "python manage.py check --deploy",
            "Django Deployment Check"
        ),
        (
            "python manage.py makemigrations --check --dry-run",
            "Migration Check"
        )
    ]

    for command, description in integration_commands:
        success = run_command(command, description)
        test_results[description] = success
        overall_success &= success

    # 3. Database Migrations
    print("\n🗄️ Phase 3: Database Migrations")
    print("-" * 30)

    migration_success = run_command(
        "python manage.py migrate --run-syncdb",
        "Apply Database Migrations"
    )
    test_results["Database Migrations"] = migration_success
    overall_success &= migration_success

    # 4. Admin Interface Test
    print("\n⚙️ Phase 4: Admin Interface")
    print("-" * 30)

    admin_success = run_command(
        "python manage.py check streamlab issue_tracker",
        "Admin Interface Check"
    )
    test_results["Admin Interface"] = admin_success
    overall_success &= admin_success

    # 5. Security Tests (if available)
    print("\n🔒 Phase 5: Security Validation")
    print("-" * 30)

    security_commands = [
        (
            "python -m pytest apps/streamlab/tests/test_security.py::TestPIIProtection -v",
            "PII Protection Validation"
        ),
        (
            "python -m pytest apps/streamlab/tests/test_security.py::TestAccessControls -v",
            "Access Control Validation"
        )
    ]

    for command, description in security_commands:
        success = run_command(command, description, timeout=60)
        test_results[description] = success
        overall_success &= success

    # 6. Performance Tests (Quick version)
    print("\n⚡ Phase 6: Performance Tests")
    print("-" * 30)

    # Only run if Django server can be started
    server_process = None
    try:
        print("🚀 Starting Django test server...")
        server_process = subprocess.Popen(
            ["python", "manage.py", "runserver", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for server to start
        time.sleep(10)

        # Run spike test
        spike_success = run_command(
            "python testing/stream_load_testing/spike_test.py",
            "Stream Spike Test",
            timeout=120
        )
        test_results["Spike Test"] = spike_success
        overall_success &= spike_success

        # Validate SLOs if results exist
        if Path("spike_test_results.json").exists():
            slo_success = run_command(
                "python testing/stream_load_testing/check_slos.py spike_test_results.json",
                "SLO Validation"
            )
            test_results["SLO Validation"] = slo_success
            overall_success &= slo_success

    except Exception as e:
        print(f"⚠️  Performance tests skipped: {e}")
        test_results["Performance Tests"] = False

    finally:
        # Clean up server process
        if server_process:
            server_process.terminate()
            server_process.wait(timeout=10)

    # 7. Kotlin Generator Tests
    print("\n☕ Phase 7: Kotlin Generator Tests")
    print("-" * 30)

    if Path("intelliwiz_kotlin/build.gradle.kts").exists():
        kotlin_commands = [
            (
                "cd intelliwiz_kotlin && ./gradlew test",
                "Kotlin Unit Tests"
            ),
            (
                "cd intelliwiz_kotlin && ./gradlew build",
                "Kotlin Build Test"
            )
        ]

        for command, description in kotlin_commands:
            success = run_command(command, description, timeout=180)
            test_results[description] = success
            overall_success &= success
    else:
        print("⚠️  Kotlin generator not found, skipping Kotlin tests")

    # 8. Final Report
    print("\n" + "=" * 60)
    print("📊 STREAM TESTBENCH TEST RESULTS SUMMARY")
    print("=" * 60)

    passed_tests = sum(1 for success in test_results.values() if success)
    total_tests = len(test_results)

    print(f"\nTest Results: {passed_tests}/{total_tests} passed")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

    print("\nDetailed Results:")
    for test_name, success in test_results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {test_name}: {status}")

    if overall_success:
        print("\n🎉 ALL TESTS PASSED!")
        print("🚀 Stream Testbench is ready for production use")
        return 0
    else:
        print("\n💥 SOME TESTS FAILED!")
        print("🔧 Please fix the failing tests before deploying")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)