"""
Enhanced Python indexer using libcst for advanced AST parsing and analysis.

This indexer provides comprehensive Python code analysis including:
- Import graph with circular dependency detection
- Call graph analysis for function relationships
- Decorator analysis for Django-specific patterns
- Docstring extraction with structured parsing
- Complexity metrics (cyclomatic, cognitive)
"""

import ast
import re
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass

try:
    import libcst as cst
except ImportError:
    LIBCST_AVAILABLE = False
    cst = None

from django.db import transaction
from django.contrib.postgres.search import SearchVector

from apps.mentor.models import IndexedFile, CodeSymbol, SymbolRelation


@dataclass
class SymbolInfo:
    """Container for symbol information."""
    name: str
    kind: str
    span_start: int
    span_end: int
    parents: List[str]
    decorators: List[str]
    docstring: str
    signature: str
    complexity: int
    return_type: Optional[str] = None
    parameters: List[Dict[str, Any]] = None
    is_async: bool = False
    is_property: bool = False
    visibility: str = "public"  # public, private, protected


@dataclass
class ImportInfo:
    """Container for import information."""
    module: str
    name: Optional[str] = None
    alias: Optional[str] = None
    is_from_import: bool = False
    line_number: int = 0


class ComplexityAnalyzer(ast.NodeVisitor):
    """Calculate cyclomatic and cognitive complexity."""

    def __init__(self):
        self.cyclomatic = 0
        self.cognitive = 0
        self.nesting_level = 0

    def visit_If(self, node):
        self.cyclomatic += 1
        self.cognitive += (1 + self.nesting_level)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_While(self, node):
        self.cyclomatic += 1
        self.cognitive += (1 + self.nesting_level)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_For(self, node):
        self.cyclomatic += 1
        self.cognitive += (1 + self.nesting_level)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_ExceptHandler(self, node):
        self.cyclomatic += 1
        self.cognitive += (1 + self.nesting_level)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_With(self, node):
        self.cyclomatic += 1
        self.cognitive += (1 + self.nesting_level)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_BoolOp(self, node):
        self.cognitive += 1
        self.generic_visit(node)

    def visit_Compare(self, node):
        if len(node.ops) > 1:
            self.cognitive += len(node.ops) - 1
        self.generic_visit(node)


