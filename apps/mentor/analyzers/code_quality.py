"""
Code quality analyzer with Django anti-patterns detection.

This analyzer provides:
- Django anti-patterns: Fat models, signal abuse
- Complexity metrics: Maintainability index
- Dead code detection: Unused imports, functions
- Duplicate code: Similar patterns across files
- Convention violations: PEP8, Django style guide
"""

import ast
import re
from collections import defaultdict, Counter
from difflib import SequenceMatcher
from enum import Enum



class QualityIssueType(Enum):
    """Types of code quality issues."""
    DJANGO_ANTI_PATTERN = "django_anti_pattern"
    HIGH_COMPLEXITY = "high_complexity"
    DEAD_CODE = "dead_code"
    DUPLICATE_CODE = "duplicate_code"
    NAMING_VIOLATION = "naming_violation"
    LONG_METHOD = "long_method"
    LARGE_CLASS = "large_class"
    TOO_MANY_PARAMETERS = "too_many_parameters"
    MAGIC_NUMBER = "magic_number"
    MISSING_DOCSTRING = "missing_docstring"
    IMPORT_VIOLATION = "import_violation"
    DESIGN_VIOLATION = "design_violation"


class QualitySeverity(Enum):
    """Code quality issue severity levels."""
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


@dataclass
class QualityIssue:
    """Container for code quality issue information."""
    type: QualityIssueType
    severity: QualitySeverity
    description: str
    file_path: str
    line_number: int
    symbol_name: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    suggestion: str = ""
    example: str = ""


@dataclass
class ComplexityMetric:
    """Container for complexity metrics."""
    cyclomatic_complexity: int
    cognitive_complexity: int
    maintainability_index: float
    lines_of_code: int
    halstead_volume: float


@dataclass
class DuplicateCodeBlock:
    """Container for duplicate code information."""
    file1: str
    file2: str
    line1: int
    line2: int
    similarity: float
    code_block: str
    size: int


