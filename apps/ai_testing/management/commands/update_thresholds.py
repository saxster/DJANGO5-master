"""
AI Testing Management Command: Update Adaptive Thresholds
Update adaptive thresholds based on recent performance data and user behavior
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.ai_testing.services.adaptive_threshold_updater import AdaptiveThresholdUpdater
from apps.streamlab.models import TestRun, StreamEvent


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update adaptive thresholds based on recent performance data and user behavior'

    def add_arguments(self, parser):
        parser.add_argument(
            '--metric',
            choices=['all', 'latency', 'throughput', 'error_rate', 'anomaly_detection'],
            default='all',
            help='Update specific metric thresholds (default: all)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to analyze for threshold updates (default: 7)'
        )
        parser.add_argument(
            '--min-samples',
            type=int,
            default=100,
            help='Minimum number of samples required for threshold update (default: 100)'
        )
        parser.add_argument(
            '--sensitivity',
            choices=['low', 'medium', 'high'],
            default='medium',
            help='Sensitivity level for threshold adjustments (default: medium)'
        )
        parser.add_argument(
            '--force-update',
            action='store_true',
            help='Force update even if thresholds were recently updated'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without saving changes'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output with detailed threshold calculations'
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        metric = options['metric']
        days = options['days']
        min_samples = options['min_samples']
        sensitivity = options['sensitivity']
        force_update = options['force_update']
        dry_run = options['dry_run']
        verbose = options['verbose']

        self.stdout.write(
            self.style.SUCCESS('🎯 Starting Adaptive Threshold Updates')
        )
        self.stdout.write(f'Metric focus: {metric}')
        self.stdout.write(f'Analysis period: {days} days')
        self.stdout.write(f'Sensitivity: {sensitivity}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        try:
            # Initialize threshold updater
            updater = AdaptiveThresholdUpdater(
                sensitivity_level=sensitivity,
                min_samples=min_samples
            )

            # Set analysis window
            since_date = timezone.now() - timedelta(days=days)

            # Step 1: Collect performance data
            self.stdout.write('\n📊 Collecting performance data...')

            performance_data = self._collect_performance_data(since_date, verbose)

            if not performance_data['has_sufficient_data']:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Insufficient data for reliable threshold updates '
                        f'(minimum {min_samples} samples required)'
                    )
                )
                if not force_update:
                    return

            # Step 2: Get current thresholds
            current_thresholds = self._get_current_thresholds(metric)

            # Step 3: Calculate new thresholds
            self.stdout.write('\n🔧 Calculating new thresholds...')

            new_thresholds = updater.calculate_adaptive_thresholds(
                performance_data['metrics'],
                current_thresholds,
                force_update=force_update
            )

            # Step 4: Apply updates
            if new_thresholds:
                self.stdout.write('\n💾 Applying threshold updates...')

                update_results = self._apply_threshold_updates(
                    new_thresholds,
                    current_thresholds,
                    dry_run,
                    verbose
                )

                # Display results
                self._display_update_results(update_results, performance_data)

            else:
                self.stdout.write(
                    self.style.SUCCESS('✅ All thresholds are already optimal - no updates needed')
                )

            # Step 5: Cleanup stale thresholds
            if not dry_run:
                cleanup_results = self._cleanup_stale_thresholds(days * 3)  # Remove very old thresholds
                if cleanup_results['removed'] > 0:
                    self.stdout.write(f'🧹 Cleaned up {cleanup_results["removed"]} stale thresholds')

            # Execution time
            duration = timezone.now() - start_time
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Threshold updates completed in {duration.total_seconds():.1f}s'
                )
            )

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            logger.error(f'Threshold update failed: {str(e)}', exc_info=True)
            raise CommandError(f'Update failed: {str(e)}')

    def _collect_performance_data(self, since_date, verbose):
        """Collect performance data for threshold analysis"""
        test_runs = TestRun.objects.filter(
            started_at__gte=since_date,
            status='completed'
        )

        stream_events = StreamEvent.objects.filter(
            timestamp__gte=since_date
        )

        anomaly_occurrences = AnomalyOccurrence.objects.filter(
            created_at__gte=since_date
        )

        # Calculate aggregate metrics
        metrics = {
            'latency': self._calculate_latency_metrics(test_runs, stream_events),
            'throughput': self._calculate_throughput_metrics(test_runs),
            'error_rate': self._calculate_error_rate_metrics(test_runs, stream_events),
            'anomaly_detection': self._calculate_anomaly_metrics(anomaly_occurrences)
        }

        # Check if we have sufficient data
        total_samples = sum(
            m.get('sample_count', 0) for m in metrics.values()
        )

        data_summary = {
            'metrics': metrics,
            'total_samples': total_samples,
            'has_sufficient_data': total_samples >= 100,  # Minimum threshold
            'data_quality_score': min(1.0, total_samples / 1000)  # Quality score 0-1
        }

        if verbose:
            self.stdout.write(f'  - Test runs analyzed: {test_runs.count()}')
            self.stdout.write(f'  - Stream events analyzed: {stream_events.count()}')
            self.stdout.write(f'  - Anomaly occurrences: {anomaly_occurrences.count()}')
            self.stdout.write(f'  - Total samples: {total_samples}')
            self.stdout.write(f'  - Data quality: {data_summary["data_quality_score"]:.1%}')

        return data_summary

    def _calculate_latency_metrics(self, test_runs, stream_events):
        """Calculate latency-related metrics"""
        # P95 latencies from test runs
        p95_latencies = [
            run.p95_latency_ms for run in test_runs
            if run.p95_latency_ms is not None
        ]

        # Individual event latencies
        event_latencies = [
            event.latency_ms for event in stream_events
            if event.latency_ms is not None
        ]

        combined_latencies = p95_latencies + event_latencies

        if not combined_latencies:
            return {'sample_count': 0}

        combined_latencies.sort()
        n = len(combined_latencies)

        return {
            'sample_count': n,
            'mean': sum(combined_latencies) / n,
            'p50': combined_latencies[int(n * 0.5)],
            'p95': combined_latencies[int(n * 0.95)],
            'p99': combined_latencies[int(n * 0.99)],
            'min': min(combined_latencies),
            'max': max(combined_latencies),
            'std_dev': self._calculate_std_dev(combined_latencies)
        }

    def _calculate_throughput_metrics(self, test_runs):
        """Calculate throughput-related metrics"""
        throughputs = [
            run.throughput_qps for run in test_runs
            if run.throughput_qps is not None
        ]

        if not throughputs:
            return {'sample_count': 0}

        throughputs.sort()
        n = len(throughputs)

        return {
            'sample_count': n,
            'mean': sum(throughputs) / n,
            'p50': throughputs[int(n * 0.5)],
            'p95': throughputs[int(n * 0.95)],
            'min': min(throughputs),
            'max': max(throughputs),
            'std_dev': self._calculate_std_dev(throughputs)
        }

    def _calculate_error_rate_metrics(self, test_runs, stream_events):
        """Calculate error rate metrics"""
        # Test run error rates
        run_error_rates = [
            run.error_rate for run in test_runs
            if run.error_rate is not None
        ]

        # Stream event error rates (by time window)
        error_rates_by_window = []
        if stream_events.exists():
            # Group events by hour and calculate error rates
            events_by_hour = {}
            for event in stream_events:
                hour = event.timestamp.replace(minute=0, second=0, microsecond=0)
                if hour not in events_by_hour:
                    events_by_hour[hour] = {'total': 0, 'errors': 0}

                events_by_hour[hour]['total'] += 1
                if event.outcome == 'error':
                    events_by_hour[hour]['errors'] += 1

            error_rates_by_window = [
                data['errors'] / data['total'] if data['total'] > 0 else 0
                for data in events_by_hour.values()
            ]

        combined_error_rates = run_error_rates + error_rates_by_window

        if not combined_error_rates:
            return {'sample_count': 0}

        combined_error_rates.sort()
        n = len(combined_error_rates)

        return {
            'sample_count': n,
            'mean': sum(combined_error_rates) / n,
            'p50': combined_error_rates[int(n * 0.5)],
            'p95': combined_error_rates[int(n * 0.95)],
            'max': max(combined_error_rates),
            'std_dev': self._calculate_std_dev(combined_error_rates)
        }

    def _calculate_anomaly_metrics(self, anomaly_occurrences):
        """Calculate anomaly detection metrics"""
        if not anomaly_occurrences.exists():
            return {'sample_count': 0}

        # Group by signature and calculate frequency
        signature_counts = {}
        total_occurrences = 0

        for occurrence in anomaly_occurrences:
            sig_id = occurrence.signature.id
            signature_counts[sig_id] = signature_counts.get(sig_id, 0) + 1
            total_occurrences += 1

        frequencies = list(signature_counts.values())
        frequencies.sort()
        n = len(frequencies)

        return {
            'sample_count': total_occurrences,
            'unique_signatures': len(signature_counts),
            'mean_frequency': sum(frequencies) / n if n > 0 else 0,
            'p95_frequency': frequencies[int(n * 0.95)] if n > 0 else 0,
            'max_frequency': max(frequencies) if frequencies else 0,
            'total_occurrences': total_occurrences
        }

    def _calculate_std_dev(self, values):
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _get_current_thresholds(self, metric_filter):
        """Get current adaptive thresholds"""
        thresholds = AdaptiveThreshold.objects.all()

        if metric_filter != 'all':
            thresholds = thresholds.filter(metric_name=metric_filter)

        return {
            threshold.metric_name: threshold
            for threshold in thresholds
        }

    def _apply_threshold_updates(self, new_thresholds, current_thresholds, dry_run, verbose):
        """Apply threshold updates"""
        results = {
            'created': 0,
            'updated': 0,
            'unchanged': 0,
            'details': []
        }

        for metric_name, threshold_data in new_thresholds.items():
            current_threshold = current_thresholds.get(metric_name)

            if current_threshold:
                # Check if update is needed
                change_percentage = abs(
                    (threshold_data['value'] - current_threshold.value) /
                    current_threshold.value
                ) if current_threshold.value != 0 else 1.0

                if change_percentage > 0.05:  # 5% change threshold
                    if not dry_run:
                        current_threshold.value = threshold_data['value']
                        current_threshold.confidence_interval = threshold_data.get('confidence_interval', 0.95)
                        current_threshold.sample_count = threshold_data.get('sample_count', 0)
                        current_threshold.accuracy = threshold_data.get('accuracy', current_threshold.accuracy)
                        current_threshold.precision = threshold_data.get('precision', current_threshold.precision)
                        current_threshold.updated_at = timezone.now()
                        current_threshold.save()

                    results['updated'] += 1
                    results['details'].append({
                        'metric': metric_name,
                        'action': 'updated',
                        'old_value': current_threshold.value,
                        'new_value': threshold_data['value'],
                        'change_percent': change_percentage * 100
                    })

                    if verbose:
                        self.stdout.write(
                            f'  📈 {metric_name}: {current_threshold.value:.3f} → '
                            f'{threshold_data["value"]:.3f} ({change_percentage*100:+.1f}%)'
                        )
                else:
                    results['unchanged'] += 1
                    if verbose:
                        self.stdout.write(f'  ✓ {metric_name}: No significant change needed')

            else:
                # Create new threshold
                if not dry_run:
                    AdaptiveThreshold.objects.create(
                        metric_name=metric_name,
                        value=threshold_data['value'],
                        confidence_interval=threshold_data.get('confidence_interval', 0.95),
                        sample_count=threshold_data.get('sample_count', 0),
                        accuracy=threshold_data.get('accuracy', 0.85),
                        precision=threshold_data.get('precision', 0.80)
                    )

                results['created'] += 1
                results['details'].append({
                    'metric': metric_name,
                    'action': 'created',
                    'new_value': threshold_data['value']
                })

                if verbose:
                    self.stdout.write(f'  ✨ {metric_name}: Created with value {threshold_data["value"]:.3f}')

        return results

    def _cleanup_stale_thresholds(self, days_old):
        """Remove very old threshold records"""
        cutoff_date = timezone.now() - timedelta(days=days_old)

        stale_thresholds = AdaptiveThreshold.objects.filter(
            updated_at__lt=cutoff_date,
            accuracy__lt=0.5  # Only remove poorly performing thresholds
        )

        count = stale_thresholds.count()
        stale_thresholds.delete()

        return {'removed': count}

    def _display_update_results(self, results, performance_data):
        """Display threshold update results"""
        self.stdout.write('\n📊 Update Results:')
        self.stdout.write(f'  ✨ Created: {results["created"]}')
        self.stdout.write(f'  🔄 Updated: {results["updated"]}')
        self.stdout.write(f'  ✓ Unchanged: {results["unchanged"]}')

        if results['details']:
            total_changes = results['created'] + results['updated']
            self.stdout.write(f'  📈 Total improvements: {total_changes}')

        self.stdout.write('\n💡 Threshold Health:')
        self.stdout.write(f'  📊 Data quality: {performance_data["data_quality_score"]:.1%}')
        self.stdout.write(f'  🔢 Sample size: {performance_data["total_samples"]}')

        # Recommendations
        if performance_data['data_quality_score'] < 0.7:
            self.stdout.write(
                self.style.WARNING(
                    '  ⚠️  Consider increasing data collection period for better threshold accuracy'
                )
            )

        if results['updated'] == 0 and results['created'] == 0:
            self.stdout.write('  ✅ All thresholds are optimally tuned')