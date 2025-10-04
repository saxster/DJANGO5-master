"""
Sync Migration Helpers - Standardized database migration utilities

Eliminates duplicate migration patterns for adding mobile sync fields.
Provides reusable functions for consistent sync field addition.

Following .claude/rules.md:
- Rule #7: Helper functions <50 lines each
- Rule #12: Consistent database indexes
"""

from django.db import migrations, models
import uuid


def add_sync_fields_to_model(apps, schema_editor, app_label: str, model_name: str):
    """
    Add standardized sync fields to an existing model.

    This helper replaces the duplicate patterns found in:
    - apps/activity/migrations/0012_add_mobile_sync_fields.py
    - apps/y_helpdesk/migrations/0011_add_mobile_sync_fields.py
    - apps/attendance/migrations/0011_add_mobile_sync_fields.py

    Args:
        apps: Django apps registry
        schema_editor: Schema editor for database operations
        app_label: App name (e.g., 'activity', 'y_helpdesk')
        model_name: Model name (e.g., 'jobneed', 'ticket')
    """
    operations = [
        # Add mobile_id field
        migrations.AddField(
            model_name=model_name,
            name='mobile_id',
            field=models.UUIDField(
                null=True,
                blank=True,
                db_index=True,
                help_text='Unique identifier from mobile client for sync tracking'
            ),
        ),

        # Add last_sync_timestamp field
        migrations.AddField(
            model_name=model_name,
            name='last_sync_timestamp',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Last successful sync timestamp from mobile client'
            ),
        ),

        # Add sync_status field
        migrations.AddField(
            model_name=model_name,
            name='sync_status',
            field=models.CharField(
                max_length=20,
                default='synced',
                choices=[
                    ('synced', 'Synced'),
                    ('pending_sync', 'Pending Sync'),
                    ('sync_error', 'Sync Error'),
                    ('pending_delete', 'Pending Delete'),
                    ('conflict', 'Conflict Detected'),
                ],
                help_text='Current sync status for mobile client'
            ),
        ),

        # Add version field for optimistic locking
        migrations.AddField(
            model_name=model_name,
            name='version',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Version number for optimistic locking'
            ),
        ),

        # Add composite index for efficient sync queries
        migrations.AddIndex(
            model_name=model_name,
            index=models.Index(
                fields=['mobile_id', 'version'],
                name=f'{app_label}_{model_name}_sync_idx'
            ),
        ),

        # Add index for querying pending syncs
        migrations.AddIndex(
            model_name=model_name,
            index=models.Index(
                fields=['sync_status', 'last_sync_timestamp'],
                name=f'{app_label}_{model_name}_status_idx'
            ),
        ),
    ]

    return operations


def add_conflict_tracking_fields(apps, schema_editor, app_label: str, model_name: str):
    """
    Add conflict tracking fields to a model.

    For models that need advanced conflict resolution capabilities.

    Args:
        apps: Django apps registry
        schema_editor: Schema editor for database operations
        app_label: App name
        model_name: Model name
    """
    operations = [
        # Add conflict resolution field
        migrations.AddField(
            model_name=model_name,
            name='conflict_resolution',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('none', 'No Conflict'),
                    ('client_wins', 'Client Version Wins'),
                    ('server_wins', 'Server Version Wins'),
                    ('manual_required', 'Manual Resolution Required'),
                    ('merged', 'Merged Resolution'),
                ],
                default='none',
                help_text='How conflicts should be resolved for this record'
            ),
        ),

        # Add conflict metadata field
        migrations.AddField(
            model_name=model_name,
            name='conflict_data',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Metadata about conflicts and resolution attempts'
            ),
        ),

        # Add conflict timing fields
        migrations.AddField(
            model_name=model_name,
            name='conflict_detected_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='When conflict was first detected'
            ),
        ),

        migrations.AddField(
            model_name=model_name,
            name='conflict_resolved_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='When conflict was resolved'
            ),
        ),

        # Add conflict indexes
        migrations.AddIndex(
            model_name=model_name,
            index=models.Index(
                fields=['conflict_resolution'],
                name=f'{app_label}_{model_name}_conflict_idx'
            ),
        ),

        migrations.AddIndex(
            model_name=model_name,
            index=models.Index(
                fields=['conflict_detected_at'],
                name=f'{app_label}_{model_name}_conflict_time_idx'
            ),
        ),
    ]

    return operations


def add_sync_metrics_fields(apps, schema_editor, app_label: str, model_name: str):
    """
    Add sync performance metrics fields to a model.

    For models that need detailed sync monitoring capabilities.

    Args:
        apps: Django apps registry
        schema_editor: Schema editor for database operations
        app_label: App name
        model_name: Model name
    """
    operations = [
        # Add sync attempt counters
        migrations.AddField(
            model_name=model_name,
            name='sync_attempts',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of sync attempts for this record'
            ),
        ),

        migrations.AddField(
            model_name=model_name,
            name='sync_failures',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of failed sync attempts'
            ),
        ),

        # Add timing metrics
        migrations.AddField(
            model_name=model_name,
            name='last_sync_duration_ms',
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                help_text='Duration of last sync operation in milliseconds'
            ),
        ),

        migrations.AddField(
            model_name=model_name,
            name='avg_sync_duration_ms',
            field=models.FloatField(
                default=0.0,
                help_text='Average sync duration across all attempts'
            ),
        ),

        # Add metrics index for performance queries
        migrations.AddIndex(
            model_name=model_name,
            index=models.Index(
                fields=['sync_attempts', 'sync_failures'],
                name=f'{app_label}_{model_name}_metrics_idx'
            ),
        ),
    ]

    return operations


