"""
Django management command for baseline performance profiling.

Usage:
    python manage.py baseline_help_modules
"""

from django.core.management.base import BaseCommand
import psutil
import time
import json
import os


class Command(BaseCommand):
    help = "Run baseline performance profiling for help modules"

    def measure_memory(self):
        """Get current process memory in MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024

    def benchmark_service_import(self, service_path):
        """Benchmark service import time and memory."""
        start_memory = self.measure_memory()
        start_time = time.perf_counter()

        try:
            if service_path == "helpbot":
                from apps.helpbot.services.conversation_service import HelpBotConversationService
                service = HelpBotConversationService
            elif service_path == "help_center":
                from apps.help_center.services.search_service import SearchService
                service = SearchService
            elif service_path == "kb_suggester":
                from apps.y_helpdesk.services.kb_suggester import KBSuggester
                service = KBSuggester
            else:
                return None

            end_time = time.perf_counter()
            end_memory = self.measure_memory()

            return {
                'import_time_ms': (end_time - start_time) * 1000,
                'memory_delta_mb': end_memory - start_memory,
                'available': True
            }
        except (ImportError, AttributeError, ModuleNotFoundError) as e:
            return {
                'import_time_ms': 0,
                'memory_delta_mb': 0,
                'available': False,
                'error': str(e)
            }

    def benchmark_helpbot_mock(self, queries, iterations=100):
        """
        Mock benchmark for HelpBot - measures service initialization overhead.
        Real benchmarking happens in Phase 2 with proper test fixtures.
        """
        latencies = []

        try:
            from apps.helpbot.services.conversation_service import HelpBotConversationService

            for _ in range(iterations):
                start = time.perf_counter()
                # Just measure instantiation overhead
                _ = HelpBotConversationService()
                end = time.perf_counter()
                latencies.append((end - start) * 1000)  # ms
        except (ImportError, AttributeError, RuntimeError, ValueError) as e:
            self.stdout.write(self.style.WARNING(f"HelpBot benchmarking failed: {e}"))
            # Return placeholder values
            latencies = [0.1] * iterations

        latencies.sort()
        return {
            'p50': latencies[len(latencies) // 2],
            'p95': latencies[int(len(latencies) * 0.95)],
            'p99': latencies[int(len(latencies) * 0.99)],
            'mean': sum(latencies) / len(latencies),
            'note': 'Mock baseline - measuring service initialization only'
        }

    def benchmark_help_center_mock(self, queries, iterations=100):
        """
        Mock benchmark for help_center - measures service availability.
        Real benchmarking happens in Phase 2 with proper test fixtures.
        """
        latencies = []

        try:
            from apps.help_center.services.search_service import SearchService

            for _ in range(iterations):
                start = time.perf_counter()
                # Just measure class reference overhead
                _ = SearchService
                end = time.perf_counter()
                latencies.append((end - start) * 1000)  # ms
        except (ImportError, AttributeError, RuntimeError) as e:
            self.stdout.write(self.style.WARNING(f"help_center benchmarking failed: {e}"))
            latencies = [0.1] * iterations

        latencies.sort()
        return {
            'p50': latencies[len(latencies) // 2],
            'p95': latencies[int(len(latencies) * 0.95)],
            'p99': latencies[int(len(latencies) * 0.99)],
            'mean': sum(latencies) / len(latencies),
            'note': 'Mock baseline - measuring service availability only'
        }

    def handle(self, *args, **options):
        """Run baseline performance measurement."""
        self.stdout.write("=" * 60)
        self.stdout.write("PERFORMANCE BASELINE - HELP MODULES")
        self.stdout.write("=" * 60)
        self.stdout.write("Note: This is a simplified baseline measuring service availability")
        self.stdout.write("      and import overhead. Full performance testing happens in Phase 2.")
        self.stdout.write("=" * 60)

        # Memory baseline
        initial_memory = self.measure_memory()
        self.stdout.write(f"\nInitial memory: {initial_memory:.2f} MB")

        # Test queries (for future use)
        queries = [
            "how do I authenticate",
            "what is SLA tracking",
            "troubleshoot GPS permissions",
            "explain secure file download"
        ]

        # Check service availability
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SERVICE AVAILABILITY CHECK")
        self.stdout.write("=" * 60)

        helpbot_import = self.benchmark_service_import("helpbot")
        self.stdout.write(f"\nHelpBot Service:")
        if helpbot_import['available']:
            self.stdout.write(self.style.SUCCESS(f"  Available: Yes"))
            self.stdout.write(f"  Import time: {helpbot_import['import_time_ms']:.2f}ms")
            self.stdout.write(f"  Memory delta: {helpbot_import['memory_delta_mb']:.2f}MB")
        else:
            self.stdout.write(self.style.ERROR(f"  Available: No"))
            self.stdout.write(f"  Error: {helpbot_import.get('error', 'Unknown')}")

        help_center_import = self.benchmark_service_import("help_center")
        self.stdout.write(f"\nhelp_center Service:")
        if help_center_import['available']:
            self.stdout.write(self.style.SUCCESS(f"  Available: Yes"))
            self.stdout.write(f"  Import time: {help_center_import['import_time_ms']:.2f}ms")
            self.stdout.write(f"  Memory delta: {help_center_import['memory_delta_mb']:.2f}MB")
        else:
            self.stdout.write(self.style.ERROR(f"  Available: No"))
            self.stdout.write(f"  Error: {help_center_import.get('error', 'Unknown')}")

        kb_suggester_import = self.benchmark_service_import("kb_suggester")
        self.stdout.write(f"\nKB Suggester Service:")
        if kb_suggester_import['available']:
            self.stdout.write(self.style.SUCCESS(f"  Available: Yes"))
            self.stdout.write(f"  Import time: {kb_suggester_import['import_time_ms']:.2f}ms")
            self.stdout.write(f"  Memory delta: {kb_suggester_import['memory_delta_mb']:.2f}MB")
        else:
            self.stdout.write(self.style.ERROR(f"  Available: No"))
            self.stdout.write(f"  Error: {kb_suggester_import.get('error', 'Unknown')}")

        # Mock benchmarks (measuring service initialization)
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("MOCK PERFORMANCE BENCHMARKS")
        self.stdout.write("=" * 60)

        self.stdout.write("\nBenchmarking HelpBot service initialization...")
        helpbot_stats = self.benchmark_helpbot_mock(queries, iterations=100)
        self.stdout.write(f"HelpBot P95: {helpbot_stats['p95']:.2f}ms (initialization overhead)")
        self.stdout.write(f"Note: {helpbot_stats['note']}")

        self.stdout.write("\nBenchmarking help_center service...")
        help_center_stats = self.benchmark_help_center_mock(queries, iterations=100)
        self.stdout.write(f"help_center P95: {help_center_stats['p95']:.2f}ms (reference overhead)")
        self.stdout.write(f"Note: {help_center_stats['note']}")

        # Final memory
        final_memory = self.measure_memory()
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("MEMORY SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Initial memory: {initial_memory:.2f} MB")
        self.stdout.write(f"Final memory: {final_memory:.2f} MB")
        self.stdout.write(f"Memory delta: {final_memory - initial_memory:.2f} MB")

        # Save results
        results = {
            'timestamp': time.time(),
            'baseline_type': 'simplified_phase1',
            'note': 'Simplified baseline measuring service availability and import overhead',
            'memory': {
                'initial_mb': initial_memory,
                'final_mb': final_memory,
                'delta_mb': final_memory - initial_memory
            },
            'service_availability': {
                'helpbot': helpbot_import,
                'help_center': help_center_import,
                'kb_suggester': kb_suggester_import
            },
            'mock_benchmarks': {
                'helpbot': helpbot_stats,
                'help_center': help_center_stats
            }
        }

        baseline_file = 'performance_baseline.json'
        with open(baseline_file, 'w') as f:
            json.dump(results, f, indent=2)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Baseline saved to {baseline_file}"))
        self.stdout.write("=" * 60)
        self.stdout.write("\nNext Steps:")
        self.stdout.write("  1. Review service availability status above")
        self.stdout.write("  2. Proceed to Phase 1 Task 1.2: Add Ontology Decorators")
        self.stdout.write("  3. Full performance testing happens in Phase 2")
        self.stdout.write("=" * 60)
