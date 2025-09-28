#!/usr/bin/env python3
"""
Mobile Performance Testing CI/CD Integration

Builds on existing run_stream_tests.py patterns for mobile performance gate enforcement.
Integrates Macrobenchmark and visual regression test results with Stream Testbench.
"""

import os
import sys
import json
import time
import logging
import subprocess
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')

import django
django.setup()

from apps.streamlab.models import StreamEvent, TestRun, TestScenario
from apps.issue_tracker.models import AnomalyOccurrence
from apps.streamlab.services.visual_diff_processor import VisualDiffProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceThresholds:
    """Performance SLO thresholds for mobile app"""
    startup_cold_p95_ms: float = 2000.0
    startup_warm_p95_ms: float = 1000.0
    scroll_jank_percentage: float = 5.0
    navigation_p95_ms: float = 500.0
    memory_allocation_mb: float = 100.0
    visual_diff_threshold: float = 0.05  # 5% visual change
    composition_time_p95_ms: float = 100.0
    frame_time_p95_ms: float = 16.67  # 60 FPS


@dataclass
class TestResult:
    """Individual test result"""
    test_name: str
    test_type: str  # 'macrobenchmark', 'visual_regression', 'performance'
    duration_ms: int
    success: bool
    metrics: Dict[str, float]
    error_message: Optional[str] = None
    artifacts: Optional[List[str]] = None


@dataclass
class MobileTestResults:
    """Complete mobile test run results"""
    run_id: str
    app_version: str
    commit_sha: str
    branch: str
    test_results: List[TestResult]
    slo_violations: List[Dict[str, any]]
    total_duration_ms: int
    passed: bool


