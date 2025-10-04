"""
Add Unique Constraints to JobneedDetails

CRITICAL: Run scripts/cleanup_jobneeddetails_duplicates.py BEFORE this migration!

This migration adds database-level constraints to prevent:
1. Duplicate questions within the same jobneed
2. Duplicate sequence numbers within the same jobneed

Benefits:
- Prevents data corruption from duplicate checklist items
- Ensures sequence ordering integrity
- Improves query performance with unique indexes

Rollback Plan:
- Remove constraints if needed, but duplicates may reappear

Follows .claude/rules.md Rule #17: Transaction-based migrations
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0013_add_spatial_indexes'),
    ]

    operations = [
        # Add unique constraint for (jobneed, question) pairs
        # Prevents duplicate questions in the same jobneed
        migrations.AddConstraint(
            model_name='jobneeddetails',
            constraint=models.UniqueConstraint(
                fields=['jobneed', 'question'],
                name='jobneeddetails_jobneed_question_uk',
                violation_error_message=(
                    "Duplicate question not allowed for the same jobneed. "
                    "Each question can only appear once per jobneed."
                )
            ),
        ),

        # Add unique constraint for (jobneed, seqno) pairs
        # Ensures sequence number uniqueness within a jobneed
        migrations.AddConstraint(
            model_name='jobneeddetails',
            constraint=models.UniqueConstraint(
                fields=['jobneed', 'seqno'],
                name='jobneeddetails_jobneed_seqno_uk',
                violation_error_message=(
                    "Duplicate sequence number not allowed for the same jobneed. "
                    "Each seqno must be unique within a jobneed."
                )
            ),
        ),
    ]
