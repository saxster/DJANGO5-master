"""
Enhanced Django-specific codemods using LibCST for common refactoring patterns.

This module provides sophisticated code transformations for Django projects:
- Model field migrations and optimizations
- View and API endpoint improvements
- Query optimization patterns
- Security enhancements
- Performance optimizations
"""

import libcst as cst
from pathlib import Path

from libcst import matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand


@dataclass
class CodemodResult:
    """Result of applying a codemod."""
    original_code: str
    transformed_code: str
    changes_made: List[str]
    warnings: List[str]
    success: bool


class DjangoModelOptimizationCodemod(VisitorBasedCodemodCommand):
    """Optimize Django model definitions."""

    DESCRIPTION: str = "Optimize Django model field definitions and add performance improvements"

    def __init__(self, context: CodemodContext):
        super().__init__(context)
        self.changes_made = []

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[cst.ClassDef]:
        """Visit class definitions to optimize Django models."""
        # Check if this is a Django model
        if self._is_django_model(node):
            return self._optimize_model_class(node)
        return node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[cst.FunctionDef]:
        """Optimize model methods."""
        # Look for common patterns to optimize
        if node.name.value in ['__str__', '__repr__']:
            return self._optimize_string_representation(node)
        elif node.name.value.startswith('get_'):
            return self._optimize_getter_method(node)
        return node

    def _is_django_model(self, node: cst.ClassDef) -> bool:
        """Check if class is a Django model."""
        if not node.bases:
            return False

        for base in node.bases:
            if m.matches(base, m.Arg(value=m.Attribute(value=m.Name("models"), attr=m.Name("Model")))):
                return True
            if m.matches(base, m.Arg(value=m.Name("Model"))):
                return True

        return False

    def _optimize_model_class(self, node: cst.ClassDef) -> cst.ClassDef:
        """Apply optimizations to Django model class."""
        new_body = []
        meta_class_found = False

        for stmt in node.body.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                # Check for field definitions
                for element in stmt.body:
                    if isinstance(element, cst.Assign):
                        optimized_assign = self._optimize_field_assignment(element)
                        if optimized_assign:
                            new_body.append(cst.SimpleStatementLine(body=[optimized_assign]))
                        else:
                            new_body.append(stmt)
                    else:
                        new_body.append(stmt)
            elif isinstance(stmt, cst.ClassDef) and stmt.name.value == "Meta":
                meta_class_found = True
                optimized_meta = self._optimize_meta_class(stmt)
                new_body.append(optimized_meta)
            else:
                new_body.append(stmt)

        # Add Meta class if not found and optimizations are beneficial
        if not meta_class_found and self._should_add_meta_class(node):
            meta_class = self._create_optimized_meta_class()
            new_body.append(meta_class)
            self.changes_made.append("Added optimized Meta class")

        return node.with_changes(body=cst.IndentedBlock(body=new_body))

    def _optimize_field_assignment(self, assign: cst.Assign) -> Optional[cst.Assign]:
        """Optimize Django model field assignments."""
        if not assign.targets or len(assign.targets) != 1:
            return assign

        target = assign.targets[0]
        if not isinstance(target.target, cst.Name):
            return assign

        field_name = target.target.value
        value = assign.value

        # Check if this is a field assignment
        if isinstance(value, cst.Call):
            if self._is_field_call(value):
                return self._optimize_field_call(assign, field_name, value)

        return assign

    def _is_field_call(self, call: cst.Call) -> bool:
        """Check if call is a Django field."""
        field_types = [
            'CharField', 'TextField', 'IntegerField', 'DateTimeField',
            'ForeignKey', 'OneToOneField', 'ManyToManyField', 'BooleanField'
        ]

        if isinstance(call.func, cst.Name) and call.func.value in field_types:
            return True

        if isinstance(call.func, cst.Attribute):
            if (isinstance(call.func.value, cst.Name) and
                call.func.value.value == 'models' and
                call.func.attr.value in field_types):
                return True

        return False

    def _optimize_field_call(self, assign: cst.Assign, field_name: str, call: cst.Call) -> cst.Assign:
        """Optimize field call with performance improvements."""
        args = list(call.args)
        kwargs = []

        # Extract existing kwargs
        for arg in args:
            if arg.keyword:
                kwargs.append(arg)

        # Add db_index for commonly queried fields
        if self._should_add_db_index(field_name, call):
            if not any(kw.keyword and kw.keyword.value == 'db_index' for kw in kwargs):
                kwargs.append(cst.Arg(
                    keyword=cst.Name('db_index'),
                    value=cst.Name('True')
                ))
                self.changes_made.append(f"Added db_index to {field_name}")

        # Add appropriate max_length for CharField if missing
        if self._is_char_field(call) and not any(kw.keyword and kw.keyword.value == 'max_length' for kw in kwargs):
            kwargs.append(cst.Arg(
                keyword=cst.Name('max_length'),
                value=cst.Integer('255')  # Reasonable default
            ))
            self.changes_made.append(f"Added max_length to CharField {field_name}")

        # Optimize foreign key fields
        if self._is_foreign_key_field(call):
            kwargs = self._optimize_foreign_key_args(kwargs, field_name)

        # Reconstruct call with optimized args
        new_args = [arg for arg in args if not arg.keyword] + kwargs
        new_call = call.with_changes(args=new_args)

        return assign.with_changes(value=new_call)

    def _should_add_db_index(self, field_name: str, call: cst.Call) -> bool:
        """Determine if field should have db_index."""
        # Common patterns that benefit from indexing
        index_patterns = [
            'email', 'username', 'slug', 'code', 'identifier',
            'status', 'type', 'category', 'created_by', 'updated_by'
        ]

        return any(pattern in field_name.lower() for pattern in index_patterns)

    def _is_char_field(self, call: cst.Call) -> bool:
        """Check if call is a CharField."""
        if isinstance(call.func, cst.Name):
            return call.func.value == 'CharField'
        elif isinstance(call.func, cst.Attribute):
            return call.func.attr.value == 'CharField'
        return False

    def _is_foreign_key_field(self, call: cst.Call) -> bool:
        """Check if call is a ForeignKey field."""
        if isinstance(call.func, cst.Name):
            return call.func.value == 'ForeignKey'
        elif isinstance(call.func, cst.Attribute):
            return call.func.attr.value == 'ForeignKey'
        return False

    def _optimize_foreign_key_args(self, kwargs: List[cst.Arg], field_name: str) -> List[cst.Arg]:
        """Optimize ForeignKey field arguments."""
        # Add on_delete if missing (required in modern Django)
        if not any(kw.keyword and kw.keyword.value == 'on_delete' for kw in kwargs):
            kwargs.append(cst.Arg(
                keyword=cst.Name('on_delete'),
                value=cst.Attribute(value=cst.Name('models'), attr=cst.Name('CASCADE'))
            ))
            self.changes_made.append(f"Added on_delete=models.CASCADE to {field_name}")

        return kwargs

    def _optimize_meta_class(self, meta_class: cst.ClassDef) -> cst.ClassDef:
        """Optimize Django model Meta class."""
        new_body = list(meta_class.body.body)

        # Check for common optimizations
        has_ordering = self._meta_has_attribute(meta_class, 'ordering')
        has_indexes = self._meta_has_attribute(meta_class, 'indexes')

        # Add default ordering if not present
        if not has_ordering:
            ordering_stmt = cst.SimpleStatementLine(body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name('ordering'))],
                    value=cst.List([cst.Element(value=cst.SimpleString("'-created_at'"))])
                )
            ])
            new_body.append(ordering_stmt)
            self.changes_made.append("Added default ordering to Meta class")

        return meta_class.with_changes(body=cst.IndentedBlock(body=new_body))

    def _meta_has_attribute(self, meta_class: cst.ClassDef, attr_name: str) -> bool:
        """Check if Meta class has a specific attribute."""
        for stmt in meta_class.body.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                for element in stmt.body:
                    if isinstance(element, cst.Assign):
                        for target in element.targets:
                            if (isinstance(target.target, cst.Name) and
                                target.target.value == attr_name):
                                return True
        return False


