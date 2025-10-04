#!/usr/bin/env python3

"""
Celery Queue Performance Monitor

Comprehensive monitoring script for the multi-queue Celery architecture.
Provides real-time metrics, alerts, and performance analysis.

Usage:
    python scripts/celery_monitor.py --mode=dashboard
    python scripts/celery_monitor.py --mode=alerts --threshold-critical=30
    python scripts/celery_monitor.py --mode=export --format=json
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Django setup
sys.path.append('/Users/amar/Desktop/MyCode/DJANGO5-master')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')

import django
django.setup()

from celery import Celery
from django.conf import settings
from django.core.cache import cache
from apps.core.tasks.base import TaskMetrics


class CeleryMonitor:
    """Comprehensive Celery monitoring and alerting system"""

    def __init__(self):
        self.app = Celery('intelliwiz_config')
        self.app.config_from_object(settings, namespace='CELERY')

        # Queue configuration from settings
        self.queue_config = {
            'critical': {'priority': 10, 'alert_threshold': 5, 'critical_threshold': 10},
            'high_priority': {'priority': 8, 'alert_threshold': 20, 'critical_threshold': 50},
            'email': {'priority': 7, 'alert_threshold': 30, 'critical_threshold': 100},
            'reports': {'priority': 6, 'alert_threshold': 50, 'critical_threshold': 200},
            'external_api': {'priority': 5, 'alert_threshold': 15, 'critical_threshold': 40},
            'maintenance': {'priority': 3, 'alert_threshold': 100, 'critical_threshold': 500},
            'default': {'priority': 5, 'alert_threshold': 25, 'critical_threshold': 100}
        }

    def get_worker_stats(self) -> Dict[str, Any]:
        """Get comprehensive worker statistics"""
        try:
            inspect = self.app.control.inspect()

            stats = {
                'active_workers': [],
                'total_active_tasks': 0,
                'workers_by_queue': {},
                'memory_usage': {},
                'worker_status': {}
            }

            # Get active workers
            active = inspect.active()
            if active:
                for worker, tasks in active.items():
                    stats['active_workers'].append(worker)
                    stats['total_active_tasks'] += len(tasks)

                    # Group by queue
                    for task in tasks:
                        queue = task.get('delivery_info', {}).get('routing_key', 'unknown')
                        if queue not in stats['workers_by_queue']:
                            stats['workers_by_queue'][queue] = 0
                        stats['workers_by_queue'][queue] += 1

            # Get worker status
            registered = inspect.registered()
            if registered:
                for worker, tasks in registered.items():
                    stats['worker_status'][worker] = {
                        'registered_tasks': len(tasks),
                        'status': 'active' if worker in stats['active_workers'] else 'inactive'
                    }

            return stats

        except Exception as e:
            return {'error': f"Failed to get worker stats: {e}"}

    def get_queue_depths(self) -> Dict[str, int]:
        """Get current queue depths"""
        try:
            inspect = self.app.control.inspect()
            queue_lengths = {}

            # Try to get queue lengths from broker
            reserved = inspect.reserved()
            active = inspect.active()

            for queue_name in self.queue_config.keys():
                total_tasks = 0

                if reserved:
                    for worker, tasks in reserved.items():
                        total_tasks += len([t for t in tasks
                                         if t.get('delivery_info', {}).get('routing_key') == queue_name])

                if active:
                    for worker, tasks in active.items():
                        total_tasks += len([t for t in tasks
                                         if t.get('delivery_info', {}).get('routing_key') == queue_name])

                queue_lengths[queue_name] = total_tasks

            return queue_lengths

        except Exception as e:
            return {queue: 0 for queue in self.queue_config.keys()}

    def get_task_metrics(self) -> Dict[str, Any]:
        """Get task performance metrics from cache"""
        metrics = {}

        # Get metrics from TaskMetrics cache
        for metric_type in ['task_started', 'task_success', 'task_failure', 'task_retry']:
            cache_keys = cache.keys(f"task_metrics:{metric_type}:*")
            for key in cache_keys:
                value = cache.get(key, 0)
                if value > 0:
                    metrics[key] = value

        # Calculate derived metrics
        if metrics:
            total_started = sum(v for k, v in metrics.items() if 'task_started' in k)
            total_success = sum(v for k, v in metrics.items() if 'task_success' in k)
            total_failed = sum(v for k, v in metrics.items() if 'task_failure' in k)

            if total_started > 0:
                metrics['success_rate'] = (total_success / total_started) * 100
                metrics['failure_rate'] = (total_failed / total_started) * 100

        return metrics

    def check_alerts(self, critical_threshold: int = 30) -> List[Dict[str, Any]]:
        """Check for performance alerts"""
        alerts = []
        queue_depths = self.get_queue_depths()
        current_time = datetime.now()

        # Check queue depth alerts
        for queue_name, depth in queue_depths.items():
            config = self.queue_config.get(queue_name, {})
            alert_threshold = config.get('alert_threshold', 25)
            critical_level = config.get('critical_threshold', critical_threshold)

            if depth > critical_level:
                alerts.append({
                    'type': 'CRITICAL',
                    'queue': queue_name,
                    'metric': 'queue_depth',
                    'value': depth,
                    'threshold': critical_level,
                    'timestamp': current_time.isoformat(),
                    'message': f"Queue {queue_name} has {depth} pending tasks (critical: {critical_level})"
                })
            elif depth > alert_threshold:
                alerts.append({
                    'type': 'WARNING',
                    'queue': queue_name,
                    'metric': 'queue_depth',
                    'value': depth,
                    'threshold': alert_threshold,
                    'timestamp': current_time.isoformat(),
                    'message': f"Queue {queue_name} has {depth} pending tasks (warning: {alert_threshold})"
                })

        # Check worker health
        worker_stats = self.get_worker_stats()
        if 'error' in worker_stats:
            alerts.append({
                'type': 'CRITICAL',
                'queue': 'system',
                'metric': 'worker_connectivity',
                'value': 0,
                'threshold': 1,
                'timestamp': current_time.isoformat(),
                'message': f"Worker connectivity error: {worker_stats['error']}"
            })

        # Check task failure rates
        metrics = self.get_task_metrics()
        failure_rate = metrics.get('failure_rate', 0)

        if failure_rate > 20:  # 20% failure rate is critical
            alerts.append({
                'type': 'CRITICAL',
                'queue': 'system',
                'metric': 'failure_rate',
                'value': failure_rate,
                'threshold': 20,
                'timestamp': current_time.isoformat(),
                'message': f"Task failure rate is {failure_rate:.1f}% (critical: 20%)"
            })
        elif failure_rate > 10:  # 10% failure rate is warning
            alerts.append({
                'type': 'WARNING',
                'queue': 'system',
                'metric': 'failure_rate',
                'value': failure_rate,
                'threshold': 10,
                'timestamp': current_time.isoformat(),
                'message': f"Task failure rate is {failure_rate:.1f}% (warning: 10%)"
            })

        return alerts

    def display_dashboard(self):
        """Display real-time dashboard"""
        try:
            while True:
                os.system('clear')  # Clear screen
                print("=" * 80)
                print(f"CELERY MULTI-QUEUE DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 80)

                # Worker Statistics
                worker_stats = self.get_worker_stats()
                print(f"\n📊 WORKER STATISTICS:")
                print(f"   Active Workers: {len(worker_stats.get('active_workers', []))}")
                print(f"   Total Active Tasks: {worker_stats.get('total_active_tasks', 0)}")

                # Queue Depths
                queue_depths = self.get_queue_depths()
                print(f"\n🚦 QUEUE DEPTHS:")
                for queue_name, depth in queue_depths.items():
                    config = self.queue_config[queue_name]
                    status = "🔴" if depth > config['critical_threshold'] else "🟡" if depth > config['alert_threshold'] else "🟢"
                    print(f"   {status} {queue_name:<15}: {depth:>3} tasks (Priority: {config['priority']})")

                # Task Metrics
                metrics = self.get_task_metrics()
                print(f"\n📈 TASK METRICS:")
                if metrics:
                    success_rate = metrics.get('success_rate', 0)
                    failure_rate = metrics.get('failure_rate', 0)
                    print(f"   Success Rate: {success_rate:.1f}%")
                    print(f"   Failure Rate: {failure_rate:.1f}%")
                else:
                    print("   No metrics available")

                # Recent Alerts
                alerts = self.check_alerts()
                print(f"\n🚨 ALERTS ({len(alerts)}):")
                if alerts:
                    for alert in alerts[-5:]:  # Show last 5 alerts
                        icon = "🔴" if alert['type'] == 'CRITICAL' else "🟡"
                        print(f"   {icon} {alert['message']}")
                else:
                    print("   🟢 No alerts - All systems healthy")

                print(f"\n📝 Press Ctrl+C to exit")
                time.sleep(5)

        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")

    def export_metrics(self, format_type: str = 'json') -> str:
        """Export metrics in specified format"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'worker_stats': self.get_worker_stats(),
            'queue_depths': self.get_queue_depths(),
            'task_metrics': self.get_task_metrics(),
            'alerts': self.check_alerts()
        }

        if format_type.lower() == 'json':
            return json.dumps(data, indent=2)
        else:
            # Could add CSV, XML, etc.
            return json.dumps(data, indent=2)

    def run_health_check(self) -> bool:
        """Run comprehensive health check"""
        print("🏥 Running Celery Health Check...")

        all_healthy = True

        # Check worker connectivity
        worker_stats = self.get_worker_stats()
        if 'error' in worker_stats:
            print(f"❌ Worker Connectivity: FAILED - {worker_stats['error']}")
            all_healthy = False
        else:
            active_workers = len(worker_stats.get('active_workers', []))
            if active_workers == 0:
                print(f"❌ Worker Status: No active workers found")
                all_healthy = False
            else:
                print(f"✅ Worker Status: {active_workers} active workers")

        # Check queue health
        queue_depths = self.get_queue_depths()
        critical_queues = []

        for queue_name, depth in queue_depths.items():
            config = self.queue_config[queue_name]
            if depth > config['critical_threshold']:
                critical_queues.append(f"{queue_name}({depth})")

        if critical_queues:
            print(f"❌ Queue Health: Critical queues: {', '.join(critical_queues)}")
            all_healthy = False
        else:
            print(f"✅ Queue Health: All queues within normal limits")

        # Check task metrics
        metrics = self.get_task_metrics()
        failure_rate = metrics.get('failure_rate', 0)

        if failure_rate > 20:
            print(f"❌ Task Health: High failure rate ({failure_rate:.1f}%)")
            all_healthy = False
        else:
            print(f"✅ Task Health: Failure rate acceptable ({failure_rate:.1f}%)")

        print(f"\n🎯 Overall Health: {'✅ HEALTHY' if all_healthy else '❌ UNHEALTHY'}")
        return all_healthy


