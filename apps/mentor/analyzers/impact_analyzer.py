"""
Impact analyzer for comprehensive change propagation analysis.

This analyzer provides:
- Change propagation: Track effects through dependency graph
- Breaking change detection: API contract analysis
- Migration requirements: Model field changes
- Test coverage gaps: Identify untested changes
- URL route impacts: Endpoint modification tracking
"""

from collections import defaultdict, deque
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

    IndexedFile, CodeSymbol, SymbolRelation, DjangoURL,
    DjangoModel, TestCase, TestCoverage
)


class ImpactSeverity(Enum):
    """Impact severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeType(Enum):
    """Types of code changes."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class ImpactResult:
    """Container for impact analysis results."""
    affected_files: Set[str]
    affected_symbols: Set[str]
    affected_tests: Set[str]
    affected_urls: Set[str]
    breaking_changes: List[Dict[str, Any]]
    migration_required: bool
    migration_suggestions: List[str]
    test_coverage_gaps: List[str]
    severity: ImpactSeverity
    confidence: float


@dataclass
class BreakingChange:
    """Container for breaking change information."""
    type: str  # 'api_change', 'model_field', 'url_change', 'interface_change'
    description: str
    file_path: str
    symbol_name: str
    severity: ImpactSeverity
    migration_path: Optional[str] = None
    backwards_compatible: bool = False


@dataclass
class DependencyChain:
    """Container for dependency chain information."""
    source: str
    target: str
    path: List[str]
    depth: int
    impact_weight: float


