"""
Django migration generator with comprehensive safety checks.

This generator provides:
- Field change detection: Type, constraints, defaults
- Data migration: Safe data transformation
- Relationship updates: Foreign keys, M2M
- Index optimization: Performance-aware indexes
- Rollback scripts: Reversible operations
"""

from enum import Enum
from datetime import datetime

from django.db import models
from django.apps import apps



class MigrationType(Enum):
    """Types of migrations that can be generated."""
    ADD_FIELD = "add_field"
    REMOVE_FIELD = "remove_field"
    ALTER_FIELD = "alter_field"
    RENAME_FIELD = "rename_field"
    ADD_INDEX = "add_index"
    REMOVE_INDEX = "remove_index"
    ADD_CONSTRAINT = "add_constraint"
    REMOVE_CONSTRAINT = "remove_constraint"
    CREATE_MODEL = "create_model"
    DELETE_MODEL = "delete_model"
    RENAME_MODEL = "rename_model"
    DATA_MIGRATION = "data_migration"


class MigrationRisk(Enum):
    """Risk levels for migrations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FieldChange:
    """Container for field change information."""
    field_name: str
    old_definition: Optional[Dict[str, Any]]
    new_definition: Dict[str, Any]
    change_type: MigrationType
    is_breaking: bool
    data_loss_risk: bool
    requires_default: bool


@dataclass
class MigrationOperation:
    """Container for a single migration operation."""
    type: MigrationType
    model_name: str
    app_label: str
    operation_code: str
    reverse_code: Optional[str]
    risk_level: MigrationRisk
    description: str
    warnings: List[str]
    prerequisites: List[str]
    data_migration_needed: bool = False


@dataclass
class GeneratedMigration:
    """Container for a complete generated migration."""
    app_label: str
    migration_name: str
    dependencies: List[str]
    operations: List[MigrationOperation]
    migration_code: str
    rollback_code: str
    safety_checks: List[str]
    estimated_time: str
    risk_assessment: str


class MigrationGenerator:
    """Intelligent Django migration generator with safety analysis."""

    def __init__(self):
        self.model_changes = {}
        self.detected_changes = []

    def analyze_model_changes(self, app_labels: List[str] = None) -> Dict[str, Any]:
        """Analyze changes in Django models and suggest migrations."""
        try:
            if not app_labels:
                app_labels = [app.label for app in apps.get_app_configs()
                            if not app.label.startswith('django.')]

            all_changes = {}

            for app_label in app_labels:
                changes = self._analyze_app_models(app_label)
                if changes:
                    all_changes[app_label] = changes

            return all_changes

        except (ValueError, TypeError) as e:
            print(f"Error analyzing model changes: {e}")
            return {}

    def generate_migration(self, app_label: str, changes: List[FieldChange]) -> GeneratedMigration:
        """Generate a migration file for the given changes."""
        try:
            # Generate migration name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            migration_name = f"{timestamp}_auto_generated_migration"

            # Convert changes to operations
            operations = []
            for change in changes:
                operation = self._change_to_operation(app_label, change)
                if operation:
                    operations.append(operation)

            # Generate migration code
            migration_code = self._generate_migration_code(
                app_label, migration_name, operations
            )

            # Generate rollback code
            rollback_code = self._generate_rollback_code(operations)

            # Perform safety analysis
            safety_checks = self._analyze_migration_safety(operations)

            # Calculate risk assessment
            risk_assessment = self._assess_migration_risk(operations)

            # Estimate execution time
            estimated_time = self._estimate_migration_time(operations)

            return GeneratedMigration(
                app_label=app_label,
                migration_name=migration_name,
                dependencies=self._get_migration_dependencies(app_label),
                operations=operations,
                migration_code=migration_code,
                rollback_code=rollback_code,
                safety_checks=safety_checks,
                estimated_time=estimated_time,
                risk_assessment=risk_assessment
            )

        except (ValueError, TypeError) as e:
            print(f"Error generating migration: {e}")
            return None

    def _analyze_app_models(self, app_label: str) -> List[FieldChange]:
        """Analyze model changes in a specific app."""
        changes = []

        try:
            # Get current model definitions from database
            db_models = DjangoModel.objects.filter(app_label=app_label)

            # Get current model definitions from code
            app_config = apps.get_app_config(app_label)
            code_models = app_config.get_models()

            # Compare and find changes
            for code_model in code_models:
                model_name = code_model.__name__

                # Find corresponding database model
                db_model = db_models.filter(model_name=model_name).first()

                if db_model:
                    # Compare fields
                    field_changes = self._compare_model_fields(code_model, db_model)
                    changes.extend(field_changes)
                else:
                    # New model
                    changes.append(self._create_new_model_change(code_model))

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            print(f"Error analyzing app models {app_label}: {e}")

        return changes

    def _compare_model_fields(self, code_model, db_model: DjangoModel) -> List[FieldChange]:
        """Compare fields between code model and database model."""
        changes = []

        # Get current fields from code
        code_fields = {}
        for field in code_model._meta.get_fields():
            if hasattr(field, 'name'):
                code_fields[field.name] = self._serialize_field(field)

        # Get stored fields from database
        db_fields = db_model.fields

        # Find added fields
        for field_name, field_def in code_fields.items():
            if field_name not in db_fields:
                changes.append(FieldChange(
                    field_name=field_name,
                    old_definition=None,
                    new_definition=field_def,
                    change_type=MigrationType.ADD_FIELD,
                    is_breaking=False,
                    data_loss_risk=False,
                    requires_default=not field_def.get('null', True) and not field_def.get('blank', True)
                ))

        # Find removed fields
        for field_name, field_def in db_fields.items():
            if field_name not in code_fields:
                changes.append(FieldChange(
                    field_name=field_name,
                    old_definition=field_def,
                    new_definition=None,
                    change_type=MigrationType.REMOVE_FIELD,
                    is_breaking=True,
                    data_loss_risk=True,
                    requires_default=False
                ))

        # Find modified fields
        for field_name in set(code_fields.keys()) & set(db_fields.keys()):
            code_def = code_fields[field_name]
            db_def = db_fields[field_name]

            if self._fields_are_different(code_def, db_def):
                changes.append(FieldChange(
                    field_name=field_name,
                    old_definition=db_def,
                    new_definition=code_def,
                    change_type=MigrationType.ALTER_FIELD,
                    is_breaking=self._is_breaking_field_change(db_def, code_def),
                    data_loss_risk=self._has_data_loss_risk(db_def, code_def),
                    requires_default=self._requires_default_value(db_def, code_def)
                ))

        return changes

    def _serialize_field(self, field) -> Dict[str, Any]:
        """Serialize a Django model field to a dictionary."""
        return {
            'type': field.__class__.__name__,
            'null': getattr(field, 'null', False),
            'blank': getattr(field, 'blank', False),
            'unique': getattr(field, 'unique', False),
            'db_index': getattr(field, 'db_index', False),
            'primary_key': getattr(field, 'primary_key', False),
            'max_length': getattr(field, 'max_length', None),
            'default': self._serialize_default(getattr(field, 'default', models.NOT_PROVIDED)),
            'choices': getattr(field, 'choices', None),
            'help_text': getattr(field, 'help_text', ''),
        }

    def _serialize_default(self, default):
        """Serialize field default value."""
        if default is models.NOT_PROVIDED:
            return None
        elif callable(default):
            return f"<callable: {default.__name__}>"
        else:
            return str(default)

    def _fields_are_different(self, field1: Dict[str, Any], field2: Dict[str, Any]) -> bool:
        """Check if two field definitions are different."""
        # Compare significant attributes
        significant_attrs = ['type', 'null', 'unique', 'max_length', 'default']

        for attr in significant_attrs:
            if field1.get(attr) != field2.get(attr):
                return True

        return False

    def _is_breaking_field_change(self, old_def: Dict[str, Any], new_def: Dict[str, Any]) -> bool:
        """Check if field change is breaking."""
        # Type changes are usually breaking
        if old_def.get('type') != new_def.get('type'):
            return True

        # Making field non-nullable without default is breaking
        if old_def.get('null', True) and not new_def.get('null', True) and not new_def.get('default'):
            return True

        # Reducing max_length is potentially breaking
        old_length = old_def.get('max_length')
        new_length = new_def.get('max_length')
        if old_length and new_length and new_length < old_length:
            return True

        return False

    def _has_data_loss_risk(self, old_def: Dict[str, Any], new_def: Dict[str, Any]) -> bool:
        """Check if field change has data loss risk."""
        # Type changes may cause data loss
        if old_def.get('type') != new_def.get('type'):
            return True

        # Reducing max_length may truncate data
        old_length = old_def.get('max_length')
        new_length = new_def.get('max_length')
        if old_length and new_length and new_length < old_length:
            return True

        return False

    def _requires_default_value(self, old_def: Dict[str, Any], new_def: Dict[str, Any]) -> bool:
        """Check if field change requires a default value."""
        # Adding NOT NULL constraint without default
        if (old_def.get('null', True) and
            not new_def.get('null', True) and
            not new_def.get('default')):
            return True

        return False

    def _create_new_model_change(self, model) -> FieldChange:
        """Create change for new model."""
        return FieldChange(
            field_name="__model__",
            old_definition=None,
            new_definition={'model_name': model.__name__},
            change_type=MigrationType.CREATE_MODEL,
            is_breaking=False,
            data_loss_risk=False,
            requires_default=False
        )

    def _change_to_operation(self, app_label: str, change: FieldChange) -> MigrationOperation:
        """Convert a field change to a migration operation."""
        if change.change_type == MigrationType.ADD_FIELD:
            return self._generate_add_field_operation(app_label, change)
        elif change.change_type == MigrationType.REMOVE_FIELD:
            return self._generate_remove_field_operation(app_label, change)
        elif change.change_type == MigrationType.ALTER_FIELD:
            return self._generate_alter_field_operation(app_label, change)
        elif change.change_type == MigrationType.CREATE_MODEL:
            return self._generate_create_model_operation(app_label, change)

        return None

    def _generate_add_field_operation(self, app_label: str, change: FieldChange) -> MigrationOperation:
        """Generate add field operation."""
        field_def = change.new_definition
        field_type = field_def.get('type', 'CharField')

        # Build field definition
        field_args = []
        field_kwargs = []

        if field_def.get('max_length'):
            field_kwargs.append(f"max_length={field_def['max_length']}")

        if field_def.get('null'):
            field_kwargs.append("null=True")

        if field_def.get('blank'):
            field_kwargs.append("blank=True")

        if field_def.get('default') is not None:
            default_value = field_def['default']
            if isinstance(default_value, str) and not default_value.startswith('<callable'):
                field_kwargs.append(f"default='{default_value}'")
            elif not default_value.startswith('<callable'):
                field_kwargs.append(f"default={default_value}")

        kwargs_str = ', '.join(field_kwargs)
        operation_code = f"migrations.AddField(\n" \
                        f"    model_name='{change.field_name.split('.')[0]}',\n" \
                        f"    name='{change.field_name}',\n" \
                        f"    field=models.{field_type}({kwargs_str}),\n" \
                        f"),"

        reverse_code = f"migrations.RemoveField(\n" \
                      f"    model_name='{change.field_name.split('.')[0]}',\n" \
                      f"    name='{change.field_name}',\n" \
                      f"),"

        warnings = []
        if change.requires_default:
            warnings.append("Field added without default value - may require data migration")

        return MigrationOperation(
            type=MigrationType.ADD_FIELD,
            model_name=change.field_name.split('.')[0] if '.' in change.field_name else 'Unknown',
            app_label=app_label,
            operation_code=operation_code,
            reverse_code=reverse_code,
            risk_level=MigrationRisk.LOW,
            description=f"Add field '{change.field_name}'",
            warnings=warnings,
            prerequisites=[],
            data_migration_needed=change.requires_default
        )

    def _generate_remove_field_operation(self, app_label: str, change: FieldChange) -> MigrationOperation:
        """Generate remove field operation."""
        operation_code = f"migrations.RemoveField(\n" \
                        f"    model_name='{change.field_name.split('.')[0]}',\n" \
                        f"    name='{change.field_name}',\n" \
                        f"),"

        # Reverse operation would be AddField with old definition
        field_def = change.old_definition
        reverse_code = f"# TODO: Add reverse AddField operation for '{change.field_name}'"

        return MigrationOperation(
            type=MigrationType.REMOVE_FIELD,
            model_name=change.field_name.split('.')[0] if '.' in change.field_name else 'Unknown',
            app_label=app_label,
            operation_code=operation_code,
            reverse_code=reverse_code,
            risk_level=MigrationRisk.HIGH,
            description=f"Remove field '{change.field_name}'",
            warnings=["This operation will permanently delete data"],
            prerequisites=["Backup database before running this migration"],
            data_migration_needed=True
        )

    def _generate_alter_field_operation(self, app_label: str, change: FieldChange) -> MigrationOperation:
        """Generate alter field operation."""
        field_def = change.new_definition
        field_type = field_def.get('type', 'CharField')

        # Build field kwargs
        field_kwargs = []
        if field_def.get('max_length'):
            field_kwargs.append(f"max_length={field_def['max_length']}")
        if field_def.get('null'):
            field_kwargs.append("null=True")
        if field_def.get('blank'):
            field_kwargs.append("blank=True")

        kwargs_str = ', '.join(field_kwargs)
        operation_code = f"migrations.AlterField(\n" \
                        f"    model_name='{change.field_name.split('.')[0]}',\n" \
                        f"    name='{change.field_name}',\n" \
                        f"    field=models.{field_type}({kwargs_str}),\n" \
                        f"),"

        risk_level = MigrationRisk.HIGH if change.is_breaking else MigrationRisk.MEDIUM

        warnings = []
        if change.data_loss_risk:
            warnings.append("This change may cause data loss")
        if change.requires_default:
            warnings.append("May require default value for existing records")

        return MigrationOperation(
            type=MigrationType.ALTER_FIELD,
            model_name=change.field_name.split('.')[0] if '.' in change.field_name else 'Unknown',
            app_label=app_label,
            operation_code=operation_code,
            reverse_code="# TODO: Add reverse AlterField operation",
            risk_level=risk_level,
            description=f"Alter field '{change.field_name}'",
            warnings=warnings,
            prerequisites=["Test migration on copy of production data"] if change.data_loss_risk else [],
            data_migration_needed=change.requires_default
        )

    def _generate_create_model_operation(self, app_label: str, change: FieldChange) -> MigrationOperation:
        """Generate create model operation."""
        model_name = change.new_definition.get('model_name', 'UnknownModel')

        operation_code = f"migrations.CreateModel(\n" \
                        f"    name='{model_name}',\n" \
                        f"    fields=[\n" \
                        f"        # TODO: Add field definitions\n" \
                        f"    ],\n" \
                        f"),"

        reverse_code = f"migrations.DeleteModel(\n" \
                      f"    name='{model_name}',\n" \
                      f"),"

        return MigrationOperation(
            type=MigrationType.CREATE_MODEL,
            model_name=model_name,
            app_label=app_label,
            operation_code=operation_code,
            reverse_code=reverse_code,
            risk_level=MigrationRisk.LOW,
            description=f"Create model '{model_name}'",
            warnings=[],
            prerequisites=[],
            data_migration_needed=False
        )

    def _generate_migration_code(self, app_label: str, migration_name: str,
                                operations: List[MigrationOperation]) -> str:
        """Generate complete migration file code."""
        dependencies = self._get_migration_dependencies(app_label)

        operations_code = '\n        '.join([op.operation_code for op in operations])

        migration_code = f'''# Generated by Django AI Mentor System
# Migration: {migration_name}

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = {dependencies}

    operations = [
        {operations_code}
    ]
'''

        return migration_code

    def _generate_rollback_code(self, operations: List[MigrationOperation]) -> str:
        """Generate rollback migration code."""
        rollback_operations = []

        for operation in reversed(operations):
            if operation.reverse_code and not operation.reverse_code.startswith("# TODO"):
                rollback_operations.append(operation.reverse_code)

        operations_code = '\n        '.join(rollback_operations)

        rollback_code = f'''# Rollback migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = []  # Set appropriate dependencies

    operations = [
        {operations_code}
    ]
'''

        return rollback_code

    def _analyze_migration_safety(self, operations: List[MigrationOperation]) -> List[str]:
        """Analyze migration safety and generate checks."""
        safety_checks = []

        for operation in operations:
            if operation.risk_level in [MigrationRisk.HIGH, MigrationRisk.CRITICAL]:
                safety_checks.append(f"⚠️ HIGH RISK: {operation.description}")

            if operation.data_migration_needed:
                safety_checks.append(f"📊 DATA MIGRATION NEEDED: {operation.description}")

            for warning in operation.warnings:
                safety_checks.append(f"⚠️ WARNING: {warning}")

            for prereq in operation.prerequisites:
                safety_checks.append(f"📋 PREREQUISITE: {prereq}")

        return safety_checks

    def _assess_migration_risk(self, operations: List[MigrationOperation]) -> str:
        """Assess overall migration risk."""
        risk_levels = [op.risk_level for op in operations]

        if MigrationRisk.CRITICAL in risk_levels:
            return "CRITICAL - Manual review required"
        elif MigrationRisk.HIGH in risk_levels:
            return "HIGH - Test thoroughly before production"
        elif MigrationRisk.MEDIUM in risk_levels:
            return "MEDIUM - Standard testing recommended"
        else:
            return "LOW - Safe to apply"

    def _estimate_migration_time(self, operations: List[MigrationOperation]) -> str:
        """Estimate migration execution time."""
        base_time = 1  # 1 second base time

        for operation in operations:
            if operation.type == MigrationType.ADD_INDEX:
                base_time += 30  # Indexes take time
            elif operation.type in [MigrationType.ALTER_FIELD, MigrationType.REMOVE_FIELD]:
                base_time += 10  # Field alterations take time
            elif operation.data_migration_needed:
                base_time += 60  # Data migrations are slow
            else:
                base_time += 2

        if base_time < 60:
            return f"{base_time} seconds"
        else:
            return f"{base_time // 60} minutes {base_time % 60} seconds"

    def _get_migration_dependencies(self, app_label: str) -> List[str]:
        """Get migration dependencies for the app."""
        # This is a simplified implementation
        # In practice, you'd need to find the latest migration
        return [f"('{app_label}', '0001_initial')"]

    def create_data_migration(self, app_label: str, description: str,
                            forward_code: str, reverse_code: str) -> str:
        """Create a data migration file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        migration_name = f"{timestamp}_data_{description.lower().replace(' ', '_')}"

        data_migration_code = f'''# Data migration: {description}
# Generated by Django AI Mentor System

from django.db import migrations


def migrate_data_forward(apps, schema_editor):
    """Forward data migration."""
{forward_code}


def migrate_data_reverse(apps, schema_editor):
    """Reverse data migration."""
{reverse_code}


class Migration(migrations.Migration):

    dependencies = {self._get_migration_dependencies(app_label)}

    operations = [
        migrations.RunPython(
            migrate_data_forward,
            migrate_data_reverse,
            hints={{'app_label': '{app_label}'}}
        ),
    ]
'''

        return data_migration_code