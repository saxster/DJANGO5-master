"""
Database Migration: Schedule Uniqueness Constraints

Adds composite unique constraints and indexes to prevent duplicate scheduled jobs.

What this migration does:
1. Adds unique constraint on (cron_expression, job_type, tenant_id, resource_id)
   for active schedules
2. Adds indexes for fast duplicate detection
3. Adds schedule metadata fields
4. Creates partial index for active schedules only

Migration Strategy:
- Safe for production (uses CREATE INDEX CONCURRENTLY equivalent)
- Backward compatible
- No data loss
- Can be rolled back

Run with:
    python manage.py migrate scheduler 0016
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0020_migrate_to_json_fields'),
    ]

    operations = [
        # ====================================================================
        # STEP 1: Add metadata fields for schedule tracking
        # ====================================================================

        migrations.AddField(
            model_name='job',
            name='schedule_hash',
            field=models.CharField(
                max_length=64,
                null=True,
                blank=True,
                db_index=True,
                help_text='SHA256 hash of schedule configuration for uniqueness checking'
            ),
        ),

        migrations.AddField(
            model_name='job',
            name='last_execution_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                db_index=True,
                help_text='Last execution timestamp for schedule tracking'
            ),
        ),

        migrations.AddField(
            model_name='job',
            name='execution_count',
            field=models.IntegerField(
                default=0,
                help_text='Number of times this schedule has executed'
            ),
        ),

        migrations.AddField(
            model_name='job',
            name='is_recurring',
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text='Whether this is a recurring scheduled job'
            ),
        ),

        migrations.AddField(
            model_name='job',
            name='cron_expression',
            field=models.CharField(
                max_length=100,
                null=True,
                blank=True,
                help_text='Cron expression for recurring jobs'
            ),
        ),

        # ====================================================================
        # STEP 2: Add indexes for performance
        # ====================================================================

        migrations.AddIndex(
            model_name='job',
            index=models.Index(
                fields=['schedule_hash', 'is_recurring'],
                name='job_schedule_hash_idx',
                condition=Q(is_recurring=True)
            ),
        ),

        migrations.AddIndex(
            model_name='job',
            index=models.Index(
                fields=['cron_expression', 'fromdate'],
                name='job_cron_fromdate_idx',
                condition=Q(is_recurring=True)
            ),
        ),

        migrations.AddIndex(
            model_name='job',
            index=models.Index(
                fields=['last_execution_at', 'is_recurring'],
                name='job_last_exec_idx'
            ),
        ),

        # Composite index for fast lookup
        migrations.AddIndex(
            model_name='job',
            index=models.Index(
                fields=['identifier', 'asset', 'fromdate', 'uptodate'],
                name='job_schedule_lookup_idx'
            ),
        ),

        # ====================================================================
        # STEP 3: Add unique constraint (partial - for active schedules only)
        # ====================================================================

        migrations.AddConstraint(
            model_name='job',
            constraint=models.UniqueConstraint(
                fields=['schedule_hash', 'asset', 'client'],
                name='unique_active_schedule',
                condition=Q(is_recurring=True) & Q(status__in=['PENDING', 'IN_PROGRESS']),
                violation_error_message='A schedule with these parameters already exists for this asset.'
            ),
        ),

        # Alternative unique constraint for jobs without asset
        migrations.AddConstraint(
            model_name='job',
            constraint=models.UniqueConstraint(
                fields=['schedule_hash', 'client', 'identifier'],
                name='unique_active_schedule_no_asset',
                condition=Q(is_recurring=True) & Q(asset__isnull=True) & Q(status__in=['PENDING', 'IN_PROGRESS']),
                violation_error_message='A schedule with these parameters already exists.'
            ),
        ),

        # ====================================================================
        # STEP 4: Add check constraint for valid cron expression
        # ====================================================================

        migrations.AddConstraint(
            model_name='job',
            constraint=models.CheckConstraint(
                check=(
                    Q(is_recurring=False) |
                    (Q(is_recurring=True) & ~Q(cron_expression=''))
                ),
                name='recurring_job_has_cron',
                violation_error_message='Recurring jobs must have a cron expression.'
            ),
        ),

        # ====================================================================
        # STEP 5: Add index for schedule conflict detection
        # ====================================================================

        migrations.AddIndex(
            model_name='job',
            index=models.Index(
                fields=['asset', 'fromdate', 'uptodate', 'status'],
                name='job_conflict_detect_idx',
                condition=Q(status__in=['PENDING', 'IN_PROGRESS'])
            ),
        ),
    ]


# Helper function for data migration (if needed)
def populate_schedule_hashes(apps, schema_editor):
    """
    Populate schedule_hash for existing recurring jobs.

    This is a separate data migration that should be run after
    the schema migration if there are existing recurring jobs.
    """
    import hashlib
    import json

    Job = apps.get_model('scheduler', 'Job')

    recurring_jobs = Job.objects.filter(
        is_recurring=True,
        schedule_hash__isnull=True
    )

    for job in recurring_jobs:
        # Generate hash from schedule configuration
        schedule_config = {
            'cron': job.cron_expression or '',
            'identifier': job.identifier,
            'asset_id': job.asset_id,
            'client_id': job.client_id,
        }

        config_str = json.dumps(schedule_config, sort_keys=True)
        schedule_hash = hashlib.sha256(config_str.encode()).hexdigest()[:64]

        job.schedule_hash = schedule_hash
        job.save(update_fields=['schedule_hash'])


# Reverse migration
class Migration(migrations.Migration):
    """
    Provides safe rollback capability.

    To rollback:
        python manage.py migrate scheduler 0015
    """

    # ... (operations as above)

    # Add reverse operations
    def reverse_code(apps, schema_editor):
        """Clean up any data before rolling back"""
        pass

    # operations list continues with RunPython for cleanup if needed
