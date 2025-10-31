"""
Add comprehensive audit logging models.

Creates tables for:
- AuditLog: General audit trail for all entity changes
- StateTransitionAudit: Specialized audit for state machine transitions
- BulkOperationAudit: Audit trail for bulk operations
- PermissionDenialAudit: Security audit for permission denials

Compliance with .claude/rules.md:
- Rule #15: PII redaction in audit logs
- Rule #17: Transaction management
"""

from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields
import uuid
from django.conf import settings
from apps.core.constants.datetime_constants import SECONDS_IN_DAY


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('correlation_id', models.UUIDField(default=uuid.uuid4, db_index=True, help_text='Links related audit events together')),
                ('event_type', models.CharField(
                    max_length=30,
                    choices=[
                        ('CREATED', 'Entity Created'),
                        ('UPDATED', 'Entity Updated'),
                        ('DELETED', 'Entity Deleted'),
                        ('STATE_CHANGED', 'State Transition'),
                        ('BULK_OPERATION', 'Bulk Operation'),
                        ('PERMISSION_DENIED', 'Permission Denied'),
                    ],
                    db_index=True,
                )),
                ('object_id', models.CharField(max_length=255, db_index=True)),
                ('changes', models.JSONField(default=dict, help_text='PII-redacted change data')),
                ('ip_address', models.GenericIPAddressField(null=True, blank=True)),
                ('user_agent', models.TextField(blank=True)),
                ('security_flags', django.contrib.postgres.fields.ArrayField(
                    base_field=models.CharField(max_length=50),
                    default=list,
                    blank=True,
                    help_text='Security event flags (e.g., SECURITY_EVENT, HIGH_RISK)'
                )),
                ('retention_until', models.DateTimeField(db_index=True, help_text='Automatic deletion after this date')),
                ('actor', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    related_name='audit_actions',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='contenttypes.contenttype',
                )),
            ],
            options={
                'verbose_name': 'Audit Log',
                'verbose_name_plural': 'Audit Logs',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['correlation_id', 'created_at'], name='audit_corr_created_idx'),
                    models.Index(fields=['event_type', 'created_at'], name='audit_event_created_idx'),
                    models.Index(fields=['retention_until'], name='audit_retention_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='StateTransitionAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('from_state', models.CharField(max_length=50)),
                ('to_state', models.CharField(max_length=50)),
                ('transition_reason', models.TextField(blank=True)),
                ('transition_duration_seconds', models.IntegerField(
                    null=True,
                    blank=True,
                    help_text='Time spent in previous state (seconds)'
                )),
                ('audit_log', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='state_transition_details',
                    to='core.auditlog',
                )),
            ],
            options={
                'verbose_name': 'State Transition Audit',
                'verbose_name_plural': 'State Transition Audits',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BulkOperationAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('operation_type', models.CharField(max_length=100, help_text='Type of bulk operation (e.g., transition_to_APPROVED)')),
                ('total_items', models.IntegerField()),
                ('successful_items', models.IntegerField()),
                ('failed_items', models.IntegerField()),
                ('failure_details', models.JSONField(default=dict, help_text='Details of failed items')),
                ('execution_time_seconds', models.FloatField(null=True, blank=True)),
                ('audit_log', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bulk_operation_details',
                    to='core.auditlog',
                )),
            ],
            options={
                'verbose_name': 'Bulk Operation Audit',
                'verbose_name_plural': 'Bulk Operation Audits',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PermissionDenialAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('required_permission', models.CharField(max_length=255)),
                ('action_attempted', models.TextField()),
                ('risk_level', models.CharField(
                    max_length=20,
                    choices=[
                        ('LOW', 'Low Risk'),
                        ('MEDIUM', 'Medium Risk'),
                        ('HIGH', 'High Risk'),
                        ('CRITICAL', 'Critical Risk'),
                    ],
                    default='MEDIUM',
                )),
                ('audit_log', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='permission_denial_details',
                    to='core.auditlog',
                )),
            ],
            options={
                'verbose_name': 'Permission Denial Audit',
                'verbose_name_plural': 'Permission Denial Audits',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['risk_level', 'created_at'], name='perm_risk_created_idx'),
                ],
            },
        ),
    ]
