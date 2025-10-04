"""
Django management command for Redis memory optimization.

Usage:
    python manage.py optimize_redis_memory
    python manage.py optimize_redis_memory --force
    python manage.py optimize_redis_memory --check-only
    python manage.py optimize_redis_memory --alert-threshold 80
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.core.services.redis_memory_manager import redis_memory_manager
import json


class Command(BaseCommand):
    help = 'Optimize Redis memory usage and check for memory-related issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            help='Force optimization even if recently performed'
        )

        parser.add_argument(
            '--check-only',
            action='store_true',
            dest='check_only',
            help='Only check memory status without performing optimization'
        )

        parser.add_argument(
            '--alert-threshold',
            type=float,
            dest='alert_threshold',
            default=85.0,
            help='Memory usage percentage threshold for alerts (default: 85.0)'
        )

        parser.add_argument(
            '--json',
            action='store_true',
            dest='json_output',
            help='Output results in JSON format'
        )

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1))
        force = options.get('force', False)
        check_only = options.get('check_only', False)
        alert_threshold = options.get('alert_threshold', 85.0)
        json_output = options.get('json_output', False)

        try:
            # Get current memory statistics
            stats = redis_memory_manager.get_memory_stats()

            if not stats:
                raise CommandError('Unable to connect to Redis or retrieve memory statistics')

            # Calculate current usage percentage
            if stats.maxmemory > 0:
                usage_percentage = (stats.used_memory / stats.maxmemory) * 100
            else:
                import psutil
                system_memory = psutil.virtual_memory().total
                usage_percentage = (stats.used_memory / system_memory) * 100

            # Prepare results
            results = {
                'timestamp': timezone.now().isoformat(),
                'redis_stats': {
                    'used_memory_human': stats.used_memory_human,
                    'memory_usage_percentage': round(usage_percentage, 2),
                    'fragmentation_ratio': stats.memory_fragmentation_ratio,
                    'hit_ratio': stats.hit_ratio,
                    'evicted_keys': stats.evicted_keys,
                    'expired_keys': stats.expired_keys
                },
                'alerts': [],
                'optimization_performed': False,
                'optimization_results': None,
                'recommendations': []
            }

            # Check memory health
            alerts = redis_memory_manager.check_memory_health()
            results['alerts'] = [
                {
                    'level': alert.level,
                    'message': alert.message,
                    'current_usage': alert.current_usage,
                    'recommended_action': alert.recommended_action
                }
                for alert in alerts
            ]

            # Get optimization recommendations
            recommendations = redis_memory_manager.get_optimization_recommendations()
            results['recommendations'] = recommendations

            # Perform optimization if requested and needed
            if not check_only:
                should_optimize = force or usage_percentage >= alert_threshold

                if should_optimize:
                    if verbosity >= 1 and not json_output:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Memory usage at {usage_percentage:.1f}% - performing optimization...'
                            )
                        )

                    optimization_results = redis_memory_manager.optimize_memory_usage(force=force)
                    results['optimization_performed'] = True
                    results['optimization_results'] = optimization_results

                    if verbosity >= 1 and not json_output:
                        if optimization_results['status'] == 'completed':
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Optimization completed: {optimization_results['keys_cleaned']} keys cleaned"
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Optimization status: {optimization_results['status']}"
                                )
                            )

            # Output results
            if json_output:
                self.stdout.write(json.dumps(results, indent=2))
            else:
                self._display_formatted_output(results, verbosity)

        except Exception as e:
            if json_output:
                error_result = {
                    'timestamp': timezone.now().isoformat(),
                    'error': str(e),
                    'status': 'failed'
                }
                self.stdout.write(json.dumps(error_result, indent=2))
            else:
                raise CommandError(f'Redis memory optimization failed: {e}')

    def _display_formatted_output(self, results, verbosity):
        """Display results in human-readable format."""

        # Header
        self.stdout.write(
            self.style.HTTP_INFO('=' * 60)
        )
        self.stdout.write(
            self.style.HTTP_INFO('Redis Memory Optimization Report')
        )
        self.stdout.write(
            self.style.HTTP_INFO('=' * 60)
        )

        # Current stats
        stats = results['redis_stats']
        self.stdout.write(f"Memory Usage: {stats['used_memory_human']} ({stats['memory_usage_percentage']}%)")
        self.stdout.write(f"Fragmentation Ratio: {stats['fragmentation_ratio']:.2f}")
        self.stdout.write(f"Cache Hit Ratio: {stats['hit_ratio']}%")
        self.stdout.write(f"Evicted Keys: {stats['evicted_keys']:,}")
        self.stdout.write(f"Expired Keys: {stats['expired_keys']:,}")

        # Alerts
        if results['alerts']:
            self.stdout.write('\nAlerts:')
            for alert in results['alerts']:
                level_style = {
                    'warning': self.style.WARNING,
                    'critical': self.style.ERROR,
                    'emergency': self.style.ERROR
                }.get(alert['level'], self.style.NOTICE)

                self.stdout.write(
                    level_style(f"  [{alert['level'].upper()}] {alert['message']}")
                )
                self.stdout.write(f"    Action: {alert['recommended_action']}")
        else:
            self.stdout.write(
                self.style.SUCCESS('\nNo memory alerts detected.')
            )

        # Optimization results
        if results['optimization_performed'] and results['optimization_results']:
            opt_results = results['optimization_results']
            self.stdout.write('\nOptimization Results:')
            self.stdout.write(f"  Status: {opt_results['status']}")

            if opt_results['status'] == 'completed':
                self.stdout.write(f"  Keys Cleaned: {opt_results['keys_cleaned']:,}")
                if opt_results['memory_freed'] > 0:
                    freed_mb = opt_results['memory_freed'] / (1024 * 1024)
                    self.stdout.write(f"  Memory Freed: {freed_mb:.1f} MB")
                self.stdout.write(f"  Duration: {opt_results['duration_seconds']:.2f} seconds")

        # Recommendations
        if results['recommendations'] and verbosity >= 1:
            self.stdout.write('\nRecommendations:')
            for i, rec in enumerate(results['recommendations'], 1):
                self.stdout.write(f"  {i}. {rec}")

        self.stdout.write(
            self.style.HTTP_INFO('=' * 60)
        )