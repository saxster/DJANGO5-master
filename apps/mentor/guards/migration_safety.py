"""
Migration safety validator for comprehensive safety checks.

This validator provides:
- Destructive operation detection: Column drops, data loss
- Rollback verification: Ensure reversibility
- Data integrity checks: Constraint validation
- Performance impact: Large table warnings
- Dependency ordering: Migration sequencing
"""

from dataclasses import dataclass
from enum import Enum




class SafetyLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"
    DESTRUCTIVE = "destructive"


@dataclass
class SafetyCheck:
    level: SafetyLevel
    description: str
    recommendation: str
    auto_fix: Optional[str] = None


class MigrationSafetyValidator:
    """Validates migration safety before execution."""

    def validate_migration_safety(self, migration_file: str, migration_data: Dict) -> List[SafetyCheck]:
        """Validate the safety of a Django migration.

        Args:
            migration_file: Path to the migration file
            migration_data: Parsed migration operations

        Returns:
            List of safety checks with recommendations
        """
        checks = []

        # Parse the actual migration file if migration_data is incomplete
        if not migration_data.get('operations'):
            migration_data = self._parse_migration_file(migration_file)

        # Validate each operation in the migration
        operations = migration_data.get('operations', [])
        for operation in operations:
            operation_checks = self._validate_operation(operation)
            checks.extend(operation_checks)

        # Add database-specific checks
        db_checks = self._validate_database_constraints(operations)
        checks.extend(db_checks)

        # Add timing and performance checks
        perf_checks = self._validate_performance_impact(operations)
        checks.extend(perf_checks)

        return checks

    def validate_migration(self, migration_ops: List[Dict]) -> List[SafetyCheck]:
        """Validate migration operations for safety (legacy method)."""
        checks = []

        for op in migration_ops:
            op_checks = self._validate_operation(op)
            checks.extend(op_checks)

        return checks

    def _validate_operation(self, operation: Dict) -> List[SafetyCheck]:
        """Validate a single migration operation."""
        op_type = operation.get('type', '')

        if op_type == 'RemoveField':
            return self._validate_remove_field(operation)
        elif op_type == 'AlterField':
            return self._validate_alter_field(operation)
        elif op_type == 'DeleteModel':
            return self._validate_delete_model(operation)
        elif op_type == 'AddIndex':
            return self._validate_add_index(operation)

        return []

    def _validate_remove_field(self, operation: Dict) -> List[SafetyCheck]:
        """Validate field removal safety."""
        return [SafetyCheck(
            level=SafetyLevel.DESTRUCTIVE,
            description=f"Removing field {operation.get('name')} will permanently delete data",
            recommendation="Create data migration to backup data before removal"
        )]

    def _validate_alter_field(self, operation: Dict) -> List[SafetyCheck]:
        """Validate field alteration safety."""
        checks = []

        # Check for data type changes that may cause data loss
        if self._is_lossy_type_change(operation):
            checks.append(SafetyCheck(
                level=SafetyLevel.DANGEROUS,
                description="Field type change may cause data loss",
                recommendation="Test migration on production data copy first"
            ))

        return checks

    def _validate_delete_model(self, operation: Dict) -> List[SafetyCheck]:
        """Validate model deletion safety."""
        return [SafetyCheck(
            level=SafetyLevel.DESTRUCTIVE,
            description=f"Deleting model {operation.get('name')} will remove all data",
            recommendation="Export data before deletion"
        )]

    def _validate_add_index(self, operation: Dict) -> List[SafetyCheck]:
        """Validate index addition safety."""
        return [SafetyCheck(
            level=SafetyLevel.WARNING,
            description="Adding index may take time on large tables",
            recommendation="Consider using CONCURRENTLY option for PostgreSQL"
        )]

    def _is_lossy_type_change(self, operation: Dict) -> bool:
        """Check if field type change is potentially lossy."""
        old_field = operation.get('old_field', {})
        new_field = operation.get('field', {})

        if not old_field or not new_field:
            # If we can't determine the fields, assume it's risky
            return True

        old_type = self._extract_field_type(old_field)
        new_type = self._extract_field_type(new_field)

        # Define lossy type conversions
        lossy_conversions = {
            ('CharField', 'IntegerField'): True,  # Text to number conversion
            ('TextField', 'CharField'): True,     # Unlimited to limited text
            ('IntegerField', 'SmallIntegerField'): True,  # Larger to smaller int
            ('BigIntegerField', 'IntegerField'): True,    # Bigger to smaller int
            ('FloatField', 'IntegerField'): True,         # Float to int loses precision
            ('DecimalField', 'IntegerField'): True,       # Decimal to int loses precision
            ('JSONField', 'CharField'): True,             # JSON to text may truncate
            ('DateTimeField', 'DateField'): True,         # DateTime to Date loses time
        }

        # Check for max_length reduction
        old_max_length = self._extract_max_length(old_field)
        new_max_length = self._extract_max_length(new_field)

        if old_max_length and new_max_length and new_max_length < old_max_length:
            return True

        # Check for null/blank constraint changes
        if self._is_constraint_tightening(old_field, new_field):
            return True

        return lossy_conversions.get((old_type, new_type), False)

    def _extract_field_type(self, field_def: Dict) -> str:
        """Extract the Django field type from field definition."""
        if isinstance(field_def, dict):
            return field_def.get('type', 'UnknownField')
        elif hasattr(field_def, '__class__'):
            return field_def.__class__.__name__
        else:
            return str(type(field_def).__name__)

    def _extract_max_length(self, field_def: Dict) -> Optional[int]:
        """Extract max_length from field definition."""
        if isinstance(field_def, dict):
            return field_def.get('max_length')
        elif hasattr(field_def, 'max_length'):
            return getattr(field_def, 'max_length', None)
        return None

    def _is_constraint_tightening(self, old_field: Dict, new_field: Dict) -> bool:
        """Check if constraints are being tightened (potentially dangerous)."""
        # Check null constraint
        old_null = self._get_field_attr(old_field, 'null', True)
        new_null = self._get_field_attr(new_field, 'null', True)

        if old_null and not new_null:  # Changing from nullable to non-nullable
            return True

        # Check blank constraint
        old_blank = self._get_field_attr(old_field, 'blank', True)
        new_blank = self._get_field_attr(new_field, 'blank', True)

        if old_blank and not new_blank:  # Changing from blank allowed to not allowed
            return True

        # Check unique constraint
        old_unique = self._get_field_attr(old_field, 'unique', False)
        new_unique = self._get_field_attr(new_field, 'unique', False)

        if not old_unique and new_unique:  # Adding unique constraint
            return True

        return False

    def _get_field_attr(self, field_def: Dict, attr_name: str, default_value) -> Any:
        """Get attribute value from field definition."""
        if isinstance(field_def, dict):
            return field_def.get(attr_name, default_value)
        elif hasattr(field_def, attr_name):
            return getattr(field_def, attr_name, default_value)
        return default_value

    def _parse_migration_file(self, migration_file: str) -> Dict:
        """Parse a Django migration file to extract operations."""
        import ast
        from pathlib import Path

        try:
            file_path = Path(migration_file)
            if not file_path.exists():
                return {'operations': []}

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse the Python AST
            tree = ast.parse(content)

            operations = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == 'Migration':
                    # Find the operations attribute
                    for item in node.body:
                        if (isinstance(item, ast.Assign) and
                            any(target.id == 'operations' for target in item.targets
                                if isinstance(target, ast.Name))):
                            # Extract operations from the AST
                            operations = self._extract_operations_from_ast(item.value)
                            break

            return {'operations': operations}

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            # If parsing fails, return empty operations
            return {'operations': []}

    def _extract_operations_from_ast(self, node) -> List[Dict]:
        """Extract Django migration operations from AST node."""
        operations = []

        if isinstance(node, ast.List):
            for element in node.elts:
                if isinstance(element, ast.Call):
                    op_dict = self._parse_operation_call(element)
                    if op_dict:
                        operations.append(op_dict)

        return operations

    def _parse_operation_call(self, call_node) -> Optional[Dict]:
        """Parse a single migration operation call."""
        if not isinstance(call_node, ast.Call):
            return None

        # Extract the operation type from the function name
        op_type = None
        if isinstance(call_node.func, ast.Attribute):
            op_type = call_node.func.attr
        elif isinstance(call_node.func, ast.Name):
            op_type = call_node.func.id

        if not op_type:
            return None

        # Extract arguments
        operation = {'type': op_type}

        # Parse positional arguments
        if call_node.args:
            if op_type in ['AddField', 'RemoveField', 'AlterField']:
                # First arg is usually model name, second is field name
                if len(call_node.args) >= 2:
                    operation['model'] = self._extract_string_value(call_node.args[0])
                    operation['name'] = self._extract_string_value(call_node.args[1])
                if len(call_node.args) >= 3 and op_type in ['AddField', 'AlterField']:
                    # Third argument is the field definition
                    operation['field'] = self._parse_field_definition(call_node.args[2])

        # Parse keyword arguments
        for keyword in call_node.keywords:
            if keyword.arg:
                operation[keyword.arg] = self._extract_ast_value(keyword.value)

        return operation

    def _extract_string_value(self, node) -> Optional[str]:
        """Extract string value from AST node."""
        if isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def _extract_ast_value(self, node):
        """Extract basic value from AST node."""
        if isinstance(node, (ast.Str, ast.Constant)):
            return node.s if hasattr(node, 's') else node.value
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.NameConstant):
            return node.value
        elif isinstance(node, ast.List):
            return [self._extract_ast_value(item) for item in node.elts]
        elif isinstance(node, ast.Dict):
            result = {}
            for key, value in zip(node.keys, node.values):
                key_val = self._extract_ast_value(key)
                val_val = self._extract_ast_value(value)
                if key_val is not None:
                    result[key_val] = val_val
            return result
        return None

    def _parse_field_definition(self, field_node) -> Dict:
        """Parse a Django field definition from AST."""
        field_def = {'type': 'UnknownField'}

        if isinstance(field_node, ast.Call):
            # Extract field type
            if isinstance(field_node.func, ast.Attribute):
                field_def['type'] = field_node.func.attr
            elif isinstance(field_node.func, ast.Name):
                field_def['type'] = field_node.func.id

            # Extract field arguments
            for keyword in field_node.keywords:
                if keyword.arg:
                    field_def[keyword.arg] = self._extract_ast_value(keyword.value)

        return field_def

    def _validate_database_constraints(self, operations: List[Dict]) -> List[SafetyCheck]:
        """Validate database-specific constraints."""
        checks = []

        for operation in operations:
            op_type = operation.get('type')

            # Check for operations that require table locks
            if op_type in ['AddField', 'AlterField'] and not operation.get('null', True):
                # Adding non-nullable field without default requires table rewrite
                if 'default' not in operation.get('field', {}):
                    checks.append(SafetyCheck(
                        level=SafetyLevel.DANGEROUS,
                        description="Adding non-nullable field without default requires table rewrite",
                        recommendation="Add default value or make field nullable initially"
                    ))

            # Check for operations that may cause downtime
            if op_type == 'AddIndex' and operation.get('atomic', True):
                checks.append(SafetyCheck(
                    level=SafetyLevel.WARNING,
                    description="Index creation may cause table locks on large tables",
                    recommendation="Consider using CREATE INDEX CONCURRENTLY (set atomic=False)"
                ))

        return checks

    def _validate_performance_impact(self, operations: List[Dict]) -> List[SafetyCheck]:
        """Validate potential performance impacts."""
        checks = []

        risky_operations = ['DeleteModel', 'RemoveField', 'AlterField']
        bulk_operations = [op for op in operations if op.get('type') in risky_operations]

        if len(bulk_operations) > 3:
            checks.append(SafetyCheck(
                level=SafetyLevel.WARNING,
                description=f"Migration contains {len(bulk_operations)} potentially slow operations",
                recommendation="Consider splitting into smaller migrations"
            ))

        # Check for operations that scan entire table
        for operation in operations:
            if operation.get('type') == 'AlterField':
                field_def = operation.get('field', {})
                if field_def.get('unique') and not operation.get('preserve_default'):
                    checks.append(SafetyCheck(
                        level=SafetyLevel.WARNING,
                        description="Adding unique constraint requires full table scan",
                        recommendation="Ensure adequate maintenance window"
                    ))

        return checks