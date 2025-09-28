"""
Add mobile sync fields to Tracking model

Enables offline-first mobile sync with conflict resolution for attendance records.
Adds: mobile_id, version, last_sync_timestamp, sync_status

Following .claude/rules.md patterns for mobile sync infrastructure.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0010_add_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='tracking',
            name='mobile_id',
            field=models.UUIDField(
                null=True,
                blank=True,
                db_index=True,
                help_text='Unique identifier from mobile client for sync tracking'
            ),
        ),

        migrations.AddField(
            model_name='tracking',
            name='version',
            field=models.IntegerField(
                default=1,
                help_text='Version number for optimistic locking and conflict resolution'
            ),
        ),

        migrations.AddField(
            model_name='tracking',
            name='last_sync_timestamp',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Last successful sync timestamp from mobile client'
            ),
        ),

        migrations.AddField(
            model_name='tracking',
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

        # Composite index for efficient sync queries
        migrations.AddIndex(
            model_name='tracking',
            index=models.Index(
                fields=['mobile_id', 'version'],
                name='tracking_mobile_sync_idx'
            ),
        ),

        # Index for querying pending syncs and delta changes
        migrations.AddIndex(
            model_name='tracking',
            index=models.Index(
                fields=['sync_status', 'last_sync_timestamp'],
                name='tracking_sync_status_idx'
            ),
        ),
    ]