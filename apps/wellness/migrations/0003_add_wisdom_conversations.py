# Generated manually for Wisdom Conversations feature

import django.core.validators
from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('journal', '0003_refactor_journal_entry_models'),
        ('wellness', '0002_add_conversation_translation_models'),
        ('wellness', '0002_add_mental_health_interventions'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConversationThread',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('thread_type', models.CharField(choices=[('gratitude_journey', 'Gratitude Practice Journey'), ('stress_management', 'Stress Management Path'), ('three_good_things', 'Three Good Things Evolution'), ('cbt_cognitive', 'Cognitive Behavioral Insights'), ('crisis_recovery', 'Crisis Recovery Narrative'), ('workplace_wellness', 'Workplace Wellness Journey'), ('motivational_growth', 'Motivational Growth Story'), ('preventive_care', 'Preventive Mental Health'), ('achievement_celebration', 'Achievement & Milestone Celebrations'), ('reflection_insights', 'Deep Reflection Insights')], max_length=50)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True, help_text='Brief description of this conversation thread')),
                ('status', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('completed', 'Completed'), ('archived', 'Archived')], default='active', max_length=20)),
                ('priority_level', models.IntegerField(default=1, help_text='1=Low, 5=Critical (for crisis threads)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('conversation_count', models.PositiveIntegerField(default=0)),
                ('first_conversation_date', models.DateTimeField(blank=True, null=True)),
                ('last_conversation_date', models.DateTimeField(blank=True, null=True)),
                ('narrative_style', models.CharField(choices=[('warm_supportive', 'Warm & Supportive'), ('professional_clinical', 'Professional Clinical'), ('gentle_encouraging', 'Gentle Encouraging'), ('motivational_energetic', 'Motivational Energetic'), ('crisis_stabilizing', 'Crisis Stabilizing')], default='warm_supportive', max_length=30)),
                ('personalization_data', models.JSONField(default=dict, help_text='User preferences and effectiveness data for this thread type')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_threads', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'wellness_conversation_threads',
            },
        ),
        migrations.CreateModel(
            name='WisdomConversation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('conversation_text', models.TextField(help_text='The main conversational text that feels like a continuous book narrative')),
                ('conversation_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('conversation_tone', models.CharField(choices=[('celebratory', 'Celebratory'), ('supportive', 'Supportive'), ('encouraging', 'Encouraging'), ('reflective', 'Reflective'), ('motivational', 'Motivational'), ('crisis_stabilizing', 'Crisis Stabilizing'), ('gentle_guidance', 'Gentle Guidance'), ('professional_clinical', 'Professional Clinical')], max_length=30)),
                ('source_type', models.CharField(choices=[('intervention_delivery', 'Mental Health Intervention'), ('crisis_response', 'Crisis Response'), ('milestone_celebration', 'Milestone Achievement'), ('weekly_reflection', 'Weekly Reflection'), ('contextual_bridge', 'Contextual Bridge'), ('manual_entry', 'Manual Entry')], max_length=30)),
                ('contextual_bridge_text', models.TextField(blank=True, help_text='Bridging text that connects this conversation to the previous one seamlessly')),
                ('word_count', models.PositiveIntegerField(default=0)),
                ('estimated_reading_time_seconds', models.PositiveIntegerField(default=0)),
                ('personalization_score', models.FloatField(default=0.0, help_text='How well personalized this conversation is (0.0-1.0)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('conversation_metadata', models.JSONField(default=dict, help_text='Additional metadata like intervention techniques used, keywords, etc.')),
                ('sequence_number', models.PositiveIntegerField(help_text='Position in the chronological conversation sequence for this thread')),
                ('is_milestone_conversation', models.BooleanField(default=False, help_text='Marks significant conversations (achievements, breakthroughs, etc.)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('bridges_from_conversation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bridges_to_conversations', to='wellness.wisdomconversation')),
                ('source_intervention_delivery', models.ForeignKey(blank=True, help_text='Source intervention delivery that was transformed into this conversation', null=True, on_delete=django.db.models.deletion.SET_NULL, to='wellness.interventiondeliverylog')),
                ('source_journal_entry', models.ForeignKey(blank=True, help_text='Journal entry that triggered this conversation', null=True, on_delete=django.db.models.deletion.SET_NULL, to='journal.journalentry')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wisdom_conversations', to='wellness.conversationthread')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wisdom_conversations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'wellness_wisdom_conversations',
                'ordering': ['thread', 'sequence_number'],
            },
        ),
        migrations.CreateModel(
            name='ConversationEngagement',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('engagement_type', models.CharField(choices=[('view', 'Viewed'), ('read_complete', 'Read Completely'), ('bookmark', 'Bookmarked'), ('share', 'Shared'), ('reflection_note', 'Added Reflection Note'), ('positive_feedback', 'Positive Feedback'), ('request_more', 'Requested More'), ('skip', 'Skipped'), ('negative_feedback', 'Negative Feedback')], max_length=30)),
                ('engagement_date', models.DateTimeField(auto_now_add=True)),
                ('time_spent_seconds', models.PositiveIntegerField(default=0, help_text='Time user spent reading/engaging with this conversation')),
                ('scroll_percentage', models.FloatField(default=0.0, help_text='Percentage of conversation text scrolled through', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(100.0)])),
                ('effectiveness_rating', models.IntegerField(blank=True, help_text='User rating of conversation effectiveness (1-5)', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('user_reflection_note', models.TextField(blank=True, help_text='Optional user reflection or notes about this conversation')),
                ('device_type', models.CharField(choices=[('mobile', 'Mobile'), ('tablet', 'Tablet'), ('desktop', 'Desktop')], default='mobile', max_length=20)),
                ('access_context', models.CharField(choices=[('routine_check', 'Routine Check'), ('notification_prompt', 'Notification Prompt'), ('crisis_support', 'Crisis Support'), ('milestone_celebration', 'Milestone Celebration'), ('search_discovery', 'Search Discovery'), ('manual_browse', 'Manual Browse')], default='routine_check', max_length=30)),
                ('engagement_metadata', models.JSONField(default=dict, help_text='Additional engagement context and analytics data')),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='engagements', to='wellness.wisdomconversation')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_engagements', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'wellness_conversation_engagements',
            },
        ),
        migrations.CreateModel(
            name='ConversationBookmark',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('category', models.CharField(choices=[('breakthrough', 'Breakthrough Moment'), ('inspiration', 'Inspiration'), ('practical_tool', 'Practical Tool'), ('crisis_help', 'Crisis Help'), ('milestone', 'Personal Milestone'), ('daily_reminder', 'Daily Reminder'), ('professional_reference', 'Professional Reference'), ('share_worthy', 'Worth Sharing')], default='inspiration', max_length=30)),
                ('personal_note', models.TextField(blank=True, help_text='Personal note about why this conversation was bookmarked')),
                ('reminder_enabled', models.BooleanField(default=False, help_text='Whether to send periodic reminders about this bookmarked conversation')),
                ('reminder_frequency_days', models.PositiveIntegerField(default=30, help_text='How often to remind user about this bookmark (in days)')),
                ('last_reminder_sent', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookmarks', to='wellness.wisdomconversation')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_bookmarks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'wellness_conversation_bookmarks',
            },
        ),
        migrations.AddIndex(
            model_name='conversationthread',
            index=models.Index(fields=['user', 'thread_type'], name='wellness_co_user_id_fa0eb6_idx'),
        ),
        migrations.AddIndex(
            model_name='conversationthread',
            index=models.Index(fields=['status', 'priority_level'], name='wellness_co_status_b3e8b0_idx'),
        ),
        migrations.AddIndex(
            model_name='conversationthread',
            index=models.Index(fields=['last_conversation_date'], name='wellness_co_last_co_ec8d62_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='conversationthread',
            unique_together={('user', 'thread_type')},
        ),
        migrations.AddIndex(
            model_name='wisdomconversation',
            index=models.Index(fields=['user', 'conversation_date'], name='wellness_wi_user_id_56b4e9_idx'),
        ),
        migrations.AddIndex(
            model_name='wisdomconversation',
            index=models.Index(fields=['thread', 'sequence_number'], name='wellness_wi_thread__a1de57_idx'),
        ),
        migrations.AddIndex(
            model_name='wisdomconversation',
            index=models.Index(fields=['source_type', 'conversation_date'], name='wellness_wi_source__53c7a5_idx'),
        ),
        migrations.AddIndex(
            model_name='wisdomconversation',
            index=models.Index(fields=['is_milestone_conversation'], name='wellness_wi_is_mile_d54de9_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='wisdomconversation',
            unique_together={('thread', 'sequence_number')},
        ),
        migrations.AddIndex(
            model_name='conversationengagement',
            index=models.Index(fields=['user', 'engagement_date'], name='wellness_co_user_id_1f8b2b_idx'),
        ),
        migrations.AddIndex(
            model_name='conversationengagement',
            index=models.Index(fields=['conversation', 'engagement_type'], name='wellness_co_convers_89f3d9_idx'),
        ),
        migrations.AddIndex(
            model_name='conversationengagement',
            index=models.Index(fields=['effectiveness_rating'], name='wellness_co_effecti_7feba5_idx'),
        ),
        migrations.AddIndex(
            model_name='conversationengagement',
            index=models.Index(fields=['access_context', 'engagement_date'], name='wellness_co_access__d0e9a8_idx'),
        ),
        migrations.AddIndex(
            model_name='conversationbookmark',
            index=models.Index(fields=['user', 'category'], name='wellness_co_user_id_8e0041_idx'),
        ),
        migrations.AddIndex(
            model_name='conversationbookmark',
            index=models.Index(fields=['reminder_enabled', 'last_reminder_sent'], name='wellness_co_reminre_dd97f8_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='conversationbookmark',
            unique_together={('user', 'conversation')},
        ),
    ]