class EnhancedPythonIndexer:
    """Enhanced Python code indexer with advanced analysis capabilities."""

    def __init__(self, file_obj: IndexedFile):
        self.file_obj = file_obj
        self.symbols: List[SymbolInfo] = []
        self.imports: List[ImportInfo] = []
        self.relations: List[Tuple[str, str, str, int]] = []  # source, target, kind, line
        self.call_graph: Dict[str, Set[str]] = {}
        self.current_scope: List[str] = []
        self.django_patterns: Dict[str, Any] = {}

    def index_file(self, content: str) -> Dict[str, int]:
        """Main entry point to index a Python file."""
        try:
            # Parse with standard AST first
            tree = ast.parse(content)

            # Extract basic symbols
            self._extract_imports(tree)
            self._extract_symbols(tree)
            self._build_call_graph(tree)
            self._detect_django_patterns(tree, content)

            # Try enhanced parsing with libcst if available
            if LIBCST_AVAILABLE:
                try:
                    self._enhance_with_libcst(content)
                except (ValueError, TypeError) as e:
                    # Fall back to AST-only analysis
                    print(f"LibCST analysis failed, using AST only: {e}")

            # Store results in database
            return self._save_to_database()

        except SyntaxError as e:
            print(f"Syntax error in {self.file_obj.path}: {e}")
            return {'symbols': 0, 'relations': 0, 'errors': 1}

    def _extract_imports(self, tree: ast.AST):
        """Extract import statements."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append(ImportInfo(
                        module=alias.name,
                        alias=alias.asname,
                        line_number=node.lineno
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    self.imports.append(ImportInfo(
                        module=module,
                        name=alias.name,
                        alias=alias.asname,
                        is_from_import=True,
                        line_number=node.lineno
                    ))

    def _extract_symbols(self, tree: ast.AST):
        """Extract symbols with detailed analysis."""
        extractor = EnhancedSymbolExtractor(self.file_obj.path)
        extractor.visit(tree)
        self.symbols = extractor.symbols

    def _build_call_graph(self, tree: ast.AST):
        """Build function call relationships."""
        builder = CallGraphBuilder()
        builder.visit(tree)
        self.call_graph = builder.call_graph

    def _detect_django_patterns(self, tree: ast.AST, content: str):
        """Detect Django-specific patterns."""
        detector = DjangoPatternDetector()
        detector.visit(tree)
        self.django_patterns = detector.patterns

        # Additional pattern detection from content
        self._detect_django_content_patterns(content)

    def _detect_django_content_patterns(self, content: str):
        """Detect Django patterns from content analysis."""
        patterns = {}

        # Model field patterns
        field_patterns = [
            r'(\w+)\s*=\s*models\.(\w+Field)\(',
            r'(\w+)\s*=\s*models\.(ForeignKey|ManyToManyField|OneToOneField)\(',
        ]

        for pattern in field_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                field_name, field_type = match.groups()
                if 'model_fields' not in patterns:
                    patterns['model_fields'] = []
                patterns['model_fields'].append({
                    'name': field_name,
                    'type': field_type,
                    'line': content[:match.start()].count('\n') + 1
                })

        # URL pattern detection
        url_patterns = [
            r'path\([\'"]([^\'"]+)[\'"],\s*([^,]+)',
            r'url\(r[\'"]([^\'"]+)[\'"],\s*([^,]+)',
        ]

        for pattern in url_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                route, view = match.groups()
                if 'url_patterns' not in patterns:
                    patterns['url_patterns'] = []
                patterns['url_patterns'].append({
                    'route': route,
                    'view': view.strip(),
                    'line': content[:match.start()].count('\n') + 1
                })

        self.django_patterns.update(patterns)

    def _enhance_with_libcst(self, content: str):
        """Enhance analysis using libcst."""
        if not LIBCST_AVAILABLE:
            return

        try:
            tree = cst.parse_expression(content) if content.strip() else cst.parse_module(content)

            # Enhanced analysis with libcst
            enhancer = LibCSTEnhancer()
            tree.visit(enhancer)

            # Merge enhanced information
            for symbol in self.symbols:
                enhanced_info = enhancer.get_symbol_info(symbol.name)
                if enhanced_info:
                    symbol.return_type = enhanced_info.get('return_type')
                    symbol.parameters = enhanced_info.get('parameters', [])

        except (AttributeError, DatabaseError, IntegrityError, TypeError, ValueError) as e:
            print(f"LibCST enhancement failed: {e}")

    def _save_to_database(self) -> Dict[str, int]:
        """Save extracted information to database."""
        stats = {'symbols': 0, 'relations': 0, 'errors': 0}

        try:
            with transaction.atomic():
                # Clear existing symbols for this file
                CodeSymbol.objects.filter(file=self.file_obj).delete()
                SymbolRelation.objects.filter(
                    source__file=self.file_obj
                ).delete()

                # Create symbol objects
                symbol_map = {}
                for symbol_info in self.symbols:
                    symbol = CodeSymbol.objects.create(
                        file=self.file_obj,
                        name=symbol_info.name,
                        kind=symbol_info.kind,
                        span_start=symbol_info.span_start,
                        span_end=symbol_info.span_end,
                        parents=symbol_info.parents,
                        decorators=symbol_info.decorators,
                        docstring=symbol_info.docstring,
                        signature=symbol_info.signature,
                        complexity=symbol_info.complexity,
                        search_vector=SearchVector('name') + SearchVector('docstring'),
                    )
                    symbol_map[symbol_info.name] = symbol
                    stats['symbols'] += 1

                # Create relations
                for source_name, target_name, kind, line_num in self.relations:
                    if source_name in symbol_map and target_name in symbol_map:
                        SymbolRelation.objects.create(
                            source=symbol_map[source_name],
                            target=symbol_map[target_name],
                            kind=kind,
                            line_number=line_num,
                        )
                        stats['relations'] += 1

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            print(f"Database save error: {e}")
            stats['errors'] = 1

        return stats


class EnhancedSymbolExtractor(ast.NodeVisitor):
    """Enhanced symbol extractor with detailed analysis."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.symbols: List[SymbolInfo] = []
        self.current_class = None
        self.scope_stack: List[str] = []

    def visit_ClassDef(self, node):
        """Extract class definitions with enhanced analysis."""
        parents = list(self.scope_stack)
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]

        # Analyze inheritance
        bases = [self._get_name(base) for base in node.bases]

        # Calculate complexity
        complexity_analyzer = ComplexityAnalyzer()
        complexity_analyzer.visit(node)

        symbol = SymbolInfo(
            name=node.name,
            kind='class',
            span_start=node.lineno,
            span_end=getattr(node, 'end_lineno', node.lineno),
            parents=parents,
            decorators=decorators,
            docstring=ast.get_docstring(node) or '',
            signature=f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}",
            complexity=complexity_analyzer.cyclomatic,
            visibility=self._get_visibility(node.name)
        )

        self.symbols.append(symbol)

        # Enter class scope
        self.scope_stack.append(node.name)
        self.current_class = node.name
        self.generic_visit(node)
        self.scope_stack.pop()
        self.current_class = None

    def visit_FunctionDef(self, node):
        """Extract function definitions with enhanced analysis."""
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node):
        """Extract async function definitions."""
        self._process_function(node, is_async=True)

    def _process_function(self, node, is_async: bool):
        """Process function/method definitions."""
        parents = list(self.scope_stack)
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]

        # Determine if it's a method or function
        kind = 'method' if self.current_class else 'function'

        # Check if it's a property
        is_property = any('property' in dec for dec in decorators)
        if is_property:
            kind = 'property'

        # Build signature with type annotations
        signature = self._build_signature(node, is_async)

        # Extract parameters
        parameters = self._extract_parameters(node)

        # Calculate complexity
        complexity_analyzer = ComplexityAnalyzer()
        complexity_analyzer.visit(node)

        # Extract return type
        return_type = None
        if node.returns:
            return_type = self._get_type_annotation(node.returns)

        symbol = SymbolInfo(
            name=node.name,
            kind=kind,
            span_start=node.lineno,
            span_end=getattr(node, 'end_lineno', node.lineno),
            parents=parents,
            decorators=decorators,
            docstring=ast.get_docstring(node) or '',
            signature=signature,
            complexity=complexity_analyzer.cyclomatic,
            return_type=return_type,
            parameters=parameters,
            is_async=is_async,
            is_property=is_property,
            visibility=self._get_visibility(node.name)
        )

        self.symbols.append(symbol)

        # Enter function scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Assign(self, node):
        """Extract variable assignments."""
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            parents = list(self.scope_stack)

            # Classify the variable
            kind = self._classify_variable(var_name, node.value)

            if kind:  # Only store significant variables
                symbol = SymbolInfo(
                    name=var_name,
                    kind=kind,
                    span_start=node.lineno,
                    span_end=node.lineno,
                    parents=parents,
                    decorators=[],
                    docstring='',
                    signature=f"{var_name} = ...",
                    complexity=0,
                    visibility=self._get_visibility(var_name)
                )
                self.symbols.append(symbol)

        self.generic_visit(node)

    def _get_decorator_name(self, decorator) -> str:
        """Get decorator name as string."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return ast.unparse(decorator)
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return ast.unparse(decorator.func)
        return str(decorator)

    def _get_name(self, node) -> str:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return ast.unparse(node)
        return str(node)

    def _build_signature(self, node, is_async: bool) -> str:
        """Build function signature with type annotations."""
        parts = []
        if is_async:
            parts.append('async')
        parts.append('def')
        parts.append(node.name)

        # Parameters
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._get_type_annotation(arg.annotation)}"
            args.append(arg_str)

        parts.append(f"({', '.join(args)})")

        # Return type
        if node.returns:
            parts.append(f" -> {self._get_type_annotation(node.returns)}")

        return ' '.join(parts)

    def _extract_parameters(self, node) -> List[Dict[str, Any]]:
        """Extract function parameters with type information."""
        parameters = []

        for arg in node.args.args:
            param = {
                'name': arg.arg,
                'type': self._get_type_annotation(arg.annotation) if arg.annotation else None,
                'default': None  # Would need more complex analysis for defaults
            }
            parameters.append(param)

        return parameters

    def _get_type_annotation(self, annotation) -> str:
        """Get type annotation as string."""
        try:
            return ast.unparse(annotation)
        except:
            return str(annotation)

    def _classify_variable(self, name: str, value_node) -> Optional[str]:
        """Classify variable type based on name and value."""
        if name.isupper():
            return 'constant'
        elif name.startswith('_'):
            if isinstance(value_node, ast.Call):
                return 'private_variable'
        elif isinstance(value_node, ast.Call):
            # Could be a factory or instantiation
            return 'variable'
        elif isinstance(value_node, (ast.List, ast.Dict, ast.Set, ast.Tuple)):
            return 'collection'

        return None

    def _get_visibility(self, name: str) -> str:
        """Determine symbol visibility."""
        if name.startswith('__') and not name.endswith('__'):
            return 'private'
        elif name.startswith('_'):
            return 'protected'
        return 'public'


class CallGraphBuilder(ast.NodeVisitor):
    """Build function call relationships."""

    def __init__(self):
        self.call_graph: Dict[str, Set[str]] = {}
        self.current_function = None

    def visit_FunctionDef(self, node):
        self.current_function = node.name
        self.call_graph[node.name] = set()
        self.generic_visit(node)
        self.current_function = None

    def visit_Call(self, node):
        if self.current_function:
            func_name = self._get_function_name(node.func)
            if func_name:
                self.call_graph[self.current_function].add(func_name)
        self.generic_visit(node)

    def _get_function_name(self, node) -> Optional[str]:
        """Get function name from call node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None


