"""
NOC Advanced Indexes Migration.

Implements composite and partial indexes for optimal query performance.
Uses BRIN indexes for time-series data and partial indexes for active records.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('noc', '0002_partition_metric_snapshot'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                """
                -- Composite index for tenant + client + time range queries
                CREATE INDEX IF NOT EXISTS idx_noc_snapshot_tenant_client_time
                ON noc_metric_snapshot (tenant_id, client_id, window_end DESC);
                """,

                """
                -- Composite index for geographic filtering
                CREATE INDEX IF NOT EXISTS idx_noc_snapshot_geo_time
                ON noc_metric_snapshot (city, state, window_end DESC)
                WHERE city IS NOT NULL OR state IS NOT NULL;
                """,

                """
                -- Composite index for OIC filtering
                CREATE INDEX IF NOT EXISTS idx_noc_snapshot_oic_time
                ON noc_metric_snapshot (oic_id, window_end DESC)
                WHERE oic_id IS NOT NULL;
                """,

                """
                -- BRIN index for time-series queries (efficient for large tables)
                CREATE INDEX IF NOT EXISTS idx_noc_snapshot_window_end_brin
                ON noc_metric_snapshot USING BRIN (window_end);
                """,

                """
                -- Partial index for active alerts (most frequently queried)
                CREATE INDEX IF NOT EXISTS idx_noc_alert_active
                ON noc_alert_event (tenant_id, severity, cdtz DESC)
                WHERE status IN ('NEW', 'ACKNOWLEDGED', 'ASSIGNED');
                """,

                """
                -- Index for alert deduplication lookups
                CREATE INDEX IF NOT EXISTS idx_noc_alert_dedup_active
                ON noc_alert_event (tenant_id, dedup_key, status)
                WHERE status IN ('NEW', 'ACKNOWLEDGED');
                """,

                """
                -- Index for alert correlation queries
                CREATE INDEX IF NOT EXISTS idx_noc_alert_correlation_id
                ON noc_alert_event (correlation_id, cdtz DESC)
                WHERE correlation_id IS NOT NULL;
                """,

                """
                -- Composite index for incident queries
                CREATE INDEX IF NOT EXISTS idx_noc_incident_tenant_state
                ON noc_incident (tenant_id, state, severity, created_at DESC);
                """,

                """
                -- Index for maintenance window lookups
                CREATE INDEX IF NOT EXISTS idx_noc_maintenance_active
                ON noc_maintenance_window (tenant_id, start_time, end_time)
                WHERE start_time <= NOW() AND end_time >= NOW();
                """,

                """
                -- Index for audit log queries (performance critical)
                CREATE INDEX IF NOT EXISTS idx_noc_audit_tenant_time
                ON noc_audit_log (tenant_id, action_time DESC);
                """,

                """
                -- Create statistics for query planner
                ANALYZE noc_metric_snapshot;
                ANALYZE noc_alert_event;
                ANALYZE noc_incident;
                """,
            ],
            reverse_sql=[
                "DROP INDEX IF EXISTS idx_noc_snapshot_tenant_client_time;",
                "DROP INDEX IF EXISTS idx_noc_snapshot_geo_time;",
                "DROP INDEX IF EXISTS idx_noc_snapshot_oic_time;",
                "DROP INDEX IF EXISTS idx_noc_snapshot_window_end_brin;",
                "DROP INDEX IF EXISTS idx_noc_alert_active;",
                "DROP INDEX IF EXISTS idx_noc_alert_dedup_active;",
                "DROP INDEX IF EXISTS idx_noc_alert_correlation_id;",
                "DROP INDEX IF EXISTS idx_noc_incident_tenant_state;",
                "DROP INDEX IF EXISTS idx_noc_maintenance_active;",
                "DROP INDEX IF EXISTS idx_noc_audit_tenant_time;",
            ]
        ),
    ]