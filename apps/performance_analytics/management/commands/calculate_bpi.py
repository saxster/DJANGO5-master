"""
Calculate BPI Management Command

Calculate BPI scores for workers on a specific date or range.

Usage:
    python manage.py calculate_bpi --date=2025-11-05
    python manage.py calculate_bpi --yesterday
    python manage.py calculate_bpi --worker=john.smith

Compliance:
- Rule #11: Specific exception handling
"""

from datetime import timedelta, date as date_class
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.performance_analytics.services.metrics_aggregator import MetricsAggregator
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

People = get_user_model()


class Command(BaseCommand):
    """Calculate BPI scores for workers."""
    
    help = 'Calculate Balanced Performance Index for workers'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--date',
            type=str,
            help='Date to calculate (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--yesterday',
            action='store_true',
            help='Calculate for yesterday',
        )
        parser.add_argument(
            '--worker',
            type=str,
            help='Specific worker loginid (optional)',
        )
    
    def handle(self, *args, **options):
        """Execute BPI calculation."""
        try:
            # Determine target date
            if options['yesterday']:
                target_date = (timezone.now() - timedelta(days=1)).date()
            elif options['date']:
                target_date = date_class.fromisoformat(options['date'])
            else:
                raise CommandError("Must specify --date or --yesterday")
            
            self.stdout.write(f"Calculating BPI for {target_date}...")
            
            # Specific worker or all?
            if options['worker']:
                try:
                    worker = People.objects.get(loginid=options['worker'])
                    result = MetricsAggregator.aggregate_worker_metrics(worker, target_date)
                    
                    self.stdout.write(self.style.SUCCESS(f"\n✓ {worker.loginid}:"))
                    self.stdout.write(f"  BPI: {result['bpi']}/100")
                    self.stdout.write(f"  Band: {result['performance_band']}")
                    self.stdout.write(f"  Percentile: {result['bpi_percentile']}th")
                    self.stdout.write(f"  Components:")
                    for comp, score in result['components'].items():
                        self.stdout.write(f"    - {comp}: {score}/100")
                    
                except People.DoesNotExist:
                    raise CommandError(f"Worker not found: {options['worker']}")
            else:
                # Process all workers
                result = MetricsAggregator.aggregate_all_metrics(target_date)
                
                self.stdout.write(self.style.SUCCESS(f"\n✓ Processed:"))
                self.stdout.write(f"  Workers: {result['workers_processed']}")
                self.stdout.write(f"  Teams: {result['teams_updated']}")
                self.stdout.write(f"  Avg BPI: {result.get('avg_bpi', 0):.1f}")
            
        except DATABASE_EXCEPTIONS as e:
            raise CommandError(f"Database error: {e}")
        except (ValueError, TypeError) as e:
            raise CommandError(f"Invalid input: {e}")
