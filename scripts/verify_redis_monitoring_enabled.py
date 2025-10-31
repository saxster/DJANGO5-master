#!/usr/bin/env python
"""
Verify Redis Monitoring Tasks are Enabled in Celery Beat Schedule

Ensures that Redis performance monitoring, trend analysis, and capacity planning
tasks are properly configured in the Celery beat schedule.

Usage:
    python scripts/verify_redis_monitoring_enabled.py
    python scripts/verify_redis_monitoring_enabled.py --verbose
    python scripts/verify_redis_monitoring_enabled.py --add-missing
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')

# Initialize Django
import django
django.setup()

from django.conf import settings
from intelliwiz_config.celery import app as celery_app
from celery.schedules import crontab


# Expected Redis monitoring tasks
EXPECTED_MONITORING_TASKS = {
    'collect-redis-metrics': {
        'task': 'collect_redis_performance_metrics',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'description': 'Collect Redis performance metrics',
        'queue': 'maintenance',
        'priority': 'CRITICAL'
    },
    'analyze-redis-trends': {
        'task': 'analyze_redis_performance_trends',
        'schedule': crontab(minute=0),  # Every hour
        'description': 'Analyze Redis performance trends',
        'queue': 'maintenance',
        'priority': 'HIGH'
    },
    'redis-capacity-report': {
        'task': 'generate_redis_capacity_report',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
        'description': 'Generate Redis capacity planning report',
        'queue': 'maintenance',
        'priority': 'MEDIUM'
    },
}


def verify_beat_schedule():
    """Verify Redis monitoring tasks are in Celery beat schedule"""
    print("\n" + "="*80)
    print("REDIS MONITORING TASKS VERIFICATION")
    print("="*80)

    beat_schedule = celery_app.conf.beat_schedule
    print(f"\nTotal beat schedule entries: {len(beat_schedule)}")

    results = {
        'total_expected': len(EXPECTED_MONITORING_TASKS),
        'found': [],
        'missing': [],
        'misconfigured': []
    }

    for task_name, expected_config in EXPECTED_MONITORING_TASKS.items():
        print(f"\n{'─'*80}")
        print(f"Checking: {task_name}")
        print(f"Expected Task: {expected_config['task']}")
        print(f"Description: {expected_config['description']}")
        print(f"Priority: {expected_config['priority']}")

        if task_name in beat_schedule:
            actual_config = beat_schedule[task_name]
            print(f"✓ Found in beat schedule")

            # Verify task name matches
            if actual_config.get('task') == expected_config['task']:
                print(f"  ✓ Task name correct: {expected_config['task']}")
                results['found'].append(task_name)
            else:
                print(f"  ✗ Task name mismatch!")
                print(f"    Expected: {expected_config['task']}")
                print(f"    Found: {actual_config.get('task')}")
                results['misconfigured'].append(task_name)

            # Verify queue configuration
            queue = actual_config.get('options', {}).get('queue')
            if queue:
                print(f"  ✓ Queue: {queue}")
            else:
                print(f"  ⚠  Queue not specified (will use default)")

            # Show schedule
            schedule = actual_config.get('schedule')
            print(f"  ℹ  Schedule: {schedule}")

        else:
            print(f"✗ NOT FOUND in beat schedule!")
            print(f"  This monitoring task is not scheduled to run automatically")
            print(f"  Performance monitoring will be incomplete")
            results['missing'].append(task_name)

    return results


def verify_task_registration():
    """Verify monitoring task functions are actually registered with Celery"""
    print("\n" + "="*80)
    print("TASK REGISTRATION VERIFICATION")
    print("="*80)

    from celery import current_app
    registered_tasks = current_app.tasks

    results = {
        'expected_tasks': [],
        'registered': [],
        'missing': []
    }

    for task_name, config in EXPECTED_MONITORING_TASKS.items():
        task_full_name = config['task']
        results['expected_tasks'].append(task_full_name)

        print(f"\nChecking registration: {task_full_name}")

        if task_full_name in registered_tasks:
            print(f"  ✓ Task registered with Celery")
            task_obj = registered_tasks[task_full_name]
            print(f"    Module: {task_obj.__module__}")
            results['registered'].append(task_full_name)
        else:
            print(f"  ✗ Task NOT registered!")
            print(f"    This task cannot be executed by Celery")
            print(f"    Check: apps/core/tasks/redis_monitoring_tasks.py")
            results['missing'].append(task_full_name)

    return results


def test_monitoring_task_execution():
    """Test that monitoring tasks can be executed"""
    print("\n" + "="*80)
    print("MONITORING TASK EXECUTION TEST")
    print("="*80)

    try:
        from apps.core.tasks.redis_monitoring_tasks import (
            collect_redis_performance_metrics,
            analyze_redis_performance_trends,
            generate_redis_capacity_report
        )

        tasks_to_test = [
            ('collect_redis_performance_metrics', collect_redis_performance_metrics),
            ('analyze_redis_performance_trends', analyze_redis_performance_trends),
            ('generate_redis_capacity_report', generate_redis_capacity_report)
        ]

        results = []

        for task_name, task_func in tasks_to_test:
            print(f"\nTesting: {task_name}")

            try:
                # Queue task (don't wait for completion in verification)
                result = task_func.delay()
                print(f"  ✓ Task queued successfully")
                print(f"    Task ID: {result.id}")
                print(f"    State: {result.state}")
                results.append((task_name, True, None))

            except Exception as e:
                print(f"  ✗ Failed to queue task: {e}")
                results.append((task_name, False, str(e)))

        return results

    except ImportError as e:
        print(f"\n✗ Failed to import monitoring tasks: {e}")
        print(f"  Check: apps/core/tasks/redis_monitoring_tasks.py exists")
        return []


def print_summary(schedule_results, registration_results, execution_results):
    """Print comprehensive summary"""
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)

    # Beat schedule status
    print(f"\nBeat Schedule:")
    print(f"  Expected tasks: {schedule_results['total_expected']}")
    print(f"  Found: {len(schedule_results['found'])}")
    print(f"  Missing: {len(schedule_results['missing'])}")
    print(f"  Misconfigured: {len(schedule_results['misconfigured'])}")

    # Task registration status
    print(f"\nTask Registration:")
    print(f"  Expected: {len(registration_results['expected_tasks'])}")
    print(f"  Registered: {len(registration_results['registered'])}")
    print(f"  Missing: {len(registration_results['missing'])}")

    # Execution status
    if execution_results:
        print(f"\nTask Execution:")
        success_count = len([r for r in execution_results if r[1]])
        print(f"  Tested: {len(execution_results)}")
        print(f"  Success: {success_count}")
        print(f"  Failed: {len(execution_results) - success_count}")

    # Overall status
    print("\n" + "="*80)

    all_scheduled = len(schedule_results['missing']) == 0
    all_registered = len(registration_results['missing']) == 0
    all_executable = execution_results and all(r[1] for r in execution_results)

    if all_scheduled and all_registered and all_executable:
        print("✅ ALL REDIS MONITORING TASKS PROPERLY CONFIGURED")
        print("="*80)
        print("\nMonitoring is operational:")
        print("  - Metrics collected every 5 minutes")
        print("  - Trends analyzed hourly")
        print("  - Capacity reports generated daily at 6 AM")
        print("")
        print("Dashboard: http://localhost:8000/admin/redis/dashboard/")
        return 0
    else:
        print("❌ REDIS MONITORING INCOMPLETE")
        print("="*80)

        if not all_scheduled:
            print("\nMissing from beat schedule:")
            for task in schedule_results['missing']:
                print(f"  - {task}")
            print("\nAction: Add to intelliwiz_config/celery.py beat_schedule")

        if not all_registered:
            print("\nTasks not registered:")
            for task in registration_results['missing']:
                print(f"  - {task}")
            print("\nAction: Check apps/core/tasks/redis_monitoring_tasks.py")

        if execution_results and not all_executable:
            print("\nTasks failed execution:")
            for task_name, success, error in execution_results:
                if not success:
                    print(f"  - {task_name}: {error}")

        return 1


def main():
    """Main verification function"""
    import argparse

    parser = argparse.ArgumentParser(description='Verify Redis monitoring task configuration')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--test-execution', action='store_true', help='Test task execution (queues tasks)')
    args = parser.parse_args()

    print("Redis Monitoring Tasks Verification")
    print(f"Environment: {os.environ.get('DJANGO_ENVIRONMENT', 'development')}")

    # Verify beat schedule
    schedule_results = verify_beat_schedule()

    # Verify task registration
    registration_results = verify_task_registration()

    # Test execution (optional)
    execution_results = []
    if args.test_execution:
        execution_results = test_monitoring_task_execution()

    # Print summary
    return print_summary(schedule_results, registration_results, execution_results)


if __name__ == '__main__':
    sys.exit(main())
