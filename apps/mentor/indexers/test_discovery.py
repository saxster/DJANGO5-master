"""
Test discovery engine with pytest integration for comprehensive test analysis.

This engine provides deep analysis of:
- pytest integration: Marker extraction, fixture dependencies
- Django TestCase analysis: setUp/tearDown patterns
- Coverage mapping: Line-level coverage with pytest-cov
- Test categorization: Unit/integration/e2e classification
- Flakiness detection: Historical success rate tracking
"""

import ast
import json
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass

try:
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

from django.db import transaction



@dataclass
class TestInfo:
    """Container for test information."""
    node_id: str
    file_path: str
    class_name: Optional[str]
    method_name: str
    markers: List[str]
    fixtures: List[str]
    parametrize_values: List[Dict[str, Any]]
    docstring: Optional[str]
    line_number: int
    test_type: str  # 'unit', 'integration', 'e2e', 'functional'
    estimated_duration: float
    dependencies: List[str]
    tags: List[str]


@dataclass
class FixtureInfo:
    """Container for pytest fixture information."""
    name: str
    scope: str
    autouse: bool
    params: List[Any]
    file_path: str
    line_number: int
    dependencies: List[str]


@dataclass
class CoverageInfo:
    """Container for test coverage information."""
    test_node_id: str
    covered_files: Dict[str, List[int]]  # file_path -> covered_lines
    coverage_percentage: float
    missing_lines: Dict[str, List[int]]


