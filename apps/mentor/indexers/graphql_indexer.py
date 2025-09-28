"""
GraphQL schema walker and indexer for comprehensive GraphQL analysis.

This indexer provides deep analysis of:
- Type extraction: Objects, interfaces, unions, enums
- Resolver mapping: Query/mutation to function mapping
- Field relationship analysis: Type connections
- Permission detection: Authentication/authorization decorators
- Subscription endpoints: Real-time data mappings
"""

import ast
import importlib
import inspect
from pathlib import Path
from dataclasses import dataclass

try:
    from graphene_django import DjangoObjectType
    GRAPHENE_AVAILABLE = True
except ImportError:
    GRAPHENE_AVAILABLE = False
    graphene = None

from django.db import transaction
from apps.mentor.models import IndexedFile, GraphQLDefinition


@dataclass
class GraphQLTypeInfo:
    """Container for GraphQL type information."""
    name: str
    kind: str  # 'object', 'interface', 'union', 'enum', 'scalar', 'input'
    fields: Dict[str, Any]
    interfaces: List[str]
    possible_types: List[str]  # For unions
    values: List[str]  # For enums
    description: Optional[str]
    file_path: str
    line_number: int


@dataclass
class GraphQLFieldInfo:
    """Container for GraphQL field information."""
    name: str
    type: str
    args: Dict[str, str]
    resolver: Optional[str]
    description: Optional[str]
    deprecated: bool
    deprecation_reason: Optional[str]


@dataclass
class GraphQLResolverInfo:
    """Container for GraphQL resolver information."""
    name: str
    type_name: str
    field_name: str
    function_name: str
    permissions: List[str]
    decorators: List[str]
    is_async: bool
    file_path: str
    line_number: int


@dataclass
class GraphQLQueryInfo:
    """Container for GraphQL query/mutation information."""
    name: str
    type: str  # 'query', 'mutation', 'subscription'
    return_type: str
    args: Dict[str, str]
    resolver: Optional[str]
    permissions: List[str]
    description: Optional[str]
    file_path: str
    line_number: int