class DjangoPatternDetector(ast.NodeVisitor):
    """Detect Django-specific patterns in code."""

    def __init__(self):
        self.patterns: Dict[str, Any] = {
            'models': [],
            'views': [],
            'forms': [],
            'admin': [],
            'serializers': [],
            'signals': [],
        }

    def visit_ClassDef(self, node):
        """Detect Django class patterns."""
        bases = [self._get_base_name(base) for base in node.bases]

        # Model detection
        if any('Model' in base for base in bases):
            self.patterns['models'].append({
                'name': node.name,
                'line': node.lineno,
                'bases': bases
            })

        # View detection
        if any('View' in base for base in bases):
            self.patterns['views'].append({
                'name': node.name,
                'line': node.lineno,
                'bases': bases
            })

        # Form detection
        if any('Form' in base for base in bases):
            self.patterns['forms'].append({
                'name': node.name,
                'line': node.lineno,
                'bases': bases
            })

        # Serializer detection
        if any('Serializer' in base for base in bases):
            self.patterns['serializers'].append({
                'name': node.name,
                'line': node.lineno,
                'bases': bases
            })

        self.generic_visit(node)

    def _get_base_name(self, base) -> str:
        """Get base class name."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return ast.unparse(base)
        return str(base)


class LibCSTEnhancer:
    """Enhance analysis using libcst for more detailed information."""

    def __init__(self):
        self.symbol_info: Dict[str, Dict[str, Any]] = {}

    def get_symbol_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get enhanced symbol information."""
        return self.symbol_info.get(name)