class TestDiscoveryEngine:
    """Comprehensive test discovery and analysis engine."""

    def __init__(self):
        self.tests_info: List[TestInfo] = []
        self.fixtures_info: List[FixtureInfo] = []
        self.coverage_info: List[CoverageInfo] = []
        self.test_files: Set[str] = set()

    def discover_tests(self, test_paths: List[str]) -> Dict[str, int]:
        """Discover and analyze tests from given paths."""
        try:
            # Discover test files
            self._discover_test_files(test_paths)

            # Analyze each test file
            for file_path in self.test_files:
                self._analyze_test_file(file_path)

            # Run pytest collection if available
            if PYTEST_AVAILABLE:
                self._pytest_discovery(test_paths)

            # Analyze coverage data if available
            self._analyze_coverage_data()

            # Save to database
            return self._save_to_database()

        except (ValueError, TypeError) as e:
            print(f"Error discovering tests: {e}")
            return {'error': 1}

    def _discover_test_files(self, test_paths: List[str]):
        """Discover test files in the given paths."""
        for path_str in test_paths:
            path = Path(path_str)

            if path.is_file() and self._is_test_file(path):
                self.test_files.add(str(path))

            elif path.is_dir():
                # Recursively search for test files
                for py_file in path.rglob('*.py'):
                    if self._is_test_file(py_file):
                        self.test_files.add(str(py_file))

    def _is_test_file(self, file_path: Path) -> bool:
        """Check if file is a test file."""
        # Common test file patterns
        test_patterns = [
            'test_*.py',
            '*_test.py',
            'tests.py'
        ]

        # Check if filename matches test patterns
        for pattern in test_patterns:
            if file_path.match(pattern):
                return True

        # Check if file is in a tests directory
        if 'test' in str(file_path).lower():
            return True

        # Check file content for test indicators
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            test_indicators = [
                'class Test',
                'def test_',
                'import unittest',
                'from django.test',
                'import pytest',
                '@pytest.',
                'TestCase'
            ]

            return any(indicator in content for indicator in test_indicators)

        except (FileNotFoundError, IOError, OSError, PermissionError):
            return False

    def _analyze_test_file(self, file_path: str):
        """Analyze a single test file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            # Extract test information
            extractor = TestFileExtractor(file_path)
            extractor.visit(tree)

            # Merge results
            self.tests_info.extend(extractor.tests_info)
            self.fixtures_info.extend(extractor.fixtures_info)

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Error analyzing test file {file_path}: {e}")

    def _pytest_discovery(self, test_paths: List[str]):
        """Use pytest to discover tests and collect metadata."""
        if not PYTEST_AVAILABLE:
            return

        try:
            # Run pytest collection to get detailed test information
            cmd = [
                sys.executable, '-m', 'pytest',
                '--collect-only',
                '--quiet',
                '--tb=no'
            ] + test_paths

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                self._parse_pytest_collection(result.stdout)

        except subprocess.TimeoutExpired:
            print("Pytest collection timed out")
        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Pytest collection failed: {e}")

    def _parse_pytest_collection(self, collection_output: str):
        """Parse pytest collection output."""
        # This is a simplified parser - in practice, you'd use pytest's JSON plugin
        # or the pytest API directly for more detailed information
        lines = collection_output.split('\n')

        for line in lines:
            line = line.strip()
            if '::' in line and 'test_' in line:
                # This looks like a test node ID
                node_id = line

                # Extract information from node ID
                parts = node_id.split('::')
                if len(parts) >= 2:
                    file_path = parts[0]
                    test_name = parts[-1]

                    # Check if we already have this test
                    existing = any(
                        test.node_id == node_id for test in self.tests_info
                    )

                    if not existing:
                        # Create basic test info
                        test_info = TestInfo(
                            node_id=node_id,
                            file_path=file_path,
                            class_name=parts[1] if len(parts) > 2 else None,
                            method_name=test_name,
                            markers=[],
                            fixtures=[],
                            parametrize_values=[],
                            docstring=None,
                            line_number=1,
                            test_type='unit',  # Default
                            estimated_duration=1.0,
                            dependencies=[],
                            tags=[]
                        )
                        self.tests_info.append(test_info)

    def _analyze_coverage_data(self):
        """Analyze test coverage data if available."""
        try:
            # Look for coverage data files
            coverage_files = [
                '.coverage',
                'coverage.json',
                '.coverage.xml'
            ]

            for coverage_file in coverage_files:
                coverage_path = Path(coverage_file)
                if coverage_path.exists():
                    self._parse_coverage_file(coverage_path)
                    break

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Coverage analysis failed: {e}")

    def _parse_coverage_file(self, coverage_path: Path):
        """Parse coverage data file."""
        # This is a simplified implementation
        # In practice, you'd use the coverage.py API
        try:
            if coverage_path.name == 'coverage.json':
                with open(coverage_path, 'r') as f:
                    data = json.load(f)

                # Extract coverage information
                files = data.get('files', {})
                for file_path, coverage_data in files.items():
                    covered_lines = coverage_data.get('executed_lines', [])
                    missing_lines = coverage_data.get('missing_lines', [])

                    # This is simplified - would need to map to specific tests
                    coverage_info = CoverageInfo(
                        test_node_id='unknown',
                        covered_files={file_path: covered_lines},
                        coverage_percentage=coverage_data.get('summary', {}).get('percent_covered', 0),
                        missing_lines={file_path: missing_lines}
                    )
                    self.coverage_info.append(coverage_info)

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Error parsing coverage file {coverage_path}: {e}")

    def _save_to_database(self) -> Dict[str, int]:
        """Save test information to database."""
        stats = {'tests': 0, 'coverage_records': 0, 'errors': 0}

        try:
            with transaction.atomic():
                # Save tests
                for test_info in self.tests_info:
                    try:
                        # Get or create indexed file
                        indexed_file, _ = IndexedFile.objects.get_or_create(
                            path=test_info.file_path,
                            defaults={
                                'sha': 'unknown',
                                'mtime': 0,
                                'size': 0,
                                'language': 'python',
                                'is_test': True
                            }
                        )

                        # Save test case
                        TestCase.objects.update_or_create(
                            node_id=test_info.node_id,
                            defaults={
                                'file': indexed_file,
                                'class_name': test_info.class_name or '',
                                'method_name': test_info.method_name,
                                'markers': test_info.markers,
                                'covered_modules': test_info.dependencies,
                                'avg_execution_time': test_info.estimated_duration,
                                'success_rate': 1.0,  # Default
                            }
                        )
                        stats['tests'] += 1

                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                        print(f"Error saving test {test_info.node_id}: {e}")
                        stats['errors'] += 1

                # Save coverage information
                for coverage_info in self.coverage_info:
                    try:
                        # This is simplified - would need proper test-to-coverage mapping
                        pass  # Implementation would map coverage to specific tests

                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                        print(f"Error saving coverage info: {e}")
                        stats['errors'] += 1

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            print(f"Database transaction error: {e}")
            stats['errors'] += 1

        return stats


class TestFileExtractor(ast.NodeVisitor):
    """Extract test information from Python AST."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tests_info: List[TestInfo] = []
        self.fixtures_info: List[FixtureInfo] = []
        self.current_class = None

    def visit_ClassDef(self, node):
        """Visit test class definitions."""
        if self._is_test_class(node):
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = None
        else:
            self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Visit test function definitions."""
        if self._is_test_function(node):
            test_info = self._extract_test_info(node)
            self.tests_info.append(test_info)
        elif self._is_fixture_function(node):
            fixture_info = self._extract_fixture_info(node)
            self.fixtures_info.append(fixture_info)

        self.generic_visit(node)

    def _is_test_class(self, node: ast.ClassDef) -> bool:
        """Check if class is a test class."""
        # Check class name
        if node.name.startswith('Test'):
            return True

        # Check base classes
        for base in node.bases:
            base_name = ast.unparse(base) if hasattr(ast, 'unparse') else str(base)
            if 'TestCase' in base_name or 'Test' in base_name:
                return True

        return False

    def _is_test_function(self, node: ast.FunctionDef) -> bool:
        """Check if function is a test function."""
        return node.name.startswith('test_')

    def _is_fixture_function(self, node: ast.FunctionDef) -> bool:
        """Check if function is a pytest fixture."""
        for decorator in node.decorator_list:
            decorator_name = ast.unparse(decorator) if hasattr(ast, 'unparse') else str(decorator)
            if 'fixture' in decorator_name or 'pytest.fixture' in decorator_name:
                return True
        return False

    def _extract_test_info(self, node: ast.FunctionDef) -> TestInfo:
        """Extract information from test function."""
        # Build node ID
        if self.current_class:
            node_id = f"{self.file_path}::{self.current_class}::{node.name}"
        else:
            node_id = f"{self.file_path}::{node.name}"

        # Extract markers from decorators
        markers = []
        for decorator in node.decorator_list:
            decorator_name = ast.unparse(decorator) if hasattr(ast, 'unparse') else str(decorator)
            if 'pytest.mark' in decorator_name:
                marker = decorator_name.replace('pytest.mark.', '').split('(')[0]
                markers.append(marker)

        # Extract fixtures from parameters
        fixtures = []
        for arg in node.args.args:
            if arg.arg != 'self':  # Skip self parameter
                fixtures.append(arg.arg)

        # Classify test type
        test_type = self._classify_test_type(node, markers)

        # Estimate duration based on complexity
        estimated_duration = self._estimate_test_duration(node)

        return TestInfo(
            node_id=node_id,
            file_path=self.file_path,
            class_name=self.current_class,
            method_name=node.name,
            markers=markers,
            fixtures=fixtures,
            parametrize_values=[],  # Would need more complex analysis
            docstring=ast.get_docstring(node),
            line_number=node.lineno,
            test_type=test_type,
            estimated_duration=estimated_duration,
            dependencies=[],  # Would need import analysis
            tags=markers  # Use markers as tags for now
        )

    def _extract_fixture_info(self, node: ast.FunctionDef) -> FixtureInfo:
        """Extract pytest fixture information."""
        # Extract fixture parameters from decorator
        scope = 'function'  # Default
        autouse = False
        params = []

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                decorator_name = ast.unparse(decorator.func) if hasattr(ast, 'unparse') else str(decorator.func)
                if 'fixture' in decorator_name:
                    # Extract fixture parameters
                    for keyword in decorator.keywords:
                        if keyword.arg == 'scope':
                            scope = ast.literal_eval(keyword.value) if isinstance(keyword.value, ast.Constant) else 'function'
                        elif keyword.arg == 'autouse':
                            autouse = ast.literal_eval(keyword.value) if isinstance(keyword.value, ast.Constant) else False
                        elif keyword.arg == 'params':
                            # This would need more complex analysis
                            params = []

        # Extract fixture dependencies from parameters
        dependencies = []
        for arg in node.args.args:
            dependencies.append(arg.arg)

        return FixtureInfo(
            name=node.name,
            scope=scope,
            autouse=autouse,
            params=params,
            file_path=self.file_path,
            line_number=node.lineno,
            dependencies=dependencies
        )

    def _classify_test_type(self, node: ast.FunctionDef, markers: List[str]) -> str:
        """Classify test type based on markers and content."""
        # Check markers first
        if 'integration' in markers:
            return 'integration'
        elif 'e2e' in markers or 'end_to_end' in markers:
            return 'e2e'
        elif 'functional' in markers:
            return 'functional'
        elif 'unit' in markers:
            return 'unit'

        # Analyze test content for classification hints
        test_source = ast.unparse(node) if hasattr(ast, 'unparse') else str(node)

        # Look for integration test indicators
        integration_indicators = [
            'client.get',
            'client.post',
            'self.client',
            'api',
            'request',
            'response',
            'database',
            'db',
            'transaction'
        ]

        if any(indicator in test_source.lower() for indicator in integration_indicators):
            return 'integration'

        # Default to unit test
        return 'unit'

    def _estimate_test_duration(self, node: ast.FunctionDef) -> float:
        """Estimate test execution duration based on complexity."""
        # Simple heuristic based on function complexity
        complexity = 0

        # Count control flow statements
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try)):
                complexity += 1
            elif isinstance(child, ast.Call):
                complexity += 0.5

        # Base time + complexity factor
        base_time = 0.1  # 100ms base
        complexity_factor = complexity * 0.05  # 50ms per complexity point

        return base_time + complexity_factor