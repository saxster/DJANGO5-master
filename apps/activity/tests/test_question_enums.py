"""
Test suite for centralized Question enumerations.

Tests:
- Enum consolidation and uniqueness
- Backward compatibility with model enums
- Helper method functionality
- Mobile compatibility checks

Created: 2025-10-03
Following .claude/rules.md Rule #11: Specific exception handling
"""

import pytest
from django.test import TestCase
from apps.activity.enums import AnswerType, AvptType, ConditionalOperator, QuestionSetType
from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging


class TestAnswerTypeEnum(TestCase):
    """Test AnswerType enumeration."""

    def test_all_answer_types_defined(self):
        """Verify all expected answer types are present."""
        expected_types = {
            'CHECKBOX', 'DATE', 'DROPDOWN', 'EMAILID', 'MULTILINE',
            'NUMERIC', 'SIGNATURE', 'SINGLELINE', 'TIME', 'RATING',
            'PEOPLELIST', 'SITELIST', 'METERREADING', 'MULTISELECT',
            'GPSLOCATION', 'BACKCAMERA', 'FRONTCAMERA', 'NONE'
        }

        actual_types = {choice[0] for choice in AnswerType.choices}
        self.assertEqual(expected_types, actual_types)

    def test_backward_compatibility_with_question_model(self):
        """Verify Question.AnswerType proxies to centralized enum."""
        # All values should match
        for choice in Question.AnswerType.choices:
            self.assertIn(choice[0], [c[0] for c in AnswerType.choices])

    def test_backward_compatibility_with_belonging_model(self):
        """Verify QuestionSetBelonging.AnswerType includes camera types."""
        # Belonging should have deprecated camera types
        belonging_values = {choice[0] for choice in QuestionSetBelonging.AnswerType.choices}
        self.assertIn('BACKCAMERA', belonging_values)
        self.assertIn('FRONTCAMERA', belonging_values)

    def test_requires_options_helper(self):
        """Test requires_options() helper method."""
        # Choice types require options
        self.assertIn(AnswerType.CHECKBOX, AnswerType.requires_options())
        self.assertIn(AnswerType.DROPDOWN, AnswerType.requires_options())
        self.assertIn(AnswerType.MULTISELECT, AnswerType.requires_options())

        # Numeric types don't require options
        self.assertNotIn(AnswerType.NUMERIC, AnswerType.requires_options())
        self.assertNotIn(AnswerType.RATING, AnswerType.requires_options())

    def test_requires_min_max_helper(self):
        """Test requires_min_max() helper method."""
        # Numeric types require min/max
        self.assertIn(AnswerType.NUMERIC, AnswerType.requires_min_max())
        self.assertIn(AnswerType.RATING, AnswerType.requires_min_max())
        self.assertIn(AnswerType.METERREADING, AnswerType.requires_min_max())

        # Choice types don't require min/max
        self.assertNotIn(AnswerType.DROPDOWN, AnswerType.requires_min_max())

    def test_is_numeric_type_helper(self):
        """Test is_numeric_type() helper method."""
        self.assertTrue(AnswerType.is_numeric_type(AnswerType.NUMERIC))
        self.assertTrue(AnswerType.is_numeric_type(AnswerType.RATING))
        self.assertFalse(AnswerType.is_numeric_type(AnswerType.CHECKBOX))

    def test_is_choice_type_helper(self):
        """Test is_choice_type() helper method."""
        self.assertTrue(AnswerType.is_choice_type(AnswerType.DROPDOWN))
        self.assertTrue(AnswerType.is_choice_type(AnswerType.CHECKBOX))
        self.assertFalse(AnswerType.is_choice_type(AnswerType.NUMERIC))

    def test_is_deprecated_helper(self):
        """Test is_deprecated() helper for camera types."""
        self.assertTrue(AnswerType.is_deprecated(AnswerType.BACKCAMERA))
        self.assertTrue(AnswerType.is_deprecated(AnswerType.FRONTCAMERA))
        self.assertFalse(AnswerType.is_deprecated(AnswerType.NUMERIC))

    def test_supports_alerts_helper(self):
        """Test supports_alerts() helper method."""
        supporting_types = AnswerType.supports_alerts()

        # Numeric types support alerts
        self.assertIn(AnswerType.NUMERIC, supporting_types)
        self.assertIn(AnswerType.RATING, supporting_types)

        # Choice types support alerts
        self.assertIn(AnswerType.CHECKBOX, supporting_types)
        self.assertIn(AnswerType.DROPDOWN, supporting_types)

        # Text types don't support alerts
        self.assertNotIn(AnswerType.SINGLELINE, supporting_types)

    def test_mobile_supported_types(self):
        """Test mobile_supported_types() returns valid list."""
        mobile_types = AnswerType.mobile_supported_types()

        # Should not include deprecated camera types
        self.assertNotIn(AnswerType.BACKCAMERA, mobile_types)
        self.assertNotIn(AnswerType.FRONTCAMERA, mobile_types)

        # Should include all modern types
        self.assertIn(AnswerType.NUMERIC, mobile_types)
        self.assertIn(AnswerType.DROPDOWN, mobile_types)
        self.assertIn(AnswerType.SIGNATURE, mobile_types)


