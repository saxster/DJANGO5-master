"""
Management command to audit and fix logging security issues.

This command identifies logging statements that may expose sensitive data
and provides recommendations for fixes using the sanitized logging utilities.
"""
import os
import re
from typing import List, Dict, Tuple
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = """
    Audit logging statements across the codebase for potential security issues
    where sensitive data might be exposed in log messages.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix identified logging issues where possible',
        )
        parser.add_argument(
            '--path',
            type=str,
            default='apps',
            help='Path to audit (default: apps)',
        )
        parser.add_argument(
            '--exclude',
            type=str,
            nargs='*',
            default=['migrations', '__pycache__', '.git'],
            help='Directories to exclude from audit',
        )

    def handle(self, *args, **options):
        """Main audit handler."""
        fix_mode = options['fix']
        audit_path = options['path']
        exclude_dirs = options['exclude']

        self.stdout.write(
            self.style.WARNING("🔍 LOGGING SECURITY AUDIT")
        )
        self.stdout.write(f"Auditing path: {audit_path}")

        if fix_mode:
            self.stdout.write(
                self.style.WARNING("⚠️  FIX MODE ENABLED - Files will be modified!")
            )

        # Find all Python files
        python_files = self._find_python_files(audit_path, exclude_dirs)
        self.stdout.write(f"Found {len(python_files)} Python files to audit")

        # Audit each file
        total_issues = 0
        fixed_issues = 0

        for file_path in python_files:
            issues, fixes_applied = self._audit_file(file_path, fix_mode)
            total_issues += len(issues)
            fixed_issues += fixes_applied

            if issues:
                self._report_file_issues(file_path, issues)

        # Print summary
        self._print_summary(total_issues, fixed_issues, fix_mode)

    def _find_python_files(self, path: str, exclude_dirs: List[str]) -> List[str]:
        """Find all Python files in the given path."""
        python_files = []

        for root, dirs, files in os.walk(path):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))

        return python_files

    def _audit_file(self, file_path: str, fix_mode: bool) -> Tuple[List[Dict], int]:
        """
        Audit a single file for logging security issues.

        Args:
            file_path: Path to the file to audit
            fix_mode: Whether to apply automatic fixes

        Returns:
            Tuple of (issues found, fixes applied count)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()

            issues = []
            original_content = content
            modified_content = content
            fixes_applied = 0

            # Pattern for logger statements that might contain sensitive data
            sensitive_logging_patterns = [
                # Email in logging
                (
                    re.compile(r'logger\.(info|debug|error|warning)\([^)]*\{[^}]*\.email[^}]*\}', re.IGNORECASE),
                    'Email address in log message',
                    'Use safe_user_ref or correlation ID instead'
                ),
                # Mobile number in logging
                (
                    re.compile(r'logger\.(info|debug|error|warning)\([^)]*\{[^}]*mobno[^}]*\}', re.IGNORECASE),
                    'Mobile number in log message',
                    'Use safe_user_ref or correlation ID instead'
                ),
                # User object directly in logging
                (
                    re.compile(r'logger\.(info|debug|error|warning)\([^)]*\{[^}]*user\.[^}]*\}', re.IGNORECASE),
                    'User object property in log message',
                    'Use safe_user_ref instead'
                ),
                # Password-related logging
                (
                    re.compile(r'logger\.(info|debug|error|warning)\([^)]*password', re.IGNORECASE),
                    'Password reference in log message',
                    'Never log password-related information'
                ),
                # Token-related logging
                (
                    re.compile(r'logger\.(info|debug|error|warning)\([^)]*token', re.IGNORECASE),
                    'Token reference in log message',
                    'Use correlation ID for tracking instead'
                ),
                # Secret-related logging
                (
                    re.compile(r'logger\.(info|debug|error|warning)\([^)]*secret', re.IGNORECASE),
                    'Secret reference in log message',
                    'Never log secrets or API keys'
                ),
            ]

            for line_num, line in enumerate(lines, 1):
                for pattern, issue_type, recommendation in sensitive_logging_patterns:
                    if pattern.search(line):
                        issues.append({
                            'line': line_num,
                            'content': line.strip(),
                            'issue_type': issue_type,
                            'recommendation': recommendation
                        })

                        # Apply automatic fixes where possible
                        if fix_mode:
                            fixed_line = self._apply_logging_fix(line)
                            if fixed_line != line:
                                modified_content = modified_content.replace(line, fixed_line, 1)
                                fixes_applied += 1

            # Write back modified content if fixes were applied
            if fix_mode and fixes_applied > 0:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)

            return issues, fixes_applied

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            self.stderr.write(f"Error auditing {file_path}: {e}")
            return [], 0

    def _apply_logging_fix(self, line: str) -> str:
        """
        Apply automatic fixes to logging statements where possible.

        Args:
            line: Original line of code

        Returns:
            str: Fixed line of code
        """
        fixed_line = line

        # Fix email logging - replace with safe user reference
        email_pattern = re.compile(r'(\{[^}]*\.email[^}]*\})', re.IGNORECASE)
        if email_pattern.search(fixed_line):
            # Add comment about using safe reference
            if 'user.email' in fixed_line:
                fixed_line = email_pattern.sub('{request.safe_user_ref}', fixed_line)
                fixed_line += '  # FIXED: Use safe user reference instead of email'

        # Fix mobile number logging
        mobile_pattern = re.compile(r'(\{[^}]*mobno[^}]*\})', re.IGNORECASE)
        if mobile_pattern.search(fixed_line):
            fixed_line = mobile_pattern.sub('{request.safe_user_ref}', fixed_line)
            fixed_line += '  # FIXED: Use safe user reference instead of mobile'

        return fixed_line

    def _report_file_issues(self, file_path: str, issues: List[Dict]):
        """Report issues found in a file."""
        self.stdout.write(f"\n📁 {file_path}")
        self.stdout.write("─" * 80)

        for issue in issues:
            self.stdout.write(
                f"Line {issue['line']}: {self.style.ERROR(issue['issue_type'])}"
            )
            self.stdout.write(f"  Code: {issue['content']}")
            self.stdout.write(f"  Fix: {self.style.SUCCESS(issue['recommendation'])}")
            self.stdout.write("")

    def _print_summary(self, total_issues: int, fixed_issues: int, fix_mode: bool):
        """Print audit summary."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("📊 AUDIT SUMMARY")
        self.stdout.write("=" * 80)

        if total_issues == 0:
            self.stdout.write(self.style.SUCCESS("✅ No logging security issues found!"))
        else:
            self.stdout.write(f"🚨 Total issues found: {total_issues}")

            if fix_mode:
                self.stdout.write(f"🔧 Issues automatically fixed: {fixed_issues}")
                self.stdout.write(f"⚠️  Issues requiring manual fix: {total_issues - fixed_issues}")
            else:
                self.stdout.write("💡 Run with --fix to automatically fix some issues")

        self.stdout.write("\n🔧 RECOMMENDED NEXT STEPS:")
        self.stdout.write("1. Add LogSanitizationMiddleware to MIDDLEWARE in settings")
        self.stdout.write("2. Replace direct user.email logging with request.safe_user_ref")
        self.stdout.write("3. Use correlation IDs for tracking instead of sensitive data")
        self.stdout.write("4. Import and use sanitized_info/warning/error functions")
        self.stdout.write("5. Test logging in development to ensure sensitive data is sanitized")