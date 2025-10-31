"""
Migration for File Upload Audit Log model.

Adds comprehensive audit logging for file upload security events.
Supports compliance reporting and forensic analysis.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_add_audit_models'),
        ('core', '0002_add_rate_limiting_models'),
        ('core', '0003_delete_ratelimitattempt_remove_apikey_rate_limit'),
        ('peoples', '0003_add_performance_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='FileUploadAuditLog',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('correlation_id', models.UUIDField(db_index=True)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('event_type', models.CharField(
                    choices=[
                        ('UPLOAD_ATTEMPT', 'Upload Attempt'),
                        ('UPLOAD_SUCCESS', 'Upload Successful'),
                        ('UPLOAD_FAILED', 'Upload Failed'),
                        ('VALIDATION_FAILED', 'Validation Failed'),
                        ('PATH_TRAVERSAL_BLOCKED', 'Path Traversal Blocked'),
                        ('MALWARE_DETECTED', 'Malware Detected'),
                        ('QUARANTINED', 'File Quarantined'),
                        ('FILE_DELETED', 'File Deleted'),
                    ],
                    db_index=True,
                    max_length=50
                )),
                ('severity', models.CharField(
                    choices=[
                        ('INFO', 'Information'),
                        ('WARNING', 'Warning'),
                        ('ERROR', 'Error'),
                        ('CRITICAL', 'Critical'),
                    ],
                    db_index=True,
                    max_length=20
                )),
                ('ip_address', models.GenericIPAddressField(null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('filename', models.CharField(db_index=True, max_length=255)),
                ('original_filename', models.CharField(max_length=255)),
                ('file_size', models.BigIntegerField(null=True)),
                ('file_type', models.CharField(max_length=50)),
                ('mime_type', models.CharField(blank=True, max_length=100)),
                ('file_path', models.TextField(blank=True)),
                ('upload_context', models.JSONField(default=dict)),
                ('validation_results', models.JSONField(default=dict)),
                ('security_analysis', models.JSONField(default=dict)),
                ('malware_scan_results', models.JSONField(default=dict)),
                ('error_message', models.TextField(blank=True)),
                ('additional_metadata', models.JSONField(default=dict)),
                ('user', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='peoples.people'
                )),
            ],
            options={
                'db_table': 'file_upload_audit_log',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='fileuploadauditlog',
            index=models.Index(
                fields=['-timestamp', 'event_type'],
                name='file_upload_timestamp_event_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='fileuploadauditlog',
            index=models.Index(
                fields=['user', '-timestamp'],
                name='file_upload_user_timestamp_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='fileuploadauditlog',
            index=models.Index(
                fields=['severity', '-timestamp'],
                name='file_upload_severity_timestamp_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='fileuploadauditlog',
            index=models.Index(
                fields=['correlation_id'],
                name='file_upload_correlation_idx'
            ),
        ),
    ]