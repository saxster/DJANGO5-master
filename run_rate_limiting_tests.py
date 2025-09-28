#!/usr/bin/env python
"""
Rate Limiting Test Runner

Runs comprehensive test suite for rate limiting implementation including:
- Unit tests for middleware
- Integration tests for endpoint protection
- Penetration tests for attack scenarios
- Performance validation
"""

import sys
import subprocess


def run_tests():
    """Run all rate limiting tests with detailed output."""

    print("=" * 80)
    print("RATE LIMITING COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print()

    test_suites = [
        {
            'name': 'Comprehensive Unit Tests',
            'command': [
                'python', '-m', 'pytest',
                'apps/core/tests/test_rate_limiting_comprehensive.py',
                '-v', '--tb=short'
            ],
            'critical': True
        },
        {
            'name': 'Penetration Tests',
            'command': [
                'python', '-m', 'pytest',
                'apps/core/tests/test_rate_limiting_penetration.py',
                '-v', '--tb=short', '-m', 'penetration'
            ],
            'critical': True
        },
        {
            'name': 'Security Integration Tests',
            'command': [
                'python', '-m', 'pytest',
                '-m', 'security',
                '-k', 'rate_limit',
                '-v', '--tb=short'
            ],
            'critical': False
        },
        {
            'name': 'Settings Validation',
            'command': [
                'python', '-m', 'pytest',
                'tests/test_security_modular_refactoring.py::SecurityModularRefactoringTests::test_rate_limiting_configuration',
                '-v'
            ],
            'critical': True
        }
    ]

    results = []

    for suite in test_suites:
        print(f"\n{'=' * 80}")
        print(f"Running: {suite['name']}")
        print(f"{'=' * 80}\n")

        try:
            result = subprocess.run(
                suite['command'],
                capture_output=True,
                text=True,
                timeout=300
            )

            print(result.stdout)

            if result.returncode == 0:
                results.append({'name': suite['name'], 'status': 'PASSED'})
                print(f"\n✅ {suite['name']}: PASSED\n")
            else:
                results.append({'name': suite['name'], 'status': 'FAILED'})
                print(f"\n❌ {suite['name']}: FAILED\n")
                print("STDERR:", result.stderr)

                if suite['critical']:
                    print(f"\n🚨 CRITICAL TEST FAILED: {suite['name']}")
                    print("This is a critical security test. Fix before deploying.\n")

        except subprocess.TimeoutExpired:
            results.append({'name': suite['name'], 'status': 'TIMEOUT'})
            print(f"\n⏱ {suite['name']}: TIMEOUT (> 5 minutes)\n")

        except Exception as e:
            results.append({'name': suite['name'], 'status': 'ERROR'})
            print(f"\n❌ {suite['name']}: ERROR - {str(e)}\n")

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r['status'] == 'PASSED')
    failed = sum(1 for r in results if r['status'] == 'FAILED')
    errors = sum(1 for r in results if r['status'] in ['TIMEOUT', 'ERROR'])

    for result in results:
        status_icon = {
            'PASSED': '✅',
            'FAILED': '❌',
            'TIMEOUT': '⏱',
            'ERROR': '❌'
        }.get(result['status'], '❓')

        print(f"{status_icon} {result['name']}: {result['status']}")

    print()
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed} | Errors: {errors}")
    print()

    if failed > 0 or errors > 0:
        print("🚨 SOME TESTS FAILED - Review output above")
        print("=" * 80)
        return 1
    else:
        print("✅ ALL TESTS PASSED - Rate limiting implementation verified")
        print("=" * 80)
        return 0


if __name__ == '__main__':
    sys.exit(run_tests())