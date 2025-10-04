"""
Add JSON fields for structured options and alert configuration.

This migration adds new JSONFields alongside existing text fields for a phased migration:

Phase 1 (This migration): Add nullable JSON fields
Phase 2 (Next migration): Populate JSON fields from existing text data
Phase 3 (Future): Dual-write to both fields
Phase 4 (Future): Deprecate text fields
Phase 5 (Future): Remove text fields

Benefits of JSON fields:
- Structured validation (Pydantic schemas)
- Easier parsing in mobile apps (no CSV splitting)
- Type-safe alert configuration (no string parsing like "<10, >90")
- Better GraphQL schema representation

Android Impact: BACKWARD COMPATIBLE
- Old fields (options, alerton) remain unchanged
- New fields (options_json, alert_config) are optional
- Mobile app can migrate gradually over 2 release cycles

Created: 2025-10-03
Following .claude/rules.md Rule #12: Database query optimization
"""

from django.db import migrations, models
from django.core.serializers.json import DjangoJSONEncoder


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0018_add_question_performance_indexes'),
    ]

    operations = [
        # Question model - add JSON fields
        migrations.AddField(
            model_name='question',
            name='options_json',
            field=models.JSONField(
                verbose_name='Options (JSON)',
                encoder=DjangoJSONEncoder,
                null=True,
                blank=True,
                help_text='Structured options array. Replaces text "options" field. Format: ["Option1", "Option2", "Option3"]'
            ),
        ),
        migrations.AddField(
            model_name='question',
            name='alert_config',
            field=models.JSONField(
                verbose_name='Alert Configuration',
                encoder=DjangoJSONEncoder,
                null=True,
                blank=True,
                help_text='Structured alert configuration. Replaces text "alerton" field. Format: {"numeric": {"below": 10.5, "above": 90.0}, "choice": ["Alert1"], "enabled": true}'
            ),
        ),

        # QuestionSetBelonging model - add JSON fields
        migrations.AddField(
            model_name='questionsetbelonging',
            name='options_json',
            field=models.JSONField(
                verbose_name='Options (JSON)',
                encoder=DjangoJSONEncoder,
                null=True,
                blank=True,
                help_text='Structured options array. Replaces text "options" field. Format: ["Option1", "Option2", "Option3"]'
            ),
        ),
        migrations.AddField(
            model_name='questionsetbelonging',
            name='alert_config',
            field=models.JSONField(
                verbose_name='Alert Configuration',
                encoder=DjangoJSONEncoder,
                null=True,
                blank=True,
                help_text='Structured alert configuration. Replaces text "alerton" field. Format: {"numeric": {"below": 10.5, "above": 90.0}, "choice": ["Alert1"], "enabled": true}'
            ),
        ),

        # Add indexes for JSON field queries (PostgreSQL GIN indexes)
        migrations.RunSQL(
            sql="""
                -- Index for options_json queries on Question
                CREATE INDEX IF NOT EXISTS question_options_json_gin_idx
                ON question USING GIN (options_json);

                -- Index for alert_config queries on Question
                CREATE INDEX IF NOT EXISTS question_alert_config_gin_idx
                ON question USING GIN (alert_config);

                -- Index for options_json queries on QuestionSetBelonging
                CREATE INDEX IF NOT EXISTS qsb_options_json_gin_idx
                ON questionsetbelonging USING GIN (options_json);

                -- Index for alert_config queries on QuestionSetBelonging
                CREATE INDEX IF NOT EXISTS qsb_alert_config_gin_idx
                ON questionsetbelonging USING GIN (alert_config);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS question_options_json_gin_idx;
                DROP INDEX IF EXISTS question_alert_config_gin_idx;
                DROP INDEX IF EXISTS qsb_options_json_gin_idx;
                DROP INDEX IF EXISTS qsb_alert_config_gin_idx;
            """,
        ),

        # Add helpful comments to old fields
        migrations.AlterField(
            model_name='question',
            name='options',
            field=models.TextField(
                verbose_name='Options (Text - DEPRECATED)',
                max_length=2000,
                null=True,
                help_text='DEPRECATED: Use options_json instead. This field will be removed in future release.'
            ),
        ),
        migrations.AlterField(
            model_name='question',
            name='alerton',
            field=models.CharField(
                verbose_name='Alert On (Text - DEPRECATED)',
                max_length=300,
                null=True,
                help_text='DEPRECATED: Use alert_config instead. This field will be removed in future release.'
            ),
        ),
        migrations.AlterField(
            model_name='questionsetbelonging',
            name='options',
            field=models.CharField(
                verbose_name='Options (Text - DEPRECATED)',
                max_length=2000,
                null=True,
                blank=True,
                help_text='DEPRECATED: Use options_json instead. This field will be removed in future release.'
            ),
        ),
        migrations.AlterField(
            model_name='questionsetbelonging',
            name='alerton',
            field=models.CharField(
                verbose_name='Alert On (Text - DEPRECATED)',
                max_length=300,
                null=True,
                blank=True,
                help_text='DEPRECATED: Use alert_config instead. This field will be removed in future release.'
            ),
        ),
    ]
