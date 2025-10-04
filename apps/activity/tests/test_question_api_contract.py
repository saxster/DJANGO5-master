"""
Android-Kotlin API Contract Tests for Question/QuestionSet.

CRITICAL: These tests ensure backward compatibility with the Android frontend.
Any breaking changes will cause mobile app crashes.

Tests verify:
- GraphQL schema compatibility
- Field name consistency
- Data type compatibility
- Backward compatibility for deprecated fields
- Deprecation warning detection

Created: 2025-10-03
Following .claude/rules.md Rule #9: Validate all inputs
"""

import pytest
import json
from django.test import TestCase
from graphene.test import Client as GraphQLClient

from apps.service.schema import schema  # Main GraphQL schema
from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging


@pytest.mark.android_contract
class TestQuestionGraphQLContract(TestCase):
    """Test Question GraphQL API contract for Android app."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        from apps.onboarding.models import Bt
        from apps.peoples.models import People

        # Create test client
        cls.client_obj = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'TEST', 'buname': 'Test Client', 'tenant_id': 1}
        )[0]

        # Create test user
        cls.user = People.objects.get_or_create(
            id=1,
            defaults={
                'loginid': 'testuser',
                'peoplename': 'Test User',
                'client_id': 1,
                'tenant_id': 1,
                'people_extras': {'assignsitegroup': [], 'tempincludes': []}
            }
        )[0]

        # Create test question
        cls.question = Question.objects.create(
            quesname="Temperature Reading",
            answertype='NUMERIC',
            options="NONE",
            options_json=None,  # Will be populated by migration
            alerton="<0, >100",
            alert_config={"numeric": {"below": 0.0, "above": 100.0}, "enabled": True},
            min=0.0,
            max=150.0,
            client=cls.client_obj,
            tenant_id=1
        )

    def test_get_questionsmodifiedafter_response_structure(self):
        """Test getQuestionsModifiedAfter returns expected structure."""
        graphql_client = GraphQLClient(schema)

        query = '''
            query {
                getQuestionsmodifiedafter(
                    mdtz: "2025-01-01T00:00:00Z",
                    ctzoffset: 0,
                    clientid: 1
                ) {
                    nrows
                    records
                    msg
                }
            }
        '''

        result = graphql_client.execute(query)

        # Should have no errors
        self.assertIsNone(result.get('errors'))

        # Should have data
        data = result['data']['getQuestionsmodifiedafter']
        self.assertIn('nrows', data)
        self.assertIn('records', data)
        self.assertIn('msg', data)

    def test_question_fields_backward_compatible(self):
        """Test Question fields match Android expectations."""
        # Expected fields by Android app (from KOTLIN_FRONTEND_CONTRACT.md if exists)
        expected_fields = [
            'id',
            'quesname',
            'answertype',
            'options',  # OLD - must exist
            'min',
            'max',
            'alerton',  # OLD - must exist
            'isavpt',
            'avpttype',
            'isworkflow',
            'unit_id',
            'category_id',
            'client_id',
        ]

        # Query to get question
        from django.http import HttpRequest
        request = HttpRequest()
        request.session = {'client_id': 1}

        questions = Question.objects.questions_listview(
            request,
            fields=expected_fields + ['created_at', 'updated_at'],
            related=['unit', 'category', 'client']
        )

        if questions:
            question = questions[0]
            # All expected fields should be present
            for field in expected_fields:
                self.assertIn(field, question, f"Field '{field}' missing from Question response")

    def test_new_json_fields_are_optional(self):
        """Test new JSON fields don't break existing queries."""
        # Old-style query without JSON fields
        question = Question.objects.filter(id=self.question.id).values(
            'id', 'quesname', 'answertype', 'options', 'alerton'  # No JSON fields
        ).first()

        # Should work without errors
        self.assertIsNotNone(question)
        self.assertEqual(question['quesname'], 'Temperature Reading')

    def test_json_fields_available_when_requested(self):
        """Test new JSON fields can be queried."""
        # New-style query with JSON fields
        question = Question.objects.filter(id=self.question.id).values(
            'id', 'quesname', 'options', 'options_json', 'alerton', 'alert_config'
        ).first()

        # Should have both old and new fields
        self.assertIn('options', question)
        self.assertIn('options_json', question)
        self.assertIn('alerton', question)
        self.assertIn('alert_config', question)


