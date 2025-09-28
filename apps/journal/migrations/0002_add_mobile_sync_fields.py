"""
Add mobile sync fields to Journal models

Enables offline-first mobile sync with conflict resolution for journal entries.
Journal already has mobile_id and version from initial migration,
this adds last_sync_timestamp and sync_status for completeness.

Following .claude/rules.md patterns for mobile sync infrastructure.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('journal', '0001_initial'),
    ]

    operations = [
        # Note: JournalEntry already has mobile_id and version from 0001_initial
        # Only adding sync tracking fields

        migrations.AddField(
            model_name='journalentry',
            name='last_sync_timestamp',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Last successful sync timestamp from mobile client'
            ),
        ),

        migrations.AddField(
            model_name='journalentry',
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

        # Index for querying pending syncs
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(
                fields=['sync_status', 'last_sync_timestamp'],
                name='journal_sync_status_idx'
            ),
        ),

        # Also add sync fields to media attachments
        migrations.AddField(
            model_name='journalmediaattachment',
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
    ]