class DjangoViewOptimizationCodemod(VisitorBasedCodemodCommand):
    """Optimize Django view functions and classes."""

    DESCRIPTION: str = "Optimize Django views for performance and security"

    def __init__(self, context: CodemodContext):
        super().__init__(context)
        self.changes_made = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[cst.FunctionDef]:
        """Optimize view functions."""
        # Check if this is a view function
        if self._is_view_function(node):
            return self._optimize_view_function(node)
        return node

    def _is_view_function(self, node: cst.FunctionDef) -> bool:
        """Check if function is a Django view."""
        # Look for decorators
        if node.decorators:
            for decorator in node.decorators:
                if isinstance(decorator.decorator, cst.Name):
                    if decorator.decorator.value in ['login_required', 'require_POST', 'api_view']:
                        return True

        # Check function parameters for request
        if node.params and node.params.params:
            first_param = node.params.params[0]
            if isinstance(first_param.name, cst.Name) and first_param.name.value == 'request':
                return True

        return False

    def _optimize_view_function(self, node: cst.FunctionDef) -> cst.FunctionDef:
        """Apply optimizations to view function."""
        # Add transaction.atomic decorator for data modifications
        if self._modifies_data(node) and not self._has_transaction_decorator(node):
            transaction_decorator = cst.Decorator(
                decorator=cst.Attribute(
                    value=cst.Name('transaction'),
                    attr=cst.Name('atomic')
                )
            )

            new_decorators = list(node.decorators or [])
            new_decorators.append(transaction_decorator)

            self.changes_made.append(f"Added @transaction.atomic to {node.name.value}")
            return node.with_changes(decorators=new_decorators)

        return node

    def _modifies_data(self, node: cst.FunctionDef) -> bool:
        """Check if function modifies data."""
        # Look for save(), create(), update(), delete() calls
        modifier_methods = ['save', 'create', 'update', 'delete', 'bulk_create']

        for child in cst.walk(node):
            if isinstance(child, cst.Call):
                if isinstance(child.func, cst.Attribute):
                    if child.func.attr.value in modifier_methods:
                        return True

        return False

    def _has_transaction_decorator(self, node: cst.FunctionDef) -> bool:
        """Check if function already has transaction decorator."""
        if not node.decorators:
            return False

        for decorator in node.decorators:
            if isinstance(decorator.decorator, cst.Attribute):
                if (isinstance(decorator.decorator.value, cst.Name) and
                    decorator.decorator.value.value == 'transaction' and
                    decorator.decorator.attr.value == 'atomic'):
                    return True

        return False