def remove_sync_fields_from_model(apps, schema_editor, app_label: str, model_name: str):
    """
    Remove sync fields from a model (for migration rollbacks).

    Args:
        apps: Django apps registry
        schema_editor: Schema editor for database operations
        app_label: App name
        model_name: Model name
    """
    operations = [
        # Remove indexes first
        migrations.RemoveIndex(
            model_name=model_name,
            name=f'{app_label}_{model_name}_sync_idx',
        ),

        migrations.RemoveIndex(
            model_name=model_name,
            name=f'{app_label}_{model_name}_status_idx',
        ),

        # Remove fields
        migrations.RemoveField(
            model_name=model_name,
            name='mobile_id',
        ),

        migrations.RemoveField(
            model_name=model_name,
            name='last_sync_timestamp',
        ),

        migrations.RemoveField(
            model_name=model_name,
            name='sync_status',
        ),

        migrations.RemoveField(
            model_name=model_name,
            name='version',
        ),
    ]

    return operations


def create_sync_migration_template(app_label: str, model_name: str, include_conflicts: bool = False, include_metrics: bool = False):
    """
    Generate a complete migration template for adding sync capabilities.

    Args:
        app_label: App name
        model_name: Model name
        include_conflicts: Whether to include conflict tracking fields
        include_metrics: Whether to include sync metrics fields

    Returns:
        String containing complete migration file content
    """
    template = f'''"""
Add mobile sync fields to {model_name.title()} model

Enables offline-first mobile sync with conflict resolution.
Generated using sync_migration_helpers.

Following .claude/rules.md patterns for mobile sync infrastructure.
"""

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('{app_label}', 'XXXX_previous_migration'),
    ]

    operations = ['''

    # Add basic sync fields
    basic_fields = '''
        # Add mobile sync fields
        migrations.AddField(
            model_name='{model_name}',
            name='mobile_id',
            field=models.UUIDField(
                null=True,
                blank=True,
                db_index=True,
                help_text='Unique identifier from mobile client for sync tracking'
            ),
        ),

        migrations.AddField(
            model_name='{model_name}',
            name='last_sync_timestamp',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Last successful sync timestamp from mobile client'
            ),
        ),

        migrations.AddField(
            model_name='{model_name}',
            name='sync_status',
            field=models.CharField(
                max_length=20,
                default='synced',
                choices=[
                    ('synced', 'Synced'),
                    ('pending_sync', 'Pending Sync'),
                    ('sync_error', 'Sync Error'),
                    ('pending_delete', 'Pending Delete'),
                    ('conflict', 'Conflict Detected'),
                ],
                help_text='Current sync status for mobile client'
            ),
        ),

        migrations.AddField(
            model_name='{model_name}',
            name='version',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Version number for optimistic locking'
            ),
        ),

        # Composite index for efficient sync queries
        migrations.AddIndex(
            model_name='{model_name}',
            index=models.Index(
                fields=['mobile_id', 'version'],
                name='{app_label}_{model_name}_sync_idx'
            ),
        ),

        # Index for querying pending syncs
        migrations.AddIndex(
            model_name='{model_name}',
            index=models.Index(
                fields=['sync_status', 'last_sync_timestamp'],
                name='{app_label}_{model_name}_status_idx'
            ),
        ),'''

    template += basic_fields

    if include_conflicts:
        conflict_fields = f'''

        # Add conflict tracking fields
        migrations.AddField(
            model_name='{model_name}',
            name='conflict_resolution',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('none', 'No Conflict'),
                    ('client_wins', 'Client Version Wins'),
                    ('server_wins', 'Server Version Wins'),
                    ('manual_required', 'Manual Resolution Required'),
                    ('merged', 'Merged Resolution'),
                ],
                default='none',
                help_text='How conflicts should be resolved for this record'
            ),
        ),

        migrations.AddField(
            model_name='{model_name}',
            name='conflict_data',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Metadata about conflicts and resolution attempts'
            ),
        ),

        migrations.AddIndex(
            model_name='{model_name}',
            index=models.Index(
                fields=['conflict_resolution'],
                name='{app_label}_{model_name}_conflict_idx'
            ),
        ),'''
        template += conflict_fields

    if include_metrics:
        metrics_fields = f'''

        # Add sync metrics fields
        migrations.AddField(
            model_name='{model_name}',
            name='sync_attempts',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of sync attempts for this record'
            ),
        ),

        migrations.AddField(
            model_name='{model_name}',
            name='sync_failures',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of failed sync attempts'
            ),
        ),'''
        template += metrics_fields

    template += '''
    ]
'''

    return template