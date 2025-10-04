"""
Initial migration for voice_recognition app

Creates VoiceVerificationLog model for mobile sync audit logging.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='VoiceVerificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('verification_id', models.CharField(
                    db_index=True,
                    help_text='Unique identifier for this verification attempt',
                    max_length=100,
                    unique=True
                )),
                ('user_id', models.CharField(
                    db_index=True,
                    help_text='User ID performing voice verification',
                    max_length=100
                )),
                ('device_id', models.CharField(
                    blank=True,
                    help_text='Device identifier for tracking',
                    max_length=100,
                    null=True
                )),
                ('verified', models.BooleanField(
                    default=False,
                    help_text='Whether voice verification succeeded'
                )),
                ('confidence_score', models.FloatField(
                    blank=True,
                    help_text='ML model confidence score (0.0-1.0)',
                    null=True
                )),
                ('quality_score', models.FloatField(
                    blank=True,
                    help_text='Audio quality score (0.0-1.0)',
                    null=True
                )),
                ('processing_time_ms', models.IntegerField(
                    blank=True,
                    help_text='Processing time in milliseconds',
                    null=True
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='Timestamp of verification attempt'
                )),
            ],
            options={
                'verbose_name': 'Voice Verification Log',
                'verbose_name_plural': 'Voice Verification Logs',
                'db_table': 'voice_verification_log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='voiceverificationlog',
            index=models.Index(fields=['user_id', 'created_at'], name='voice_ver_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='voiceverificationlog',
            index=models.Index(fields=['device_id', 'created_at'], name='voice_ver_device_created_idx'),
        ),
        migrations.AddIndex(
            model_name='voiceverificationlog',
            index=models.Index(fields=['verified', 'created_at'], name='voice_ver_status_created_idx'),
        ),
    ]