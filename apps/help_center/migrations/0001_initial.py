"""
Initial migration for help_center app.

Creates 6 models with full-text search and pgvector support:
- HelpTag: Simple tagging
- HelpCategory: Hierarchical categorization
- HelpArticle: Knowledge base with FTS + semantic search
- HelpSearchHistory: Search analytics
- HelpArticleInteraction: User engagement tracking
- HelpTicketCorrelation: Ticket integration

Dependencies:
- Enable pgvector extension
- Create FTS trigger for automatic search_vector updates
- Create indexes (GIN for FTS, composite for queries)

Following CLAUDE.md security standards:
- Tenant isolation via foreign keys
- Proper index strategy
- Audit fields (created_at, updated_at)
"""

from django.db import migrations, models
import django.contrib.postgres.search
import django.contrib.postgres.indexes
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('peoples', '0001_initial'),  # Adjust to actual latest migration
        ('y_helpdesk', '0001_initial'),  # Adjust to actual latest migration
        ('tenants', '0001_initial'),  # Adjust to actual latest migration
    ]

    operations = [
        # Enable pgvector extension (idempotent)
        migrations.RunSQL(
            sql='CREATE EXTENSION IF NOT EXISTS vector;',
            reverse_sql='DROP EXTENSION IF EXISTS vector;'
        ),

        # HelpTag model
        migrations.CreateModel(
            name='HelpTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=50)),
                ('slug', models.SlugField(max_length=60, unique=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'db_table': 'help_center_tag',
                'ordering': ['name'],
                'unique_together': {('tenant', 'slug')},
            },
        ),

        # HelpCategory model
        migrations.CreateModel(
            name='HelpCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('icon', models.CharField(blank=True, help_text="Icon class (e.g., 'fa-wrench', 'material-icons:build')", max_length=50)),
                ('color', models.CharField(default='#1976d2', help_text='Hex color code for category badge', max_length=7)),
                ('display_order', models.IntegerField(db_index=True, default=0)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='help_center.helpcategory')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'db_table': 'help_center_category',
                'ordering': ['display_order', 'name'],
                'verbose_name_plural': 'Help Categories',
                'unique_together': {('tenant', 'slug')},
            },
        ),

        # HelpArticle model
        migrations.CreateModel(
            name='HelpArticle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(db_index=True, max_length=200)),
                ('slug', models.SlugField(max_length=250)),
                ('summary', models.TextField(max_length=500)),
                ('content', models.TextField()),
                ('difficulty_level', models.CharField(choices=[('BEGINNER', 'Beginner'), ('INTERMEDIATE', 'Intermediate'), ('ADVANCED', 'Advanced')], db_index=True, default='BEGINNER', max_length=20)),
                ('target_roles', models.JSONField(default=list, help_text='List of permission group names that can view this article')),
                ('search_vector', django.contrib.postgres.search.SearchVectorField(editable=False, null=True)),
                ('embedding', models.JSONField(blank=True, help_text='384-dim embedding for semantic search (pgvector)', null=True)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('REVIEW', 'Under Review'), ('PUBLISHED', 'Published'), ('ARCHIVED', 'Archived')], db_index=True, default='DRAFT', max_length=20)),
                ('version', models.IntegerField(default=1)),
                ('view_count', models.IntegerField(db_index=True, default=0)),
                ('helpful_count', models.IntegerField(default=0)),
                ('not_helpful_count', models.IntegerField(default=0)),
                ('published_date', models.DateTimeField(blank=True, null=True)),
                ('last_reviewed_date', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='articles', to='help_center.helpcategory')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='help_articles_created', to='peoples.people')),
                ('last_updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='help_articles_updated', to='peoples.people')),
                ('previous_version', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='next_versions', to='help_center.helparticle')),
                ('tags', models.ManyToManyField(blank=True, to='help_center.helptag')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'db_table': 'help_center_article',
                'ordering': ['-published_date', '-created_at'],
                'unique_together': {('tenant', 'slug')},
            },
        ),

        # HelpSearchHistory model
        migrations.CreateModel(
            name='HelpSearchHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(db_index=True, max_length=500)),
                ('results_count', models.IntegerField(db_index=True, default=0)),
                ('click_position', models.IntegerField(blank=True, help_text='Position of clicked result (1-based)', null=True)),
                ('session_id', models.UUIDField(blank=True, db_index=True, help_text='Link to HelpArticleInteraction.session_id', null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('clicked_article', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='search_clicks', to='help_center.helparticle')),
                ('refinement_of', models.ForeignKey(blank=True, help_text='If this is a refined search, link to original', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='refinements', to='help_center.helpsearchhistory')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='help_searches', to='peoples.people')),
            ],
            options={
                'db_table': 'help_center_search_history',
                'ordering': ['-timestamp'],
            },
        ),

        # HelpArticleInteraction model
        migrations.CreateModel(
            name='HelpArticleInteraction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('interaction_type', models.CharField(choices=[('VIEW', 'Viewed'), ('BOOKMARK', 'Bookmarked'), ('SHARE', 'Shared'), ('VOTE_HELPFUL', 'Voted Helpful'), ('VOTE_NOT_HELPFUL', 'Voted Not Helpful'), ('FEEDBACK_INCORRECT', 'Reported Incorrect'), ('FEEDBACK_OUTDATED', 'Reported Outdated')], db_index=True, max_length=20)),
                ('time_spent_seconds', models.IntegerField(blank=True, help_text='Time spent reading article (seconds)', null=True)),
                ('scroll_depth_percent', models.IntegerField(blank=True, help_text='How far user scrolled (0-100%)', null=True)),
                ('feedback_comment', models.TextField(blank=True, help_text='Optional comment for votes/feedback')),
                ('session_id', models.UUIDField(db_index=True)),
                ('referrer_url', models.CharField(blank=True, help_text='Page user was on when accessing help', max_length=500)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='interactions', to='help_center.helparticle')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='help_interactions', to='peoples.people')),
            ],
            options={
                'db_table': 'help_center_interaction',
                'ordering': ['-timestamp'],
            },
        ),

        # HelpTicketCorrelation model
        migrations.CreateModel(
            name='HelpTicketCorrelation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('help_attempted', models.BooleanField(db_index=True, default=False, help_text='Did user view any help articles before creating ticket?')),
                ('help_session_id', models.UUIDField(blank=True, help_text='Link to help session if help was attempted', null=True)),
                ('search_queries', models.JSONField(default=list, help_text='List of search queries attempted before ticket creation')),
                ('relevant_article_exists', models.BooleanField(blank=True, help_text='Based on ticket analysis, does relevant help content exist?', null=True)),
                ('content_gap', models.BooleanField(db_index=True, default=False, help_text='Should content team create new article for this topic?')),
                ('resolution_time_minutes', models.IntegerField(blank=True, help_text='Time from ticket creation to resolution (minutes)', null=True)),
                ('analyzed_at', models.DateTimeField(blank=True, help_text='When correlation analysis was performed', null=True)),
                ('articles_viewed', models.ManyToManyField(blank=True, related_name='ticket_correlations', to='help_center.helparticle')),
                ('suggested_article', models.ForeignKey(blank=True, help_text='Article to show in ticket view', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='suggested_for_tickets', to='help_center.helparticle')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('ticket', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='help_correlation', to='y_helpdesk.ticket')),
            ],
            options={
                'db_table': 'help_center_ticket_correlation',
            },
        ),

        # Add indexes for HelpArticle
        migrations.AddIndex(
            model_name='helparticle',
            index=django.contrib.postgres.indexes.GinIndex(fields=['search_vector'], name='help_article_search_idx'),
        ),
        migrations.AddIndex(
            model_name='helparticle',
            index=models.Index(fields=['status', 'published_date'], name='help_article_published_idx'),
        ),
        migrations.AddIndex(
            model_name='helparticle',
            index=models.Index(fields=['category', 'status'], name='help_article_category_idx'),
        ),
        migrations.AddIndex(
            model_name='helparticle',
            index=models.Index(fields=['view_count'], name='help_article_popularity_idx'),
        ),

        # Add indexes for HelpSearchHistory
        migrations.AddIndex(
            model_name='helpsearchhistory',
            index=models.Index(fields=['query', 'results_count'], name='help_search_zero_idx'),
        ),
        migrations.AddIndex(
            model_name='helpsearchhistory',
            index=models.Index(fields=['user', 'timestamp'], name='help_search_user_idx'),
        ),

        # Add indexes for HelpArticleInteraction
        migrations.AddIndex(
            model_name='helparticleinteraction',
            index=models.Index(fields=['article', 'interaction_type'], name='help_interaction_type_idx'),
        ),
        migrations.AddIndex(
            model_name='helparticleinteraction',
            index=models.Index(fields=['user', 'timestamp'], name='help_interaction_user_idx'),
        ),
        migrations.AddIndex(
            model_name='helparticleinteraction',
            index=models.Index(fields=['session_id'], name='help_interaction_session_idx'),
        ),

        # Add indexes for HelpTicketCorrelation
        migrations.AddIndex(
            model_name='helpticketcorrelation',
            index=models.Index(fields=['help_attempted', 'content_gap'], name='help_ticket_gap_idx'),
        ),
        migrations.AddIndex(
            model_name='helpticketcorrelation',
            index=models.Index(fields=['ticket'], name='help_ticket_correlation_idx'),
        ),

        # Create trigger for automatic search_vector updates
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION help_article_search_update_trigger()
                RETURNS trigger AS $$
                BEGIN
                    NEW.search_vector :=
                        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                        setweight(to_tsvector('english', COALESCE(NEW.summary, '')), 'B') ||
                        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'C');
                    RETURN NEW;
                END
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER help_article_search_update
                BEFORE INSERT OR UPDATE ON help_center_article
                FOR EACH ROW EXECUTE FUNCTION help_article_search_update_trigger();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS help_article_search_update ON help_center_article;
                DROP FUNCTION IF EXISTS help_article_search_update_trigger();
            """
        ),
    ]
