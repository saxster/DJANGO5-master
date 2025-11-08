"""
Data migration to copy existing intervention data to encrypted fields.

This migration:
1. Copies user_response data to encrypted field
2. Marks entries as encrypted with is_encrypted=True
3. Processes in batches for large datasets
"""

from django.db import migrations
import logging
# Migration-specific exceptions
ENCRYPTION_EXCEPTIONS = (ValueError, TypeError, UnicodeDecodeError, UnicodeEncodeError, AttributeError)

logger = logging.getLogger('migrations')


def migrate_to_encrypted_fields(apps, schema_editor):
    """
    Migrate existing intervention delivery logs to encrypted fields.
    """
    InterventionDeliveryLog = apps.get_model('wellness', 'InterventionDeliveryLog')

    batch_size = 1000
    total_migrated = 0
    total_errors = 0

    # Get all entries that haven't been migrated yet
    entries_to_migrate = InterventionDeliveryLog.objects.filter(is_encrypted=False)
    total_count = entries_to_migrate.count()

    logger.info(f"Starting encryption migration for {total_count} intervention delivery logs")

    # Process in batches
    offset = 0
    while True:
        batch = list(entries_to_migrate[offset:offset + batch_size])

        if not batch:
            break

        migrated_batch = []

        for entry in batch:
            try:
                # Copy data to encrypted field
                entry.user_response_encrypted = entry.user_response or {}

                # Mark as encrypted
                entry.is_encrypted = True

                migrated_batch.append(entry)
                total_migrated += 1

            except ENCRYPTION_EXCEPTIONS as e:
                logger.error(
                    f"Error migrating intervention delivery log {entry.id}: {str(e)}",
                    exc_info=True
                )
                total_errors += 1

        # Bulk update the batch
        if migrated_batch:
            InterventionDeliveryLog.objects.bulk_update(
                migrated_batch,
                ['user_response_encrypted', 'is_encrypted'],
                batch_size=batch_size
            )

        logger.info(
            f"Migrated batch: {offset}-{offset + len(batch)} "
            f"({total_migrated}/{total_count} entries)"
        )

        offset += batch_size

    logger.info(
        f"Encryption migration complete: "
        f"{total_migrated} migrated, {total_errors} errors"
    )


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - copy data back to unencrypted field.
    """
    InterventionDeliveryLog = apps.get_model('wellness', 'InterventionDeliveryLog')

    logger.warning("Reversing encryption migration - data will be unencrypted!", exc_info=True)

    entries = InterventionDeliveryLog.objects.filter(is_encrypted=True)

    for entry in entries.iterator(chunk_size=1000):
        try:
            if entry.user_response_encrypted:
                entry.user_response = entry.user_response_encrypted

            entry.user_response_encrypted = None
            entry.is_encrypted = False
            entry.save()

        except ENCRYPTION_EXCEPTIONS as e:
            logger.error(f"Error reversing migration for entry {entry.id}: {str(e)}", exc_info=True)


class Migration(migrations.Migration):

    dependencies = [
        ('wellness', '0004_add_encrypted_fields'),
    ]

    operations = [
        migrations.RunPython(
            migrate_to_encrypted_fields,
            reverse_code=reverse_migration
        ),
    ]
