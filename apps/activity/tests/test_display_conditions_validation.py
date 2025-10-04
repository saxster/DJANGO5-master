"""
Test suite for display_conditions Pydantic validation.

Tests:
- Pydantic schema validation
- Dependency ordering validation
- Circular dependency detection
- Database constraint validation
- qsb_id vs question_id naming clarification

Created: 2025-10-03
Following .claude/rules.md Rule #11: Specific exception handling
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from apps.activity.validators import (
    DependencySchema,
    DisplayConditionsSchema,
    DisplayConditionsValidator,
    validate_display_conditions,
)
from apps.activity.enums import ConditionalOperator
from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging


class TestDependencySchema(TestCase):
    """Test DependencySchema Pydantic model."""

    def test_valid_dependency_structure(self):
        """Test valid dependency validates successfully."""
        data = {
            'qsb_id': 123,
            'operator': 'EQUALS',
            'values': ['Yes']
        }

        schema = DependencySchema(**data)

        self.assertEqual(schema.qsb_id, 123)
        self.assertEqual(schema.operator, 'EQUALS')
        self.assertEqual(schema.values, ['Yes'])

    def test_backward_compatible_question_id_alias(self):
        """Test 'question_id' alias works for qsb_id."""
        data = {
            'question_id': 456,  # Old key name
            'operator': 'EQUALS',
            'values': ['Yes']
        }

        schema = DependencySchema(**data)

        # Should map to qsb_id
        self.assertEqual(schema.qsb_id, 456)

    def test_invalid_operator_raises_error(self):
        """Test invalid operator raises validation error."""
        data = {
            'qsb_id': 123,
            'operator': 'INVALID_OP',
            'values': ['Yes']
        }

        with self.assertRaises(Exception):
            DependencySchema(**data)

    def test_negative_qsb_id_raises_error(self):
        """Test negative qsb_id raises validation error."""
        data = {
            'qsb_id': -1,
            'operator': 'EQUALS',
            'values': ['Yes']
        }

        with self.assertRaises(Exception):
            DependencySchema(**data)

    def test_values_xss_sanitization(self):
        """Test values are sanitized for XSS."""
        data = {
            'qsb_id': 123,
            'operator': 'EQUALS',
            'values': ['<script>alert("xss")</script>']
        }

        schema = DependencySchema(**data)

        # Script tags should be removed
        self.assertNotIn('<script>', schema.values[0])

    def test_empty_values_allowed_for_is_empty_operator(self):
        """Test empty values list is valid for IS_EMPTY operator."""
        data = {
            'qsb_id': 123,
            'operator': 'IS_EMPTY',
            'values': []
        }

        # Should not raise error
        schema = DependencySchema(**data)
        self.assertEqual(schema.values, [])


class TestDisplayConditionsSchema(TestCase):
    """Test DisplayConditionsSchema Pydantic model."""

    def test_valid_complete_structure(self):
        """Test complete valid structure validates successfully."""
        data = {
            'depends_on': {
                'qsb_id': 123,
                'operator': 'EQUALS',
                'values': ['Yes']
            },
            'show_if': True,
            'cascade_hide': False,
            'group': 'labour_work'
        }

        schema = DisplayConditionsSchema(**data)

        self.assertIsNotNone(schema.depends_on)
        self.assertEqual(schema.show_if, True)
        self.assertEqual(schema.cascade_hide, False)
        self.assertEqual(schema.group, 'labour_work')

    def test_optional_fields_have_defaults(self):
        """Test optional fields use sensible defaults."""
        data = {
            'depends_on': {
                'qsb_id': 123,
                'operator': 'EQUALS',
                'values': ['Yes']
            }
        }

        schema = DisplayConditionsSchema(**data)

        # Defaults
        self.assertTrue(schema.show_if)
        self.assertFalse(schema.cascade_hide)
        self.assertIsNone(schema.group)

    def test_empty_conditions(self):
        """Test empty conditions (no dependencies)."""
        data = {}

        schema = DisplayConditionsSchema(**data)

        self.assertIsNone(schema.depends_on)
        self.assertTrue(schema.show_if)
        self.assertFalse(schema.cascade_hide)

    def test_group_name_sanitization(self):
        """Test group name is sanitized."""
        data = {
            'group': 'labour work@#$%'
        }

        schema = DisplayConditionsSchema(**data)

        # Special characters should be removed
        self.assertEqual(schema.group, 'labourwork')

    def test_operator_requires_values_validation(self):
        """Test operators requiring values are validated."""
        data = {
            'depends_on': {
                'qsb_id': 123,
                'operator': 'EQUALS',  # Requires values
                'values': []  # Empty!
            }
        }

        with self.assertRaises(Exception) as cm:
            DisplayConditionsSchema(**data)

        self.assertIn('values', str(cm.exception).lower())


class TestDisplayConditionsValidator(TestCase):
    """Test DisplayConditionsValidator database validation."""

    def setUp(self):
        """Create test data."""
        from apps.onboarding.models import Bt

        # Create test data
        self.client = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'TEST', 'buname': 'Test Client', 'tenant_id': 1}
        )[0]

        self.qset = QuestionSet.objects.create(
            qsetname="Test Checklist",
            type='CHECKLIST',
            client=self.client,
            bu=self.client,
            tenant_id=1
        )

        self.question1 = Question.objects.create(
            quesname="First Question",
            answertype='DROPDOWN',
            options="Yes,No",
            client=self.client,
            tenant_id=1
        )

        self.question2 = Question.objects.create(
            quesname="Second Question",
            answertype='SINGLELINE',
            client=self.client,
            tenant_id=1
        )

        # Create belongings
        self.qsb1 = QuestionSetBelonging.objects.create(
            qset=self.qset,
            question=self.question1,
            answertype='DROPDOWN',
            seqno=1,
            options="Yes,No",
            client=self.client,
            bu=self.client,
            tenant_id=1
        )

        self.qsb2 = QuestionSetBelonging.objects.create(
            qset=self.qset,
            question=self.question2,
            answertype='SINGLELINE',
            seqno=2,
            client=self.client,
            bu=self.client,
            tenant_id=1
        )

    def test_validate_dependency_exists_valid(self):
        """Test valid dependency validation."""
        validator = DisplayConditionsValidator()

        result = validator.validate_dependency_exists(
            qsb_id=self.qsb2.id,
            dependency_qsb_id=self.qsb1.id,
            qset_id=self.qset.id
        )

        self.assertTrue(result['valid'])
        self.assertEqual(result['dependency_seqno'], 1)

    def test_validate_dependency_different_qset_raises_error(self):
        """Test dependency in different qset raises error."""
        # Create second qset
        qset2 = QuestionSet.objects.create(
            qsetname="Other Checklist",
            type='CHECKLIST',
            client=self.client,
            bu=self.client,
            tenant_id=1
        )

        validator = DisplayConditionsValidator()

        with self.assertRaises(ValueError) as cm:
            validator.validate_dependency_exists(
                qsb_id=self.qsb2.id,
                dependency_qsb_id=self.qsb1.id,
                qset_id=qset2.id  # Different qset!
            )

        self.assertIn('same question set', str(cm.exception))

    def test_validate_dependency_not_found_raises_error(self):
        """Test non-existent dependency raises error."""
        validator = DisplayConditionsValidator()

        with self.assertRaises(ValueError) as cm:
            validator.validate_dependency_exists(
                qsb_id=self.qsb2.id,
                dependency_qsb_id=99999,  # Doesn't exist
                qset_id=self.qset.id
            )

        self.assertIn('does not exist', str(cm.exception))

    def test_validate_dependency_ordering_valid(self):
        """Test valid dependency ordering."""
        validator = DisplayConditionsValidator()

        # qsb1 (seqno=1) before qsb2 (seqno=2) is valid
        result = validator.validate_dependency_ordering(
            current_seqno=2,
            dependency_seqno=1,
            dependency_qsb_id=self.qsb1.id
        )

        self.assertTrue(result)

    def test_validate_dependency_ordering_invalid(self):
        """Test invalid dependency ordering raises error."""
        validator = DisplayConditionsValidator()

        # qsb2 (seqno=2) AFTER qsb1 (seqno=1) trying to depend on it is invalid
        with self.assertRaises(ValueError) as cm:
            validator.validate_dependency_ordering(
                current_seqno=1,  # Earlier question
                dependency_seqno=2,  # Trying to depend on later question
                dependency_qsb_id=self.qsb2.id
            )

        self.assertIn('must come BEFORE', str(cm.exception))

    def test_validate_dependency_same_seqno_invalid(self):
        """Test dependency with same seqno raises error."""
        validator = DisplayConditionsValidator()

        with self.assertRaises(ValueError) as cm:
            validator.validate_dependency_ordering(
                current_seqno=2,
                dependency_seqno=2,  # Same seqno
                dependency_qsb_id=self.qsb1.id
            )

        self.assertIn('must come BEFORE', str(cm.exception))

    def test_detect_circular_dependency_simple(self):
        """Test simple circular dependency detection."""
        # Create circular dependency: qsb1 → qsb2 → qsb1
        self.qsb2.display_conditions = {
            'depends_on': {'question_id': self.qsb1.id, 'operator': 'EQUALS', 'values': ['Yes']}
        }
        self.qsb2.save(update_fields=['display_conditions'])

        # Now try to make qsb1 depend on qsb2 (would create circle)
        self.qsb1.display_conditions = {
            'depends_on': {'question_id': self.qsb2.id, 'operator': 'EQUALS', 'values': ['No']}
        }

        validator = DisplayConditionsValidator()

        # Should detect circular dependency
        with self.assertRaises(ValueError) as cm:
            validator.detect_circular_dependency(self.qsb1.id, self.qset.id)

        self.assertIn('Circular dependency', str(cm.exception))

    def test_complete_validation_workflow(self):
        """Test complete validation with all checks."""
        # Valid display conditions
        data = {
            'depends_on': {
                'qsb_id': self.qsb1.id,
                'operator': 'EQUALS',
                'values': ['Yes']
            },
            'show_if': True,
            'cascade_hide': False
        }

        # Should validate successfully
        validated = validate_display_conditions(
            data=data,
            qsb_id=self.qsb2.id,
            qset_id=self.qset.id,
            seqno=2
        )

        self.assertIsNotNone(validated)
        self.assertEqual(validated.depends_on.qsb_id, self.qsb1.id)


class TestModelIntegration(TestCase):
    """Test integration with QuestionSetBelonging model."""

    def setUp(self):
        """Create test data."""
        from apps.onboarding.models import Bt

        self.client = Bt.objects.get_or_create(
            id=1,
            defaults={'bucode': 'TEST', 'buname': 'Test Client', 'tenant_id': 1}
        )[0]

        self.qset = QuestionSet.objects.create(
            qsetname="Test Checklist",
            type='CHECKLIST',
            client=self.client,
            bu=self.client,
            tenant_id=1
        )

        self.question1 = Question.objects.create(
            quesname="Has Issue?",
            answertype='DROPDOWN',
            options="Yes,No",
            client=self.client,
            tenant_id=1
        )

        self.qsb1 = QuestionSetBelonging.objects.create(
            qset=self.qset,
            question=self.question1,
            answertype='DROPDOWN',
            seqno=1,
            options="Yes,No",
            client=self.client,
            bu=self.client,
            tenant_id=1
        )

    def test_model_clean_validates_display_conditions(self):
        """Test model clean() method validates display_conditions."""
        question2 = Question.objects.create(
            quesname="Describe Issue",
            answertype='MULTILINE',
            client=self.client,
            tenant_id=1
        )

        qsb2 = QuestionSetBelonging(
            qset=self.qset,
            question=question2,
            answertype='MULTILINE',
            seqno=2,
            client=self.client,
            bu=self.client,
            tenant_id=1,
            display_conditions={
                'depends_on': {
                    'qsb_id': self.qsb1.id,
                    'operator': 'EQUALS',
                    'values': ['Yes']
                },
                'show_if': True
            }
        )

        # Should validate successfully
        qsb2.full_clean()  # Should not raise

    def test_model_clean_rejects_invalid_conditions(self):
        """Test model clean() rejects invalid display_conditions."""
        question2 = Question.objects.create(
            quesname="Invalid Question",
            answertype='MULTILINE',
            client=self.client,
            tenant_id=1
        )

        qsb2 = QuestionSetBelonging(
            qset=self.qset,
            question=question2,
            answertype='MULTILINE',
            seqno=2,
            client=self.client,
            bu=self.client,
            tenant_id=1,
            display_conditions={
                'depends_on': {
                    'qsb_id': 99999,  # Doesn't exist
                    'operator': 'EQUALS',
                    'values': ['Yes']
                }
            }
        )

        # Should raise ValidationError
        with self.assertRaises(ValidationError) as cm:
            qsb2.full_clean()

        self.assertIn('display_conditions', cm.exception.message_dict)

    def test_model_save_calls_validation(self):
        """Test save() method calls full_clean()."""
        question2 = Question.objects.create(
            quesname="Another Question",
            answertype='SINGLELINE',
            client=self.client,
            tenant_id=1
        )

        qsb2 = QuestionSetBelonging(
            qset=self.qset,
            question=question2,
            answertype='SINGLELINE',
            seqno=0,  # Invalid: before qsb1 but depends on it
            client=self.client,
            bu=self.client,
            tenant_id=1,
            display_conditions={
                'depends_on': {
                    'qsb_id': self.qsb1.id,
                    'operator': 'EQUALS',
                    'values': ['Yes']
                }
            }
        )

        # save() should call full_clean() and raise error
        with self.assertRaises(ValidationError):
            qsb2.save()


@pytest.mark.security
class TestSecurityValidation(TestCase):
    """Test security aspects of validation."""

    def test_xss_prevention_in_values(self):
        """Test XSS attempts in values are blocked."""
        data = {
            'depends_on': {
                'qsb_id': 123,
                'operator': 'EQUALS',
                'values': [
                    '<script>alert("xss")</script>',
                    '<img src=x onerror=alert(1)>',
                    'javascript:alert(1)'
                ]
            }
        }

        schema = DependencySchema(**data.get('depends_on'))

        # All script tags should be removed
        for value in schema.values:
            self.assertNotIn('<script>', value.lower())
            self.assertNotIn('<img', value.lower())
            self.assertNotIn('javascript:', value.lower())

    def test_group_name_injection_prevention(self):
        """Test group name prevents injection."""
        data = {
            'group': '../../etc/passwd'
        }

        schema = DisplayConditionsSchema(**data)

        # Path traversal characters should be removed
        self.assertNotIn('..', schema.group)
        self.assertNotIn('/', schema.group)

    def test_values_length_limit(self):
        """Test excessively long values are truncated."""
        long_value = 'A' * 1000
        data = {
            'depends_on': {
                'qsb_id': 123,
                'operator': 'EQUALS',
                'values': [long_value]
            }
        }

        schema = DependencySchema(**data)

        # Should be truncated to 500 chars
        self.assertLessEqual(len(schema.values[0]), 500)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
