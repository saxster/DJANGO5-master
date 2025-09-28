"""
Add mobile sync fields to JobNeed model

Enables offline-first mobile sync with conflict resolution.
Adds: mobile_id, last_sync_timestamp, sync_status

Following .claude/rules.md patterns for mobile sync infrastructure.
"""

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0011_add_job_workflow_audit_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobneed',
            name='mobile_id',
            field=models.UUIDField(
                null=True,
                blank=True,
                db_index=True,
                help_text='Unique identifier from mobile client for sync tracking'
            ),
        ),

        migrations.AddField(
            model_name='jobneed',
            name='last_sync_timestamp',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Last successful sync timestamp from mobile client'
            ),
        ),

        migrations.AddField(
            model_name='jobneed',
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
            model_name='jobneed',
            index=models.Index(
                fields=['mobile_id', 'version'],
                name='jobneed_mobile_sync_idx'
            ),
        ),

        # Index for querying pending syncs
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['sync_status', 'last_sync_timestamp'],
                name='jobneed_sync_status_idx'
            ),
        ),
    ]