#!/usr/bin/env python3
"""
Test runner script for Conversational Onboarding (Phase 1 MVP)
"""
import os
import sys
import subprocess

def run_onboarding_tests():
    """Run tests for the conversational onboarding feature"""
    print("🚀 Running Conversational Onboarding Tests (Phase 1 MVP)")
    print("=" * 60)

    # Set environment variables for testing
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
    os.environ.setdefault('ENABLE_CONVERSATIONAL_ONBOARDING', 'True')

    # Test commands to run
    test_commands = [
        # Test onboarding models
        ['python', 'manage.py', 'test', 'apps.onboarding.tests', '-v', '2'],

        # Test onboarding API
        ['python', 'manage.py', 'test', 'apps.onboarding_api.tests', '-v', '2'],

        # Test specific onboarding functionality with markers
        ['python', '-m', 'pytest', 'apps/onboarding_api/tests/', '-v', '--tb=short'],
    ]

    success_count = 0
    total_commands = len(test_commands)

    for i, cmd in enumerate(test_commands, 1):
        print(f"\n📋 Running test command {i}/{total_commands}:")
        print(f"   {' '.join(cmd)}")
        print("-" * 40)

        try:
            result = subprocess.run(cmd, capture_output=False, check=False)

            if result.returncode == 0:
                print(f"✅ Test command {i} passed!")
                success_count += 1
            else:
                print(f"❌ Test command {i} failed with return code {result.returncode}")

        except FileNotFoundError:
            print(f"⚠️  Command not found: {' '.join(cmd)}")
            print("   Skipping this test...")
        except Exception as e:
            print(f"❌ Error running test command {i}: {str(e)}")

    # Summary
    print("\n" + "=" * 60)
    print("🎯 Test Summary")
    print(f"   Passed: {success_count}/{total_commands}")

    if success_count == total_commands:
        print("🎉 All tests completed successfully!")
        return 0
    else:
        print(f"⚠️  {total_commands - success_count} test suite(s) had issues")
        print("\nNote: Some test failures may be expected in MVP due to:")
        print("- Missing virtual environment activation")
        print("- Database not set up")
        print("- Dependencies not installed")
        print("- This is a development/testing environment")
        return 1

def check_system():
    """Check system prerequisites"""
    print("🔍 Checking system prerequisites...")

    checks = [
        ("Python", ["python", "--version"]),
        ("Django", ["python", "-c", "import django; print(f'Django {django.get_version()}')"]),
        ("PostgreSQL available", ["which", "psql"]),
    ]

    for name, cmd in checks:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"✅ {name}: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ {name}: Not available or failed")

def show_api_endpoints():
    """Show available API endpoints"""
    print("\n🌐 Available Conversational Onboarding API Endpoints:")
    print("=" * 60)

    endpoints = [
        ("POST", "/api/v1/onboarding/conversation/start/", "Start new conversation"),
        ("POST", "/api/v1/onboarding/conversation/{id}/process/", "Process user input"),
        ("GET", "/api/v1/onboarding/conversation/{id}/status/", "Get conversation status"),
        ("POST", "/api/v1/onboarding/recommendations/approve/", "Approve recommendations"),
        ("GET", "/api/v1/onboarding/knowledge/", "List authoritative knowledge"),
        ("POST", "/api/v1/onboarding/knowledge/validate/", "Validate knowledge (admin)"),
        ("GET", "/api/v1/onboarding/knowledge/search/", "Search knowledge (admin)"),
    ]

    for method, endpoint, description in endpoints:
        print(f"   {method:6} {endpoint:50} {description}")

def main():
    """Main function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            check_system()
            return 0
        elif sys.argv[1] == "--endpoints":
            show_api_endpoints()
            return 0
        elif sys.argv[1] == "--help":
            print("Usage: python run_onboarding_tests.py [--check|--endpoints|--help]")
            print("")
            print("Options:")
            print("  --check      Check system prerequisites")
            print("  --endpoints  Show API endpoints")
            print("  --help       Show this help message")
            return 0

    # Run the tests
    return run_onboarding_tests()

if __name__ == "__main__":
    sys.exit(main())