class TestAvptTypeEnum(TestCase):
    """Test AvptType enumeration."""

    def test_all_avpt_types_defined(self):
        """Verify all AVPT types are present."""
        expected_types = {'BACKCAMPIC', 'FRONTCAMPIC', 'AUDIO', 'VIDEO', 'NONE'}
        actual_types = {choice[0] for choice in AvptType.choices}
        self.assertEqual(expected_types, actual_types)

    def test_backward_compatibility(self):
        """Verify model enums match centralized enum."""
        # Question.AvptType should match
        for choice in Question.AvptType.choices:
            self.assertIn(choice[0], [c[0] for c in AvptType.choices])

        # QuestionSetBelonging.AvptType should match
        for choice in QuestionSetBelonging.AvptType.choices:
            self.assertIn(choice[0], [c[0] for c in AvptType.choices])

    def test_is_camera_type_helper(self):
        """Test is_camera_type() helper method."""
        self.assertTrue(AvptType.is_camera_type(AvptType.BACKCAMPIC))
        self.assertTrue(AvptType.is_camera_type(AvptType.FRONTCAMPIC))
        self.assertFalse(AvptType.is_camera_type(AvptType.AUDIO))
        self.assertFalse(AvptType.is_camera_type(AvptType.NONE))

    def test_is_media_type_helper(self):
        """Test is_media_type() helper method."""
        self.assertTrue(AvptType.is_media_type(AvptType.AUDIO))
        self.assertTrue(AvptType.is_media_type(AvptType.VIDEO))
        self.assertFalse(AvptType.is_media_type(AvptType.BACKCAMPIC))

    def test_requires_device_permission_helper(self):
        """Test requires_device_permission() helper method."""
        # All types except NONE require permissions
        self.assertFalse(AvptType.requires_device_permission(AvptType.NONE))
        self.assertTrue(AvptType.requires_device_permission(AvptType.BACKCAMPIC))
        self.assertTrue(AvptType.requires_device_permission(AvptType.AUDIO))
        self.assertTrue(AvptType.requires_device_permission(AvptType.VIDEO))


