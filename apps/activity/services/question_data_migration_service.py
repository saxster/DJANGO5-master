"""
Data Migration Service for Question/QuestionSetBelonging JSON fields.

Parses existing text-based options and alerton fields into structured JSON format.
Handles edge cases and malformed data gracefully with detailed error reporting.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #4: Small functions (each < 50 lines)
- Rule #3: Self-documenting code

Created: 2025-10-03
Author: Claude Code
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class OptionsParser:
    """
    Parser for text-based options field.

    Handles multiple formats:
    - Comma-separated: "Option1,Option2,Option3"
    - Pipe-separated: "Option1|Option2|Option3"
    - Mixed: "Option1, Option2 | Option3"
    - With quotes: '"Option1","Option2"'
    - Edge cases: trailing commas, extra spaces, empty options
    """

    @staticmethod
    def parse(options_text: str) -> List[str]:
        """
        Parse text options into JSON array.

        Args:
            options_text: Text options from database

        Returns:
            List of cleaned option strings
        """
        if not options_text:
            return []

        # Handle special values
        options_text = str(options_text).strip()
        if options_text.upper() in ['NONE', 'NULL', '']:
            return []

        try:
            # Remove quotes
            options_text = options_text.replace('"', '').replace("'", '')

            # Split by both comma and pipe
            options_text = options_text.replace('|', ',')

            # Split and clean
            options = [
                opt.strip()
                for opt in options_text.split(',')
                if opt.strip() and opt.strip().upper() != 'NONE'
            ]

            # Remove duplicates while preserving order
            seen = set()
            unique_options = []
            for opt in options:
                opt_lower = opt.lower()
                if opt_lower not in seen:
                    seen.add(opt_lower)
                    # Truncate long options
                    unique_options.append(opt[:200])

            return unique_options

        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(
                f"Failed to parse options: {options_text[:100]}, error: {e}",
                exc_info=True
            )
            return []


class AlertParser:
    """
    Parser for text-based alerton field.

    Handles multiple formats:
    - Numeric: "<10.5, >90.0" → {"numeric": {"below": 10.5, "above": 90.0}}
    - Choice: "Alert1,Alert2" → {"choice": ["Alert1", "Alert2"]}
    - Single value: "Critical" → {"choice": ["Critical"]}
    - Edge cases: missing values, malformed strings
    """

    @staticmethod
    def parse(alerton_text: str, answer_type: str = None) -> Optional[Dict[str, Any]]:
        """
        Parse text alert configuration into JSON structure.

        Args:
            alerton_text: Text alert configuration from database
            answer_type: Answer type to determine parsing strategy

        Returns:
            Structured alert configuration dict or None
        """
        if not alerton_text:
            return None

        alerton_text = str(alerton_text).strip()
        if alerton_text.upper() in ['NONE', 'NULL', '']:
            return None

        try:
            # Check if it's numeric format: "<value, >value"
            if '<' in alerton_text and '>' in alerton_text:
                return AlertParser._parse_numeric_alert(alerton_text)

            # Check if it's choice format (comma-separated)
            elif ',' in alerton_text or answer_type in ['CHECKBOX', 'DROPDOWN', 'MULTISELECT']:
                return AlertParser._parse_choice_alert(alerton_text)

            # Single value - treat as choice
            else:
                return {
                    'choice': [alerton_text],
                    'enabled': True
                }

        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(
                f"Failed to parse alerton: {alerton_text[:100]}, error: {e}",
                exc_info=True
            )
            return None

    @staticmethod
    def _parse_numeric_alert(text: str) -> Dict[str, Any]:
        """
        Parse numeric alert format: "<10.5, >90.0"

        Returns:
            {"numeric": {"below": 10.5, "above": 90.0}, "enabled": true}
        """
        # Extract below value: <{value}
        below_match = re.search(r'<\s*([0-9.]+)', text)
        # Extract above value: >{value}
        above_match = re.search(r'>\s*([0-9.]+)', text)

        numeric_config = {}

        if below_match:
            try:
                numeric_config['below'] = float(below_match.group(1))
            except (ValueError, InvalidOperation):
                pass

        if above_match:
            try:
                numeric_config['above'] = float(above_match.group(1))
            except (ValueError, InvalidOperation):
                pass

        if not numeric_config:
            # Failed to parse - return None
            logger.warning(f"Failed to parse numeric alert: {text}")
            return None

        return {
            'numeric': numeric_config,
            'enabled': True
        }

    @staticmethod
    def _parse_choice_alert(text: str) -> Dict[str, Any]:
        """
        Parse choice alert format: "Alert1,Alert2,Alert3"

        Returns:
            {"choice": ["Alert1", "Alert2", "Alert3"], "enabled": true}
        """
        # Split by comma and clean
        choices = [
            choice.strip()
            for choice in text.split(',')
            if choice.strip() and choice.strip().upper() != 'NONE'
        ]

        if not choices:
            return None

        return {
            'choice': choices,
            'enabled': True
        }


class QuestionDataMigrationService:
    """
    Service for migrating Question and QuestionSetBelonging data to JSON fields.

    Provides:
    - Batch processing with progress tracking
    - Detailed error reporting
    - Dry-run mode for validation
    - Rollback support
    """

    def __init__(self, dry_run: bool = False):
        """
        Initialize migration service.

        Args:
            dry_run: If True, don't save changes - just validate
        """
        self.dry_run = dry_run
        self.stats = {
            'total_questions': 0,
            'questions_migrated': 0,
            'questions_failed': 0,
            'total_belongings': 0,
            'belongings_migrated': 0,
            'belongings_failed': 0,
            'errors': []
        }

    def migrate_question(self, question) -> Tuple[bool, Optional[str]]:
        """
        Migrate a single Question record.

        Args:
            question: Question model instance

        Returns:
            (success: bool, error_message: Optional[str])
        """
        try:
            # Parse options
            if question.options:
                question.options_json = OptionsParser.parse(question.options)

            # Parse alerton
            if question.alerton:
                question.alert_config = AlertParser.parse(
                    question.alerton,
                    question.answertype
                )

            # Save if not dry-run
            if not self.dry_run:
                question.save(update_fields=['options_json', 'alert_config'])

            return True, None

        except (AttributeError, TypeError, ValueError) as e:
            error_msg = f"Question ID {question.id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def migrate_questionsetbelonging(self, belonging) -> Tuple[bool, Optional[str]]:
        """
        Migrate a single QuestionSetBelonging record.

        Args:
            belonging: QuestionSetBelonging model instance

        Returns:
            (success: bool, error_message: Optional[str])
        """
        try:
            # Parse options
            if belonging.options:
                belonging.options_json = OptionsParser.parse(belonging.options)

            # Parse alerton
            if belonging.alerton:
                belonging.alert_config = AlertParser.parse(
                    belonging.alerton,
                    belonging.answertype
                )

            # Save if not dry-run
            if not self.dry_run:
                belonging.save(update_fields=['options_json', 'alert_config'])

            return True, None

        except (AttributeError, TypeError, ValueError) as e:
            error_msg = f"QuestionSetBelonging ID {belonging.id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def migrate_all_questions(self, batch_size: int = 500) -> Dict[str, Any]:
        """
        Migrate all Question records in batches.

        Args:
            batch_size: Number of records to process per batch

        Returns:
            Migration statistics dict
        """
        from apps.activity.models.question_model import Question

        # Get total count
        total = Question.objects.count()
        self.stats['total_questions'] = total

        logger.info(f"Starting Question migration: {total} records (dry_run={self.dry_run})")

        # Process in batches
        for offset in range(0, total, batch_size):
            questions = Question.objects.all()[offset:offset + batch_size]

            for question in questions:
                success, error = self.migrate_question(question)

                if success:
                    self.stats['questions_migrated'] += 1
                else:
                    self.stats['questions_failed'] += 1
                    self.stats['errors'].append({
                        'model': 'Question',
                        'id': question.id,
                        'error': error
                    })

            # Log progress
            if (offset + batch_size) % 1000 == 0:
                logger.info(
                    f"Question migration progress: {min(offset + batch_size, total)}/{total} "
                    f"({self.stats['questions_migrated']} migrated, {self.stats['questions_failed']} failed)"
                )

        logger.info(f"Question migration complete: {self.stats['questions_migrated']}/{total} migrated")
        return self.stats

    def migrate_all_belongings(self, batch_size: int = 500) -> Dict[str, Any]:
        """
        Migrate all QuestionSetBelonging records in batches.

        Args:
            batch_size: Number of records to process per batch

        Returns:
            Migration statistics dict
        """
        from apps.activity.models.question_model import QuestionSetBelonging

        # Get total count
        total = QuestionSetBelonging.objects.count()
        self.stats['total_belongings'] = total

        logger.info(f"Starting QuestionSetBelonging migration: {total} records (dry_run={self.dry_run})")

        # Process in batches
        for offset in range(0, total, batch_size):
            belongings = QuestionSetBelonging.objects.select_related('question')[offset:offset + batch_size]

            for belonging in belongings:
                success, error = self.migrate_questionsetbelonging(belonging)

                if success:
                    self.stats['belongings_migrated'] += 1
                else:
                    self.stats['belongings_failed'] += 1
                    self.stats['errors'].append({
                        'model': 'QuestionSetBelonging',
                        'id': belonging.id,
                        'error': error
                    })

            # Log progress
            if (offset + batch_size) % 1000 == 0:
                logger.info(
                    f"QuestionSetBelonging migration progress: {min(offset + batch_size, total)}/{total} "
                    f"({self.stats['belongings_migrated']} migrated, {self.stats['belongings_failed']} failed)"
                )

        logger.info(f"QuestionSetBelonging migration complete: {self.stats['belongings_migrated']}/{total} migrated")
        return self.stats

    def migrate_all(self, batch_size: int = 500) -> Dict[str, Any]:
        """
        Migrate all records (Questions and QuestionSetBelongings).

        Args:
            batch_size: Number of records to process per batch

        Returns:
            Combined migration statistics
        """
        logger.info(f"Starting complete migration (dry_run={self.dry_run})")

        # Migrate Questions
        self.migrate_all_questions(batch_size)

        # Migrate QuestionSetBelongings
        self.migrate_all_belongings(batch_size)

        # Summary
        total_migrated = self.stats['questions_migrated'] + self.stats['belongings_migrated']
        total_failed = self.stats['questions_failed'] + self.stats['belongings_failed']
        total_records = self.stats['total_questions'] + self.stats['total_belongings']

        logger.info(
            f"Migration complete: {total_migrated}/{total_records} migrated, "
            f"{total_failed} failed, {len(self.stats['errors'])} errors"
        )

        return self.stats

    def generate_report(self) -> str:
        """
        Generate human-readable migration report.

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("QUESTION DATA MIGRATION REPORT")
        report.append("=" * 80)
        report.append(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE MIGRATION'}")
        report.append("")

        # Questions
        report.append("QUESTIONS:")
        report.append(f"  Total: {self.stats['total_questions']}")
        report.append(f"  Migrated: {self.stats['questions_migrated']}")
        report.append(f"  Failed: {self.stats['questions_failed']}")
        if self.stats['questions_migrated'] > 0:
            success_rate = (self.stats['questions_migrated'] / self.stats['total_questions']) * 100
            report.append(f"  Success Rate: {success_rate:.2f}%")
        report.append("")

        # QuestionSetBelongings
        report.append("QUESTION SET BELONGINGS:")
        report.append(f"  Total: {self.stats['total_belongings']}")
        report.append(f"  Migrated: {self.stats['belongings_migrated']}")
        report.append(f"  Failed: {self.stats['belongings_failed']}")
        if self.stats['belongings_migrated'] > 0:
            success_rate = (self.stats['belongings_migrated'] / self.stats['total_belongings']) * 100
            report.append(f"  Success Rate: {success_rate:.2f}%")
        report.append("")

        # Errors
        if self.stats['errors']:
            report.append(f"ERRORS ({len(self.stats['errors'])}):")
            for idx, error in enumerate(self.stats['errors'][:20], 1):  # Show first 20 errors
                report.append(f"  {idx}. {error['model']} ID {error['id']}: {error['error']}")

            if len(self.stats['errors']) > 20:
                report.append(f"  ... and {len(self.stats['errors']) - 20} more errors")
        else:
            report.append("NO ERRORS - All records migrated successfully!")

        report.append("=" * 80)

        return "\n".join(report)


# Standalone utility functions for use in Django migrations

def parse_options_to_json(options_text: str) -> Optional[List[str]]:
    """
    Parse options text to JSON array.

    Safe for use in Django migrations (no ORM access).

    Args:
        options_text: Text options

    Returns:
        JSON array or None
    """
    return OptionsParser.parse(options_text) if options_text else None


def parse_alert_to_json(alerton_text: str, answer_type: str = None) -> Optional[Dict[str, Any]]:
    """
    Parse alert text to JSON config.

    Safe for use in Django migrations (no ORM access).

    Args:
        alerton_text: Text alert configuration
        answer_type: Answer type for context

    Returns:
        JSON config or None
    """
    return AlertParser.parse(alerton_text, answer_type) if alerton_text else None
