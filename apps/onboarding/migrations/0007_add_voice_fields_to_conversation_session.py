# Generated migration for voice fields in ConversationSession

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0006_add_ai_changeset_rollback_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversationsession',
            name='voice_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Whether this session uses voice input/output',
                verbose_name='Voice Enabled'
            ),
        ),
        migrations.AddField(
            model_name='conversationsession',
            name='preferred_voice_language',
            field=models.CharField(
                blank=True,
                default='en-US',
                help_text="Language code for speech recognition (e.g., 'en-US', 'hi-IN')",
                max_length=10,
                verbose_name='Preferred Voice Language'
            ),
        ),
        migrations.AddField(
            model_name='conversationsession',
            name='audio_transcripts',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Array of {timestamp, transcript, confidence, duration_seconds, language} objects',
                verbose_name='Audio Transcripts'
            ),
        ),
        migrations.AddField(
            model_name='conversationsession',
            name='voice_interaction_count',
            field=models.IntegerField(
                default=0,
                help_text='Number of voice interactions in this session',
                verbose_name='Voice Interaction Count'
            ),
        ),
        migrations.AddField(
            model_name='conversationsession',
            name='total_audio_duration_seconds',
            field=models.IntegerField(
                default=0,
                help_text='Total audio processed in seconds',
                verbose_name='Total Audio Duration'
            ),
        ),
    ]