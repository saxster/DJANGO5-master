"""
Add version field for optimistic locking on Jobneed model

Enables detection of concurrent modifications to prevent race conditions
in job workflow state transitions and JSON field updates.

Following .claude/rules.md security and architecture patterns.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0009_add_job_workflow_state_constraints'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobneed',
            name='version',
            field=models.IntegerField(
                default=0,
                help_text='Version number for optimistic locking. Incremented on each update.'
            ),
        ),

        migrations.AddField(
            model_name='jobneed',
            name='last_modified_by',
            field=models.CharField(
                max_length=100,
                null=True,
                blank=True,
                help_text='System component or user that last modified this record'
            ),
        ),

        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['id', 'version'],
                name='jobneed_id_version_idx'
            ),
        ),

        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['uuid', 'version', 'jobstatus'],
                name='jobneed_uuid_ver_status_idx'
            ),
        ),

        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['parent_id', 'version', 'mdtz'],
                name='jobneed_parent_ver_mdtz_idx'
            ),
        ),
    ]