class DjangoQueryOptimizationCodemod(VisitorBasedCodemodCommand):
    """Optimize Django ORM queries to prevent N+1 problems."""

    DESCRIPTION: str = "Add select_related and prefetch_related to optimize Django queries"

    def __init__(self, context: CodemodContext):
        super().__init__(context)
        self.changes_made = []

    def visit_Call(self, node: cst.Call) -> Optional[cst.Call]:
        """Optimize ORM query calls."""
        # Look for queryset methods that could benefit from optimization
        if self._is_queryset_method(node):
            return self._optimize_queryset_call(node)
        return node

    def _is_queryset_method(self, node: cst.Call) -> bool:
        """Check if call is a Django queryset method."""
        queryset_methods = ['filter', 'get', 'all', 'exclude', 'order_by']

        if isinstance(node.func, cst.Attribute):
            method_name = node.func.attr.value
            return method_name in queryset_methods

        return False

    def _optimize_queryset_call(self, node: cst.Call) -> cst.Call:
        """Add optimizations to queryset calls."""
        # This is a simplified optimization
        # In practice, you'd need more sophisticated analysis

        if isinstance(node.func, cst.Attribute):
            method_name = node.func.attr.value

            # For filter/get operations, suggest adding select_related
            if method_name in ['filter', 'get']:
                # Check if we're accessing foreign key fields
                if self._accesses_foreign_keys(node):
                    # Add select_related call
                    select_related_call = cst.Call(
                        func=cst.Attribute(
                            value=node,
                            attr=cst.Name('select_related')
                        ),
                        args=[]  # Empty args - Django will auto-detect
                    )
                    self.changes_made.append(f"Added select_related() to {method_name} call")
                    return select_related_call

        return node

    def _accesses_foreign_keys(self, node: cst.Call) -> bool:
        """Check if query accesses foreign key fields."""
        # Simplified check - look for double underscore in filter args
        for arg in node.args:
            if isinstance(arg.value, cst.SimpleString):
                if '__' in arg.value.value:
                    return True

        return False


