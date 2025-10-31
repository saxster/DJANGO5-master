# Generated initial migration for wellness app

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    atomic = False  # Required for CREATE INDEX CONCURRENTLY

    dependencies = [
        ('tenants', '0001_initial'),
        ('journal', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WellnessContent',
            fields=[
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('title', models.CharField(help_text='Content title - clear and actionable', max_length=200)),
                ('summary', models.TextField(help_text='Brief summary for quick scanning', max_length=500)),
                ('content', models.TextField(help_text='Main educational content')),
                ('category', models.CharField(choices=[('mental_health', 'Mental Health'), ('physical_wellness', 'Physical Wellness'), ('workplace_health', 'Workplace Health'), ('substance_awareness', 'Substance Awareness'), ('preventive_care', 'Preventive Care'), ('sleep_hygiene', 'Sleep Hygiene'), ('nutrition_basics', 'Nutrition Basics'), ('stress_management', 'Stress Management'), ('physical_activity', 'Physical Activity'), ('mindfulness', 'Mindfulness')], help_text='Primary wellness category', max_length=50)),
                ('delivery_context', models.CharField(choices=[('daily_tip', 'Daily Wellness Tip'), ('pattern_triggered', 'Pattern-Based Delivery'), ('stress_response', 'High Stress Response'), ('mood_support', 'Low Mood Support'), ('energy_boost', 'Low Energy Response'), ('shift_transition', 'Shift Start/End'), ('streak_milestone', 'Milestone Reward'), ('seasonal', 'Seasonal Health'), ('workplace_specific', 'Workplace Guidance'), ('gratitude_enhancement', 'Positive Psychology Reinforcement')], help_text='When/how this content should be delivered', max_length=50)),
                ('content_level', models.CharField(choices=[('quick_tip', 'Quick Tip (1 min)'), ('short_read', 'Short Read (3 min)'), ('deep_dive', 'Deep Dive (7 min)'), ('interactive', 'Interactive (5 min)'), ('video_content', 'Video Content (4 min)')], help_text='Content complexity and time requirement', max_length=20)),
                ('evidence_level', models.CharField(choices=[('who_cdc', 'WHO/CDC Guideline'), ('peer_reviewed', 'Peer-Reviewed Research'), ('professional', 'Professional Consensus'), ('established', 'Established Practice'), ('educational', 'General Education')], help_text='Quality of evidence backing this content', max_length=30)),
                ('tags', models.JSONField(default=list, help_text='Tags for pattern matching with journal entries')),
                ('trigger_patterns', models.JSONField(default=dict, help_text='Complex trigger conditions for content delivery')),
                ('workplace_specific', models.BooleanField(default=False, help_text='Content specifically adapted for workplace contexts')),
                ('field_worker_relevant', models.BooleanField(default=False, help_text='Relevant for field workers and mobile contexts')),
                ('action_tips', models.JSONField(default=list, help_text='Concrete, actionable advice points')),
                ('key_takeaways', models.JSONField(default=list, help_text='Key learning points and insights')),
                ('related_topics', models.JSONField(default=list, help_text='IDs of related content for progressive learning')),
                ('source_name', models.CharField(help_text='Source organization (WHO, CDC, Mayo Clinic, etc.)', max_length=100)),
                ('source_url', models.URLField(blank=True, help_text='Original source URL for verification', null=True)),
                ('evidence_summary', models.TextField(blank=True, help_text='Summary of evidence backing this content')),
                ('citations', models.JSONField(default=list, help_text='Academic citations and references')),
                ('last_verified_date', models.DateTimeField(blank=True, help_text='Last time content accuracy was verified', null=True)),
                ('is_active', models.BooleanField(default=True, help_text='Whether content is available for delivery')),
                ('priority_score', models.IntegerField(default=50, help_text='Priority for content selection (1-100, higher = more likely to show)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)])),
                ('seasonal_relevance', models.JSONField(default=list, help_text='Months when content is most relevant (1-12)')),
                ('frequency_limit_days', models.IntegerField(default=0, help_text='Minimum days between showings to same user')),
                ('estimated_reading_time', models.IntegerField(help_text='Estimated reading/consumption time in minutes')),
                ('complexity_score', models.IntegerField(default=1, help_text='Content complexity/reading difficulty (1-5)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('content_version', models.CharField(default='1.0', help_text='Version for content updates and tracking', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(help_text='Content creator/editor', null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Wellness Content',
                'verbose_name_plural': 'Wellness Content Items',
                'ordering': ['-priority_score', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WellnessUserProgress',
            fields=[
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_streak', models.IntegerField(default=0, help_text='Current consecutive days of wellness engagement')),
                ('longest_streak', models.IntegerField(default=0, help_text='Longest streak ever achieved')),
                ('last_activity_date', models.DateTimeField(blank=True, help_text='Last date user engaged with wellness content', null=True)),
                ('total_content_viewed', models.IntegerField(default=0, help_text='Total number of content items viewed')),
                ('total_content_completed', models.IntegerField(default=0, help_text='Total number of content items fully completed')),
                ('total_time_spent_minutes', models.IntegerField(default=0, help_text='Total time spent consuming wellness content')),
                ('total_score', models.IntegerField(default=0, help_text='Cumulative engagement score')),
                ('mental_health_progress', models.IntegerField(default=0, help_text='Progress score for mental health content')),
                ('physical_wellness_progress', models.IntegerField(default=0, help_text='Progress score for physical wellness content')),
                ('workplace_health_progress', models.IntegerField(default=0, help_text='Progress score for workplace health content')),
                ('substance_awareness_progress', models.IntegerField(default=0, help_text='Progress score for substance awareness content')),
                ('preventive_care_progress', models.IntegerField(default=0, help_text='Progress score for preventive care content')),
                ('preferred_content_level', models.CharField(choices=[('quick_tip', 'Quick Tip (1 min)'), ('short_read', 'Short Read (3 min)'), ('deep_dive', 'Deep Dive (7 min)'), ('interactive', 'Interactive (5 min)'), ('video_content', 'Video Content (4 min)')], default='short_read', help_text='Preferred content complexity level', max_length=20)),
                ('preferred_delivery_time', models.TimeField(blank=True, help_text='Preferred time of day for content delivery', null=True)),
                ('enabled_categories', models.JSONField(default=list, help_text='Wellness categories user wants to receive content for')),
                ('daily_tip_enabled', models.BooleanField(default=True, help_text='Whether user wants daily wellness tips')),
                ('contextual_delivery_enabled', models.BooleanField(default=True, help_text='Whether to deliver content based on journal patterns')),
                ('achievements_earned', models.JSONField(default=list, help_text='List of achievement IDs/names earned by user')),
                ('milestone_alerts_enabled', models.BooleanField(default=True, help_text='Whether to notify user of milestones and achievements')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(help_text='User this progress belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='wellness_progress', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Wellness Progress',
                'verbose_name_plural': 'User Wellness Progress',
            },
        ),
        migrations.CreateModel(
            name='WellnessContentInteraction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('interaction_type', models.CharField(choices=[('viewed', 'Viewed'), ('completed', 'Completed Reading'), ('bookmarked', 'Bookmarked'), ('shared', 'Shared'), ('dismissed', 'Dismissed'), ('rated', 'Rated'), ('acted_upon', 'Took Action'), ('requested_more', 'Requested More Info')], help_text='Type of interaction performed', max_length=20)),
                ('delivery_context', models.CharField(choices=[('daily_tip', 'Daily Wellness Tip'), ('pattern_triggered', 'Pattern-Based Delivery'), ('stress_response', 'High Stress Response'), ('mood_support', 'Low Mood Support'), ('energy_boost', 'Low Energy Response'), ('shift_transition', 'Shift Start/End'), ('streak_milestone', 'Milestone Reward'), ('seasonal', 'Seasonal Health'), ('workplace_specific', 'Workplace Guidance'), ('gratitude_enhancement', 'Positive Psychology Reinforcement')], help_text='Context in which content was delivered', max_length=50)),
                ('time_spent_seconds', models.IntegerField(blank=True, help_text='Time spent engaging with content', null=True)),
                ('completion_percentage', models.IntegerField(blank=True, help_text='Percentage of content consumed (0-100)', null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('user_rating', models.IntegerField(blank=True, help_text='User rating of content (1-5 stars)', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('user_feedback', models.TextField(blank=True, help_text='Optional user feedback or comments')),
                ('action_taken', models.BooleanField(default=False, help_text='Whether user indicated they took recommended action')),
                ('user_mood_at_delivery', models.IntegerField(blank=True, help_text="User's mood rating when content was delivered", null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('user_stress_at_delivery', models.IntegerField(blank=True, help_text="User's stress level when content was delivered", null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('interaction_date', models.DateTimeField(auto_now_add=True)),
                ('metadata', models.JSONField(default=dict, help_text='Additional context and metadata')),
                ('content', models.ForeignKey(help_text='Content that was interacted with', on_delete=django.db.models.deletion.CASCADE, related_name='interactions', to='wellness.wellnesscontent')),
                ('trigger_journal_entry', models.ForeignKey(blank=True, help_text='Journal entry that triggered this content delivery', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='triggered_wellness_content', to='journal.journalentry')),
                ('user', models.ForeignKey(help_text='User who interacted with content', on_delete=django.db.models.deletion.CASCADE, related_name='wellness_interactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Wellness Content Interaction',
                'verbose_name_plural': 'Wellness Content Interactions',
                'ordering': ['-interaction_date'],
            },
        ),
        # Database indexes for optimal performance
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_content_category_context_idx ON wellness_wellnesscontent (category, delivery_context);",
            reverse_sql="DROP INDEX IF EXISTS wellness_content_category_context_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_content_active_priority_idx ON wellness_wellnesscontent (is_active, priority_score DESC);",
            reverse_sql="DROP INDEX IF EXISTS wellness_content_active_priority_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_content_workplace_field_idx ON wellness_wellnesscontent (workplace_specific, field_worker_relevant);",
            reverse_sql="DROP INDEX IF EXISTS wellness_content_workplace_field_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_content_tenant_category_idx ON wellness_wellnesscontent (tenant_id, category);",
            reverse_sql="DROP INDEX IF EXISTS wellness_content_tenant_category_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_content_evidence_idx ON wellness_wellnesscontent (evidence_level);",
            reverse_sql="DROP INDEX IF EXISTS wellness_content_evidence_idx;"
        ),
        # GIN indexes for JSON fields (PostgreSQL specific)
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_content_tags_gin_idx ON wellness_wellnesscontent USING GIN (tags);",
            reverse_sql="DROP INDEX IF EXISTS wellness_content_tags_gin_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_content_trigger_patterns_gin_idx ON wellness_wellnesscontent USING GIN (trigger_patterns);",
            reverse_sql="DROP INDEX IF EXISTS wellness_content_trigger_patterns_gin_idx;"
        ),
        # User progress indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_progress_user_idx ON wellness_wellnessuserprogress (user_id);",
            reverse_sql="DROP INDEX IF EXISTS wellness_progress_user_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_progress_streak_idx ON wellness_wellnessuserprogress (current_streak DESC);",
            reverse_sql="DROP INDEX IF EXISTS wellness_progress_streak_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_progress_activity_idx ON wellness_wellnessuserprogress (last_activity_date DESC);",
            reverse_sql="DROP INDEX IF EXISTS wellness_progress_activity_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_progress_tenant_idx ON wellness_wellnessuserprogress (tenant_id);",
            reverse_sql="DROP INDEX IF EXISTS wellness_progress_tenant_idx;"
        ),
        # Interaction indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_interaction_user_date_idx ON wellness_wellnesscontentinteraction (user_id, interaction_date DESC);",
            reverse_sql="DROP INDEX IF EXISTS wellness_interaction_user_date_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_interaction_content_type_idx ON wellness_wellnesscontentinteraction (content_id, interaction_type);",
            reverse_sql="DROP INDEX IF EXISTS wellness_interaction_content_type_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_interaction_trigger_entry_idx ON wellness_wellnesscontentinteraction (trigger_journal_entry_id);",
            reverse_sql="DROP INDEX IF EXISTS wellness_interaction_trigger_entry_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_interaction_delivery_context_idx ON wellness_wellnesscontentinteraction (delivery_context);",
            reverse_sql="DROP INDEX IF EXISTS wellness_interaction_delivery_context_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_interaction_type_idx ON wellness_wellnesscontentinteraction (interaction_type);",
            reverse_sql="DROP INDEX IF EXISTS wellness_interaction_type_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS wellness_interaction_rating_idx ON wellness_wellnesscontentinteraction (user_rating);",
            reverse_sql="DROP INDEX IF EXISTS wellness_interaction_rating_idx;"
        ),
        # Add check constraints
        migrations.AddConstraint(
            model_name='wellnesscontent',
            constraint=models.CheckConstraint(
                check=models.Q(('priority_score__gte', 1), ('priority_score__lte', 100)),
                name='valid_wellness_priority_score'
            ),
        ),
        migrations.AddConstraint(
            model_name='wellnesscontent',
            constraint=models.CheckConstraint(
                check=models.Q(('complexity_score__gte', 1), ('complexity_score__lte', 5)),
                name='valid_wellness_complexity_score'
            ),
        ),
        migrations.AddConstraint(
            model_name='wellnesscontent',
            constraint=models.CheckConstraint(
                check=models.Q(('estimated_reading_time__gte', 1)),
                name='valid_reading_time'
            ),
        ),
        migrations.AddConstraint(
            model_name='wellnesscontentinteraction',
            constraint=models.CheckConstraint(
                check=models.Q(models.Q(('completion_percentage__gte', 0), ('completion_percentage__lte', 100)), models.Q(('completion_percentage__isnull', True)), _connector='OR'),
                name='valid_completion_percentage'
            ),
        ),
        migrations.AddConstraint(
            model_name='wellnesscontentinteraction',
            constraint=models.CheckConstraint(
                check=models.Q(models.Q(('user_rating__gte', 1), ('user_rating__lte', 5)), models.Q(('user_rating__isnull', True)), _connector='OR'),
                name='valid_user_rating'
            ),
        ),
    ]