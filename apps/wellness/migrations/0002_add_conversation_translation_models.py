# Generated migration for wisdom conversation translation models

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('peoples', '0004_add_preferred_language'),
        ('wellness', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WisdomConversationTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('target_language', models.CharField(
                    choices=[
                        ('hi', 'हिन्दी (Hindi)'),
                        ('te', 'తెలుగు (Telugu)'),
                        ('es', 'Español (Spanish)'),
                        ('fr', 'Français (French)'),
                        ('ar', 'العربية (Arabic)'),
                        ('zh', '中文 (Chinese)'),
                    ],
                    help_text="Language code for the translation",
                    max_length=10,
                    verbose_name='Target Language'
                )),
                ('translated_text', models.TextField(
                    help_text="Full translated conversation text",
                    verbose_name='Translated Text'
                )),
                ('warning_message', models.CharField(
                    help_text="Localized warning message about translation quality",
                    max_length=500,
                    verbose_name='Translation Warning'
                )),
                ('translation_backend', models.CharField(
                    choices=[
                        ('google', 'Google Translate'),
                        ('azure', 'Azure Translator'),
                        ('openai', 'OpenAI GPT Translation'),
                        ('manual', 'Manual Translation'),
                        ('hybrid', 'Hybrid (Multiple Backends)'),
                    ],
                    default='google',
                    help_text="Service used for translation",
                    max_length=20,
                    verbose_name='Translation Backend'
                )),
                ('quality_level', models.CharField(
                    choices=[
                        ('unverified', 'Unverified (Auto-translated)'),
                        ('reviewed', 'Reviewed by Human'),
                        ('professional', 'Professional Translation'),
                        ('native', 'Native Speaker Verified'),
                    ],
                    default='unverified',
                    help_text="Translation quality assessment",
                    max_length=20,
                    verbose_name='Quality Level'
                )),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Translation Pending'),
                        ('processing', 'Translation in Progress'),
                        ('completed', 'Translation Completed'),
                        ('failed', 'Translation Failed'),
                        ('expired', 'Translation Cache Expired'),
                    ],
                    default='pending',
                    help_text="Current processing status",
                    max_length=20,
                    verbose_name='Translation Status'
                )),
                ('confidence_score', models.FloatField(
                    blank=True,
                    help_text="AI confidence in translation quality (0.0-1.0)",
                    null=True,
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0)
                    ],
                    verbose_name='Confidence Score'
                )),
                ('word_count_original', models.PositiveIntegerField(
                    blank=True,
                    help_text="Number of words in original text",
                    null=True,
                    verbose_name='Original Word Count'
                )),
                ('word_count_translated', models.PositiveIntegerField(
                    blank=True,
                    help_text="Number of words in translated text",
                    null=True,
                    verbose_name='Translated Word Count'
                )),
                ('translation_time_ms', models.PositiveIntegerField(
                    blank=True,
                    help_text="Time taken for translation in milliseconds",
                    null=True,
                    verbose_name='Translation Time (ms)'
                )),
                ('cache_hit_count', models.PositiveIntegerField(
                    default=0,
                    help_text="Number of times this translation was served from cache",
                    verbose_name='Cache Hit Count'
                )),
                ('last_accessed', models.DateTimeField(
                    blank=True,
                    help_text="When this translation was last retrieved",
                    null=True,
                    verbose_name='Last Accessed'
                )),
                ('source_content_hash', models.CharField(
                    help_text="SHA-256 hash of original content for version tracking",
                    max_length=64,
                    verbose_name='Source Content Hash'
                )),
                ('translation_version', models.CharField(
                    default='1.0',
                    help_text="Version number for translation revisions",
                    max_length=20,
                    verbose_name='Translation Version'
                )),
                ('expires_at', models.DateTimeField(
                    blank=True,
                    help_text="When this translation cache should expire",
                    null=True,
                    verbose_name='Expires At'
                )),
                ('review_notes', models.TextField(
                    blank=True,
                    help_text="Notes from human reviewers about translation quality",
                    verbose_name='Review Notes'
                )),
                ('error_message', models.TextField(
                    blank=True,
                    help_text="Error details if translation failed",
                    verbose_name='Error Message'
                )),
                ('retry_count', models.PositiveSmallIntegerField(
                    default=0,
                    help_text="Number of translation retry attempts",
                    verbose_name='Retry Count'
                )),
                ('original_conversation', models.ForeignKey(
                    help_text="Original English conversation being translated",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='translations',
                    to='wellness.wisdomconversation'
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    help_text="Person who reviewed this translation",
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_translations',
                    to='peoples.people'
                )),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
            ],
            options={
                'verbose_name': 'Wisdom Conversation Translation',
                'verbose_name_plural': 'Wisdom Conversation Translations',
                'db_table': 'wellness_conversation_translation',
                'ordering': ['-quality_level', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TranslationQualityFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('feedback_type', models.CharField(
                    choices=[
                        ('rating', 'Quality Rating'),
                        ('correction', 'Text Correction'),
                        ('complaint', 'Quality Complaint'),
                        ('compliment', 'Quality Compliment'),
                    ],
                    help_text="Type of feedback provided",
                    max_length=20,
                    verbose_name='Feedback Type'
                )),
                ('quality_rating', models.PositiveSmallIntegerField(
                    blank=True,
                    choices=[
                        (1, 'Very Poor - Incomprehensible'),
                        (2, 'Poor - Many Errors'),
                        (3, 'Fair - Some Errors'),
                        (4, 'Good - Minor Issues'),
                        (5, 'Excellent - Perfect Translation'),
                    ],
                    help_text="1-5 star rating of translation quality",
                    null=True,
                    verbose_name='Quality Rating'
                )),
                ('feedback_text', models.TextField(
                    blank=True,
                    help_text="Detailed feedback or suggested corrections",
                    verbose_name='Feedback Text'
                )),
                ('suggested_translation', models.TextField(
                    blank=True,
                    help_text="User's suggested improved translation",
                    verbose_name='Suggested Translation'
                )),
                ('is_helpful', models.BooleanField(
                    default=False,
                    help_text="Whether feedback was marked as helpful by administrators",
                    verbose_name='Marked as Helpful'
                )),
                ('admin_response', models.TextField(
                    blank=True,
                    help_text="Administrator response to feedback",
                    verbose_name='Admin Response'
                )),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
                ('translation', models.ForeignKey(
                    help_text="Translation being rated",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='quality_feedback',
                    to='wellness.wisdomconversationtranslation'
                )),
                ('user', models.ForeignKey(
                    help_text="User providing feedback",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='translation_feedback',
                    to='peoples.people'
                )),
            ],
            options={
                'verbose_name': 'Translation Quality Feedback',
                'verbose_name_plural': 'Translation Quality Feedback',
                'db_table': 'wellness_translation_feedback',
            },
        ),

        # Add unique constraints
        migrations.AlterUniqueTogether(
            name='wisdomconversationtranslation',
            unique_together={('original_conversation', 'target_language', 'translation_version')},
        ),
        migrations.AlterUniqueTogether(
            name='translationqualityfeedback',
            unique_together={('translation', 'user')},
        ),

        # Add performance indexes
        migrations.AddIndex(
            model_name='wisdomconversationtranslation',
            index=models.Index(
                fields=['original_conversation', 'target_language'],
                name='wellness_conv_trans_lookup_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='wisdomconversationtranslation',
            index=models.Index(
                fields=['status', 'quality_level'],
                name='wellness_conv_trans_status_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='wisdomconversationtranslation',
            index=models.Index(
                fields=['last_accessed', 'expires_at'],
                name='wellness_conv_trans_cache_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='wisdomconversationtranslation',
            index=models.Index(
                fields=['translation_backend', 'created_at'],
                name='wellness_conv_trans_perf_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='translationqualityfeedback',
            index=models.Index(
                fields=['quality_rating', 'created_at'],
                name='wellness_trans_feedback_rating_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='translationqualityfeedback',
            index=models.Index(
                fields=['feedback_type', 'is_helpful'],
                name='wellness_trans_feedback_type_idx'
            ),
        ),
    ]