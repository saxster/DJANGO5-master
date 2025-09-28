"""
Tests for migration safety validation.
"""

import tempfile
from pathlib import Path
from django.test import TestCase

    MigrationSafetyValidator, SafetyCheck, SafetyLevel
)


class TestMigrationSafetyValidator(TestCase):
    """Test migration safety validation."""

    def setUp(self):
        self.validator = MigrationSafetyValidator()

    def test_validate_remove_field_operation(self):
        """Test validation of RemoveField operation."""
        operation = {
            'type': 'RemoveField',
            'model': 'User',
            'name': 'old_field'
        }

        checks = self.validator._validate_operation(operation)

        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].level, SafetyLevel.DESTRUCTIVE)
        self.assertIn('permanently delete data', checks[0].description)

    def test_validate_alter_field_lossy_change(self):
        """Test validation of lossy field type changes."""
        operation = {
            'type': 'AlterField',
            'model': 'User',
            'name': 'age',
            'old_field': {'type': 'CharField', 'max_length': 100},
            'field': {'type': 'IntegerField'}
        }

        checks = self.validator._validate_operation(operation)

        self.assertGreater(len(checks), 0)
        # Should detect lossy conversion from CharField to IntegerField
        dangerous_checks = [c for c in checks if c.level == SafetyLevel.DANGEROUS]
        self.assertGreater(len(dangerous_checks), 0)

    def test_validate_delete_model_operation(self):
        """Test validation of DeleteModel operation."""
        operation = {
            'type': 'DeleteModel',
            'name': 'OldModel'
        }

        checks = self.validator._validate_operation(operation)

        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].level, SafetyLevel.DESTRUCTIVE)
        self.assertIn('remove all data', checks[0].description)

    def test_validate_add_index_operation(self):
        """Test validation of AddIndex operation."""
        operation = {
            'type': 'AddIndex',
            'model': 'User',
            'fields': ['email']
        }

        checks = self.validator._validate_operation(operation)

        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].level, SafetyLevel.WARNING)
        self.assertIn('large tables', checks[0].description)

    def test_is_lossy_type_change_detection(self):
        """Test detection of lossy type changes."""
        # Test lossy conversion
        operation_lossy = {
            'old_field': {'type': 'CharField'},
            'field': {'type': 'IntegerField'}
        }
        self.assertTrue(self.validator._is_lossy_type_change(operation_lossy))

        # Test safe conversion
        operation_safe = {
            'old_field': {'type': 'IntegerField'},
            'field': {'type': 'BigIntegerField'}
        }
        self.assertFalse(self.validator._is_lossy_type_change(operation_safe))

        # Test max_length reduction
        operation_length = {
            'old_field': {'type': 'CharField', 'max_length': 200},
            'field': {'type': 'CharField', 'max_length': 100}
        }
        self.assertTrue(self.validator._is_lossy_type_change(operation_length))

    def test_constraint_tightening_detection(self):
        """Test detection of constraint tightening."""
        # Test null constraint tightening
        old_field = {'type': 'CharField', 'null': True}
        new_field = {'type': 'CharField', 'null': False}
        self.assertTrue(self.validator._is_constraint_tightening(old_field, new_field))

        # Test unique constraint addition
        old_field = {'type': 'CharField', 'unique': False}
        new_field = {'type': 'CharField', 'unique': True}
        self.assertTrue(self.validator._is_constraint_tightening(old_field, new_field))

        # Test safe constraint change
        old_field = {'type': 'CharField', 'null': False}
        new_field = {'type': 'CharField', 'null': True}
        self.assertFalse(self.validator._is_constraint_tightening(old_field, new_field))

    def test_parse_migration_file(self):
        """Test parsing of actual migration files."""
        migration_content = '''
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(max_length=50, unique=True),
        ),
    ]
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(migration_content)
            temp_file = f.name

        try:
            migration_data = self.validator._parse_migration_file(temp_file)

            self.assertIn('operations', migration_data)
            operations = migration_data['operations']
            self.assertEqual(len(operations), 2)

            # Check first operation
            add_field_op = operations[0]
            self.assertEqual(add_field_op['type'], 'AddField')
            self.assertEqual(add_field_op['model'], 'user')
            self.assertEqual(add_field_op['name'], 'email_verified')

            # Check second operation
            alter_field_op = operations[1]
            self.assertEqual(alter_field_op['type'], 'AlterField')
            self.assertEqual(alter_field_op['model'], 'user')
            self.assertEqual(alter_field_op['name'], 'username')

        finally:
            Path(temp_file).unlink()

    def test_parse_migration_file_not_found(self):
        """Test parsing non-existent migration file."""
        migration_data = self.validator._parse_migration_file("/nonexistent/file.py")

        self.assertEqual(migration_data, {'operations': []})

    def test_validate_database_constraints(self):
        """Test database constraint validation."""
        operations = [
            {
                'type': 'AddField',
                'model': 'User',
                'name': 'required_field',
                'field': {'type': 'CharField', 'null': False}
                # No default value - should trigger warning
            },
            {
                'type': 'AddIndex',
                'model': 'User',
                'fields': ['email'],
                'atomic': True
            }
        ]

        checks = self.validator._validate_database_constraints(operations)

        self.assertGreater(len(checks), 0)

        # Should have dangerous check for non-nullable field without default
        dangerous_checks = [c for c in checks if c.level == SafetyLevel.DANGEROUS]
        self.assertGreater(len(dangerous_checks), 0)
        self.assertIn('table rewrite', dangerous_checks[0].description)

        # Should have warning for atomic index creation
        warning_checks = [c for c in checks if c.level == SafetyLevel.WARNING]
        self.assertGreater(len(warning_checks), 0)

    def test_validate_performance_impact(self):
        """Test performance impact validation."""
        # Create migration with many risky operations
        operations = [
            {'type': 'DeleteModel', 'name': 'Model1'},
            {'type': 'RemoveField', 'model': 'User', 'name': 'field1'},
            {'type': 'AlterField', 'model': 'User', 'name': 'field2'},
            {'type': 'DeleteModel', 'name': 'Model2'},
        ]

        checks = self.validator._validate_performance_impact(operations)

        self.assertGreater(len(checks), 0)

        # Should warn about bulk operations
        bulk_warnings = [c for c in checks
                        if 'potentially slow operations' in c.description]
        self.assertGreater(len(bulk_warnings), 0)

    def test_extract_field_type(self):
        """Test field type extraction."""
        # Test dict format
        field_dict = {'type': 'CharField'}
        self.assertEqual(
            self.validator._extract_field_type(field_dict),
            'CharField'
        )

        # Test object format (mock)
        field_obj = MagicMock()
        field_obj.__class__.__name__ = 'IntegerField'
        self.assertEqual(
            self.validator._extract_field_type(field_obj),
            'IntegerField'
        )

    def test_extract_max_length(self):
        """Test max_length extraction."""
        # Test dict format
        field_dict = {'type': 'CharField', 'max_length': 100}
        self.assertEqual(
            self.validator._extract_max_length(field_dict),
            100
        )

        # Test dict without max_length
        field_dict_no_length = {'type': 'TextField'}
        self.assertIsNone(
            self.validator._extract_max_length(field_dict_no_length)
        )

    def test_get_field_attr(self):
        """Test field attribute extraction."""
        field_dict = {'type': 'CharField', 'null': True, 'blank': False}

        self.assertEqual(
            self.validator._get_field_attr(field_dict, 'null', False),
            True
        )

        self.assertEqual(
            self.validator._get_field_attr(field_dict, 'unique', False),
            False  # Uses default since not present
        )

    def test_validate_migration_safety_integration(self):
        """Test complete migration safety validation."""
        migration_content = '''
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.RemoveField(
            model_name='user',
            name='deprecated_field',
        ),
        migrations.AddField(
            model_name='user',
            name='required_field',
            field=models.CharField(max_length=100, null=False),
        ),
    ]
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(migration_content)
            temp_file = f.name

        try:
            checks = self.validator.validate_migration_safety(temp_file, {})

            self.assertGreater(len(checks), 0)

            # Should have destructive check for RemoveField
            destructive_checks = [c for c in checks if c.level == SafetyLevel.DESTRUCTIVE]
            self.assertGreater(len(destructive_checks), 0)

            # Should have dangerous check for non-nullable field without default
            dangerous_checks = [c for c in checks if c.level == SafetyLevel.DANGEROUS]
            self.assertGreater(len(dangerous_checks), 0)

        finally:
            Path(temp_file).unlink()