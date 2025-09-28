"""
mentor_test management command for the AI Mentor system.

This command runs targeted tests based on impact analysis,
coverage data, and code changes with intelligent test selection.
"""

import os
import json
import subprocess
import time
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

    IndexedFile, CodeSymbol, SymbolRelation, TestCase, TestCoverage, IndexMetadata
)
from apps.mentor.analyzers.impact_analyzer import ImpactAnalyzer


@dataclass
class TestResult:
    """Represents the result of a test execution."""
    node_id: str
    status: str  # passed, failed, skipped, error
    duration: float
    output: str
    error_message: Optional[str] = None


@dataclass
class TestSession:
    """Represents a complete test session."""
    session_id: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    total_duration: float
    results: List[TestResult]
    coverage_percentage: Optional[float] = None


class TestSelector:
    """Intelligent test selection based on code changes and impact analysis."""

    def __init__(self):
        self.impact_analyzer = ImpactAnalyzer()

    def select_tests_for_changes(self, changed_files: List[str]) -> Set[str]:
        """Select tests based on changed files using impact analysis."""
        selected_tests = set()

        for file_path in changed_files:
            # Direct test selection
            direct_tests = self._get_direct_tests(file_path)
            selected_tests.update(direct_tests)

            # Impact-based test selection
            impacted_symbols = self._get_impacted_symbols(file_path)
            for symbol in impacted_symbols:
                related_tests = self._get_tests_for_symbol(symbol)
                selected_tests.update(related_tests)

        return selected_tests

    def select_tests_for_symbols(self, symbols: List[str]) -> Set[str]:
        """Select tests based on specific symbols/functions."""
        selected_tests = set()

        for symbol_name in symbols:
            # Find symbol in database
            try:
                symbol = CodeSymbol.objects.filter(name=symbol_name).first()
                if symbol:
                    related_tests = self._get_tests_for_symbol(symbol)
                    selected_tests.update(related_tests)
            except (DatabaseError, IntegrityError, ObjectDoesNotExist):
                continue

        return selected_tests

    def select_flaky_tests(self, success_rate_threshold: float = 0.95) -> Set[str]:
        """Select tests that are flaky (low success rate)."""
        flaky_tests = TestCase.objects.filter(
            success_rate__lt=success_rate_threshold
        ).values_list('node_id', flat=True)

        return set(flaky_tests)

    def select_slow_tests(self, time_threshold: float = 5.0) -> Set[str]:
        """Select tests that are slow (high execution time)."""
        slow_tests = TestCase.objects.filter(
            avg_execution_time__gt=time_threshold
        ).values_list('node_id', flat=True)

        return set(slow_tests)

    def select_by_coverage_gap(self, target_files: List[str]) -> Set[str]:
        """Select tests to improve coverage for specific files."""
        selected_tests = set()

        for file_path in target_files:
            try:
                # Find file in database
                indexed_file = IndexedFile.objects.get(path=file_path)

                # Get tests that cover this file, ordered by coverage percentage
                coverage_records = TestCoverage.objects.filter(
                    file=indexed_file
                ).order_by('-coverage_percentage')[:10]  # Top 10 tests

                for record in coverage_records:
                    selected_tests.add(record.test.node_id)

            except IndexedFile.DoesNotExist:
                continue

        return selected_tests

    def _get_direct_tests(self, file_path: str) -> Set[str]:
        """Get tests directly associated with a file."""
        tests = set()

        # Pattern-based test discovery
        test_patterns = [
            file_path.replace('.py', '_test.py'),
            file_path.replace('.py', 'test.py'),
            file_path.replace('/', '/tests/').replace('.py', '_test.py'),
            file_path.replace('/', '/test_').replace('.py', '.py'),
        ]

        for pattern in test_patterns:
            if os.path.exists(pattern):
                # Get all test methods in the file
                test_cases = TestCase.objects.filter(file__path=pattern)
                tests.update(test_cases.values_list('node_id', flat=True))

        return tests

    def _get_impacted_symbols(self, file_path: str) -> List[CodeSymbol]:
        """Get symbols that might be impacted by changes to a file."""
        impacted_symbols = []

        try:
            # Get file from database
            indexed_file = IndexedFile.objects.get(path=file_path)

            # Get all symbols in the file
            file_symbols = CodeSymbol.objects.filter(file=indexed_file)

            # Get symbols that depend on these symbols
            for symbol in file_symbols:
                # Get symbols that import or call this symbol
                related_relations = SymbolRelation.objects.filter(
                    target=symbol,
                    kind__in=['import', 'call', 'reference']
                )

                for relation in related_relations:
                    impacted_symbols.append(relation.source)

        except IndexedFile.DoesNotExist:
            pass

        return impacted_symbols

    def _get_tests_for_symbol(self, symbol: CodeSymbol) -> Set[str]:
        """Get tests that exercise a specific symbol."""
        tests = set()

        # Get coverage records for this symbol's file
        coverage_records = TestCoverage.objects.filter(file=symbol.file)

        for record in coverage_records:
            # Check if the test covers the symbol's line range
            covered_lines = record.covered_lines
            if (covered_lines and
                any(symbol.span_start <= line <= symbol.span_end for line in covered_lines)):
                tests.add(record.test.node_id)

        return tests


