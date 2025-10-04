# Generated for GeoDjango Performance Optimization - Activity Models
from django.contrib.postgres.operations import AddIndexConcurrently, RemoveIndexConcurrently
from django.contrib.postgres.indexes import GistIndex
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0012_add_mobile_sync_fields'),
    ]

    operations = [
        # Add GIST indexes for spatial fields on Asset model
        AddIndexConcurrently(
            model_name='asset',
            index=GistIndex(
                fields=['gpslocation'],
                name='asset_gpslocation_gist_idx',
                condition=models.Q(gpslocation__isnull=False)
            )
        ),
        # Add GIST index for Location model
        AddIndexConcurrently(
            model_name='location',
            index=GistIndex(
                fields=['gpslocation'],
                name='location_gpslocation_gist_idx',
                condition=models.Q(gpslocation__isnull=False)
            )
        ),
        # Add GIST index for AssetLog model
        AddIndexConcurrently(
            model_name='assetlog',
            index=GistIndex(
                fields=['gpslocation'],
                name='assetlog_gpslocation_gist_idx',
                condition=models.Q(gpslocation__isnull=False)
            )
        ),
        # Add compound indexes for common spatial queries with business logic
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY asset_client_gps_idx
            ON asset USING btree(client_id, enable)
            WHERE gpslocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS asset_client_gps_idx;"
        ),
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY location_bu_gps_idx
            ON location USING btree(bu_id, enable)
            WHERE gpslocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS location_bu_gps_idx;"
        ),
        # Performance index for asset critical status with GPS
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY asset_critical_gps_idx
            ON asset USING btree(iscritical, runningstatus)
            WHERE gpslocation IS NOT NULL AND enable = true;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS asset_critical_gps_idx;"
        ),
    ]

    atomic = False  # Required for CONCURRENTLY operations