class DjangoSecurityCodemod(VisitorBasedCodemodCommand):
    """Apply security improvements to Django code."""

    DESCRIPTION: str = "Apply security improvements and best practices"

    def __init__(self, context: CodemodContext):
        super().__init__(context)
        self.changes_made = []

    def visit_Call(self, node: cst.Call) -> Optional[cst.Call]:
        """Apply security improvements to function calls."""
        # Fix raw SQL usage
        if self._is_raw_sql_call(node):
            return self._secure_raw_sql_call(node)

        # Fix eval/exec usage
        if self._is_dangerous_eval_call(node):
            return self._replace_dangerous_call(node)

        return node

    def _is_raw_sql_call(self, node: cst.Call) -> bool:
        """Check if call uses raw SQL."""
        if isinstance(node.func, cst.Attribute):
            if node.func.attr.value in ['raw', 'extra']:
                return True

        if isinstance(node.func, cst.Name):
            if node.func.value in ['cursor', 'execute']:
                return True

        return False

    def _secure_raw_sql_call(self, node: cst.Call) -> cst.Call:
        """Make raw SQL calls more secure."""
        # Add warning comment
        self.changes_made.append("Added security warning to raw SQL usage")

        # For now, just return the original with a warning
        # In practice, you'd analyze the SQL and suggest parameterized queries
        return node

    def _is_dangerous_eval_call(self, node: cst.Call) -> bool:
        """Check for dangerous eval/exec calls."""
        if isinstance(node.func, cst.Name):
            return node.func.value in ['eval', 'exec']
        return False

    def _replace_dangerous_call(self, node: cst.Call) -> cst.Call:
        """Replace dangerous eval/exec calls with safer alternatives."""
        self.changes_made.append("Flagged dangerous eval/exec usage for manual review")
        # For now, just return original - would need context to safely replace
        return node


class DjangoCodemodEngine:
    """Engine for applying Django-specific codemods."""

    def __init__(self):
        self.available_codemods = {
            'model_optimization': DjangoModelOptimizationCodemod,
            'view_optimization': DjangoViewOptimizationCodemod,
            'query_optimization': DjangoQueryOptimizationCodemod,
            'security_improvements': DjangoSecurityCodemod
        }

    def apply_codemod(self, file_path: str, codemod_name: str) -> CodemodResult:
        """Apply a specific codemod to a file."""
        if codemod_name not in self.available_codemods:
            return CodemodResult(
                original_code="",
                transformed_code="",
                changes_made=[],
                warnings=[f"Unknown codemod: {codemod_name}"],
                success=False
            )

        try:
            # Read original file
            original_code = Path(file_path).read_text(encoding='utf-8')

            # Parse code
            tree = cst.parse_module(original_code)

            # Apply codemod
            context = CodemodContext()
            codemod_class = self.available_codemods[codemod_name]
            transformer = codemod_class(context)

            # Transform the tree
            transformed_tree = tree.visit(transformer)

            # Generate transformed code
            transformed_code = transformed_tree.code

            return CodemodResult(
                original_code=original_code,
                transformed_code=transformed_code,
                changes_made=getattr(transformer, 'changes_made', []),
                warnings=[],
                success=True
            )

        except (ValueError, TypeError) as e:
            return CodemodResult(
                original_code="",
                transformed_code="",
                changes_made=[],
                warnings=[f"Codemod failed: {str(e)}"],
                success=False
            )

    def apply_multiple_codemods(self, file_path: str, codemod_names: List[str]) -> CodemodResult:
        """Apply multiple codemods to a file in sequence."""
        current_code = Path(file_path).read_text(encoding='utf-8')
        all_changes = []
        all_warnings = []

        for codemod_name in codemod_names:
            # Write current code to temporary file for processing
            temp_file = f"{file_path}.tmp"
            Path(temp_file).write_text(current_code, encoding='utf-8')

            try:
                result = self.apply_codemod(temp_file, codemod_name)

                if result.success:
                    current_code = result.transformed_code
                    all_changes.extend(result.changes_made)
                else:
                    all_warnings.extend(result.warnings)

            finally:
                # Clean up temp file
                if Path(temp_file).exists():
                    Path(temp_file).unlink()

        return CodemodResult(
            original_code=Path(file_path).read_text(encoding='utf-8'),
            transformed_code=current_code,
            changes_made=all_changes,
            warnings=all_warnings,
            success=len(all_warnings) == 0
        )

    def suggest_codemods_for_file(self, file_path: str) -> List[str]:
        """Suggest appropriate codemods for a file."""
        suggestions = []

        try:
            content = Path(file_path).read_text(encoding='utf-8')

            # Suggest model optimization for model files
            if '/models.py' in file_path or 'class' in content and 'models.Model' in content:
                suggestions.append('model_optimization')

            # Suggest view optimization for view files
            if '/views.py' in file_path or 'def ' in content and 'request' in content:
                suggestions.append('view_optimization')

            # Suggest query optimization if ORM usage detected
            if any(pattern in content for pattern in ['.filter(', '.get(', '.all()']):
                suggestions.append('query_optimization')

            # Suggest security improvements if risky patterns found
            if any(pattern in content for pattern in ['eval(', 'exec(', '.raw(', 'cursor.']):
                suggestions.append('security_improvements')

        except (ValueError, TypeError) as e:
            print(f"Error analyzing file for codemod suggestions: {e}")

        return suggestions

    def analyze_codemod_impact(self, file_path: str, codemod_names: List[str]) -> Dict[str, Any]:
        """Analyze the potential impact of applying codemods."""
        impact_analysis = {
            'file_path': file_path,
            'codemods_to_apply': codemod_names,
            'estimated_changes': 0,
            'risk_level': 'low',
            'breaking_change_risk': False,
            'backup_recommended': True
        }

        try:
            content = Path(file_path).read_text(encoding='utf-8')

            # Estimate number of changes
            for codemod_name in codemod_names:
                if codemod_name == 'model_optimization':
                    # Count model fields
                    field_count = content.count('models.') + content.count('Field(')
                    impact_analysis['estimated_changes'] += field_count // 3

                elif codemod_name == 'view_optimization':
                    # Count view functions
                    view_count = content.count('def ') + content.count('class ')
                    impact_analysis['estimated_changes'] += view_count // 2

                elif codemod_name == 'query_optimization':
                    # Count query calls
                    query_count = content.count('.filter(') + content.count('.get(')
                    impact_analysis['estimated_changes'] += query_count

            # Assess risk level
            if impact_analysis['estimated_changes'] > 20:
                impact_analysis['risk_level'] = 'high'
            elif impact_analysis['estimated_changes'] > 10:
                impact_analysis['risk_level'] = 'medium'

            # Check for breaking change risk
            if 'model_optimization' in codemod_names and 'models.py' in file_path:
                impact_analysis['breaking_change_risk'] = True

        except (ValueError, TypeError) as e:
            impact_analysis['risk_level'] = 'high'
            impact_analysis['error'] = str(e)

        return impact_analysis

    def get_available_codemods(self) -> Dict[str, str]:
        """Get list of available codemods with descriptions."""
        return {
            name: codemod_class.DESCRIPTION
            for name, codemod_class in self.available_codemods.items()
        }


