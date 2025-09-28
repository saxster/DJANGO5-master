# Generated migration for personalization models

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0004_phase2_enhancements'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add PreferenceProfile model
        migrations.CreateModel(
            name='PreferenceProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified')),
                ('profile_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('preference_vector', django.contrib.postgres.fields.ArrayField(
                    base_field=models.FloatField(), blank=True, help_text='Vector embedding of user preferences',
                    null=True, size=128, verbose_name='Preference Vector'
                )),
                ('weights', models.JSONField(
                    blank=True, default=dict, help_text='Structured preference weights and settings',
                    verbose_name='Preference Weights'
                )),
                ('stats', models.JSONField(
                    blank=True, default=dict, help_text='Approval rates, rejection reasons, timing stats, etc.',
                    verbose_name='Learning Statistics'
                )),
                ('last_updated', models.DateTimeField(
                    auto_now=True, help_text='When preferences were last updated', verbose_name='Last Updated'
                )),
                ('client', models.ForeignKey(
                    help_text='Tenant/client this profile belongs to', on_delete=django.db.models.deletion.CASCADE,
                    related_name='preference_profiles', to='onboarding.bt', verbose_name='Client'
                )),
                ('user', models.ForeignKey(
                    blank=True, help_text='User this profile belongs to (null for tenant-wide profiles)',
                    null=True, on_delete=django.db.models.deletion.CASCADE, related_name='preference_profiles',
                    to=settings.AUTH_USER_MODEL, verbose_name='User'
                )),
            ],
            options={
                'verbose_name': 'Preference Profile',
                'verbose_name_plural': 'Preference Profiles',
                'db_table': 'preference_profile',
                'get_latest_by': ['last_updated', 'mdtz'],
            },
        ),

        # Add RecommendationInteraction model
        migrations.CreateModel(
            name='RecommendationInteraction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified')),
                ('interaction_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('event_type', models.CharField(
                    choices=[
                        ('viewed', 'Viewed'), ('clicked_detail', 'Clicked Detail'), ('approved', 'Approved'),
                        ('rejected', 'Rejected'), ('modified', 'Modified'), ('escalated', 'Escalated'),
                        ('timeout', 'Timed Out'), ('abandoned', 'Abandoned')
                    ],
                    max_length=20, verbose_name='Event Type'
                )),
                ('metadata', models.JSONField(
                    blank=True, default=dict, help_text='Time on item, scroll depth, reason codes, token usage, etc.',
                    verbose_name='Interaction Metadata'
                )),
                ('occurred_at', models.DateTimeField(
                    auto_now_add=True, help_text='When the interaction occurred', verbose_name='Occurred At'
                )),
                ('recommendation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='interactions',
                    to='onboarding.llmrecommendation', verbose_name='Recommendation'
                )),
                ('session', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='interactions',
                    to='onboarding.conversationsession', verbose_name='Session'
                )),
            ],
            options={
                'verbose_name': 'Recommendation Interaction',
                'verbose_name_plural': 'Recommendation Interactions',
                'db_table': 'recommendation_interaction',
                'get_latest_by': ['occurred_at'],
            },
        ),

        # Add Experiment model
        migrations.CreateModel(
            name='Experiment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified')),
                ('experiment_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(
                    help_text='Human-readable experiment name', max_length=200, verbose_name='Experiment Name'
                )),
                ('description', models.TextField(
                    blank=True, help_text='Detailed experiment description and objectives', verbose_name='Description'
                )),
                ('scope', models.CharField(
                    choices=[('global', 'Global'), ('tenant', 'Tenant'), ('user_segment', 'User Segment')],
                    default='tenant', max_length=20, verbose_name='Scope'
                )),
                ('arms', models.JSONField(
                    help_text='Configuration for each experiment arm (A/B variants)', verbose_name='Experiment Arms'
                )),
                ('primary_metric', models.CharField(
                    default='acceptance_rate',
                    help_text='Primary metric to optimize (acceptance_rate, time_to_approval, cost_per_accepted)',
                    max_length=50, verbose_name='Primary Metric'
                )),
                ('secondary_metrics', models.JSONField(
                    blank=True, default=list, help_text='Additional metrics to track', verbose_name='Secondary Metrics'
                )),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'), ('running', 'Running'), ('paused', 'Paused'),
                        ('completed', 'Completed'), ('archived', 'Archived')
                    ],
                    default='draft', max_length=20, verbose_name='Status'
                )),
                ('holdback_pct', models.FloatField(
                    default=10.0, help_text='Percentage of traffic to hold back as control group',
                    verbose_name='Holdback Percentage'
                )),
                ('started_at', models.DateTimeField(
                    blank=True, help_text='When experiment was started', null=True, verbose_name='Started At'
                )),
                ('ended_at', models.DateTimeField(
                    blank=True, help_text='When experiment was ended', null=True, verbose_name='Ended At'
                )),
                ('safety_constraints', models.JSONField(
                    blank=True, default=dict, help_text='Safety thresholds and constraints',
                    verbose_name='Safety Constraints'
                )),
                ('results', models.JSONField(
                    blank=True, default=dict, help_text='Statistical analysis and results',
                    verbose_name='Experiment Results'
                )),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='owned_experiments',
                    to=settings.AUTH_USER_MODEL, verbose_name='Owner'
                )),
            ],
            options={
                'verbose_name': 'Experiment',
                'verbose_name_plural': 'Experiments',
                'db_table': 'experiment',
                'get_latest_by': ['started_at', 'cdtz'],
            },
        ),

        # Add ExperimentAssignment model
        migrations.CreateModel(
            name='ExperimentAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, db_index=True, verbose_name='Modified')),
                ('assignment_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('arm', models.CharField(
                    help_text='Which arm/variant this user/client is assigned to', max_length=50,
                    verbose_name='Experiment Arm'
                )),
                ('assigned_at', models.DateTimeField(
                    auto_now_add=True, help_text='When assignment was made', verbose_name='Assigned At'
                )),
                ('expires_at', models.DateTimeField(
                    blank=True, help_text='When assignment expires (null = never expires)', null=True,
                    verbose_name='Expires At'
                )),
                ('assignment_context', models.JSONField(
                    blank=True, default=dict, help_text='Context data used for assignment decision',
                    verbose_name='Assignment Context'
                )),
                ('client', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='experiment_assignments',
                    to='onboarding.bt', verbose_name='Client'
                )),
                ('experiment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='assignments',
                    to='onboarding.experiment', verbose_name='Experiment'
                )),
                ('user', models.ForeignKey(
                    blank=True, help_text='User assigned to experiment arm (null for client-level assignment)',
                    null=True, on_delete=django.db.models.deletion.CASCADE, related_name='experiment_assignments',
                    to=settings.AUTH_USER_MODEL, verbose_name='User'
                )),
            ],
            options={
                'verbose_name': 'Experiment Assignment',
                'verbose_name_plural': 'Experiment Assignments',
                'db_table': 'experiment_assignment',
                'get_latest_by': ['assigned_at'],
            },
        ),

        # Add indexes for PreferenceProfile
        migrations.AddIndex(
            model_name='preferenceprofile',
            index=models.Index(fields=['client', 'user'], name='pref_client_user_idx'),
        ),
        migrations.AddIndex(
            model_name='preferenceprofile',
            index=models.Index(fields=['last_updated'], name='pref_last_updated_idx'),
        ),
        migrations.AddIndex(
            model_name='preferenceprofile',
            index=models.Index(fields=['client', 'last_updated'], name='pref_client_updated_idx'),
        ),

        # Add indexes for RecommendationInteraction
        migrations.AddIndex(
            model_name='recommendationinteraction',
            index=models.Index(fields=['session', 'event_type'], name='interact_session_event_idx'),
        ),
        migrations.AddIndex(
            model_name='recommendationinteraction',
            index=models.Index(fields=['recommendation', 'event_type'], name='interact_rec_event_idx'),
        ),
        migrations.AddIndex(
            model_name='recommendationinteraction',
            index=models.Index(fields=['occurred_at'], name='interact_occurred_idx'),
        ),
        migrations.AddIndex(
            model_name='recommendationinteraction',
            index=models.Index(fields=['event_type', 'occurred_at'], name='interact_event_time_idx'),
        ),

        # Add indexes for Experiment
        migrations.AddIndex(
            model_name='experiment',
            index=models.Index(fields=['status', 'scope'], name='exp_status_scope_idx'),
        ),
        migrations.AddIndex(
            model_name='experiment',
            index=models.Index(fields=['owner'], name='exp_owner_idx'),
        ),
        migrations.AddIndex(
            model_name='experiment',
            index=models.Index(fields=['started_at'], name='exp_started_idx'),
        ),
        migrations.AddIndex(
            model_name='experiment',
            index=models.Index(fields=['primary_metric', 'status'], name='exp_metric_status_idx'),
        ),

        # Add indexes for ExperimentAssignment
        migrations.AddIndex(
            model_name='experimentassignment',
            index=models.Index(fields=['experiment', 'user'], name='exp_assign_exp_user_idx'),
        ),
        migrations.AddIndex(
            model_name='experimentassignment',
            index=models.Index(fields=['experiment', 'client'], name='exp_assign_exp_client_idx'),
        ),
        migrations.AddIndex(
            model_name='experimentassignment',
            index=models.Index(fields=['user', 'assigned_at'], name='exp_assign_user_date_idx'),
        ),
        migrations.AddIndex(
            model_name='experimentassignment',
            index=models.Index(fields=['client', 'assigned_at'], name='exp_assign_client_date_idx'),
        ),
        migrations.AddIndex(
            model_name='experimentassignment',
            index=models.Index(fields=['expires_at'], name='exp_assign_expires_idx'),
        ),

        # Add constraints for PreferenceProfile
        migrations.AddConstraint(
            model_name='preferenceprofile',
            constraint=models.UniqueConstraint(
                fields=['client', 'user'], name='unique_preference_per_user_client'
            ),
        ),

        # Add constraints for ExperimentAssignment
        migrations.AddConstraint(
            model_name='experimentassignment',
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=False),
                fields=['experiment', 'user', 'client'],
                name='unique_experiment_assignment_per_user'
            ),
        ),
        migrations.AddConstraint(
            model_name='experimentassignment',
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=True),
                fields=['experiment', 'client'],
                name='unique_experiment_assignment_per_client'
            ),
        ),

        # Add fields to existing LLMRecommendation model for personalization tracking
        migrations.AddField(
            model_name='llmrecommendation',
            name='provider_used',
            field=models.CharField(
                blank=True, help_text='LLM provider used for this recommendation',
                max_length=50, null=True
            ),
        ),
        migrations.AddField(
            model_name='llmrecommendation',
            name='token_usage',
            field=models.JSONField(
                blank=True, default=dict, help_text='Token usage breakdown by provider and stage'
            ),
        ),
        migrations.AddField(
            model_name='llmrecommendation',
            name='applied_policy_version',
            field=models.CharField(
                blank=True, help_text='Version of policy template applied',
                max_length=50, null=True
            ),
        ),
        migrations.AddField(
            model_name='llmrecommendation',
            name='experiment_arm',
            field=models.CharField(
                blank=True, help_text='Experiment arm this recommendation was generated under',
                max_length=50, null=True
            ),
        ),
    ]