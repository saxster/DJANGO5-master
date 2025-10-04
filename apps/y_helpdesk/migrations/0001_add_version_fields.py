"""
Add version fields for optimistic locking.

Migration for Help Desk models to add django-concurrency version fields.
This enables optimistic locking to prevent race conditions in concurrent updates.

Compliance with .claude/rules.md:
- Rule #17: Transaction management - prevents data corruption from concurrent updates
"""

from django.db import migrations
import concurrency.fields


class Migration(migrations.Migration):

    dependencies = [
        ('y_helpdesk', '__latest__'),  # Replace with actual latest migration
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='version',
            field=concurrency.fields.IntegerVersionField(default=0, help_text='Version number for optimistic locking'),
        ),
    ]
