"""
Voice Biometric Authentication Models Migration

Adds comprehensive voice biometric authentication support:
- VoiceEmbedding: Store voiceprints for speaker recognition
- VoiceAntiSpoofingModel: Track anti-spoofing model configurations
- VoiceBiometricConfig: System-wide voice biometric settings
- Enhanced VoiceVerificationLog: Comprehensive verification tracking

IMPORTANT: This migration drops and recreates VoiceVerificationLog.
If you have existing data, back it up first.

Following .claude/rules.md Rule #7: Migration handles schema changes cleanly
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields
from django.core.serializers.json import DjangoJSONEncoder


class Migration(migrations.Migration):

    dependencies = [
        ('voice_recognition', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('attendance', '0001_initial'),  # For PeopleEventlog foreign key
    ]

    operations = [
        # Drop old VoiceVerificationLog table (WARNING: DATA LOSS)
        migrations.DeleteModel(
            name='VoiceVerificationLog',
        ),

        # Create VoiceEmbedding model
        migrations.CreateModel(
            name='VoiceEmbedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant_id', models.CharField(blank=True, max_length=100, null=True)),

                ('embedding_vector', django.contrib.postgres.fields.ArrayField(
                    base_field=models.FloatField(),
                    help_text='Voice embedding vector (voiceprint)',
                    size=512
                )),
                ('source_audio_path', models.CharField(blank=True, max_length=500, null=True)),
                ('source_audio_hash', models.CharField(blank=True, max_length=64, null=True)),
                ('extraction_model_name', models.CharField(
                    default='google-speaker-recognition',
                    help_text='Model used to extract this voiceprint',
                    max_length=100
                )),
                ('extraction_model_version', models.CharField(default='1.0', max_length=20)),

                ('voice_confidence', models.FloatField(help_text='Confidence of voice detection (0-1)')),
                ('audio_quality_score', models.FloatField(
                    blank=True,
                    help_text='Quality score of source audio (0-1)',
                    null=True
                )),
                ('snr_db', models.FloatField(
                    blank=True,
                    help_text='Signal-to-noise ratio in decibels',
                    null=True
                )),

                ('language_code', models.CharField(default='en-US', help_text='Language of voice sample', max_length=10)),
                ('sample_text', models.TextField(blank=True, help_text='Text spoken in the sample (if available)', null=True)),
                ('sample_duration_seconds', models.FloatField(
                    blank=True,
                    help_text='Duration of audio sample in seconds',
                    null=True
                )),

                ('extraction_timestamp', models.DateTimeField(auto_now_add=True)),
                ('audio_features', models.JSONField(
                    blank=True,
                    encoder=DjangoJSONEncoder,
                    help_text='Additional audio features (pitch, tempo, etc.)',
                    null=True
                )),

                ('is_primary', models.BooleanField(default=False, help_text='Whether this is the primary voiceprint for the user')),
                ('is_validated', models.BooleanField(default=False, help_text='Whether this voiceprint has been validated')),
                ('validation_score', models.FloatField(blank=True, null=True)),

                ('verification_count', models.IntegerField(default=0)),
                ('successful_matches', models.IntegerField(default=0)),
                ('last_used', models.DateTimeField(blank=True, null=True)),

                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='voice_embeddings',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Voice Embedding',
                'verbose_name_plural': 'Voice Embeddings',
                'db_table': 'voice_embedding',
            },
        ),

        # Create VoiceAntiSpoofingModel
        migrations.CreateModel(
            name='VoiceAntiSpoofingModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant_id', models.CharField(blank=True, max_length=100, null=True)),

                ('name', models.CharField(max_length=100, unique=True)),
                ('model_type', models.CharField(
                    choices=[
                        ('PLAYBACK_DETECTION', 'Playback Detection'),
                        ('DEEPFAKE_DETECTION', 'Deepfake Detection'),
                        ('CHANNEL_ANALYSIS', 'Channel Analysis'),
                        ('ACOUSTIC_FINGERPRINT', 'Acoustic Fingerprinting'),
                        ('LIVENESS_CHALLENGE', 'Challenge-Response'),
                        ('MULTI_MODAL', 'Multi-modal Detection'),
                    ],
                    max_length=30
                )),
                ('version', models.CharField(default='1.0', max_length=20)),

                ('liveness_threshold', models.FloatField(default=0.5, help_text='Threshold for liveness classification')),
                ('spoof_threshold', models.FloatField(default=0.7, help_text='Threshold for spoof detection')),

                ('true_positive_rate', models.FloatField(blank=True, null=True)),
                ('false_positive_rate', models.FloatField(blank=True, null=True)),
                ('accuracy', models.FloatField(blank=True, null=True)),

                ('model_file_path', models.CharField(blank=True, max_length=500, null=True)),
                ('requires_challenge_response', models.BooleanField(
                    default=False,
                    help_text='Whether model requires challenge-response interaction'
                )),
                ('supported_languages', django.contrib.postgres.fields.ArrayField(
                    base_field=models.CharField(max_length=10),
                    default=list,
                    help_text='Supported language codes',
                    size=None
                )),

                ('detection_count', models.BigIntegerField(default=0)),
                ('spoof_detections', models.BigIntegerField(default=0)),
                ('last_used', models.DateTimeField(blank=True, null=True)),

                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Voice Anti-Spoofing Model',
                'verbose_name_plural': 'Voice Anti-Spoofing Models',
                'db_table': 'voice_anti_spoofing_model',
            },
        ),

        # Create VoiceBiometricConfig
        migrations.CreateModel(
            name='VoiceBiometricConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant_id', models.CharField(blank=True, max_length=100, null=True)),

                ('name', models.CharField(max_length=100, unique=True)),
                ('config_type', models.CharField(
                    choices=[
                        ('SYSTEM', 'System Configuration'),
                        ('SECURITY', 'Security Settings'),
                        ('PERFORMANCE', 'Performance Settings'),
                        ('USER_PREFERENCE', 'User Preferences'),
                    ],
                    max_length=20
                )),
                ('description', models.TextField()),

                ('config_data', models.JSONField(encoder=DjangoJSONEncoder, help_text='Configuration parameters')),

                ('applies_to_locations', django.contrib.postgres.fields.ArrayField(
                    base_field=models.CharField(max_length=100),
                    blank=True,
                    default=list,
                    help_text='Location codes this configuration applies to',
                    size=None
                )),

                ('is_active', models.BooleanField(default=True)),
                ('priority', models.IntegerField(default=100, help_text='Configuration priority (lower = higher priority)')),

                ('last_validated', models.DateTimeField(blank=True, null=True)),
                ('validation_errors', models.JSONField(
                    default=list,
                    encoder=DjangoJSONEncoder,
                    help_text='Configuration validation errors'
                )),

                ('applied_count', models.IntegerField(default=0)),
                ('last_applied', models.DateTimeField(blank=True, null=True)),

                ('applies_to_users', models.ManyToManyField(
                    blank=True,
                    help_text='Users this configuration applies to (empty = all users)',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Voice Biometric Configuration',
                'verbose_name_plural': 'Voice Biometric Configurations',
                'db_table': 'voice_biometric_config',
                'ordering': ['priority', 'name'],
            },
        ),

        # Create new enhanced VoiceVerificationLog
        migrations.CreateModel(
            name='VoiceVerificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant_id', models.CharField(blank=True, max_length=100, null=True)),

                ('verification_timestamp', models.DateTimeField(auto_now_add=True)),
                ('result', models.CharField(
                    choices=[
                        ('SUCCESS', 'Verification Successful'),
                        ('FAILED', 'Verification Failed'),
                        ('ERROR', 'Verification Error'),
                        ('REJECTED', 'Rejected by Anti-spoofing'),
                        ('NO_VOICE', 'No Voice Detected'),
                        ('POOR_QUALITY', 'Poor Audio Quality'),
                    ],
                    max_length=20
                )),

                ('similarity_score', models.FloatField(blank=True, help_text='Voice similarity score (0-1)', null=True)),
                ('confidence_score', models.FloatField(blank=True, help_text='Overall confidence in verification (0-1)', null=True)),

                ('liveness_score', models.FloatField(blank=True, help_text='Liveness detection score (0-1)', null=True)),
                ('spoof_detected', models.BooleanField(default=False)),
                ('spoof_type', models.CharField(
                    blank=True,
                    help_text='Type of spoofing detected (e.g., PLAYBACK, DEEPFAKE)',
                    max_length=50,
                    null=True
                )),

                ('input_audio_path', models.CharField(blank=True, max_length=500, null=True)),
                ('input_audio_hash', models.CharField(blank=True, max_length=64, null=True)),
                ('audio_quality_score', models.FloatField(blank=True, null=True)),
                ('audio_duration_seconds', models.FloatField(blank=True, null=True)),
                ('snr_db', models.FloatField(blank=True, help_text='Signal-to-noise ratio', null=True)),

                ('challenge_phrase', models.CharField(
                    blank=True,
                    help_text='Challenge phrase used for liveness detection',
                    max_length=200,
                    null=True
                )),
                ('challenge_matched', models.BooleanField(
                    default=False,
                    help_text='Whether spoken phrase matched challenge'
                )),

                ('processing_time_ms', models.FloatField(blank=True, null=True)),

                ('error_message', models.TextField(blank=True, null=True)),
                ('error_code', models.CharField(blank=True, max_length=50, null=True)),

                ('verification_metadata', models.JSONField(
                    default=dict,
                    encoder=DjangoJSONEncoder,
                    help_text='Detailed verification metadata'
                )),

                ('fraud_indicators', django.contrib.postgres.fields.ArrayField(
                    base_field=models.CharField(max_length=50),
                    blank=True,
                    default=list,
                    help_text='Detected fraud indicators',
                    size=None
                )),
                ('fraud_risk_score', models.FloatField(default=0.0, help_text='Calculated fraud risk score (0-1)')),

                ('device_id', models.CharField(blank=True, max_length=100, null=True)),
                ('device_info', models.JSONField(default=dict, encoder=DjangoJSONEncoder, help_text='Device information')),

                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('attendance_record', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='attendance.peopleeventlog'
                )),
                ('matched_embedding', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='voice_recognition.voiceembedding'
                )),
            ],
            options={
                'verbose_name': 'Voice Verification Log',
                'verbose_name_plural': 'Voice Verification Logs',
                'db_table': 'voice_verification_log',
            },
        ),

        # Add indexes for VoiceEmbedding
        migrations.AddIndex(
            model_name='voiceembedding',
            index=models.Index(fields=['user', 'is_primary'], name='voice_emb_user_primary_idx'),
        ),
        migrations.AddIndex(
            model_name='voiceembedding',
            index=models.Index(fields=['extraction_model_name', 'is_validated'], name='voice_emb_model_validated_idx'),
        ),
        migrations.AddIndex(
            model_name='voiceembedding',
            index=models.Index(fields=['language_code', 'is_validated'], name='voice_emb_lang_validated_idx'),
        ),

        # Add indexes for VoiceVerificationLog
        migrations.AddIndex(
            model_name='voiceverificationlog',
            index=models.Index(fields=['user', 'verification_timestamp'], name='voice_ver_user_time_idx'),
        ),
        migrations.AddIndex(
            model_name='voiceverificationlog',
            index=models.Index(fields=['result', 'verification_timestamp'], name='voice_ver_result_time_idx'),
        ),
        migrations.AddIndex(
            model_name='voiceverificationlog',
            index=models.Index(fields=['fraud_risk_score', 'spoof_detected'], name='voice_ver_fraud_idx'),
        ),
        migrations.AddIndex(
            model_name='voiceverificationlog',
            index=models.Index(fields=['device_id', 'verification_timestamp'], name='voice_ver_device_time_idx'),
        ),
    ]