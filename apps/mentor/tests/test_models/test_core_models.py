"""
Tests for core AI Mentor models.
"""

from django.db import IntegrityError

)
from apps.mentor.tests.base import MentorTestCase


class IndexedFileModelTest(MentorTestCase):
    """Test the IndexedFile model."""

    def test_create_indexed_file(self):
        """Test creating an indexed file."""
        file_obj = self.create_test_file(
            path='apps/test/models.py',
            content='class TestModel: pass',
            language='python'
        )

        self.assertEqual(file_obj.path, 'apps/test/models.py')
        self.assertEqual(file_obj.language, 'python')
        self.assertFalse(file_obj.is_test)

    def test_unique_path_constraint(self):
        """Test that file paths must be unique."""
        self.create_test_file('apps/test/models.py', 'content1')

        with self.assertRaises(IntegrityError):
            self.create_test_file('apps/test/models.py', 'content2')

    def test_is_fresh_property(self):
        """Test the is_fresh property."""
        # Create a file with current timestamp
        import time
        current_time = int(time.time())

        file_obj = self.create_test_file(
            path='apps/test/models.py',
            content='test',
            mtime=current_time
        )

        # Mock file system interaction
        from unittest.mock import patch, MagicMock

        # Mock file exists and has matching mtime
        mock_stat = MagicMock()
        mock_stat.st_mtime = current_time

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat', return_value=mock_stat):
            self.assertTrue(file_obj.is_fresh)

        # Mock file with different mtime
        mock_stat.st_mtime = current_time + 100
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat', return_value=mock_stat):
            self.assertFalse(file_obj.is_fresh)

        # Mock file doesn't exist
        with patch('pathlib.Path.exists', return_value=False):
            self.assertFalse(file_obj.is_fresh)

    def test_string_representation(self):
        """Test string representation."""
        file_obj = self.create_test_file('apps/test/models.py', 'test')
        self.assertEqual(str(file_obj), 'apps/test/models.py')


class CodeSymbolModelTest(MentorTestCase):
    """Test the CodeSymbol model."""

    def setUp(self):
        super().setUp()
        self.file_obj = self.create_test_file('apps/test/models.py', 'test content')

    def test_create_code_symbol(self):
        """Test creating a code symbol."""
        symbol = self.create_test_symbol(
            file_obj=self.file_obj,
            name='TestClass',
            kind='class',
            docstring='A test class',
            signature='class TestClass:'
        )

        self.assertEqual(symbol.name, 'TestClass')
        self.assertEqual(symbol.kind, 'class')
        self.assertEqual(symbol.docstring, 'A test class')
        self.assertEqual(symbol.file, self.file_obj)

    def test_full_name_property(self):
        """Test the full_name property."""
        # Symbol without parents
        symbol = self.create_test_symbol(
            file_obj=self.file_obj,
            name='function_name',
            parents=[]
        )
        self.assertEqual(symbol.full_name, 'function_name')

        # Symbol with parents
        symbol_with_parents = self.create_test_symbol(
            file_obj=self.file_obj,
            name='method_name',
            parents=['ClassName', 'InnerClass']
        )
        self.assertEqual(symbol_with_parents.full_name, 'ClassName.InnerClass.method_name')

    def test_symbol_kinds(self):
        """Test different symbol kinds."""
        kinds = ['class', 'function', 'method', 'variable', 'property', 'constant']

        for kind in kinds:
            symbol = self.create_test_symbol(
                file_obj=self.file_obj,
                name=f'test_{kind}',
                kind=kind
            )
            self.assertEqual(symbol.kind, kind)

    def test_string_representation(self):
        """Test string representation."""
        symbol = self.create_test_symbol(
            file_obj=self.file_obj,
            name='TestFunction',
            kind='function'
        )
        expected = f"{self.file_obj.path}:TestFunction (function)"
        self.assertEqual(str(symbol), expected)

    def test_cascade_delete(self):
        """Test that symbols are deleted when file is deleted."""
        symbol = self.create_test_symbol(self.file_obj, 'test_symbol')
        symbol_id = symbol.id

        self.file_obj.delete()

        self.assertEqual(CodeSymbol.objects.filter(id=symbol_id).count(), 0)


