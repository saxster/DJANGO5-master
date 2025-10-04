# Generated migration for composite spatial indexes optimization
# This migration adds performance-critical composite indexes that combine
# spatial fields with commonly-queried business logic fields

from django.contrib.postgres.operations import AddIndexConcurrently
from django.contrib.postgres.indexes import GistIndex, BTreeIndex
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_add_exif_metadata_models'),
        ('activity', '0013_add_spatial_indexes'),
        ('attendance', '0002_add_spatial_indexes'),
        ('onboarding', '0008_add_spatial_indexes'),
    ]

    operations = [
        # ================================================================
        # COMPOSITE INDEXES: Spatial + Business Logic Filters
        # ================================================================

        # ATTENDANCE: Common queries with spatial + business unit + date filters
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY peopleeventlog_bu_datefor_startloc_idx
            ON peopleeventlog USING btree(bu_id, datefor)
            WHERE startlocation IS NOT NULL AND enable = true;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS peopleeventlog_bu_datefor_startloc_idx;"
        ),

        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY peopleeventlog_client_datefor_gps_idx
            ON peopleeventlog USING btree(client_id, datefor, people_id)
            WHERE startlocation IS NOT NULL OR endlocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS peopleeventlog_client_datefor_gps_idx;"
        ),

        # ATTENDANCE: Geofence validation queries (hot path)
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY peopleeventlog_geofence_validation_idx
            ON peopleeventlog USING btree(geofence_id, datefor)
            WHERE startlocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS peopleeventlog_geofence_validation_idx;"
        ),

        # ASSET: Critical asset location tracking
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY asset_critical_client_location_idx
            ON asset USING btree(client_id, iscritical, enable)
            WHERE gpslocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS asset_critical_client_location_idx;"
        ),

        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY asset_bu_type_location_idx
            ON asset USING btree(bu_id, type_id)
            WHERE gpslocation IS NOT NULL AND enable = true;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS asset_bu_type_location_idx;"
        ),

        # ASSET: Asset identifier queries with location
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY asset_identifier_location_idx
            ON asset USING btree(identifier, client_id)
            WHERE gpslocation IS NOT NULL AND enable = true;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS asset_identifier_location_idx;"
        ),

        # LOCATION: Location hierarchy with GPS
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY location_parent_hierarchy_gps_idx
            ON location USING btree(parent_id, client_id)
            WHERE gpslocation IS NOT NULL AND enable = true;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS location_parent_hierarchy_gps_idx;"
        ),

        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY location_type_critical_gps_idx
            ON location USING btree(type_id, iscritical)
            WHERE gpslocation IS NOT NULL AND enable = true;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS location_type_critical_gps_idx;"
        ),

        # BUSINESS UNIT: Site GPS queries with client hierarchy
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY bt_gpsenable_client_idx
            ON bt USING btree(parent_id, gpsenable)
            WHERE gpslocation IS NOT NULL AND enable = true;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS bt_gpsenable_client_idx;"
        ),

        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY bt_type_location_idx
            ON bt USING btree(butype_id)
            WHERE gpslocation IS NOT NULL AND enable = true;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS bt_type_location_idx;"
        ),

        # ================================================================
        # COVERING INDEXES: Include commonly-accessed columns
        # ================================================================

        # ATTENDANCE: Covering index for dashboard queries
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY peopleeventlog_dashboard_covering_idx
            ON peopleeventlog USING btree(people_id, datefor, bu_id)
            INCLUDE (punchintime, punchouttime, distance, duration)
            WHERE startlocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS peopleeventlog_dashboard_covering_idx;"
        ),

        # ASSET: Covering index for asset listing with location
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY asset_listing_covering_idx
            ON asset USING btree(client_id, bu_id, enable)
            INCLUDE (assetcode, assetname, iscritical, runningstatus)
            WHERE gpslocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS asset_listing_covering_idx;"
        ),

        # ================================================================
        # EXPRESSION INDEXES: Computed values for common queries
        # ================================================================

        # ATTENDANCE: Date extraction for monthly reports
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY peopleeventlog_month_year_idx
            ON peopleeventlog USING btree(
                EXTRACT(YEAR FROM datefor),
                EXTRACT(MONTH FROM datefor),
                client_id
            )
            WHERE startlocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS peopleeventlog_month_year_idx;"
        ),

        # ================================================================
        # PARTIAL UNIQUE INDEXES: Enforce constraints with conditions
        # ================================================================

        # ATTENDANCE: Prevent duplicate check-ins on same day
        migrations.RunSQL(
            """
            CREATE UNIQUE INDEX CONCURRENTLY peopleeventlog_unique_daily_checkin_idx
            ON peopleeventlog(people_id, datefor, bu_id)
            WHERE startlocation IS NOT NULL AND datefor IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS peopleeventlog_unique_daily_checkin_idx;"
        ),

        # ================================================================
        # MONITORING: Index statistics collection
        # ================================================================

        # Enable pg_stat_statements for query monitoring (if not already enabled)
        migrations.RunSQL(
            """
            -- Ensure pg_stat_statements extension is available
            CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

            -- Create helper view for spatial index statistics
            CREATE OR REPLACE VIEW spatial_index_stats AS
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan as scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched,
                pg_size_pretty(pg_relation_size(indexrelid)) as size
            FROM pg_stat_user_indexes
            WHERE indexname LIKE '%gps%' OR indexname LIKE '%location%' OR indexname LIKE '%spatial%'
            ORDER BY idx_scan DESC;
            """,
            reverse_sql="""
            DROP VIEW IF EXISTS spatial_index_stats;
            """
        ),
    ]

    atomic = False  # Required for CONCURRENTLY operations