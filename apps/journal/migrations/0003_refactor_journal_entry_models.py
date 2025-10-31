# Generated migration for journal model refactoring

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import uuid


def migrate_journal_data_to_new_models(apps, schema_editor):
    """
    Migrate existing journal entry data to the new refactored models

    This function safely moves data from the original JournalEntry fields
    to the new separate models while maintaining data integrity.
    """
    JournalEntry = apps.get_model('journal', 'JournalEntry')
    JournalWellbeingMetrics = apps.get_model('journal', 'JournalWellbeingMetrics')
    JournalWorkContext = apps.get_model('journal', 'JournalWorkContext')
    JournalSyncData = apps.get_model('journal', 'JournalSyncData')

    print("Starting journal data migration to refactored models...")

    for entry in JournalEntry.objects.all():
        # Migrate wellbeing metrics
        wellbeing_data = {
            'mood_rating': getattr(entry, 'mood_rating', None),
            'mood_description': getattr(entry, 'mood_description', ''),
            'stress_level': getattr(entry, 'stress_level', None),
            'energy_level': getattr(entry, 'energy_level', None),
            'stress_triggers': getattr(entry, 'stress_triggers', []),
            'coping_strategies': getattr(entry, 'coping_strategies', []),
            'gratitude_items': getattr(entry, 'gratitude_items', []),
            'daily_goals': getattr(entry, 'daily_goals', []),
            'affirmations': getattr(entry, 'affirmations', []),
            'achievements': getattr(entry, 'achievements', []),
            'learnings': getattr(entry, 'learnings', []),
            'challenges': getattr(entry, 'challenges', []),
        }

        # Only create wellbeing metrics if there's actual data
        if any(wellbeing_data.values()):
            wellbeing_metrics = JournalWellbeingMetrics.objects.create(**wellbeing_data)
            entry.wellbeing_metrics = wellbeing_metrics

        # Migrate work context
        work_data = {
            'location_site_name': getattr(entry, 'location_site_name', ''),
            'location_address': getattr(entry, 'location_address', ''),
            'location_coordinates': getattr(entry, 'location_coordinates', None),
            'location_area_type': getattr(entry, 'location_area_type', ''),
            'team_members': getattr(entry, 'team_members', []),
            'completion_rate': getattr(entry, 'completion_rate', None),
            'efficiency_score': getattr(entry, 'efficiency_score', None),
            'quality_score': getattr(entry, 'quality_score', None),
            'items_processed': getattr(entry, 'items_processed', None),
            'tags': getattr(entry, 'tags', []),
            'priority': getattr(entry, 'priority', ''),
            'severity': getattr(entry, 'severity', ''),
            'duration_minutes': getattr(entry, 'duration_minutes', None),
        }

        # Only create work context if there's actual data
        if any(work_data.values()):
            work_context = JournalWorkContext.objects.create(**work_data)
            entry.work_context = work_context

        # Migrate sync data
        sync_data_obj = JournalSyncData.objects.create(
            sync_status=getattr(entry, 'sync_status', 'synced'),
            mobile_id=getattr(entry, 'mobile_id', None),
            version=getattr(entry, 'version', 1),
            last_sync_timestamp=getattr(entry, 'last_sync_timestamp', None),
            is_draft=getattr(entry, 'is_draft', False),
            is_deleted=getattr(entry, 'is_deleted', False),
            is_bookmarked=getattr(entry, 'is_bookmarked', False),
        )
        entry.sync_data = sync_data_obj

        entry.save()

    print(f"Successfully migrated {JournalEntry.objects.count()} journal entries")


