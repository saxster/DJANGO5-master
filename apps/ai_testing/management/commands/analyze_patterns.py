"""
AI Testing Management Command: Pattern Analysis
Runs comprehensive pattern analysis on stream test data to identify coverage gaps
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
import logging

from apps.ai_testing.services.pattern_analyzer import PatternAnalyzer
from apps.ai_testing.models.test_coverage_gaps import TestCoverageGap, TestCoveragePattern
from apps.streamlab.models import TestRun, StreamEvent


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run pattern analysis to identify test coverage gaps and update adaptive thresholds'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to look back for analysis (default: 30)'
        )
        parser.add_argument(
            '--min-confidence',
            type=float,
            default=0.6,
            help='Minimum confidence score for gap identification (default: 0.6)'
        )
        parser.add_argument(
            '--force-refresh',
            action='store_true',
            help='Force refresh of all patterns, even if recently updated'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output with detailed analysis results'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform analysis without saving results to database'
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        days = options['days']
        min_confidence = options['min_confidence']
        force_refresh = options['force_refresh']
        verbose = options['verbose']
        dry_run = options['dry_run']

        self.stdout.write(
            self.style.SUCCESS(f'🤖 Starting AI Pattern Analysis')
        )
        self.stdout.write(f'Analysis period: {days} days')
        self.stdout.write(f'Minimum confidence: {min_confidence}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        try:
            # Initialize pattern analyzer
            analyzer = PatternAnalyzer()

            # Set analysis window
            since_date = timezone.now() - timedelta(days=days)

            # Step 1: Collect data for analysis
            self.stdout.write('\n📊 Collecting data for analysis...')

            test_runs = TestRun.objects.filter(
                started_at__gte=since_date
            ).select_related('scenario')

            anomaly_occurrences = AnomalyOccurrence.objects.filter(
                created_at__gte=since_date
            ).select_related('signature')

            stream_events = StreamEvent.objects.filter(
                timestamp__gte=since_date
            ).select_related('run')

            data_stats = {
                'test_runs': test_runs.count(),
                'anomaly_occurrences': anomaly_occurrences.count(),
                'stream_events': stream_events.count()
            }

            self.stdout.write(f'  - Test runs: {data_stats["test_runs"]}')
            self.stdout.write(f'  - Anomaly occurrences: {data_stats["anomaly_occurrences"]}')
            self.stdout.write(f'  - Stream events: {data_stats["stream_events"]}')

            if data_stats['test_runs'] == 0:
                self.stdout.write(
                    self.style.WARNING('⚠️  No test runs found in the specified time period')
                )
                return

            # Step 2: Run pattern analysis
            self.stdout.write('\n🔍 Analyzing patterns...')

            analysis_results = analyzer.analyze_anomaly_patterns(
                test_runs=list(test_runs),
                anomaly_occurrences=list(anomaly_occurrences),
                min_confidence=min_confidence,
                force_refresh=force_refresh
            )

            # Step 3: Identify coverage gaps
            self.stdout.write('\n🎯 Identifying coverage gaps...')

            coverage_gaps = analyzer.identify_coverage_gaps(
                analysis_results,
                min_confidence=min_confidence
            )

            # Step 4: Save results (unless dry run)
            if not dry_run:
                self.stdout.write('\n💾 Saving analysis results...')

                gaps_created = 0
                gaps_updated = 0
                patterns_created = 0
                patterns_updated = 0

                # Save coverage gaps
                for gap_data in coverage_gaps:
                    gap, created = TestCoverageGap.objects.update_or_create(
                        anomaly_signature=gap_data['anomaly_signature'],
                        coverage_type=gap_data['coverage_type'],
                        defaults={
                            'title': gap_data['title'],
                            'description': gap_data['description'],
                            'priority': gap_data['priority'],
                            'confidence_score': gap_data['confidence_score'],
                            'impact_score': gap_data['impact_score'],
                            'affected_endpoints': gap_data.get('affected_endpoints', []),
                            'affected_platforms': gap_data.get('affected_platforms', []),
                            'recommended_framework': gap_data.get('recommended_framework', 'junit'),
                            'pattern_metadata': gap_data.get('pattern_metadata', {}),
                        }
                    )

                    if created:
                        gaps_created += 1
                    else:
                        gaps_updated += 1

                # Save patterns
                for pattern_data in analysis_results.get('patterns', []):
                    pattern, created = TestCoveragePattern.objects.update_or_create(
                        pattern_type=pattern_data['pattern_type'],
                        pattern_signature=pattern_data['pattern_signature'],
                        defaults={
                            'title': pattern_data['title'],
                            'description': pattern_data['description'],
                            'pattern_criteria': pattern_data['pattern_criteria'],
                            'occurrence_count': pattern_data['occurrence_count'],
                            'confidence_score': pattern_data['confidence_score'],
                            'recommended_actions': pattern_data.get('recommended_actions', []),
                        }
                    )

                    if created:
                        patterns_created += 1
                    else:
                        patterns_updated += 1

                self.stdout.write(f'  - Coverage gaps created: {gaps_created}')
                self.stdout.write(f'  - Coverage gaps updated: {gaps_updated}')
                self.stdout.write(f'  - Patterns created: {patterns_created}')
                self.stdout.write(f'  - Patterns updated: {patterns_updated}')

            # Step 5: Display results summary
            self.stdout.write('\n📈 Analysis Summary:')

            summary = self._generate_analysis_summary(
                coverage_gaps,
                analysis_results,
                data_stats
            )

            for line in summary:
                self.stdout.write(f'  {line}')

            if verbose:
                self.stdout.write('\n🔬 Detailed Analysis:')
                detailed_results = self._generate_detailed_results(
                    coverage_gaps,
                    analysis_results
                )
                for line in detailed_results:
                    self.stdout.write(f'  {line}')

            # Execution time
            duration = timezone.now() - start_time
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Pattern analysis completed in {duration.total_seconds():.1f}s'
                )
            )

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            logger.error(f'Pattern analysis failed: {str(e)}', exc_info=True)
            raise CommandError(f'Analysis failed: {str(e)}')

    def _generate_analysis_summary(self, coverage_gaps, analysis_results, data_stats):
        """Generate a summary of analysis results"""
        summary = []

        if coverage_gaps:
            priority_counts = {}
            coverage_type_counts = {}

            for gap in coverage_gaps:
                priority = gap.get('priority', 'unknown')
                coverage_type = gap.get('coverage_type', 'unknown')

                priority_counts[priority] = priority_counts.get(priority, 0) + 1
                coverage_type_counts[coverage_type] = coverage_type_counts.get(coverage_type, 0) + 1

            summary.append(f'Total coverage gaps identified: {len(coverage_gaps)}')

            # Priority breakdown
            for priority in ['critical', 'high', 'medium', 'low']:
                count = priority_counts.get(priority, 0)
                if count > 0:
                    summary.append(f'  - {priority.title()} priority: {count}')

            # Coverage type breakdown
            summary.append('Coverage types identified:')
            for coverage_type, count in coverage_type_counts.items():
                summary.append(f'  - {coverage_type.title()}: {count}')
        else:
            summary.append('No coverage gaps identified in the analysis period')

        # Pattern insights
        patterns = analysis_results.get('patterns', [])
        if patterns:
            summary.append(f'Patterns detected: {len(patterns)}')

            pattern_strengths = [p.get('confidence_score', 0) for p in patterns]
            if pattern_strengths:
                avg_confidence = sum(pattern_strengths) / len(pattern_strengths)
                summary.append(f'Average pattern confidence: {avg_confidence:.1%}')

        return summary

    def _generate_detailed_results(self, coverage_gaps, analysis_results):
        """Generate detailed analysis results"""
        details = []

        details.append('Top Priority Gaps:')

        # Sort gaps by priority and confidence
        priority_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        sorted_gaps = sorted(
            coverage_gaps,
            key=lambda x: (
                priority_order.get(x.get('priority', 'low'), 0),
                x.get('confidence_score', 0)
            ),
            reverse=True
        )[:5]  # Top 5

        for i, gap in enumerate(sorted_gaps, 1):
            details.append(
                f'{i}. {gap.get("title", "Unknown")} '
                f'({gap.get("priority", "unknown")} priority, '
                f'{gap.get("confidence_score", 0):.1%} confidence)'
            )

        # Pattern analysis
        patterns = analysis_results.get('patterns', [])
        if patterns:
            details.append('\nStrong Patterns:')

            sorted_patterns = sorted(
                patterns,
                key=lambda x: x.get('confidence_score', 0),
                reverse=True
            )[:3]  # Top 3

            for i, pattern in enumerate(sorted_patterns, 1):
                details.append(
                    f'{i}. {pattern.get("title", "Unknown pattern")} '
                    f'({pattern.get("occurrence_count", 0)} occurrences, '
                    f'{pattern.get("confidence_score", 0):.1%} confidence)'
                )

        return details