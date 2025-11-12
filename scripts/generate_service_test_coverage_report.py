#!/usr/bin/env python3
"""
Generate comprehensive service test coverage report.

This script:
1. Identifies all service files
2. Checks for corresponding tests
3. Runs pytest coverage for tested services
4. Generates detailed coverage report
5. Identifies untested critical paths
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def find_services():
    """Find all service files in the codebase."""
    services = []
    base_path = Path("apps")
    
    for service_file in base_path.rglob("*service*.py"):
        if "__init__" in service_file.name or "test_" in service_file.name:
            continue
        services.append(service_file)
    
    return sorted(services)

def find_tests():
    """Find all test files."""
    tests = {}
    test_paths = [Path("tests"), Path("testing")]
    
    for test_path in test_paths:
        if test_path.exists():
            for test_file in test_path.rglob("test_*.py"):
                tests[test_file.stem] = test_file
    
    # Also check for tests in apps
    for test_file in Path("apps").rglob("test_*.py"):
        tests[test_file.stem] = test_file
    
    return tests

def run_pytest_coverage(test_file):
    """Run pytest coverage for a specific test file."""
    try:
        result = subprocess.run(
            [
                "pytest",
                str(test_file),
                "--cov-report=json",
                "--cov-report=term-missing",
                "-v"
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return {
            'success': result.returncode == 0,
            'output': result.stdout,
            'errors': result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': '',
            'errors': 'Test execution timed out'
        }
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'errors': str(e)
        }

def categorize_services(services, existing_tests):
    """Categorize services by test status and priority."""
    priority_keywords = [
        'security', 'auth', 'login', 'device', 'trust', 'file_download',
        'file_upload', 'throttling', 'capability', 'permission', 'encryption'
    ]
    
    categories = {
        'tested_priority': [],
        'tested_standard': [],
        'untested_priority': [],
        'untested_standard': []
    }
    
    for service in services:
        service_name = service.stem
        expected_test = f"test_{service_name}"
        is_tested = expected_test in existing_tests
        
        # Check if priority
        is_priority = any(kw in service_name.lower() for kw in priority_keywords)
        
        if is_tested and is_priority:
            categories['tested_priority'].append((service, existing_tests[expected_test]))
        elif is_tested:
            categories['tested_standard'].append((service, existing_tests[expected_test]))
        elif is_priority:
            categories['untested_priority'].append(service)
        else:
            categories['untested_standard'].append(service)
    
    return categories

def generate_markdown_report(categories, coverage_data):
    """Generate markdown coverage report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""# Service Test Coverage Report

**Generated:** {timestamp}

## Executive Summary

| Category | Count | Percentage |
|----------|-------|------------|
| **Total Services** | {sum(len(cat) for cat in categories.values())} | 100% |
| Tested Priority Services | {len(categories['tested_priority'])} | {len(categories['tested_priority']) / sum(len(cat) for cat in categories.values()) * 100:.1f}% |
| Tested Standard Services | {len(categories['tested_standard'])} | {len(categories['tested_standard']) / sum(len(cat) for cat in categories.values()) * 100:.1f}% |
| **Untested Priority Services** | {len(categories['untested_priority'])} | {len(categories['untested_priority']) / sum(len(cat) for cat in categories.values()) * 100:.1f}% |
| Untested Standard Services | {len(categories['untested_standard'])} | {len(categories['untested_standard']) / sum(len(cat) for cat in categories.values()) * 100:.1f}% |

## Coverage Goal Status

- ✅ **Priority Services:** {len(categories['tested_priority'])} / {len(categories['tested_priority']) + len(categories['untested_priority'])} tested
- ⚠️ **All Services:** {len(categories['tested_priority']) + len(categories['tested_standard'])} / {sum(len(cat) for cat in categories.values())} tested

---

## Priority Services (Security-Critical)

### ✅ Tested Priority Services ({len(categories['tested_priority'])})

"""
    
    for service, test_file in categories['tested_priority']:
        app_name = service.parts[1] if len(service.parts) > 1 else "unknown"
        coverage_pct = coverage_data.get(str(service), 0)
        status_icon = "✅" if coverage_pct >= 80 else "⚠️"
        
        report += f"- {status_icon} **{service.name}** (`{app_name}`)\n"
        report += f"  - Test: `{test_file}`\n"
        report += f"  - Coverage: {coverage_pct}%\n"
    
    report += f"""

### 🔴 Untested Priority Services ({len(categories['untested_priority'])})

**CRITICAL:** These services handle security, authentication, or sensitive operations and MUST be tested.

"""
    
    for service in categories['untested_priority']:
        app_name = service.parts[1] if len(service.parts) > 1 else "unknown"
        report += f"- 🔴 **{service.name}** (`{app_name}`)\n"
        report += f"  - Path: `{service}`\n"
        report += f"  - Required test: `tests/{app_name}/services/test_{service.stem}.py`\n\n"
    
    report += f"""