class TestConditionalOperatorEnum(TestCase):
    """Test ConditionalOperator enumeration."""

    def test_all_operators_defined(self):
        """Verify all operators are present."""
        expected_operators = {
            'EQUALS', 'NOT_EQUALS', 'CONTAINS', 'NOT_CONTAINS',
            'IN', 'NOT_IN', 'GT', 'GTE', 'LT', 'LTE',
            'IS_EMPTY', 'IS_NOT_EMPTY'
        }
        actual_operators = {choice[0] for choice in ConditionalOperator.choices}
        self.assertEqual(expected_operators, actual_operators)

    def test_numeric_operators(self):
        """Test numeric_operators() returns correct set."""
        numeric_ops = ConditionalOperator.numeric_operators()

        # Should include comparison operators
        self.assertIn(ConditionalOperator.GREATER_THAN, numeric_ops)
        self.assertIn(ConditionalOperator.LESS_THAN, numeric_ops)
        self.assertIn(ConditionalOperator.EQUALS, numeric_ops)

        # Should not include text operators
        self.assertNotIn(ConditionalOperator.CONTAINS, numeric_ops)

    def test_text_operators(self):
        """Test text_operators() returns correct set."""
        text_ops = ConditionalOperator.text_operators()

        # Should include text operators
        self.assertIn(ConditionalOperator.CONTAINS, text_ops)
        self.assertIn(ConditionalOperator.EQUALS, text_ops)

        # Should not include comparison operators
        self.assertNotIn(ConditionalOperator.GREATER_THAN, text_ops)

    def test_choice_operators(self):
        """Test choice_operators() returns correct set."""
        choice_ops = ConditionalOperator.choice_operators()

        # Should include IN/NOT_IN
        self.assertIn(ConditionalOperator.IN, choice_ops)
        self.assertIn(ConditionalOperator.NOT_IN, choice_ops)

        # Should not include CONTAINS
        self.assertNotIn(ConditionalOperator.CONTAINS, choice_ops)

    def test_validate_for_answer_type(self):
        """Test validate_for_answer_type() validation logic."""
        # Numeric types should allow GT/LT
        self.assertTrue(
            ConditionalOperator.validate_for_answer_type(
                ConditionalOperator.GREATER_THAN,
                AnswerType.NUMERIC
            )
        )

        # Choice types should allow IN
        self.assertTrue(
            ConditionalOperator.validate_for_answer_type(
                ConditionalOperator.IN,
                AnswerType.DROPDOWN
            )
        )

        # Numeric types should NOT allow CONTAINS
        self.assertFalse(
            ConditionalOperator.validate_for_answer_type(
                ConditionalOperator.CONTAINS,
                AnswerType.NUMERIC
            )
        )


class TestQuestionSetTypeEnum(TestCase):
    """Test QuestionSetType enumeration."""

    def test_all_types_defined(self):
        """Verify all question set types are present."""
        expected_types = {
            'ASSET', 'CHECKPOINT', 'CHECKLIST', 'RPCHECKLIST',
            'QUESTIONSET', 'INCIDENTREPORT', 'SITEREPORT',
            'WORKPERMIT', 'RETURN_WORK_PERMIT', 'KPITEMPLATE',
            'SCRAPPEDTEMPLATE', 'ASSETAUDIT', 'ASSETMAINTENANCE',
            'WORK_ORDER', 'SLA_TEMPLATE', 'POSTING_ORDER', 'SITESURVEY'
        }
        actual_types = {choice[0] for choice in QuestionSetType.choices}
        self.assertEqual(expected_types, actual_types)

    def test_backward_compatibility(self):
        """Verify QuestionSet.Type proxies to centralized enum."""
        for choice in QuestionSet.Type.choices:
            self.assertIn(choice[0], [c[0] for c in QuestionSetType.choices])

    def test_kpi_template_label_standardized(self):
        """Verify KPITEMPLATE label is standardized."""
        kpi_choice = next(
            (choice for choice in QuestionSetType.choices if choice[0] == 'KPITEMPLATE'),
            None
        )
        self.assertIsNotNone(kpi_choice)
        # Label should be "KPI Template", not "Kpi"
        self.assertEqual(str(kpi_choice[1]), "KPI Template")

    def test_requires_asset_association_helper(self):
        """Test requires_asset_association() helper method."""
        asset_types = QuestionSetType.requires_asset_association()

        self.assertIn(QuestionSetType.ASSET, asset_types)
        self.assertIn(QuestionSetType.CHECKPOINT, asset_types)
        self.assertNotIn(QuestionSetType.CHECKLIST, asset_types)

    def test_supports_scheduling_helper(self):
        """Test supports_scheduling() helper method."""
        schedulable = QuestionSetType.supports_scheduling()

        self.assertIn(QuestionSetType.CHECKLIST, schedulable)
        self.assertIn(QuestionSetType.ASSETAUDIT, schedulable)
        self.assertNotIn(QuestionSetType.ASSET, schedulable)


