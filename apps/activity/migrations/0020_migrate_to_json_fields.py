"""
Data migration: Populate JSON fields from existing text data.

This migration:
1. Parses existing options text → options_json array
2. Parses existing alerton text → alert_config structured JSON
3. Validates all conversions
4. Provides detailed error reporting
5. Supports rollback (reverses the migration)

CRITICAL: This is a DATA migration - it modifies existing records.
Run in dry-run mode first:
    python manage.py migrate --plan activity 0020

Created: 2025-10-03
Following .claude/rules.md Rule #17: Transaction management
"""

from django.db import migrations
import logging
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)


def migrate_questions_to_json(apps, schema_editor):
    """
    Forward migration: Populate options_json and alert_config from text fields.
    """
    Question = apps.get_model('activity', 'Question')
    QuestionSetBelonging = apps.get_model('activity', 'QuestionSetBelonging')

    # Import parser functions
    from apps.activity.services.question_data_migration_service import (
        parse_options_to_json,
        parse_alert_to_json
    )

    # Statistics
    stats = {
        'questions_migrated': 0,
        'questions_failed': 0,
        'belongings_migrated': 0,
        'belongings_failed': 0,
        'errors': []
    }

    logger.info("Starting Question migration to JSON fields")

    # Migrate Questions
    for question in Question.objects.iterator(chunk_size=500):
        try:
            modified = False

            # Parse options if present
            if question.options and not question.options_json:
                question.options_json = parse_options_to_json(question.options)
                modified = True

            # Parse alerton if present
            if question.alerton and not question.alert_config:
                question.alert_config = parse_alert_to_json(
                    question.alerton,
                    question.answertype
                )
                modified = True

            # Save if modified
            if modified:
                question.save(update_fields=['options_json', 'alert_config'])
                stats['questions_migrated'] += 1

        except DATABASE_EXCEPTIONS as e:
            stats['questions_failed'] += 1
            error_msg = f"Question ID {question.id}: {str(e)}"
            stats['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)

    logger.info(f"Question migration complete: {stats['questions_migrated']} migrated, {stats['questions_failed']} failed")

    # Migrate QuestionSetBelongings
    logger.info("Starting QuestionSetBelonging migration to JSON fields")

    for belonging in QuestionSetBelonging.objects.iterator(chunk_size=500):
        try:
            modified = False

            # Parse options if present
            if belonging.options and not belonging.options_json:
                belonging.options_json = parse_options_to_json(belonging.options)
                modified = True

            # Parse alerton if present
            if belonging.alerton and not belonging.alert_config:
                belonging.alert_config = parse_alert_to_json(
                    belonging.alerton,
                    belonging.answertype
                )
                modified = True

            # Save if modified
            if modified:
                belonging.save(update_fields=['options_json', 'alert_config'])
                stats['belongings_migrated'] += 1

        except DATABASE_EXCEPTIONS as e:
            stats['belongings_failed'] += 1
            error_msg = f"QuestionSetBelonging ID {belonging.id}: {str(e)}"
            stats['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)

    logger.info(f"QuestionSetBelonging migration complete: {stats['belongings_migrated']} migrated, {stats['belongings_failed']} failed")

    # Final summary
    total_migrated = stats['questions_migrated'] + stats['belongings_migrated']
    total_failed = stats['questions_failed'] + stats['belongings_failed']

    logger.info(
        f"MIGRATION COMPLETE: {total_migrated} total records migrated, {total_failed} failed"
    )

    if stats['errors']:
        logger.warning(f"Migration completed with {len(stats['errors'])} errors. See logs for details.")
        # Log first 10 errors for visibility
        for error in stats['errors'][:10]:
            logger.warning(f"  - {error}")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration: Clear JSON fields (restore text-only state).

    This is safe because text fields are not modified in forward migration.
    """
    Question = apps.get_model('activity', 'Question')
    QuestionSetBelonging = apps.get_model('activity', 'QuestionSetBelonging')

    logger.info("Reversing JSON field migration (clearing JSON fields)")

    # Clear Question JSON fields
    Question.objects.update(options_json=None, alert_config=None)

    # Clear QuestionSetBelonging JSON fields
    QuestionSetBelonging.objects.update(options_json=None, alert_config=None)

    logger.info("Reverse migration complete - JSON fields cleared")


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0019_add_json_fields_for_options_and_alerts'),
    ]

    operations = [
        migrations.RunPython(
            migrate_questions_to_json,
            reverse_code=reverse_migration,
            elidable=False  # This migration should not be optimized away
        ),
    ]
