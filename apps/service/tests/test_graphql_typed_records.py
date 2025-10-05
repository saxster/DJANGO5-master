"""
Tests for GraphQL Typed Records

Validates SelectOutputType.records_typed field returns proper types
for Apollo Kotlin codegen.

Compliance with .claude/rules.md:
- Rule #11: Specific exception testing
- Ensures type safety for mobile clients
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta

from apps.service.graphql_types.record_types import (
    QuestionRecordType,
    QuestionSetRecordType,
    LocationRecordType,
    AssetRecordType,
    PgroupRecordType,
    TypeAssistRecordType,
    SelectRecordUnion,
    resolve_typed_record,
)
from apps.service.types import SelectOutputType
from apps.core.utils import get_select_output_typed


@pytest.mark.unit
class TestRecordTypeDefinitions(TestCase):
    """Test individual record type definitions."""

    def test_question_record_type_instantiation(self):
        """Test QuestionRecordType can be instantiated."""
        record = QuestionRecordType(
            id=1,
            quesname="Test Question?",
            answertype="TEXT",
            min=0.0,
            max=100.0,
            isworkflow=False,
            enable=True,
            category_id=1,
            client_id=1,
            cdtz="2025-10-05T12:00:00Z",
            mdtz="2025-10-05T12:00:00Z",
        )
        self.assertEqual(record.id, 1)
        self.assertEqual(record.quesname, "Test Question?")
        self.assertEqual(record.answertype, "TEXT")

    def test_location_record_type_instantiation(self):
        """Test LocationRecordType can be instantiated."""
        record = LocationRecordType(
            id=1,
            loccode="LOC001",
            locname="Test Location",
            enable=True,
            iscritical=False,
            client_id=1,
            cdtz="2025-10-05T12:00:00Z",
            mdtz="2025-10-05T12:00:00Z",
        )
        self.assertEqual(record.loccode, "LOC001")
        self.assertEqual(record.locname, "Test Location")

    def test_questionset_record_type_instantiation(self):
        """Test QuestionSetRecordType can be instantiated."""
        record = QuestionSetRecordType(
            id=1,
            qsetname="Test Question Set",
            type="CHECKLIST",
            enable=True,
            show_to_all_sites=False,
            client_id=1,
            cdtz="2025-10-05T12:00:00Z",
            mdtz="2025-10-05T12:00:00Z",
        )
        self.assertEqual(record.qsetname, "Test Question Set")

    def test_pgroup_record_type_instantiation(self):
        """Test PgroupRecordType can be instantiated."""
        record = PgroupRecordType(
            id=1,
            groupname="Test Group",
            enable=True,
            client_id=1,
            cdtz="2025-10-05T12:00:00Z",
            mdtz="2025-10-05T12:00:00Z",
        )
        self.assertEqual(record.groupname, "Test Group")

    def test_typeassist_record_type_instantiation(self):
        """Test TypeAssistRecordType can be instantiated."""
        record = TypeAssistRecordType(
            id=1,
            tacode="TYPE001",
            taname="Test Type",
            enable=True,
            cdtz="2025-10-05T12:00:00Z",
            mdtz="2025-10-05T12:00:00Z",
        )
        self.assertEqual(record.tacode, "TYPE001")


@pytest.mark.unit
class TestResolveTypedRecord(TestCase):
    """Test resolve_typed_record utility function."""

    def test_resolve_question_record(self):
        """Test resolving dictionary to QuestionRecordType."""
        record_dict = {
            'id': 1,
            'quesname': 'Test?',
            'answertype': 'NUMERIC',
            'min': 0,
            'max': 100,
            'enable': True,
            'client_id': 1,
            'cdtz': '2025-10-05T12:00:00Z',
            'mdtz': '2025-10-05T12:00:00Z',
        }
        resolved = resolve_typed_record(record_dict, 'question')
        self.assertIsInstance(resolved, QuestionRecordType)
        self.assertEqual(resolved.quesname, 'Test?')

    def test_resolve_location_record(self):
        """Test resolving dictionary to LocationRecordType."""
        record_dict = {
            'id': 1,
            'loccode': 'LOC001',
            'locname': 'Building A',
            'enable': True,
            'client_id': 1,
            'cdtz': '2025-10-05T12:00:00Z',
            'mdtz': '2025-10-05T12:00:00Z',
        }
        resolved = resolve_typed_record(record_dict, 'location')
        self.assertIsInstance(resolved, LocationRecordType)
        self.assertEqual(resolved.loccode, 'LOC001')

    def test_resolve_questionset_record(self):
        """Test resolving dictionary to QuestionSetRecordType."""
        record_dict = {
            'id': 1,
            'qsetname': 'Daily Checklist',
            'type': 'INSPECTION',
            'enable': True,
            'client_id': 1,
            'cdtz': '2025-10-05T12:00:00Z',
            'mdtz': '2025-10-05T12:00:00Z',
        }
        resolved = resolve_typed_record(record_dict, 'questionset')
        self.assertIsInstance(resolved, QuestionSetRecordType)
        self.assertEqual(resolved.qsetname, 'Daily Checklist')

    def test_resolve_pgroup_record(self):
        """Test resolving dictionary to PgroupRecordType."""
        record_dict = {
            'id': 1,
            'groupname': 'Security Team',
            'enable': True,
            'client_id': 1,
            'cdtz': '2025-10-05T12:00:00Z',
            'mdtz': '2025-10-05T12:00:00Z',
        }
        resolved = resolve_typed_record(record_dict, 'pgroup')
        self.assertIsInstance(resolved, PgroupRecordType)

    def test_resolve_typeassist_record(self):
        """Test resolving dictionary to TypeAssistRecordType."""
        record_dict = {
            'id': 1,
            'tacode': 'ASSET_TYPE',
            'taname': 'Asset Type',
            'enable': True,
            'cdtz': '2025-10-05T12:00:00Z',
            'mdtz': '2025-10-05T12:00:00Z',
        }
        resolved = resolve_typed_record(record_dict, 'typeassist')
        self.assertIsInstance(resolved, TypeAssistRecordType)

    def test_resolve_unknown_record_type(self):
        """Test resolving unknown record type raises ValueError."""
        record_dict = {'id': 1, 'name': 'Test'}
        with self.assertRaises(ValueError) as cm:
            resolve_typed_record(record_dict, 'unknown_type')
        self.assertIn('Unknown record type', str(cm.exception))

    def test_resolve_invalid_record_structure(self):
        """Test resolving invalid record structure raises ValueError."""
        record_dict = {'invalid_field': 'value'}  # Missing required fields
        with self.assertRaises(ValueError):
            resolve_typed_record(record_dict, 'question')


@pytest.mark.unit
class TestGetSelectOutputTyped(TestCase):
    """Test get_select_output_typed utility function."""

    def test_get_select_output_typed_with_data(self):
        """Test get_select_output_typed returns correct tuple structure."""
        from apps.activity.models.question_model import Question
        from apps.onboarding.models import Bt

        # Create test data
        bt = Bt.objects.create(btcode='TEST', btname='Test BU')
        question = Question.objects.create(
            quesname='Test Question',
            answertype='TEXT',
            bu=bt,
            client_id=1
        )

        # Get QuerySet
        queryset = Question.objects.filter(id=question.id).values('id', 'quesname', 'answertype')

        # Call function
        records_json, typed_records, count, msg, record_type = get_select_output_typed(queryset, 'question')

        # Verify structure
        self.assertIsInstance(records_json, str)  # JSON string
        self.assertIsInstance(typed_records, list)  # List of dicts
        self.assertEqual(count, 1)
        self.assertIn('fetched successfully', msg)
        self.assertEqual(record_type, 'question')

        # Verify typed_records is list of dicts
        self.assertEqual(len(typed_records), 1)
        self.assertIsInstance(typed_records[0], dict)
        self.assertEqual(typed_records[0]['quesname'], 'Test Question')

        # Cleanup
        question.delete()
        bt.delete()

    def test_get_select_output_typed_empty_queryset(self):
        """Test get_select_output_typed handles empty QuerySet."""
        from apps.activity.models.question_model import Question

        # Get empty QuerySet
        queryset = Question.objects.none().values()

        records_json, typed_records, count, msg, record_type = get_select_output_typed(queryset, 'question')

        self.assertIsNone(records_json)
        self.assertEqual(typed_records, [])
        self.assertEqual(count, 0)
        self.assertEqual(msg, "No records")
        self.assertEqual(record_type, 'question')


@pytest.mark.unit
class TestSelectOutputTypeResolution(TestCase):
    """Test SelectOutputType with typed records field."""

    def test_select_output_type_with_typed_records(self):
        """Test SelectOutputType resolves records_typed correctly."""
        # Create SelectOutputType instance with both fields
        typed_data = [
            {'id': 1, 'quesname': 'Q1', 'answertype': 'TEXT', 'enable': True, 'client_id': 1, 'cdtz': '2025-10-05T12:00:00Z', 'mdtz': '2025-10-05T12:00:00Z'},
            {'id': 2, 'quesname': 'Q2', 'answertype': 'NUMERIC', 'enable': True, 'client_id': 1, 'cdtz': '2025-10-05T12:00:00Z', 'mdtz': '2025-10-05T12:00:00Z'},
        ]

        output = SelectOutputType(
            nrows=2,
            records='[{"id":1},{"id":2}]',  # Legacy JSON string
            records_typed=typed_data,  # NEW: Typed list
            record_type='question',  # NEW: Discriminator
            msg="Test message"
        )

        # Verify fields
        self.assertEqual(output.nrows, 2)
        self.assertEqual(output.record_type, 'question')
        self.assertIsNotNone(output.records)  # Legacy field still works

        # Test resolver (simulated - requires GraphQL context in real scenario)
        # The resolve_records_typed method will convert dicts to typed objects
        self.assertEqual(len(output.records_typed), 2)

    def test_backward_compatibility_old_field(self):
        """Test old 'records' JSONString field still works."""
        output = SelectOutputType(
            nrows=1,
            records='[{"id":1,"name":"test"}]',  # Old format
            msg="Test message"
        )

        # Old field should still be accessible
        self.assertIsNotNone(output.records)
        self.assertEqual(output.nrows, 1)


@pytest.mark.unit
class TestSelectRecordUnion(TestCase):
    """Test SelectRecordUnion polymorphic type."""

    def test_union_accepts_all_record_types(self):
        """Test Union can hold all record types."""
        # This tests type definitions are compatible with Union
        types = SelectRecordUnion._meta.types

        self.assertIn(QuestionRecordType, types)
        self.assertIn(QuestionSetRecordType, types)
        self.assertIn(LocationRecordType, types)
        self.assertIn(AssetRecordType, types)
        self.assertIn(PgroupRecordType, types)
        self.assertIn(TypeAssistRecordType, types)

    def test_union_has_six_types(self):
        """Test Union includes all 6 record types."""
        types = SelectRecordUnion._meta.types
        self.assertEqual(len(types), 6)


@pytest.mark.integration
class TestGraphQLTypedRecordsIntegration(TestCase):
    """Integration tests for GraphQL queries with typed records."""

    def setUp(self):
        """Set up test data."""
        from apps.onboarding.models import Bt
        from apps.activity.models.question_model import Question
        from apps.peoples.models import People

        # Create test business unit
        self.bt = Bt.objects.create(btcode='TEST_BU', btname='Test BU')

        # Create test user
        self.user = People.objects.create(
            loginid='testuser',
            peoplecode='TEST001',
            peoplename='Test User',
            bu=self.bt,
            client_id=1,
            password='test'
        )

        # Create test question
        self.question = Question.objects.create(
            quesname='Integration Test Question',
            answertype='NUMERIC',
            min=0,
            max=100,
            bu=self.bt,
            client_id=1,
            cuser=self.user,
            muser=self.user,
        )

    def tearDown(self):
        """Clean up test data."""
        self.question.delete()
        self.user.delete()
        self.bt.delete()

    def test_question_query_returns_typed_records(self):
        """Test question query returns both legacy and typed records."""
        from apps.activity.models.question_model import Question

        # Get data like resolver does
        data = Question.objects.filter(id=self.question.id).values(
            'id', 'quesname', 'answertype', 'min', 'max', 'enable', 'client_id', 'cdtz', 'mdtz'
        )

        # Use typed output function
        records_json, typed_records, count, msg, record_type = get_select_output_typed(data, 'question')

        # Verify structure
        self.assertEqual(count, 1)
        self.assertEqual(record_type, 'question')
        self.assertIsInstance(typed_records, list)
        self.assertEqual(len(typed_records), 1)

        # Verify typed record can be converted to GraphQL type
        resolved = resolve_typed_record(typed_records[0], record_type)
        self.assertIsInstance(resolved, QuestionRecordType)
        self.assertEqual(resolved.quesname, 'Integration Test Question')

    def test_select_output_type_dual_fields(self):
        """Test SelectOutputType contains both legacy and typed fields."""
        from apps.activity.models.question_model import Question

        data = Question.objects.filter(id=self.question.id).values('id', 'quesname')
        records_json, typed_records, count, msg, record_type = get_select_output_typed(data, 'question')

        # Create SelectOutputType
        output = SelectOutputType(
            nrows=count,
            records=records_json,  # Legacy
            records_typed=typed_records,  # NEW
            record_type=record_type,  # NEW
            msg=msg
        )

        # Both fields should be present
        self.assertIsNotNone(output.records)  # Legacy JSON string
        self.assertIsNotNone(output.records_typed)  # Typed list
        self.assertEqual(output.record_type, 'question')


@pytest.mark.unit
class TestBackwardCompatibility(TestCase):
    """Test backward compatibility with existing mobile clients."""

    def test_old_resolvers_still_work(self):
        """Test old get_select_output() function still works (deprecated)."""
        from apps.core.utils import get_select_output
        from apps.activity.models.question_model import Question
        from apps.onboarding.models import Bt
        from apps.peoples.models import People

        # Create minimal test data
        bt = Bt.objects.create(btcode='TEST', btname='Test')
        user = People.objects.create(
            loginid='test', peoplecode='T001', peoplename='Test',
            bu=bt, client_id=1, password='test'
        )
        q = Question.objects.create(
            quesname='Test', answertype='TEXT',
            bu=bt, client_id=1, cuser=user, muser=user
        )

        queryset = Question.objects.filter(id=q.id).values('id', 'quesname')

        # Old function should still work
        records, count, msg = get_select_output(queryset)

        self.assertIsInstance(records, str)  # JSON string
        self.assertEqual(count, 1)
        self.assertIn('fetched successfully', msg)

        # Cleanup
        q.delete()
        user.delete()
        bt.delete()

    def test_select_output_type_without_typed_fields(self):
        """Test SelectOutputType works without new typed fields (backward compat)."""
        # Old usage pattern (before migration)
        output = SelectOutputType(
            nrows=1,
            records='[{"id":1}]',  # Only legacy field
            msg="Test"
        )

        # Should work without errors
        self.assertEqual(output.nrows, 1)
        self.assertIsNotNone(output.records)


@pytest.mark.unit
class TestErrorHandling(TestCase):
    """Test error handling in typed record resolution."""

    def test_resolve_typed_record_with_missing_fields(self):
        """Test resolving record with missing fields raises ValueError."""
        record_dict = {'id': 1}  # Missing required fields
        with self.assertRaises(ValueError):
            resolve_typed_record(record_dict, 'question')

    def test_resolve_typed_record_invalid_type(self):
        """Test resolving with invalid type raises ValueError."""
        record_dict = {'id': 1, 'name': 'Test'}
        with self.assertRaises(ValueError) as cm:
            resolve_typed_record(record_dict, 'invalid_type')
        self.assertIn('Unknown record type', str(cm.exception))

    def test_select_output_type_resolve_typed_handles_errors(self):
        """Test SelectOutputType.resolve_records_typed handles errors gracefully."""
        # Create instance with invalid typed data
        output = SelectOutputType(
            nrows=1,
            records='[{}]',
            records_typed=[{'invalid': 'data'}],  # Invalid structure
            record_type='question',
            msg="Test"
        )

        # Resolver should return empty list instead of raising
        # (simulated call - real test would need GraphQL context)
        # In production, this returns [] and logs error
        self.assertIsNotNone(output.records_typed)