class SymbolRelationModelTest(MentorTestCase):
    """Test the SymbolRelation model."""

    def setUp(self):
        super().setUp()
        self.file_obj = self.create_test_file('apps/test/models.py', 'test')
        self.source_symbol = self.create_test_symbol(self.file_obj, 'SourceClass', 'class')
        self.target_symbol = self.create_test_symbol(self.file_obj, 'TargetClass', 'class')

    def test_create_relation(self):
        """Test creating a symbol relation."""
        relation = self.create_test_relation(
            source=self.source_symbol,
            target=self.target_symbol,
            kind='inherit'
        )

        self.assertEqual(relation.source, self.source_symbol)
        self.assertEqual(relation.target, self.target_symbol)
        self.assertEqual(relation.kind, 'inherit')

    def test_relation_kinds(self):
        """Test different relation kinds."""
        kinds = ['import', 'call', 'inherit', 'serialize', 'reference', 'dependency']

        for kind in kinds:
            relation = SymbolRelation.objects.create(
                source=self.source_symbol,
                target=self.target_symbol,
                kind=kind,
                line_number=10 + len(kinds)  # Ensure uniqueness
            )
            self.assertEqual(relation.kind, kind)

    def test_unique_constraint(self):
        """Test unique constraint on (source, target, kind)."""
        SymbolRelation.objects.create(
            source=self.source_symbol,
            target=self.target_symbol,
            kind='call'
        )

        # Should raise error for duplicate relation
        with self.assertRaises(IntegrityError):
            SymbolRelation.objects.create(
                source=self.source_symbol,
                target=self.target_symbol,
                kind='call'
            )

    def test_string_representation(self):
        """Test string representation."""
        relation = self.create_test_relation(
            source=self.source_symbol,
            target=self.target_symbol,
            kind='call'
        )
        expected = "SourceClass --call--> TargetClass"
        self.assertEqual(str(relation), expected)


class IndexMetadataModelTest(MentorTestCase):
    """Test the IndexMetadata model."""

    def test_get_set_value(self):
        """Test getting and setting metadata values."""
        # Test setting new value
        IndexMetadata.set_value('test_key', 'test_value')
        self.assertEqual(IndexMetadata.get_value('test_key'), 'test_value')

        # Test updating existing value
        IndexMetadata.set_value('test_key', 'updated_value')
        self.assertEqual(IndexMetadata.get_value('test_key'), 'updated_value')

        # Test getting non-existent key
        self.assertIsNone(IndexMetadata.get_value('non_existent'))

        # Test with default value
        self.assertEqual(
            IndexMetadata.get_value('non_existent', 'default'),
            'default'
        )

    def test_commit_tracking(self):
        """Test commit SHA tracking."""
        # Initially no commit
        self.assertIsNone(IndexMetadata.get_indexed_commit())

        # Set commit
        IndexMetadata.set_indexed_commit('abc123def456')
        self.assertEqual(IndexMetadata.get_indexed_commit(), 'abc123def456')

        # Verify timestamp is also set
        timestamp = IndexMetadata.get_value('index_updated_at')
        self.assertIsNotNone(timestamp)

    def test_get_index_stats(self):
        """Test getting index statistics."""
        # Create some test data
        file_obj = self.create_test_file('apps/test/models.py', 'content')
        self.create_test_symbol(file_obj, 'TestClass', 'class')

        IndexMetadata.set_indexed_commit('test_commit')

        stats = IndexMetadata.get_index_stats()

        self.assertIn('files', stats)
        self.assertIn('symbols', stats)
        self.assertIn('relations', stats)
        self.assertIn('indexed_commit', stats)

        self.assertEqual(stats['files'], 1)
        self.assertEqual(stats['symbols'], 1)
        self.assertEqual(stats['indexed_commit'], 'test_commit')

    def test_string_representation(self):
        """Test string representation."""
        IndexMetadata.set_value('test_key', 'a very long value that should be truncated')
        metadata = IndexMetadata.objects.get(key='test_key')

        str_repr = str(metadata)
        self.assertTrue(str_repr.startswith('test_key: a very long value that should be trunca'))
        self.assertTrue(str_repr.endswith('...'))