class MobilePerformanceRunner:
    """
    Mobile Performance Test Runner

    Integrates with existing Stream Testbench infrastructure for mobile performance gates.
    """

    def __init__(self,
                 app_package: str = "com.example.testapp",
                 stream_testbench_url: str = "ws://localhost:8000/ws/mobile-sync/",
                 thresholds: Optional[PerformanceThresholds] = None):
        self.app_package = app_package
        self.stream_testbench_url = stream_testbench_url
        self.thresholds = thresholds or PerformanceThresholds()
        self.visual_processor = VisualDiffProcessor()

        # Get environment info
        self.app_version = os.getenv('APP_VERSION', 'unknown')
        self.commit_sha = os.getenv('GITHUB_SHA', self._get_git_sha())
        self.branch = os.getenv('GITHUB_REF_NAME', self._get_git_branch())

        logger.info(f"Mobile Performance Runner initialized for {app_package}")
        logger.info(f"App version: {self.app_version}, Commit: {self.commit_sha}, Branch: {self.branch}")

    def run_all_tests(self) -> MobileTestResults:
        """
        Run complete mobile performance test suite.

        Returns:
            MobileTestResults with all test outcomes and SLO validation
        """
        run_id = f"mobile_perf_{int(time.time())}"
        start_time = time.time()

        logger.info(f"Starting mobile performance test run: {run_id}")

        # Create test run in Stream Testbench
        test_run = self._create_stream_testbench_run(run_id)

        all_results = []
        slo_violations = []

        try:
            # 1. Run Macrobenchmark tests
            logger.info("Running Macrobenchmark performance tests...")
            macro_results = self._run_macrobenchmark_tests()
            all_results.extend(macro_results)

            # 2. Run Visual Regression tests
            logger.info("Running Visual Regression tests...")
            visual_results = self._run_visual_regression_tests()
            all_results.extend(visual_results)

            # 3. Run Compose Performance tests
            logger.info("Running Compose Performance tests...")
            compose_results = self._run_compose_performance_tests()
            all_results.extend(compose_results)

            # 4. Validate SLOs
            logger.info("Validating performance SLOs...")
            slo_violations = self._validate_performance_slos(all_results)

            # 5. Upload results to Stream Testbench
            self._upload_results_to_stream_testbench(test_run, all_results)

            total_duration = int((time.time() - start_time) * 1000)
            passed = len(slo_violations) == 0 and all(r.success for r in all_results)

            results = MobileTestResults(
                run_id=run_id,
                app_version=self.app_version,
                commit_sha=self.commit_sha,
                branch=self.branch,
                test_results=all_results,
                slo_violations=slo_violations,
                total_duration_ms=total_duration,
                passed=passed
            )

            self._finalize_test_run(test_run, results)

            logger.info(f"Mobile performance test run completed: {run_id}")
            logger.info(f"Tests passed: {len([r for r in all_results if r.success])}/{len(all_results)}")
            logger.info(f"SLO violations: {len(slo_violations)}")

            return results

        except Exception as e:
            logger.error(f"Mobile performance test run failed: {e}")
            self._mark_test_run_failed(test_run, str(e))
            raise

    def _run_macrobenchmark_tests(self) -> List[TestResult]:
        """Run Macrobenchmark performance tests"""
        results = []

        benchmark_tests = [
            ("startupBenchmark", "startup_cold"),
            ("warmStartupBenchmark", "startup_warm"),
            ("scrollBenchmark", "scroll_performance"),
            ("navigationBenchmark", "navigation_performance"),
            ("memoryBenchmark", "memory_allocations")
        ]

        for test_method, test_name in benchmark_tests:
            try:
                logger.info(f"Running {test_name} benchmark...")

                # Run benchmark test (mock implementation)
                success, metrics, duration, error = self._execute_benchmark_test(test_method)

                result = TestResult(
                    test_name=test_name,
                    test_type="macrobenchmark",
                    duration_ms=duration,
                    success=success,
                    metrics=metrics,
                    error_message=error
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Failed to run {test_name}: {e}")
                results.append(TestResult(
                    test_name=test_name,
                    test_type="macrobenchmark",
                    duration_ms=0,
                    success=False,
                    metrics={},
                    error_message=str(e)
                ))

        return results

    def _run_visual_regression_tests(self) -> List[TestResult]:
        """Run Paparazzi visual regression tests"""
        results = []

        visual_tests = [
            "login_screen",
            "user_profile_screen",
            "button_states_screen",
            "navigation_drawer_screen"
        ]

        for screen_name in visual_tests:
            try:
                logger.info(f"Running visual regression test for {screen_name}...")

                # Run Paparazzi test (mock implementation)
                success, visual_hash, diff_score, duration, error = self._execute_visual_test(screen_name)

                result = TestResult(
                    test_name=f"visual_{screen_name}",
                    test_type="visual_regression",
                    duration_ms=duration,
                    success=success,
                    metrics={
                        "visual_diff_score": diff_score,
                        "baseline_hash_length": len(visual_hash) if visual_hash else 0
                    },
                    error_message=error,
                    artifacts=[f"screenshots/{screen_name}.png"] if success else None
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Failed to run visual test for {screen_name}: {e}")
                results.append(TestResult(
                    test_name=f"visual_{screen_name}",
                    test_type="visual_regression",
                    duration_ms=0,
                    success=False,
                    metrics={},
                    error_message=str(e)
                ))

        return results

    def _run_compose_performance_tests(self) -> List[TestResult]:
        """Run Compose UI performance tests"""
        results = []

        compose_tests = [
            ("composition_timing", "composition_performance"),
            ("jank_detection", "jank_metrics"),
            ("frame_timing", "frame_performance")
        ]

        for test_method, test_name in compose_tests:
            try:
                logger.info(f"Running {test_name} test...")

                # Run compose performance test (mock implementation)
                success, metrics, duration, error = self._execute_compose_test(test_method)

                result = TestResult(
                    test_name=test_name,
                    test_type="compose_performance",
                    duration_ms=duration,
                    success=success,
                    metrics=metrics,
                    error_message=error
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Failed to run {test_name}: {e}")
                results.append(TestResult(
                    test_name=test_name,
                    test_type="compose_performance",
                    duration_ms=0,
                    success=False,
                    metrics={},
                    error_message=str(e)
                ))

        return results

    def _validate_performance_slos(self, results: List[TestResult]) -> List[Dict[str, any]]:
        """Validate performance results against SLO thresholds"""
        violations = []

        slo_checks = {
            "startup_cold": ("p95_latency_ms", self.thresholds.startup_cold_p95_ms),
            "startup_warm": ("p95_latency_ms", self.thresholds.startup_warm_p95_ms),
            "scroll_performance": ("jank_percentage", self.thresholds.scroll_jank_percentage),
            "navigation_performance": ("p95_latency_ms", self.thresholds.navigation_p95_ms),
            "memory_allocations": ("allocation_mb", self.thresholds.memory_allocation_mb),
            "composition_performance": ("p95_composition_ms", self.thresholds.composition_time_p95_ms),
            "frame_performance": ("p95_frame_ms", self.thresholds.frame_time_p95_ms),
        }

        for result in results:
            if result.test_name in slo_checks:
                metric_name, threshold = slo_checks[result.test_name]

                if metric_name in result.metrics:
                    actual_value = result.metrics[metric_name]

                    if actual_value > threshold:
                        violation = {
                            "test_name": result.test_name,
                            "metric_name": metric_name,
                            "actual_value": actual_value,
                            "threshold": threshold,
                            "violation_percentage": ((actual_value - threshold) / threshold) * 100,
                            "severity": "critical" if actual_value > threshold * 1.5 else "warning"
                        }
                        violations.append(violation)

                        logger.warning(f"SLO violation in {result.test_name}: {metric_name}={actual_value} > {threshold}")

        # Check visual regression thresholds
        visual_results = [r for r in results if r.test_type == "visual_regression"]
        for result in visual_results:
            diff_score = result.metrics.get("visual_diff_score", 0.0)
            if diff_score > self.thresholds.visual_diff_threshold:
                violation = {
                    "test_name": result.test_name,
                    "metric_name": "visual_diff_score",
                    "actual_value": diff_score,
                    "threshold": self.thresholds.visual_diff_threshold,
                    "violation_percentage": ((diff_score - self.thresholds.visual_diff_threshold) / self.thresholds.visual_diff_threshold) * 100,
                    "severity": "warning"
                }
                violations.append(violation)

                logger.warning(f"Visual regression detected in {result.test_name}: diff_score={diff_score}")

        return violations

    def _create_stream_testbench_run(self, run_id: str):
        """Create test run in Stream Testbench"""
        try:
            # Create test scenario for mobile performance
            scenario, created = TestScenario.objects.get_or_create(
                name="mobile_performance_suite",
                defaults={
                    "description": "Mobile app performance testing with Macrobenchmark and visual regression",
                    "protocol": "mobile",
                    "endpoint": f"mobile://{self.app_package}",
                    "config": {
                        "app_version": self.app_version,
                        "test_types": ["macrobenchmark", "visual_regression", "compose_performance"]
                    },
                    "expected_p95_latency_ms": self.thresholds.startup_cold_p95_ms,
                    "expected_error_rate": 0.05,
                    "created_by_id": 1  # System user
                }
            )

            # Create test run
            test_run = TestRun.objects.create(
                scenario=scenario,
                started_by_id=1,  # System user
                runtime_config={
                    "run_id": run_id,
                    "app_package": self.app_package,
                    "app_version": self.app_version,
                    "commit_sha": self.commit_sha,
                    "branch": self.branch,
                    "ci_environment": True
                }
            )

            logger.info(f"Created Stream Testbench run: {test_run.id}")
            return test_run

        except Exception as e:
            logger.error(f"Failed to create Stream Testbench run: {e}")
            raise

    def _upload_results_to_stream_testbench(self, test_run, results: List[TestResult]):
        """Upload test results as StreamEvents"""
        try:
            for result in results:
                # Create StreamEvent for each test result
                stream_event = StreamEvent.objects.create(
                    run=test_run,
                    correlation_id=self._generate_correlation_id(),
                    direction='outbound',
                    endpoint=f"mobile_test/{result.test_name}",
                    latency_ms=result.duration_ms,
                    message_size_bytes=len(json.dumps(result.metrics)),
                    outcome='success' if result.success else 'error',
                    error_message=result.error_message or '',
                    payload_sanitized={
                        "test_name": result.test_name,
                        "test_type": result.test_type,
                        "metrics": result.metrics,
                        "app_version": self.app_version,
                        "commit_sha": self.commit_sha
                    },
                    payload_schema_hash=self._calculate_payload_hash(result.metrics),

                    # Phase 2: Mobile performance fields
                    performance_metrics=result.metrics,
                    jank_score=result.metrics.get("jank_percentage", 0.0) * 10,  # Scale to 0-100
                    composition_time_ms=result.metrics.get("p95_composition_ms"),
                    client_app_version=self.app_version,
                    client_os_version="Android 13",  # Would get from device
                    client_device_model="Pixel 5",   # Would get from device

                    # Phase 2: Visual regression fields (if applicable)
                    visual_baseline_hash=result.metrics.get("baseline_hash", ""),
                    visual_diff_score=result.metrics.get("visual_diff_score"),
                    visual_diff_metadata={
                        "test_framework": "paparazzi" if result.test_type == "visual_regression" else "macrobenchmark",
                        "artifacts": result.artifacts or []
                    } if result.test_type in ["visual_regression", "macrobenchmark"] else None
                )

                # Process visual regression if applicable
                if result.test_type == "visual_regression":
                    self.visual_processor.process_visual_event(stream_event)

                logger.debug(f"Created StreamEvent {stream_event.id} for {result.test_name}")

            logger.info(f"Uploaded {len(results)} test results to Stream Testbench")

        except Exception as e:
            logger.error(f"Failed to upload results to Stream Testbench: {e}")
            raise

    def _finalize_test_run(self, test_run, results: MobileTestResults):
        """Finalize test run with summary metrics"""
        try:
            # Calculate summary metrics
            successful_results = [r for r in results.test_results if r.success]
            failed_results = [r for r in results.test_results if not r.success]

            # Update test run
            test_run.total_events = len(results.test_results)
            test_run.successful_events = len(successful_results)
            test_run.failed_events = len(failed_results)
            test_run.anomalies_detected = len(results.slo_violations)

            # Calculate performance metrics
            all_durations = [r.duration_ms for r in results.test_results if r.duration_ms > 0]
            if all_durations:
                test_run.p50_latency_ms = sorted(all_durations)[len(all_durations) // 2]
                test_run.p95_latency_ms = sorted(all_durations)[int(len(all_durations) * 0.95)]
                test_run.p99_latency_ms = sorted(all_durations)[int(len(all_durations) * 0.99)]

            test_run.error_rate = len(failed_results) / len(results.test_results) if results.test_results else 0
            test_run.throughput_qps = len(results.test_results) / (results.total_duration_ms / 1000.0)

            test_run.metrics = {
                "slo_violations": results.slo_violations,
                "app_version": results.app_version,
                "commit_sha": results.commit_sha,
                "branch": results.branch,
                "test_summary": {
                    "macrobenchmark_tests": len([r for r in results.test_results if r.test_type == "macrobenchmark"]),
                    "visual_regression_tests": len([r for r in results.test_results if r.test_type == "visual_regression"]),
                    "compose_performance_tests": len([r for r in results.test_results if r.test_type == "compose_performance"])
                }
            }

            if results.passed:
                test_run.mark_completed()
            else:
                test_run.mark_failed(f"SLO violations: {len(results.slo_violations)}, Failed tests: {len(failed_results)}")

            logger.info(f"Finalized test run {test_run.id}: {'PASSED' if results.passed else 'FAILED'}")

        except Exception as e:
            logger.error(f"Failed to finalize test run: {e}")
            test_run.mark_failed(str(e))

    # Mock test execution methods (would be replaced with actual test execution)
    def _execute_benchmark_test(self, test_method: str) -> Tuple[bool, Dict[str, float], int, Optional[str]]:
        """Mock benchmark test execution"""
        import random

        success = random.random() > 0.1  # 90% success rate
        duration = random.randint(5000, 15000)  # 5-15 seconds

        if success:
            metrics = {
                "p50_latency_ms": random.uniform(100, 500),
                "p95_latency_ms": random.uniform(500, 1500),
                "p99_latency_ms": random.uniform(1000, 3000),
                "jank_percentage": random.uniform(0, 10),
                "allocation_mb": random.uniform(50, 150)
            }
            return True, metrics, duration, None
        else:
            return False, {}, duration, f"Mock failure in {test_method}"

    def _execute_visual_test(self, screen_name: str) -> Tuple[bool, str, float, int, Optional[str]]:
        """Mock visual regression test execution"""
        import random
        import hashlib

        success = random.random() > 0.05  # 95% success rate
        duration = random.randint(2000, 8000)  # 2-8 seconds

        if success:
            visual_hash = hashlib.md5(f"{screen_name}_{time.time()}".encode()).hexdigest()[:16]
            diff_score = random.uniform(0, 0.15)  # 0-15% change
            return True, visual_hash, diff_score, duration, None
        else:
            return False, "", 0.0, duration, f"Mock failure in visual test for {screen_name}"

    def _execute_compose_test(self, test_method: str) -> Tuple[bool, Dict[str, float], int, Optional[str]]:
        """Mock Compose performance test execution"""
        import random

        success = random.random() > 0.05  # 95% success rate
        duration = random.randint(3000, 10000)  # 3-10 seconds

        if success:
            metrics = {
                "p95_composition_ms": random.uniform(50, 200),
                "p95_frame_ms": random.uniform(10, 25),
                "jank_percentage": random.uniform(0, 8),
                "avg_frame_ms": random.uniform(8, 18)
            }
            return True, metrics, duration, None
        else:
            return False, {}, duration, f"Mock failure in {test_method}"

    def _generate_correlation_id(self) -> str:
        """Generate correlation ID for tracking"""
        import uuid
        return str(uuid.uuid4())

    def _calculate_payload_hash(self, payload: Dict) -> str:
        """Calculate payload schema hash"""
        import hashlib
        schema_str = json.dumps(sorted(payload.keys()))
        return hashlib.md5(schema_str.encode()).hexdigest()[:16]

    def _get_git_sha(self) -> str:
        """Get current git SHA"""
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
            return result.stdout.strip()[:8] if result.returncode == 0 else 'unknown'
        except:
            return 'unknown'

    def _get_git_branch(self) -> str:
        """Get current git branch"""
        try:
            result = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else 'unknown'
        except:
            return 'unknown'

    def _mark_test_run_failed(self, test_run, error_message: str):
        """Mark test run as failed"""
        try:
            test_run.mark_failed(error_message)
        except Exception as e:
            logger.error(f"Failed to mark test run as failed: {e}")


def main():
    """Main entry point for CI/CD integration"""
    import argparse

    parser = argparse.ArgumentParser(description='Mobile Performance Testing CI/CD Integration')
    parser.add_argument('--app-package', default='com.example.testapp', help='Android app package name')
    parser.add_argument('--stream-testbench-url', default='ws://localhost:8000/ws/mobile-sync/', help='Stream Testbench WebSocket URL')
    parser.add_argument('--fail-on-slo-violation', action='store_true', help='Fail CI/CD pipeline on SLO violations')
    parser.add_argument('--output-json', help='Output results to JSON file')

    args = parser.parse_args()

    # Initialize runner
    runner = MobilePerformanceRunner(
        app_package=args.app_package,
        stream_testbench_url=args.stream_testbench_url
    )

    try:
        # Run tests
        results = runner.run_all_tests()

        # Output results
        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(asdict(results), f, indent=2, default=str)
            logger.info(f"Results written to {args.output_json}")

        # Print summary
        print(f"\n{'='*60}")
        print(f"MOBILE PERFORMANCE TEST RESULTS")
        print(f"{'='*60}")
        print(f"Run ID: {results.run_id}")
        print(f"App Version: {results.app_version}")
        print(f"Branch: {results.branch}")
        print(f"Commit: {results.commit_sha}")
        print(f"\nTest Results:")
        print(f"  Total Tests: {len(results.test_results)}")
        print(f"  Passed: {len([r for r in results.test_results if r.success])}")
        print(f"  Failed: {len([r for r in results.test_results if not r.success])}")
        print(f"  SLO Violations: {len(results.slo_violations)}")
        print(f"\nOverall Result: {'PASSED' if results.passed else 'FAILED'}")

        if results.slo_violations:
            print(f"\nSLO Violations:")
            for violation in results.slo_violations:
                print(f"  - {violation['test_name']}: {violation['metric_name']} = {violation['actual_value']:.2f} > {violation['threshold']:.2f} ({violation['violation_percentage']:.1f}% over)")

        # Exit with appropriate code
        if not results.passed and args.fail_on_slo_violation:
            sys.exit(1)
        elif not results.passed:
            print(f"\nNote: SLO violations detected but not failing CI/CD (use --fail-on-slo-violation to fail)")

    except Exception as e:
        logger.error(f"Mobile performance testing failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()