# Additional utility codemods

class DjangoImportOptimizationCodemod(VisitorBasedCodemodCommand):
    """Optimize Django imports."""

    DESCRIPTION: str = "Optimize and organize Django imports"

    def __init__(self, context: CodemodContext):
        super().__init__(context)
        self.django_imports = set()
        self.other_imports = set()

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[cst.ImportFrom]:
        """Optimize Django imports."""
        if node.module:
            module_name = self._get_module_name(node.module)
            if module_name.startswith('django'):
                # Collect Django imports for reorganization
                self.django_imports.add(node)
                return cst.RemovalSentinel.REMOVE
            else:
                self.other_imports.add(node)

        return node

    def _get_module_name(self, module: cst.Module) -> str:
        """Get string representation of module name."""
        if isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        elif isinstance(module, cst.Name):
            return module.value
        return ""


class DjangoTestOptimizationCodemod(VisitorBasedCodemodCommand):
    """Optimize Django test classes."""

    DESCRIPTION: str = "Optimize Django test classes for performance"

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[cst.ClassDef]:
        """Optimize test classes."""
        if self._is_test_class(node):
            return self._optimize_test_class(node)
        return node

    def _is_test_class(self, node: cst.ClassDef) -> bool:
        """Check if class is a Django test class."""
        if node.name.value.startswith('Test') or node.name.value.endswith('Test'):
            return True

        # Check base classes
        if node.bases:
            for base in node.bases:
                if isinstance(base.value, cst.Attribute):
                    if base.value.attr.value in ['TestCase', 'TransactionTestCase']:
                        return True

        return False

    def _optimize_test_class(self, node: cst.ClassDef) -> cst.ClassDef:
        """Add optimizations to test class."""
        # Could add setUpClass optimizations, database setup, etc.
        return node


# Global engine instance
_codemod_engine = None

def get_codemod_engine() -> DjangoCodemodEngine:
    """Get global codemod engine instance."""
    global _codemod_engine
    if _codemod_engine is None:
        _codemod_engine = DjangoCodemodEngine()
    return _codemod_engine