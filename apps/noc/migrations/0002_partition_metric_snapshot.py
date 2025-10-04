"""
NOC Metric Snapshot Table Partitioning Migration.

Implements monthly partitioning for noc_metric_snapshot table for optimal performance.
Partitions data by window_end date to enable partition pruning in queries.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('noc', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                """
                -- Create partitioned version of noc_metric_snapshot
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_partitioned (
                    LIKE noc_metric_snapshot INCLUDING ALL
                ) PARTITION BY RANGE (window_end);
                """,

                """
                -- Create partitions for 12 rolling months
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_01
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_02
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_03
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_04
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_05
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_06
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_07
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_08
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_09
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_10
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_11
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
                """,

                """
                CREATE TABLE IF NOT EXISTS noc_metric_snapshot_2025_12
                PARTITION OF noc_metric_snapshot_partitioned
                FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
                """,

                """
                -- Migrate existing data
                INSERT INTO noc_metric_snapshot_partitioned
                SELECT * FROM noc_metric_snapshot;
                """,

                """
                -- Rename tables
                ALTER TABLE noc_metric_snapshot RENAME TO noc_metric_snapshot_old;
                ALTER TABLE noc_metric_snapshot_partitioned RENAME TO noc_metric_snapshot;
                """,

                """
                -- Create function for automatic partition creation
                CREATE OR REPLACE FUNCTION create_monthly_partition()
                RETURNS void AS $$
                DECLARE
                    partition_date DATE;
                    partition_name TEXT;
                    start_date TEXT;
                    end_date TEXT;
                BEGIN
                    partition_date := date_trunc('month', CURRENT_DATE + INTERVAL '2 months');
                    partition_name := 'noc_metric_snapshot_' || to_char(partition_date, 'YYYY_MM');
                    start_date := to_char(partition_date, 'YYYY-MM-DD');
                    end_date := to_char(partition_date + INTERVAL '1 month', 'YYYY-MM-DD');

                    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF noc_metric_snapshot FOR VALUES FROM (%L) TO (%L)',
                                   partition_name, start_date, end_date);
                END;
                $$ LANGUAGE plpgsql;
                """,

                """
                -- Create function for partition cleanup (retain 90 days)
                CREATE OR REPLACE FUNCTION cleanup_old_partitions()
                RETURNS void AS $$
                DECLARE
                    partition_name TEXT;
                    cutoff_date DATE;
                BEGIN
                    cutoff_date := CURRENT_DATE - INTERVAL '90 days';

                    FOR partition_name IN
                        SELECT tablename FROM pg_tables
                        WHERE schemaname = 'public'
                        AND tablename LIKE 'noc_metric_snapshot_2%'
                        AND to_date(substring(tablename from 22), 'YYYY_MM') < date_trunc('month', cutoff_date)
                    LOOP
                        EXECUTE format('DROP TABLE IF EXISTS %I', partition_name);
                    END LOOP;
                END;
                $$ LANGUAGE plpgsql;
                """,
            ],
            reverse_sql=[
                "ALTER TABLE noc_metric_snapshot RENAME TO noc_metric_snapshot_partitioned;",
                "ALTER TABLE noc_metric_snapshot_old RENAME TO noc_metric_snapshot;",
                "DROP TABLE IF EXISTS noc_metric_snapshot_partitioned CASCADE;",
                "DROP FUNCTION IF EXISTS create_monthly_partition();",
                "DROP FUNCTION IF EXISTS cleanup_old_partitions();",
            ]
        ),
    ]