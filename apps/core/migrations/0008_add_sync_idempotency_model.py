"""
Add SyncIdempotencyRecord model for mobile sync deduplication

Enables batch and item-level idempotency for mobile sync operations.
Prevents duplicates when clients retry sync requests.

Following .claude/rules.md patterns for mobile sync infrastructure.
"""

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_add_monitoring_api_key_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyncIdempotencyRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('idempotency_key', models.CharField(
                    db_index=True,
                    help_text='SHA256 hash of request for idempotency',
                    max_length=64,
                    unique=True
                )),
                ('scope', models.CharField(
                    choices=[('batch', 'Batch Level'), ('item', 'Item Level')],
                    default='batch',
                    help_text='Scope of idempotency (batch or item)',
                    max_length=10
                )),
                ('request_hash', models.CharField(
                    help_text='Hash of full request payload for verification',
                    max_length=64
                )),
                ('response_data', models.JSONField(
                    help_text='Cached response to return on duplicate request'
                )),
                ('user_id', models.CharField(
                    blank=True,
                    help_text='User who initiated the sync operation',
                    max_length=100,
                    null=True
                )),
                ('device_id', models.CharField(
                    blank=True,
                    help_text='Device identifier for tracking',
                    max_length=100,
                    null=True
                )),
                ('endpoint', models.CharField(
                    help_text='Sync endpoint that was called',
                    max_length=255
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    help_text='When this idempotency record was created'
                )),
                ('expires_at', models.DateTimeField(
                    db_index=True,
                    help_text='When this record expires (24-hour TTL)'
                )),
                ('hit_count', models.IntegerField(
                    default=0,
                    help_text='Number of times this idempotency key was used'
                )),
                ('last_hit_at', models.DateTimeField(
                    blank=True,
                    help_text='Last time this key was used',
                    null=True
                )),
            ],
            options={
                'verbose_name': 'Sync Idempotency Record',
                'verbose_name_plural': 'Sync Idempotency Records',
                'db_table': 'sync_idempotency_record',
            },
        ),
        migrations.AddIndex(
            model_name='syncidempotencyrecord',
            index=models.Index(fields=['user_id', 'created_at'], name='sync_idemp_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='syncidempotencyrecord',
            index=models.Index(fields=['device_id', 'created_at'], name='sync_idemp_device_created_idx'),
        ),
        migrations.AddIndex(
            model_name='syncidempotencyrecord',
            index=models.Index(fields=['expires_at'], name='sync_idemp_expires_idx'),
        ),
    ]