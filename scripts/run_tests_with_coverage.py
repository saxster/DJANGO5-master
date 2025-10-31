#!/usr/bin/env python
"""
Test runner with coverage reporting for YOUTILITY5
Provides comprehensive test execution and coverage analysis
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime

from apps.core.constants.datetime_constants import FILE_TIMESTAMP_FORMAT


class TestRunner:
    """Manages test execution and coverage reporting"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.python_path = "/home/redmine/DJANGO5/django5-env/bin/python"
        self.coverage_dir = self.project_root / "coverage_reports"
        self.timestamp = datetime.now().strftime(FILE_TIMESTAMP_FORMAT)

    def ensure_coverage_dir(self):
        """Create coverage directory if it doesn't exist"""
        self.coverage_dir.mkdir(exist_ok=True)
        (self.coverage_dir / "html").mkdir(exist_ok=True)
        (self.coverage_dir / "xml").mkdir(exist_ok=True)
        (self.coverage_dir / "json").mkdir(exist_ok=True)

    def run_tests(self, app=None, specific_test=None, verbose=False):
        """
        Run tests with coverage

        Args:
            app: Specific app to test (e.g., 'peoples')
            specific_test: Specific test file or class
            verbose: Enable verbose output
        """
        self.ensure_coverage_dir()

        # Build test command
        cmd = [
            self.python_path,
            "-m", "pytest",
            "--cov=apps",
            "--cov-report=term-missing",
            f"--cov-report=html:{self.coverage_dir}/html",
            f"--cov-report=xml:{self.coverage_dir}/xml/coverage_{self.timestamp}.xml",
            f"--cov-report=json:{self.coverage_dir}/json/coverage_{self.timestamp}.json",
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        # Add specific test target
        if app:
            cmd.append(f"apps/{app}/tests/")
        elif specific_test:
            cmd.append(specific_test)
        else:
            cmd.append("apps/")

        # Set environment variables
        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = "intelliwiz_config.settings.test"
        env["PYTHONPATH"] = str(self.project_root)

        print(f"Running: {' '.join(cmd)}")
        print("=" * 80)

        # Run tests
        result = subprocess.run(cmd, env=env, capture_output=False, text=True)

        return result.returncode

    def run_security_tests(self):
        """Run security-focused tests"""
        print("\n" + "=" * 80)
        print("RUNNING SECURITY TESTS")
        print("=" * 80)

        cmd = [
            self.python_path,
            "-m", "pytest",
            "-m", "security",
            "--tb=short",
            "apps/"
        ]

        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = "intelliwiz_config.settings.test"

        result = subprocess.run(cmd, env=env, capture_output=False, text=True)
        return result.returncode

    def run_performance_tests(self):
        """Run performance tests"""
        print("\n" + "=" * 80)
        print("RUNNING PERFORMANCE TESTS")
        print("=" * 80)

        cmd = [
            self.python_path,
            "-m", "pytest",
            "-m", "performance",
            "--tb=short",
            "apps/"
        ]

        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = "intelliwiz_config.settings.test"

        result = subprocess.run(cmd, env=env, capture_output=False, text=True)
        return result.returncode

    def generate_coverage_report(self):
        """Generate detailed coverage report"""
        print("\n" + "=" * 80)
        print("COVERAGE SUMMARY")
        print("=" * 80)

        # Read JSON coverage report
        json_files = list((self.coverage_dir / "json").glob("coverage_*.json"))
        if json_files:
            latest_json = max(json_files, key=lambda p: p.stat().st_mtime)

            with open(latest_json) as f:
                coverage_data = json.load(f)

            # Calculate statistics
            total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)

            print(f"\nOverall Coverage: {total_coverage:.2f}%")
            print(f"HTML Report: file://{self.coverage_dir}/html/index.html")

            # Show per-app coverage
            print("\nPer-App Coverage:")
            print("-" * 40)

            files = coverage_data.get("files", {})
            app_coverage = {}

            for file_path, file_data in files.items():
                if "/apps/" in file_path:
                    app_name = file_path.split("/apps/")[1].split("/")[0]
                    if app_name not in app_coverage:
                        app_coverage[app_name] = {
                            "covered": 0,
                            "total": 0
                        }

                    summary = file_data.get("summary", {})
                    app_coverage[app_name]["covered"] += summary.get("covered_lines", 0)
                    app_coverage[app_name]["total"] += summary.get("num_statements", 0)

            for app, data in sorted(app_coverage.items()):
                if data["total"] > 0:
                    percent = (data["covered"] / data["total"]) * 100
                    status = "✓" if percent >= 80 else "⚠" if percent >= 60 else "✗"
                    print(f"{status} {app:20s}: {percent:6.2f}% ({data['covered']}/{data['total']} lines)")

    def run_specific_tests(self):
        """Interactive test runner"""
        print("\n" + "=" * 80)
        print("YOUTILITY5 TEST RUNNER")
        print("=" * 80)
        print("\nSelect test option:")
        print("1. Run all tests with coverage")
        print("2. Run tests for specific app")
        print("3. Run security tests")
        print("4. Run performance tests")
        print("5. Run specific test file")
        print("6. Generate coverage report only")
        print("0. Exit")

        choice = input("\nEnter choice (0-6): ").strip()

        if choice == "1":
            return self.run_tests(verbose=True)
        elif choice == "2":
            app = input("Enter app name (e.g., peoples, activity): ").strip()
            return self.run_tests(app=app, verbose=True)
        elif choice == "3":
            return self.run_security_tests()
        elif choice == "4":
            return self.run_performance_tests()
        elif choice == "5":
            test_file = input("Enter test file path: ").strip()
            return self.run_tests(specific_test=test_file, verbose=True)
        elif choice == "6":
            self.generate_coverage_report()
            return 0
        elif choice == "0":
            print("Exiting...")
            return 0
        else:
            print("Invalid choice!")
            return 1


def main():
    """Main entry point"""
    runner = TestRunner()

    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            exit_code = runner.run_tests(verbose=True)
        elif sys.argv[1] == "--app" and len(sys.argv) > 2:
            exit_code = runner.run_tests(app=sys.argv[2], verbose=True)
        elif sys.argv[1] == "--security":
            exit_code = runner.run_security_tests()
        elif sys.argv[1] == "--performance":
            exit_code = runner.run_performance_tests()
        elif sys.argv[1] == "--coverage":
            runner.generate_coverage_report()
            exit_code = 0
        elif sys.argv[1] == "--help":
            print("""
Usage: python run_tests_with_coverage.py [OPTIONS]

Options:
  --all              Run all tests with coverage
  --app APP_NAME     Run tests for specific app
  --security         Run security tests only
  --performance      Run performance tests only
  --coverage         Generate coverage report
  --help             Show this help message

Interactive mode:
  python run_tests_with_coverage.py
            """)
            exit_code = 0
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
            exit_code = 1
    else:
        # Interactive mode
        exit_code = runner.run_specific_tests()

    # Always generate coverage report after tests
    if exit_code == 0 and "--coverage" not in sys.argv:
        runner.generate_coverage_report()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
