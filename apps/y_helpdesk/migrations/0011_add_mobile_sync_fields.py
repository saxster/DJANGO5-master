"""
Add mobile sync fields to Ticket model

Enables offline-first mobile sync with conflict resolution for helpdesk tickets.
Adds: mobile_id, last_sync_timestamp, sync_status
Note: version field already exists from 0002_add_version_field_ticket.py

Following .claude/rules.md patterns for mobile sync infrastructure.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('y_helpdesk', '0010_add_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='mobile_id',
            field=models.UUIDField(
                null=True,
                blank=True,
                db_index=True,
                help_text='Unique identifier from mobile client for sync tracking'
            ),
        ),

        migrations.AddField(
            model_name='ticket',
            name='last_sync_timestamp',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Last successful sync timestamp from mobile client'
            ),
        ),

        migrations.AddField(
            model_name='ticket',
            name='sync_status',
            field=models.CharField(
                max_length=20,
                default='synced',
                choices=[
                    ('synced', 'Synced'),
                    ('pending_sync', 'Pending Sync'),
                    ('sync_error', 'Sync Error'),
                    ('pending_delete', 'Pending Delete'),
                ],
                help_text='Current sync status for mobile client'
            ),
        ),

        # Composite index for efficient sync queries (version already indexed)
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(
                fields=['mobile_id', 'version'],
                name='ticket_mobile_sync_idx'
            ),
        ),

        # Index for querying pending syncs
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(
                fields=['sync_status', 'last_sync_timestamp'],
                name='ticket_sync_status_idx'
            ),
        ),
    ]