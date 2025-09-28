"""
Add unique constraint to ensure only one primary embedding per user per model type
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('face_recognition', '0002_auto_20250101_0000'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Ensure only one primary embedding per user per extraction model
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_one_primary_per_user_model
                ON face_embedding (user_id, extraction_model_id)
                WHERE is_primary = TRUE;
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_one_primary_per_user_model;
            """,
            state_operations=[
                # This helps Django understand the constraint exists
            ]
        ),
    ]