class TestRunner:
    """Executes tests and collects results."""

    def __init__(self):
        self.base_dir = Path(settings.BASE_DIR)

    def run_tests(self, test_node_ids: Set[str],
                  collect_coverage: bool = False,
                  parallel: bool = True,
                  timeout: int = 600) -> TestSession:
        """Run specified tests and return results."""
        if not test_node_ids:
            raise ValueError("No tests specified")

        session_id = f"session_{int(time.time())}"

        # Build pytest command
        cmd = ['python', '-m', 'pytest', '-v', '--tb=short']

        if collect_coverage:
            cmd.extend(['--cov=apps', '--cov-report=json'])

        if parallel:
            cmd.append('--parallel')

        # Add test node IDs
        cmd.extend(test_node_ids)

        self.stdout.write(f"🧪 Running {len(test_node_ids)} tests...")

        start_time = time.time()

        try:
            # Run pytest
            result = subprocess.run(
                cmd,
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            end_time = time.time()
            duration = end_time - start_time

            # Parse results
            session = self._parse_pytest_output(
                result, session_id, test_node_ids, duration
            )

            # Parse coverage if collected
            if collect_coverage:
                session.coverage_percentage = self._parse_coverage_data()

            return session

        except subprocess.TimeoutExpired:
            raise CommandError(f"Tests timed out after {timeout} seconds")
        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            raise CommandError(f"Test execution failed: {e}")

    def run_all_tests(self, markers: Optional[List[str]] = None,
                     collect_coverage: bool = False) -> TestSession:
        """Run all tests with optional filtering by markers."""
        cmd = ['python', '-m', 'pytest', '-v', '--tb=short']

        if collect_coverage:
            cmd.extend(['--cov=apps', '--cov-report=json'])

        if markers:
            for marker in markers:
                cmd.extend(['-m', marker])

        session_id = f"full_session_{int(time.time())}"
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout for full test suite
            )

            end_time = time.time()
            duration = end_time - start_time

            # Get all test node IDs (approximate)
            all_tests = TestCase.objects.values_list('node_id', flat=True)

            session = self._parse_pytest_output(
                result, session_id, set(all_tests), duration
            )

            if collect_coverage:
                session.coverage_percentage = self._parse_coverage_data()

            return session

        except subprocess.TimeoutExpired:
            raise CommandError("Full test suite timed out")
        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            raise CommandError(f"Full test execution failed: {e}")

    def _parse_pytest_output(self, result: subprocess.CompletedProcess,
                           session_id: str, test_node_ids: Set[str],
                           duration: float) -> TestSession:
        """Parse pytest output into structured results."""
        test_results = []

        # Parse the output to extract individual test results
        output_lines = result.stdout.split('\n')

        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        # Simple parsing - in production, we'd use pytest-json-report plugin
        for line in output_lines:
            if '::' in line and any(status in line for status in ['PASSED', 'FAILED', 'SKIPPED', 'ERROR']):
                parts = line.split()
                if len(parts) >= 2:
                    node_id = parts[0]
                    status = 'passed'  # Default

                    if 'FAILED' in line:
                        status = 'failed'
                        failed += 1
                    elif 'SKIPPED' in line:
                        status = 'skipped'
                        skipped += 1
                    elif 'ERROR' in line:
                        status = 'error'
                        errors += 1
                    else:
                        passed += 1

                    # Extract duration if available
                    test_duration = 0.1  # Default
                    if '[' in line and ']' in line:
                        try:
                            duration_str = line.split('[')[1].split(']')[0]
                            if 's' in duration_str:
                                test_duration = float(duration_str.replace('s', ''))
                        except:
                            pass

                    test_results.append(TestResult(
                        node_id=node_id,
                        status=status,
                        duration=test_duration,
                        output=line,
                        error_message=None if status == 'passed' else 'Test failed'
                    ))

        return TestSession(
            session_id=session_id,
            total_tests=len(test_node_ids),
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            total_duration=duration,
            results=test_results
        )

    def _parse_coverage_data(self) -> Optional[float]:
        """Parse coverage data from JSON report."""
        coverage_file = self.base_dir / 'coverage.json'

        if coverage_file.exists():
            try:
                with open(coverage_file) as f:
                    coverage_data = json.load(f)
                    return coverage_data.get('totals', {}).get('percent_covered')
            except:
                pass

        return None