class GraphQLIndexer:
    """Comprehensive GraphQL schema indexer."""

    def __init__(self):
        self.types_info: List[GraphQLTypeInfo] = []
        self.resolvers_info: List[GraphQLResolverInfo] = []
        self.queries_info: List[GraphQLQueryInfo] = []
        self.schema_files: Set[str] = set()

    def index_graphql_schema(self, schema_paths: List[str]) -> Dict[str, int]:
        """Index GraphQL schema from given paths."""
        if not GRAPHENE_AVAILABLE:
            print("Graphene not available, skipping GraphQL indexing")
            return {'error': 1}

        try:
            # Discover schema files
            self._discover_schema_files(schema_paths)

            # Index each schema file
            for file_path in self.schema_files:
                self._index_schema_file(file_path)

            # Save to database
            return self._save_to_database()

        except (ValueError, TypeError) as e:
            print(f"Error indexing GraphQL schema: {e}")
            return {'error': 1}

    def _discover_schema_files(self, schema_paths: List[str]):
        """Discover GraphQL schema files."""
        for path_str in schema_paths:
            path = Path(path_str)

            if path.is_file() and path.suffix == '.py':
                # Check if file contains GraphQL definitions
                if self._contains_graphql_definitions(path):
                    self.schema_files.add(str(path))

            elif path.is_dir():
                # Recursively search for schema files
                for py_file in path.rglob('*.py'):
                    if self._contains_graphql_definitions(py_file):
                        self.schema_files.add(str(py_file))

    def _contains_graphql_definitions(self, file_path: Path) -> bool:
        """Check if file contains GraphQL definitions."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for GraphQL-related imports and classes
            graphql_indicators = [
                'graphene',
                'DjangoObjectType',
                'ObjectType',
                'Mutation',
                'Query',
                'Subscription',
                'Schema',
                'Field',
                'List',
                'Interface',
                'Union'
            ]

            return any(indicator in content for indicator in graphql_indicators)

        except (FileNotFoundError, IOError, OSError, PermissionError):
            return False

    def _index_schema_file(self, file_path: str):
        """Index a single schema file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            # Extract GraphQL components
            extractor = GraphQLSchemaExtractor(file_path)
            extractor.visit(tree)

            # Merge results
            self.types_info.extend(extractor.types_info)
            self.resolvers_info.extend(extractor.resolvers_info)
            self.queries_info.extend(extractor.queries_info)

            # Try dynamic inspection if possible
            self._dynamic_inspection(file_path, content)

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Error indexing schema file {file_path}: {e}")

    def _dynamic_inspection(self, file_path: str, content: str):
        """Perform dynamic inspection of GraphQL schema."""
        try:
            # Extract module name from file path
            path = Path(file_path)
            module_parts = []

            # Build module path
            for part in path.parts:
                if part == 'apps' or module_parts:
                    module_parts.append(part)

            if module_parts:
                module_name = '.'.join(module_parts[:-1]) + '.' + path.stem
                module_name = module_name.replace('/', '.')

                try:
                    module = importlib.import_module(module_name)
                    self._inspect_module(module, file_path)
                except ImportError:
                    pass

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Dynamic inspection failed for {file_path}: {e}")

    def _inspect_module(self, module, file_path: str):
        """Inspect a module for GraphQL definitions."""
        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            if inspect.isclass(attr):
                # Check if it's a GraphQL type
                if self._is_graphql_type(attr):
                    type_info = self._analyze_graphql_type(attr, attr_name, file_path)
                    self.types_info.append(type_info)

                # Check if it's a query/mutation/subscription
                elif self._is_graphql_operation(attr):
                    operation_info = self._analyze_graphql_operation(attr, attr_name, file_path)
                    self.queries_info.append(operation_info)

    def _is_graphql_type(self, cls) -> bool:
        """Check if class is a GraphQL type."""
        if not inspect.isclass(cls):
            return False

        if not GRAPHENE_AVAILABLE:
            return False

        # Check inheritance
        try:
            return (issubclass(cls, ObjectType) or
                    issubclass(cls, DjangoObjectType) or
                    issubclass(cls, Interface) or
                    issubclass(cls, Union) or
                    issubclass(cls, Enum))
        except:
            return False

    def _is_graphql_operation(self, cls) -> bool:
        """Check if class defines GraphQL operations."""
        if not inspect.isclass(cls):
            return False

        # Look for typical operation names
        operation_names = ['Query', 'Mutation', 'Subscription']
        return cls.__name__ in operation_names or any(op in cls.__name__ for op in operation_names)

    def _analyze_graphql_type(self, cls, name: str, file_path: str) -> GraphQLTypeInfo:
        """Analyze a GraphQL type class."""
        # Determine type kind
        kind = 'object'
        if GRAPHENE_AVAILABLE:
            if issubclass(cls, Interface):
                kind = 'interface'
            elif issubclass(cls, Union):
                kind = 'union'
            elif issubclass(cls, Enum):
                kind = 'enum'

        # Extract fields
        fields = {}
        if hasattr(cls, '_meta') and hasattr(cls._meta, 'fields'):
            for field_name, field in cls._meta.fields.items():
                fields[field_name] = self._analyze_graphql_field(field)

        # Extract class-level fields
        for attr_name in dir(cls):
            if not attr_name.startswith('_'):
                attr = getattr(cls, attr_name)
                if GRAPHENE_AVAILABLE and isinstance(attr, Field):
                    fields[attr_name] = self._analyze_graphql_field(attr)

        # Extract interfaces
        interfaces = []
        if hasattr(cls, '_meta') and hasattr(cls._meta, 'interfaces'):
            interfaces = [iface.__name__ for iface in cls._meta.interfaces]

        # Extract possible types (for unions)
        possible_types = []
        if hasattr(cls, '_meta') and hasattr(cls._meta, 'types'):
            possible_types = [t.__name__ for t in cls._meta.types]

        # Extract enum values
        values = []
        if kind == 'enum' and hasattr(cls, '_meta') and hasattr(cls._meta, 'enum'):
            values = [item.name for item in cls._meta.enum]

        return GraphQLTypeInfo(
            name=name,
            kind=kind,
            fields=fields,
            interfaces=interfaces,
            possible_types=possible_types,
            values=values,
            description=getattr(cls, '__doc__', None),
            file_path=file_path,
            line_number=self._get_class_line_number(cls)
        )

    def _analyze_graphql_field(self, field) -> Dict[str, Any]:
        """Analyze a GraphQL field."""
        field_info = {
            'type': str(field.type) if hasattr(field, 'type') else 'Unknown',
            'description': getattr(field, 'description', None),
            'deprecated': getattr(field, 'deprecation_reason', None) is not None,
            'deprecation_reason': getattr(field, 'deprecation_reason', None),
        }

        # Extract arguments
        if hasattr(field, 'args') and field.args:
            field_info['args'] = {
                arg_name: str(arg.type) if hasattr(arg, 'type') else 'Unknown'
                for arg_name, arg in field.args.items()
            }
        else:
            field_info['args'] = {}

        return field_info

    def _analyze_graphql_operation(self, cls, name: str, file_path: str) -> GraphQLQueryInfo:
        """Analyze a GraphQL operation (Query/Mutation/Subscription)."""
        # Determine operation type
        operation_type = 'query'
        if 'Mutation' in name:
            operation_type = 'mutation'
        elif 'Subscription' in name:
            operation_type = 'subscription'

        # This is a simplified analysis - in practice, you'd need to examine
        # the specific fields defined in the operation class
        return GraphQLQueryInfo(
            name=name,
            type=operation_type,
            return_type='Unknown',
            args={},
            resolver=None,
            permissions=[],
            description=getattr(cls, '__doc__', None),
            file_path=file_path,
            line_number=self._get_class_line_number(cls)
        )

    def _get_class_line_number(self, cls) -> int:
        """Get line number where class is defined."""
        try:
            return inspect.getsourcelines(cls)[1]
        except:
            return 1

    def _save_to_database(self) -> Dict[str, int]:
        """Save GraphQL definitions to database."""
        stats = {'types': 0, 'queries': 0, 'errors': 0}

        try:
            with transaction.atomic():
                # Clear existing GraphQL definitions
                # (In practice, you might want more sophisticated cleanup)

                # Save types
                for type_info in self.types_info:
                    try:
                        # Get or create indexed file
                        indexed_file, _ = IndexedFile.objects.get_or_create(
                            path=type_info.file_path,
                            defaults={
                                'sha': 'unknown',
                                'mtime': 0,
                                'size': 0,
                                'language': 'python'
                            }
                        )

                        # Save GraphQL definition
                        GraphQLDefinition.objects.update_or_create(
                            name=type_info.name,
                            kind=type_info.kind,
                            file=indexed_file,
                            defaults={
                                'type_definition': {
                                    'fields': type_info.fields,
                                    'interfaces': type_info.interfaces,
                                    'possible_types': type_info.possible_types,
                                    'values': type_info.values,
                                    'description': type_info.description,
                                },
                                'line_number': type_info.line_number,
                            }
                        )
                        stats['types'] += 1

                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                        print(f"Error saving GraphQL type {type_info.name}: {e}")
                        stats['errors'] += 1

                # Save queries/mutations/subscriptions
                for query_info in self.queries_info:
                    try:
                        # Get or create indexed file
                        indexed_file, _ = IndexedFile.objects.get_or_create(
                            path=query_info.file_path,
                            defaults={
                                'sha': 'unknown',
                                'mtime': 0,
                                'size': 0,
                                'language': 'python'
                            }
                        )

                        # Save GraphQL definition
                        GraphQLDefinition.objects.update_or_create(
                            name=query_info.name,
                            kind=query_info.type,
                            file=indexed_file,
                            defaults={
                                'type_definition': {
                                    'return_type': query_info.return_type,
                                    'args': query_info.args,
                                    'resolver': query_info.resolver,
                                    'permissions': query_info.permissions,
                                    'description': query_info.description,
                                },
                                'line_number': query_info.line_number,
                            }
                        )
                        stats['queries'] += 1

                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                        print(f"Error saving GraphQL query {query_info.name}: {e}")
                        stats['errors'] += 1

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            print(f"Database transaction error: {e}")
            stats['errors'] += 1

        return stats


