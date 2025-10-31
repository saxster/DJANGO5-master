"""
Add version fields for optimistic locking.

Migration for Attendance models to add django-concurrency version fields.
This enables optimistic locking to prevent race conditions in concurrent updates.

Compliance with .claude/rules.md:
- Rule #17: Transaction management - prevents data corruption from concurrent updates
"""

from django.db import migrations
import concurrency.fields


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0011_add_mobile_sync_fields'),
    ]

    operations = [
        # Note: Make idempotent - version field may already exist from earlier migrations
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='peopleeventlog' AND column_name='version'
                ) THEN
                    ALTER TABLE peopleeventlog ADD COLUMN version INTEGER DEFAULT 0;
                END IF;
            END $$;
            """,
            reverse_sql="ALTER TABLE peopleeventlog DROP COLUMN IF EXISTS version;"
        ),
    ]
