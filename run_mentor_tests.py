#!/usr/bin/env python3
"""
Test runner for AI Mentor system functionality.

This script runs comprehensive tests for the mentor system including:
- Command implementations
- LibCST codemods
- API endpoints
- Maker/Checker pattern
- Integration workflows
"""

import os
import sys
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
os.environ['MENTOR_ENABLED'] = '1'  # Enable mentor for testing

def run_mentor_tests():
    """Run all mentor-related tests."""

    test_commands = [
        # Test mentor commands
        [
            'python3', '-m', 'pytest',
            'apps/mentor/tests/test_commands/',
            '-v', '--tb=short', '--cov=apps.mentor.management.commands'
        ],

        # Test LibCST codemods
        [
            'python3', '-m', 'pytest',
            'apps/mentor/tests/test_codemods/',
            '-v', '--tb=short', '--cov=apps.mentor.codemods'
        ],

        # Test API endpoints
        [
            'python3', '-m', 'pytest',
            'apps/mentor/tests/test_api/',
            '-v', '--tb=short', '--cov=apps.mentor_api'
        ],

        # Test LLM and Maker/Checker pattern
        [
            'python3', '-m', 'pytest',
            'apps/mentor/tests/test_llm/',
            '-v', '--tb=short', '--cov=apps.mentor.llm'
        ],

        # Test guards and safety
        [
            'python3', '-m', 'pytest',
            'apps/mentor/tests/test_guards/',
            '-v', '--tb=short', '--cov=apps.mentor.guards'
        ],

        # Test integration workflows
        [
            'python3', '-m', 'pytest',
            'apps/mentor/tests/test_integration/',
            '-v', '--tb=short', '--cov=apps.mentor'
        ],

        # Test enhanced generators
        [
            'python3', '-m', 'pytest',
            'apps/mentor/tests/test_generators/',
            '-v', '--tb=short', '--cov=apps.mentor.generators'
        ]
    ]

    print("🤖 Running AI Mentor Test Suite")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    for i, cmd in enumerate(test_commands, 1):
        test_name = cmd[3].split('/')[-2]  # Extract test category
        print(f"\n[{i}/{len(test_commands)}] Running {test_name} tests...")
        print("-" * 40)

        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                check=False,  # Don't raise on non-zero exit
                capture_output=False  # Show output in real-time
            )

            if result.returncode == 0:
                print(f"✅ {test_name} tests PASSED")
                total_passed += 1
            else:
                print(f"❌ {test_name} tests FAILED (exit code: {result.returncode})")
                total_failed += 1

        except Exception as e:
            print(f"💥 {test_name} tests ERROR: {e}")
            total_failed += 1

    print("\n" + "=" * 60)
    print("🏁 AI MENTOR TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print(f"📊 Total: {total_passed + total_failed}")

    if total_failed == 0:
        print("\n🎉 All AI Mentor tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total_failed} test category(ies) failed")
        return 1


def run_security_validation():
    """Run security-specific tests."""
    print("\n🔒 Running Security Validation Tests")
    print("-" * 40)

    security_cmd = [
        'python3', '-m', 'pytest',
        'apps/mentor/tests/',
        '-m', 'security',
        '-v', '--tb=short'
    ]

    try:
        result = subprocess.run(
            security_cmd,
            cwd=project_root,
            check=False
        )

        if result.returncode == 0:
            print("✅ Security validation PASSED")
        else:
            print("❌ Security validation FAILED")

        return result.returncode

    except Exception as e:
        print(f"💥 Security validation ERROR: {e}")
        return 1


def main():
    """Main test runner."""
    if len(sys.argv) > 1 and sys.argv[1] == '--security-only':
        return run_security_validation()

    # Run standard mentor tests
    mentor_result = run_mentor_tests()

    # Run security validation
    security_result = run_security_validation()

    # Overall result
    if mentor_result == 0 and security_result == 0:
        print("\n🌟 All AI Mentor tests and validations passed!")
        return 0
    else:
        print(f"\n⚡ Some tests failed. Mentor: {mentor_result}, Security: {security_result}")
        return max(mentor_result, security_result)


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)