def migrate_data_back_to_original_model(apps, schema_editor):
    """
    Reverse migration: Move data back from new models to original JournalEntry fields

    This function safely restores data from the separate models back to the original
    JournalEntry model in case the migration needs to be reversed.
    """
    JournalEntry = apps.get_model('journal', 'JournalEntry')

    print("Reversing journal data migration...")

    for entry in JournalEntry.objects.all():
        # Restore wellbeing metrics
        if entry.wellbeing_metrics:
            metrics = entry.wellbeing_metrics
            entry.mood_rating = metrics.mood_rating
            entry.mood_description = metrics.mood_description
            entry.stress_level = metrics.stress_level
            entry.energy_level = metrics.energy_level
            entry.stress_triggers = metrics.stress_triggers
            entry.coping_strategies = metrics.coping_strategies
            entry.gratitude_items = metrics.gratitude_items
            entry.daily_goals = metrics.daily_goals
            entry.affirmations = metrics.affirmations
            entry.achievements = metrics.achievements
            entry.learnings = metrics.learnings
            entry.challenges = metrics.challenges

        # Restore work context
        if entry.work_context:
            context = entry.work_context
            entry.location_site_name = context.location_site_name
            entry.location_address = context.location_address
            entry.location_coordinates = context.location_coordinates
            entry.location_area_type = context.location_area_type
            entry.team_members = context.team_members
            entry.completion_rate = context.completion_rate
            entry.efficiency_score = context.efficiency_score
            entry.quality_score = context.quality_score
            entry.items_processed = context.items_processed
            entry.tags = context.tags
            entry.priority = context.priority
            entry.severity = context.severity
            entry.duration_minutes = context.duration_minutes

        # Restore sync data
        if entry.sync_data:
            sync_data = entry.sync_data
            entry.sync_status = sync_data.sync_status
            entry.mobile_id = sync_data.mobile_id
            entry.version = sync_data.version
            entry.last_sync_timestamp = sync_data.last_sync_timestamp
            entry.is_draft = sync_data.is_draft
            entry.is_deleted = sync_data.is_deleted
            entry.is_bookmarked = sync_data.is_bookmarked

        entry.save()

    print(f"Successfully restored {JournalEntry.objects.count()} journal entries")


