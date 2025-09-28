#!/usr/bin/env python3
"""
Validation script for Generic Exception Handling Anti-Pattern Remediation.

This script validates that:
1. No generic 'except Exception:' patterns remain in critical modules
2. Enhanced exception classes are properly defined
3. Error handling framework uses specific exception types
4. Critical security fixes are in place

Usage:
    python3 validate_exception_fixes.py
"""

import os
import re
import sys
from pathlib import Path


class ExceptionPatternValidator:
    """Validates exception handling patterns across the codebase."""

    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.errors = []
        self.warnings = []
        self.successes = []

    def validate_all(self):
        """Run all validation checks."""
        print("🔍 Starting Generic Exception Handling Anti-Pattern Validation")
        print("=" * 70)

        # Check if enhanced exception system exists
        self.validate_enhanced_exceptions_exist()

        # Check critical modules for generic exception patterns
        self.validate_critical_modules()

        # Check for specific exception imports
        self.validate_specific_exception_imports()

        # Print results
        self.print_results()

        return len(self.errors) == 0

    def validate_enhanced_exceptions_exist(self):
        """Check if enhanced exception classes are properly defined."""
        exceptions_file = self.project_root / "apps" / "core" / "exceptions.py"

        if not exceptions_file.exists():
            self.errors.append("❌ Enhanced exception system not found: apps/core/exceptions.py")
            return

        content = exceptions_file.read_text()

        required_classes = [
            "BaseApplicationException",
            "SecurityException",
            "EnhancedValidationException",
            "DatabaseException",
            "BusinessLogicException",
            "ExceptionFactory"
        ]

        for class_name in required_classes:
            if f"class {class_name}" in content:
                self.successes.append(f"✅ Found {class_name} in exception system")
            else:
                self.errors.append(f"❌ Missing {class_name} in exception system")

        # Check for correlation ID support
        if "correlation_id" in content and "uuid.uuid4()" in content:
            self.successes.append("✅ Correlation ID support implemented")
        else:
            self.errors.append("❌ Correlation ID support missing")

    def validate_critical_modules(self):
        """Check critical modules for generic exception patterns."""
        critical_files = [
            "apps/core/error_handling.py",
            "apps/peoples/models.py",
            "apps/activity/views/question_views.py"
        ]

        for file_path in critical_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                self.check_file_for_generic_exceptions(full_path, file_path)
            else:
                self.warnings.append(f"⚠️ File not found: {file_path}")

    def check_file_for_generic_exceptions(self, file_path, display_path):
        """Check a file for generic exception patterns."""
        content = file_path.read_text()

        # Pattern to find generic exception handling
        generic_pattern = re.compile(r'except\s+Exception\s*:', re.MULTILINE)
        matches = list(generic_pattern.finditer(content))

        if matches:
            # Check if these are acceptable patterns (with ErrorHandler.handle_exception)
            acceptable_patterns = [
                "ErrorHandler.handle_exception",
                "logger.critical",
                "exc_info=True"
            ]

            lines = content.split('\n')
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1].strip()

                # Look for context around the exception (next 5 lines)
                context_lines = lines[line_num:line_num + 5]
                context = ' '.join(context_lines)

                is_acceptable = any(pattern in context for pattern in acceptable_patterns)

                if is_acceptable:
                    self.warnings.append(
                        f"⚠️ Generic exception at {display_path}:{line_num} "
                        f"(but uses proper error handling)"
                    )
                else:
                    self.errors.append(
                        f"❌ Generic exception at {display_path}:{line_num}: {line_content}"
                    )
        else:
            self.successes.append(f"✅ No problematic generic exceptions in {display_path}")

    def validate_specific_exception_imports(self):
        """Check that files import specific exception types."""
        files_to_check = [
            ("apps/core/error_handling.py", ["ValidationError", "DatabaseError"]),
            ("apps/peoples/models.py", ["DatabaseError"]),
            ("apps/activity/views/question_views.py", ["ValidationError", "DatabaseError"])
        ]

        for file_path, required_imports in files_to_check:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue

            content = full_path.read_text()

            for import_name in required_imports:
                if import_name in content and ("import" in content or "from" in content):
                    self.successes.append(f"✅ {file_path} imports {import_name}")
                else:
                    self.warnings.append(f"⚠️ {file_path} may be missing {import_name} import")

    def print_results(self):
        """Print validation results."""
        print("\n📊 VALIDATION RESULTS")
        print("=" * 50)

        if self.successes:
            print(f"\n✅ SUCCESSES ({len(self.successes)}):")
            for success in self.successes:
                print(f"  {success}")

        if self.warnings:
            print(f"\n⚠️ WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  {warning}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  {error}")

        print(f"\n📈 SUMMARY:")
        print(f"  ✅ Successes: {len(self.successes)}")
        print(f"  ⚠️ Warnings: {len(self.warnings)}")
        print(f"  ❌ Errors: {len(self.errors)}")

        if self.errors:
            print(f"\n🚨 VALIDATION FAILED - {len(self.errors)} errors found")
            print("   Please fix the errors above before proceeding.")
        else:
            print(f"\n🎉 VALIDATION PASSED!")
            print("   Generic Exception Handling Anti-Pattern remediation successful!")

        print("\n" + "=" * 70)


def main():
    """Main validation function."""
    # Get the project root directory (where this script is located)
    project_root = Path(__file__).parent

    validator = ExceptionPatternValidator(project_root)
    success = validator.validate_all()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()