class CodeQualityAnalyzer:
    """Comprehensive code quality analyzer for Django applications."""

    def __init__(self):
        self.quality_issues = []
        self.complexity_metrics = {}
        self.duplicate_blocks = []
        self.django_patterns = {}

    def analyze_code_quality(self, file_paths: List[str]) -> Dict[str, Any]:
        """Analyze code quality issues in the given files."""
        try:
            # Analyze each file
            for file_path in file_paths:
                if file_path.endswith('.py'):
                    self._analyze_file_quality(file_path)

            # Detect Django anti-patterns
            self._analyze_django_patterns()

            # Detect duplicate code
            self._detect_duplicate_code(file_paths)

            # Generate quality report
            report = self._generate_quality_report()

            return report

        except (AttributeError, TypeError, ValueError) as e:
            print(f"Code quality analysis failed: {e}")
            return {'error': str(e)}

    def _analyze_file_quality(self, file_path: str):
        """Analyze code quality issues in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            # Analyze with visitor
            analyzer = FileQualityAnalyzer(file_path, content)
            analyzer.visit(tree)

            # Merge results
            self.quality_issues.extend(analyzer.quality_issues)
            if analyzer.complexity_metrics:
                self.complexity_metrics[file_path] = analyzer.complexity_metrics

        except (AttributeError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError) as e:
            print(f"Error analyzing file {file_path}: {e}")

    def _analyze_django_patterns(self):
        """Analyze Django-specific patterns and anti-patterns."""
        try:
            # Analyze Django models for anti-patterns
            models = DjangoModel.objects.all()

            for model in models:
                self._check_fat_model(model)
                self._check_model_patterns(model)

        except (AttributeError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError) as e:
            print(f"Error analyzing Django patterns: {e}")

    def _check_fat_model(self, model: DjangoModel):
        """Check for fat model anti-pattern."""
        try:
            # Get model file
            model_file = model.file

            # Count methods in model
            model_symbols = CodeSymbol.objects.filter(
                file=model_file,
                parents__contains=[model.model_name],
                kind='method'
            )

            method_count = model_symbols.count()
            total_complexity = sum(symbol.complexity for symbol in model_symbols)

            # Check for fat model indicators
            if method_count > 15:
                self.quality_issues.append(QualityIssue(
                    type=QualityIssueType.DJANGO_ANTI_PATTERN,
                    severity=QualitySeverity.MAJOR,
                    description=f"Fat model detected: {model.model_name} has {method_count} methods",
                    file_path=model.file.path,
                    line_number=model.line_number,
                    symbol_name=model.model_name,
                    metric_value=method_count,
                    threshold=15,
                    suggestion="Consider extracting business logic to services or managers"
                ))

            if total_complexity > 50:
                self.quality_issues.append(QualityIssue(
                    type=QualityIssueType.HIGH_COMPLEXITY,
                    severity=QualitySeverity.MAJOR,
                    description=f"High complexity model: {model.model_name} complexity={total_complexity}",
                    file_path=model.file.path,
                    line_number=model.line_number,
                    symbol_name=model.model_name,
                    metric_value=total_complexity,
                    threshold=50,
                    suggestion="Refactor complex methods into smaller functions"
                ))

        except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValueError) as e:
            print(f"Error checking fat model {model.model_name}: {e}")

    def _check_model_patterns(self, model: DjangoModel):
        """Check for Django model anti-patterns."""
        # Check for missing __str__ method
        has_str_method = CodeSymbol.objects.filter(
            file=model.file,
            parents__contains=[model.model_name],
            name='__str__'
        ).exists()

        if not has_str_method:
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.DJANGO_ANTI_PATTERN,
                severity=QualitySeverity.MINOR,
                description=f"Model {model.model_name} missing __str__ method",
                file_path=model.file.path,
                line_number=model.line_number,
                symbol_name=model.model_name,
                suggestion="Add __str__ method for better representation"
            ))

        # Check for too many fields
        field_count = len(model.fields)
        if field_count > 20:
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.DJANGO_ANTI_PATTERN,
                severity=QualitySeverity.MAJOR,
                description=f"Model {model.model_name} has too many fields ({field_count})",
                file_path=model.file.path,
                line_number=model.line_number,
                symbol_name=model.model_name,
                metric_value=field_count,
                threshold=20,
                suggestion="Consider splitting into multiple related models"
            ))

    def _detect_duplicate_code(self, file_paths: List[str]):
        """Detect duplicate code across files."""
        try:
            # Read all files
            file_contents = {}
            for file_path in file_paths:
                if file_path.endswith('.py'):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_contents[file_path] = f.read()
                    except (FileNotFoundError, IOError, OSError, PermissionError):
                        continue

            # Compare files pairwise
            files = list(file_contents.keys())
            for i in range(len(files)):
                for j in range(i + 1, len(files)):
                    file1, file2 = files[i], files[j]
                    duplicates = self._find_duplicates_between_files(
                        file1, file_contents[file1],
                        file2, file_contents[file2]
                    )
                    self.duplicate_blocks.extend(duplicates)

        except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValueError) as e:
            print(f"Error detecting duplicate code: {e}")

    def _find_duplicates_between_files(self, file1: str, content1: str,
                                     file2: str, content2: str) -> List[DuplicateCodeBlock]:
        """Find duplicate code blocks between two files."""
        duplicates = []

        lines1 = content1.split('\n')
        lines2 = content2.split('\n')

        # Use sliding window approach to find similar blocks
        min_block_size = 5  # Minimum 5 lines to consider duplicate

        for i in range(len(lines1) - min_block_size + 1):
            block1 = '\n'.join(lines1[i:i + min_block_size])

            for j in range(len(lines2) - min_block_size + 1):
                block2 = '\n'.join(lines2[j:j + min_block_size])

                # Calculate similarity
                similarity = SequenceMatcher(None, block1, block2).ratio()

                if similarity > 0.8:  # 80% similarity threshold
                    # Extend the block to find the full duplicate
                    extended_size = min_block_size
                    while (i + extended_size < len(lines1) and
                           j + extended_size < len(lines2)):
                        extended_block1 = '\n'.join(lines1[i:i + extended_size + 1])
                        extended_block2 = '\n'.join(lines2[j:j + extended_size + 1])

                        extended_similarity = SequenceMatcher(None, extended_block1, extended_block2).ratio()

                        if extended_similarity > 0.8:
                            extended_size += 1
                        else:
                            break

                    duplicate = DuplicateCodeBlock(
                        file1=file1,
                        file2=file2,
                        line1=i + 1,
                        line2=j + 1,
                        similarity=similarity,
                        code_block=block1,
                        size=extended_size
                    )
                    duplicates.append(duplicate)

        return duplicates

    def _generate_quality_report(self) -> Dict[str, Any]:
        """Generate comprehensive quality report."""
        # Group issues by type and severity
        issues_by_type = defaultdict(list)
        issues_by_severity = defaultdict(list)

        for issue in self.quality_issues:
            issues_by_type[issue.type.value].append(issue.__dict__)
            issues_by_severity[issue.severity.value].append(issue.__dict__)

        # Calculate quality metrics
        quality_score = self._calculate_quality_score()
        maintainability_score = self._calculate_maintainability_score()

        # Generate recommendations
        recommendations = self._generate_quality_recommendations()

        return {
            'total_issues': len(self.quality_issues),
            'quality_score': quality_score,
            'maintainability_score': maintainability_score,
            'issues_by_type': dict(issues_by_type),
            'issues_by_severity': dict(issues_by_severity),
            'complexity_metrics': self.complexity_metrics,
            'duplicate_blocks': [block.__dict__ for block in self.duplicate_blocks],
            'recommendations': recommendations,
            'summary': {
                'critical': len(issues_by_severity[QualitySeverity.CRITICAL.value]),
                'major': len(issues_by_severity[QualitySeverity.MAJOR.value]),
                'minor': len(issues_by_severity[QualitySeverity.MINOR.value]),
                'info': len(issues_by_severity[QualitySeverity.INFO.value]),
                'duplicate_code_blocks': len(self.duplicate_blocks),
                'files_analyzed': len(self.complexity_metrics)
            }
        }

    def _calculate_quality_score(self) -> float:
        """Calculate overall quality score (0-100)."""
        if not self.quality_issues:
            return 100.0

        # Weight issues by severity
        severity_weights = {
            QualitySeverity.CRITICAL: 20,
            QualitySeverity.MAJOR: 10,
            QualitySeverity.MINOR: 5,
            QualitySeverity.INFO: 1
        }

        total_penalty = sum(severity_weights.get(issue.severity, 0) for issue in self.quality_issues)
        max_score = 100.0

        return max(max_score - total_penalty, 0.0)

    def _calculate_maintainability_score(self) -> float:
        """Calculate maintainability score based on complexity metrics."""
        if not self.complexity_metrics:
            return 75.0  # Default score

        maintainability_scores = []

        for file_path, metrics in self.complexity_metrics.items():
            if isinstance(metrics, ComplexityMetric):
                # Use maintainability index if available
                score = metrics.maintainability_index
                maintainability_scores.append(score)

        return sum(maintainability_scores) / len(maintainability_scores) if maintainability_scores else 75.0

    def _generate_quality_recommendations(self) -> List[Dict[str, Any]]:
        """Generate quality improvement recommendations."""
        recommendations = []

        # Group issues for recommendations
        issue_counts = Counter(issue.type for issue in self.quality_issues)

        # Django-specific recommendations
        if issue_counts[QualityIssueType.DJANGO_ANTI_PATTERN] > 0:
            recommendations.append({
                'category': 'Django Best Practices',
                'priority': 'HIGH',
                'title': 'Address Django Anti-Patterns',
                'description': f"Found {issue_counts[QualityIssueType.DJANGO_ANTI_PATTERN]} Django anti-patterns",
                'actions': [
                    'Extract business logic from fat models',
                    'Use Django managers and querysets effectively',
                    'Implement proper model methods',
                    'Follow Django naming conventions'
                ]
            })

        # Complexity recommendations
        if issue_counts[QualityIssueType.HIGH_COMPLEXITY] > 0:
            recommendations.append({
                'category': 'Code Complexity',
                'priority': 'MEDIUM',
                'title': 'Reduce Code Complexity',
                'description': f"Found {issue_counts[QualityIssueType.HIGH_COMPLEXITY]} high complexity issues",
                'actions': [
                    'Break down complex functions into smaller ones',
                    'Reduce cyclomatic complexity',
                    'Simplify conditional logic',
                    'Use design patterns to improve structure'
                ]
            })

        # Duplicate code recommendations
        if len(self.duplicate_blocks) > 0:
            recommendations.append({
                'category': 'Code Duplication',
                'priority': 'MEDIUM',
                'title': 'Eliminate Code Duplication',
                'description': f"Found {len(self.duplicate_blocks)} duplicate code blocks",
                'actions': [
                    'Extract common code into functions',
                    'Create utility modules for shared logic',
                    'Use inheritance or composition patterns',
                    'Implement DRY (Don\'t Repeat Yourself) principle'
                ]
            })

        # Dead code recommendations
        if issue_counts[QualityIssueType.DEAD_CODE] > 0:
            recommendations.append({
                'category': 'Dead Code',
                'priority': 'LOW',
                'title': 'Remove Dead Code',
                'description': f"Found {issue_counts[QualityIssueType.DEAD_CODE]} dead code issues",
                'actions': [
                    'Remove unused imports',
                    'Delete unused functions and classes',
                    'Clean up commented code',
                    'Use code coverage tools to identify unused code'
                ]
            })

        return recommendations


class FileQualityAnalyzer(ast.NodeVisitor):
    """Analyze code quality issues in a single file."""

    def __init__(self, file_path: str, content: str):
        self.file_path = file_path
        self.content = content
        self.lines = content.split('\n')
        self.quality_issues = []
        self.complexity_metrics = None

        # Analysis state
        self.current_class = None
        self.current_function = None
        self.imports = set()
        self.used_names = set()

    def visit_Import(self, node):
        """Track imports."""
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Track from imports."""
        if node.module:
            for alias in node.names:
                imported_name = alias.name
                self.imports.add(f"{node.module}.{imported_name}")
        self.generic_visit(node)

    def visit_Name(self, node):
        """Track name usage."""
        self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Analyze class definitions."""
        old_class = self.current_class
        self.current_class = node.name

        # Check class size
        class_length = (node.end_lineno or node.lineno) - node.lineno

        if class_length > 200:
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.LARGE_CLASS,
                severity=QualitySeverity.MAJOR,
                description=f"Large class '{node.name}' ({class_length} lines)",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                metric_value=class_length,
                threshold=200,
                suggestion="Consider breaking down into smaller classes"
            ))

        # Check for missing docstring
        if not ast.get_docstring(node):
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.MISSING_DOCSTRING,
                severity=QualitySeverity.MINOR,
                description=f"Class '{node.name}' missing docstring",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                suggestion="Add class docstring to explain purpose"
            ))

        # Check naming convention
        if not self._is_valid_class_name(node.name):
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.NAMING_VIOLATION,
                severity=QualitySeverity.MINOR,
                description=f"Class '{node.name}' doesn't follow PascalCase convention",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                suggestion="Use PascalCase for class names"
            ))

        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        """Analyze function definitions."""
        old_function = self.current_function
        self.current_function = node.name

        # Calculate complexity
        complexity = self._calculate_cyclomatic_complexity(node)

        # Check function length
        func_length = (node.end_lineno or node.lineno) - node.lineno

        if func_length > 50:
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.LONG_METHOD,
                severity=QualitySeverity.MAJOR,
                description=f"Long method '{node.name}' ({func_length} lines)",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                metric_value=func_length,
                threshold=50,
                suggestion="Break down into smaller functions"
            ))

        # Check cyclomatic complexity
        if complexity > 10:
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.HIGH_COMPLEXITY,
                severity=QualitySeverity.MAJOR,
                description=f"High complexity function '{node.name}' (complexity={complexity})",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                metric_value=complexity,
                threshold=10,
                suggestion="Reduce complexity by simplifying logic"
            ))

        # Check parameter count
        param_count = len(node.args.args)
        if param_count > 7:
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.TOO_MANY_PARAMETERS,
                severity=QualitySeverity.MINOR,
                description=f"Too many parameters in '{node.name}' ({param_count})",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                metric_value=param_count,
                threshold=7,
                suggestion="Consider using parameter objects or reducing parameters"
            ))

        # Check for missing docstring
        if not ast.get_docstring(node) and not node.name.startswith('_'):
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.MISSING_DOCSTRING,
                severity=QualitySeverity.MINOR,
                description=f"Function '{node.name}' missing docstring",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                suggestion="Add function docstring to explain purpose and parameters"
            ))

        # Check naming convention
        if not self._is_valid_function_name(node.name):
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.NAMING_VIOLATION,
                severity=QualitySeverity.MINOR,
                description=f"Function '{node.name}' doesn't follow snake_case convention",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                suggestion="Use snake_case for function names"
            ))

        self.generic_visit(node)
        self.current_function = old_function

    def visit_Num(self, node):
        """Check for magic numbers."""
        # Skip common acceptable numbers
        acceptable_numbers = {0, 1, 2, 10, 100, 1000}

        if hasattr(node, 'n') and node.n not in acceptable_numbers:
            self.quality_issues.append(QualityIssue(
                type=QualityIssueType.MAGIC_NUMBER,
                severity=QualitySeverity.MINOR,
                description=f"Magic number {node.n} found",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=str(node.n),
                suggestion="Replace magic numbers with named constants"
            ))

        self.generic_visit(node)

    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity

    def _is_valid_class_name(self, name: str) -> bool:
        """Check if class name follows PascalCase convention."""
        return re.match(r'^[A-Z][a-zA-Z0-9]*$', name) is not None

    def _is_valid_function_name(self, name: str) -> bool:
        """Check if function name follows snake_case convention."""
        return re.match(r'^[a-z_][a-z0-9_]*$', name) is not None

    def analyze_unused_imports(self):
        """Find unused imports."""
        for import_name in self.imports:
            # Simple heuristic - check if import name appears in used names
            base_name = import_name.split('.')[-1]
            if base_name not in self.used_names:
                self.quality_issues.append(QualityIssue(
                    type=QualityIssueType.DEAD_CODE,
                    severity=QualitySeverity.MINOR,
                    description=f"Unused import: {import_name}",
                    file_path=self.file_path,
                    line_number=1,  # Approximation
                    symbol_name=import_name,
                    suggestion="Remove unused import"
                ))