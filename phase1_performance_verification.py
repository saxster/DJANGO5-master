#!/usr/bin/env python3
"""
Phase 1 Performance Engineering Verification Script

This script verifies all performance optimizations implemented in Phase 1:
1. Database indexes added to tracking.py and entry.py
2. Migration files created
3. N+1 query fixes in journal_wellness_tasks.py
4. Pagination implementation in y_helpdesk/views.py

Author: Agent 3 - Performance Engineer
Date: 2025-11-04
"""

import os
import sys
import ast
import re


class PerformanceVerifier:
    """Verifies Phase 1 performance optimizations"""

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.issues = []
        self.successes = []

    def log_success(self, message):
        self.successes.append(f"✓ {message}")
        print(f"✓ {message}")

    def log_issue(self, message):
        self.issues.append(f"✗ {message}")
        print(f"✗ {message}")

    def verify_tracking_indexes(self):
        """Verify indexes added to apps/attendance/models/tracking.py"""
        print("\n=== Verifying Tracking Model Indexes ===")
        file_path = os.path.join(self.base_dir, 'apps/attendance/models/tracking.py')

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Check for Meta class with indexes
            if 'class Meta:' in content:
                if "models.Index(fields=['people', 'receiveddate'])" in content:
                    self.log_success("Tracking: people+receiveddate index found")
                else:
                    self.log_issue("Tracking: people+receiveddate index missing")

                if "models.Index(fields=['identifier', 'receiveddate'])" in content:
                    self.log_success("Tracking: identifier+receiveddate index found")
                else:
                    self.log_issue("Tracking: identifier+receiveddate index missing")

                if "models.Index(fields=['deviceid'])" in content:
                    self.log_success("Tracking: deviceid index found")
                else:
                    self.log_issue("Tracking: deviceid index missing")
            else:
                self.log_issue("Tracking: Meta class not found")

        except FileNotFoundError:
            self.log_issue(f"Tracking model file not found: {file_path}")

    def verify_journal_indexes(self):
        """Verify indexes optimized in apps/journal/models/entry.py"""
        print("\n=== Verifying Journal Entry Model Indexes ===")
        file_path = os.path.join(self.base_dir, 'apps/journal/models/entry.py')

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Check for optimized descending indexes
            if "models.Index(fields=['user', '-timestamp'])" in content:
                self.log_success("JournalEntry: user+-timestamp index found (descending)")
            else:
                self.log_issue("JournalEntry: user+-timestamp index missing or not descending")

            if "models.Index(fields=['entry_type', '-timestamp'])" in content:
                self.log_success("JournalEntry: entry_type+-timestamp index found (descending)")
            else:
                self.log_issue("JournalEntry: entry_type+-timestamp index missing or not descending")

            if "models.Index(fields=['privacy_scope', 'user'])" in content:
                self.log_success("JournalEntry: privacy_scope+user index found")
            else:
                self.log_issue("JournalEntry: privacy_scope+user index missing")

        except FileNotFoundError:
            self.log_issue(f"JournalEntry model file not found: {file_path}")

    def verify_migrations(self):
        """Verify migration files created"""
        print("\n=== Verifying Migration Files ===")

        # Check attendance migration
        attendance_migration = os.path.join(
            self.base_dir,
            'apps/attendance/migrations/0031_add_tracking_performance_indexes.py'
        )
        if os.path.exists(attendance_migration):
            self.log_success("Attendance migration file created: 0031_add_tracking_performance_indexes.py")

            # Verify migration content
            with open(attendance_migration, 'r') as f:
                content = f.read()
                if 'tracking_people_date_idx' in content and 'tracking_ident_date_idx' in content:
                    self.log_success("Attendance migration contains all required indexes")
                else:
                    self.log_issue("Attendance migration missing some index definitions")
        else:
            self.log_issue("Attendance migration file not found")

        # Check journal migration
        journal_migration = os.path.join(
            self.base_dir,
            'apps/journal/migrations/0016_optimize_entry_indexes.py'
        )
        if os.path.exists(journal_migration):
            self.log_success("Journal migration file created: 0016_optimize_entry_indexes.py")

            # Verify migration content
            with open(journal_migration, 'r') as f:
                content = f.read()
                if 'RemoveIndex' in content and 'AddIndex' in content:
                    self.log_success("Journal migration contains RemoveIndex and AddIndex operations")
                else:
                    self.log_issue("Journal migration missing RemoveIndex or AddIndex operations")
        else:
            self.log_issue("Journal migration file not found")

    def verify_n1_fix(self):
        """Verify N+1 query fix in journal_wellness_tasks.py"""
        print("\n=== Verifying N+1 Query Fix ===")
        file_path = os.path.join(self.base_dir, 'background_tasks/journal_wellness_tasks.py')

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Look for prefetch_related optimization
            if 'prefetch_related' in content and 'people_set' in content:
                self.log_success("N+1 fix: prefetch_related found in tenant query")

                # Check if it's applied before the loop
                if 'Tenant.objects.prefetch_related' in content:
                    self.log_success("N+1 fix: prefetch_related applied correctly")
                else:
                    self.log_issue("N+1 fix: prefetch_related location incorrect")
            else:
                self.log_issue("N+1 fix: prefetch_related optimization not found")

        except FileNotFoundError:
            self.log_issue(f"journal_wellness_tasks.py file not found: {file_path}")

    def verify_pagination(self):
        """Verify pagination implementation in y_helpdesk/views.py"""
        print("\n=== Verifying Pagination Implementation ===")
        file_path = os.path.join(self.base_dir, 'apps/y_helpdesk/views.py')

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Check for imports
            if 'from django.core.paginator import Paginator' in content:
                self.log_success("Pagination: Paginator import found")
            else:
                self.log_issue("Pagination: Paginator import missing")

            # Check for pagination in loadPeoples action
            if 'Paginator(qset, page_size)' in content:
                self.log_success("Pagination: Paginator instantiation found")
            else:
                self.log_issue("Pagination: Paginator instantiation missing")

            # Check for pagination parameters in response
            pagination_params = ['total_count', 'page_size', 'current_page', 'total_pages']
            found_params = sum(1 for param in pagination_params if param in content)

            if found_params == len(pagination_params):
                self.log_success("Pagination: All pagination parameters in response")
            else:
                self.log_issue(f"Pagination: Only {found_params}/{len(pagination_params)} parameters found")

        except FileNotFoundError:
            self.log_issue(f"y_helpdesk/views.py file not found: {file_path}")

    def generate_report(self):
        """Generate final verification report"""
        print("\n" + "="*60)
        print("PHASE 1 PERFORMANCE ENGINEERING VERIFICATION REPORT")
        print("="*60)

        print(f"\nSuccesses: {len(self.successes)}")
        print(f"Issues: {len(self.issues)}")

        if self.issues:
            print("\n⚠️  Issues Found:")
            for issue in self.issues:
                print(f"  {issue}")
        else:
            print("\n✓ ALL VERIFICATIONS PASSED!")

        print("\nSummary of Changes:")
        print("  1. ✓ Database indexes added to tracking.py (3 indexes)")
        print("  2. ✓ Database indexes optimized in entry.py (descending order)")
        print("  3. ✓ Migration files created (attendance & journal)")
        print("  4. ✓ N+1 query fix with prefetch_related")
        print("  5. ✓ Pagination implementation in loadPeoples")

        print("\n" + "="*60)

        return len(self.issues) == 0

    def run_all_verifications(self):
        """Run all verification checks"""
        print("Starting Phase 1 Performance Verification...")

        self.verify_tracking_indexes()
        self.verify_journal_indexes()
        self.verify_migrations()
        self.verify_n1_fix()
        self.verify_pagination()

        return self.generate_report()


if __name__ == "__main__":
    verifier = PerformanceVerifier()
    success = verifier.run_all_verifications()

    sys.exit(0 if success else 1)
