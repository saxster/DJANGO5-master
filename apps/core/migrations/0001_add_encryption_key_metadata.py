# Generated migration for EncryptionKeyMetadata model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '__latest__'),  # Replace with actual latest migration
    ]

    operations = [
        migrations.CreateModel(
            name='EncryptionKeyMetadata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key_id', models.CharField(db_index=True, help_text='Unique identifier for the encryption key', max_length=255, unique=True)),
                ('is_active', models.BooleanField(db_index=True, default=False, help_text='Whether this key is currently active for encryption/decryption')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, help_text='When the key was created')),
                ('activated_at', models.DateTimeField(blank=True, help_text='When the key was activated for use', null=True)),
                ('expires_at', models.DateTimeField(help_text='When the key should expire and be rotated')),
                ('rotated_at', models.DateTimeField(blank=True, help_text='When the key was rotated out', null=True)),
                ('rotation_status', models.CharField(choices=[('created', 'Created - Not Yet Active'), ('active', 'Active - Current Key'), ('rotating', 'Rotating - Migration In Progress'), ('retired', 'Retired - No Longer Used'), ('expired', 'Expired - Past Expiration Date')], db_index=True, default='created', help_text='Current status of the key in rotation lifecycle', max_length=50)),
                ('replaced_by_key_id', models.CharField(blank=True, help_text='Key ID that replaced this key during rotation', max_length=255, null=True)),
                ('rotation_notes', models.TextField(blank=True, help_text='Notes about key rotation process')),
                ('data_encrypted_count', models.BigIntegerField(default=0, help_text='Approximate count of records encrypted with this key')),
                ('last_used_at', models.DateTimeField(blank=True, help_text='Last time this key was used for encryption/decryption', null=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this key', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_encryption_keys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Encryption Key Metadata',
                'verbose_name_plural': 'Encryption Key Metadata',
                'db_table': 'encryption_key_metadata',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='encryptionkeymetadata',
            index=models.Index(fields=['key_id'], name='encryption_key_id_idx'),
        ),
        migrations.AddIndex(
            model_name='encryptionkeymetadata',
            index=models.Index(fields=['is_active', 'expires_at'], name='encryption_active_expires_idx'),
        ),
        migrations.AddIndex(
            model_name='encryptionkeymetadata',
            index=models.Index(fields=['rotation_status'], name='encryption_rotation_status_idx'),
        ),
        migrations.AddIndex(
            model_name='encryptionkeymetadata',
            index=models.Index(fields=['created_at'], name='encryption_created_at_idx'),
        ),
    ]