"""
Management command to run monitoring tasks.
"""

import time
import signal
import sys
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from monitoring.alerts import check_and_send_alerts
from monitoring.django_monitoring import metrics_collector
from monitoring.config import monitoring_config


class Command(BaseCommand):
    help = 'Run monitoring background tasks'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Check interval in seconds (default: 60)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once and exit'
        )
    
    def handle(self, *args, **options):
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        interval = options['interval']
        run_once = options['once']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting monitoring tasks (interval: {interval}s)'
            )
        )
        
        while self.running:
            try:
                # Run monitoring tasks
                self._run_monitoring_tasks()
                
                if run_once:
                    break
                
                # Wait for next interval
                time.sleep(interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f'Error in monitoring loop: {e}')
                )
                if run_once:
                    sys.exit(1)
                time.sleep(interval)
        
        self.stdout.write(self.style.SUCCESS('Monitoring stopped'))
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.running = False
        self.stdout.write(self.style.WARNING('Received shutdown signal'))
    
    def _run_monitoring_tasks(self):
        """Run all monitoring tasks"""
        start_time = time.time()
        
        self.stdout.write(f'Running monitoring tasks at {timezone.now()}')
        
        # 1. Check and send alerts
        alerts = check_and_send_alerts()
        if alerts:
            self.stdout.write(
                self.style.WARNING(f'  - Triggered {len(alerts)} alerts')
            )
        
        # 2. Clean old metrics
        self._clean_old_metrics()
        
        # 3. Export metrics snapshot
        self._export_metrics_snapshot()
        
        # 4. Check system health
        self._check_system_health()
        
        elapsed = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f'Monitoring tasks completed in {elapsed:.2f}s'
            )
        )
    
    def _clean_old_metrics(self):
        """Clean metrics older than retention period"""
        retention_hours = monitoring_config.METRICS_RETENTION_HOURS
        
        # This is a simplified version - in production you'd want
        # to persist metrics to a time-series database
        with metrics_collector.lock:
            for metric_type in list(metrics_collector.metrics.keys()):
                # Keep only recent metrics
                cutoff_time = time.time() - (retention_hours * 3600)
                metrics_collector.metrics[metric_type] = [
                    m for m in metrics_collector.metrics[metric_type]
                    if datetime.fromisoformat(m['timestamp']).timestamp() > cutoff_time
                ]
    
    def _export_metrics_snapshot(self):
        """Export current metrics snapshot for external systems"""
        # This could export to:
        # - Time-series database (InfluxDB, Prometheus)
        # - Cloud monitoring (CloudWatch, Stackdriver)
        # - APM systems (New Relic, Datadog)
        
        snapshot = {
            'timestamp': timezone.now().isoformat(),
            'response_time': metrics_collector.get_stats('response_time', 5),
            'query_performance': metrics_collector.get_stats('query_time', 5),
            'error_rate': self._calculate_error_rate(5),
            'cache_hit_rate': self._calculate_cache_hit_rate(5)
        }
        
        # Log snapshot (in production, send to monitoring system)
        self.stdout.write(f'  - Metrics snapshot: {snapshot}')
    
    def _check_system_health(self):
        """Check overall system health"""
        from monitoring.views import HealthCheckView
        
        # Database health
        db_health = HealthCheckView.check_database()
        if db_health['status'] != 'healthy':
            self.stderr.write(
                self.style.ERROR(f"  - Database unhealthy: {db_health}")
            )
        
        # Cache health
        cache_health = HealthCheckView.check_cache()
        if cache_health['status'] != 'healthy':
            self.stderr.write(
                self.style.ERROR(f"  - Cache unhealthy: {cache_health}")
            )
    
    def _calculate_error_rate(self, window_minutes):
        """Calculate error rate"""
        total = metrics_collector.get_stats('request', window_minutes).get('count', 0)
        errors = metrics_collector.get_stats('error', window_minutes).get('count', 0)
        return (errors / total) if total > 0 else 0
    
    def _calculate_cache_hit_rate(self, window_minutes):
        """Calculate cache hit rate"""
        hits = metrics_collector.get_stats('cache_hit', window_minutes).get('count', 0)
        misses = metrics_collector.get_stats('cache_miss', window_minutes).get('count', 0)
        total = hits + misses
        return (hits / total) if total > 0 else 0