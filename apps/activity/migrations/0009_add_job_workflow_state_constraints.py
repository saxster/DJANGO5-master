"""
Migration to add workflow state integrity constraints and performance indexes

Prevents race conditions and data corruption through database-level enforcement:
- Valid parent relationships
- Valid status values
- Performance indexes for locking operations
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0008_add_performance_indexes'),
    ]

    operations = [
        # Ensure jobneed has valid parent (not orphaned)
        migrations.AddConstraint(
            model_name='jobneed',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(parent_id__isnull=False) |
                    models.Q(parent_id=1) |
                    models.Q(parent_id=-1)
                ),
                name='jobneed_valid_parent_ck'
            ),
        ),

        # Ensure valid job status values
        migrations.AddConstraint(
            model_name='jobneed',
            constraint=models.CheckConstraint(
                check=models.Q(jobstatus__in=[
                    'ASSIGNED',
                    'AUTOCLOSED',
                    'COMPLETED',
                    'INPROGRESS',
                    'PARTIALLYCOMPLETED',
                    'MAINTENANCE',
                    'STANDBY',
                    'WORKING'
                ]),
                name='jobneed_valid_status_ck'
            ),
        ),

        # Ensure valid job type values
        migrations.AddConstraint(
            model_name='jobneed',
            constraint=models.CheckConstraint(
                check=models.Q(jobtype__in=['SCHEDULE', 'ADHOC']),
                name='jobneed_valid_jobtype_ck'
            ),
        ),

        # Add composite index for parent-child workflow queries with status
        # This improves select_for_update() performance significantly
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['parent_id', 'jobstatus', 'mdtz'],
                name='jobneed_parent_status_mdtz_idx'
            ),
        ),

        # Add index for concurrent job updates by identifier
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['identifier', 'bu_id', 'jobstatus'],
                name='jobneed_identifier_bu_status_idx'
            ),
        ),

        # Add index for locking performance on UUID lookups
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['uuid', 'jobstatus'],
                name='jobneed_uuid_status_idx'
            ),
        ),
    ]