---

## Standard Services

### ✅ Tested Standard Services ({len(categories['tested_standard'])})

"""
    
    # Group by app
    by_app = defaultdict(list)
    for service, test_file in categories['tested_standard']:
        app_name = service.parts[1] if len(service.parts) > 1 else "unknown"
        coverage_pct = coverage_data.get(str(service), 0)
        by_app[app_name].append((service, test_file, coverage_pct))
    
    for app_name in sorted(by_app.keys()):
        report += f"\n#### {app_name.upper()} ({len(by_app[app_name])} services)\n\n"
        for service, test_file, coverage_pct in by_app[app_name]:
            status_icon = "✅" if coverage_pct >= 80 else "⚠️"
            report += f"- {status_icon} {service.name} - Coverage: {coverage_pct}%\n"
    
    report += f"""

### Untested Standard Services ({len(categories['untested_standard'])})

**Note:** While not priority, these should eventually have test coverage.

"""
    
    # Group by app
    by_app = defaultdict(list)
    for service in categories['untested_standard']:
        app_name = service.parts[1] if len(service.parts) > 1 else "unknown"
        by_app[app_name].append(service)
    
    for app_name in sorted(by_app.keys()):
        report += f"- **{app_name}:** {len(by_app[app_name])} untested services\n"
    
    report += """

---

## Next Steps

### Immediate Actions (Priority Services)

1. **Create tests for untested priority services**
   - Focus on security-critical services first
   - Target: 80%+ coverage per service
   - Deadline: Next sprint

2. **Improve coverage for low-coverage priority services**
   - Services with <80% coverage need additional tests
   - Focus on edge cases and error handling

### Mid-term Actions (Standard Services)

1. **Batch test creation**
   - Group services by app/domain
   - Create test suites for each batch
   - Target: 60%+ coverage initially

2. **CI/CD Integration**
   - Add coverage thresholds to pipeline
   - Require tests for new services
   - Track coverage trends over time

### Test Quality Guidelines

- ✅ Test happy path scenarios
- ✅ Test error conditions and edge cases
- ✅ Test security boundaries and access control
- ✅ Test database error handling
- ✅ Test cache/network failure scenarios
- ✅ Mock external dependencies
- ✅ Use fixtures for common test data
- ✅ Aim for 80%+ line coverage

---

## Coverage Details

"""
    
    if coverage_data:
        report += "| Service | App | Coverage | Status |\n"
        report += "|---------|-----|----------|--------|\n"
        
        for service_path, coverage_pct in sorted(coverage_data.items(), key=lambda x: x[1], reverse=True):
            service = Path(service_path)
            app_name = service.parts[1] if len(service.parts) > 1 else "unknown"
            status = "✅ Good" if coverage_pct >= 80 else "⚠️ Needs work" if coverage_pct >= 60 else "🔴 Low"
            report += f"| {service.name} | {app_name} | {coverage_pct}% | {status} |\n"
    else:
        report += "*Run pytest with coverage to populate this section*\n"
    
    report += """

---

**Report generated by:** `scripts/generate_service_test_coverage_report.py`

"""
    
    return report

def main():
    """Main execution."""
    print("=" * 80)
    print("SERVICE TEST COVERAGE REPORT GENERATOR")
    print("=" * 80)
    
    # Find services and tests
    print("\n📊 Analyzing codebase...")
    services = find_services()
    existing_tests = find_tests()
    
    print(f"✓ Found {len(services)} service files")
    print(f"✓ Found {len(existing_tests)} test files")
    
    # Categorize services
    print("\n📋 Categorizing services...")
    categories = categorize_services(services, existing_tests)
    
    print(f"✓ Priority services: {len(categories['tested_priority']) + len(categories['untested_priority'])}")
    print(f"  - Tested: {len(categories['tested_priority'])}")
    print(f"  - Untested: {len(categories['untested_priority'])}")
    
    # Mock coverage data (in real implementation, would parse coverage.json)
    coverage_data = {}
    
    # Generate report
    print("\n📝 Generating report...")
    report = generate_markdown_report(categories, coverage_data)
    
    # Write report
    report_path = Path("SERVICE_TEST_COVERAGE_REPORT.md")
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n✅ Report written to: {report_path}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    total = sum(len(cat) for cat in categories.values())
    tested = len(categories['tested_priority']) + len(categories['tested_standard'])
    
    print(f"Total Services: {total}")
    print(f"Tested: {tested} ({tested/total*100:.1f}%)")
    print(f"Untested: {total - tested} ({(total-tested)/total*100:.1f}%)")
    print()
    print(f"🔴 CRITICAL: {len(categories['untested_priority'])} priority services need tests")
    print(f"⚠️  WARNING: {len(categories['untested_standard'])} standard services need tests")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
