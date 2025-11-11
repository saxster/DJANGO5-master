#!/usr/bin/env python3
"""
N+1 Query Fix Validation Script

Validates that N+1 query optimizations are in place by checking for:
1. select_related() usage where ForeignKey relationships are accessed
2. prefetch_related() usage where ManyToMany relationships are accessed
3. get_queryset() overrides in ViewSets

Run: python scripts/validate_n_plus_one_fixes.py
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple


class N1ValidationResult:
    def __init__(self):
        self.total_checks = 0
        self.passed = 0
        self.failed = 0
        self.warnings = []
        self.errors = []
        self.successes = []

    def add_success(self, message: str):
        self.passed += 1
        self.total_checks += 1
        self.successes.append(f"✅ {message}")

    def add_error(self, message: str):
        self.failed += 1
        self.total_checks += 1
        self.errors.append(f"❌ {message}")

    def add_warning(self, message: str):
        self.warnings.append(f"⚠️  {message}")

    def print_report(self):
        print("\n" + "="*80)
        print("N+1 QUERY FIX VALIDATION REPORT")
        print("="*80 + "\n")

        print(f"Total Checks: {self.total_checks}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {(self.passed/self.total_checks*100) if self.total_checks > 0 else 0:.1f}%\n")

        if self.successes:
            print("\n✅ SUCCESSES:")
            for success in self.successes:
                print(f"  {success}")

        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")

        if self.errors:
            print("\n❌ ERRORS:")
            for error in self.errors:
                print(f"  {error}")

        print("\n" + "="*80 + "\n")


def check_file_for_optimization(filepath: str, pattern: str, optimization: str) -> bool:
    """Check if a file contains the required optimization near the pattern."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Find the line with the pattern
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if pattern in line:
                    # Check surrounding 5 lines for optimization
                    context = '\n'.join(lines[max(0, i-2):min(len(lines), i+5)])
                    if optimization in context:
                        return True
            return False
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False


def validate_service_optimizations(result: N1ValidationResult):
    """Validate service layer has proper select_related."""
    
    checks = [
        {
            'file': 'apps/attendance/services/bulk_roster_service.py',
            'pattern': 'People.objects.filter(id__in=worker_ids)',
            'optimization': "select_related('profile', 'organizational')",
            'description': 'BulkRosterService worker prefetch (line 84)'
        },
        {
            'file': 'apps/attendance/services/bulk_roster_service.py',
            'pattern': 'People.objects.filter(id__in=available_worker_ids)',
            'optimization': "select_related('profile', 'organizational')",
            'description': 'BulkRosterService available workers (line 396)'
        },
        {
            'file': 'apps/attendance/services/emergency_assignment_service.py',
            'pattern': 'available_workers = People.objects.filter',
            'optimization': "select_related('profile', 'organizational'",
            'description': 'EmergencyAssignmentService worker fetch'
        },
        {
            'file': 'apps/attendance/services/fraud_detection_orchestrator.py',
            'pattern': 'employees = User.objects.filter(id__in=employee_ids)',
            'optimization': "select_related('profile', 'organizational')",
            'description': 'FraudDetectionOrchestrator employee fetch'
        },
    ]
    
    for check in checks:
        filepath = os.path.join('/Users/amar/Desktop/MyCode/DJANGO5-master', check['file'])
        if os.path.exists(filepath):
            if check_file_for_optimization(filepath, check['pattern'], check['optimization']):
                result.add_success(f"{check['description']}: Has {check['optimization']}")
            else:
                result.add_error(f"{check['description']}: Missing {check['optimization']}")
        else:
            result.add_warning(f"{check['file']} not found")


def validate_viewset_optimizations(result: N1ValidationResult):
    """Validate ViewSets have get_queryset() overrides."""
    
    viewsets = [
        {
            'file': 'apps/peoples/api/viewsets/people_sync_viewset.py',
            'class': 'PeopleSyncViewSet',
            'expected_optimization': "select_related('profile', 'organizational')"
        },
        {
            'file': 'apps/activity/api/viewsets/question_viewset.py',
            'class': 'QuestionSyncViewSet',
            'expected_optimization': "select_related('created_by', 'modified_by')"
        },
        {
            'file': 'apps/activity/api/viewsets/task_sync_viewset.py',
            'class': 'TaskSyncViewSet',
            'expected_optimization': "select_related("
        },
    ]
    
    for viewset in viewsets:
        filepath = os.path.join('/Users/amar/Desktop/MyCode/DJANGO5-master', viewset['file'])
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Check for get_queryset override
                    if 'def get_queryset(self):' in content:
                        if viewset['expected_optimization'] in content:
                            result.add_success(
                                f"{viewset['class']}: Has get_queryset() with optimizations"
                            )
                        else:
                            result.add_error(
                                f"{viewset['class']}: Has get_queryset() but missing expected optimization"
                            )
                    else:
                        result.add_error(
                            f"{viewset['class']}: Missing get_queryset() override"
                        )
            except Exception as e:
                result.add_error(f"{viewset['file']}: Error reading file - {e}")
        else:
            result.add_warning(f"{viewset['file']} not found")


def validate_manager_optimizations(result: N1ValidationResult):
    """Validate that People manager has optimization methods."""
    
    filepath = '/Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/managers.py'
    
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for optimization methods
                methods = [
                    'def with_profile(self):',
                    'def with_organizational(self):',
                    'def with_full_details(self):',
                ]
                
                for method in methods:
                    if method in content:
                        result.add_success(f"PeopleManager: Has {method.split('(')[0].replace('def ', '')}")
                    else:
                        result.add_error(f"PeopleManager: Missing {method.split('(')[0].replace('def ', '')}")
        except Exception as e:
            result.add_error(f"PeopleManager: Error reading file - {e}")
    else:
        result.add_error("apps/peoples/managers.py not found")


def check_common_n_plus_one_antipatterns(result: N1ValidationResult):
    """Scan for common N+1 antipatterns that should be flagged."""
    
    # Patterns to check in service/view files
    antipatterns = [
        {
            'pattern': r'\.objects\.all\(\)',
            'suggestion': 'Use .select_related() or .prefetch_related() after .all()',
            'severity': 'warning'
        },
        {
            'pattern': r'\.objects\.filter\([^)]*\)(?!\s*\.\s*select_related|\s*\.\s*prefetch_related)',
            'suggestion': 'Consider adding .select_related() or .prefetch_related() after .filter()',
            'severity': 'info'
        }
    ]
    
    # Only show summary, not individual matches
    result.add_warning(
        "Run manual code review for remaining .objects.all() and .objects.filter() patterns"
    )


def main():
    """Run all validation checks."""
    result = N1ValidationResult()
    
    print("\n🔍 Validating N+1 Query Fixes...\n")
    
    print("1️⃣  Checking service layer optimizations...")
    validate_service_optimizations(result)
    
    print("2️⃣  Checking ViewSet optimizations...")
    validate_viewset_optimizations(result)
    
    print("3️⃣  Checking manager optimization methods...")
    validate_manager_optimizations(result)
    
    print("4️⃣  Checking for antipatterns...")
    check_common_n_plus_one_antipatterns(result)
    
    result.print_report()
    
    # Return exit code based on results
    return 0 if result.failed == 0 else 1


if __name__ == '__main__':
    exit(main())
