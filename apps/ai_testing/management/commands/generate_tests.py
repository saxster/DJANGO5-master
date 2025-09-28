"""
AI Testing Management Command: Batch Test Generation
Generate test files for multiple coverage gaps in batch mode
"""

from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
import logging

from apps.ai_testing.models.test_coverage_gaps import TestCoverageGap
from apps.ai_testing.services.test_synthesizer import TestSynthesizer


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate test files for coverage gaps in batch mode'

    def add_arguments(self, parser):
        parser.add_argument(
            '--priority',
            choices=['critical', 'high', 'medium', 'low'],
            help='Generate tests only for gaps with specified priority'
        )
        parser.add_argument(
            '--framework',
            choices=[
                'paparazzi', 'macrobenchmark', 'espresso', 'junit',
                'robolectric', 'ui_testing', 'xctest', 'custom'
            ],
            help='Generate tests only for specified framework'
        )
        parser.add_argument(
            '--coverage-type',
            choices=[
                'visual', 'performance', 'functional', 'integration',
                'edge_case', 'error_handling', 'user_flow', 'api_contract',
                'device_specific', 'network_condition'
            ],
            help='Generate tests only for specified coverage type'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='generated_tests',
            help='Output directory for generated test files (default: generated_tests)'
        )
        parser.add_argument(
            '--max-count',
            type=int,
            default=50,
            help='Maximum number of tests to generate (default: 50)'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing generated test files'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be generated without creating files'
        )
        parser.add_argument(
            '--update-status',
            action='store_true',
            help='Update gap status to "test_generated" after successful generation'
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        priority = options.get('priority')
        framework = options.get('framework')
        coverage_type = options.get('coverage_type')
        output_dir = options['output_dir']
        max_count = options['max_count']
        overwrite = options['overwrite']
        dry_run = options['dry_run']
        update_status = options['update_status']

        self.stdout.write(
            self.style.SUCCESS('🧪 Starting Batch Test Generation')
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be created'))

        try:
            # Build queryset based on filters
            gaps = TestCoverageGap.objects.filter(
                status__in=['identified', 'test_generated']
            )

            if priority:
                gaps = gaps.filter(priority=priority)
                self.stdout.write(f'Filter: Priority = {priority}')

            if framework:
                gaps = gaps.filter(recommended_framework=framework)
                self.stdout.write(f'Filter: Framework = {framework}')

            if coverage_type:
                gaps = gaps.filter(coverage_type=coverage_type)
                self.stdout.write(f'Filter: Coverage type = {coverage_type}')

            # Order by priority and confidence for best results first
            priority_order = {
                'critical': 4,
                'high': 3,
                'medium': 2,
                'low': 1
            }

            gaps = sorted(
                gaps[:max_count * 2],  # Get more to allow for filtering
                key=lambda x: (
                    priority_order.get(x.priority, 0),
                    x.confidence_score
                ),
                reverse=True
            )[:max_count]

            if not gaps:
                self.stdout.write(
                    self.style.WARNING('No coverage gaps found matching the specified filters')
                )
                return

            self.stdout.write(f'Found {len(gaps)} coverage gap(s) to process')

            # Create output directory
            if not dry_run:
                output_path = self._create_output_directory(output_dir)
                self.stdout.write(f'Output directory: {output_path}')

            # Initialize test synthesizer
            synthesizer = TestSynthesizer()

            # Track generation results
            results = {
                'generated': 0,
                'skipped': 0,
                'failed': 0,
                'updated': 0,
                'files': []
            }

            # Generate tests
            self.stdout.write('\n🔧 Generating tests...')

            for i, gap in enumerate(gaps, 1):
                self.stdout.write(
                    f'\n[{i}/{len(gaps)}] Processing: {gap.title[:60]}{"..." if len(gap.title) > 60 else ""}'
                )

                # Determine framework to use
                test_framework = framework or gap.recommended_framework or 'junit'

                # Generate filename
                filename = self._generate_filename(gap, test_framework)

                if not dry_run:
                    filepath = output_path / filename

                    # Check if file exists and handle overwrite
                    if filepath.exists() and not overwrite:
                        self.stdout.write(f'  ⏭️  Skipped: File already exists (use --overwrite to replace)')
                        results['skipped'] += 1
                        continue

                try:
                    # Generate test code
                    test_code = synthesizer.generate_test_for_gap(gap, test_framework)

                    if test_code:
                        if not dry_run:
                            # Write file
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(test_code)

                            results['files'].append(str(filepath))

                            # Update gap status if requested
                            if update_status and gap.status == 'identified':
                                gap.status = 'test_generated'
                                gap.auto_generated_test_code = test_code
                                gap.save()
                                results['updated'] += 1

                        self.stdout.write(f'  ✅ Generated: {filename}')
                        results['generated'] += 1

                    else:
                        self.stdout.write(f'  ❌ Failed: Could not generate test code')
                        results['failed'] += 1

                except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
                    logger.error(f'Test generation failed for gap {gap.id}: {str(e)}')
                    self.stdout.write(f'  ❌ Error: {str(e)}')
                    results['failed'] += 1

            # Display results summary
            self._display_results_summary(results, output_dir if not dry_run else None)

            # Execution time
            duration = timezone.now() - start_time
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Batch test generation completed in {duration.total_seconds():.1f}s'
                )
            )

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            logger.error(f'Batch test generation failed: {str(e)}', exc_info=True)
            raise CommandError(f'Generation failed: {str(e)}')

    def _create_output_directory(self, output_dir):
        """Create timestamped output directory"""
        timestamp = timezone.now().strftime('%Y-%m-%d_%H-%M-%S')
        base_path = Path(settings.BASE_DIR) / output_dir / timestamp

        base_path.mkdir(parents=True, exist_ok=True)

        return base_path

    def _generate_filename(self, gap, framework):
        """Generate appropriate filename for test file"""
        # Sanitize gap title for filename
        safe_title = ''.join(
            c for c in gap.title.lower().replace(' ', '_')
            if c.isalnum() or c == '_'
        )[:30]  # Limit length

        # Determine file extension
        if framework in ['ui_testing', 'xctest']:
            extension = 'swift'
        else:
            extension = 'kt'

        # Create filename
        filename = f'test_{gap.coverage_type}_{safe_title}_{gap.id.hex[:8]}.{extension}'

        return filename

    def _display_results_summary(self, results, output_dir):
        """Display generation results summary"""
        self.stdout.write('\n📊 Generation Summary:')
        self.stdout.write(f'  ✅ Successfully generated: {results["generated"]}')
        self.stdout.write(f'  ⏭️  Skipped (existing): {results["skipped"]}')
        self.stdout.write(f'  ❌ Failed: {results["failed"]}')

        if results['updated'] > 0:
            self.stdout.write(f'  🔄 Status updated: {results["updated"]}')

        total_processed = results['generated'] + results['skipped'] + results['failed']
        success_rate = (results['generated'] / total_processed * 100) if total_processed > 0 else 0

        self.stdout.write(f'  📈 Success rate: {success_rate:.1f}%')

        if output_dir and results['files']:
            self.stdout.write(f'\n📁 Generated files in: {output_dir}')

            # Show sample files
            sample_files = results['files'][:5]
            for filepath in sample_files:
                filename = Path(filepath).name
                self.stdout.write(f'  - {filename}')

            if len(results['files']) > 5:
                self.stdout.write(f'  ... and {len(results["files"]) - 5} more files')

        # Recommendations
        self.stdout.write('\n💡 Next Steps:')

        if results['generated'] > 0:
            self.stdout.write('  1. Review generated test files for accuracy')
            self.stdout.write('  2. Integrate tests into your test suite')
            self.stdout.write('  3. Customize assertions based on your requirements')

        if results['failed'] > 0:
            self.stdout.write(f'  4. Investigate {results["failed"]} failed generations')

        if results['skipped'] > 0:
            self.stdout.write('  5. Use --overwrite if you want to regenerate existing tests')