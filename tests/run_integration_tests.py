#!/usr/bin/env python
"""
Integration test runner for Django ORM migration.
Runs tests in phases and generates detailed reports.
"""

import os
import sys
import django
import json
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

import unittest
from django.test.utils import get_runner
from django.conf import settings
from django.test import TestCase
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)


class IntegrationTestRunner:
    """Custom test runner for integration tests"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'phases': {},
            'summary': {
                'total_tests': 0,
                'passed': 0,
                'failed': 0,
                'errors': 0,
                'skipped': 0
            }
        }
    
    def print_header(self, text, level=1):
        """Print formatted header"""
        if level == 1:
            print(f"\n{Fore.BLUE}{'=' * 80}")
            print(f"{Fore.BLUE}{text.center(80)}")
            print(f"{Fore.BLUE}{'=' * 80}{Style.RESET_ALL}\n")
        elif level == 2:
            print(f"\n{Fore.CYAN}{'-' * 60}")
            print(f"{Fore.CYAN}{text}")
            print(f"{Fore.CYAN}{'-' * 60}{Style.RESET_ALL}\n")
    
    def print_success(self, text):
        """Print success message"""
        print(f"{Fore.GREEN}✓ {text}{Style.RESET_ALL}")
    
    def print_error(self, text):
        """Print error message"""
        print(f"{Fore.RED}✗ {text}{Style.RESET_ALL}")
    
    def print_warning(self, text):
        """Print warning message"""
        print(f"{Fore.YELLOW}⚠ {text}{Style.RESET_ALL}")
    
    def run_phase_1_tests(self):
        """Phase 1: Test individual query methods"""
        self.print_header("PHASE 1: Individual Query Method Tests", 2)
        
        test_modules = [
            ('Capability Queries', 'test_orm_migration.TestCapabilityQueries'),
            ('BT Queries', 'test_orm_migration.TestBtQueries'),
            ('Ticket Queries', 'test_orm_migration.TestTicketQueries'),
            ('Asset Queries', 'test_orm_migration.TestAssetQueries'),
            ('Tree Traversal', 'test_orm_migration.TestTreeTraversal'),
        ]
        
        phase_results = []
        
        for name, test_class in test_modules:
            print(f"\nTesting {name}...")
            
            # Run the specific test class
            suite = unittest.TestLoader().loadTestsFromName(test_class)
            runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
            result = runner.run(suite)
            
            if result.wasSuccessful():
                self.print_success(f"{name}: All tests passed ({result.testsRun} tests)")
                phase_results.append({
                    'module': name,
                    'status': 'passed',
                    'tests_run': result.testsRun
                })
            else:
                self.print_error(f"{name}: {len(result.failures)} failures, {len(result.errors)} errors")
                phase_results.append({
                    'module': name,
                    'status': 'failed',
                    'tests_run': result.testsRun,
                    'failures': len(result.failures),
                    'errors': len(result.errors)
                })
        
        self.results['phases']['phase_1'] = phase_results
        return all(r['status'] == 'passed' for r in phase_results)
    
    def run_phase_2_tests(self):
        """Phase 2: Test report queries"""
        self.print_header("PHASE 2: Report Query Tests", 2)
        
        test_modules = [
            ('Report Queries', 'test_orm_migration.TestReportQueries'),
            ('Attendance Queries', 'test_orm_migration.TestAttendanceQueries'),
        ]
        
        phase_results = []
        
        for name, test_class in test_modules:
            print(f"\nTesting {name}...")
            
            suite = unittest.TestLoader().loadTestsFromName(test_class)
            runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
            result = runner.run(suite)
            
            if result.wasSuccessful():
                self.print_success(f"{name}: All tests passed ({result.testsRun} tests)")
                phase_results.append({
                    'module': name,
                    'status': 'passed',
                    'tests_run': result.testsRun
                })
            else:
                self.print_error(f"{name}: {len(result.failures)} failures, {len(result.errors)} errors")
                phase_results.append({
                    'module': name,
                    'status': 'failed',
                    'tests_run': result.testsRun,
                    'failures': len(result.failures),
                    'errors': len(result.errors)
                })
        
        self.results['phases']['phase_2'] = phase_results
        return all(r['status'] == 'passed' for r in phase_results)
    
    def run_phase_3_tests(self):
        """Phase 3: Test manager integrations"""
        self.print_header("PHASE 3: Manager Integration Tests", 2)
        
        test_modules = [
            ('Background Tasks', 'test_orm_migration.TestBackgroundTaskQueries'),
            ('Manager Integration', 'test_orm_migration.TestManagerIntegration'),
        ]
        
        phase_results = []
        
        for name, test_class in test_modules:
            print(f"\nTesting {name}...")
            
            suite = unittest.TestLoader().loadTestsFromName(test_class)
            runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
            result = runner.run(suite)
            
            if result.wasSuccessful():
                self.print_success(f"{name}: All tests passed ({result.testsRun} tests)")
                phase_results.append({
                    'module': name,
                    'status': 'passed',
                    'tests_run': result.testsRun
                })
            else:
                self.print_error(f"{name}: {len(result.failures)} failures, {len(result.errors)} errors")
                phase_results.append({
                    'module': name,
                    'status': 'failed',
                    'tests_run': result.testsRun,
                    'failures': len(result.failures),
                    'errors': len(result.errors)
                })
        
        self.results['phases']['phase_3'] = phase_results
        return all(r['status'] == 'passed' for r in phase_results)
    
    def run_performance_tests(self):
        """Run performance comparison tests"""
        self.print_header("PERFORMANCE TESTS", 2)
        
        print("Running performance comparison tests...")
        
        suite = unittest.TestLoader().loadTestsFromName('test_orm_migration.TestPerformanceComparison')
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        if result.wasSuccessful():
            self.print_success("Performance tests passed")
            return True
        else:
            self.print_error("Performance tests failed")
            return False
    
    def generate_report(self):
        """Generate detailed test report"""
        self.print_header("TEST SUMMARY REPORT", 1)
        
        # Calculate totals
        total_tests = 0
        total_passed = 0
        total_failed = 0
        
        for phase, results in self.results['phases'].items():
            for test_result in results:
                total_tests += test_result['tests_run']
                if test_result['status'] == 'passed':
                    total_passed += test_result['tests_run']
                else:
                    total_failed += test_result.get('failures', 0) + test_result.get('errors', 0)
        
        # Update summary
        self.results['summary']['total_tests'] = total_tests
        self.results['summary']['passed'] = total_passed
        self.results['summary']['failed'] = total_failed
        
        # Print summary
        print(f"Total Tests Run: {total_tests}")
        print(f"Passed: {Fore.GREEN}{total_passed}{Style.RESET_ALL}")
        print(f"Failed: {Fore.RED}{total_failed}{Style.RESET_ALL}")
        
        if total_failed == 0:
            self.print_success("\nAll integration tests passed successfully!")
        else:
            self.print_error(f"\n{total_failed} tests failed. Please review the failures.")
        
        # Save report to file
        report_path = project_root / 'tests' / 'integration_test_report.json'
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_path}")
    
    def run_all_tests(self):
        """Run all integration tests in phases"""
        self.print_header("DJANGO ORM MIGRATION INTEGRATION TESTS", 1)
        
        print("Starting comprehensive integration testing...")
        print(f"Test database: {settings.DATABASES['default']['NAME']}")
        print(f"Django version: {django.VERSION}")
        
        # Run tests in phases
        phase1_success = self.run_phase_1_tests()
        phase2_success = self.run_phase_2_tests()
        phase3_success = self.run_phase_3_tests()
        perf_success = self.run_performance_tests()
        
        # Generate report
        self.generate_report()
        
        # Return overall success
        return all([phase1_success, phase2_success, phase3_success, perf_success])


def check_calling_files():
    """Check all files that call the ORM queries"""
    print("\n" + "=" * 80)
    print("CHECKING CALLING FILES".center(80))
    print("=" * 80 + "\n")
    
    calling_files = [
        # Report design files
        'apps/reports/report_designs/task_summary.py',
        'apps/reports/report_designs/tour_summary.py',
        'apps/reports/report_designs/site_report.py',
        'apps/reports/report_designs/RP_SiteVisitReport.py',
        'apps/reports/report_designs/people_attendance_summary.py',
        
        # Background task files
        'background_tasks/tasks.py',
        'background_tasks/utils.py',
        'background_tasks/report_tasks.py',
        
        # Manager files
        'apps/y_helpdesk/managers.py',
        'apps/onboarding/managers.py',
        'apps/attendance/managers.py',
        'apps/activity/managers/asset_manager.py',
        
        # Utility files
        'apps/peoples/utils.py',
        'apps/core/utils_new/business_logic.py',
    ]
    
    issues = []
    
    for file_path in calling_files:
        full_path = project_root / file_path
        if full_path.exists():
            with open(full_path, 'r') as f:
                content = f.read()
                
            # Check for any remaining raw SQL usage
            if 'runrawsql' in content and 'get_query' in content:
                # Check if it's using the new ORM
                if 'apps.core.queries' not in content:
                    issues.append({
                        'file': file_path,
                        'issue': 'Still using raw SQL without ORM import'
                    })
        else:
            issues.append({
                'file': file_path,
                'issue': 'File not found'
            })
    
    if issues:
        print(f"{Fore.YELLOW}Found {len(issues)} potential issues:{Style.RESET_ALL}")
        for issue in issues:
            print(f"  - {issue['file']}: {issue['issue']}")
    else:
        print(f"{Fore.GREEN}✓ All calling files properly updated{Style.RESET_ALL}")
    
    return len(issues) == 0


def main():
    """Main entry point"""
    # Check Python version
    if sys.version_info < (3, 8):
        print(f"{Fore.RED}Error: Python 3.8+ required{Style.RESET_ALL}")
        sys.exit(1)
    
    # Create test runner
    runner = IntegrationTestRunner()
    
    # Check calling files first
    files_ok = check_calling_files()
    
    # Run integration tests
    tests_passed = runner.run_all_tests()
    
    # Exit with appropriate code
    if tests_passed and files_ok:
        print(f"\n{Fore.GREEN}✓ All integration tests passed successfully!{Style.RESET_ALL}")
        sys.exit(0)
    else:
        print(f"\n{Fore.RED}✗ Some tests or checks failed. Please review the output.{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == '__main__':
    main()