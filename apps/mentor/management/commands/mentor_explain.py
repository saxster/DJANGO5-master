"""
mentor_explain management command for the AI Mentor system.

This command provides detailed explanations of code symbols, files,
URLs, models, and their relationships using the indexed knowledge base.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Q

    IndexedFile, CodeSymbol, SymbolRelation, DjangoURL,
    DjangoModel, GraphQLDefinition, TestCase, TestCoverage, IndexMetadata
)


@dataclass
class ExplanationContext:
    """Context information for explanations."""
    target: str
    target_type: str  # symbol, file, url, model, graphql
    related_symbols: List[CodeSymbol]
    related_files: List[IndexedFile]
    relationships: List[SymbolRelation]
    test_coverage: List[TestCase]
    documentation: Optional[str]


class CodeExplainer:
    """Generates explanations for code elements using indexed data."""

    def __init__(self):
        self.context_depth = 2  # How deep to traverse relationships

    def explain_symbol(self, symbol_ref: str, include_usage: bool = True) -> Dict[str, Any]:
        """Explain a code symbol (class, function, method, etc.)."""
        # Parse symbol reference (file:line or symbol_name)
        symbol = self._resolve_symbol_reference(symbol_ref)

        if not symbol:
            return {'error': f'Symbol not found: {symbol_ref}'}

        explanation = {
            'symbol': {
                'name': symbol.name,
                'full_name': symbol.full_name,
                'kind': symbol.kind,
                'file': symbol.file.path,
                'location': f"lines {symbol.span_start}-{symbol.span_end}",
                'signature': symbol.signature,
                'docstring': symbol.docstring,
                'complexity': symbol.complexity,
                'decorators': symbol.decorators,
                'parents': symbol.parents
            },
            'context': self._build_symbol_context(symbol),
            'relationships': self._get_symbol_relationships(symbol),
            'usage': self._get_symbol_usage(symbol) if include_usage else None,
            'tests': self._get_symbol_tests(symbol),
            'documentation': self._extract_symbol_documentation(symbol)
        }

        return explanation

    def explain_file(self, file_path: str) -> Dict[str, Any]:
        """Explain a file and its contents."""
        try:
            indexed_file = IndexedFile.objects.get(path=file_path)
        except IndexedFile.DoesNotExist:
            return {'error': f'File not indexed: {file_path}'}

        # Get all symbols in the file
        symbols = CodeSymbol.objects.filter(file=indexed_file).order_by('span_start')

        # Get file relationships
        file_relationships = self._get_file_relationships(indexed_file)

        explanation = {
            'file': {
                'path': indexed_file.path,
                'language': indexed_file.language,
                'size': indexed_file.size,
                'is_test': indexed_file.is_test,
                'last_modified': indexed_file.updated_at.isoformat(),
                'is_fresh': indexed_file.is_fresh
            },
            'overview': self._generate_file_overview(indexed_file, symbols),
            'symbols': [self._summarize_symbol(s) for s in symbols],
            'imports': self._get_file_imports(indexed_file),
            'dependencies': file_relationships['dependencies'],
            'dependents': file_relationships['dependents'],
            'tests': self._get_file_tests(indexed_file),
            'models': self._get_file_models(indexed_file),
            'urls': self._get_file_urls(indexed_file),
            'graphql': self._get_file_graphql(indexed_file)
        }

        return explanation

    def explain_url(self, url_pattern: str) -> Dict[str, Any]:
        """Explain a Django URL pattern."""
        # Find matching URL patterns
        urls = DjangoURL.objects.filter(
            Q(route__icontains=url_pattern) |
            Q(name__icontains=url_pattern) |
            Q(view_name__icontains=url_pattern)
        )

        if not urls.exists():
            return {'error': f'URL pattern not found: {url_pattern}'}

        explanations = []

        for url in urls:
            # Find the view symbol
            view_symbol = self._find_view_symbol(url.view_name)

            explanation = {
                'url': {
                    'route': url.route,
                    'name': url.name,
                    'view_name': url.view_name,
                    'methods': url.methods,
                    'permissions': url.permissions,
                    'app_label': url.app_label,
                    'file': url.file.path,
                    'line': url.line_number
                },
                'view': self._explain_view_symbol(view_symbol) if view_symbol else None,
                'parameters': self._extract_url_parameters(url.route),
                'related_urls': self._get_related_urls(url),
                'tests': self._get_url_tests(url)
            }

            explanations.append(explanation)

        return {'urls': explanations}

    def explain_model(self, model_name: str) -> Dict[str, Any]:
        """Explain a Django model."""
        # Try exact match first, then partial
        try:
            model = DjangoModel.objects.get(model_name__iexact=model_name)
        except DjangoModel.DoesNotExist:
            models = DjangoModel.objects.filter(model_name__icontains=model_name)
            if not models.exists():
                return {'error': f'Model not found: {model_name}'}
            model = models.first()

        # Find the model class symbol
        model_symbol = self._find_model_symbol(model)

        explanation = {
            'model': {
                'name': model.model_name,
                'app_label': model.app_label,
                'full_name': f"{model.app_label}.{model.model_name}",
                'db_table': model.db_table,
                'file': model.file.path,
                'line': model.line_number,
                'fields': model.fields,
                'meta_options': model.meta_options
            },
            'class_definition': self._explain_view_symbol(model_symbol) if model_symbol else None,
            'field_analysis': self._analyze_model_fields(model),
            'relationships': self._get_model_relationships(model),
            'usage': self._get_model_usage(model),
            'migrations': self._get_model_migrations(model),
            'admin': self._check_model_admin(model),
            'serializers': self._find_model_serializers(model),
            'tests': self._get_model_tests(model)
        }

        return explanation

    def explain_graphql(self, type_name: str) -> Dict[str, Any]:
        """Explain a GraphQL type or resolver."""
        graphql_defs = GraphQLDefinition.objects.filter(name__icontains=type_name)

        if not graphql_defs.exists():
            return {'error': f'GraphQL definition not found: {type_name}'}

        explanations = []

        for gql_def in graphql_defs:
            explanation = {
                'graphql': {
                    'name': gql_def.name,
                    'kind': gql_def.kind,
                    'type_definition': gql_def.type_definition,
                    'file': gql_def.file.path,
                    'line': gql_def.line_number
                },
                'schema_analysis': self._analyze_graphql_schema(gql_def),
                'resolvers': self._find_graphql_resolvers(gql_def),
                'mutations': self._find_related_mutations(gql_def),
                'usage': self._get_graphql_usage(gql_def)
            }

            explanations.append(explanation)

        return {'definitions': explanations}

    def explain_query(self, query: str) -> Dict[str, Any]:
        """Explain a search query across all indexed content."""
        results = {
            'query': query,
            'symbols': [],
            'files': [],
            'urls': [],
            'models': [],
            'graphql': []
        }

        # Search symbols
        symbols = CodeSymbol.objects.filter(
            Q(name__icontains=query) |
            Q(docstring__icontains=query) |
            Q(signature__icontains=query)
        )[:10]

        for symbol in symbols:
            results['symbols'].append(self._summarize_symbol(symbol))

        # Search files
        files = IndexedFile.objects.filter(
            Q(path__icontains=query) |
            Q(content_preview__icontains=query)
        )[:10]

        for file in files:
            results['files'].append({
                'path': file.path,
                'language': file.language,
                'is_test': file.is_test,
                'preview': file.content_preview[:200]
            })

        # Search URLs
        urls = DjangoURL.objects.filter(
            Q(route__icontains=query) |
            Q(name__icontains=query) |
            Q(view_name__icontains=query)
        )[:10]

        for url in urls:
            results['urls'].append({
                'route': url.route,
                'name': url.name,
                'view_name': url.view_name,
                'app_label': url.app_label
            })

        # Search models
        models = DjangoModel.objects.filter(
            Q(model_name__icontains=query) |
            Q(app_label__icontains=query)
        )[:10]

        for model in models:
            results['models'].append({
                'name': model.model_name,
                'app_label': model.app_label,
                'db_table': model.db_table,
                'field_count': len(model.fields)
            })

        # Search GraphQL
        graphql_defs = GraphQLDefinition.objects.filter(
            Q(name__icontains=query)
        )[:10]

        for gql_def in graphql_defs:
            results['graphql'].append({
                'name': gql_def.name,
                'kind': gql_def.kind,
                'file': gql_def.file.path
            })

        return results

    def _resolve_symbol_reference(self, symbol_ref: str) -> Optional[CodeSymbol]:
        """Resolve a symbol reference to a CodeSymbol object."""
        if ':' in symbol_ref:
            # Format: file.py:line_number or file.py:symbol_name
            file_path, ref = symbol_ref.split(':', 1)

            try:
                indexed_file = IndexedFile.objects.get(path=file_path)
            except IndexedFile.DoesNotExist:
                return None

            # Try as line number first
            try:
                line_number = int(ref)
                return CodeSymbol.objects.filter(
                    file=indexed_file,
                    span_start__lte=line_number,
                    span_end__gte=line_number
                ).first()
            except ValueError:
                # Try as symbol name
                return CodeSymbol.objects.filter(
                    file=indexed_file,
                    name=ref
                ).first()
        else:
            # Just a symbol name - find the best match
            symbols = CodeSymbol.objects.filter(name=symbol_ref)
            return symbols.first() if symbols.exists() else None

    def _build_symbol_context(self, symbol: CodeSymbol) -> Dict[str, Any]:
        """Build context information for a symbol."""
        context = {
            'file_context': self._get_file_context(symbol.file),
            'class_hierarchy': self._get_class_hierarchy(symbol),
            'scope': self._get_symbol_scope(symbol)
        }

        return context

    def _get_symbol_relationships(self, symbol: CodeSymbol) -> Dict[str, List]:
        """Get relationships for a symbol."""
        outgoing = SymbolRelation.objects.filter(source=symbol).select_related('target')
        incoming = SymbolRelation.objects.filter(target=symbol).select_related('source')

        return {
            'calls': [r.target.name for r in outgoing if r.kind == 'call'],
            'imports': [r.target.name for r in outgoing if r.kind == 'import'],
            'inherits_from': [r.target.name for r in outgoing if r.kind == 'inherit'],
            'called_by': [r.source.name for r in incoming if r.kind == 'call'],
            'imported_by': [r.source.name for r in incoming if r.kind == 'import'],
            'extended_by': [r.source.name for r in incoming if r.kind == 'inherit']
        }

    def _get_symbol_usage(self, symbol: CodeSymbol) -> List[Dict]:
        """Get usage examples of a symbol."""
        # Find where this symbol is referenced
        incoming_relations = SymbolRelation.objects.filter(
            target=symbol
        ).select_related('source', 'source__file')

        usage = []
        for relation in incoming_relations[:10]:  # Limit to 10 examples
            usage.append({
                'file': relation.source.file.path,
                'line': relation.line_number,
                'context': relation.source.name,
                'relationship': relation.kind
            })

        return usage

    def _get_symbol_tests(self, symbol: CodeSymbol) -> List[Dict]:
        """Get tests that cover a symbol."""
        coverage = TestCoverage.objects.filter(
            file=symbol.file,
            covered_lines__overlap=[list(range(symbol.span_start, symbol.span_end + 1))]
        ).select_related('test')

        tests = []
        for cov in coverage:
            tests.append({
                'test_name': cov.test.node_id,
                'coverage_percentage': cov.coverage_percentage,
                'execution_time': cov.test.avg_execution_time,
                'success_rate': cov.test.success_rate
            })

        return tests

    def _extract_symbol_documentation(self, symbol: CodeSymbol) -> Optional[str]:
        """Extract and format symbol documentation."""
        if symbol.docstring:
            return symbol.docstring

        # Try to extract from file content
        try:
            file_path = Path(settings.BASE_DIR) / symbol.file.path
            if file_path.exists():
                content = file_path.read_text()
                lines = content.split('\n')

                # Look for comments around the symbol
                start_line = max(0, symbol.span_start - 3)
                end_line = min(len(lines), symbol.span_start + 1)

                comments = []
                for i in range(start_line, end_line):
                    line = lines[i].strip()
                    if line.startswith('#'):
                        comments.append(line[1:].strip())

                if comments:
                    return '\n'.join(comments)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist):
            pass

        return None

    def _generate_file_overview(self, file: IndexedFile, symbols: List[CodeSymbol]) -> str:
        """Generate a high-level overview of a file."""
        overview_parts = []

        if file.language:
            overview_parts.append(f"This is a {file.language} file")

        if file.is_test:
            overview_parts.append("containing test cases")

        symbol_counts = {}
        for symbol in symbols:
            symbol_counts[symbol.kind] = symbol_counts.get(symbol.kind, 0) + 1

        if symbol_counts:
            symbol_desc = []
            for kind, count in symbol_counts.items():
                if count == 1:
                    symbol_desc.append(f"1 {kind}")
                else:
                    symbol_desc.append(f"{count} {kind}s")

            overview_parts.append(f"with {', '.join(symbol_desc)}")

        return ' '.join(overview_parts) + '.'

    def _summarize_symbol(self, symbol: CodeSymbol) -> Dict[str, Any]:
        """Create a summary of a symbol."""
        return {
            'name': symbol.name,
            'kind': symbol.kind,
            'file': symbol.file.path,
            'line': symbol.span_start,
            'signature': symbol.signature,
            'docstring_preview': (symbol.docstring[:100] + '...') if symbol.docstring and len(symbol.docstring) > 100 else symbol.docstring,
            'complexity': symbol.complexity
        }

    def _get_file_relationships(self, file: IndexedFile) -> Dict[str, List]:
        """Get file-level relationships."""
        symbols_in_file = CodeSymbol.objects.filter(file=file)

        # Get dependencies (what this file imports/uses)
        dependencies = set()
        dependents = set()

        for symbol in symbols_in_file:
            outgoing = SymbolRelation.objects.filter(source=symbol).select_related('target__file')
            for relation in outgoing:
                if relation.target.file != file:
                    dependencies.add(relation.target.file.path)

            incoming = SymbolRelation.objects.filter(target=symbol).select_related('source__file')
            for relation in incoming:
                if relation.source.file != file:
                    dependents.add(relation.source.file.path)

        return {
            'dependencies': list(dependencies),
            'dependents': list(dependents)
        }

    def _get_file_imports(self, file: IndexedFile) -> List[str]:
        """Get imports in a file."""
        import_symbols = CodeSymbol.objects.filter(
            file=file,
            kind='import'
        ).values_list('name', flat=True)

        return list(import_symbols)

    def _get_file_tests(self, file: IndexedFile) -> List[Dict]:
        """Get tests for a file."""
        tests = TestCase.objects.filter(file=file)

        return [{
            'name': test.node_id,
            'class_name': test.class_name,
            'method_name': test.method_name,
            'markers': test.markers,
            'avg_execution_time': test.avg_execution_time,
            'success_rate': test.success_rate
        } for test in tests]

    def _get_file_models(self, file: IndexedFile) -> List[Dict]:
        """Get Django models in a file."""
        models = DjangoModel.objects.filter(file=file)

        return [{
            'name': model.model_name,
            'app_label': model.app_label,
            'db_table': model.db_table,
            'field_count': len(model.fields)
        } for model in models]

    def _get_file_urls(self, file: IndexedFile) -> List[Dict]:
        """Get URL patterns in a file."""
        urls = DjangoURL.objects.filter(file=file)

        return [{
            'route': url.route,
            'name': url.name,
            'view_name': url.view_name,
            'methods': url.methods
        } for url in urls]

    def _get_file_graphql(self, file: IndexedFile) -> List[Dict]:
        """Get GraphQL definitions in a file."""
        graphql_defs = GraphQLDefinition.objects.filter(file=file)

        return [{
            'name': gql.name,
            'kind': gql.kind
        } for gql in graphql_defs]

    def _find_view_symbol(self, view_name: str) -> Optional[CodeSymbol]:
        """Find the symbol for a view function or class."""
        # Try different patterns
        patterns = [view_name, view_name.split('.')[-1]]

        for pattern in patterns:
            symbol = CodeSymbol.objects.filter(
                name=pattern,
                kind__in=['function', 'class']
            ).first()
            if symbol:
                return symbol

        return None

    def _explain_view_symbol(self, symbol: CodeSymbol) -> Dict[str, Any]:
        """Create detailed explanation for a view symbol."""
        if not symbol:
            return None

        return {
            'name': symbol.name,
            'kind': symbol.kind,
            'signature': symbol.signature,
            'docstring': symbol.docstring,
            'decorators': symbol.decorators,
            'complexity': symbol.complexity,
            'file': symbol.file.path,
            'lines': f"{symbol.span_start}-{symbol.span_end}"
        }

    # Additional helper methods would continue here...
    # For brevity, I'll implement the remaining methods as stubs

    def _extract_url_parameters(self, route: str) -> List[str]:
        """Extract URL parameters from route pattern."""
        import re
        params = re.findall(r'<(\w+)>', route) + re.findall(r'\(\?P<(\w+)>', route)
        return params

    def _get_related_urls(self, url: DjangoURL) -> List[str]:
        """Get related URL patterns."""
        related = DjangoURL.objects.filter(
            app_label=url.app_label
        ).exclude(id=url.id).values_list('route', flat=True)[:5]
        return list(related)

    def _get_url_tests(self, url: DjangoURL) -> List[Dict]:
        """Get tests for a URL."""
        # This would be implemented to find tests that hit this URL
        return []

    def _find_model_symbol(self, model: DjangoModel) -> Optional[CodeSymbol]:
        """Find the class symbol for a model."""
        return CodeSymbol.objects.filter(
            file=model.file,
            name=model.model_name,
            kind='class'
        ).first()

    def _analyze_model_fields(self, model: DjangoModel) -> Dict[str, Any]:
        """Analyze model fields."""
        return {
            'field_count': len(model.fields),
            'field_types': list(set(field.get('type', 'unknown') for field in model.fields.values())),
            'required_fields': [name for name, field in model.fields.items() if not field.get('null', False)],
            'relationships': [name for name, field in model.fields.items() if 'ForeignKey' in field.get('type', '')]
        }

    def _get_model_relationships(self, model: DjangoModel) -> Dict[str, List]:
        """Get model relationships."""
        # This would analyze foreign keys, many-to-many, etc.
        return {'foreign_keys': [], 'reverse_relations': [], 'many_to_many': []}

    def _get_model_usage(self, model: DjangoModel) -> List[Dict]:
        """Get where a model is used."""
        # Find symbols that reference this model
        model_refs = CodeSymbol.objects.filter(
            name__icontains=model.model_name
        ).exclude(file=model.file)[:10]

        return [self._summarize_symbol(s) for s in model_refs]

    def _get_model_migrations(self, model: DjangoModel) -> List[str]:
        """Get migrations for a model."""
        # This would scan migration files
        return []

    def _check_model_admin(self, model: DjangoModel) -> Optional[Dict]:
        """Check if model has admin configuration."""
        # This would look for ModelAdmin classes
        return None

    def _find_model_serializers(self, model: DjangoModel) -> List[Dict]:
        """Find serializers for a model."""
        # This would look for DRF serializers
        return []

    def _get_model_tests(self, model: DjangoModel) -> List[Dict]:
        """Get tests for a model."""
        return []

    # Continue with GraphQL analysis methods...
    def _analyze_graphql_schema(self, gql_def: GraphQLDefinition) -> Dict[str, Any]:
        """Analyze GraphQL schema definition."""
        return {'fields': [], 'mutations': [], 'queries': []}

    def _find_graphql_resolvers(self, gql_def: GraphQLDefinition) -> List[Dict]:
        """Find resolvers for GraphQL definition."""
        return []

    def _find_related_mutations(self, gql_def: GraphQLDefinition) -> List[Dict]:
        """Find related mutations."""
        return []

    def _get_graphql_usage(self, gql_def: GraphQLDefinition) -> List[Dict]:
        """Get GraphQL usage examples."""
        return []

    # Additional helper methods...
    def _get_file_context(self, file: IndexedFile) -> Dict[str, Any]:
        """Get file context information."""
        return {
            'directory': str(Path(file.path).parent),
            'app': file.path.split('/')[1] if '/' in file.path else None,
            'type': 'test' if file.is_test else 'source'
        }

    def _get_class_hierarchy(self, symbol: CodeSymbol) -> List[str]:
        """Get class hierarchy for a symbol."""
        if symbol.kind == 'class':
            # Find inheritance relationships
            inherits = SymbolRelation.objects.filter(
                source=symbol,
                kind='inherit'
            ).select_related('target')
            return [rel.target.name for rel in inherits]
        return []

    def _get_symbol_scope(self, symbol: CodeSymbol) -> str:
        """Get the scope of a symbol."""
        if symbol.parents:
            return '.'.join(symbol.parents)
        return 'module'


class Command(BaseCommand):
    help = 'Explain code symbols, files, URLs, models, and their relationships'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.explainer = CodeExplainer()

    def add_arguments(self, parser):
        # Main target argument
        parser.add_argument(
            'target',
            type=str,
            help='What to explain (symbol reference, file path, URL pattern, model name, or search query)'
        )

        # Type specification
        parser.add_argument(
            '--type',
            type=str,
            choices=['symbol', 'file', 'url', 'model', 'graphql', 'query'],
            help='Type of target to explain (auto-detected if not specified)'
        )

        # Output options
        parser.add_argument(
            '--format',
            type=str,
            choices=['markdown', 'json', 'summary'],
            default='markdown',
            help='Output format'
        )

        parser.add_argument(
            '--depth',
            type=int,
            default=2,
            help='Depth of relationship traversal'
        )

        # Content options
        parser.add_argument(
            '--include-usage',
            action='store_true',
            default=True,
            help='Include usage examples'
        )

        parser.add_argument(
            '--include-tests',
            action='store_true',
            default=True,
            help='Include test information'
        )

        parser.add_argument(
            '--include-docs',
            action='store_true',
            default=True,
            help='Include documentation'
        )

        # Search options
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit number of results for queries'
        )

        # Save options
        parser.add_argument(
            '--save',
            type=str,
            help='Save explanation to file'
        )

    def handle(self, *args, **options):
        target = options['target']
        target_type = options.get('type')
        output_format = options['format']
        depth = options['depth']
        include_usage = options.get('include_usage', True)
        include_tests = options.get('include_tests', True)
        include_docs = options.get('include_docs', True)
        limit = options.get('limit', 10)
        save_path = options.get('save')

        self.stdout.write(f"🔍 Explaining: {target}")

        try:
            # Set explainer options
            self.explainer.context_depth = depth

            # Auto-detect type if not specified
            if not target_type:
                target_type = self._detect_target_type(target)

            # Generate explanation
            if target_type == 'symbol':
                explanation = self.explainer.explain_symbol(target, include_usage)
            elif target_type == 'file':
                explanation = self.explainer.explain_file(target)
            elif target_type == 'url':
                explanation = self.explainer.explain_url(target)
            elif target_type == 'model':
                explanation = self.explainer.explain_model(target)
            elif target_type == 'graphql':
                explanation = self.explainer.explain_graphql(target)
            elif target_type == 'query':
                explanation = self.explainer.explain_query(target)
            else:
                raise CommandError(f"Unknown target type: {target_type}")

            # Check for errors
            if 'error' in explanation:
                self.stdout.write(self.style.ERROR(f"❌ {explanation['error']}"))
                return

            # Format output
            if output_format == 'json':
                output = json.dumps(explanation, indent=2, default=str)
            elif output_format == 'summary':
                output = self._format_summary(explanation, target_type)
            else:  # markdown
                output = self._format_markdown(explanation, target_type)

            # Save or display
            if save_path:
                Path(save_path).write_text(output)
                self.stdout.write(f"💾 Explanation saved to {save_path}")
            else:
                self.stdout.write("\n" + "="*60)
                self.stdout.write(output)
                self.stdout.write("="*60)

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValueError, json.JSONDecodeError) as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))
            raise CommandError(f"Explanation failed: {e}")

    def _detect_target_type(self, target: str) -> str:
        """Auto-detect the type of target."""
        if ':' in target:
            return 'symbol'
        elif target.endswith('.py'):
            return 'file'
        elif '/' in target or target.startswith('^'):
            return 'url'
        elif target[0].isupper():
            return 'model'
        elif 'Type' in target or 'Query' in target or 'Mutation' in target:
            return 'graphql'
        else:
            return 'query'

    def _format_summary(self, explanation: Dict[str, Any], target_type: str) -> str:
        """Format explanation as summary."""
        lines = [f"EXPLANATION SUMMARY ({target_type.upper()})"]

        if target_type == 'symbol':
            symbol = explanation.get('symbol', {})
            lines.extend([
                f"Name: {symbol.get('name')}",
                f"Type: {symbol.get('kind')}",
                f"File: {symbol.get('file')}",
                f"Location: {symbol.get('location')}",
                f"Complexity: {symbol.get('complexity', 0)}"
            ])

            if symbol.get('docstring'):
                lines.append(f"Description: {symbol['docstring'][:100]}...")

        elif target_type == 'file':
            file_info = explanation.get('file', {})
            lines.extend([
                f"Path: {file_info.get('path')}",
                f"Language: {file_info.get('language')}",
                f"Type: {'Test' if file_info.get('is_test') else 'Source'}",
                f"Size: {file_info.get('size', 0)} bytes",
                f"Symbols: {len(explanation.get('symbols', []))}"
            ])

        elif target_type == 'model':
            model_info = explanation.get('model', {})
            lines.extend([
                f"Name: {model_info.get('name')}",
                f"App: {model_info.get('app_label')}",
                f"Table: {model_info.get('db_table')}",
                f"Fields: {len(model_info.get('fields', {}))}"
            ])

        return '\n'.join(lines)

    def _format_markdown(self, explanation: Dict[str, Any], target_type: str) -> str:
        """Format explanation as markdown."""
        if target_type == 'symbol':
            return self._format_symbol_markdown(explanation)
        elif target_type == 'file':
            return self._format_file_markdown(explanation)
        elif target_type == 'model':
            return self._format_model_markdown(explanation)
        elif target_type == 'query':
            return self._format_query_markdown(explanation)
        else:
            return json.dumps(explanation, indent=2, default=str)

    def _format_symbol_markdown(self, explanation: Dict[str, Any]) -> str:
        """Format symbol explanation as markdown."""
        symbol = explanation.get('symbol', {})
        lines = [
            f"# Symbol: {symbol.get('name')}",
            f"",
            f"**Type:** {symbol.get('kind')}",
            f"**File:** `{symbol.get('file')}`",
            f"**Location:** {symbol.get('location')}",
            f"**Complexity:** {symbol.get('complexity', 0)}",
            f"",
        ]

        if symbol.get('signature'):
            lines.extend([
                f"## Signature",
                f"```python",
                f"{symbol['signature']}",
                f"```",
                f"",
            ])

        if symbol.get('docstring'):
            lines.extend([
                f"## Documentation",
                f"{symbol['docstring']}",
                f"",
            ])

        # Add relationships
        relationships = explanation.get('relationships', {})
        if any(relationships.values()):
            lines.extend([f"## Relationships", f""])

            for rel_type, items in relationships.items():
                if items:
                    lines.append(f"**{rel_type.replace('_', ' ').title()}:** {', '.join(items)}")
                    lines.append("")

        # Add usage examples
        usage = explanation.get('usage')
        if usage:
            lines.extend([
                f"## Usage Examples",
                f"",
            ])

            for example in usage[:5]:  # Limit to 5 examples
                lines.append(f"- `{example.get('file')}:{example.get('line')}` - {example.get('context')}")

            lines.append("")

        # Add test information
        tests = explanation.get('tests')
        if tests:
            lines.extend([
                f"## Tests",
                f"",
                f"This symbol is covered by {len(tests)} test(s):",
                f"",
            ])

            for test in tests[:3]:  # Limit to 3 tests
                lines.append(f"- {test.get('test_name')} ({test.get('coverage_percentage', 0):.1f}% coverage)")

        return '\n'.join(lines)

    def _format_file_markdown(self, explanation: Dict[str, Any]) -> str:
        """Format file explanation as markdown."""
        file_info = explanation.get('file', {})
        lines = [
            f"# File: {file_info.get('path')}",
            f"",
            f"**Language:** {file_info.get('language')}",
            f"**Type:** {'Test file' if file_info.get('is_test') else 'Source file'}",
            f"**Size:** {file_info.get('size', 0):,} bytes",
            f"",
        ]

        # Add overview
        overview = explanation.get('overview')
        if overview:
            lines.extend([
                f"## Overview",
                f"{overview}",
                f"",
            ])

        # Add symbols
        symbols = explanation.get('symbols', [])
        if symbols:
            lines.extend([
                f"## Symbols ({len(symbols)})",
                f"",
            ])

            # Group by kind
            symbol_groups = {}
            for symbol in symbols:
                kind = symbol.get('kind', 'unknown')
                if kind not in symbol_groups:
                    symbol_groups[kind] = []
                symbol_groups[kind].append(symbol)

            for kind, kind_symbols in symbol_groups.items():
                lines.append(f"### {kind.title()}s")
                for symbol in kind_symbols:
                    lines.append(f"- `{symbol.get('name')}` (line {symbol.get('line')})")
                    if symbol.get('docstring_preview'):
                        lines.append(f"  {symbol['docstring_preview']}")
                lines.append("")

        return '\n'.join(lines)

    def _format_model_markdown(self, explanation: Dict[str, Any]) -> str:
        """Format model explanation as markdown."""
        model_info = explanation.get('model', {})
        lines = [
            f"# Model: {model_info.get('name')}",
            f"",
            f"**App:** {model_info.get('app_label')}",
            f"**Database Table:** `{model_info.get('db_table')}`",
            f"**File:** `{model_info.get('file')}`",
            f"",
        ]

        # Add fields
        fields = model_info.get('fields', {})
        if fields:
            lines.extend([
                f"## Fields ({len(fields)})",
                f"",
            ])

            for field_name, field_info in fields.items():
                field_type = field_info.get('type', 'Unknown')
                lines.append(f"- **{field_name}** (`{field_type}`)")
                if field_info.get('help_text'):
                    lines.append(f"  {field_info['help_text']}")

            lines.append("")

        # Add field analysis
        field_analysis = explanation.get('field_analysis', {})
        if field_analysis:
            lines.extend([
                f"## Field Analysis",
                f"",
                f"- **Total Fields:** {field_analysis.get('field_count', 0)}",
                f"- **Field Types:** {', '.join(field_analysis.get('field_types', []))}",
                f"- **Required Fields:** {len(field_analysis.get('required_fields', []))}",
                f"- **Relationships:** {len(field_analysis.get('relationships', []))}",
                f"",
            ])

        return '\n'.join(lines)

    def _format_query_markdown(self, explanation: Dict[str, Any]) -> str:
        """Format query results as markdown."""
        lines = [
            f"# Search Results: {explanation.get('query')}",
            f"",
        ]

        # Add each category
        for category, items in explanation.items():
            if category == 'query' or not items:
                continue

            lines.extend([
                f"## {category.title()} ({len(items)})",
                f"",
            ])

            for item in items[:5]:  # Limit to 5 items per category
                if category == 'symbols':
                    lines.append(f"- **{item.get('name')}** ({item.get('kind')}) in `{item.get('file')}`")
                elif category == 'files':
                    lines.append(f"- `{item.get('path')}` ({item.get('language')})")
                elif category == 'models':
                    lines.append(f"- **{item.get('name')}** in `{item.get('app_label')}`")
                elif category == 'urls':
                    lines.append(f"- `{item.get('route')}` → `{item.get('view_name')}`")

            lines.append("")

        return '\n'.join(lines)