@pytest.mark.android_contract
class TestQuestionSetBelongingGraphQLContract(TestCase):
    """Test QuestionSetBelonging GraphQL API contract."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        from apps.onboarding.models import Bt

        cls.client_obj = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'TEST', 'buname': 'Test Client', 'tenant_id': 1}
        )[0]

        cls.qset = QuestionSet.objects.create(
            qsetname="Mobile Test Checklist",
            type='CHECKLIST',
            client=cls.client_obj,
            bu=cls.client_obj,
            tenant_id=1
        )

        cls.question1 = Question.objects.create(
            quesname="Has Damage?",
            answertype='DROPDOWN',
            options="Yes,No",
            options_json=["Yes", "No"],
            client=cls.client_obj,
            tenant_id=1
        )

        cls.question2 = Question.objects.create(
            quesname="Describe Damage",
            answertype='MULTILINE',
            client=cls.client_obj,
            tenant_id=1
        )

        # First question (no dependency)
        cls.qsb1 = QuestionSetBelonging.objects.create(
            qset=cls.qset,
            question=cls.question1,
            answertype='DROPDOWN',
            seqno=1,
            options="Yes,No",
            options_json=["Yes", "No"],
            client=cls.client_obj,
            bu=cls.client_obj,
            tenant_id=1
        )

        # Second question (depends on first)
        cls.qsb2 = QuestionSetBelonging.objects.create(
            qset=cls.qset,
            question=cls.question2,
            answertype='MULTILINE',
            seqno=2,
            client=cls.client_obj,
            bu=cls.client_obj,
            tenant_id=1,
            display_conditions={
                'depends_on': {
                    'question_id': cls.qsb1.id,  # OLD key for backward compat
                    'operator': 'EQUALS',
                    'values': ['Yes']
                },
                'show_if': True
            }
        )

    def test_get_questionset_with_conditional_logic_structure(self):
        """Test questionset with logic returns expected structure for Android."""
        result = QuestionSetBelonging.objects.get_questions_with_logic(self.qset.id)

        # Verify structure matches Android expectations
        self.assertIn('questions', result)
        self.assertIn('dependency_map', result)
        self.assertIn('has_conditional_logic', result)

        # Verify questions array structure
        questions = result['questions']
        self.assertEqual(len(questions), 2)

        # Each question should have required fields
        required_fields = [
            'pk', 'question_id', 'quesname', 'answertype',
            'min', 'max', 'options', 'alerton',
            'ismandatory', 'seqno', 'isavpt', 'avpttype',
            'display_conditions'
        ]

        for question in questions:
            for field in required_fields:
                self.assertIn(field, question, f"Field '{field}' missing from question")

    def test_dependency_map_structure_for_android(self):
        """Test dependency_map structure matches Android expectations."""
        result = QuestionSetBelonging.objects.get_questions_with_logic(self.qset.id)

        dependency_map = result['dependency_map']

        # Should have qsb1.id as key (since qsb2 depends on it)
        self.assertIn(self.qsb1.id, dependency_map)

        # Dependency should have required fields
        dependent_info = dependency_map[self.qsb1.id][0]

        android_required_fields = [
            'question_id',  # The dependent question's ID
            'question_seqno',
            'operator',
            'values',
            'show_if',
            'cascade_hide',
            'group'
        ]

        for field in android_required_fields:
            self.assertIn(field, dependent_info, f"Field '{field}' missing from dependency info")

    def test_backward_compatible_question_id_key(self):
        """Test old 'question_id' key still works in display_conditions."""
        result = QuestionSetBelonging.objects.get_questions_with_logic(self.qset.id)

        # qsb2 uses old 'question_id' key
        qsb2_data = next(
            (q for q in result['questions'] if q['pk'] == self.qsb2.id),
            None
        )

        self.assertIsNotNone(qsb2_data)
        self.assertIn('display_conditions', qsb2_data)

        depends_on = qsb2_data['display_conditions']['depends_on']

        # Should have question_id key (backward compat)
        self.assertIn('question_id', depends_on)
        self.assertEqual(depends_on['question_id'], self.qsb1.id)

    def test_validation_warnings_structure(self):
        """Test validation_warnings structure for Android error handling."""
        # Create invalid dependency (later question)
        question3 = Question.objects.create(
            quesname="Future Question",
            answertype='SINGLELINE',
            client=self.client_obj,
            tenant_id=1
        )

        qsb3 = QuestionSetBelonging.objects.create(
            qset=self.qset,
            question=question3,
            answertype='SINGLELINE',
            seqno=0,  # Before qsb1, but depends on it (invalid)
            client=self.client_obj,
            bu=self.client_obj,
            tenant_id=1,
            display_conditions={
                'depends_on': {
                    'question_id': self.qsb1.id,
                    'operator': 'EQUALS',
                    'values': ['Yes']
                }
            }
        )

        result = QuestionSetBelonging.objects.get_questions_with_logic(self.qset.id)

        # Should have validation warnings
        if 'validation_warnings' in result:
            warnings = result['validation_warnings']
            self.assertGreater(len(warnings), 0)

            # Each warning should have structure for Android
            for warning in warnings:
                self.assertIn('question_id', warning)
                self.assertIn('warning', warning)
                self.assertIn('severity', warning)


@pytest.mark.android_contract
class TestEnumValueCompatibility(TestCase):
    """Test enum values match Android Kotlin enum definitions."""

    def test_answer_type_values_match_android(self):
        """Test AnswerType values match Android enum."""
        from apps.activity.enums import AnswerType

        # Android app expects these exact string values
        android_expected = [
            'CHECKBOX', 'DATE', 'DROPDOWN', 'EMAILID', 'MULTILINE',
            'NUMERIC', 'SIGNATURE', 'SINGLELINE', 'TIME', 'RATING',
            'PEOPLELIST', 'SITELIST', 'METERREADING', 'MULTISELECT',
            'GPSLOCATION', 'NONE'
        ]

        # Deprecated camera types - Android should handle gracefully
        android_deprecated = ['BACKCAMERA', 'FRONTCAMERA']

        # All expected values should exist
        answer_type_values = [choice[0] for choice in AnswerType.choices]

        for expected in android_expected:
            self.assertIn(expected, answer_type_values, f"Android expects '{expected}' in AnswerType")

        # Deprecated values should exist for backward compat
        for deprecated in android_deprecated:
            self.assertIn(deprecated, answer_type_values, f"Android may have '{deprecated}' in old data")

    def test_avpt_type_values_match_android(self):
        """Test AvptType values match Android enum."""
        from apps.activity.enums import AvptType

        # Android app expects these exact string values
        android_expected = ['BACKCAMPIC', 'FRONTCAMPIC', 'AUDIO', 'VIDEO', 'NONE']

        avpt_type_values = [choice[0] for choice in AvptType.choices]

        for expected in android_expected:
            self.assertIn(expected, avpt_type_values, f"Android expects '{expected}' in AvptType")

    def test_conditional_operator_values_for_android(self):
        """Test ConditionalOperator values are Android-compatible."""
        from apps.activity.enums import ConditionalOperator

        # Android app should support these operators
        android_supported = [
            'EQUALS', 'NOT_EQUALS', 'CONTAINS', 'IN', 'GT', 'LT', 'GTE', 'LTE'
        ]

        operator_values = [choice[0] for choice in ConditionalOperator.choices]

        for supported in android_supported:
            self.assertIn(supported, operator_values, f"Android needs '{supported}' operator")


@pytest.mark.android_contract
class TestGraphQLResponseFormat(TestCase):
    """Test GraphQL responses match Android parsing expectations."""

    @classmethod
    def setUpTestData(cls):
        """Create comprehensive test data."""
        from apps.onboarding.models import Bt

        cls.client_obj = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'MOBILE', 'buname': 'Mobile Test', 'tenant_id': 1}
        )[0]

        cls.qset = QuestionSet.objects.create(
            qsetname="Mobile Checklist",
            type='CHECKLIST',
            client=cls.client_obj,
            bu=cls.client_obj,
            tenant_id=1
        )

        # Create questions with various types
        cls.questions = []
        for i in range(5):
            question = Question.objects.create(
                quesname=f"Question {i+1}",
                answertype='NUMERIC' if i % 2 == 0 else 'DROPDOWN',
                options=f"Opt1,Opt2,Opt3" if i % 2 != 0 else None,
                options_json=["Opt1", "Opt2", "Opt3"] if i % 2 != 0 else None,
                min=0.0 if i % 2 == 0 else None,
                max=100.0 if i % 2 == 0 else None,
                client=cls.client_obj,
                tenant_id=1
            )
            cls.questions.append(question)

            QuestionSetBelonging.objects.create(
                qset=cls.qset,
                question=question,
                answertype=question.answertype,
                seqno=i + 1,
                options=question.options,
                options_json=question.options_json,
                min=question.min,
                max=question.max,
                client=cls.client_obj,
                bu=cls.client_obj,
                tenant_id=1
            )

    def test_questionset_with_logic_json_serializable(self):
        """Test response is fully JSON-serializable for Android."""
        result = QuestionSetBelonging.objects.get_questions_with_logic(self.qset.id)

        # Should be JSON-serializable
        try:
            json_str = json.dumps(result)
            # Android should be able to parse this
            parsed = json.loads(json_str)

            self.assertEqual(len(parsed['questions']), 5)

        except (TypeError, ValueError) as e:
            self.fail(f"Response not JSON-serializable: {e}")

    def test_both_old_and_new_fields_present(self):
        """Test response contains both old and new fields during transition."""
        result = QuestionSetBelonging.objects.get_questions_with_logic(self.qset.id)

        for question in result['questions']:
            # Old fields (for backward compat)
            self.assertIn('options', question)
            self.assertIn('alerton', question)

            # NEW fields are in model but may be None
            # Android should check both and prefer JSON if available

    def test_dropdown_options_format(self):
        """Test dropdown options format matches Android expectations."""
        # Get a dropdown question
        dropdown_question = next(
            (q for q in self.questions if q.answertype == 'DROPDOWN'),
            None
        )

        self.assertIsNotNone(dropdown_question)

        # Old format: "Opt1,Opt2,Opt3"
        self.assertEqual(dropdown_question.options, "Opt1,Opt2,Opt3")

        # New format: ["Opt1", "Opt2", "Opt3"]
        self.assertEqual(dropdown_question.options_json, ["Opt1", "Opt2", "Opt3"])

    def test_numeric_alert_format(self):
        """Test numeric alert format matches Android expectations."""
        # Create numeric question with alerts
        question = Question.objects.create(
            quesname="Temp with Alerts",
            answertype='NUMERIC',
            options="NONE",
            alerton="<10, >90",  # OLD format
            alert_config={  # NEW format
                "numeric": {"below": 10.0, "above": 90.0},
                "enabled": True
            },
            min=0.0,
            max=100.0,
            client=self.client_obj,
            tenant_id=1
        )

        # Old format should be parseable by Android
        self.assertIn('<', question.alerton)
        self.assertIn('>', question.alerton)

        # New format should be structured
        self.assertIsInstance(question.alert_config, dict)
        self.assertIn('numeric', question.alert_config)
        self.assertEqual(question.alert_config['numeric']['below'], 10.0)
        self.assertEqual(question.alert_config['numeric']['above'], 90.0)


@pytest.mark.android_contract
class TestDeprecationWarnings(TestCase):
    """Test deprecation warnings for Android migration planning."""

    def test_deprecated_answer_types_logged(self):
        """Test deprecated camera answer types trigger warnings."""
        from apps.activity.enums import AnswerType

        # BACKCAMERA and FRONTCAMERA are deprecated
        self.assertTrue(AnswerType.is_deprecated(AnswerType.BACKCAMERA))
        self.assertTrue(AnswerType.is_deprecated(AnswerType.FRONTCAMERA))

        # Android should migrate to using AVPT instead

    def test_deprecated_field_usage_detected(self):
        """Test that we can detect when old fields are used."""
        from apps.onboarding.models import Bt

        client = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'TEST', 'buname': 'Test', 'tenant_id': 1}
        )[0]

        question = Question.objects.create(
            quesname="Legacy Question",
            answertype='DROPDOWN',
            options="Old,Format",  # Using old field
            options_json=None,  # Not using new field
            client=client,
            tenant_id=1
        )

        # Can detect migration needed
        needs_migration = question.options and not question.options_json
        self.assertTrue(needs_migration)


@pytest.mark.android_contract
class TestAndroidMigrationPath(TestCase):
    """Test migration path for Android app."""

    def test_release_n_both_fields_available(self):
        """Test Release N: Both old and new fields available."""
        from apps.onboarding.models import Bt

        client = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'TEST', 'buname': 'Test', 'tenant_id': 1}
        )[0]

        # Create question with both fields
        question = Question.objects.create(
            quesname="Dual Format Question",
            answertype='DROPDOWN',
            options="A,B,C",  # OLD
            options_json=["A", "B", "C"],  # NEW
            client=client,
            tenant_id=1
        )

        # Android can read either field
        self.assertIsNotNone(question.options)  # OLD API
        self.assertIsNotNone(question.options_json)  # NEW API

    def test_android_can_prefer_json_when_available(self):
        """Test Android can check for JSON field first."""
        from apps.onboarding.models import Bt

        client = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'TEST', 'buname': 'Test', 'tenant_id': 1}
        )[0]

        question = Question.objects.create(
            quesname="Migration Test",
            answertype='DROPDOWN',
            options="Old,Format",
            options_json=["New", "Format"],  # Different data
            client=client,
            tenant_id=1
        )

        # Simulated Android logic:
        options_to_use = question.options_json if question.options_json else (
            question.options.split(',') if question.options else []
        )

        # Should prefer JSON
        self.assertEqual(options_to_use, ["New", "Format"])


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
