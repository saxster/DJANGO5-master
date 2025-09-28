#!/usr/bin/env python
"""
Comprehensive test runner for Conversational Onboarding API

Runs all tests for critical fixes and high-impact features with
proper categorization, reporting, and performance monitoring.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def run_command(command, description="Running command"):
    """Run a command and return the result"""
    print(f"\n🔧 {description}")
    print(f"Command: {' '.join(command)}")
    print("-" * 50)

    start_time = time.time()
    result = subprocess.run(command, capture_output=True, text=True)
    end_time = time.time()

    duration = end_time - start_time

    if result.returncode == 0:
        print(f"✅ SUCCESS ({duration:.1f}s)")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ FAILED ({duration:.1f}s)")
        if result.stderr:
            print("STDERR:", result.stderr)
        if result.stdout:
            print("STDOUT:", result.stdout)

    return result.returncode == 0, duration, result.stdout, result.stderr


def run_critical_fixes_tests():
    """Run tests for critical bug fixes"""
    print("\n" + "=" * 60)
    print("🚨 RUNNING CRITICAL FIXES TESTS")
    print("=" * 60)

    test_commands = [
        # Test that module imports work (no NameError)
        (
            [sys.executable, '-c', 'import apps.onboarding_api.views; print("✅ Module imports successfully")'],
            "Testing module import (decorator bug fix)"
        ),

        # Test idempotency decorators
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_critical_fixes_comprehensive.py::CriticalBugFixesTestCase::test_idempotency_decorators_applied',
             '-v'],
            "Testing idempotency decorators applied"
        ),

        # Test serializer fixes
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_critical_fixes_comprehensive.py::CriticalBugFixesTestCase::test_resume_existing_field_in_serializer',
             '-v'],
            "Testing serializer field fixes"
        ),

        # Test tenant scope enforcement
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_security_comprehensive.py::TenantIsolationTestCase',
             '-v'],
            "Testing tenant scope enforcement"
        )
    ]

    results = []
    for command, description in test_commands:
        success, duration, stdout, stderr = run_command(command, description)
        results.append((description, success, duration))

    return results


def run_security_tests():
    """Run comprehensive security tests"""
    print("\n" + "=" * 60)
    print("🔒 RUNNING SECURITY TESTS")
    print("=" * 60)

    test_commands = [
        # Tenant isolation tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_security_comprehensive.py::TenantIsolationTestCase',
             '-v', '--tb=short'],
            "Testing tenant isolation"
        ),

        # Permission boundary tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_security_comprehensive.py::PermissionBoundaryTestCase',
             '-v', '--tb=short'],
            "Testing permission boundaries"
        ),

        # Input validation tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_security_comprehensive.py::InputValidationTestCase',
             '-v', '--tb=short'],
            "Testing input validation and injection prevention"
        ),

        # Idempotency tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_security_comprehensive.py::IdempotencyTestCase',
             '-v', '--tb=short'],
            "Testing idempotency protection"
        )
    ]

    results = []
    for command, description in test_commands:
        success, duration, stdout, stderr = run_command(command, description)
        results.append((description, success, duration))

    return results


def run_high_impact_tests():
    """Run tests for high-impact features"""
    print("\n" + "=" * 60)
    print("🚀 RUNNING HIGH-IMPACT FEATURES TESTS")
    print("=" * 60)

    test_commands = [
        # Industry templates tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_high_impact_features.py::IndustryTemplatesHighImpactTestCase',
             '-v', '--tb=short'],
            "Testing industry templates and one-click deployment"
        ),

        # Funnel analytics tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_high_impact_features.py::OnboardingFunnelAnalyticsTestCase',
             '-v', '--tb=short'],
            "Testing onboarding funnel analytics"
        ),

        # Change review UX tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_high_impact_features.py::ChangeReviewUXTestCase',
             '-v', '--tb=short'],
            "Testing enhanced change review UX"
        ),

        # Real LLM integration tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_high_impact_features.py::RealLLMIntegrationTestCase',
             '-v', '--tb=short'],
            "Testing real LLM integration with cost controls"
        ),

        # Enhanced knowledge embeddings tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_high_impact_features.py::EnhancedKnowledgeEmbeddingsTestCase',
             '-v', '--tb=short'],
            "Testing enhanced knowledge embeddings"
        ),

        # Organization rollout tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_high_impact_features.py::OrganizationRolloutTestCase',
             '-v', '--tb=short'],
            "Testing organization rollout controls"
        )
    ]

    results = []
    for command, description in test_commands:
        success, duration, stdout, stderr = run_command(command, description)
        results.append((description, success, duration))

    return results


def run_integration_tests():
    """Run end-to-end integration tests"""
    print("\n" + "=" * 60)
    print("🔄 RUNNING INTEGRATION TESTS")
    print("=" * 60)

    test_commands = [
        # Complete flow integration
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_high_impact_features.py::IntegrationTestSuite',
             '-v', '--tb=short'],
            "Testing complete onboarding flow integration"
        ),

        # Cross-feature compatibility
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_critical_fixes_comprehensive.py::IntegrationTestSuite',
             '-v', '--tb=short'],
            "Testing cross-feature compatibility"
        ),

        # Error handling and resilience
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_security_comprehensive.py::ErrorHandlingTestCase',
             '-v', '--tb=short'],
            "Testing error handling and resilience"
        )
    ]

    results = []
    for command, description in test_commands:
        success, duration, stdout, stderr = run_command(command, description)
        results.append((description, success, duration))

    return results


def run_performance_tests():
    """Run performance and scalability tests"""
    print("\n" + "=" * 60)
    print("⚡ RUNNING PERFORMANCE TESTS")
    print("=" * 60)

    test_commands = [
        # Performance tests
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_high_impact_features.py::PerformanceAndScalabilityTestCase',
             '-v', '--tb=short'],
            "Testing performance and scalability"
        ),

        # Embedding service performance
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_critical_fixes_comprehensive.py::EmbeddingServiceTestCase::test_embedding_service_performance',
             '-v', '--tb=short'],
            "Testing embedding service performance"
        ),

        # Template loading performance
        (
            [sys.executable, '-m', 'pytest',
             'apps/onboarding_api/tests/test_critical_fixes_comprehensive.py::PerformanceTestSuite',
             '-v', '--tb=short'],
            "Testing template and notification performance"
        )
    ]

    results = []
    for command, description in test_commands:
        success, duration, stdout, stderr = run_command(command, description)
        results.append((description, success, duration))

    return results


def run_all_tests():
    """Run complete test suite"""
    print("🧪 RUNNING COMPREHENSIVE ONBOARDING API TEST SUITE")
    print("=" * 70)

    all_results = []

    # Run test categories in order
    test_categories = [
        ("Critical Fixes", run_critical_fixes_tests),
        ("Security", run_security_tests),
        ("High-Impact Features", run_high_impact_tests),
        ("Integration", run_integration_tests),
        ("Performance", run_performance_tests)
    ]

    for category_name, test_runner in test_categories:
        print(f"\n🎯 CATEGORY: {category_name}")
        category_results = test_runner()
        all_results.extend([(category_name, desc, success, duration) for desc, success, duration in category_results])

    return all_results


def generate_test_report(results):
    """Generate comprehensive test report"""
    print("\n" + "=" * 70)
    print("📊 TEST EXECUTION REPORT")
    print("=" * 70)

    total_tests = len(results)
    passed_tests = sum(1 for _, _, success, _ in results if success)
    failed_tests = total_tests - passed_tests
    total_time = sum(duration for _, _, _, duration in results)

    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    print(f"Total Time: {total_time:.1f}s")

    # Detailed results by category
    print("\n📋 DETAILED RESULTS:")
    print("-" * 50)

    current_category = None
    for category, description, success, duration in results:
        if category != current_category:
            print(f"\n{category}:")
            current_category = category

        status_icon = "✅" if success else "❌"
        print(f"  {status_icon} {description} ({duration:.1f}s)")

    # Failed tests summary
    if failed_tests > 0:
        print("\n❌ FAILED TESTS:")
        print("-" * 30)
        for category, description, success, duration in results:
            if not success:
                print(f"  • {category}: {description}")

    print("\n" + "=" * 70)

    return passed_tests == total_tests


def run_specific_test_category(category):
    """Run specific test category"""
    test_runners = {
        'critical': run_critical_fixes_tests,
        'security': run_security_tests,
        'features': run_high_impact_tests,
        'integration': run_integration_tests,
        'performance': run_performance_tests
    }

    if category not in test_runners:
        print(f"❌ Unknown test category: {category}")
        print(f"Available categories: {', '.join(test_runners.keys())}")
        return False

    results = test_runners[category]()
    success = generate_test_report([(category, desc, success, duration) for desc, success, duration in results])

    return success


def validate_test_environment():
    """Validate that test environment is properly set up"""
    print("🔍 VALIDATING TEST ENVIRONMENT")
    print("-" * 40)

    checks = [
        ("Django available", lambda: __import__('django')),
        ("REST framework available", lambda: __import__('rest_framework')),
        ("Onboarding models available", lambda: __import__('apps.onboarding.models')),
        ("Test database accessible", lambda: subprocess.run([sys.executable, 'manage.py', 'check', '--database', 'default'],
                                                           capture_output=True, check=True)),
    ]

    all_passed = True

    for check_name, check_func in checks:
        try:
            check_func()
            print(f"✅ {check_name}")
        except Exception as e:
            print(f"❌ {check_name}: {str(e)}")
            all_passed = False

    if all_passed:
        print("✅ Test environment validation passed")
    else:
        print("❌ Test environment validation failed")

    return all_passed


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(
        description='Comprehensive test runner for Conversational Onboarding API'
    )
    parser.add_argument(
        '--category',
        choices=['critical', 'security', 'features', 'integration', 'performance', 'all'],
        default='all',
        help='Test category to run'
    )
    parser.add_argument(
        '--validate-env',
        action='store_true',
        help='Validate test environment before running tests'
    )
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Run tests with coverage reporting'
    )

    args = parser.parse_args()

    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    print("🧪 CONVERSATIONAL ONBOARDING API - COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    # Validate environment if requested
    if args.validate_env:
        if not validate_test_environment():
            print("❌ Environment validation failed. Please fix issues before running tests.")
            return 1

    # Run tests
    if args.category == 'all':
        results = run_all_tests()
        success = generate_test_report(results)
    else:
        success = run_specific_test_category(args.category)

    # Generate coverage report if requested
    if args.coverage and success:
        print("\n📈 GENERATING COVERAGE REPORT")
        print("-" * 40)

        coverage_command = [
            sys.executable, '-m', 'pytest',
            'apps/onboarding_api/tests/',
            '--cov=apps.onboarding_api',
            '--cov-report=html:coverage_reports/onboarding_api',
            '--cov-report=term',
            '--tb=short'
        ]

        run_command(coverage_command, "Generating coverage report")

    # Final summary
    if success:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("✅ Critical fixes verified")
        print("✅ Security enhancements validated")
        print("✅ High-impact features working")
        print("✅ Integration tests successful")
        return 0
    else:
        print("\n💥 SOME TESTS FAILED!")
        print("❌ Please review failed tests and fix issues")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)