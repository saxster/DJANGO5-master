"""
Django management command for Redis Sentinel administration.

Usage:
    python manage.py sentinel_admin --status
    python manage.py sentinel_admin --failover-test
    python manage.py sentinel_admin --validate
    python manage.py sentinel_admin --masters
    python manage.py sentinel_admin --replicas
"""

import json
import time
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS



class Command(BaseCommand):
    help = 'Administer Redis Sentinel cluster - status, failover testing, validation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show overall Sentinel cluster status'
        )

        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate Sentinel configuration and connectivity'
        )

        parser.add_argument(
            '--masters',
            action='store_true',
            help='Show information about monitored masters'
        )

        parser.add_argument(
            '--replicas',
            action='store_true',
            help='Show information about replicas'
        )

        parser.add_argument(
            '--failover-test',
            action='store_true',
            help='Test failover capability (simulation only - does not trigger actual failover)'
        )

        parser.add_argument(
            '--trigger-failover',
            action='store_true',
            help='DANGEROUS: Trigger actual failover for testing'
        )

        parser.add_argument(
            '--master-name',
            type=str,
            default='mymaster',
            help='Master service name (default: mymaster)'
        )

        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format'
        )

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1))
        json_output = options.get('json', False)

        try:
            # Check if Sentinel is enabled
            from django.conf import settings
            import os

            if not os.environ.get('REDIS_SENTINEL_ENABLED') == 'true':
                raise CommandError(
                    "Redis Sentinel is not enabled. Set REDIS_SENTINEL_ENABLED=true to use Sentinel mode."
                )

            # Determine operation
            if options.get('status'):
                result = self._get_cluster_status(options)
            elif options.get('validate'):
                result = self._validate_configuration(options)
            elif options.get('masters'):
                result = self._get_masters_info(options)
            elif options.get('replicas'):
                result = self._get_replicas_info(options)
            elif options.get('failover_test'):
                result = self._test_failover_capability(options)
            elif options.get('trigger_failover'):
                result = self._trigger_failover(options)
            else:
                # Default to status
                result = self._get_cluster_status(options)

            # Output results
            if json_output:
                self.stdout.write(json.dumps(result, indent=2, default=str))
            else:
                self._display_formatted_result(result, verbosity)

        except DATABASE_EXCEPTIONS as e:
            if json_output:
                error_result = {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
                self.stdout.write(json.dumps(error_result, indent=2))
            else:
                raise CommandError(f'Sentinel operation failed: {e}')

    def _get_cluster_status(self, options):
        """Get overall Sentinel cluster status."""
        from apps.core.health_checks.sentinel import (
            check_sentinel_cluster_health,
            check_master_replica_status,
            check_sentinel_quorum
        )

        # Run all health checks
        cluster_health = check_sentinel_cluster_health()
        replication_status = check_master_replica_status()
        quorum_status = check_sentinel_quorum()

        return {
            'operation': 'cluster_status',
            'timestamp': timezone.now(),
            'overall_status': self._calculate_overall_status([
                cluster_health['status'],
                replication_status['status'],
                quorum_status['status']
            ]),
            'cluster_health': cluster_health,
            'replication_status': replication_status,
            'quorum_status': quorum_status
        }

    def _validate_configuration(self, options):
        """Validate Sentinel configuration."""
        from intelliwiz_config.settings.redis_sentinel import validate_sentinel_configuration

        validation_results = validate_sentinel_configuration()

        return {
            'operation': 'validate_configuration',
            'timestamp': timezone.now(),
            'validation_results': validation_results,
            'overall_status': 'healthy' if validation_results['valid'] else 'error'
        }

    def _get_masters_info(self, options):
        """Get detailed information about monitored masters."""
        try:
            from intelliwiz_config.settings.redis_sentinel import get_sentinel_settings
            import redis.sentinel

            sentinel_settings = get_sentinel_settings()
            sentinel = redis.sentinel.Sentinel(
                sentinel_settings['sentinels'],
                sentinel_kwargs=sentinel_settings['sentinel_kwargs']
            )

            masters_info = sentinel.sentinel_masters()

            return {
                'operation': 'masters_info',
                'timestamp': timezone.now(),
                'masters_count': len(masters_info),
                'masters': [
                    {
                        'name': master.get('name'),
                        'ip': master.get('ip'),
                        'port': master.get('port'),
                        'status': master.get('flags'),
                        'last_ping_reply': master.get('last-ping-reply'),
                        'num_slaves': master.get('num-slaves', 0),
                        'quorum': master.get('quorum'),
                        'parallel_syncs': master.get('parallel-syncs'),
                        'down_after_milliseconds': master.get('down-after-milliseconds'),
                        'failover_timeout': master.get('failover-timeout')
                    }
                    for master in masters_info
                ]
            }

        except DATABASE_EXCEPTIONS as e:
            raise CommandError(f"Failed to get masters info: {e}")

    def _get_replicas_info(self, options):
        """Get detailed information about replicas."""
        try:
            from intelliwiz_config.settings.redis_sentinel import get_sentinel_settings
            import redis.sentinel

            sentinel_settings = get_sentinel_settings()
            master_name = options.get('master_name', 'mymaster')

            sentinel = redis.sentinel.Sentinel(
                sentinel_settings['sentinels'],
                sentinel_kwargs=sentinel_settings['sentinel_kwargs']
            )

            replicas_info = sentinel.sentinel_slaves(master_name)

            return {
                'operation': 'replicas_info',
                'timestamp': timezone.now(),
                'master_name': master_name,
                'replicas_count': len(replicas_info),
                'replicas': [
                    {
                        'name': replica.get('name'),
                        'ip': replica.get('ip'),
                        'port': replica.get('port'),
                        'status': replica.get('flags'),
                        'last_ping_reply': replica.get('last-ping-reply'),
                        'master_link_down_time': replica.get('master-link-down-time'),
                        'master_link_status': replica.get('master-link-status'),
                        'replica_priority': replica.get('slave-priority'),
                        'replica_repl_offset': replica.get('slave-repl-offset'),
                        'replica_lag': replica.get('slave-lag')
                    }
                    for replica in replicas_info
                ]
            }

        except DATABASE_EXCEPTIONS as e:
            raise CommandError(f"Failed to get replicas info: {e}")

    def _test_failover_capability(self, options):
        """Test failover capability without triggering actual failover."""
        from apps.core.health_checks.sentinel import check_sentinel_failover_capability

        failover_test = check_sentinel_failover_capability()

        return {
            'operation': 'failover_test',
            'timestamp': timezone.now(),
            'test_result': failover_test,
            'failover_ready': failover_test['status'] == 'healthy'
        }

    def _trigger_failover(self, options):
        """DANGEROUS: Trigger actual failover."""
        master_name = options.get('master_name', 'mymaster')

        # Multiple confirmations for safety
        self.stdout.write(
            self.style.ERROR(
                "\n🚨 CRITICAL WARNING: You are about to trigger a Redis failover!"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "This will cause a brief service interruption and promote a replica to master."
            )
        )

        # In a real implementation, you would need interactive confirmation
        # For now, return a warning
        return {
            'operation': 'trigger_failover',
            'timestamp': timezone.now(),
            'status': 'aborted',
            'message': 'Failover not implemented in management command for safety. Use Redis CLI: SENTINEL FAILOVER mymaster'
        }

    def _calculate_overall_status(self, statuses):
        """Calculate overall status from multiple check results."""
        if 'error' in statuses:
            return 'error'
        elif 'degraded' in statuses:
            return 'degraded'
        else:
            return 'healthy'

    def _display_formatted_result(self, result, verbosity):
        """Display results in human-readable format."""
        operation = result.get('operation', 'unknown')

        # Header
        self.stdout.write(
            self.style.HTTP_INFO('=' * 70)
        )
        self.stdout.write(
            self.style.HTTP_INFO(f'Redis Sentinel Administration: {operation.title().replace("_", " ")}')
        )
        self.stdout.write(
            self.style.HTTP_INFO('=' * 70)
        )

        if operation == 'cluster_status':
            self._display_cluster_status(result, verbosity)
        elif operation == 'validate_configuration':
            self._display_validation_results(result, verbosity)
        elif operation == 'masters_info':
            self._display_masters_info(result, verbosity)
        elif operation == 'replicas_info':
            self._display_replicas_info(result, verbosity)
        elif operation == 'failover_test':
            self._display_failover_test(result, verbosity)

        self.stdout.write(
            self.style.HTTP_INFO('=' * 70)
        )

    def _display_cluster_status(self, result, verbosity):
        """Display cluster status results."""
        overall_status = result['overall_status']

        # Overall status
        status_style = {
            'healthy': self.style.SUCCESS,
            'degraded': self.style.WARNING,
            'error': self.style.ERROR
        }.get(overall_status, self.style.NOTICE)

        self.stdout.write(
            status_style(f"Overall Status: {overall_status.upper()}")
        )
        self.stdout.write("")

        # Individual check results
        checks = [
            ('Cluster Health', result['cluster_health']),
            ('Replication Status', result['replication_status']),
            ('Quorum Status', result['quorum_status'])
        ]

        for check_name, check_result in checks:
            status = check_result['status']
            message = check_result['message']

            status_style = {
                'healthy': self.style.SUCCESS,
                'degraded': self.style.WARNING,
                'error': self.style.ERROR
            }.get(status, self.style.NOTICE)

            self.stdout.write(
                status_style(f"  {check_name}: {status.upper()}")
            )
            self.stdout.write(f"    {message}")

            if verbosity >= 2 and check_result.get('details'):
                self.stdout.write(f"    Duration: {check_result.get('duration_ms', 0):.1f}ms")

        self.stdout.write("")

    def _display_validation_results(self, result, verbosity):
        """Display validation results."""
        validation = result['validation_results']

        if validation['valid']:
            self.stdout.write(
                self.style.SUCCESS("✅ Sentinel configuration is valid!")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ Sentinel configuration validation failed!")
            )

        if validation['errors']:
            self.stdout.write("\nErrors:")
            for error in validation['errors']:
                self.stdout.write(
                    self.style.ERROR(f"  - {error}")
                )

        if validation['warnings']:
            self.stdout.write("\nWarnings:")
            for warning in validation['warnings']:
                self.stdout.write(
                    self.style.WARNING(f"  - {warning}")
                )

        if verbosity >= 2:
            self.stdout.write(f"\nSentinel nodes: {len(validation['sentinel_nodes'])}")
            for node in validation['sentinel_nodes']:
                self.stdout.write(f"  Node {node['node']}: {node['status']}")

    def _display_masters_info(self, result, verbosity):
        """Display masters information."""
        masters = result['masters']

        self.stdout.write(f"Monitored Masters: {len(masters)}")

        for master in masters:
            status_style = (
                self.style.SUCCESS if 'master' in master['status']
                else self.style.ERROR
            )

            self.stdout.write("")
            self.stdout.write(
                status_style(f"📊 Master: {master['name']}")
            )
            self.stdout.write(f"   Address: {master['ip']}:{master['port']}")
            self.stdout.write(f"   Status: {master['status']}")
            self.stdout.write(f"   Replicas: {master['num_slaves']}")
            self.stdout.write(f"   Quorum: {master['quorum']}")

            if verbosity >= 2:
                self.stdout.write(f"   Last Ping: {master['last_ping_reply']}ms")
                self.stdout.write(f"   Failover Timeout: {master['failover_timeout']}ms")

    def _display_replicas_info(self, result, verbosity):
        """Display replicas information."""
        replicas = result['replicas']

        self.stdout.write(f"Replicas for {result['master_name']}: {len(replicas)}")

        for replica in replicas:
            status_style = (
                self.style.SUCCESS if 'slave' in replica['status']
                else self.style.ERROR
            )

            self.stdout.write("")
            self.stdout.write(
                status_style(f"📊 Replica: {replica['name']}")
            )
            self.stdout.write(f"   Address: {replica['ip']}:{replica['port']}")
            self.stdout.write(f"   Status: {replica['status']}")
            self.stdout.write(f"   Priority: {replica['replica_priority']}")
            self.stdout.write(f"   Link Status: {replica['master_link_status']}")

            if verbosity >= 2:
                self.stdout.write(f"   Last Ping: {replica['last_ping_reply']}ms")
                self.stdout.write(f"   Repl Offset: {replica['replica_repl_offset']}")
                self.stdout.write(f"   Link Down Time: {replica['master_link_down_time']}")

    def _display_failover_test(self, result, verbosity):
        """Display failover test results."""
        test_result = result['test_result']
        failover_ready = result['failover_ready']

        if failover_ready:
            self.stdout.write(
                self.style.SUCCESS("✅ Failover capability test PASSED!")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ Failover capability test FAILED!")
            )

        self.stdout.write(f"\nTest Message: {test_result['message']}")

        if verbosity >= 2 and test_result.get('details'):
            details = test_result['details']
            self.stdout.write("\nDetailed Results:")
            self.stdout.write(f"  Can Discover Master: {'✅' if details['can_discover_master'] else '❌'}")
            self.stdout.write(f"  Can Discover Replicas: {'✅' if details['can_discover_replicas'] else '❌'}")
            self.stdout.write(f"  Sufficient Replicas: {'✅' if details['sufficient_replicas'] else '❌'}")
            self.stdout.write(f"  Quorum Available: {'✅' if details['quorum_available'] else '❌'}")
            self.stdout.write(f"  Failover Ready: {'✅' if details['failover_ready'] else '❌'}")