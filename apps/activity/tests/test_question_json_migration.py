"""
Test suite for Question/QuestionSetBelonging JSON field migration.

Tests parsing of text-based options and alert configurations into structured JSON.
Critical for ensuring data integrity during migration.

Created: 2025-10-03
Following .claude/rules.md Rule #11: Specific exception handling
"""

import pytest
from django.test import TestCase
from apps.activity.services.question_data_migration_service import (
    OptionsParser,
    AlertParser,
    QuestionDataMigrationService
)


class TestOptionsParser(TestCase):
    """Test OptionsParser for text → JSON array conversion."""

    def test_parse_comma_separated_options(self):
        """Test standard comma-separated format."""
        input_text = "Option1,Option2,Option3"
        result = OptionsParser.parse(input_text)

        self.assertEqual(result, ["Option1", "Option2", "Option3"])

    def test_parse_pipe_separated_options(self):
        """Test pipe-separated format."""
        input_text = "Option1|Option2|Option3"
        result = OptionsParser.parse(input_text)

        self.assertEqual(result, ["Option1", "Option2", "Option3"])

    def test_parse_mixed_separators(self):
        """Test mixed comma and pipe separators."""
        input_text = "Option1, Option2 | Option3, Option4"
        result = OptionsParser.parse(input_text)

        self.assertEqual(result, ["Option1", "Option2", "Option3", "Option4"])

    def test_parse_with_quotes(self):
        """Test options with quotes."""
        input_text = '"Option1","Option2","Option3"'
        result = OptionsParser.parse(input_text)

        self.assertEqual(result, ["Option1", "Option2", "Option3"])

    def test_parse_with_extra_whitespace(self):
        """Test options with trailing/leading whitespace."""
        input_text = " Option1 ,  Option2  , Option3   "
        result = OptionsParser.parse(input_text)

        self.assertEqual(result, ["Option1", "Option2", "Option3"])

    def test_parse_removes_duplicates(self):
        """Test duplicate options are removed."""
        input_text = "Option1,Option2,Option1,Option3,Option2"
        result = OptionsParser.parse(input_text)

        # Should preserve order but remove duplicates
        self.assertEqual(result, ["Option1", "Option2", "Option3"])

    def test_parse_case_insensitive_duplicates(self):
        """Test case-insensitive duplicate removal."""
        input_text = "Yes,yes,YES,No,no"
        result = OptionsParser.parse(input_text)

        # Should keep first occurrence of each unique option (case-insensitive)
        self.assertEqual(result, ["Yes", "No"])

    def test_parse_none_value(self):
        """Test handling of NONE value."""
        self.assertEqual(OptionsParser.parse("NONE"), [])
        self.assertEqual(OptionsParser.parse("none"), [])
        self.assertEqual(OptionsParser.parse("None"), [])

    def test_parse_empty_string(self):
        """Test handling of empty string."""
        self.assertEqual(OptionsParser.parse(""), [])
        self.assertEqual(OptionsParser.parse(None), [])
        self.assertEqual(OptionsParser.parse("   "), [])

    def test_parse_trailing_commas(self):
        """Test handling of trailing commas."""
        input_text = "Option1,Option2,Option3,"
        result = OptionsParser.parse(input_text)

        self.assertEqual(result, ["Option1", "Option2", "Option3"])

    def test_parse_truncates_long_options(self):
        """Test very long options are truncated."""
        long_option = "A" * 300
        input_text = f"{long_option},Option2"
        result = OptionsParser.parse(input_text)

        # First option should be truncated to 200 chars
        self.assertEqual(len(result[0]), 200)
        self.assertEqual(result[1], "Option2")


class TestAlertParser(TestCase):
    """Test AlertParser for text → JSON config conversion."""

    def test_parse_numeric_alert_both_bounds(self):
        """Test numeric alert with both below and above."""
        input_text = "<10.5, >90.0"
        result = AlertParser.parse(input_text, 'NUMERIC')

        expected = {
            'numeric': {
                'below': 10.5,
                'above': 90.0
            },
            'enabled': True
        }
        self.assertEqual(result, expected)

    def test_parse_numeric_alert_below_only(self):
        """Test numeric alert with only below threshold."""
        input_text = "<10.5"
        result = AlertParser.parse(input_text, 'NUMERIC')

        expected = {
            'numeric': {
                'below': 10.5
            },
            'enabled': True
        }
        self.assertEqual(result, expected)

    def test_parse_numeric_alert_above_only(self):
        """Test numeric alert with only above threshold."""
        input_text = ">90.0"
        result = AlertParser.parse(input_text, 'NUMERIC')

        expected = {
            'numeric': {
                'above': 90.0
            },
            'enabled': True
        }
        self.assertEqual(result, expected)

    def test_parse_numeric_alert_with_spaces(self):
        """Test numeric alert with extra whitespace."""
        input_text = "< 10.5 , > 90.0"
        result = AlertParser.parse(input_text, 'NUMERIC')

        self.assertEqual(result['numeric']['below'], 10.5)
        self.assertEqual(result['numeric']['above'], 90.0)

    def test_parse_choice_alert_comma_separated(self):
        """Test choice alert with comma-separated values."""
        input_text = "Alert1,Alert2,Alert3"
        result = AlertParser.parse(input_text, 'DROPDOWN')

        expected = {
            'choice': ['Alert1', 'Alert2', 'Alert3'],
            'enabled': True
        }
        self.assertEqual(result, expected)

    def test_parse_choice_alert_single_value(self):
        """Test choice alert with single value."""
        input_text = "Critical"
        result = AlertParser.parse(input_text, 'DROPDOWN')

        expected = {
            'choice': ['Critical'],
            'enabled': True
        }
        self.assertEqual(result, expected)

    def test_parse_none_value(self):
        """Test handling of NONE value."""
        self.assertIsNone(AlertParser.parse("NONE"))
        self.assertIsNone(AlertParser.parse("none"))
        self.assertIsNone(AlertParser.parse("NULL"))

    def test_parse_empty_string(self):
        """Test handling of empty string."""
        self.assertIsNone(AlertParser.parse(""))
        self.assertIsNone(AlertParser.parse(None))
        self.assertIsNone(AlertParser.parse("   "))

    def test_parse_malformed_numeric_returns_none(self):
        """Test malformed numeric alert returns None."""
        # Missing values
        self.assertIsNone(AlertParser.parse("<, >", 'NUMERIC'))

        # Invalid format
        self.assertIsNone(AlertParser.parse("invalid", 'NUMERIC'))

    def test_parse_with_integer_values(self):
        """Test numeric alerts with integer values."""
        input_text = "<10, >90"
        result = AlertParser.parse(input_text, 'NUMERIC')

        self.assertEqual(result['numeric']['below'], 10.0)
        self.assertEqual(result['numeric']['above'], 90.0)

    def test_parse_with_decimal_values(self):
        """Test numeric alerts with decimal values."""
        input_text = "<10.75, >89.25"
        result = AlertParser.parse(input_text, 'NUMERIC')

        self.assertEqual(result['numeric']['below'], 10.75)
        self.assertEqual(result['numeric']['above'], 89.25)


