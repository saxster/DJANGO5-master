# Generated migration for adding performance indexes to activity models

from django.db import migrations



class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0007_add_performance_indexes'),
    ]

    operations = [
        # Question model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_question_answertype_unit ON question (answertype, unit_id) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_question_answertype_unit;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_question_workflow ON question (isworkflow) WHERE enable = true AND isworkflow = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_question_workflow;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_question_search ON question (quesname, answertype) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_question_search;"
        ),

        # QuestionSet model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_questionset_type_bu ON questionset (type, bu_id) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_questionset_type_bu;"
        ),
        # Note: Removed WHERE clause with CURRENT_TIMESTAMP because it's not IMMUTABLE
        # Full index on mdtz is acceptable - recently modified records will be at end of B-tree
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_questionset_modified_recent ON questionset (mdtz DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_questionset_modified_recent;"
        ),

        # QuestionSetBelonging model indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_qsetbelonging_qset_question ON questionsetbelonging (qset_id, question_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_qsetbelonging_qset_question;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_qsetbelonging_mandatory ON questionsetbelonging (qset_id, ismandatory, seqno) WHERE ismandatory = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_qsetbelonging_mandatory;"
        ),
        # Note: Removed idx_qsetbelonging_workflow - isworkflow column doesn't exist in QuestionSetBelonging model

        # Asset model indexes (for checkpoints)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_asset_identifier_location ON asset (identifier, location_id) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_asset_identifier_location;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_asset_parent_status ON asset (parent_id, runningstatus) WHERE enable = true AND parent_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_asset_parent_status;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_asset_checkpoint ON asset (identifier) WHERE identifier = 'CHECKPOINT' AND enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_asset_checkpoint;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_asset_search ON asset (assetname, assetcode) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_asset_search;"
        ),

        # Location model indexes (if applicable)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_location_parent_active ON location (parent_id) WHERE enable = true AND parent_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_location_parent_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_location_hierarchy ON location (bu_id, parent_id) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_location_hierarchy;"
        ),

        # Note: Removed idx_question_extras_gin - question_extras column doesn't exist in Question model

        # Composite indexes for common query patterns
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_question_unit_type_active ON question (unit_id, answertype, enable) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_question_unit_type_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_asset_location_type_status ON asset (location_id, type_id, runningstatus) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_asset_location_type_status;"
        ),
    ]