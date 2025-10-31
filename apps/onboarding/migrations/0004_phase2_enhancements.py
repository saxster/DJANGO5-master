# Generated manually for Conversational Onboarding Phase 2 Enhancements

import uuid
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0003_add_conversational_onboarding_models'),
    ]

    operations = [
        # Add Phase 2 fields to LLMRecommendation
        migrations.AddField(
            model_name='llmrecommendation',
            name='status',
            field=models.CharField(
                choices=[
                    ('queued', 'Queued'),
                    ('processing', 'Processing'),
                    ('validated', 'Validated'),
                    ('needs_review', 'Needs Review'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed')
                ],
                default='queued',
                help_text='Current processing status of the recommendation',
                max_length=20,
                verbose_name='Status'
            ),
        ),
        migrations.AddField(
            model_name='llmrecommendation',
            name='latency_ms',
            field=models.IntegerField(
                blank=True,
                help_text='Total processing time in milliseconds',
                null=True,
                verbose_name='Latency (ms)'
            ),
        ),
        migrations.AddField(
            model_name='llmrecommendation',
            name='provider_cost_cents',
            field=models.IntegerField(
                blank=True,
                help_text='Cost of LLM provider calls in cents',
                null=True,
                verbose_name='Provider Cost (cents)'
            ),
        ),
        migrations.AddField(
            model_name='llmrecommendation',
            name='eval_scores',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Quality evaluation scores and metrics',
                verbose_name='Evaluation Scores'
            ),
        ),
        migrations.AddField(
            model_name='llmrecommendation',
            name='trace_id',
            field=models.CharField(
                blank=True,
                help_text='Distributed tracing ID for request correlation',
                max_length=50,
                verbose_name='Trace ID'
            ),
        ),

        # Create AuthoritativeKnowledgeChunk model (UUID primary key - no auto id field)
        migrations.CreateModel(
            name='AuthoritativeKnowledgeChunk',
            fields=[
                ('chunk_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified Date')),
                ('cdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Created By')),
                ('mdby', models.CharField(blank=True, max_length=100, null=True, verbose_name='Modified By')),
                ('chunk_index', models.IntegerField(help_text='Sequential chunk number within the document', verbose_name='Chunk Index')),
                ('content_text', models.TextField(help_text='Text content of this chunk', verbose_name='Content Text')),
                ('content_vector', django.contrib.postgres.fields.ArrayField(
                    base_field=models.FloatField(),
                    blank=True,
                    help_text='Vector embedding of the chunk content',
                    null=True,
                    size=None,
                    verbose_name='Content Vector'
                )),
                ('tags', models.JSONField(blank=True, default=dict, help_text='Metadata tags for filtering and categorization', verbose_name='Tags')),
                ('last_verified', models.DateTimeField(auto_now=True, help_text='When this chunk was last verified for accuracy', verbose_name='Last Verified')),
                ('is_current', models.BooleanField(default=True, help_text='Whether this chunk is still current and valid', verbose_name='Is Current')),
                ('authority_level', models.CharField(blank=True, help_text='Cached authority level from parent knowledge', max_length=20, verbose_name='Authority Level')),
                ('source_organization', models.CharField(blank=True, help_text='Cached source organization from parent knowledge', max_length=200, verbose_name='Source Organization')),
                ('knowledge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='onboarding.authoritativeknowledge', verbose_name='Knowledge Document')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_objects', to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Knowledge Chunk',
                'verbose_name_plural': 'Knowledge Chunks',
                'db_table': 'authoritative_knowledge_chunk',
                'get_latest_by': ['last_verified', 'mdtz'],
            },
        ),

        # Add indexes for LLMRecommendation
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS llm_rec_session_status_idx ON llm_recommendation (session_id, status);",
            reverse_sql="DROP INDEX IF EXISTS llm_rec_session_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS llm_rec_confidence_idx ON llm_recommendation (confidence_score);",
            reverse_sql="DROP INDEX IF EXISTS llm_rec_confidence_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS llm_rec_trace_id_idx ON llm_recommendation (trace_id);",
            reverse_sql="DROP INDEX IF EXISTS llm_rec_trace_id_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS llm_rec_status_created_idx ON llm_recommendation (status, cdtz);",
            reverse_sql="DROP INDEX IF EXISTS llm_rec_status_created_idx;"
        ),

        # Add indexes for AuthoritativeKnowledgeChunk
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS knowledge_chunk_idx ON authoritative_knowledge_chunk (knowledge_id, chunk_index);",
            reverse_sql="DROP INDEX IF EXISTS knowledge_chunk_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS chunk_current_idx ON authoritative_knowledge_chunk (is_current);",
            reverse_sql="DROP INDEX IF EXISTS chunk_current_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS chunk_authority_idx ON authoritative_knowledge_chunk (authority_level);",
            reverse_sql="DROP INDEX IF EXISTS chunk_authority_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS chunk_source_idx ON authoritative_knowledge_chunk (source_organization);",
            reverse_sql="DROP INDEX IF EXISTS chunk_source_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS chunk_current_auth_idx ON authoritative_knowledge_chunk (is_current, authority_level);",
            reverse_sql="DROP INDEX IF EXISTS chunk_current_auth_idx;"
        ),

        # Add unique constraint for knowledge chunks
        migrations.AddConstraint(
            model_name='authoritativeknowledgechunk',
            constraint=models.UniqueConstraint(
                fields=['knowledge', 'chunk_index'],
                name='knowledge_chunk_unique'
            ),
        ),
    ]