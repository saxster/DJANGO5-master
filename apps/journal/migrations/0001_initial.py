# Generated initial migration for journal app

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='JournalPrivacySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('default_privacy_scope', models.CharField(choices=[('private', 'Private - Only visible to me'), ('manager', 'Manager - Visible to my direct manager'), ('team', 'Team - Visible to my team'), ('aggregate', 'Aggregate - Anonymous statistics only'), ('shared', 'Shared - Visible to selected stakeholders')], default='private', help_text='Default privacy scope for new entries', max_length=20)),
                ('wellbeing_sharing_consent', models.BooleanField(default=False, help_text='Consent to share wellbeing data for analytics')),
                ('manager_access_consent', models.BooleanField(default=False, help_text='Consent for manager to access certain entries')),
                ('analytics_consent', models.BooleanField(default=False, help_text='Consent for anonymous analytics and insights')),
                ('crisis_intervention_consent', models.BooleanField(default=False, help_text='Consent for crisis intervention based on entries')),
                ('data_retention_days', models.IntegerField(default=365, help_text='How long to retain journal data (30-3650 days)', validators=[django.core.validators.MinValueValidator(30), django.core.validators.MaxValueValidator(3650)])),
                ('auto_delete_enabled', models.BooleanField(default=False, help_text='Whether to automatically delete old entries')),
                ('consent_timestamp', models.DateTimeField(help_text='When initial consent was given')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(help_text='User these privacy settings belong to', on_delete=django.db.models.deletion.CASCADE, related_name='journal_privacy_settings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Journal Privacy Settings',
                'verbose_name_plural': 'Journal Privacy Settings',
            },
        ),
        migrations.CreateModel(
            name='JournalEntry',
            fields=[
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('entry_type', models.CharField(choices=[('site_inspection', 'Site Inspection'), ('equipment_maintenance', 'Equipment Maintenance'), ('safety_audit', 'Safety Audit'), ('training_completed', 'Training Completed'), ('project_milestone', 'Project Milestone'), ('team_collaboration', 'Team Collaboration'), ('client_interaction', 'Client Interaction'), ('process_improvement', 'Process Improvement'), ('documentation_update', 'Documentation Update'), ('field_observation', 'Field Observation'), ('quality_note', 'Quality Note'), ('investigation_note', 'Investigation Note'), ('safety_concern', 'Safety Concern'), ('personal_reflection', 'Personal Reflection'), ('mood_check_in', 'Mood Check-in'), ('gratitude', 'Gratitude Entry'), ('three_good_things', '3 Good Things'), ('daily_affirmations', 'Daily Affirmations'), ('stress_log', 'Stress Log'), ('strength_spotting', 'Strength Spotting'), ('reframe_challenge', 'Reframe Challenge'), ('daily_intention', 'Daily Intention'), ('end_of_shift_reflection', 'End of Shift Reflection'), ('best_self_weekly', 'Best Self Weekly')], help_text='Type of journal entry (work or wellbeing)', max_length=50)),
                ('title', models.CharField(help_text='Entry title', max_length=200)),
                ('subtitle', models.CharField(blank=True, help_text='Optional subtitle', max_length=200)),
                ('content', models.TextField(blank=True, help_text='Main entry content')),
                ('timestamp', models.DateTimeField(help_text='When this entry was created')),
                ('duration_minutes', models.IntegerField(blank=True, help_text='Duration of activity in minutes', null=True)),
                ('privacy_scope', models.CharField(choices=[('private', 'Private - Only visible to me'), ('manager', 'Manager - Visible to my direct manager'), ('team', 'Team - Visible to my team'), ('aggregate', 'Aggregate - Anonymous statistics only'), ('shared', 'Shared - Visible to selected stakeholders')], default='private', help_text='Who can access this entry', max_length=20)),
                ('consent_given', models.BooleanField(default=False, help_text='User consent for data processing')),
                ('consent_timestamp', models.DateTimeField(blank=True, help_text='When consent was given', null=True)),
                ('sharing_permissions', models.JSONField(default=list, help_text='List of user IDs who can access this entry')),
                ('mood_rating', models.IntegerField(blank=True, help_text='Mood rating on 1-10 scale', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('mood_description', models.CharField(blank=True, help_text='Optional mood description', max_length=100)),
                ('stress_level', models.IntegerField(blank=True, help_text='Stress level on 1-5 scale', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('energy_level', models.IntegerField(blank=True, help_text='Energy level on 1-10 scale', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('stress_triggers', models.JSONField(default=list, help_text='List of identified stress triggers')),
                ('coping_strategies', models.JSONField(default=list, help_text='List of coping strategies used')),
                ('gratitude_items', models.JSONField(default=list, help_text='List of things user is grateful for')),
                ('daily_goals', models.JSONField(default=list, help_text='List of daily goals or intentions')),
                ('affirmations', models.JSONField(default=list, help_text='List of positive affirmations')),
                ('achievements', models.JSONField(default=list, help_text='List of achievements or accomplishments')),
                ('learnings', models.JSONField(default=list, help_text='List of key learnings from the day')),
                ('challenges', models.JSONField(default=list, help_text='List of challenges faced')),
                ('location_site_name', models.CharField(blank=True, help_text='Name of work site or location', max_length=200)),
                ('location_address', models.TextField(blank=True, help_text='Full address of location')),
                ('location_coordinates', models.JSONField(blank=True, help_text='GPS coordinates as {"lat": 0.0, "lng": 0.0}', null=True)),
                ('location_area_type', models.CharField(blank=True, help_text='Type of work area (office, field, client site, etc.)', max_length=100)),
                ('team_members', models.JSONField(default=list, help_text='List of team members involved')),
                ('tags', models.JSONField(default=list, help_text='List of tags for categorization and search')),
                ('priority', models.CharField(blank=True, help_text='Priority level (low, medium, high, urgent)', max_length=20)),
                ('severity', models.CharField(blank=True, help_text='Severity level for issues or concerns', max_length=20)),
                ('completion_rate', models.FloatField(blank=True, help_text='Completion rate as decimal (0.0 to 1.0)', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('efficiency_score', models.FloatField(blank=True, help_text='Efficiency score on 0-10 scale', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(10.0)])),
                ('quality_score', models.FloatField(blank=True, help_text='Quality score on 0-10 scale', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(10.0)])),
                ('items_processed', models.IntegerField(blank=True, help_text='Number of items or tasks processed', null=True)),
                ('is_bookmarked', models.BooleanField(default=False, help_text='Whether entry is bookmarked by user')),
                ('is_draft', models.BooleanField(default=False, help_text='Whether entry is still a draft')),
                ('is_deleted', models.BooleanField(default=False, help_text='Soft delete flag')),
                ('sync_status', models.CharField(choices=[('draft', 'Draft'), ('pending_sync', 'Pending Sync'), ('synced', 'Synced'), ('sync_error', 'Sync Error'), ('pending_delete', 'Pending Delete')], default='synced', help_text='Current sync status with mobile clients', max_length=20)),
                ('mobile_id', models.UUIDField(blank=True, help_text='Client-generated ID for sync conflict resolution', null=True)),
                ('version', models.IntegerField(default=1, help_text='Version number for conflict resolution')),
                ('last_sync_timestamp', models.DateTimeField(blank=True, help_text='Last successful sync with mobile client', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('metadata', models.JSONField(default=dict, help_text='Flexible additional data and context')),
                ('user', models.ForeignKey(help_text='Owner of this journal entry', on_delete=django.db.models.deletion.CASCADE, related_name='journal_entries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Journal Entry',
                'verbose_name_plural': 'Journal Entries',
                'ordering': ['-timestamp', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='JournalMediaAttachment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('media_type', models.CharField(choices=[('PHOTO', 'Photo'), ('VIDEO', 'Video'), ('DOCUMENT', 'Document'), ('AUDIO', 'Audio')], help_text='Type of media attachment', max_length=20)),
                ('file', models.FileField(help_text='Media file upload', upload_to='journal_media/%Y/%m/%d/')),
                ('original_filename', models.CharField(help_text='Original filename from client', max_length=255)),
                ('mime_type', models.CharField(help_text='MIME type of the file', max_length=100)),
                ('file_size', models.BigIntegerField(help_text='File size in bytes')),
                ('caption', models.TextField(blank=True, help_text='Optional caption for the media')),
                ('display_order', models.IntegerField(default=0, help_text='Order for displaying multiple media items')),
                ('is_hero_image', models.BooleanField(default=False, help_text='Whether this is the main/hero image for the entry')),
                ('mobile_id', models.UUIDField(blank=True, help_text='Client-generated ID for sync', null=True)),
                ('sync_status', models.CharField(choices=[('draft', 'Draft'), ('pending_sync', 'Pending Sync'), ('synced', 'Synced'), ('sync_error', 'Sync Error'), ('pending_delete', 'Pending Delete')], default='synced', help_text='Sync status with mobile clients', max_length=20)),
                ('is_deleted', models.BooleanField(default=False, help_text='Soft delete flag')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('journal_entry', models.ForeignKey(help_text='Associated journal entry', on_delete=django.db.models.deletion.CASCADE, related_name='media_attachments', to='journal.journalentry')),
            ],
            options={
                'verbose_name': 'Journal Media Attachment',
                'verbose_name_plural': 'Journal Media Attachments',
                'ordering': ['display_order', '-created_at'],
            },
        ),
        # Database indexes for optimal performance
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_entry_user_timestamp_idx ON journal_journalentry (user_id, timestamp DESC);",
            reverse_sql="DROP INDEX IF EXISTS journal_entry_user_timestamp_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_entry_type_user_idx ON journal_journalentry (entry_type, user_id);",
            reverse_sql="DROP INDEX IF EXISTS journal_entry_type_user_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_privacy_scope_user_idx ON journal_journalentry (privacy_scope, user_id);",
            reverse_sql="DROP INDEX IF EXISTS journal_privacy_scope_user_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_mood_timestamp_idx ON journal_journalentry (mood_rating, timestamp DESC);",
            reverse_sql="DROP INDEX IF EXISTS journal_mood_timestamp_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_stress_timestamp_idx ON journal_journalentry (stress_level, timestamp DESC);",
            reverse_sql="DROP INDEX IF EXISTS journal_stress_timestamp_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_sync_mobile_idx ON journal_journalentry (sync_status, mobile_id);",
            reverse_sql="DROP INDEX IF EXISTS journal_sync_mobile_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_deleted_draft_idx ON journal_journalentry (is_deleted, is_draft);",
            reverse_sql="DROP INDEX IF EXISTS journal_deleted_draft_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_tenant_timestamp_idx ON journal_journalentry (tenant_id, timestamp DESC);",
            reverse_sql="DROP INDEX IF EXISTS journal_tenant_timestamp_idx;"
        ),
        # GIN indexes for JSON fields (PostgreSQL specific)
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_tags_gin_idx ON journal_journalentry USING GIN (tags);",
            reverse_sql="DROP INDEX IF EXISTS journal_tags_gin_idx;"
        ),
        # Media attachment indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_media_entry_order_idx ON journal_journalmediaattachment (journal_entry_id, display_order);",
            reverse_sql="DROP INDEX IF EXISTS journal_media_entry_order_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_media_type_idx ON journal_journalmediaattachment (media_type);",
            reverse_sql="DROP INDEX IF EXISTS journal_media_type_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_media_sync_idx ON journal_journalmediaattachment (sync_status);",
            reverse_sql="DROP INDEX IF EXISTS journal_media_sync_idx;"
        ),
        # Add check constraints
        migrations.AddConstraint(
            model_name='journalentry',
            constraint=models.CheckConstraint(
                check=models.Q(models.Q(('mood_rating__gte', 1), ('mood_rating__lte', 10)), models.Q(('mood_rating__isnull', True)), _connector='OR'),
                name='valid_mood_rating_range'
            ),
        ),
        migrations.AddConstraint(
            model_name='journalentry',
            constraint=models.CheckConstraint(
                check=models.Q(models.Q(('stress_level__gte', 1), ('stress_level__lte', 5)), models.Q(('stress_level__isnull', True)), _connector='OR'),
                name='valid_stress_level_range'
            ),
        ),
        migrations.AddConstraint(
            model_name='journalentry',
            constraint=models.CheckConstraint(
                check=models.Q(models.Q(('energy_level__gte', 1), ('energy_level__lte', 10)), models.Q(('energy_level__isnull', True)), _connector='OR'),
                name='valid_energy_level_range'
            ),
        ),
        migrations.AddConstraint(
            model_name='journalentry',
            constraint=models.CheckConstraint(
                check=models.Q(models.Q(('completion_rate__gte', 0.0), ('completion_rate__lte', 1.0)), models.Q(('completion_rate__isnull', True)), _connector='OR'),
                name='valid_completion_rate_range'
            ),
        ),
    ]

    atomic = False  # Required for CONCURRENTLY operations