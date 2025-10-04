"""
NOC Materialized Views Migration.

Creates materialized views for executive summary and client health scores.
Includes refresh functions and pg_cron scheduling for automatic updates.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('noc', '0003_advanced_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                """
                -- Create pg_cron extension (requires superuser privileges)
                -- This may fail in environments without superuser access
                CREATE EXTENSION IF NOT EXISTS pg_cron;
                """,

                """
                -- Executive Summary Materialized View (hourly rollups)
                CREATE MATERIALIZED VIEW IF NOT EXISTS noc_executive_summary AS
                SELECT
                    client_id,
                    date_trunc('hour', window_end) as hour,
                    AVG(tickets_open) as avg_tickets_open,
                    MAX(tickets_overdue) as max_tickets_overdue,
                    AVG(CASE
                        WHEN attendance_expected > 0
                        THEN (attendance_present::float / attendance_expected) * 100
                        ELSE 0
                    END) as avg_attendance_rate,
                    SUM(device_health_offline) as total_devices_offline,
                    AVG(work_orders_pending) as avg_work_orders_pending,
                    COUNT(*) as snapshot_count
                FROM noc_metric_snapshot
                WHERE window_end > NOW() - INTERVAL '7 days'
                GROUP BY client_id, date_trunc('hour', window_end)
                ORDER BY client_id, hour DESC;
                """,

                """
                -- Create unique index on materialized view for concurrent refresh
                CREATE UNIQUE INDEX IF NOT EXISTS idx_noc_exec_summary_client_hour
                ON noc_executive_summary (client_id, hour);
                """,

                """
                -- Client Health Score Materialized View
                CREATE MATERIALIZED VIEW IF NOT EXISTS noc_client_health_score AS
                SELECT
                    client_id,
                    CASE
                        WHEN MAX(tickets_overdue) > 10 THEN 'CRITICAL'
                        WHEN MAX(tickets_overdue) > 5 THEN 'WARNING'
                        WHEN AVG(attendance_present::float / NULLIF(attendance_expected, 0)) < 0.8 THEN 'WARNING'
                        ELSE 'HEALTHY'
                    END as health_status,
                    AVG(tickets_open) as avg_tickets,
                    MAX(tickets_overdue) as max_overdue,
                    AVG(attendance_present::float / NULLIF(attendance_expected, 0)) as attendance_rate,
                    SUM(device_health_offline) as total_offline_devices,
                    MAX(window_end) as last_updated
                FROM noc_metric_snapshot
                WHERE window_end > NOW() - INTERVAL '24 hours'
                GROUP BY client_id;
                """,

                """
                -- Create unique index on client health score view
                CREATE UNIQUE INDEX IF NOT EXISTS idx_noc_client_health_client
                ON noc_client_health_score (client_id);
                """,

                """
                -- Function to refresh materialized views concurrently
                CREATE OR REPLACE FUNCTION refresh_noc_materialized_views()
                RETURNS void AS $$
                BEGIN
                    REFRESH MATERIALIZED VIEW CONCURRENTLY noc_executive_summary;
                    REFRESH MATERIALIZED VIEW CONCURRENTLY noc_client_health_score;
                END;
                $$ LANGUAGE plpgsql;
                """,

                """
                -- Schedule automatic refresh every 5 minutes using pg_cron
                -- This may fail if pg_cron is not installed
                SELECT cron.schedule(
                    'refresh-noc-views',
                    '*/5 * * * *',
                    'SELECT refresh_noc_materialized_views();'
                );
                """,
            ],
            reverse_sql=[
                "SELECT cron.unschedule('refresh-noc-views');",
                "DROP FUNCTION IF EXISTS refresh_noc_materialized_views();",
                "DROP MATERIALIZED VIEW IF EXISTS noc_client_health_score CASCADE;",
                "DROP MATERIALIZED VIEW IF EXISTS noc_executive_summary CASCADE;",
            ]
        ),
    ]