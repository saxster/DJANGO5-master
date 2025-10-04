"""
Enable PostgreSQL pg_stat_statements extension for query performance monitoring.

This migration enables comprehensive query performance tracking by:
1. Installing pg_stat_statements extension
2. Configuring automatic query statistics collection
3. Setting up query execution tracking

Benefits:
- Identify slow queries and performance bottlenecks
- Monitor query frequency and execution patterns
- Analyze resource usage per query type
- Enable data-driven query optimization decisions

Requirements:
- PostgreSQL 9.2+ (satisfied - using 14.2+)
- Superuser privileges for extension installation
- postgresql.conf: shared_preload_libraries = 'pg_stat_statements'

Post-migration setup required:
1. Add to postgresql.conf: shared_preload_libraries = 'pg_stat_statements'
2. Restart PostgreSQL server
3. Run migration to enable extension
4. Use pg_stat_statements view for monitoring

Compliance: Rule #7 (Migration < 200 lines), Enterprise monitoring standards
"""

from django.db import migrations
import logging

logger = logging.getLogger("django.db.migrations")


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_add_comprehensive_performance_indexes'),
    ]

    operations = [
        # Enable pg_stat_statements extension for query monitoring
        migrations.RunSQL(
            sql=[
                """
                -- Enable pg_stat_statements extension
                -- Note: Requires shared_preload_libraries = 'pg_stat_statements' in postgresql.conf
                CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
                """,

                """
                -- Reset statistics to start fresh monitoring
                -- This clears any existing query statistics
                SELECT pg_stat_statements_reset();
                """,

                """
                -- Create function to get top slow queries
                CREATE OR REPLACE FUNCTION get_slow_queries(limit_count integer DEFAULT 10)
                RETURNS TABLE(
                    query_hash bigint,
                    query_text text,
                    calls bigint,
                    total_exec_time numeric,
                    mean_exec_time numeric,
                    max_exec_time numeric,
                    rows_returned bigint,
                    temp_blks_written bigint
                ) AS $$
                BEGIN
                    RETURN QUERY
                    SELECT
                        pss.queryid,
                        pss.query,
                        pss.calls,
                        round(pss.total_exec_time::numeric, 2),
                        round(pss.mean_exec_time::numeric, 2),
                        round(pss.max_exec_time::numeric, 2),
                        pss.rows,
                        pss.temp_blks_written
                    FROM pg_stat_statements pss
                    WHERE pss.query NOT LIKE '%pg_stat_statements%'
                        AND pss.query NOT LIKE '%COMMIT%'
                        AND pss.query NOT LIKE '%BEGIN%'
                    ORDER BY pss.total_exec_time DESC
                    LIMIT limit_count;
                END;
                $$ LANGUAGE plpgsql;
                """,

                """
                -- Create function to get most frequently called queries
                CREATE OR REPLACE FUNCTION get_frequent_queries(limit_count integer DEFAULT 10)
                RETURNS TABLE(
                    query_hash bigint,
                    query_text text,
                    calls bigint,
                    total_exec_time numeric,
                    mean_exec_time numeric,
                    rows_per_call numeric
                ) AS $$
                BEGIN
                    RETURN QUERY
                    SELECT
                        pss.queryid,
                        pss.query,
                        pss.calls,
                        round(pss.total_exec_time::numeric, 2),
                        round(pss.mean_exec_time::numeric, 2),
                        round((pss.rows::numeric / NULLIF(pss.calls, 0)), 2)
                    FROM pg_stat_statements pss
                    WHERE pss.query NOT LIKE '%pg_stat_statements%'
                        AND pss.query NOT LIKE '%COMMIT%'
                        AND pss.query NOT LIKE '%BEGIN%'
                    ORDER BY pss.calls DESC
                    LIMIT limit_count;
                END;
                $$ LANGUAGE plpgsql;
                """,

                """
                -- Create function to analyze query patterns
                CREATE OR REPLACE FUNCTION get_query_stats_summary()
                RETURNS TABLE(
                    total_queries bigint,
                    total_exec_time numeric,
                    avg_exec_time numeric,
                    slowest_query_time numeric,
                    most_frequent_calls bigint
                ) AS $$
                BEGIN
                    RETURN QUERY
                    SELECT
                        COUNT(*)::bigint,
                        round(SUM(pss.total_exec_time)::numeric, 2),
                        round(AVG(pss.mean_exec_time)::numeric, 2),
                        round(MAX(pss.max_exec_time)::numeric, 2),
                        MAX(pss.calls)::bigint
                    FROM pg_stat_statements pss
                    WHERE pss.query NOT LIKE '%pg_stat_statements%';
                END;
                $$ LANGUAGE plpgsql;
                """,

                """
                -- Create view for easy query analysis
                CREATE OR REPLACE VIEW query_performance_analysis AS
                SELECT
                    queryid as query_hash,
                    LEFT(query, 100) as query_preview,
                    calls,
                    round(total_exec_time::numeric, 2) as total_time_ms,
                    round(mean_exec_time::numeric, 2) as avg_time_ms,
                    round(max_exec_time::numeric, 2) as max_time_ms,
                    round((rows::numeric / NULLIF(calls, 0)), 2) as avg_rows_per_call,
                    round((100.0 * total_exec_time / SUM(total_exec_time) OVER()), 2) as pct_total_time,
                    temp_blks_written,
                    temp_blks_read,
                    local_blks_hit,
                    local_blks_read
                FROM pg_stat_statements
                WHERE query NOT LIKE '%pg_stat_statements%'
                    AND query NOT LIKE '%COMMIT%'
                    AND query NOT LIKE '%BEGIN%'
                ORDER BY total_exec_time DESC;
                """,
            ],
            reverse_sql=[
                "DROP VIEW IF EXISTS query_performance_analysis;",
                "DROP FUNCTION IF EXISTS get_query_stats_summary();",
                "DROP FUNCTION IF EXISTS get_frequent_queries(integer);",
                "DROP FUNCTION IF EXISTS get_slow_queries(integer);",
                "DROP EXTENSION IF EXISTS pg_stat_statements CASCADE;",
            ]
        ),

        # Add helpful comments for DBAs
        migrations.RunSQL(
            sql=[
                """
                -- Add comments for database administrators
                COMMENT ON EXTENSION pg_stat_statements IS
                'Query performance monitoring extension - tracks execution statistics for all SQL statements';
                """,

                """
                COMMENT ON FUNCTION get_slow_queries IS
                'Returns top N slowest queries by total execution time with detailed metrics';
                """,

                """
                COMMENT ON FUNCTION get_frequent_queries IS
                'Returns top N most frequently executed queries with efficiency metrics';
                """,

                """
                COMMENT ON VIEW query_performance_analysis IS
                'Comprehensive query performance analysis with percentage breakdown and resource usage';
                """,
            ],
            reverse_sql=[
                # Comments are dropped automatically when objects are dropped
            ]
        ),
    ]