class Command(BaseCommand):
    help = 'Run targeted tests based on code changes and impact analysis'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_selector = TestSelector()
        self.test_runner = TestRunner()

    def add_arguments(self, parser):
        parser.add_argument(
            '--targets',
            type=str,
            nargs='*',
            help='Specific files or symbols to test'
        )
        parser.add_argument(
            '--changed',
            action='store_true',
            help='Test only files changed since last commit'
        )
        parser.add_argument(
            '--since',
            type=str,
            help='Test files changed since specific commit SHA'
        )
        parser.add_argument(
            '--flaky',
            action='store_true',
            help='Run only flaky tests (low success rate)'
        )
        parser.add_argument(
            '--slow',
            action='store_true',
            help='Run only slow tests'
        )
        parser.add_argument(
            '--coverage',
            action='store_true',
            help='Collect code coverage data'
        )
        parser.add_argument(
            '--coverage-gap',
            type=str,
            nargs='*',
            help='Run tests to improve coverage for specific files'
        )
        parser.add_argument(
            '--markers',
            type=str,
            nargs='*',
            help='Filter tests by pytest markers (unit, integration, security, etc.)'
        )
        parser.add_argument(
            '--parallel',
            action='store_true',
            default=True,
            help='Run tests in parallel'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=600,
            help='Test execution timeout in seconds'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all tests (overrides other filters)'
        )
        parser.add_argument(
            '--update-stats',
            action='store_true',
            help='Update test statistics in database'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['summary', 'detailed', 'json'],
            default='summary',
            help='Output format'
        )

    def handle(self, *args, **options):
        targets = options.get('targets', [])
        changed = options.get('changed', False)
        since_commit = options.get('since')
        flaky = options.get('flaky', False)
        slow = options.get('slow', False)
        coverage = options.get('coverage', False)
        coverage_gap = options.get('coverage_gap', [])
        markers = options.get('markers')
        parallel = options.get('parallel', True)
        timeout = options.get('timeout', 600)
        run_all = options.get('all', False)
        update_stats = options.get('update_stats', False)
        output_format = options.get('format', 'summary')

        try:
            if run_all:
                self.stdout.write("🧪 Running full test suite...")
                session = self.test_runner.run_all_tests(
                    markers=markers,
                    collect_coverage=coverage
                )
            else:
                # Select tests based on criteria
                selected_tests = set()

                if targets:
                    self.stdout.write(f"🎯 Selecting tests for targets: {targets}")
                    # Check if targets are files or symbols
                    file_targets = [t for t in targets if os.path.exists(t)]
                    symbol_targets = [t for t in targets if t not in file_targets]

                    if file_targets:
                        selected_tests.update(
                            self.test_selector.select_tests_for_changes(file_targets)
                        )

                    if symbol_targets:
                        selected_tests.update(
                            self.test_selector.select_tests_for_symbols(symbol_targets)
                        )

                if changed:
                    self.stdout.write("📊 Selecting tests for changed files...")
                    changed_files = self._get_changed_files(since_commit)
                    if changed_files:
                        selected_tests.update(
                            self.test_selector.select_tests_for_changes(changed_files)
                        )
                        self.stdout.write(f"Found {len(changed_files)} changed files")

                if flaky:
                    self.stdout.write("🎲 Selecting flaky tests...")
                    flaky_tests = self.test_selector.select_flaky_tests()
                    selected_tests.update(flaky_tests)
                    self.stdout.write(f"Found {len(flaky_tests)} flaky tests")

                if slow:
                    self.stdout.write("🐌 Selecting slow tests...")
                    slow_tests = self.test_selector.select_slow_tests()
                    selected_tests.update(slow_tests)
                    self.stdout.write(f"Found {len(slow_tests)} slow tests")

                if coverage_gap:
                    self.stdout.write(f"📈 Selecting tests to improve coverage for: {coverage_gap}")
                    gap_tests = self.test_selector.select_by_coverage_gap(coverage_gap)
                    selected_tests.update(gap_tests)

                if not selected_tests:
                    self.stdout.write(self.style.WARNING("⚠️  No tests selected"))
                    return

                # Run selected tests
                session = self.test_runner.run_tests(
                    selected_tests,
                    collect_coverage=coverage,
                    parallel=parallel,
                    timeout=timeout
                )

            # Display results
            self._display_results(session, output_format)

            # Update test statistics in database
            if update_stats:
                self._update_test_stats(session)

            # Exit with error code if tests failed
            if session.failed > 0 or session.errors > 0:
                raise CommandError(f"Tests failed: {session.failed} failed, {session.errors} errors")

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))
            raise

    def _get_changed_files(self, since_commit: Optional[str] = None) -> List[str]:
        """Get list of changed files using git."""
        try:
            if since_commit:
                cmd = ['git', 'diff', '--name-only', since_commit, 'HEAD']
            else:
                cmd = ['git', 'diff', '--name-only', 'HEAD~1', 'HEAD']

            result = subprocess.run(
                cmd,
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                check=True
            )

            changed_files = [
                line.strip() for line in result.stdout.split('\n')
                if line.strip() and line.strip().endswith('.py')
            ]

            return changed_files

        except subprocess.CalledProcessError:
            return []

    def _display_results(self, session: TestSession, output_format: str):
        """Display test results in the specified format."""
        if output_format == 'json':
            self._display_json_results(session)
        elif output_format == 'detailed':
            self._display_detailed_results(session)
        else:
            self._display_summary_results(session)

    def _display_summary_results(self, session: TestSession):
        """Display summary test results."""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("TEST RESULTS SUMMARY")
        self.stdout.write("="*60)

        # Overall stats
        total = session.total_tests
        success_rate = (session.passed / total * 100) if total > 0 else 0

        self.stdout.write(f"Total Tests: {total}")
        self.stdout.write(f"Passed: {session.passed} ({session.passed/total*100:.1f}%)" if total > 0 else "Passed: 0")
        self.stdout.write(f"Failed: {session.failed}")
        self.stdout.write(f"Skipped: {session.skipped}")
        self.stdout.write(f"Errors: {session.errors}")
        self.stdout.write(f"Duration: {session.total_duration:.2f}s")

        if session.coverage_percentage:
            self.stdout.write(f"Coverage: {session.coverage_percentage:.1f}%")

        # Status icon
        if session.failed == 0 and session.errors == 0:
            self.stdout.write(self.style.SUCCESS("✅ All tests passed!"))
        else:
            self.stdout.write(self.style.ERROR("❌ Some tests failed"))

    def _display_detailed_results(self, session: TestSession):
        """Display detailed test results."""
        self._display_summary_results(session)

        if session.results:
            self.stdout.write("\n" + "="*60)
            self.stdout.write("DETAILED RESULTS")
            self.stdout.write("="*60)

            for result in session.results:
                status_icon = {
                    'passed': '✅',
                    'failed': '❌',
                    'skipped': '⏭️',
                    'error': '💥'
                }.get(result.status, '❓')

                self.stdout.write(f"{status_icon} {result.node_id} ({result.duration:.2f}s)")

                if result.error_message:
                    self.stdout.write(f"   Error: {result.error_message}")

    def _display_json_results(self, session: TestSession):
        """Display results in JSON format."""
        result_data = {
            'session_id': session.session_id,
            'total_tests': session.total_tests,
            'passed': session.passed,
            'failed': session.failed,
            'skipped': session.skipped,
            'errors': session.errors,
            'duration': session.total_duration,
            'coverage_percentage': session.coverage_percentage,
            'results': [
                {
                    'node_id': r.node_id,
                    'status': r.status,
                    'duration': r.duration,
                    'error_message': r.error_message
                } for r in session.results
            ]
        }

        self.stdout.write(json.dumps(result_data, indent=2))

    def _update_test_stats(self, session: TestSession):
        """Update test statistics in the database."""
        self.stdout.write("📊 Updating test statistics...")

        for result in session.results:
            try:
                test_case = TestCase.objects.get(node_id=result.node_id)

                # Update execution time (moving average)
                if test_case.avg_execution_time > 0:
                    test_case.avg_execution_time = (
                        (test_case.avg_execution_time + result.duration) / 2
                    )
                else:
                    test_case.avg_execution_time = result.duration

                # Update success rate (simple moving average)
                if result.status == 'passed':
                    test_case.success_rate = min(1.0, test_case.success_rate + 0.1)
                elif result.status in ['failed', 'error']:
                    test_case.success_rate = max(0.0, test_case.success_rate - 0.1)

                test_case.last_run = timezone.now()
                test_case.save()

            except TestCase.DoesNotExist:
                # Create new test case record
                TestCase.objects.create(
                    node_id=result.node_id,
                    file=None,  # Would need to parse to get file
                    method_name=result.node_id.split('::')[-1] if '::' in result.node_id else result.node_id,
                    avg_execution_time=result.duration,
                    success_rate=1.0 if result.status == 'passed' else 0.0,
                    last_run=timezone.now()
                )

        self.stdout.write("✅ Test statistics updated")