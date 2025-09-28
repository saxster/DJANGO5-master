"""
Add JobWorkflowAuditLog model for comprehensive workflow tracking

Provides immutable audit trail of all job/jobneed state transitions
for compliance, debugging, and performance monitoring.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.core.serializers.json
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0010_add_version_field_jobneed'),
        ('peoples', '0003_add_performance_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobWorkflowAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('operation_type', models.CharField(
                    choices=[
                        ('STATUS_CHANGE', 'Status Change'),
                        ('ASSIGNMENT_CHANGE', 'Assignment Change'),
                        ('CHECKPOINT_UPDATE', 'Checkpoint Update'),
                        ('AUTOCLOSE', 'Auto Close'),
                        ('ESCALATION', 'Escalation'),
                        ('CREATION', 'Creation'),
                        ('DELETION', 'Deletion')
                    ],
                    db_index=True,
                    help_text='Type of workflow operation',
                    max_length=50
                )),
                ('old_status', models.CharField(blank=True, help_text='Previous status value', max_length=60, null=True)),
                ('new_status', models.CharField(blank=True, help_text='New status value', max_length=60, null=True)),
                ('old_assignment_person_id', models.BigIntegerField(blank=True, help_text='Previous assigned person ID', null=True)),
                ('new_assignment_person_id', models.BigIntegerField(blank=True, help_text='New assigned person ID', null=True)),
                ('old_assignment_group_id', models.BigIntegerField(blank=True, help_text='Previous assigned group ID', null=True)),
                ('new_assignment_group_id', models.BigIntegerField(blank=True, help_text='New assigned group ID', null=True)),
                ('change_timestamp', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When the change occurred')),
                ('lock_acquisition_time_ms', models.IntegerField(blank=True, help_text='Time taken to acquire lock (milliseconds)', null=True)),
                ('transaction_duration_ms', models.IntegerField(blank=True, help_text='Total transaction duration (milliseconds)', null=True)),
                ('metadata', models.JSONField(default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder, help_text='Additional metadata about the change')),
                ('correlation_id', models.CharField(blank=True, db_index=True, help_text='Correlation ID for tracing related operations', max_length=100, null=True)),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created date time')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified date time')),
                ('ctzoffset', models.IntegerField(default=0, verbose_name='Client time zone offset')),
                ('enable', models.BooleanField(default=True)),
                ('bu', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='%(class)s_bus', to='onboarding.bt')),
                ('changed_by', models.ForeignKey(help_text='User or system that made the change', on_delete=django.db.models.deletion.RESTRICT, related_name='job_workflow_changes', to=settings.AUTH_USER_MODEL)),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='%(class)s_clients', to='onboarding.bt')),
                ('cuser', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='%(class)s_cusers', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('job', models.ForeignKey(blank=True, help_text='Parent job (if applicable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workflow_audit_logs', to='activity.job')),
                ('jobneed', models.ForeignKey(help_text='Jobneed that was modified', on_delete=django.db.models.deletion.CASCADE, related_name='workflow_audit_logs', to='activity.jobneed')),
                ('muser', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='%(class)s_musers', to=settings.AUTH_USER_MODEL, verbose_name='Modified by')),
            ],
            options={
                'verbose_name': 'Job Workflow Audit Log',
                'verbose_name_plural': 'Job Workflow Audit Logs',
                'db_table': 'job_workflow_audit_log',
                'ordering': ['-change_timestamp'],
                'indexes': [
                    models.Index(fields=['jobneed', 'change_timestamp'], name='audit_jobneed_ts_idx'),
                    models.Index(fields=['operation_type', 'change_timestamp'], name='audit_op_ts_idx'),
                    models.Index(fields=['changed_by', 'change_timestamp'], name='audit_user_ts_idx'),
                    models.Index(fields=['old_status', 'new_status'], name='audit_status_transition_idx'),
                ],
            },
        ),
    ]