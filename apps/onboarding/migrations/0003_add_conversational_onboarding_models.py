# Generated manually for Conversational Onboarding Phase 1 MVP

import uuid
from django.conf import settings
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add new fields to existing Bt model
        migrations.AddField(
            model_name='bt',
            name='onboarding_context',
            field=models.JSONField(blank=True, default=dict, help_text='Context data for conversational onboarding process', verbose_name='Onboarding Context'),
        ),
        migrations.AddField(
            model_name='bt',
            name='setup_confidence_score',
            field=models.FloatField(blank=True, help_text='AI confidence score for the setup recommendations', null=True, verbose_name='Setup Confidence Score'),
        ),

        # Create ConversationSession model
        migrations.CreateModel(
            name='ConversationSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified Date')),
                ('cdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Created By')),
                ('mdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Modified By')),
                ('session_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('language', models.CharField(default='en', help_text='ISO language code for the conversation', max_length=10, verbose_name='Language')),
                ('conversation_type', models.CharField(choices=[('initial_setup', 'Initial Setup'), ('config_update', 'Configuration Update'), ('troubleshooting', 'Troubleshooting'), ('feature_request', 'Feature Request')], default='initial_setup', max_length=50, verbose_name='Conversation Type')),
                ('context_data', models.JSONField(blank=True, default=dict, help_text='Initial context and environment data', verbose_name='Context Data')),
                ('current_state', models.CharField(choices=[('started', 'Started'), ('in_progress', 'In Progress'), ('generating', 'Generating Recommendations'), ('awaiting_approval', 'Awaiting User Approval'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('error', 'Error')], default='started', max_length=50, verbose_name='Current State')),
                ('collected_data', models.JSONField(blank=True, default=dict, help_text='Data collected during the conversation', verbose_name='Collected Data')),
                ('error_message', models.TextField(blank=True, help_text='Error details if session failed', null=True, verbose_name='Error Message')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_sessions', to='onboarding.bt', verbose_name='Client')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_sessions', to=settings.AUTH_USER_MODEL, verbose_name='User')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_objects', to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Conversation Session',
                'verbose_name_plural': 'Conversation Sessions',
                'db_table': 'conversation_session',
                'get_latest_by': ['mdtz', 'cdtz'],
            },
        ),

        # Create LLMRecommendation model
        migrations.CreateModel(
            name='LLMRecommendation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified Date')),
                ('cdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Created By')),
                ('mdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Modified By')),
                ('recommendation_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('maker_output', models.JSONField(help_text='Raw output from the maker LLM', verbose_name='Maker Output')),
                ('checker_output', models.JSONField(blank=True, help_text='Validation output from checker LLM', null=True, verbose_name='Checker Output')),
                ('consensus', models.JSONField(blank=True, default=dict, help_text='Final consensus between maker and checker', verbose_name='Consensus')),
                ('authoritative_sources', models.JSONField(blank=True, default=list, help_text='References to authoritative knowledge sources', verbose_name='Authoritative Sources')),
                ('confidence_score', models.FloatField(help_text='Overall confidence score (0.0 to 1.0)', verbose_name='Confidence Score')),
                ('user_decision', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('modified', 'Modified')], default='pending', max_length=20, verbose_name='User Decision')),
                ('rejection_reason', models.TextField(blank=True, help_text='Why the user rejected the recommendation', null=True, verbose_name='Rejection Reason')),
                ('modifications', models.JSONField(blank=True, default=dict, help_text='User modifications to the recommendation', verbose_name='Modifications')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recommendations', to='onboarding.conversationsession', verbose_name='Session')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_objects', to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'LLM Recommendation',
                'verbose_name_plural': 'LLM Recommendations',
                'db_table': 'llm_recommendation',
                'get_latest_by': ['mdtz', 'cdtz'],
            },
        ),

        # Create AuthoritativeKnowledge model
        migrations.CreateModel(
            name='AuthoritativeKnowledge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified Date')),
                ('cdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Created By')),
                ('mdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Modified By')),
                ('knowledge_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('source_organization', models.CharField(help_text='Organization that published this knowledge', max_length=200, verbose_name='Source Organization')),
                ('document_title', models.CharField(help_text='Title of the source document', max_length=500, verbose_name='Document Title')),
                ('document_version', models.CharField(blank=True, help_text='Version of the document', max_length=50, verbose_name='Document Version')),
                ('authority_level', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('official', 'Official')], default='medium', max_length=20, verbose_name='Authority Level')),
                ('content_vector', django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), blank=True, help_text='Vector embedding of the content', null=True, size=None, verbose_name='Content Vector')),
                ('content_summary', models.TextField(help_text='Summary of the knowledge content', verbose_name='Content Summary')),
                ('publication_date', models.DateTimeField(help_text='When this knowledge was published', verbose_name='Publication Date')),
                ('last_verified', models.DateTimeField(auto_now=True, help_text='When this knowledge was last verified', verbose_name='Last Verified')),
                ('is_current', models.BooleanField(default=True, help_text='Whether this knowledge is still current', verbose_name='Is Current')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_objects', to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Authoritative Knowledge',
                'verbose_name_plural': 'Authoritative Knowledge',
                'db_table': 'authoritative_knowledge',
                'get_latest_by': ['publication_date', 'mdtz'],
            },
        ),

        # Create UserFeedbackLearning model
        migrations.CreateModel(
            name='UserFeedbackLearning',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified Date')),
                ('cdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Created By')),
                ('mdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Modified By')),
                ('feedback_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('feedback_type', models.CharField(choices=[('rec_quality', 'Recommendation Quality'), ('conv_flow', 'Conversation Flow'), ('accuracy', 'Accuracy'), ('completeness', 'Completeness'), ('usability', 'Usability'), ('other', 'Other')], max_length=50, verbose_name='Feedback Type')),
                ('feedback_data', models.JSONField(help_text='Structured feedback data', verbose_name='Feedback Data')),
                ('learning_extracted', models.JSONField(blank=True, default=dict, help_text='Learning patterns extracted from this feedback', verbose_name='Learning Extracted')),
                ('applied_to_model', models.BooleanField(default=False, help_text='Whether this feedback has been applied to improve the model', verbose_name='Applied to Model')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedback_received', to='onboarding.bt', verbose_name='Client')),
                ('recommendation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedback', to='onboarding.llmrecommendation', verbose_name='Recommendation')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedback_given', to=settings.AUTH_USER_MODEL, verbose_name='User')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_objects', to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'User Feedback Learning',
                'verbose_name_plural': 'User Feedback Learning',
                'db_table': 'user_feedback_learning',
                'get_latest_by': ['mdtz', 'cdtz'],
            },
        ),
    ]