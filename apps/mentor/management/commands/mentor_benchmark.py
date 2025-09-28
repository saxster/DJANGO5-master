"""
mentor_benchmark management command for running golden benchmark tests.

This command runs the comprehensive benchmark suite to validate
AI Mentor system quality and performance.
"""

import json
import time

from django.core.management.base import BaseCommand, CommandError

from apps.mentor.testing.golden_benchmarks import (
    GoldenBenchmarkSuite, BenchmarkRunner, BenchmarkType, DifficultyLevel
)


class Command(BaseCommand):
    help = 'Run golden benchmark tests for AI Mentor system validation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            choices=[bt.value for bt in BenchmarkType],
            help='Run benchmarks of specific type only'
        )
        parser.add_argument(
            '--difficulty',
            choices=[dl.value for dl in DifficultyLevel],
            help='Run benchmarks of specific difficulty only'
        )
        parser.add_argument(
            '--scenario',
            type=str,
            help='Run specific scenario by ID'
        )
        parser.add_argument(
            '--regression-only',
            action='store_true',
            help='Run only critical regression benchmarks'
        )
        parser.add_argument(
            '--performance-only',
            action='store_true',
            help='Run only performance benchmarks'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export results to file (JSON format)'
        )
        parser.add_argument(
            '--fail-fast',
            action='store_true',
            help='Stop on first failure'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        try:
            if options.get('regression_only'):
                self._run_regression_tests(options)
            elif options.get('performance_only'):
                self._run_performance_tests(options)
            elif options.get('scenario'):
                self._run_single_scenario(options['scenario'], options)
            else:
                self._run_full_suite(options)

        except (TypeError, ValidationError, ValueError) as e:
            self.stdout.write(self.style.ERROR(f"❌ Benchmark execution failed: {e}"))
            raise CommandError(f"Benchmark failed: {e}")

    def _run_regression_tests(self, options):
        """Run critical regression benchmarks."""
        self.stdout.write("🔍 Running Regression Benchmark Suite")
        self.stdout.write("=" * 50)

        runner = BenchmarkRunner()
        passed = runner.run_regression_tests()

        if passed:
            self.stdout.write(self.style.SUCCESS("✅ All regression tests passed"))
        else:
            self.stdout.write(self.style.ERROR("❌ Regression tests failed"))
            if options.get('fail_fast'):
                raise CommandError("Regression tests failed")

    def _run_performance_tests(self, options):
        """Run performance benchmarks."""
        self.stdout.write("⚡ Running Performance Benchmark Suite")
        self.stdout.write("=" * 50)

        runner = BenchmarkRunner()
        performance_results = runner.run_performance_benchmarks()

        self.stdout.write("Performance Results:")
        for scenario_id, execution_time in performance_results.items():
            if execution_time > 30:  # Over 30 seconds
                status = self.style.ERROR("SLOW")
            elif execution_time > 10:
                status = self.style.WARNING("ACCEPTABLE")
            else:
                status = self.style.SUCCESS("FAST")

            self.stdout.write(f"  {scenario_id}: {execution_time:.2f}s {status}")

    def _run_single_scenario(self, scenario_id: str, options):
        """Run a single benchmark scenario."""
        self.stdout.write(f"🎯 Running Single Scenario: {scenario_id}")
        self.stdout.write("=" * 50)

        suite = GoldenBenchmarkSuite()
        scenario = suite.get_scenario(scenario_id)

        if not scenario:
            self.stdout.write(self.style.ERROR(f"Scenario not found: {scenario_id}"))
            return

        # Display scenario info
        self.stdout.write(f"Name: {scenario.name}")
        self.stdout.write(f"Type: {scenario.benchmark_type.value}")
        self.stdout.write(f"Difficulty: {scenario.difficulty.value}")
        self.stdout.write(f"Request: {scenario.request}")
        self.stdout.write("")

        # Run the benchmark
        result = suite.run_benchmark(scenario_id)

        # Display results
        self._display_scenario_result(result, options.get('verbose', False))

        if options.get('export'):
            self._export_single_result(result, options['export'])

    def _run_full_suite(self, options):
        """Run the full benchmark suite."""
        self.stdout.write("🏆 Running Full Golden Benchmark Suite")
        self.stdout.write("=" * 50)

        suite = GoldenBenchmarkSuite()

        # Filter scenarios if requested
        scenarios = suite.scenarios
        if options.get('type'):
            benchmark_type = BenchmarkType(options['type'])
            scenarios = suite.get_scenarios_by_type(benchmark_type)
            self.stdout.write(f"Filtering to {benchmark_type.value} scenarios: {len(scenarios)} scenarios")

        if options.get('difficulty'):
            difficulty = DifficultyLevel(options['difficulty'])
            scenarios = [s for s in scenarios if s.difficulty == difficulty]
            self.stdout.write(f"Filtering to {difficulty.value} difficulty: {len(scenarios)} scenarios")

        if not scenarios:
            self.stdout.write(self.style.WARNING("No scenarios match the filter criteria"))
            return

        # Run benchmarks
        results = []
        failed_count = 0

        for i, scenario in enumerate(scenarios, 1):
            self.stdout.write(f"\n[{i}/{len(scenarios)}] Running: {scenario.name}")

            try:
                result = suite.run_benchmark(scenario.id)
                results.append(result)

                status_icon = "✅" if result.passed else "❌"
                score_text = f"Score: {result.score:.2f}"
                time_text = f"Time: {result.execution_time_seconds:.1f}s"

                self.stdout.write(f"  {status_icon} {score_text} | {time_text}")

                if options.get('verbose') and not result.passed:
                    for diff in result.differences[:3]:  # Show first 3 differences
                        self.stdout.write(f"    • {diff}")

                if not result.passed:
                    failed_count += 1
                    if options.get('fail_fast'):
                        self.stdout.write(self.style.ERROR("Stopping due to --fail-fast"))
                        break

            except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                failed_count += 1
                self.stdout.write(f"  ❌ ERROR: {str(e)}")

                if options.get('fail_fast'):
                    raise CommandError(f"Benchmark failed: {e}")

        # Summary
        self._display_suite_summary(results, len(scenarios), failed_count)

        # Export if requested
        if options.get('export'):
            self._export_results(results, options['export'])

    def _display_scenario_result(self, result, verbose: bool = False):
        """Display detailed result for a single scenario."""
        status = "PASSED ✅" if result.passed else "FAILED ❌"
        self.stdout.write(f"Result: {status}")
        self.stdout.write(f"Score: {result.score:.2f}")
        self.stdout.write(f"Execution Time: {result.execution_time_seconds:.2f} seconds")
        self.stdout.write(f"Actual Steps: {result.actual_steps}")
        self.stdout.write(f"Actual Risk Level: {result.actual_risk_level}")

        if result.differences:
            self.stdout.write("\nDifferences from expected:")
            for diff in result.differences:
                self.stdout.write(f"  • {diff}")

        if verbose and result.actual_files:
            self.stdout.write(f"\nFiles affected: {', '.join(result.actual_files)}")

    def _display_suite_summary(self, results: List, total_scenarios: int, failed_count: int):
        """Display summary of suite execution."""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("📊 BENCHMARK SUITE SUMMARY")
        self.stdout.write("=" * 50)

        passed_count = len([r for r in results if r.passed])
        avg_score = sum(r.score for r in results) / len(results) if results else 0
        avg_time = sum(r.execution_time_seconds for r in results) / len(results) if results else 0

        self.stdout.write(f"Total Scenarios: {total_scenarios}")
        self.stdout.write(f"Executed: {len(results)}")
        self.stdout.write(f"Passed: {passed_count}")
        self.stdout.write(f"Failed: {failed_count}")
        self.stdout.write(f"Pass Rate: {(passed_count / len(results) * 100):.1f}%" if results else "N/A")
        self.stdout.write(f"Average Score: {avg_score:.2f}")
        self.stdout.write(f"Average Time: {avg_time:.2f} seconds")

        # Status determination
        if failed_count == 0:
            self.stdout.write(self.style.SUCCESS("\n🎉 ALL BENCHMARKS PASSED!"))
        elif failed_count <= total_scenarios * 0.1:  # Less than 10% failed
            self.stdout.write(self.style.WARNING(f"\n⚠️  MOSTLY PASSED ({failed_count} failures)"))
        else:
            self.stdout.write(self.style.ERROR(f"\n❌ SUITE FAILED ({failed_count} failures)"))

    def _export_results(self, results: List, export_path: str):
        """Export benchmark results to file."""
        export_data = {
            'export_timestamp': time.time(),
            'total_results': len(results),
            'passed_results': len([r for r in results if r.passed]),
            'average_score': sum(r.score for r in results) / len(results) if results else 0,
            'results': [self._result_to_dict(r) for r in results]
        }

        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        self.stdout.write(f"📁 Results exported to: {export_path}")

    def _export_single_result(self, result, export_path: str):
        """Export single result to file."""
        result_data = self._result_to_dict(result)

        with open(export_path, 'w') as f:
            json.dump(result_data, f, indent=2, default=str)

        self.stdout.write(f"📁 Result exported to: {export_path}")

    def _result_to_dict(self, result) -> Dict[str, Any]:
        """Convert benchmark result to dictionary."""
        return {
            'scenario_id': result.scenario_id,
            'passed': result.passed,
            'score': result.score,
            'execution_time_seconds': result.execution_time_seconds,
            'actual_steps': result.actual_steps,
            'actual_files': result.actual_files,
            'actual_risk_level': result.actual_risk_level,
            'differences': result.differences,
            'llm_iterations': result.llm_iterations,
            'confidence_score': result.confidence_score,
            'timestamp': result.timestamp
        }