# Generated for GeoDjango Performance Optimization - Onboarding Models
from django.contrib.postgres.operations import AddIndexConcurrently, RemoveIndexConcurrently
from django.contrib.postgres.indexes import GistIndex
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0007_add_voice_fields_to_conversation_session'),
    ]

    operations = [
        # Add GIST index for Bt (Business Unit) model gpslocation
        AddIndexConcurrently(
            model_name='bt',
            index=GistIndex(
                fields=['gpslocation'],
                name='bt_gpslocation_gist_idx',
                condition=models.Q(gpslocation__isnull=False)
            )
        ),
        # Add compound indexes for common business unit spatial queries
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY bt_enable_gps_idx
            ON bt USING btree(enable, gpsenable)
            WHERE gpslocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS bt_enable_gps_idx;"
        ),
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY bt_parent_gps_idx
            ON bt USING btree(parent_id, enable)
            WHERE gpslocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS bt_parent_gps_idx;"
        ),
        # Performance index for site geofencing queries
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY bt_geofence_enabled_idx
            ON bt USING btree(gpsenable, enable, isvendor)
            WHERE gpslocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS bt_geofence_enabled_idx;"
        ),
    ]

    atomic = False  # Required for CONCURRENTLY operations