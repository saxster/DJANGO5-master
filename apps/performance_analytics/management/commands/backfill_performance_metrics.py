"""
Backfill Performance Metrics Management Command

Backfill historical performance data for a date range.

Usage:
    python manage.py backfill_performance_metrics --days=90
    python manage.py backfill_performance_metrics --start=2025-10-01 --end=2025-11-01
    python manage.py backfill_performance_metrics --workers=user1,user2 --days=30

Compliance:
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta, date as date_class
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.performance_analytics.services.metrics_aggregator import MetricsAggregator
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS

logger = logging.getLogger('performance_analytics.commands')


class Command(BaseCommand):
    """Backfill historical performance metrics."""
    
    help = 'Backfill performance metrics for historical date range'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--days',
            type=int,
            help='Number of days to backfill from today (e.g., 90)',
        )
        parser.add_argument(
            '--start',
            type=str,
            help='Start date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end',
            type=str,
            help='End date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--workers',
            type=str,
            help='Comma-separated worker loginids (optional, processes all if not specified)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output',
        )
    
    def handle(self, *args, **options):
        """Execute backfill command."""
        try:
            # Determine date range
            if options['days']:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=options['days'])
            elif options['start'] and options['end']:
                start_date = date_class.fromisoformat(options['start'])
                end_date = date_class.fromisoformat(options['end'])
            else:
                raise CommandError(
                    "Must specify either --days or both --start and --end"
                )
            
            # Validate date range
            if start_date > end_date:
                raise CommandError("Start date must be before end date")
            
            days_to_process = (end_date - start_date).days + 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting backfill: {start_date} to {end_date} ({days_to_process} days)"
                )
            )
            
            # Parse worker filter
            worker_filter = None
            if options['workers']:
                worker_filter = [w.strip() for w in options['workers'].split(',')]
                self.stdout.write(f"  Filtering to workers: {', '.join(worker_filter)}")
            
            # Process each date
            current_date = start_date
            dates_processed = 0
            total_workers_processed = 0
            errors = []
            
            while current_date <= end_date:
                try:
                    if options['verbose']:
                        self.stdout.write(f"  Processing {current_date}...")
                    
                    # Run aggregation
                    result = MetricsAggregator.aggregate_all_metrics(
                        target_date=current_date,
                        worker_filter=worker_filter
                    )
                    
                    dates_processed += 1
                    total_workers_processed += result['workers_processed']
                    
                    if options['verbose']:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"    ✓ {result['workers_processed']} workers, "
                                f"{result['teams_updated']} teams"
                            )
                        )
                    
                except (DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS) as e:
                    errors.append({'date': current_date, 'error': str(e)})
                    self.stdout.write(
                        self.style.WARNING(
                            f"    ✗ Error processing {current_date}: {e}"
                        )
                    )
                
                current_date += timedelta(days=1)
            
            # Summary
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.SUCCESS("BACKFILL COMPLETE"))
            self.stdout.write("="*60)
            self.stdout.write(f"  Dates processed: {dates_processed}/{days_to_process}")
            self.stdout.write(f"  Workers processed: {total_workers_processed}")
            
            if errors:
                self.stdout.write(
                    self.style.WARNING(f"  Errors: {len(errors)}")
                )
                for err in errors:
                    self.stdout.write(f"    - {err['date']}: {err['error']}")
            else:
                self.stdout.write(self.style.SUCCESS("  No errors ✓"))
            
            # Update cohort benchmarks after backfill
            self.stdout.write("\n  Updating cohort benchmarks...")
            from apps.performance_analytics.services.cohort_analyzer import CohortAnalyzer
            
            benchmark_result = CohortAnalyzer.update_all_cohort_benchmarks(
                start_date, end_date
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ {benchmark_result['cohorts_updated']} cohorts updated"
                )
            )
            
        except (ValueError, TypeError) as e:
            raise CommandError(f"Invalid argument: {e}")
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n\nBackfill interrupted by user"))
            raise CommandError("Backfill cancelled")