class TestQuestionDataMigrationService(TestCase):
    """Test QuestionDataMigrationService for batch migrations."""

    def setUp(self):
        """Set up test data."""
        from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging
        from apps.onboarding.models import Bt

        # Create test client
        self.client = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'TEST', 'buname': 'Test Client', 'tenant_id': 1}
        )[0]

        # Create test question
        self.question = Question.objects.create(
            quesname="Test Numeric Question",
            answertype='NUMERIC',
            options="NONE",  # Should parse to empty
            alerton="<10, >90",  # Should parse to {"numeric": {"below": 10, "above": 90}}
            min=0.0,
            max=100.0,
            client=self.client,
            tenant_id=1
        )

    def test_migrate_question_dry_run(self):
        """Test question migration in dry-run mode."""
        service = QuestionDataMigrationService(dry_run=True)

        success, error = service.migrate_question(self.question)

        # Should succeed
        self.assertTrue(success)
        self.assertIsNone(error)

        # Should not save in dry-run
        self.question.refresh_from_db()
        self.assertIsNone(self.question.options_json)

    def test_migrate_question_live(self):
        """Test question migration in live mode."""
        service = QuestionDataMigrationService(dry_run=False)

        success, error = service.migrate_question(self.question)

        # Should succeed
        self.assertTrue(success)
        self.assertIsNone(error)

        # Should save in live mode
        self.question.refresh_from_db()
        self.assertIsNotNone(self.question.alert_config)
        self.assertEqual(self.question.alert_config['numeric']['below'], 10.0)
        self.assertEqual(self.question.alert_config['numeric']['above'], 90.0)

    def test_generate_report(self):
        """Test migration report generation."""
        service = QuestionDataMigrationService(dry_run=True)
        service.stats['total_questions'] = 100
        service.stats['questions_migrated'] = 95
        service.stats['questions_failed'] = 5
        service.stats['errors'] = [
            {'model': 'Question', 'id': 1, 'error': 'Parse error'}
        ]

        report = service.generate_report()

        # Report should contain stats
        self.assertIn('100', report)
        self.assertIn('95', report)
        self.assertIn('5', report)
        self.assertIn('DRY RUN', report)


@pytest.mark.integration
class TestEndToEndMigration(TestCase):
    """Test complete migration workflow."""

    def setUp(self):
        """Create comprehensive test dataset."""
        from apps.activity.models.question_model import Question
        from apps.onboarding.models import Bt

        self.client = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'TEST', 'buname': 'Test Client', 'tenant_id': 1}
        )[0]

        # Create questions with various formats
        self.questions = [
            # Numeric with alerts
            Question.objects.create(
                quesname="Temperature",
                answertype='NUMERIC',
                options="NONE",
                alerton="<0, >100",
                min=0.0,
                max=150.0,
                client=self.client,
                tenant_id=1
            ),
            # Dropdown with options
            Question.objects.create(
                quesname="Status",
                answertype='DROPDOWN',
                options="Good,Average,Poor",
                alerton="Poor",
                client=self.client,
                tenant_id=1
            ),
            # Checkbox with options
            Question.objects.create(
                quesname="Issues",
                answertype='CHECKBOX',
                options='"Broken"|"Damaged"|"Missing"',
                alerton="Broken,Missing",
                client=self.client,
                tenant_id=1
            ),
        ]

    def test_complete_migration_workflow(self):
        """Test complete migration of all question types."""
        service = QuestionDataMigrationService(dry_run=False)

        # Migrate all
        stats = service.migrate_all_questions(batch_size=10)

        # All questions should migrate successfully
        self.assertEqual(stats['questions_migrated'], 3)
        self.assertEqual(stats['questions_failed'], 0)

        # Verify each question
        for question in self.questions:
            question.refresh_from_db()

            if question.answertype == 'NUMERIC':
                # Should have numeric alert config
                self.assertIsNotNone(question.alert_config)
                self.assertIn('numeric', question.alert_config)
                self.assertEqual(question.alert_config['numeric']['below'], 0.0)
                self.assertEqual(question.alert_config['numeric']['above'], 100.0)

            elif question.answertype in ['DROPDOWN', 'CHECKBOX']:
                # Should have options_json
                self.assertIsNotNone(question.options_json)
                self.assertIsInstance(question.options_json, list)
                self.assertGreater(len(question.options_json), 0)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