class Migration(migrations.Migration):

    dependencies = [
        ('journal', '0002_add_mobile_sync_fields'),
    ]

    atomic = False  # Required for CREATE INDEX CONCURRENTLY

    operations = [
        # Create JournalWellbeingMetrics model
        migrations.CreateModel(
            name='JournalWellbeingMetrics',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
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
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Journal Wellbeing Metrics',
                'verbose_name_plural': 'Journal Wellbeing Metrics',
            },
        ),

        # Create JournalWorkContext model
        migrations.CreateModel(
            name='JournalWorkContext',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('location_site_name', models.CharField(blank=True, help_text='Name of work site or location', max_length=200)),
                ('location_address', models.TextField(blank=True, help_text='Full address of location')),
                ('location_coordinates', models.JSONField(blank=True, help_text='GPS coordinates as {"lat": 0.0, "lng": 0.0}', null=True)),
                ('location_area_type', models.CharField(blank=True, help_text='Type of work area (office, field, client site, etc.)', max_length=100)),
                ('team_members', models.JSONField(default=list, help_text='List of team members involved')),
                ('completion_rate', models.FloatField(blank=True, help_text='Completion rate as decimal (0.0 to 1.0)', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('efficiency_score', models.FloatField(blank=True, help_text='Efficiency score on 0-10 scale', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(10.0)])),
                ('quality_score', models.FloatField(blank=True, help_text='Quality score on 0-10 scale', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(10.0)])),
                ('items_processed', models.IntegerField(blank=True, help_text='Number of items or tasks processed', null=True)),
                ('tags', models.JSONField(default=list, help_text='List of tags for categorization and search')),
                ('priority', models.CharField(blank=True, help_text='Priority level (low, medium, high, urgent)', max_length=20)),
                ('severity', models.CharField(blank=True, help_text='Severity level for issues or concerns', max_length=20)),
                ('duration_minutes', models.IntegerField(blank=True, help_text='Duration of activity in minutes', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Journal Work Context',
                'verbose_name_plural': 'Journal Work Contexts',
            },
        ),

        # Create JournalSyncData model
        migrations.CreateModel(
            name='JournalSyncData',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('sync_status', models.CharField(choices=[('draft', 'Draft'), ('pending_sync', 'Pending Sync'), ('synced', 'Synced'), ('sync_error', 'Sync Error'), ('pending_delete', 'Pending Delete')], default='synced', help_text='Current sync status with mobile clients', max_length=20)),
                ('mobile_id', models.UUIDField(blank=True, help_text='Client-generated ID for sync conflict resolution', null=True)),
                ('version', models.IntegerField(default=1, help_text='Version number for conflict resolution')),
                ('last_sync_timestamp', models.DateTimeField(blank=True, help_text='Last successful sync with mobile client', null=True)),
                ('is_draft', models.BooleanField(default=False, help_text='Whether entry is still a draft')),
                ('is_deleted', models.BooleanField(default=False, help_text='Soft delete flag')),
                ('is_bookmarked', models.BooleanField(default=False, help_text='Whether entry is bookmarked by user')),
                ('sync_metadata', models.JSONField(default=dict, help_text='Additional sync-related metadata')),
                ('client_device_id', models.CharField(blank=True, help_text='Device identifier from mobile client', max_length=255)),
                ('client_app_version', models.CharField(blank=True, help_text='Mobile app version that created/updated this entry', max_length=50)),
                ('has_conflicts', models.BooleanField(default=False, help_text='Whether this entry has unresolved sync conflicts')),
                ('conflict_data', models.JSONField(blank=True, help_text='Data from conflicting versions for manual resolution', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Journal Sync Data',
                'verbose_name_plural': 'Journal Sync Data',
            },
        ),

        # Add database indexes for the new models
        migrations.RunSQL(
            sql=[
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_wellbeingmetrics_mood_rating_idx ON journal_journalwellbeingmetrics (mood_rating);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_wellbeingmetrics_stress_level_idx ON journal_journalwellbeingmetrics (stress_level);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_wellbeingmetrics_energy_level_idx ON journal_journalwellbeingmetrics (energy_level);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_wellbeingmetrics_created_at_idx ON journal_journalwellbeingmetrics (created_at);",

                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_workcontext_location_site_name_idx ON journal_journalworkcontext (location_site_name);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_workcontext_priority_idx ON journal_journalworkcontext (priority);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_workcontext_severity_idx ON journal_journalworkcontext (severity);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_workcontext_completion_rate_idx ON journal_journalworkcontext (completion_rate);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_workcontext_created_at_idx ON journal_journalworkcontext (created_at);",

                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_syncdata_sync_status_idx ON journal_journalsyncdata (sync_status);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_syncdata_mobile_id_idx ON journal_journalsyncdata (mobile_id);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_syncdata_version_idx ON journal_journalsyncdata (version);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_syncdata_last_sync_timestamp_idx ON journal_journalsyncdata (last_sync_timestamp);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_syncdata_is_draft_idx ON journal_journalsyncdata (is_draft);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_syncdata_is_deleted_idx ON journal_journalsyncdata (is_deleted);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_syncdata_has_conflicts_idx ON journal_journalsyncdata (has_conflicts);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_syncdata_client_device_id_idx ON journal_journalsyncdata (client_device_id);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_syncdata_created_at_idx ON journal_journalsyncdata (created_at);",
            ],
            reverse_sql=[
                "DROP INDEX CONCURRENTLY IF EXISTS journal_wellbeingmetrics_mood_rating_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_wellbeingmetrics_stress_level_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_wellbeingmetrics_energy_level_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_wellbeingmetrics_created_at_idx;",

                "DROP INDEX CONCURRENTLY IF EXISTS journal_workcontext_location_site_name_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_workcontext_priority_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_workcontext_severity_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_workcontext_completion_rate_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_workcontext_created_at_idx;",

                "DROP INDEX CONCURRENTLY IF EXISTS journal_syncdata_sync_status_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_syncdata_mobile_id_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_syncdata_version_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_syncdata_last_sync_timestamp_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_syncdata_is_draft_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_syncdata_is_deleted_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_syncdata_has_conflicts_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_syncdata_client_device_id_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_syncdata_created_at_idx;",
            ],
        ),

        # Add constraints
        migrations.RunSQL(
            sql=[
                "ALTER TABLE journal_journalwellbeingmetrics ADD CONSTRAINT valid_mood_rating_range CHECK (mood_rating IS NULL OR (mood_rating >= 1 AND mood_rating <= 10));",
                "ALTER TABLE journal_journalwellbeingmetrics ADD CONSTRAINT valid_stress_level_range CHECK (stress_level IS NULL OR (stress_level >= 1 AND stress_level <= 5));",
                "ALTER TABLE journal_journalwellbeingmetrics ADD CONSTRAINT valid_energy_level_range CHECK (energy_level IS NULL OR (energy_level >= 1 AND energy_level <= 10));",

                "ALTER TABLE journal_journalworkcontext ADD CONSTRAINT valid_completion_rate_range CHECK (completion_rate IS NULL OR (completion_rate >= 0.0 AND completion_rate <= 1.0));",
                "ALTER TABLE journal_journalworkcontext ADD CONSTRAINT valid_efficiency_score_range CHECK (efficiency_score IS NULL OR (efficiency_score >= 0.0 AND efficiency_score <= 10.0));",
                "ALTER TABLE journal_journalworkcontext ADD CONSTRAINT valid_quality_score_range CHECK (quality_score IS NULL OR (quality_score >= 0.0 AND quality_score <= 10.0));",
            ],
            reverse_sql=[
                "ALTER TABLE journal_journalwellbeingmetrics DROP CONSTRAINT IF EXISTS valid_mood_rating_range;",
                "ALTER TABLE journal_journalwellbeingmetrics DROP CONSTRAINT IF EXISTS valid_stress_level_range;",
                "ALTER TABLE journal_journalwellbeingmetrics DROP CONSTRAINT IF EXISTS valid_energy_level_range;",

                "ALTER TABLE journal_journalworkcontext DROP CONSTRAINT IF EXISTS valid_completion_rate_range;",
                "ALTER TABLE journal_journalworkcontext DROP CONSTRAINT IF EXISTS valid_efficiency_score_range;",
                "ALTER TABLE journal_journalworkcontext DROP CONSTRAINT IF EXISTS valid_quality_score_range;",
            ],
        ),

        # Create GIN indexes for JSON fields (PostgreSQL specific)
        migrations.RunSQL(
            sql=[
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_wellbeingmetrics_stress_triggers_gin_idx ON journal_journalwellbeingmetrics USING gin (stress_triggers);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_wellbeingmetrics_gratitude_items_gin_idx ON journal_journalwellbeingmetrics USING gin (gratitude_items);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_workcontext_tags_gin_idx ON journal_journalworkcontext USING gin (tags);",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS journal_workcontext_team_members_gin_idx ON journal_journalworkcontext USING gin (team_members);",
            ],
            reverse_sql=[
                "DROP INDEX CONCURRENTLY IF EXISTS journal_wellbeingmetrics_stress_triggers_gin_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_wellbeingmetrics_gratitude_items_gin_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_workcontext_tags_gin_idx;",
                "DROP INDEX CONCURRENTLY IF EXISTS journal_workcontext_team_members_gin_idx;",
            ],
        ),

        # Add one-to-one relationships to existing JournalEntry model
        migrations.AddField(
            model_name='journalentry',
            name='wellbeing_metrics',
            field=models.OneToOneField(blank=True, help_text='Wellbeing metrics (mood, stress, energy, positive psychology)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='journal_entry', to='journal.journalwellbeingmetrics'),
        ),
        migrations.AddField(
            model_name='journalentry',
            name='work_context',
            field=models.OneToOneField(blank=True, help_text='Work context (location, team, performance metrics)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='journal_entry', to='journal.journalworkcontext'),
        ),
        migrations.AddField(
            model_name='journalentry',
            name='sync_data',
            field=models.OneToOneField(blank=True, help_text='Mobile sync and versioning data', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='journal_entry', to='journal.journalsyncdata'),
        ),

        # Data migration: Move existing data to new models
        migrations.RunPython(
            code=migrate_journal_data_to_new_models,
            reverse_code=migrate_data_back_to_original_model,
        ),

        # Remove old fields from JournalEntry model (done in separate migration for safety)
        # migrations.RemoveField(model_name='journalentry', name='mood_rating'),
        # migrations.RemoveField(model_name='journalentry', name='stress_level'),
        # ... (other fields to be removed in a follow-up migration)
    ]
