"""
Performance analyzer for N+1 query detection and optimization opportunities.

This analyzer provides:
- N+1 query detection: Missing select_related/prefetch_related
- Missing index detection: Slow query patterns
- Cache opportunity identification: Repeated computations
- Memory leak patterns: Circular references, unbounded caches
- Async opportunity detection: I/O-bound operations
"""

import ast
import re
from collections import defaultdict, Counter
from enum import Enum

from django.db import models


class PerformanceIssueType(Enum):
    """Types of performance issues."""
    N_PLUS_ONE_QUERY = "n_plus_one_query"
    MISSING_INDEX = "missing_index"
    MISSING_CACHE = "missing_cache"
    MEMORY_LEAK = "memory_leak"
    INEFFICIENT_LOOP = "inefficient_loop"
    ASYNC_OPPORTUNITY = "async_opportunity"
    LARGE_QUERYSET = "large_queryset"
    REPEATED_COMPUTATION = "repeated_computation"


class Severity(Enum):
    """Performance issue severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PerformanceIssue:
    """Container for performance issue information."""
    type: PerformanceIssueType
    severity: Severity
    description: str
    file_path: str
    line_number: int
    symbol_name: str
    suggestion: str
    code_snippet: Optional[str] = None
    estimated_impact: str = "unknown"
    fix_complexity: str = "medium"


@dataclass
class QueryPattern:
    """Container for query pattern analysis."""
    queryset_call: str
    model_name: str
    related_fields: List[str]
    filters: List[str]
    annotations: List[str]
    has_select_related: bool
    has_prefetch_related: bool
    in_loop: bool
    loop_depth: int


@dataclass
class CacheOpportunity:
    """Container for cache opportunity analysis."""
    computation_type: str
    description: str
    file_path: str
    line_number: int
    frequency_score: int
    cache_key_suggestion: str
    timeout_suggestion: int


class PerformanceAnalyzer:
    """Comprehensive performance analyzer for Django applications."""

    def __init__(self):
        self.query_patterns = []
        self.performance_issues = []
        self.cache_opportunities = []
        self.model_relationships = {}

    def analyze_performance(self, file_paths: List[str]) -> Dict[str, Any]:
        """Analyze performance issues in the given files."""
        try:
            # Build model relationship graph
            self._build_model_relationships()

            # Analyze each file
            for file_path in file_paths:
                self._analyze_file_performance(file_path)

            # Generate recommendations
            recommendations = self._generate_recommendations()

            return {
                'issues': [issue.__dict__ for issue in self.performance_issues],
                'cache_opportunities': [opp.__dict__ for opp in self.cache_opportunities],
                'recommendations': recommendations,
                'summary': self._generate_summary()
            }

        except (ValueError, TypeError) as e:
            print(f"Performance analysis failed: {e}")
            return {'error': str(e)}

    def _build_model_relationships(self):
        """Build a graph of Django model relationships."""
        try:
            models = DjangoModel.objects.all()

            for model in models:
                model_key = f"{model.app_label}.{model.model_name}"
                self.model_relationships[model_key] = {
                    'fields': model.fields,
                    'relationships': []
                }

                # Extract relationships from fields
                for field_name, field_info in model.fields.items():
                    field_type = field_info.get('type', '')

                    if field_type in ['ForeignKey', 'OneToOneField', 'ManyToManyField']:
                        # Extract related model from field info
                        related_model = self._extract_related_model(field_info)
                        if related_model:
                            self.model_relationships[model_key]['relationships'].append({
                                'field': field_name,
                                'type': field_type,
                                'related_model': related_model
                            })

        except (ValueError, TypeError) as e:
            print(f"Error building model relationships: {e}")

    def _extract_related_model(self, field_info: Dict[str, Any]) -> Optional[str]:
        """Extract related model name from field info."""
        # This would need more sophisticated parsing in practice
        # For now, we'll use a simplified approach
        return None  # Placeholder

    def _analyze_file_performance(self, file_path: str):
        """Analyze performance issues in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            # Extract performance-related patterns
            analyzer = FilePerformanceAnalyzer(file_path, content)
            analyzer.visit(tree)

            # Merge results
            self.query_patterns.extend(analyzer.query_patterns)
            self.performance_issues.extend(analyzer.performance_issues)
            self.cache_opportunities.extend(analyzer.cache_opportunities)

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Error analyzing file {file_path}: {e}")

    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate performance improvement recommendations."""
        recommendations = []

        # Group issues by type
        issue_groups = defaultdict(list)
        for issue in self.performance_issues:
            issue_groups[issue.type].append(issue)

        # Generate recommendations for each issue type
        for issue_type, issues in issue_groups.items():
            if issue_type == PerformanceIssueType.N_PLUS_ONE_QUERY:
                recommendations.extend(self._recommend_query_optimizations(issues))
            elif issue_type == PerformanceIssueType.MISSING_INDEX:
                recommendations.extend(self._recommend_database_indexes(issues))
            elif issue_type == PerformanceIssueType.MISSING_CACHE:
                recommendations.extend(self._recommend_caching_strategies(issues))

        return recommendations

    def _recommend_query_optimizations(self, issues: List[PerformanceIssue]) -> List[Dict[str, Any]]:
        """Generate query optimization recommendations."""
        recommendations = []

        for issue in issues:
            recommendations.append({
                'type': 'query_optimization',
                'priority': issue.severity.value,
                'title': f"Optimize query in {issue.file_path}:{issue.line_number}",
                'description': issue.description,
                'suggestion': issue.suggestion,
                'estimated_impact': 'High - Reduces database queries significantly',
                'implementation_steps': [
                    f"Add select_related() or prefetch_related() to the queryset",
                    f"Review the query pattern in {issue.symbol_name}",
                    f"Test the performance improvement"
                ]
            })

        return recommendations

    def _recommend_database_indexes(self, issues: List[PerformanceIssue]) -> List[Dict[str, Any]]:
        """Generate database index recommendations."""
        recommendations = []

        for issue in issues:
            recommendations.append({
                'type': 'database_index',
                'priority': issue.severity.value,
                'title': f"Add database index for {issue.symbol_name}",
                'description': issue.description,
                'suggestion': issue.suggestion,
                'estimated_impact': 'Medium - Improves query performance',
                'implementation_steps': [
                    f"Add db_index=True to the model field",
                    f"Create a migration",
                    f"Apply the migration to production"
                ]
            })

        return recommendations

    def _recommend_caching_strategies(self, issues: List[PerformanceIssue]) -> List[Dict[str, Any]]:
        """Generate caching strategy recommendations."""
        recommendations = []

        for issue in issues:
            recommendations.append({
                'type': 'caching_strategy',
                'priority': issue.severity.value,
                'title': f"Add caching for {issue.symbol_name}",
                'description': issue.description,
                'suggestion': issue.suggestion,
                'estimated_impact': 'Medium - Reduces computation time',
                'implementation_steps': [
                    f"Identify the cache key strategy",
                    f"Implement cache.get/set pattern",
                    f"Set appropriate cache timeout",
                    f"Handle cache invalidation"
                ]
            })

        return recommendations

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of performance analysis."""
        issue_counts = Counter(issue.type.value for issue in self.performance_issues)
        severity_counts = Counter(issue.severity.value for issue in self.performance_issues)

        return {
            'total_issues': len(self.performance_issues),
            'issue_breakdown': dict(issue_counts),
            'severity_breakdown': dict(severity_counts),
            'cache_opportunities': len(self.cache_opportunities),
            'most_common_issue': issue_counts.most_common(1)[0] if issue_counts else None,
            'critical_issues': len([i for i in self.performance_issues if i.severity == Severity.CRITICAL])
        }


