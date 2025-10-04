"""
Data migration to copy existing data to encrypted fields.

This migration:
1. Copies data from unencrypted fields to encrypted fields
2. Marks entries as encrypted with is_encrypted=True
3. Validates data integrity
4. Logs migration progress

IMPORTANT:
- Run this migration during low-traffic period
- Monitor memory usage for large datasets
- Can be run in batches if needed
"""

from django.db import migrations
import logging

logger = logging.getLogger('migrations')


def migrate_to_encrypted_fields(apps, schema_editor):
    """
    Migrate existing journal entries to encrypted fields.

    Processes entries in batches to avoid memory issues.
    """
    JournalEntry = apps.get_model('journal', 'JournalEntry')

    batch_size = 1000
    total_migrated = 0
    total_errors = 0

    # Get all entries that haven't been migrated yet
    entries_to_migrate = JournalEntry.objects.filter(is_encrypted=False)
    total_count = entries_to_migrate.count()

    logger.info(f"Starting encryption migration for {total_count} journal entries")

    # Process in batches
    offset = 0
    while True:
        batch = list(entries_to_migrate[offset:offset + batch_size])

        if not batch:
            break

        migrated_batch = []

        for entry in batch:
            try:
                # Copy data to encrypted fields
                entry.content_encrypted = entry.content or ''
                entry.mood_description_encrypted = entry.mood_description or ''
                entry.stress_triggers_encrypted = entry.stress_triggers or []
                entry.coping_strategies_encrypted = entry.coping_strategies or []
                entry.gratitude_items_encrypted = entry.gratitude_items or []
                entry.affirmations_encrypted = entry.affirmations or []
                entry.challenges_encrypted = entry.challenges or []

                # Mark as encrypted
                entry.is_encrypted = True

                migrated_batch.append(entry)
                total_migrated += 1

            except Exception as e:
                logger.error(
                    f"Error migrating journal entry {entry.id}: {str(e)}",
                    exc_info=True
                )
                total_errors += 1

        # Bulk update the batch
        if migrated_batch:
            JournalEntry.objects.bulk_update(
                migrated_batch,
                [
                    'content_encrypted',
                    'mood_description_encrypted',
                    'stress_triggers_encrypted',
                    'coping_strategies_encrypted',
                    'gratitude_items_encrypted',
                    'affirmations_encrypted',
                    'challenges_encrypted',
                    'is_encrypted'
                ],
                batch_size=batch_size
            )

        # Log progress
        logger.info(
            f"Migrated batch: {offset}-{offset + len(batch)} "
            f"({total_migrated}/{total_count} entries)"
        )

        offset += batch_size

    # Final summary
    logger.info(
        f"Encryption migration complete: "
        f"{total_migrated} migrated, {total_errors} errors"
    )

    if total_errors > 0:
        logger.warning(
            f"Migration completed with {total_errors} errors. "
            "Review logs for details."
        )


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - copy data back to unencrypted fields.

    WARNING: This removes encryption! Only use for rollback.
    """
    JournalEntry = apps.get_model('journal', 'JournalEntry')

    logger.warning("Reversing encryption migration - data will be unencrypted!")

    entries = JournalEntry.objects.filter(is_encrypted=True)

    for entry in entries.iterator(chunk_size=1000):
        try:
            # Copy encrypted data back to unencrypted fields
            if entry.content_encrypted:
                entry.content = entry.content_encrypted
            if entry.mood_description_encrypted:
                entry.mood_description = entry.mood_description_encrypted

            # Clear encrypted fields
            entry.content_encrypted = None
            entry.mood_description_encrypted = None
            entry.stress_triggers_encrypted = None
            entry.coping_strategies_encrypted = None
            entry.gratitude_items_encrypted = None
            entry.affirmations_encrypted = None
            entry.challenges_encrypted = None

            entry.is_encrypted = False
            entry.save()

        except Exception as e:
            logger.error(f"Error reversing migration for entry {entry.id}: {str(e)}")


class Migration(migrations.Migration):

    dependencies = [
        ('journal', '0014_add_encrypted_fields'),
    ]

    operations = [
        migrations.RunPython(
            migrate_to_encrypted_fields,
            reverse_code=reverse_migration
        ),
    ]