class GraphQLSchemaExtractor(ast.NodeVisitor):
    """Extract GraphQL schema information from AST."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.types_info: List[GraphQLTypeInfo] = []
        self.resolvers_info: List[GraphQLResolverInfo] = []
        self.queries_info: List[GraphQLQueryInfo] = []

    def visit_ClassDef(self, node):
        """Visit class definitions to extract GraphQL types."""
        # Check if this is a GraphQL type
        if self._is_graphql_class(node):
            type_info = self._extract_type_info(node)
            self.types_info.append(type_info)

        # Check if this is a GraphQL operation
        if self._is_graphql_operation_class(node):
            operation_info = self._extract_operation_info(node)
            self.queries_info.append(operation_info)

        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Visit function definitions to extract resolvers."""
        # Check if this is a resolver function
        if self._is_resolver_function(node):
            resolver_info = self._extract_resolver_info(node)
            self.resolvers_info.append(resolver_info)

        self.generic_visit(node)

    def _is_graphql_class(self, node: ast.ClassDef) -> bool:
        """Check if class is a GraphQL type."""
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.append(ast.unparse(base))

        graphql_bases = [
            'ObjectType', 'DjangoObjectType', 'Interface', 'Union', 'Enum',
            'InputObjectType', 'Scalar'
        ]

        return any(gql_base in ' '.join(base_names) for gql_base in graphql_bases)

    def _is_graphql_operation_class(self, node: ast.ClassDef) -> bool:
        """Check if class defines GraphQL operations."""
        operation_names = ['Query', 'Mutation', 'Subscription']
        return node.name in operation_names or any(op in node.name for op in operation_names)

    def _is_resolver_function(self, node: ast.FunctionDef) -> bool:
        """Check if function is a GraphQL resolver."""
        # Look for resolver patterns
        resolver_indicators = [
            'resolve_',
            '@staticmethod',
            'info',  # GraphQL info parameter
            'root',  # GraphQL root parameter
        ]

        # Check function name
        if node.name.startswith('resolve_'):
            return True

        # Check parameters
        arg_names = [arg.arg for arg in node.args.args]
        if 'info' in arg_names or ('self' in arg_names and 'info' in arg_names):
            return True

        return False

    def _extract_type_info(self, node: ast.ClassDef) -> GraphQLTypeInfo:
        """Extract information from GraphQL type class."""
        # Determine type kind
        kind = 'object'  # Default
        for base in node.bases:
            base_name = ast.unparse(base) if hasattr(ast, 'unparse') else str(base)
            if 'Interface' in base_name:
                kind = 'interface'
            elif 'Union' in base_name:
                kind = 'union'
            elif 'Enum' in base_name:
                kind = 'enum'
            elif 'InputObjectType' in base_name:
                kind = 'input'
            elif 'Scalar' in base_name:
                kind = 'scalar'

        # Extract fields from class body
        fields = {}
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_info = self._analyze_field_assignment(item)
                        if field_info:
                            fields[target.id] = field_info

        return GraphQLTypeInfo(
            name=node.name,
            kind=kind,
            fields=fields,
            interfaces=[],  # Would need more complex analysis
            possible_types=[],  # Would need more complex analysis
            values=[],  # Would need more complex analysis for enums
            description=ast.get_docstring(node),
            file_path=self.file_path,
            line_number=node.lineno
        )

    def _extract_operation_info(self, node: ast.ClassDef) -> GraphQLQueryInfo:
        """Extract information from GraphQL operation class."""
        operation_type = 'query'
        if 'Mutation' in node.name:
            operation_type = 'mutation'
        elif 'Subscription' in node.name:
            operation_type = 'subscription'

        return GraphQLQueryInfo(
            name=node.name,
            type=operation_type,
            return_type='Unknown',  # Would need field analysis
            args={},  # Would need field analysis
            resolver=None,
            permissions=[],  # Would need decorator analysis
            description=ast.get_docstring(node),
            file_path=self.file_path,
            line_number=node.lineno
        )

    def _extract_resolver_info(self, node: ast.FunctionDef) -> GraphQLResolverInfo:
        """Extract resolver function information."""
        # Extract decorators
        decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)
            else:
                decorators.append(ast.unparse(decorator))

        # Extract permissions from decorators
        permissions = []
        for dec in decorators:
            if 'permission' in dec.lower() or 'auth' in dec.lower():
                permissions.append(dec)

        return GraphQLResolverInfo(
            name=node.name,
            type_name='Unknown',  # Would need context analysis
            field_name=node.name.replace('resolve_', '') if node.name.startswith('resolve_') else node.name,
            function_name=node.name,
            permissions=permissions,
            decorators=decorators,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            file_path=self.file_path,
            line_number=node.lineno
        )

    def _analyze_field_assignment(self, node: ast.Assign) -> Optional[Dict[str, Any]]:
        """Analyze field assignment in GraphQL type."""
        if isinstance(node.value, ast.Call):
            func_name = ast.unparse(node.value.func) if hasattr(ast, 'unparse') else str(node.value.func)

            # Check if it's a GraphQL field
            if any(field_type in func_name for field_type in ['Field', 'List', 'NonNull', 'String', 'Int', 'Boolean']):
                return {
                    'type': func_name,
                    'args': {},  # Would need argument analysis
                    'description': None,  # Would need keyword analysis
                    'deprecated': False,
                }

        return None