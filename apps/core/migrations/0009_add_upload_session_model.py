"""
Migration to add UploadSession model for resumable file uploads.

Sprint 3 implementation: Chunked upload system for large files
with poor network resilience.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0008_add_sync_idempotency_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='UploadSession',
            fields=[
                ('upload_id', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    help_text='Unique identifier for this upload session',
                    primary_key=True,
                    serialize=False
                )),
                ('filename', models.CharField(
                    help_text='Original filename (sanitized)',
                    max_length=255
                )),
                ('total_size', models.BigIntegerField(
                    help_text='Total file size in bytes'
                )),
                ('chunk_size', models.IntegerField(
                    default=1048576,
                    help_text='Size of each chunk in bytes (default 1MB)'
                )),
                ('mime_type', models.CharField(
                    help_text='MIME type of the file',
                    max_length=100
                )),
                ('chunks_received', models.JSONField(
                    default=list,
                    help_text='List of chunk indices received (e.g., [0,1,2,5,7])'
                )),
                ('total_chunks', models.IntegerField(
                    help_text='Total number of chunks expected'
                )),
                ('file_hash', models.CharField(
                    help_text='SHA-256 hash for final file validation',
                    max_length=64
                )),
                ('temp_directory', models.CharField(
                    help_text='Temporary directory path for storing chunks',
                    max_length=500
                )),
                ('status', models.CharField(
                    choices=[
                        ('active', 'Active - Accepting Chunks'),
                        ('assembling', 'Assembling - Merging Chunks'),
                        ('completed', 'Completed Successfully'),
                        ('failed', 'Failed - Error Occurred'),
                        ('cancelled', 'Cancelled by User'),
                        ('expired', 'Expired - TTL Exceeded')
                    ],
                    db_index=True,
                    default='active',
                    help_text='Current status of the upload session',
                    max_length=20
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='When the upload session was created'
                )),
                ('expires_at', models.DateTimeField(
                    db_index=True,
                    help_text='When this session expires (24-hour TTL)'
                )),
                ('completed_at', models.DateTimeField(
                    blank=True,
                    help_text='When the upload was completed',
                    null=True
                )),
                ('last_activity_at', models.DateTimeField(
                    auto_now=True,
                    help_text='Last time a chunk was received'
                )),
                ('error_message', models.TextField(
                    blank=True,
                    help_text='Error message if upload failed'
                )),
                ('final_file_path', models.CharField(
                    blank=True,
                    help_text='Path to final assembled file',
                    max_length=500
                )),
                ('user', models.ForeignKey(
                    help_text='User who initiated this upload',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='upload_sessions',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'upload_sessions',
                'verbose_name': 'Upload Session',
                'verbose_name_plural': 'Upload Sessions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='uploadsession',
            index=models.Index(fields=['user', 'status'], name='upload_sess_user_id_status_idx'),
        ),
        migrations.AddIndex(
            model_name='uploadsession',
            index=models.Index(fields=['status', 'expires_at'], name='upload_sess_status_expires_idx'),
        ),
        migrations.AddIndex(
            model_name='uploadsession',
            index=models.Index(fields=['created_at'], name='upload_sess_created_idx'),
        ),
    ]