class DjangoModelModelTest(MentorTestCase):
    """Test the DjangoModel model."""

    def setUp(self):
        super().setUp()
        self.file_obj = self.create_test_file('apps/test/models.py', 'model content')

    def test_create_django_model(self):
        """Test creating a Django model record."""
        fields = {
            'name': {'type': 'CharField', 'max_length': 100},
            'email': {'type': 'EmailField'},
            'created_at': {'type': 'DateTimeField', 'auto_now_add': True}
        }

        model = DjangoModel.objects.create(
            app_label='test_app',
            model_name='User',
            fields=fields,
            db_table='test_users',
            file=self.file_obj,
            line_number=10
        )

        self.assertEqual(model.app_label, 'test_app')
        self.assertEqual(model.model_name, 'User')
        self.assertEqual(model.db_table, 'test_users')
        self.assertEqual(model.fields, fields)

    def test_field_names_property(self):
        """Test the field_names property."""
        fields = {
            'name': {'type': 'CharField'},
            'email': {'type': 'EmailField'},
            'created_at': {'type': 'DateTimeField'}
        }

        model = DjangoModel.objects.create(
            app_label='test_app',
            model_name='User',
            fields=fields,
            file=self.file_obj,
            line_number=10
        )

        field_names = model.field_names
        self.assertEqual(set(field_names), {'name', 'email', 'created_at'})

        # Test with empty fields
        empty_model = DjangoModel.objects.create(
            app_label='test_app',
            model_name='EmptyModel',
            fields={},
            file=self.file_obj,
            line_number=20
        )
        self.assertEqual(empty_model.field_names, [])

    def test_unique_constraint(self):
        """Test unique constraint on (app_label, model_name)."""
        DjangoModel.objects.create(
            app_label='test_app',
            model_name='User',
            file=self.file_obj,
            line_number=10
        )

        # Should raise error for duplicate model
        with self.assertRaises(IntegrityError):
            DjangoModel.objects.create(
                app_label='test_app',
                model_name='User',
                file=self.file_obj,
                line_number=20
            )

    def test_string_representation(self):
        """Test string representation."""
        model = DjangoModel.objects.create(
            app_label='test_app',
            model_name='User',
            file=self.file_obj,
            line_number=10
        )
        self.assertEqual(str(model), 'test_app.User')


class MentorTestCaseModelTest(MentorTestCase):
    """Test the TestCase model."""

    def setUp(self):
        super().setUp()
        self.file_obj = self.create_test_file('apps/test/test_models.py', 'test content')

    def test_create_test_case(self):
        """Test creating a test case record."""
        test = MentorTestCase.objects.create(
            node_id='apps/test/test_models.py::TestClass::test_method',
            file=self.file_obj,
            class_name='TestClass',
            method_name='test_method',
            markers=['unit', 'django_db']
        )

        self.assertEqual(test.node_id, 'apps/test/test_models.py::TestClass::test_method')
        self.assertEqual(test.class_name, 'TestClass')
        self.assertEqual(test.method_name, 'test_method')
        self.assertEqual(test.markers, ['unit', 'django_db'])

    def test_is_flaky_property(self):
        """Test the is_flaky property."""
        # Non-flaky test
        test = MentorTestCase.objects.create(
            node_id='test::reliable',
            file=self.file_obj,
            method_name='test_reliable',
            success_rate=0.98
        )
        self.assertFalse(test.is_flaky)

        # Flaky test
        flaky_test = MentorTestCase.objects.create(
            node_id='test::flaky',
            file=self.file_obj,
            method_name='test_flaky',
            success_rate=0.80
        )
        self.assertTrue(flaky_test.is_flaky)

    def test_is_slow_property(self):
        """Test the is_slow property."""
        # Fast test
        test = MentorTestCase.objects.create(
            node_id='test::fast',
            file=self.file_obj,
            method_name='test_fast',
            avg_execution_time=1.5
        )
        self.assertFalse(test.is_slow)

        # Slow test
        slow_test = MentorTestCase.objects.create(
            node_id='test::slow',
            file=self.file_obj,
            method_name='test_slow',
            avg_execution_time=10.0
        )
        self.assertTrue(slow_test.is_slow)

    def test_string_representation(self):
        """Test string representation."""
        test = MentorTestCase.objects.create(
            node_id='apps/test/test_models.py::TestClass::test_method',
            file=self.file_obj,
            method_name='test_method'
        )
        self.assertEqual(str(test), 'apps/test/test_models.py::TestClass::test_method')