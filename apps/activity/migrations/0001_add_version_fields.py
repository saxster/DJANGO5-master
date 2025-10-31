"""
Add version fields for optimistic locking.

Migration for Activity models to add django-concurrency version fields.
This enables optimistic locking to prevent race conditions in concurrent updates.

Compliance with .claude/rules.md:
- Rule #17: Transaction management - prevents data corruption from concurrent updates
"""

from django.db import migrations
import concurrency.fields


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0020_migrate_to_json_fields'),
    ]

    operations = [
        # Note: Job version field added (jobneed.version already exists from 0010_add_version_field_jobneed)
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='job' AND column_name='version'
                ) THEN
                    ALTER TABLE job ADD COLUMN version INTEGER DEFAULT 0;
                END IF;
            END $$;
            """,
            reverse_sql="ALTER TABLE job DROP COLUMN IF EXISTS version;"
        ),
        # Skip jobneed.version - already added by migration 0010
    ]