class ImpactAnalyzer:
    """Comprehensive impact analyzer for code changes."""

    def __init__(self):
        self.dependency_graph = {}
        self.reverse_dependency_graph = {}
        self.symbol_usage_map = {}
        self.test_coverage_map = {}

    def analyze_changes(self, changed_files: List[str],
                       change_type: ChangeType = ChangeType.MODIFIED) -> ImpactResult:
        """Analyze the impact of changes to specified files."""
        try:
            # Build dependency graphs
            self._build_dependency_graphs()

            # Find all affected components
            affected_files = set(changed_files)
            affected_symbols = set()
            affected_tests = set()
            affected_urls = set()

            # Propagate changes through dependency graph
            self._propagate_file_changes(changed_files, affected_files, affected_symbols)

            # Analyze symbol changes
            for file_path in changed_files:
                file_symbols = self._get_file_symbols(file_path)
                for symbol in file_symbols:
                    symbol_impacts = self._analyze_symbol_impact(symbol, change_type)
                    affected_symbols.update(symbol_impacts['symbols'])
                    affected_tests.update(symbol_impacts['tests'])
                    affected_urls.update(symbol_impacts['urls'])

            # Detect breaking changes
            breaking_changes = self._detect_breaking_changes(changed_files, change_type)

            # Check migration requirements
            migration_required, migration_suggestions = self._check_migration_requirements(changed_files)

            # Find test coverage gaps
            test_coverage_gaps = self._find_test_coverage_gaps(affected_files, affected_symbols)

            # Calculate overall severity and confidence
            severity = self._calculate_severity(
                len(affected_files),
                len(breaking_changes),
                migration_required
            )
            confidence = self._calculate_confidence(affected_files, affected_symbols)

            return ImpactResult(
                affected_files=affected_files,
                affected_symbols=affected_symbols,
                affected_tests=affected_tests,
                affected_urls=affected_urls,
                breaking_changes=[bc.__dict__ for bc in breaking_changes],
                migration_required=migration_required,
                migration_suggestions=migration_suggestions,
                test_coverage_gaps=test_coverage_gaps,
                severity=severity,
                confidence=confidence
            )

        except (DatabaseError, IntegrityError) as e:
            print(f"Impact analysis failed: {e}")
            return ImpactResult(
                affected_files=set(changed_files),
                affected_symbols=set(),
                affected_tests=set(),
                affected_urls=set(),
                breaking_changes=[],
                migration_required=False,
                migration_suggestions=[],
                test_coverage_gaps=[],
                severity=ImpactSeverity.LOW,
                confidence=0.0
            )

    def _build_dependency_graphs(self):
        """Build dependency graphs from symbol relations."""
        self.dependency_graph = defaultdict(set)
        self.reverse_dependency_graph = defaultdict(set)

        # Build from symbol relations
        relations = SymbolRelation.objects.select_related(
            'source__file', 'target__file'
        ).all()

        for relation in relations:
            source_file = relation.source.file.path
            target_file = relation.target.file.path
            source_symbol = f"{source_file}::{relation.source.name}"
            target_symbol = f"{target_file}::{relation.target.name}"

            # File-level dependencies
            if source_file != target_file:
                self.dependency_graph[source_file].add(target_file)
                self.reverse_dependency_graph[target_file].add(source_file)

            # Symbol-level dependencies
            self.dependency_graph[source_symbol].add(target_symbol)
            self.reverse_dependency_graph[target_symbol].add(source_symbol)

        # Build symbol usage map
        for symbol in CodeSymbol.objects.select_related('file').all():
            symbol_key = f"{symbol.file.path}::{symbol.name}"
            self.symbol_usage_map[symbol_key] = {
                'type': symbol.kind,
                'file': symbol.file.path,
                'complexity': symbol.complexity,
                'decorators': symbol.decorators,
            }

    def _propagate_file_changes(self, changed_files: List[str],
                               affected_files: Set[str],
                               affected_symbols: Set[str]):
        """Propagate changes through the dependency graph."""
        to_process = deque(changed_files)
        processed = set()

        while to_process:
            current_file = to_process.popleft()

            if current_file in processed:
                continue

            processed.add(current_file)
            affected_files.add(current_file)

            # Add file symbols to affected symbols
            file_symbols = self._get_file_symbols(current_file)
            affected_symbols.update(file_symbols)

            # Find files that depend on this file
            if current_file in self.reverse_dependency_graph:
                for dependent_file in self.reverse_dependency_graph[current_file]:
                    if dependent_file not in processed:
                        to_process.append(dependent_file)
                        affected_files.add(dependent_file)

    def _get_file_symbols(self, file_path: str) -> List[str]:
        """Get all symbols defined in a file."""
        symbols = []
        try:
            file_obj = IndexedFile.objects.get(path=file_path)
            for symbol in file_obj.symbols.all():
                symbols.append(f"{file_path}::{symbol.name}")
        except IndexedFile.DoesNotExist:
            pass
        return symbols

    def _analyze_symbol_impact(self, symbol_key: str, change_type: ChangeType) -> Dict[str, Set[str]]:
        """Analyze the impact of changes to a specific symbol."""
        impact = {
            'symbols': set(),
            'tests': set(),
            'urls': set()
        }

        # Find symbols that depend on this one
        if symbol_key in self.reverse_dependency_graph:
            for dependent_symbol in self.reverse_dependency_graph[symbol_key]:
                impact['symbols'].add(dependent_symbol)

                # Check if dependent symbol is in a test file
                if self._is_test_symbol(dependent_symbol):
                    impact['tests'].add(dependent_symbol)

        # Find URLs that might be affected
        symbol_name = symbol_key.split('::')[-1]
        if self._is_view_symbol(symbol_key):
            affected_urls = self._find_urls_for_view(symbol_name)
            impact['urls'].update(affected_urls)

        return impact

    def _is_test_symbol(self, symbol_key: str) -> bool:
        """Check if symbol is in a test file."""
        file_path = symbol_key.split('::')[0]
        return any(test_indicator in file_path.lower()
                  for test_indicator in ['test_', '/tests/', '_test.'])

    def _is_view_symbol(self, symbol_key: str) -> bool:
        """Check if symbol is a Django view."""
        if symbol_key in self.symbol_usage_map:
            symbol_info = self.symbol_usage_map[symbol_key]
            # Check for view-related decorators or patterns
            decorators = symbol_info.get('decorators', [])
            return any('login_required' in dec or 'require_' in dec
                      for dec in decorators)
        return False

    def _find_urls_for_view(self, view_name: str) -> List[str]:
        """Find URLs that reference a specific view."""
        urls = []
        try:
            django_urls = DjangoURL.objects.filter(view_name__icontains=view_name)
            for url in django_urls:
                urls.append(url.route)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist):
            pass
        return urls

    def _detect_breaking_changes(self, changed_files: List[str],
                                change_type: ChangeType) -> List[BreakingChange]:
        """Detect potential breaking changes."""
        breaking_changes = []

        for file_path in changed_files:
            # Check for model changes
            model_breaking_changes = self._detect_model_breaking_changes(file_path, change_type)
            breaking_changes.extend(model_breaking_changes)

            # Check for API changes
            api_breaking_changes = self._detect_api_breaking_changes(file_path, change_type)
            breaking_changes.extend(api_breaking_changes)

            # Check for URL changes
            url_breaking_changes = self._detect_url_breaking_changes(file_path, change_type)
            breaking_changes.extend(url_breaking_changes)

        return breaking_changes

    def _detect_model_breaking_changes(self, file_path: str,
                                     change_type: ChangeType) -> List[BreakingChange]:
        """Detect breaking changes in Django models."""
        breaking_changes = []

        if '/models.py' in file_path or '/models/' in file_path:
            try:
                # Get models in this file
                models_in_file = DjangoModel.objects.filter(file__path=file_path)

                for model in models_in_file:
                    # Check for potentially breaking field changes
                    breaking_fields = self._analyze_model_field_changes(model)
                    for field_name, issue in breaking_fields.items():
                        breaking_changes.append(BreakingChange(
                            type='model_field',
                            description=f"Model {model.model_name}.{field_name}: {issue}",
                            file_path=file_path,
                            symbol_name=f"{model.model_name}.{field_name}",
                            severity=ImpactSeverity.HIGH,
                            migration_path=f"Create migration for {model.model_name}",
                            backwards_compatible=False
                        ))

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                print(f"Error analyzing model breaking changes: {e}")

        return breaking_changes

    def _analyze_model_field_changes(self, model: DjangoModel) -> Dict[str, str]:
        """Analyze model field changes for breaking changes."""
        issues = {}

        for field_name, field_info in model.fields.items():
            # Check for potentially breaking field changes
            if not field_info.get('null', True) and not field_info.get('default'):
                if field_info.get('type') in ['ForeignKey', 'OneToOneField']:
                    issues[field_name] = "Non-nullable foreign key without default"
                elif field_info.get('unique', False):
                    issues[field_name] = "Unique field without default"

        return issues

    def _detect_api_breaking_changes(self, file_path: str,
                                   change_type: ChangeType) -> List[BreakingChange]:
        """Detect breaking changes in API endpoints."""
        breaking_changes = []

        if '/views.py' in file_path or '/api/' in file_path:
            # Analyze view functions/classes for breaking changes
            try:
                file_obj = IndexedFile.objects.get(path=file_path)

                for symbol in file_obj.symbols.filter(kind__in=['function', 'method']):
                    if self._is_api_endpoint(symbol):
                        # Check for potential breaking changes
                        if change_type == ChangeType.DELETED:
                            breaking_changes.append(BreakingChange(
                                type='api_change',
                                description=f"API endpoint {symbol.name} deleted",
                                file_path=file_path,
                                symbol_name=symbol.name,
                                severity=ImpactSeverity.CRITICAL,
                                backwards_compatible=False
                            ))

            except IndexedFile.DoesNotExist:
                pass
            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                print(f"Error analyzing API breaking changes: {e}")

        return breaking_changes

    def _is_api_endpoint(self, symbol: CodeSymbol) -> bool:
        """Check if symbol is an API endpoint."""
        # Check for API-related decorators
        api_decorators = [
            'api_view', 'require_http_methods', 'require_GET', 'require_POST'
        ]
        return any(api_dec in ' '.join(symbol.decorators) for api_dec in api_decorators)

    def _detect_url_breaking_changes(self, file_path: str,
                                   change_type: ChangeType) -> List[BreakingChange]:
        """Detect breaking changes in URL patterns."""
        breaking_changes = []

        if '/urls.py' in file_path:
            try:
                urls_in_file = DjangoURL.objects.filter(file__path=file_path)

                for url in urls_in_file:
                    if change_type == ChangeType.DELETED:
                        breaking_changes.append(BreakingChange(
                            type='url_change',
                            description=f"URL pattern {url.route} deleted",
                            file_path=file_path,
                            symbol_name=url.route,
                            severity=ImpactSeverity.HIGH,
                            backwards_compatible=False
                        ))

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                print(f"Error analyzing URL breaking changes: {e}")

        return breaking_changes

    def _check_migration_requirements(self, changed_files: List[str]) -> Tuple[bool, List[str]]:
        """Check if database migrations are required."""
        migration_required = False
        suggestions = []

        for file_path in changed_files:
            if '/models.py' in file_path or '/models/' in file_path:
                migration_required = True
                suggestions.append(f"Run makemigrations for changes in {file_path}")

        return migration_required, suggestions

    def _find_test_coverage_gaps(self, affected_files: Set[str],
                                affected_symbols: Set[str]) -> List[str]:
        """Find test coverage gaps for affected code."""
        gaps = []

        # Check file-level coverage
        for file_path in affected_files:
            if not self._has_test_coverage(file_path):
                gaps.append(f"No test coverage for file: {file_path}")

        # Check symbol-level coverage
        for symbol_key in affected_symbols:
            if not self._symbol_has_test_coverage(symbol_key):
                gaps.append(f"No test coverage for symbol: {symbol_key}")

        return gaps

    def _has_test_coverage(self, file_path: str) -> bool:
        """Check if file has test coverage."""
        try:
            file_obj = IndexedFile.objects.get(path=file_path)
            return TestCoverage.objects.filter(file=file_obj).exists()
        except IndexedFile.DoesNotExist:
            return False

    def _symbol_has_test_coverage(self, symbol_key: str) -> bool:
        """Check if symbol has test coverage."""
        # This is a simplified check - in practice, you'd need more sophisticated analysis
        file_path = symbol_key.split('::')[0]
        return self._has_test_coverage(file_path)

    def _calculate_severity(self, affected_file_count: int,
                          breaking_change_count: int,
                          migration_required: bool) -> ImpactSeverity:
        """Calculate overall impact severity."""
        if breaking_change_count > 0 or migration_required:
            if breaking_change_count >= 5 or affected_file_count >= 20:
                return ImpactSeverity.CRITICAL
            elif breaking_change_count >= 2 or affected_file_count >= 10:
                return ImpactSeverity.HIGH
            else:
                return ImpactSeverity.MEDIUM
        elif affected_file_count >= 5:
            return ImpactSeverity.MEDIUM
        else:
            return ImpactSeverity.LOW

    def _calculate_confidence(self, affected_files: Set[str],
                            affected_symbols: Set[str]) -> float:
        """Calculate confidence in impact analysis."""
        # Base confidence
        confidence = 0.8

        # Adjust based on data completeness
        indexed_files = IndexedFile.objects.filter(path__in=affected_files).count()
        file_coverage_ratio = indexed_files / len(affected_files) if affected_files else 0

        confidence *= file_coverage_ratio

        # Adjust based on symbol analysis completeness
        if affected_symbols:
            symbol_coverage = len([s for s in affected_symbols if s in self.symbol_usage_map])
            symbol_coverage_ratio = symbol_coverage / len(affected_symbols)
            confidence *= symbol_coverage_ratio

        return min(confidence, 1.0)

    def analyze_dependency_chain(self, source: str, target: str) -> Optional[DependencyChain]:
        """Analyze dependency chain between two components."""
        try:
            # Use BFS to find shortest dependency path
            queue = deque([(source, [source])])
            visited = {source}

            while queue:
                current, path = queue.popleft()

                if current == target:
                    return DependencyChain(
                        source=source,
                        target=target,
                        path=path,
                        depth=len(path) - 1,
                        impact_weight=1.0 / len(path)  # Inverse of path length
                    )

                if current in self.dependency_graph:
                    for neighbor in self.dependency_graph[current]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append((neighbor, path + [neighbor]))

            return None

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            print(f"Dependency chain analysis failed: {e}")
            return None

    def get_impact_report(self, impact_result: ImpactResult) -> str:
        """Generate a human-readable impact report."""
        report_lines = [
            "🔍 Impact Analysis Report",
            "=" * 50,
            f"📊 Severity: {impact_result.severity.value.upper()}",
            f"🎯 Confidence: {impact_result.confidence:.2%}",
            "",
            f"📁 Affected Files: {len(impact_result.affected_files)}",
            f"🔤 Affected Symbols: {len(impact_result.affected_symbols)}",
            f"🧪 Affected Tests: {len(impact_result.affected_tests)}",
            f"🌐 Affected URLs: {len(impact_result.affected_urls)}",
            "",
        ]

        if impact_result.breaking_changes:
            report_lines.append("⚠️ Breaking Changes:")
            for bc in impact_result.breaking_changes:
                report_lines.append(f"  • {bc['description']} ({bc['severity']})")
            report_lines.append("")

        if impact_result.migration_required:
            report_lines.append("🔄 Migration Required:")
            for suggestion in impact_result.migration_suggestions:
                report_lines.append(f"  • {suggestion}")
            report_lines.append("")

        if impact_result.test_coverage_gaps:
            report_lines.append("🕳️ Test Coverage Gaps:")
            for gap in impact_result.test_coverage_gaps[:5]:  # Limit to top 5
                report_lines.append(f"  • {gap}")
            if len(impact_result.test_coverage_gaps) > 5:
                report_lines.append(f"  • ... and {len(impact_result.test_coverage_gaps) - 5} more")
            report_lines.append("")

        return "\n".join(report_lines)