def main():
    parser = argparse.ArgumentParser(description='Celery Multi-Queue Monitor')
    parser.add_argument('--mode', choices=['dashboard', 'alerts', 'export', 'health'],
                       default='dashboard', help='Monitoring mode')
    parser.add_argument('--threshold-critical', type=int, default=30,
                       help='Critical threshold for alerts')
    parser.add_argument('--format', choices=['json', 'csv'], default='json',
                       help='Export format')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously (for alerts mode)')

    args = parser.parse_args()

    monitor = CeleryMonitor()

    if args.mode == 'dashboard':
        monitor.display_dashboard()

    elif args.mode == 'alerts':
        if args.continuous:
            try:
                while True:
                    alerts = monitor.check_alerts(args.threshold_critical)
                    if alerts:
                        print(f"\n🚨 ALERTS DETECTED - {datetime.now().strftime('%H:%M:%S')}")
                        for alert in alerts:
                            icon = "🔴" if alert['type'] == 'CRITICAL' else "🟡"
                            print(f"{icon} {alert['message']}")
                    time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                print("\nAlert monitoring stopped.")
        else:
            alerts = monitor.check_alerts(args.threshold_critical)
            if alerts:
                print("🚨 CURRENT ALERTS:")
                for alert in alerts:
                    icon = "🔴" if alert['type'] == 'CRITICAL' else "🟡"
                    print(f"{icon} {alert['message']}")
            else:
                print("🟢 No alerts - All systems healthy")

    elif args.mode == 'export':
        output = monitor.export_metrics(args.format)
        print(output)

    elif args.mode == 'health':
        healthy = monitor.run_health_check()
        sys.exit(0 if healthy else 1)


if __name__ == '__main__':
    main()