class TestEnumIntegration(TestCase):
    """Test integration between enums and models."""

    def test_question_model_uses_centralized_enums(self):
        """Verify Question model uses centralized enums."""
        # Create question with centralized enum
        from apps.activity.enums import AnswerType as UnifiedAnswerType

        # Should work with unified enum
        question = Question(
            quesname="Test Question",
            answertype=UnifiedAnswerType.NUMERIC,
            client_id=1,
            tenant_id=1
        )

        # answertype should match
        self.assertEqual(question.answertype, 'NUMERIC')

    def test_backward_compatible_enum_access(self):
        """Verify old enum access patterns still work."""
        # Old pattern: Question.AnswerType.NUMERIC
        # Should still work (with deprecation warning)
        self.assertEqual(Question.AnswerType.NUMERIC, 'NUMERIC')
        self.assertEqual(Question.AvptType.BACKCAMPIC, 'BACKCAMPIC')
        self.assertEqual(QuestionSet.Type.CHECKLIST, 'CHECKLIST')

    def test_enum_values_immutable(self):
        """Verify enum values are immutable."""
        # Enums should be immutable
        with self.assertRaises(AttributeError):
            AnswerType.NUMERIC = 'CHANGED'

    def test_enum_validation_helpers_work_with_model_data(self):
        """Test that helpers work with actual model field values."""
        # Simulate answer types from database
        numeric_type = 'NUMERIC'
        dropdown_type = 'DROPDOWN'

        # Helpers should work with string values
        self.assertTrue(AnswerType.is_numeric_type(numeric_type))
        self.assertTrue(AnswerType.is_choice_type(dropdown_type))
        self.assertFalse(AnswerType.is_numeric_type(dropdown_type))


class TestEnumValidationHelpers(TestCase):
    """Test validation helper functions."""

    def test_validate_options_for_answer_type(self):
        """Test validate_options_for_answer_type() function."""
        from apps.activity.enums import validate_options_for_answer_type

        # Choice types require options
        self.assertFalse(validate_options_for_answer_type(AnswerType.DROPDOWN, None))
        self.assertTrue(validate_options_for_answer_type(AnswerType.DROPDOWN, "Option1,Option2"))

        # Numeric types don't require options
        self.assertTrue(validate_options_for_answer_type(AnswerType.NUMERIC, None))

    def test_validate_min_max_for_answer_type(self):
        """Test validate_min_max_for_answer_type() function."""
        from apps.activity.enums import validate_min_max_for_answer_type

        # Numeric types require valid min/max
        self.assertTrue(validate_min_max_for_answer_type(AnswerType.NUMERIC, 0.0, 100.0))
        self.assertFalse(validate_min_max_for_answer_type(AnswerType.NUMERIC, None, None))
        self.assertFalse(validate_min_max_for_answer_type(AnswerType.NUMERIC, 100.0, 0.0))  # Invalid: min > max

        # Choice types don't require min/max
        self.assertTrue(validate_min_max_for_answer_type(AnswerType.DROPDOWN, None, None))

    def test_get_legacy_answer_type_display(self):
        """Test get_legacy_answer_type_display() for deprecated types."""
        from apps.activity.enums import get_legacy_answer_type_display

        # Deprecated types should show warning
        backcam_display = get_legacy_answer_type_display(AnswerType.BACKCAMERA)
        self.assertIn("Deprecated", backcam_display)
        self.assertIn("AVPT", backcam_display)

        # Modern types should show normal label
        numeric_display = get_legacy_answer_type_display(AnswerType.NUMERIC)
        self.assertEqual(numeric_display, "Numeric")


@pytest.mark.unit
class TestEnumPerformance(TestCase):
    """Test enum performance characteristics."""

    def test_helper_methods_are_fast(self):
        """Verify helper methods execute quickly (< 1ms)."""
        import time

        # Test requires_options (should be O(1) set lookup)
        start = time.perf_counter()
        for _ in range(1000):
            AnswerType.requires_options()
        elapsed = time.perf_counter() - start

        # 1000 calls should take < 10ms
        self.assertLess(elapsed, 0.01, f"requires_options() too slow: {elapsed:.4f}s for 1000 calls")

    def test_validation_helpers_are_cacheable(self):
        """Verify validation helpers return consistent results."""
        # Same input should always return same output
        result1 = AnswerType.is_numeric_type(AnswerType.NUMERIC)
        result2 = AnswerType.is_numeric_type(AnswerType.NUMERIC)
        self.assertEqual(result1, result2)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
