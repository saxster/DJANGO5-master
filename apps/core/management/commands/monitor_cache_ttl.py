"""
Management command to monitor cache TTL health and generate reports.
Provides actionable insights for cache optimization.
"""

import logging
from django.core.management.base import BaseCommand
from apps.core.caching.ttl_monitor import get_ttl_health_report, detect_ttl_anomalies
from apps.core.caching.ttl_optimizer import recommend_ttl_adjustments

logger = logging.getLogger(__name__)

__all__ = ['Command']


class Command(BaseCommand):
    help = 'Monitor cache TTL health and detect anomalies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate comprehensive TTL health report'
        )
        parser.add_argument(
            '--anomalies',
            action='store_true',
            help='Detect and report TTL anomalies'
        )
        parser.add_argument(
            '--recommendations',
            action='store_true',
            help='Generate TTL optimization recommendations'
        )
        parser.add_argument(
            '--save-to-db',
            action='store_true',
            help='Save metrics to database for historical analysis'
        )

    def handle(self, *args, **options):
        """Execute TTL monitoring"""
        try:
            report_flag = options.get('report', False)
            anomalies_flag = options.get('anomalies', False)
            recommendations_flag = options.get('recommendations', False)
            save_to_db = options.get('save_to_db', False)

            if not any([report_flag, anomalies_flag, recommendations_flag]):
                report_flag = True

            if report_flag:
                self._generate_health_report(save_to_db)

            if anomalies_flag:
                self._detect_anomalies(save_to_db)

            if recommendations_flag:
                self._show_recommendations()

        except (ValueError, TypeError) as e:
            logger.error(f'TTL monitoring failed: {e}', exc_info=True)
            self.stderr.write(
                self.style.ERROR(f'✗ Monitoring failed: {str(e)}')
            )

    def _generate_health_report(self, save_to_db: bool):
        """Generate and display TTL health report"""
        self.stdout.write(
            self.style.SUCCESS('═══ TTL HEALTH REPORT ═══')
        )

        report = get_ttl_health_report()

        self.stdout.write(f"\nGenerated: {report.get('generated_at', 'N/A')}")
        self.stdout.write(f"Overall Health: {report.get('overall_health', 'unknown').upper()}")
        self.stdout.write(f"Patterns Analyzed: {report.get('total_patterns_analyzed', 0)}")
        self.stdout.write(f"Unhealthy Patterns: {report.get('unhealthy_patterns', 0)}\n")

        for pattern_name, health in sorted(report.get('patterns', {}).items()):
            status_icon = '✓' if health.get('health_status') == 'healthy' else '✗'
            hit_ratio_pct = health.get('hit_ratio', 0) * 100

            self.stdout.write(f"\n{status_icon} {pattern_name}:")
            self.stdout.write(f"  Hit Ratio: {hit_ratio_pct:.2f}%")
            self.stdout.write(f"  Total Hits: {health.get('total_hits', 0)}")
            self.stdout.write(f"  Total Misses: {health.get('total_misses', 0)}")
            self.stdout.write(f"  Avg TTL at Hit: {health.get('avg_ttl_remaining_at_hit', 0):.0f}s")
            self.stdout.write(f"  Recommendation: {health.get('recommendation', 'N/A')}")

        if save_to_db:
            self._save_metrics_to_db(report)

    def _detect_anomalies(self, save_to_db: bool):
        """Detect and display cache anomalies"""
        self.stdout.write(
            self.style.WARNING('\n═══ TTL ANOMALY DETECTION ═══\n')
        )

        anomalies = detect_ttl_anomalies()

        if not anomalies:
            self.stdout.write(
                self.style.SUCCESS('✓ No anomalies detected - all patterns healthy')
            )
            return

        self.stdout.write(f"Found {len(anomalies)} anomalies:\n")

        for anomaly in anomalies:
            severity_color = self.style.ERROR if anomaly['severity'] == 'high' else self.style.WARNING

            self.stdout.write(severity_color(f"\n⚠️  {anomaly['pattern_name']}:"))
            self.stdout.write(f"  Severity: {anomaly['severity'].upper()}")
            self.stdout.write(f"  Hit Ratio: {anomaly['hit_ratio'] * 100:.2f}%")
            self.stdout.write(f"  Recommendation: {anomaly['recommendation']}")
            self.stdout.write(f"  Detected: {anomaly['detected_at']}")

        if save_to_db:
            self._save_anomalies_to_db(anomalies)

    def _show_recommendations(self):
        """Display TTL optimization recommendations"""
        self.stdout.write(
            self.style.SUCCESS('\n═══ TTL OPTIMIZATION RECOMMENDATIONS ═══\n')
        )

        recommendations = recommend_ttl_adjustments()

        if not recommendations:
            self.stdout.write(
                self.style.SUCCESS('✓ All TTL values are optimally configured')
            )
            return

        self.stdout.write(f"Found {len(recommendations)} optimization opportunities:\n")

        for idx, rec in enumerate(recommendations, 1):
            priority_color = self.style.ERROR if rec['priority'] == 'high' else self.style.WARNING

            self.stdout.write(priority_color(f"\n{idx}. {rec['pattern']} [{rec['priority'].upper()}]:"))
            self.stdout.write(f"   Current Hit Ratio: {rec['current_hit_ratio'] * 100:.2f}%")
            self.stdout.write(f"   Action: {rec['recommendation']}")

    def _save_metrics_to_db(self, report: dict):
        """Save metrics to database for historical analysis"""
        try:
            from apps.core.models.cache_analytics import CacheMetrics

            saved_count = 0
            for pattern_name, health in report.get('patterns', {}).items():
                if health.get('health_status') == 'insufficient_data':
                    continue

                from apps.core.caching.utils import CACHE_TIMEOUTS
                configured_ttl = CACHE_TIMEOUTS.get(
                    pattern_name.upper().replace('-', '_'),
                    CACHE_TIMEOUTS['DEFAULT']
                )

                CacheMetrics.objects.create(
                    pattern_name=pattern_name,
                    pattern_key=health.get('pattern', ''),
                    interval='hourly',
                    total_hits=health.get('total_hits', 0),
                    total_misses=health.get('total_misses', 0),
                    hit_ratio=health.get('hit_ratio', 0),
                    avg_ttl_at_hit=int(health.get('avg_ttl_remaining_at_hit', 0)),
                    configured_ttl=configured_ttl
                )
                saved_count += 1

            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Saved {saved_count} metric snapshots to database')
            )

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            logger.error(f'Error saving metrics to database: {e}')
            self.stderr.write(
                self.style.WARNING(f'⚠️  Could not save to database: {str(e)}')
            )

    def _save_anomalies_to_db(self, anomalies: list):
        """Save detected anomalies to database"""
        try:
            from apps.core.models.cache_analytics import CacheAnomalyLog

            saved_count = 0
            for anomaly in anomalies:
                CacheAnomalyLog.objects.create(
                    pattern_name=anomaly['pattern_name'],
                    anomaly_type='low_hit_ratio',
                    severity=anomaly['severity'],
                    hit_ratio_at_detection=anomaly['hit_ratio'],
                    description=f"Low hit ratio detected: {anomaly['hit_ratio'] * 100:.2f}%",
                    recommendation=anomaly['recommendation']
                )
                saved_count += 1

            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Logged {saved_count} anomalies to database')
            )

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            logger.error(f'Error saving anomalies to database: {e}')
            self.stderr.write(
                self.style.WARNING(f'⚠️  Could not save anomalies: {str(e)}')
            )