class FilePerformanceAnalyzer(ast.NodeVisitor):
    """Analyze performance issues in a single file."""

    def __init__(self, file_path: str, content: str):
        self.file_path = file_path
        self.content = content
        self.lines = content.split('\n')

        self.query_patterns = []
        self.performance_issues = []
        self.cache_opportunities = []

        self.current_function = None
        self.loop_depth = 0
        self.in_loop = False

    def visit_FunctionDef(self, node):
        """Visit function definitions."""
        old_function = self.current_function
        self.current_function = node.name

        # Analyze function for performance issues
        self._analyze_function_performance(node)

        self.generic_visit(node)
        self.current_function = old_function

    def visit_For(self, node):
        """Visit for loops to detect N+1 queries."""
        self.loop_depth += 1
        old_in_loop = self.in_loop
        self.in_loop = True

        self.generic_visit(node)

        self.in_loop = old_in_loop
        self.loop_depth -= 1

    def visit_While(self, node):
        """Visit while loops."""
        self.loop_depth += 1
        old_in_loop = self.in_loop
        self.in_loop = True

        self.generic_visit(node)

        self.in_loop = old_in_loop
        self.loop_depth -= 1

    def visit_Call(self, node):
        """Visit function calls to detect query patterns."""
        # Analyze database query calls
        if self._is_query_call(node):
            self._analyze_query_call(node)

        # Analyze potential cache opportunities
        if self._is_computation_call(node):
            self._analyze_computation_call(node)

        self.generic_visit(node)

    def _analyze_function_performance(self, node: ast.FunctionDef):
        """Analyze function for performance issues."""
        # Check for large functions (potential performance issue)
        function_length = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 50

        if function_length > 100:
            self.performance_issues.append(PerformanceIssue(
                type=PerformanceIssueType.INEFFICIENT_LOOP,
                severity=Severity.MEDIUM,
                description=f"Large function ({function_length} lines) may have performance implications",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                suggestion="Consider breaking down into smaller functions",
                estimated_impact="Medium - Improves maintainability and potential performance"
            ))

        # Check for potential async opportunities
        if self._has_io_operations(node):
            self.performance_issues.append(PerformanceIssue(
                type=PerformanceIssueType.ASYNC_OPPORTUNITY,
                severity=Severity.LOW,
                description=f"Function {node.name} contains I/O operations that could benefit from async",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=node.name,
                suggestion="Consider using async/await for I/O operations",
                estimated_impact="Medium - Improves concurrency"
            ))

    def _is_query_call(self, node: ast.Call) -> bool:
        """Check if call is a database query."""
        call_str = ast.unparse(node) if hasattr(ast, 'unparse') else str(node)

        query_patterns = [
            '.objects.', '.filter(', '.get(', '.all(', '.exclude(',
            '.select_related(', '.prefetch_related(', '.annotate('
        ]

        return any(pattern in call_str for pattern in query_patterns)

    def _analyze_query_call(self, node: ast.Call):
        """Analyze a database query call."""
        call_str = ast.unparse(node) if hasattr(ast, 'unparse') else str(node)

        # Check for N+1 query patterns
        if self.in_loop and ('.objects.' in call_str or '.get(' in call_str):
            # Check if select_related or prefetch_related is used
            has_select_related = 'select_related' in call_str
            has_prefetch_related = 'prefetch_related' in call_str

            if not has_select_related and not has_prefetch_related:
                self.performance_issues.append(PerformanceIssue(
                    type=PerformanceIssueType.N_PLUS_ONE_QUERY,
                    severity=Severity.HIGH,
                    description=f"Potential N+1 query detected in loop (depth: {self.loop_depth})",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    symbol_name=self.current_function or "unknown",
                    suggestion="Add select_related() or prefetch_related() to optimize the query",
                    code_snippet=self._get_line(node.lineno),
                    estimated_impact="High - Can reduce database queries from N+1 to 2",
                    fix_complexity="easy"
                ))

        # Check for missing index opportunities
        if '.filter(' in call_str:
            self._analyze_filter_for_index(node, call_str)

        # Check for large queryset operations
        if '.all()' in call_str and self.in_loop:
            self.performance_issues.append(PerformanceIssue(
                type=PerformanceIssueType.LARGE_QUERYSET,
                severity=Severity.MEDIUM,
                description="Using .all() in a loop may load large datasets",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=self.current_function or "unknown",
                suggestion="Consider pagination or specific filtering",
                code_snippet=self._get_line(node.lineno),
                estimated_impact="Medium - Reduces memory usage"
            ))

    def _analyze_filter_for_index(self, node: ast.Call, call_str: str):
        """Analyze filter calls for missing index opportunities."""
        # Extract filter fields (simplified)
        filter_match = re.search(r'\.filter\(([^)]+)\)', call_str)
        if filter_match:
            filter_args = filter_match.group(1)

            # Look for common patterns that benefit from indexes
            if '=' in filter_args and '__icontains' not in filter_args:
                self.performance_issues.append(PerformanceIssue(
                    type=PerformanceIssueType.MISSING_INDEX,
                    severity=Severity.MEDIUM,
                    description=f"Filter operation may benefit from database index",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    symbol_name=self.current_function or "unknown",
                    suggestion=f"Consider adding db_index=True to the filtered field",
                    code_snippet=self._get_line(node.lineno),
                    estimated_impact="Medium - Improves query performance"
                ))

    def _is_computation_call(self, node: ast.Call) -> bool:
        """Check if call involves expensive computation."""
        call_str = ast.unparse(node) if hasattr(ast, 'unparse') else str(node)

        expensive_patterns = [
            'sum(', 'max(', 'min(', 'len(',
            '.aggregate(', '.count()',
            'json.loads(', 'json.dumps(',
            're.search(', 're.findall('
        ]

        return any(pattern in call_str for pattern in expensive_patterns)

    def _analyze_computation_call(self, node: ast.Call):
        """Analyze expensive computation calls for cache opportunities."""
        call_str = ast.unparse(node) if hasattr(ast, 'unparse') else str(node)

        # Check if this computation is repeated
        if self.in_loop or self._is_in_frequently_called_function():
            self.cache_opportunities.append(CacheOpportunity(
                computation_type="expensive_computation",
                description=f"Expensive computation in loop or frequent function: {call_str[:50]}",
                file_path=self.file_path,
                line_number=node.lineno,
                frequency_score=self.loop_depth + (2 if self._is_in_frequently_called_function() else 0),
                cache_key_suggestion=f"cache_key_for_{self.current_function}_{node.lineno}",
                timeout_suggestion=300  # 5 minutes default
            ))

    def _has_io_operations(self, node: ast.FunctionDef) -> bool:
        """Check if function has I/O operations."""
        function_str = ast.unparse(node) if hasattr(ast, 'unparse') else str(node)

        io_patterns = [
            'requests.', 'urllib.', 'http',
            'open(', 'read(', 'write(',
            'json.loads', 'json.dumps',
            '.save(', '.create(', '.update(',
            'send_email', 'mail.'
        ]

        return any(pattern in function_str for pattern in io_patterns)

    def _is_in_frequently_called_function(self) -> bool:
        """Check if current function is likely to be called frequently."""
        if not self.current_function:
            return False

        frequent_patterns = [
            'get_', 'list_', 'search_', 'filter_',
            'process_', 'handle_', 'view_',
            '__str__', '__repr__'
        ]

        return any(pattern in self.current_function for pattern in frequent_patterns)

    def _get_line(self, line_number: int) -> str:
        """Get source code line by number."""
        try:
            if 1 <= line_number <= len(self.lines):
                return self.lines[line_number - 1].strip()
        except:
            pass
        return ""