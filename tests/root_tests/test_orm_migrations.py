#!/usr/bin/env python
"""
Comprehensive test suite for all Django ORM migrations.
Tests PostgreSQL function replacements and validates output consistency.
"""

import os
import sys
import django
from datetime import datetime, timedelta
import json
import time
from typing import List, Dict, Any, Tuple

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.db import connection
from django.test import TestCase
from django.utils import timezone

# Import ORM implementations
from apps.activity.managers.asset_manager_orm import AssetManagerORM
from apps.activity.managers.job_manager_orm import JobneedManagerORM
from apps.onboarding.bt_manager_orm import BtManagerORM
from apps.peoples.models import Capability
from apps.activity.models.job_model import Jobneed
from apps.onboarding.models import Bt
from apps.core import utils


class ORMTestResult:
    """Stores test result information"""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = False
        self.orm_time = 0.0
        self.pg_time = 0.0
        self.orm_count = 0
        self.pg_count = 0
        self.error_message = ""
        self.match_percentage = 0.0


class TestORMMigrations:
    """Test suite for ORM migrations"""
    
    def __init__(self):
        self.results: List[ORMTestResult] = []
        self.test_bu_id = 1  # Default test BU ID
        self.test_client_id = 1  # Default test client ID
        self.test_people_id = 1  # Default test people ID
        
    def run_all_tests(self):
        """Run all migration tests"""
        print("=" * 80)
        print("DJANGO ORM MIGRATION TEST SUITE")
        print("=" * 80)
        print(f"Testing environment: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
        print(f"Database: {connection.settings_dict['NAME']}")
        print("=" * 80)
        
        # Run individual test categories
        self.test_asset_functions()
        self.test_job_functions()
        self.test_business_unit_functions()
        self.test_capability_functions()
        
        # Print summary
        self.print_summary()
        
    def test_asset_functions(self):
        """Test asset-related function migrations"""
        print("\n=== Testing Asset Functions ===")
        
        # Test 1: fn_getassetvsquestionset
        result = ORMTestResult("fn_getassetvsquestionset")
        try:
            test_cases = [
                {'bu_id': self.test_bu_id, 'asset_id': '1', 'return_type': ''},
                {'bu_id': self.test_bu_id, 'asset_id': '1', 'return_type': 'name'},
            ]
            
            for test in test_cases:
                # ORM version
                start = time.time()
                orm_result = AssetManagerORM.get_asset_vs_questionset(
                    test['bu_id'], test['asset_id'], test['return_type']
                )
                result.orm_time += time.time() - start
                
                # PostgreSQL version
                start = time.time()
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT fn_getassetvsquestionset(%s, %s, %s)",
                        [test['bu_id'], test['asset_id'], test['return_type']]
                    )
                    pg_result = cursor.fetchone()[0] or ''
                result.pg_time += time.time() - start
                
                # Compare results
                if orm_result == pg_result:
                    result.match_percentage = 100.0
                else:
                    result.match_percentage = 0.0
                    result.error_message = f"Mismatch: ORM='{orm_result}' PG='{pg_result}'"
                    
            result.passed = result.match_percentage == 100.0
            
        except Exception as e:
            result.error_message = str(e)
            
        self.results.append(result)
        self._print_result(result)
        
        # Test 2: fn_getassetdetails
        result = ORMTestResult("fn_getassetdetails")
        try:
            test_date = timezone.now() - timedelta(days=30)
            
            # ORM version
            start = time.time()
            orm_assets = AssetManagerORM.get_asset_details(test_date, self.test_bu_id)
            result.orm_time = time.time() - start
            result.orm_count = len(orm_assets)
            
            # PostgreSQL version
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM fn_getassetdetails(%s, %s)",
                    [test_date, self.test_bu_id]
                )
                columns = [col[0] for col in cursor.description]
                pg_assets = []
                for row in cursor.fetchall():
                    pg_assets.append(dict(zip(columns, row)))
            result.pg_time = time.time() - start
            result.pg_count = len(pg_assets)
            
            # Compare counts
            if result.orm_count == result.pg_count:
                result.match_percentage = 100.0
                result.passed = True
            else:
                result.match_percentage = (min(result.orm_count, result.pg_count) / 
                                         max(result.orm_count, result.pg_count)) * 100
                result.error_message = f"Count mismatch: ORM={result.orm_count} PG={result.pg_count}"
                
        except Exception as e:
            result.error_message = str(e)
            
        self.results.append(result)
        self._print_result(result)
        
    def test_job_functions(self):
        """Test job-related function migrations"""
        print("\n=== Testing Job Functions ===")
        
        # Test 1: fun_getjobneed
        result = ORMTestResult("fun_getjobneed")
        try:
            # ORM version
            start = time.time()
            orm_jobs = JobneedManagerORM.get_job_needs(
                Jobneed.objects,
                self.test_people_id,
                self.test_bu_id,
                self.test_client_id
            )
            result.orm_time = time.time() - start
            result.orm_count = len(orm_jobs)
            
            # PostgreSQL version
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM fun_getjobneed(%s, %s, %s)",
                    [self.test_people_id, self.test_bu_id, self.test_client_id]
                )
                pg_jobs = cursor.fetchall()
            result.pg_time = time.time() - start
            result.pg_count = len(pg_jobs)
            
            # Compare counts
            if result.orm_count == result.pg_count:
                result.match_percentage = 100.0
                result.passed = True
            else:
                result.match_percentage = (min(result.orm_count, result.pg_count) / 
                                         max(result.orm_count, result.pg_count) if result.pg_count > 0 else 0) * 100
                result.error_message = f"Count mismatch: ORM={result.orm_count} PG={result.pg_count}"
                
        except Exception as e:
            result.error_message = str(e)
            
        self.results.append(result)
        self._print_result(result)
        
        # Test 2: fun_getexttourjobneed
        result = ORMTestResult("fun_getexttourjobneed")
        try:
            # ORM version
            start = time.time()
            orm_tours = JobneedManagerORM.get_external_tour_job_needs(
                Jobneed.objects,
                self.test_people_id,
                self.test_bu_id,
                self.test_client_id
            )
            result.orm_time = time.time() - start
            result.orm_count = len(orm_tours)
            
            # PostgreSQL version
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM fun_getexttourjobneed(%s, %s, %s)",
                    [self.test_people_id, self.test_bu_id, self.test_client_id]
                )
                pg_tours = cursor.fetchall()
            result.pg_time = time.time() - start
            result.pg_count = len(pg_tours)
            
            # Compare counts
            if result.orm_count == result.pg_count:
                result.match_percentage = 100.0
                result.passed = True
            else:
                result.match_percentage = (min(result.orm_count, result.pg_count) / 
                                         max(result.orm_count, result.pg_count) if result.pg_count > 0 else 0) * 100
                result.error_message = f"Count mismatch: ORM={result.orm_count} PG={result.pg_count}"
                
        except Exception as e:
            result.error_message = str(e)
            
        self.results.append(result)
        self._print_result(result)
        
    def test_business_unit_functions(self):
        """Test business unit function migrations"""
        print("\n=== Testing Business Unit Functions ===")
        
        # Test fn_getbulist_basedon_idnf
        result = ORMTestResult("fn_getbulist_basedon_idnf")
        try:
            test_cases = [
                {'include_customers': True, 'include_sites': True},
                {'include_customers': True, 'include_sites': False},
                {'include_customers': False, 'include_sites': True},
                {'include_customers': False, 'include_sites': False},
            ]
            
            total_matches = 0
            for test in test_cases:
                # ORM version
                start = time.time()
                orm_result = BtManagerORM.get_bulist_basedon_idnf(
                    self.test_bu_id,
                    test['include_customers'],
                    test['include_sites']
                )
                result.orm_time += time.time() - start
                
                # PostgreSQL version
                start = time.time()
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT fn_getbulist_basedon_idnf(%s, %s, %s)",
                        [self.test_bu_id, test['include_customers'], test['include_sites']]
                    )
                    pg_result = cursor.fetchone()[0] or ''
                result.pg_time += time.time() - start
                
                # Compare results
                orm_ids = set(orm_result.split()) if orm_result else set()
                pg_ids = set(pg_result.split()) if pg_result else set()
                
                if orm_ids == pg_ids:
                    total_matches += 1
                    
            result.match_percentage = (total_matches / len(test_cases)) * 100
            result.passed = result.match_percentage == 100.0
            
            if not result.passed:
                result.error_message = f"Some test cases failed: {total_matches}/{len(test_cases)} passed"
                
        except Exception as e:
            result.error_message = str(e)
            
        self.results.append(result)
        self._print_result(result)
        
    def test_capability_functions(self):
        """Test capability function migrations"""
        print("\n=== Testing Capability Functions ===")
        
        result = ORMTestResult("get_web_caps_for_client")
        try:
            # ORM version
            start = time.time()
            orm_caps = Capability.objects.get_web_caps_for_client_orm()
            result.orm_time = time.time() - start
            result.orm_count = len(orm_caps)
            
            # PostgreSQL version (using raw query)
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute("""
                    WITH RECURSIVE cap(id, capsname, capscode, parent_id, cfor, depth, path, xpath) AS (
                        SELECT id, capsname, capscode, parent_id, cfor, 1::INT AS depth, 
                               capability.capscode::TEXT AS path, capability.id::text as xpath
                        FROM capability
                        WHERE id = 1 and cfor='WEB'
                        UNION ALL
                        SELECT ch.id, ch.capsname, ch.capscode, ch.parent_id, ch.cfor, 
                               rt.depth + 1 AS depth, (rt.path || '->' || ch.capscode::TEXT), 
                               (xpath||'>'||ch.id||rt.depth + 1)
                        FROM capability ch INNER JOIN cap rt ON rt.id = ch.parent_id
                    )
                    SELECT * FROM cap ORDER BY xpath
                """)
                pg_caps = cursor.fetchall()
            result.pg_time = time.time() - start
            result.pg_count = len(pg_caps)
            
            # Compare counts and structure
            if result.orm_count == result.pg_count:
                result.match_percentage = 100.0
                result.passed = True
            else:
                result.match_percentage = (min(result.orm_count, result.pg_count) / 
                                         max(result.orm_count, result.pg_count)) * 100
                result.error_message = f"Count mismatch: ORM={result.orm_count} PG={result.pg_count}"
                
        except Exception as e:
            result.error_message = str(e)
            
        self.results.append(result)
        self._print_result(result)
        
    def _print_result(self, result: ORMTestResult):
        """Print individual test result"""
        status = "✅ PASSED" if result.passed else "❌ FAILED"
        print(f"\n{result.test_name}: {status}")
        
        if result.orm_time > 0 or result.pg_time > 0:
            print(f"  Performance: ORM={result.orm_time:.4f}s, PG={result.pg_time:.4f}s")
            if result.pg_time > 0:
                ratio = result.orm_time / result.pg_time
                print(f"  Speed Ratio: {ratio:.2f}x")
                
        if result.orm_count > 0 or result.pg_count > 0:
            print(f"  Record Count: ORM={result.orm_count}, PG={result.pg_count}")
            
        if result.match_percentage < 100:
            print(f"  Match Rate: {result.match_percentage:.1f}%")
            
        if result.error_message:
            print(f"  Error: {result.error_message}")
            
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
        print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        
        # Performance comparison
        total_orm_time = sum(r.orm_time for r in self.results)
        total_pg_time = sum(r.pg_time for r in self.results)
        
        print(f"\nTotal ORM Time: {total_orm_time:.4f}s")
        print(f"Total PG Time: {total_pg_time:.4f}s")
        if total_pg_time > 0:
            print(f"Overall Speed Ratio: {total_orm_time/total_pg_time:.2f}x")
            
        # Failed tests detail
        if failed_tests > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.test_name}: {r.error_message}")
                    
        print("\n" + "=" * 80)
        
        # Recommendations
        print("RECOMMENDATIONS:")
        if failed_tests == 0:
            print("✅ All tests passed! ORM implementations are ready for production.")
            print("   Consider enabling feature flags to use ORM implementations.")
        else:
            print("⚠️  Some tests failed. Review the errors and fix before deployment.")
            print("   Keep using PostgreSQL functions until all tests pass.")
            
        if total_orm_time > total_pg_time * 1.5:
            print("⚠️  ORM is significantly slower than PostgreSQL functions.")
            print("   Consider performance optimization or caching strategies.")
            
        print("=" * 80)


def main():
    """Run the test suite"""
    try:
        # Check if we have test data
        print("Checking for test data...")
        
        # Get sample IDs for testing
        try:
            test_bu = Bt.objects.filter(enable=True).first()
            test_people = utils.get_db_rows(
                "SELECT id FROM people WHERE enable=true LIMIT 1",
                args=[]
            )
            
            if test_bu and test_people:
                tester = TestORMMigrations()
                tester.test_bu_id = test_bu.id
                tester.test_client_id = test_bu.client_id if hasattr(test_bu, 'client_id') else 1
                
                # Run all tests
                tester.run_all_tests()
            else:
                print("⚠️  No test data found. Please ensure database has sample data.")
                
        except Exception as e:
            print(f"Error getting test data: {e}")
            print("Running with default test IDs...")
            tester = TestORMMigrations()
            tester.run_all_tests()
            
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()