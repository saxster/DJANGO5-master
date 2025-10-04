"""
Management command to analyze ticket system performance and index usage.

Monitors the effectiveness of performance indexes and identifies
additional optimization opportunities.

Usage: python manage.py analyze_ticket_performance [options]
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models
from django.utils import timezone
from datetime import timedelta
import json
from typing import Dict, List, Any

from apps.y_helpdesk.models import Ticket, EscalationMatrix


class Command(BaseCommand):
    help = 'Analyze ticket system performance and index effectiveness'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to analyze (default: 7)'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed query analysis'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export results to JSON file'
        )
        parser.add_argument(
            '--check-indexes',
            action='store_true',
            help='Check index usage statistics'
        )

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self.days = options['days']
        self.detailed = options['detailed']

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🔍 TICKET SYSTEM PERFORMANCE ANALYSIS\n"
                f"{'='*50}\n"
            )
        )

        # Analyze different aspects of performance
        results = {
            'timestamp': timezone.now().isoformat(),
            'analysis_period_days': self.days,
            'ticket_stats': self.analyze_ticket_stats(),
            'query_performance': self.analyze_query_performance(),
            'index_usage': self.analyze_index_usage() if options['check_indexes'] else None,
            'recommendations': []
        }

        # Generate performance recommendations
        recommendations = self.generate_recommendations(results)
        results['recommendations'] = recommendations

        # Display results
        self.display_results(results)

        # Export if requested
        if options['export']:
            self.export_results(results, options['export'])

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Performance analysis completed successfully!\n"
            )
        )

    def analyze_ticket_stats(self) -> Dict[str, Any]:
        """Analyze basic ticket statistics."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=self.days)

        stats = {
            'total_tickets': Ticket.objects.count(),
            'recent_tickets': Ticket.objects.filter(
                cdtz__gte=start_date
            ).count(),
            'status_distribution': {},
            'priority_distribution': {},
            'escalation_stats': {}
        }

        # Status distribution
        status_counts = (
            Ticket.objects.filter(cdtz__gte=start_date)
            .values('status')
            .annotate(count=models.Count('id'))
        )
        for item in status_counts:
            stats['status_distribution'][item['status']] = item['count']

        # Priority distribution
        priority_counts = (
            Ticket.objects.filter(cdtz__gte=start_date)
            .values('priority')
            .annotate(count=models.Count('id'))
        )
        for item in priority_counts:
            stats['priority_distribution'][item['priority'] or 'NONE'] = item['count']

        # Escalation statistics
        stats['escalation_stats'] = {
            'total_escalated': Ticket.objects.filter(level__gt=0).count(),
            'high_escalation': Ticket.objects.filter(level__gte=3).count(),
            'recent_escalations': Ticket.objects.filter(
                cdtz__gte=start_date, level__gt=0
            ).count()
        }

        if self.verbosity >= 1:
            self.stdout.write(f"📊 Ticket Statistics (Last {self.days} days):")
            self.stdout.write(f"   Total tickets: {stats['total_tickets']:,}")
            self.stdout.write(f"   Recent tickets: {stats['recent_tickets']:,}")
            self.stdout.write(f"   Escalated tickets: {stats['escalation_stats']['total_escalated']:,}")

        return stats

    def analyze_query_performance(self) -> Dict[str, Any]:
        """Analyze common query patterns and their performance."""
        with connection.cursor() as cursor:
            # Test common dashboard query
            dashboard_query_time = self.time_query(
                "Dashboard Statistics Query",
                """
                SELECT status, COUNT(*)
                FROM ticket
                WHERE cdtz >= %s
                AND bu_id IN %s
                GROUP BY status
                """,
                [
                    timezone.now() - timedelta(days=30),
                    (1, 2, 3)  # Sample BU IDs
                ]
            )

            # Test ticket list query
            list_query_time = self.time_query(
                "Ticket List Query",
                """
                SELECT id, ticketno, status, priority, cdtz
                FROM ticket
                WHERE cdtz >= %s AND cdtz <= %s
                AND bu_id IN %s
                ORDER BY cdtz DESC
                LIMIT 50
                """,
                [
                    timezone.now() - timedelta(days=7),
                    timezone.now(),
                    (1, 2, 3)
                ]
            )

            # Test escalation query
            escalation_query_time = self.time_query(
                "Escalation Processing Query",
                """
                SELECT t.id, t.level, em.level as next_level
                FROM ticket t
                LEFT JOIN escalationmatrix em ON em.escalationtemplate_id = t.ticketcategory_id
                AND em.level = t.level + 1
                WHERE t.status NOT IN ('CLOSED', 'CANCELLED')
                """,
                []
            )

        performance_data = {
            'dashboard_query_ms': dashboard_query_time,
            'list_query_ms': list_query_time,
            'escalation_query_ms': escalation_query_time,
            'query_performance_rating': self.rate_performance({
                'dashboard': dashboard_query_time,
                'list': list_query_time,
                'escalation': escalation_query_time
            })
        }

        if self.verbosity >= 1:
            self.stdout.write(f"\n⚡ Query Performance Analysis:")
            self.stdout.write(f"   Dashboard query: {dashboard_query_time:.2f}ms")
            self.stdout.write(f"   List query: {list_query_time:.2f}ms")
            self.stdout.write(f"   Escalation query: {escalation_query_time:.2f}ms")

        return performance_data

    def analyze_index_usage(self) -> Dict[str, Any]:
        """Analyze database index usage statistics."""
        # This would require database-specific queries
        # PostgreSQL example - adapt for your database
        with connection.cursor() as cursor:
            try:
                # Check index usage (PostgreSQL specific)
                cursor.execute("""
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        idx_tup_read,
                        idx_tup_fetch
                    FROM pg_stat_user_indexes
                    WHERE tablename IN ('ticket', 'escalationmatrix', 'ticket_workflow')
                    ORDER BY idx_tup_read DESC
                """)

                index_stats = []
                for row in cursor.fetchall():
                    index_stats.append({
                        'schema': row[0],
                        'table': row[1],
                        'index': row[2],
                        'tuples_read': row[3],
                        'tuples_fetched': row[4]
                    })

                if self.verbosity >= 1:
                    self.stdout.write(f"\n📈 Index Usage Statistics:")
                    for stat in index_stats[:10]:  # Top 10
                        self.stdout.write(
                            f"   {stat['table']}.{stat['index']}: "
                            f"{stat['tuples_read']:,} reads"
                        )

                return {'index_statistics': index_stats}

            except Exception as e:
                if self.verbosity >= 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Index analysis not available: {e}"
                        )
                    )
                return {'error': str(e)}

    def time_query(self, query_name: str, sql: str, params: List) -> float:
        """Time a specific query execution."""
        import time

        with connection.cursor() as cursor:
            start_time = time.time()
            try:
                cursor.execute(sql, params)
                cursor.fetchall()  # Ensure full execution
                end_time = time.time()

                execution_time_ms = (end_time - start_time) * 1000

                if self.detailed:
                    self.stdout.write(f"   {query_name}: {execution_time_ms:.2f}ms")

                return execution_time_ms

            except Exception as e:
                if self.verbosity >= 1:
                    self.stdout.write(
                        self.style.ERROR(f"Query failed: {query_name} - {e}")
                    )
                return -1

    def rate_performance(self, timings: Dict[str, float]) -> str:
        """Rate overall performance based on query timings."""
        avg_time = sum(t for t in timings.values() if t > 0) / len(timings)

        if avg_time < 10:
            return "EXCELLENT"
        elif avg_time < 50:
            return "GOOD"
        elif avg_time < 200:
            return "FAIR"
        else:
            return "NEEDS_IMPROVEMENT"

    def generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []

        # Analyze query performance
        query_perf = results.get('query_performance', {})

        if query_perf.get('dashboard_query_ms', 0) > 100:
            recommendations.append(
                "Consider optimizing dashboard queries with additional indexes on "
                "(bu_id, client_id, cdtz) composite key"
            )

        if query_perf.get('escalation_query_ms', 0) > 200:
            recommendations.append(
                "Escalation processing is slow. Ensure indexes on "
                "(escalationtemplate_id, level) are being used effectively"
            )

        # Analyze ticket volume
        stats = results.get('ticket_stats', {})
        if stats.get('total_tickets', 0) > 100000:
            recommendations.append(
                "Large ticket volume detected. Consider partitioning strategies "
                "and archival policies for old tickets"
            )

        # Analyze escalation patterns
        escalation_stats = stats.get('escalation_stats', {})
        escalation_ratio = (
            escalation_stats.get('total_escalated', 0) /
            max(stats.get('total_tickets', 1), 1)
        )

        if escalation_ratio > 0.3:
            recommendations.append(
                f"High escalation ratio ({escalation_ratio:.1%}). "
                "Review auto-assignment rules and escalation thresholds"
            )

        if not recommendations:
            recommendations.append("Performance looks good! Continue monitoring.")

        return recommendations

    def display_results(self, results: Dict[str, Any]):
        """Display analysis results in a formatted manner."""
        performance_rating = results['query_performance']['query_performance_rating']

        # Color code the rating
        if performance_rating == "EXCELLENT":
            rating_style = self.style.SUCCESS
        elif performance_rating == "GOOD":
            rating_style = self.style.SUCCESS
        elif performance_rating == "FAIR":
            rating_style = self.style.WARNING
        else:
            rating_style = self.style.ERROR

        self.stdout.write(f"\n🎯 Overall Performance Rating: {rating_style(performance_rating)}")

        # Display recommendations
        if results['recommendations']:
            self.stdout.write(f"\n💡 Recommendations:")
            for i, rec in enumerate(results['recommendations'], 1):
                self.stdout.write(f"   {i}. {rec}")

    def export_results(self, results: Dict[str, Any], filename: str):
        """Export results to JSON file."""
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)

            self.stdout.write(
                self.style.SUCCESS(f"Results exported to {filename}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Export failed: {e}")
            )