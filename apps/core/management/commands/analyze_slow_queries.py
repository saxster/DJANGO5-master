"""
Automated Slow Query Detection and Analysis Command

This management command analyzes PostgreSQL performance using pg_stat_statements
and automatically creates alerts for slow queries and performance issues.

Features:
- Automated slow query detection
- Performance trend analysis
- Query optimization recommendations
- Integration with alerting systems
- Historical performance tracking

Usage:
    python manage.py analyze_slow_queries
    python manage.py analyze_slow_queries --threshold 1000 --limit 20
    python manage.py analyze_slow_queries --create-alerts
    python manage.py analyze_slow_queries --reset-stats

Compliance:
- Rule #14: Management command < 200 lines
- Enterprise monitoring standards
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from django.conf import settings
import logging
from typing import List, Dict, Optional
from decimal import Decimal
from apps.core.exceptions.patterns import ENCRYPTION_EXCEPTIONS

from apps.core.exceptions.patterns import FILE_EXCEPTIONS

from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS


logger = logging.getLogger("slow_query_analyzer")


class Command(BaseCommand):
    help = 'Analyze slow queries using pg_stat_statements and create alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=int,
            default=1000,
            help='Slow query threshold in milliseconds (default: 1000ms)'
        )

        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of slowest queries to analyze (default: 10)'
        )

        parser.add_argument(
            '--create-alerts',
            action='store_true',
            help='Create alert records for slow queries'
        )

        parser.add_argument(
            '--reset-stats',
            action='store_true',
            help='Reset pg_stat_statements statistics (use with caution)'
        )

        parser.add_argument(
            '--export-report',
            type=str,
            help='Export analysis report to file (JSON format)'
        )

    def handle(self, *args, **options):
        """Main command handler."""
        self.threshold_ms = options['threshold']
        self.limit = options['limit']
        self.create_alerts = options['create_alerts']
        self.reset_stats = options['reset_stats']
        self.export_file = options.get('export_report')

        self.stdout.write(
            self.style.SUCCESS(f"Starting slow query analysis (threshold: {self.threshold_ms}ms)")
        )

        try:
            # Check if pg_stat_statements is available
            if not self._check_pg_stat_statements():
                raise CommandError("pg_stat_statements extension is not available")

            # Reset statistics if requested
            if self.reset_stats:
                self._reset_statistics()
                self.stdout.write(
                    self.style.WARNING("pg_stat_statements statistics have been reset")
                )
                return

            # Analyze slow queries
            analysis_results = self._analyze_slow_queries()

            # Create alerts if requested
            if self.create_alerts:
                alerts_created = self._create_slow_query_alerts(analysis_results['slow_queries'])
                self.stdout.write(
                    self.style.SUCCESS(f"Created {alerts_created} slow query alerts")
                )

            # Export report if requested
            if self.export_file:
                self._export_analysis_report(analysis_results)

            # Display summary
            self._display_analysis_summary(analysis_results)

        except FILE_EXCEPTIONS as e:
            logger.error(f"Slow query analysis failed: {e}", exc_info=True)
            raise CommandError(f"Analysis failed: {e}")

    def _check_pg_stat_statements(self) -> bool:
        """Check if pg_stat_statements extension is available."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                    )
                """)
                return cursor.fetchone()[0]
        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Failed to check pg_stat_statements: {e}")
            return False

    def _reset_statistics(self) -> None:
        """Reset pg_stat_statements statistics."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_stat_statements_reset()")
                logger.info("pg_stat_statements statistics reset")
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to reset statistics: {e}")
            raise

    def _analyze_slow_queries(self) -> Dict:
        """Analyze slow queries from pg_stat_statements."""
        try:
            with connection.cursor() as cursor:
                # Get slow queries
                cursor.execute("""
                    SELECT
                        queryid,
                        query,
                        calls,
                        total_exec_time,
                        mean_exec_time,
                        max_exec_time,
                        stddev_exec_time,
                        rows,
                        shared_blks_hit,
                        shared_blks_read,
                        temp_blks_written
                    FROM pg_stat_statements
                    WHERE mean_exec_time > %s
                        AND calls > 1
                        AND query NOT LIKE '%%pg_stat_statements%%'
                    ORDER BY total_exec_time DESC
                    LIMIT %s;
                """, [self.threshold_ms, self.limit])

                slow_queries = []
                for row in cursor.fetchall():
                    slow_queries.append({
                        'query_hash': row[0],
                        'query_text': row[1],
                        'calls': row[2],
                        'total_exec_time': Decimal(str(row[3])),
                        'mean_exec_time': Decimal(str(row[4])),
                        'max_exec_time': Decimal(str(row[5])),
                        'stddev_exec_time': Decimal(str(row[6])) if row[6] else Decimal('0'),
                        'rows_returned': row[7],
                        'shared_blks_hit': row[8],
                        'shared_blks_read': row[9],
                        'temp_blks_written': row[10],
                    })

                # Get overall statistics
                cursor.execute("""
                    SELECT
                        count(*) as total_queries,
                        sum(calls) as total_calls,
                        sum(total_exec_time) as total_time,
                        avg(mean_exec_time) as avg_exec_time,
                        max(max_exec_time) as slowest_query
                    FROM pg_stat_statements
                    WHERE query NOT LIKE '%%pg_stat_statements%%';
                """)

                overall_stats = cursor.fetchone()

                return {
                    'slow_queries': slow_queries,
                    'overall_stats': {
                        'total_queries': overall_stats[0],
                        'total_calls': overall_stats[1],
                        'total_time': Decimal(str(overall_stats[2])) if overall_stats[2] else Decimal('0'),
                        'avg_exec_time': Decimal(str(overall_stats[3])) if overall_stats[3] else Decimal('0'),
                        'slowest_query': Decimal(str(overall_stats[4])) if overall_stats[4] else Decimal('0'),
                    },
                    'analysis_timestamp': timezone.now(),
                    'threshold_ms': self.threshold_ms
                }

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to analyze slow queries: {e}")
            raise

    def _create_slow_query_alerts(self, slow_queries: List[Dict]) -> int:
        """Create alert records for slow queries."""
        try:
            from apps.core.models.query_performance import SlowQueryAlert
            from apps.core.services.query_plan_analyzer import QueryPlanAnalyzer
            alerts_created = 0

            for query_data in slow_queries:
                # Determine severity based on execution time
                mean_time = float(query_data['mean_exec_time'])
                if mean_time > 5000:  # 5 seconds
                    severity = 'critical'
                elif mean_time > 2000:  # 2 seconds
                    severity = 'warning'
                else:
                    severity = 'info'

                # Check if alert already exists for this query
                existing_alert = SlowQueryAlert.objects.filter(
                    query_hash=query_data['query_hash'],
                    status__in=['new', 'acknowledged'],
                    alert_time__gte=timezone.now().replace(hour=0, minute=0, second=0)
                ).first()

                if not existing_alert:
                    alert = SlowQueryAlert.objects.create(
                        query_hash=query_data['query_hash'],
                        severity=severity,
                        alert_type='slow_query_detected',
                        execution_time=query_data['mean_exec_time'],
                        threshold_exceeded=Decimal(str(self.threshold_ms)),
                        query_text=query_data['query_text'][:1000],  # Truncate for storage
                    )
                    alerts_created += 1

                    # Automatically analyze execution plan for new alerts
                    try:
                        plan_analyzer = QueryPlanAnalyzer()
                        execution_plan = plan_analyzer.analyze_slow_query(alert)
                        if execution_plan:
                            self.stdout.write(
                                f"Captured execution plan for query {query_data['query_hash']}"
                            )
                    except FILE_EXCEPTIONS as e:
                        logger.warning(f"Failed to analyze execution plan for query {query_data['query_hash']}: {e}")

            return alerts_created

        except ENCRYPTION_EXCEPTIONS as e:
            logger.error(f"Failed to create slow query alerts: {e}")
            raise

    def _export_analysis_report(self, analysis_results: Dict) -> None:
        """Export analysis report to file."""
        try:
            import json
            from decimal import Decimal

            # Convert Decimal objects to float for JSON serialization
            def decimal_converter(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError

            with open(self.export_file, 'w') as f:
                json.dump(analysis_results, f, indent=2, default=decimal_converter)

            self.stdout.write(
                self.style.SUCCESS(f"Analysis report exported to {self.export_file}")
            )

        except FILE_EXCEPTIONS as e:
            logger.error(f"Failed to export report: {e}")
            raise

    def _display_analysis_summary(self, analysis_results: Dict) -> None:
        """Display analysis summary to console."""
        slow_queries = analysis_results['slow_queries']
        overall_stats = analysis_results['overall_stats']

        self.stdout.write(
            self.style.SUCCESS("\n=== SLOW QUERY ANALYSIS SUMMARY ===")
        )

        self.stdout.write(f"Analysis Timestamp: {analysis_results['analysis_timestamp']}")
        self.stdout.write(f"Threshold: {analysis_results['threshold_ms']}ms")
        self.stdout.write(f"Slow Queries Found: {len(slow_queries)}")

        if overall_stats['total_queries']:
            self.stdout.write(f"\nOverall Statistics:")
            self.stdout.write(f"  Total Unique Queries: {overall_stats['total_queries']}")
            self.stdout.write(f"  Total Query Calls: {overall_stats['total_calls']}")
            self.stdout.write(f"  Total Execution Time: {overall_stats['total_time']:.2f}ms")
            self.stdout.write(f"  Average Execution Time: {overall_stats['avg_exec_time']:.2f}ms")
            self.stdout.write(f"  Slowest Single Query: {overall_stats['slowest_query']:.2f}ms")

        if slow_queries:
            self.stdout.write(f"\nTop {len(slow_queries)} Slowest Queries:")
            self.stdout.write("-" * 80)

            for i, query in enumerate(slow_queries[:5], 1):  # Show top 5
                self.stdout.write(f"\n{i}. Query Hash: {query['query_hash']}")
                self.stdout.write(f"   Calls: {query['calls']}")
                self.stdout.write(f"   Mean Time: {query['mean_exec_time']:.2f}ms")
                self.stdout.write(f"   Max Time: {query['max_exec_time']:.2f}ms")
                self.stdout.write(f"   Total Time: {query['total_exec_time']:.2f}ms")

                # Show query preview
                query_preview = query['query_text'][:100].replace('\n', ' ')
                self.stdout.write(f"   Query: {query_preview}...")

                # Performance recommendations
                recommendations = self._get_query_recommendations(query)
                if recommendations:
                    self.stdout.write(f"   Recommendations: {', '.join(recommendations)}")

    def _get_query_recommendations(self, query_data: Dict) -> List[str]:
        """Generate optimization recommendations for a query."""
        recommendations = []
        query_text = query_data['query_text'].upper()

        # High execution time with many calls
        if query_data['calls'] > 100 and query_data['mean_exec_time'] > 500:
            recommendations.append("Consider caching or optimization")

        # High temp block usage
        if query_data['temp_blks_written'] > 1000:
            recommendations.append("Query using temp storage - consider indexes")

        # Low cache hit ratio
        total_blocks = query_data['shared_blks_hit'] + query_data['shared_blks_read']
        if total_blocks > 0:
            hit_ratio = query_data['shared_blks_hit'] / total_blocks
            if hit_ratio < 0.9:
                recommendations.append("Low cache hit ratio - check buffer pool")

        # Query pattern analysis
        if 'SELECT *' in query_text:
            recommendations.append("Avoid SELECT * - specify needed columns")

        if query_text.count('JOIN') > 3:
            recommendations.append("Complex joins detected - consider optimization")

        return recommendations