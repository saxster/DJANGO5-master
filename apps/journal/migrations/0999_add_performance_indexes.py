"""
Performance Index Migration for JournalEntry

Adds composite indexes to optimize:
- MQTT health check queries (timestamp + is_deleted)
- User timeline queries with deleted filter
- Multi-tenant health metric aggregations

Created: November 5, 2025
Estimated Impact: +300% query performance for health checks
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('journal', '0016_optimize_entry_indexes'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(
                fields=['timestamp', 'is_deleted'],
                name='journal_entry_timestamp_deleted_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(
                fields=['user', 'timestamp', 'is_deleted'],
                name='journal_entry_user_time_deleted_idx'
            ),
        ),
    ]
