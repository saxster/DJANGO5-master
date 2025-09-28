"""
Management command to run stream test scenarios
"""

import asyncio
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.streamlab.models import TestScenario, TestRun
from apps.streamlab.services.event_capture import stream_event_capture

User = get_user_model()
logger = logging.getLogger('streamlab.commands')


class Command(BaseCommand):
    help = 'Run a stream test scenario'

    def add_arguments(self, parser):
        parser.add_argument(
            'scenario_name',
            type=str,
            help='Name of the test scenario to run'
        )
        parser.add_argument(
            '--user',
            type=str,
            default='admin',
            help='Username to run the scenario as'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=300,
            help='Test duration in seconds (default: 300)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually running'
        )

    def handle(self, *args, **options):
        scenario_name = options['scenario_name']
        username = options['user']
        duration = options['duration']
        dry_run = options['dry_run']

        try:
            # Get scenario
            scenario = TestScenario.objects.get(name=scenario_name, is_active=True)

            # Get user
            user = User.objects.get(username=username)

            self.stdout.write(f"🎯 Running scenario: {scenario.name}")
            self.stdout.write(f"👤 User: {user.username}")
            self.stdout.write(f"⏱️  Duration: {duration} seconds")
            self.stdout.write(f"🔌 Protocol: {scenario.protocol}")
            self.stdout.write(f"📡 Endpoint: {scenario.endpoint}")

            if dry_run:
                self.stdout.write(
                    self.style.WARNING("🚫 Dry run mode - not actually executing")
                )
                return

            # Create test run
            test_run = TestRun.objects.create(
                scenario=scenario,
                started_by=user,
                runtime_config={
                    'duration_seconds': duration,
                    'command_line': True
                }
            )

            self.stdout.write(
                self.style.SUCCESS(f"✅ Created test run: {test_run.id}")
            )

            # Start event capture
            asyncio.run(self._run_scenario(test_run, duration))

        except TestScenario.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ Scenario '{scenario_name}' not found")
            )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ User '{username}' not found")
            )
        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, asyncio.CancelledError) as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error running scenario: {e}")
            )
            logger.error(f"Scenario run error: {e}", exc_info=True)

    async def _run_scenario(self, test_run: TestRun, duration: int):
        """Run the scenario asynchronously"""
        try:
            # Start event capture
            await stream_event_capture.start_test_run_capture(str(test_run.id))

            self.stdout.write(
                self.style.SUCCESS(f"🚀 Started test run {test_run.id}")
            )

            # For now, just wait for the duration
            # In a real implementation, this would trigger the load generators
            self.stdout.write("⏳ Waiting for test to complete...")

            # Simulate scenario execution
            await asyncio.sleep(min(duration, 10))  # Cap at 10 seconds for demo

            # Stop event capture
            await stream_event_capture.stop_test_run_capture(str(test_run.id))

            self.stdout.write(
                self.style.SUCCESS(f"✅ Completed test run {test_run.id}")
            )

            # Display results
            test_run.refresh_from_db()
            self._display_results(test_run)

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, asyncio.CancelledError) as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Scenario execution error: {e}")
            )
            test_run.mark_failed(str(e))

    def _display_results(self, test_run: TestRun):
        """Display test results"""
        self.stdout.write("\n" + "="*50)
        self.stdout.write("📊 TEST RESULTS")
        self.stdout.write("="*50)

        self.stdout.write(f"Status: {test_run.status}")
        self.stdout.write(f"Total Events: {test_run.total_events}")
        self.stdout.write(f"Successful: {test_run.successful_events}")
        self.stdout.write(f"Failed: {test_run.failed_events}")
        self.stdout.write(f"Anomalies: {test_run.anomalies_detected}")

        if test_run.error_rate is not None:
            self.stdout.write(f"Error Rate: {test_run.error_rate:.1%}")

        if test_run.p95_latency_ms is not None:
            self.stdout.write(f"P95 Latency: {test_run.p95_latency_ms:.1f}ms")

        if test_run.throughput_qps is not None:
            self.stdout.write(f"Throughput: {test_run.throughput_qps:.1f} QPS")

        # SLO status
        slo_met = test_run.is_within_slo
        if slo_met is not None:
            if slo_met:
                self.stdout.write(
                    self.style.SUCCESS("✅ SLO Requirements: MET")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("❌ SLO Requirements: FAILED")
                )

        self.stdout.write(f"\nTest Run ID: {test_run.id}")
        self.stdout.write("="*50)