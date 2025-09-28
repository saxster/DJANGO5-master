"""
Continuous health monitoring management command.
Runs health checks periodically and logs results for trend analysis.
Follows Rule 11: Specific exception handling only.
"""

import time
import logging
from django.core.management.base import BaseCommand
from django.db import DatabaseError
from apps.core.services.health_check_service import HealthCheckService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run continuous health monitoring with periodic checks"

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Check interval in seconds (default: 60)',
        )
        parser.add_argument(
            '--max-iterations',
            type=int,
            default=0,
            help='Maximum iterations (0 = infinite, default: 0)',
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress output except errors',
        )

    def handle(self, *args, **options):
        interval = options['interval']
        max_iterations = options['max_iterations']
        quiet = options['quiet']

        health_service = HealthCheckService()

        if not quiet:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting continuous health monitoring (interval: {interval}s)"
                )
            )

        iteration = 0

        try:
            while max_iterations == 0 or iteration < max_iterations:
                iteration += 1

                try:
                    result = health_service.run_all_checks(
                        log_results=True, update_availability=True
                    )

                    if not quiet:
                        status_style = self.style.SUCCESS
                        if result["status"] == "degraded":
                            status_style = self.style.WARNING
                        elif result["status"] == "unhealthy":
                            status_style = self.style.ERROR

                        self.stdout.write(
                            status_style(
                                f"[{iteration}] Health check: {result['status']} - "
                                f"{result['summary']['healthy']}/{result['summary']['total_checks']} checks passed"
                            )
                        )

                        if result["status"] != "healthy":
                            for check_name, check_result in result["checks"].items():
                                if check_result["status"] != "healthy":
                                    self.stdout.write(
                                        f"  - {check_name}: {check_result['status']} - {check_result.get('message', 'N/A')}"
                                    )

                except DatabaseError as e:
                    logger.error(
                        f"Health check iteration {iteration} database error: {e}",
                        extra={"iteration": iteration, "error_type": "DatabaseError"},
                    )
                    if not quiet:
                        self.stdout.write(
                            self.style.ERROR(f"Database error during health check: {e}")
                        )

                except (ConnectionError, TimeoutError) as e:
                    logger.error(
                        f"Health check iteration {iteration} connection error: {e}",
                        extra={"iteration": iteration, "error_type": type(e).__name__},
                    )
                    if not quiet:
                        self.stdout.write(
                            self.style.ERROR(f"Connection error during health check: {e}")
                        )

                if max_iterations == 0 or iteration < max_iterations:
                    time.sleep(interval)

        except KeyboardInterrupt:
            if not quiet:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nStopping health monitoring after {iteration} iterations"
                    )
                )
            return

        if not quiet:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Completed {iteration} health check iterations"
                )
            )