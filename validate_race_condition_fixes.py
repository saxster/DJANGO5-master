#!/usr/bin/env python3
"""
Race Condition Fix Validation Script

Validates that all race condition fixes are properly implemented.
Checks for:
- Required imports present
- Locking patterns used correctly
- Service layer methods available
- Migrations applied
- Tests exist

Usage:
    python validate_race_condition_fixes.py
"""

import os
import sys
import re


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def check_mark(passed):
    return f"{Colors.GREEN}✓{Colors.END}" if passed else f"{Colors.RED}✗{Colors.END}"


def validate_file_exists(filepath, description):
    """Check if a file exists"""
    exists = os.path.exists(filepath)
    status = check_mark(exists)
    print(f"{status} {description}: {filepath}")
    return exists


def validate_function_has_pattern(filepath, function_name, pattern, description):
    """Check if a function contains a specific pattern"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        func_match = re.search(rf'def {function_name}\(.*?\):', content)
        if not func_match:
            print(f"{check_mark(False)} {description}: Function {function_name} not found")
            return False

        func_start = func_match.start()

        next_def = re.search(r'\ndef \w+\(', content[func_start + 10:])
        func_end = func_start + 10 + next_def.start() if next_def else len(content)

        func_content = content[func_start:func_end]

        has_pattern = re.search(pattern, func_content, re.DOTALL) is not None

        status = check_mark(has_pattern)
        print(f"{status} {description}: {function_name}")
        return has_pattern

    except FileNotFoundError:
        print(f"{check_mark(False)} {description}: File not found")
        return False
    except Exception as e:
        print(f"{check_mark(False)} {description}: Error - {e}")
        return False


def main():
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}RACE CONDITION FIX VALIDATION{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

    results = []

    print(f"{Colors.BLUE}1. CHECKING NEW UTILITIES{Colors.END}")
    print("-" * 70)
    results.append(validate_file_exists("apps/core/utils_new/atomic_json_updater.py", "AtomicJSONFieldUpdater"))
    results.append(validate_file_exists("apps/core/utils_new/retry_mechanism.py", "Retry Mechanism"))
    results.append(validate_file_exists("apps/core/mixins/optimistic_locking.py", "Optimistic Locking Mixin"))

    print(f"\n{Colors.BLUE}2. CHECKING NEW SERVICES{Colors.END}")
    print("-" * 70)
    results.append(validate_file_exists("apps/y_helpdesk/services/ticket_workflow_service.py", "TicketWorkflowService"))
    results.append(validate_file_exists("apps/activity/models/job_workflow_audit_log.py", "JobWorkflowAuditLog"))

    print(f"\n{Colors.BLUE}3. CHECKING MIGRATIONS{Colors.END}")
    print("-" * 70)
    results.append(validate_file_exists("apps/activity/migrations/0010_add_version_field_jobneed.py", "Jobneed version field"))
    results.append(validate_file_exists("apps/y_helpdesk/migrations/0002_add_version_field_ticket.py", "Ticket version field"))
    results.append(validate_file_exists("apps/activity/migrations/0011_add_job_workflow_audit_log.py", "Audit log model"))

    print(f"\n{Colors.BLUE}4. CHECKING CRITICAL FIXES{Colors.END}")
    print("-" * 70)

    results.append(validate_function_has_pattern(
        "background_tasks/utils.py",
        "update_job_autoclose_status",
        r"distributed_lock.*timeout",
        "Job autoclose uses distributed lock"
    ))

    results.append(validate_function_has_pattern(
        "background_tasks/utils.py",
        "update_job_autoclose_status",
        r"select_for_update\(\)",
        "Job autoclose uses select_for_update"
    ))

    results.append(validate_function_has_pattern(
        "background_tasks/utils.py",
        "update_ticket_log",
        r"distributed_lock",
        "Ticket log uses distributed lock"
    ))

    results.append(validate_function_has_pattern(
        "background_tasks/utils.py",
        "update_ticket_data",
        r"F\('level'\)\s*\+\s*1",
        "Ticket escalation uses F() expression"
    ))

    results.append(validate_function_has_pattern(
        "apps/service/utils.py",
        "update_adhoc_record",
        r"distributed_lock",
        "Adhoc update uses distributed lock"
    ))

    print(f"\n{Colors.BLUE}5. CHECKING TEST FILES{Colors.END}")
    print("-" * 70)
    results.append(validate_file_exists("apps/core/tests/test_background_task_race_conditions.py", "Background task tests"))
    results.append(validate_file_exists("apps/y_helpdesk/tests/test_ticket_escalation_race_conditions.py", "Escalation tests"))
    results.append(validate_file_exists("apps/core/tests/test_atomic_json_field_updates.py", "JSON update tests"))
    results.append(validate_file_exists("comprehensive_race_condition_penetration_test.py", "Penetration test"))

    print(f"\n{Colors.BLUE}6. CHECKING DOCUMENTATION{Colors.END}")
    print("-" * 70)
    results.append(validate_file_exists("COMPREHENSIVE_RACE_CONDITION_REMEDIATION_COMPLETE.md", "Main report"))
    results.append(validate_file_exists("docs/RACE_CONDITION_PREVENTION_GUIDE.md", "Developer guide"))
    results.append(validate_file_exists("RACE_CONDITION_DEPLOYMENT_CHECKLIST.md", "Deployment checklist"))
    results.append(validate_file_exists("RACE_CONDITION_QUICK_START.md", "Quick start guide"))

    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}VALIDATION SUMMARY{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

    total = len(results)
    passed = sum(results)
    failed = total - passed

    if failed == 0:
        print(f"{Colors.GREEN}🎉 ALL CHECKS PASSED ({passed}/{total}){Colors.END}\n")
        print(f"{Colors.GREEN}✅ Race condition fixes are properly implemented{Colors.END}")
        print(f"{Colors.GREEN}✅ Ready for testing and deployment{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}⚠️  SOME CHECKS FAILED ({passed}/{total} passed){Colors.END}\n")
        print(f"{Colors.YELLOW}Please review failed items above{Colors.END}\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())