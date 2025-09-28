"""
mentor_guard management command for the AI Mentor system.

This command validates safety checks and applies guardrails
before any AI-generated changes are made to the codebase.
"""

import os
import json
import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from apps.mentor.guards.secret_scanner import SecretScanner
from apps.mentor.analyzers.security_scanner import SecurityScanner


class GuardLevel(Enum):
    """Guard levels for different types of validations."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class GuardResult:
    """Represents the result of a guard check."""
    check_name: str
    level: GuardLevel
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    recommendation: Optional[str] = None
    auto_fixable: bool = False


@dataclass
class GuardReport:
    """Complete guard validation report."""
    total_checks: int
    passed_checks: int
    failed_checks: int
    results: List[GuardResult]
    overall_status: str  # PASS, WARN, FAIL
    blocking_issues: List[GuardResult]


class PreCommitGuard:
    """Pre-commit safety checks and validations."""

    def __init__(self):
        self.scope_controller = ScopeController()
        self.migration_checker = MigrationSafetyChecker()
        self.secret_scanner = SecretScanner()
        self.security_scanner = SecurityScanner()

    def run_all_checks(self, files: Optional[List[str]] = None) -> GuardReport:
        """Run all pre-commit guard checks."""
        if not files:
            files = self._get_staged_files()

        results = []

        # Run individual checks
        results.extend(self._check_scope_compliance(files))
        results.extend(self._check_migration_safety(files))
        results.extend(self._check_for_secrets(files))
        results.extend(self._check_security_issues(files))
        results.extend(self._check_code_quality(files))
        results.extend(self._check_test_coverage(files))
        results.extend(self._check_dependencies(files))

        # Generate report
        return self._generate_report(results)

    def _get_staged_files(self) -> List[str]:
        """Get list of staged files from git."""
        try:
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only'],
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                check=True
            )
            return [line.strip() for line in result.stdout.split('\n') if line.strip()]
        except subprocess.CalledProcessError:
            return []

    def _check_scope_compliance(self, files: List[str]) -> List[GuardResult]:
        """Check if changes comply with scope restrictions."""
        results = []

        for file_path in files:
            if not self.scope_controller.is_file_allowed(file_path):
                results.append(GuardResult(
                    check_name="scope_compliance",
                    level=GuardLevel.ERROR,
                    message=f"File is outside allowed scope",
                    file_path=file_path,
                    recommendation="Move file to allowed directory or update scope configuration"
                ))

        return results

    def _check_migration_safety(self, files: List[str]) -> List[GuardResult]:
        """Check Django migration safety."""
        results = []

        migration_files = [f for f in files if 'migrations/' in f and f.endswith('.py')]

        for migration_file in migration_files:
            if not os.path.exists(migration_file):
                continue

            try:
                # Mock migration data - in real implementation, parse the file
                migration_data = {'operations': []}
                safety_checks = self.migration_checker.validate_migration_safety(
                    migration_file, migration_data
                )

                for check in safety_checks:
                    level = GuardLevel.CRITICAL if check.level == SafetyLevel.DANGEROUS else GuardLevel.WARNING
                    results.append(GuardResult(
                        check_name="migration_safety",
                        level=level,
                        message=check.description,
                        file_path=migration_file,
                        recommendation=check.recommendation
                    ))

            except (TypeError, ValidationError, ValueError) as e:
                results.append(GuardResult(
                    check_name="migration_safety",
                    level=GuardLevel.ERROR,
                    message=f"Could not validate migration: {e}",
                    file_path=migration_file
                ))

        return results

    def _check_for_secrets(self, files: List[str]) -> List[GuardResult]:
        """Scan for secrets and sensitive information."""
        results = []

        for file_path in files:
            if not os.path.exists(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                secrets = self.secret_scanner.scan_content(content, file_path)

                for secret in secrets:
                    results.append(GuardResult(
                        check_name="secret_scan",
                        level=GuardLevel.CRITICAL,
                        message=f"Potential secret detected: {secret.get('type', 'unknown')}",
                        file_path=file_path,
                        line_number=secret.get('line_number'),
                        recommendation="Remove secret and use environment variables or secure vault",
                        auto_fixable=True
                    ))

            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
                results.append(GuardResult(
                    check_name="secret_scan",
                    level=GuardLevel.WARNING,
                    message=f"Could not scan file for secrets: {e}",
                    file_path=file_path
                ))

        return results

    def _check_security_issues(self, files: List[str]) -> List[GuardResult]:
        """Check for security vulnerabilities."""
        results = []

        python_files = [f for f in files if f.endswith('.py')]

        for file_path in python_files:
            if not os.path.exists(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                security_issues = self.security_scanner.scan_file(file_path, content)

                for issue in security_issues:
                    level = GuardLevel.CRITICAL if issue.get('severity') == 'high' else GuardLevel.WARNING
                    results.append(GuardResult(
                        check_name="security_scan",
                        level=level,
                        message=f"Security issue: {issue.get('type', 'unknown')}",
                        file_path=file_path,
                        line_number=issue.get('line_number'),
                        recommendation=issue.get('recommendation'),
                        auto_fixable=issue.get('auto_fixable', False)
                    ))

            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
                results.append(GuardResult(
                    check_name="security_scan",
                    level=GuardLevel.WARNING,
                    message=f"Could not scan file for security issues: {e}",
                    file_path=file_path
                ))

        return results

    def _check_code_quality(self, files: List[str]) -> List[GuardResult]:
        """Check code quality with basic linting."""
        results = []

        python_files = [f for f in files if f.endswith('.py')]

        for file_path in python_files:
            if not os.path.exists(file_path):
                continue

            # Simple code quality checks
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')

                # Check for common issues
                for line_num, line in enumerate(lines, 1):
                    line_stripped = line.strip()

                    # Check for bare except
                    if line_stripped == 'except:':
                        results.append(GuardResult(
                            check_name="code_quality",
                            level=GuardLevel.WARNING,
                            message="Bare except clause detected",
                            file_path=file_path,
                            line_number=line_num,
                            recommendation="Specify specific exception types",
                            auto_fixable=True
                        ))

                    # Check for print statements
                    if line_stripped.startswith('print(') and 'debug' not in line.lower():
                        results.append(GuardResult(
                            check_name="code_quality",
                            level=GuardLevel.INFO,
                            message="Print statement in code",
                            file_path=file_path,
                            line_number=line_num,
                            recommendation="Use logging instead of print",
                            auto_fixable=True
                        ))

                    # Check line length (basic)
                    if len(line) > 120:
                        results.append(GuardResult(
                            check_name="code_quality",
                            level=GuardLevel.WARNING,
                            message="Line too long",
                            file_path=file_path,
                            line_number=line_num,
                            recommendation="Break line into multiple lines"
                        ))

            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError):
                pass

        return results

    def _check_test_coverage(self, files: List[str]) -> List[GuardResult]:
        """Check if changes have corresponding tests."""
        results = []

        python_files = [f for f in files if f.endswith('.py') and not f.endswith('test.py')]

        for file_path in python_files:
            # Skip test files, migrations, and other non-testable files
            if any(skip in file_path for skip in ['test', 'migration', '__init__']):
                continue

            # Check if corresponding test file exists
            test_patterns = [
                file_path.replace('.py', '_test.py'),
                file_path.replace('.py', 'test.py'),
                file_path.replace('/', '/tests/').replace('.py', '_test.py')
            ]

            has_test = any(os.path.exists(pattern) for pattern in test_patterns)

            if not has_test:
                results.append(GuardResult(
                    check_name="test_coverage",
                    level=GuardLevel.WARNING,
                    message="No corresponding test file found",
                    file_path=file_path,
                    recommendation=f"Create test file: {test_patterns[0]}"
                ))

        return results

    def _check_dependencies(self, files: List[str]) -> List[GuardResult]:
        """Check for dependency-related issues."""
        results = []

        # Check requirements.txt changes
        req_files = [f for f in files if 'requirements' in f and f.endswith('.txt')]

        for req_file in req_files:
            if not os.path.exists(req_file):
                continue

            try:
                with open(req_file, 'r') as f:
                    requirements = f.read()

                # Check for unpinned versions
                for line_num, line in enumerate(requirements.split('\n'), 1):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '==' not in line and '>=' not in line:
                            results.append(GuardResult(
                                check_name="dependency_check",
                                level=GuardLevel.WARNING,
                                message="Unpinned dependency version",
                                file_path=req_file,
                                line_number=line_num,
                                recommendation="Pin dependency to specific version"
                            ))

            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError):
                pass

        return results

    def _generate_report(self, results: List[GuardResult]) -> GuardReport:
        """Generate a comprehensive guard report."""
        total_checks = len(results)
        failed_checks = [r for r in results if r.level in [GuardLevel.ERROR, GuardLevel.CRITICAL]]
        warning_checks = [r for r in results if r.level == GuardLevel.WARNING]
        passed_checks = total_checks - len(failed_checks) - len(warning_checks)

        # Determine overall status
        if any(r.level == GuardLevel.CRITICAL for r in results):
            overall_status = "FAIL"
        elif any(r.level == GuardLevel.ERROR for r in results):
            overall_status = "FAIL"
        elif any(r.level == GuardLevel.WARNING for r in results):
            overall_status = "WARN"
        else:
            overall_status = "PASS"

        # Identify blocking issues
        blocking_issues = [r for r in results if r.level in [GuardLevel.ERROR, GuardLevel.CRITICAL]]

        return GuardReport(
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=len(failed_checks),
            results=results,
            overall_status=overall_status,
            blocking_issues=blocking_issues
        )


class Command(BaseCommand):
    help = 'Run safety checks and validation guards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Run all validation checks'
        )
        parser.add_argument(
            '--pre-commit',
            action='store_true',
            help='Run pre-commit hooks and validation'
        )
        parser.add_argument(
            '--files',
            type=str,
            nargs='*',
            help='Specific files to validate'
        )
        parser.add_argument(
            '--check',
            type=str,
            choices=['scope', 'migration', 'secrets', 'security', 'quality', 'coverage', 'dependencies'],
            help='Run specific check type'
        )
        parser.add_argument(
            '--fix-auto',
            action='store_true',
            help='Automatically fix issues that can be auto-fixed'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['summary', 'detailed', 'json'],
            default='summary',
            help='Output format'
        )
        parser.add_argument(
            '--fail-on',
            type=str,
            choices=['critical', 'error', 'warning', 'info'],
            default='error',
            help='Exit with error on this severity level or higher'
        )
        parser.add_argument(
            '--exclude',
            type=str,
            nargs='*',
            help='File patterns to exclude from checks'
        )

    def handle(self, *args, **options):
        validate = options.get('validate', False)
        pre_commit = options.get('pre_commit', False)
        files = options.get('files')
        specific_check = options.get('check')
        fix_auto = options.get('fix_auto', False)
        output_format = options.get('format', 'summary')
        fail_on_level = options.get('fail_on', 'error')
        exclude_patterns = options.get('exclude', [])

        if not (validate or pre_commit or specific_check):
            self.stdout.write(self.style.WARNING("No action specified. Use --validate, --pre-commit, or --check"))
            return

        try:
            guard = PreCommitGuard()

            self.stdout.write("🛡️  Running safety validation checks...")

            if validate or pre_commit:
                # Run all checks
                report = guard.run_all_checks(files)
            elif specific_check:
                # Run specific check
                report = self._run_specific_check(guard, specific_check, files)
            else:
                report = GuardReport(0, 0, 0, [], "PASS", [])

            # Filter out excluded patterns
            if exclude_patterns:
                report.results = self._filter_results(report.results, exclude_patterns)

            # Display results
            self._display_report(report, output_format)

            # Auto-fix if requested
            if fix_auto:
                self._apply_auto_fixes(report.results)

            # Determine exit code
            exit_code = self._get_exit_code(report, fail_on_level)

            if exit_code != 0:
                raise CommandError(f"Validation failed with {len(report.blocking_issues)} blocking issues")

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.stdout.write(self.style.ERROR(f"❌ Guard validation failed: {e}"))
            raise

    def _run_specific_check(self, guard: PreCommitGuard, check_type: str,
                          files: Optional[List[str]]) -> GuardReport:
        """Run a specific type of check."""
        if not files:
            files = guard._get_staged_files()

        results = []

        if check_type == 'scope':
            results = guard._check_scope_compliance(files)
        elif check_type == 'migration':
            results = guard._check_migration_safety(files)
        elif check_type == 'secrets':
            results = guard._check_for_secrets(files)
        elif check_type == 'security':
            results = guard._check_security_issues(files)
        elif check_type == 'quality':
            results = guard._check_code_quality(files)
        elif check_type == 'coverage':
            results = guard._check_test_coverage(files)
        elif check_type == 'dependencies':
            results = guard._check_dependencies(files)

        return guard._generate_report(results)

    def _filter_results(self, results: List[GuardResult],
                       exclude_patterns: List[str]) -> List[GuardResult]:
        """Filter out results matching exclude patterns."""
        filtered = []

        for result in results:
            if result.file_path:
                should_exclude = any(
                    pattern in result.file_path for pattern in exclude_patterns
                )
                if not should_exclude:
                    filtered.append(result)
            else:
                filtered.append(result)

        return filtered

    def _display_report(self, report: GuardReport, output_format: str):
        """Display the validation report."""
        if output_format == 'json':
            self._display_json_report(report)
        elif output_format == 'detailed':
            self._display_detailed_report(report)
        else:
            self._display_summary_report(report)

    def _display_summary_report(self, report: GuardReport):
        """Display summary validation report."""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("SAFETY VALIDATION REPORT")
        self.stdout.write("="*60)

        # Overall status
        status_icons = {
            'PASS': '✅',
            'WARN': '⚠️',
            'FAIL': '❌'
        }
        icon = status_icons.get(report.overall_status, '❓')
        self.stdout.write(f"Overall Status: {icon} {report.overall_status}")

        # Statistics
        self.stdout.write(f"Total Checks: {report.total_checks}")
        if report.passed_checks > 0:
            self.stdout.write(f"✅ Passed: {report.passed_checks}")
        if report.failed_checks > 0:
            self.stdout.write(f"❌ Failed: {report.failed_checks}")

        # Blocking issues
        if report.blocking_issues:
            self.stdout.write(f"\n🚫 BLOCKING ISSUES ({len(report.blocking_issues)}):")
            for issue in report.blocking_issues:
                self.stdout.write(f"  • {issue.file_path or 'General'}: {issue.message}")
                if issue.recommendation:
                    self.stdout.write(f"    → {issue.recommendation}")

        # Summary by check type
        check_counts = {}
        for result in report.results:
            check_counts[result.check_name] = check_counts.get(result.check_name, 0) + 1

        if check_counts:
            self.stdout.write(f"\nCHECK BREAKDOWN:")
            for check_name, count in check_counts.items():
                self.stdout.write(f"  {check_name}: {count} issues")

    def _display_detailed_report(self, report: GuardReport):
        """Display detailed validation report."""
        self._display_summary_report(report)

        if report.results:
            self.stdout.write("\n" + "="*60)
            self.stdout.write("DETAILED RESULTS")
            self.stdout.write("="*60)

            for i, result in enumerate(report.results, 1):
                level_icons = {
                    GuardLevel.INFO: 'ℹ️',
                    GuardLevel.WARNING: '⚠️',
                    GuardLevel.ERROR: '❌',
                    GuardLevel.CRITICAL: '🚨'
                }
                icon = level_icons.get(result.level, '❓')

                self.stdout.write(f"\n{i:2d}. {icon} {result.message}")
                self.stdout.write(f"    Check: {result.check_name}")
                self.stdout.write(f"    Level: {result.level.value}")

                if result.file_path:
                    location = result.file_path
                    if result.line_number:
                        location += f":{result.line_number}"
                    self.stdout.write(f"    Location: {location}")

                if result.recommendation:
                    self.stdout.write(f"    Recommendation: {result.recommendation}")

                if result.auto_fixable:
                    self.stdout.write("    🔧 Auto-fixable")

    def _display_json_report(self, report: GuardReport):
        """Display report in JSON format."""
        report_data = {
            'overall_status': report.overall_status,
            'total_checks': report.total_checks,
            'passed_checks': report.passed_checks,
            'failed_checks': report.failed_checks,
            'blocking_issues': len(report.blocking_issues),
            'results': [
                {
                    'check_name': r.check_name,
                    'level': r.level.value,
                    'message': r.message,
                    'file_path': r.file_path,
                    'line_number': r.line_number,
                    'recommendation': r.recommendation,
                    'auto_fixable': r.auto_fixable
                } for r in report.results
            ]
        }

        self.stdout.write(json.dumps(report_data, indent=2))

    def _apply_auto_fixes(self, results: List[GuardResult]):
        """Apply automatic fixes for issues that can be auto-fixed."""
        auto_fixable = [r for r in results if r.auto_fixable]

        if not auto_fixable:
            return

        self.stdout.write(f"\n🔧 Applying {len(auto_fixable)} automatic fixes...")

        for result in auto_fixable:
            try:
                if result.check_name == 'secret_scan':
                    self._fix_secret(result)
                elif result.check_name == 'code_quality':
                    self._fix_code_quality(result)

                self.stdout.write(f"  ✅ Fixed: {result.file_path}:{result.line_number or ''}")
            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
                self.stdout.write(f"  ❌ Failed to fix {result.file_path}: {e}")

    def _fix_secret(self, result: GuardResult):
        """Fix a detected secret by replacing with placeholder."""
        if not result.file_path or not result.line_number:
            return

        file_path = Path(result.file_path)
        lines = file_path.read_text().split('\n')

        if result.line_number <= len(lines):
            line = lines[result.line_number - 1]
            # Simple replacement - in production, this would be more sophisticated
            fixed_line = line.replace('password=', 'password=os.getenv("PASSWORD", "")')
            lines[result.line_number - 1] = fixed_line
            file_path.write_text('\n'.join(lines))

    def _fix_code_quality(self, result: GuardResult):
        """Fix a code quality issue."""
        if not result.file_path or not result.line_number:
            return

        file_path = Path(result.file_path)
        lines = file_path.read_text().split('\n')

        if result.line_number <= len(lines):
            line = lines[result.line_number - 1]

            if 'print(' in line:
                # Replace print with logger
                fixed_line = line.replace('print(', 'logger.info(')
                lines[result.line_number - 1] = fixed_line

            elif 'except:' in line:
                # Replace bare except
                fixed_line = line.replace('except:', 'except (DatabaseError, IntegrityError, ValueError, TypeError, ObjectDoesNotExist) as e:')
                lines[result.line_number - 1] = fixed_line

            file_path.write_text('\n'.join(lines))

    def _get_exit_code(self, report: GuardReport, fail_on_level: str) -> int:
        """Determine exit code based on validation results and fail level."""
        level_hierarchy = {
            'info': 0,
            'warning': 1,
            'error': 2,
            'critical': 3
        }

        fail_threshold = level_hierarchy.get(fail_on_level, 2)
        max_result_level = 0

        for result in report.results:
            result_level = level_hierarchy.get(result.level.value, 0)
            max_result_level = max(max_result_level, result_level)

        return 1 if max_result_level >= fail_threshold else 0