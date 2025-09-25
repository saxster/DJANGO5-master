#!/usr/bin/env python
"""
Data validation script for Django ORM migrations.
Ensures data integrity and consistency between PostgreSQL and Django ORM implementations.
"""

import os
import sys
import django
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Tuple

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.db import connection
from django.core.serializers.json import DjangoJSONEncoder

# Import implementations
from apps.activity.managers.asset_manager_orm import AssetManagerORM
from apps.activity.managers.job_manager_orm import JobneedManagerORM
from apps.onboarding.bt_manager_orm import BtManagerORM
from apps.peoples.models import Capability
from apps.activity.models.job_model import Jobneed
from apps.onboarding.models import Bt


class DataValidator:
    """Validates data consistency between implementations"""
    
    def __init__(self):
        self.validation_results = []
        self.detailed_diffs = []
        
    def validate_all(self):
        """Run all validation tests"""
        print("=" * 80)
        print("DATA VALIDATION FOR ORM MIGRATIONS")
        print("=" * 80)
        print(f"Started at: {datetime.now()}")
        print("=" * 80)
        
        # Run validations
        self.validate_asset_functions()
        self.validate_job_functions()
        self.validate_business_unit_functions()
        self.validate_capability_functions()
        
        # Print results
        self.print_validation_report()
        
    def validate_asset_functions(self):
        """Validate asset function data integrity"""
        print("\n=== Validating Asset Functions ===")
        
        # Test multiple scenarios
        test_scenarios = [
            {'days_ago': 7, 'bu_id': 1},
            {'days_ago': 30, 'bu_id': 1},
            {'days_ago': 90, 'bu_id': 1},
        ]
        
        for scenario in test_scenarios:
            test_date = datetime.now() - timedelta(days=scenario['days_ago'])
            
            # Get ORM results
            orm_assets = AssetManagerORM.get_asset_details(test_date, scenario['bu_id'])
            
            # Get PostgreSQL results
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM fn_getassetdetails(%s, %s)",
                    [test_date, scenario['bu_id']]
                )
                columns = [col[0] for col in cursor.description]
                pg_assets = []
                for row in cursor.fetchall():
                    pg_assets.append(dict(zip(columns, row)))
                    
            # Validate
            result = self._validate_result_sets(
                f"fn_getassetdetails (days={scenario['days_ago']})",
                orm_assets,
                pg_assets,
                key_field='id'
            )
            self.validation_results.append(result)
            
        # Validate question set function
        test_cases = [
            {'bu_id': 1, 'asset_id': '1', 'return_type': ''},
            {'bu_id': 1, 'asset_id': '1', 'return_type': 'name'},
        ]
        
        for test in test_cases:
            orm_result = AssetManagerORM.get_asset_vs_questionset(
                test['bu_id'], test['asset_id'], test['return_type']
            )
            
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT fn_getassetvsquestionset(%s, %s, %s)",
                    [test['bu_id'], test['asset_id'], test['return_type']]
                )
                pg_result = cursor.fetchone()[0] or ''
                
            # Compare string results
            result = {
                'function': f"fn_getassetvsquestionset (type={test['return_type']})",
                'passed': orm_result == pg_result,
                'orm_count': len(orm_result.split()),
                'pg_count': len(pg_result.split()),
                'differences': []
            }
            
            if not result['passed']:
                orm_items = set(orm_result.split())
                pg_items = set(pg_result.split())
                result['differences'] = {
                    'missing_in_orm': list(pg_items - orm_items),
                    'extra_in_orm': list(orm_items - pg_items)
                }
                
            self.validation_results.append(result)
            
    def validate_job_functions(self):
        """Validate job function data integrity"""
        print("\n=== Validating Job Functions ===")
        
        # Test different people/bu/client combinations
        test_scenarios = [
            {'people_id': 1, 'bu_id': 1, 'client_id': 1},
        ]
        
        for scenario in test_scenarios:
            # Validate fun_getjobneed
            orm_jobs = JobneedManagerORM.get_job_needs(
                Jobneed.objects,
                scenario['people_id'],
                scenario['bu_id'],
                scenario['client_id']
            )
            
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM fun_getjobneed(%s, %s, %s)",
                    [scenario['people_id'], scenario['bu_id'], scenario['client_id']]
                )
                columns = [col[0] for col in cursor.description]
                pg_jobs = []
                for row in cursor.fetchall():
                    pg_jobs.append(dict(zip(columns, row)))
                    
            result = self._validate_result_sets(
                f"fun_getjobneed (p={scenario['people_id']})",
                orm_jobs,
                pg_jobs,
                key_field='id'
            )
            self.validation_results.append(result)
            
            # Validate fun_getexttourjobneed
            orm_tours = JobneedManagerORM.get_external_tour_job_needs(
                Jobneed.objects,
                scenario['people_id'],
                scenario['bu_id'],
                scenario['client_id']
            )
            
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM fun_getexttourjobneed(%s, %s, %s)",
                    [scenario['people_id'], scenario['bu_id'], scenario['client_id']]
                )
                columns = [col[0] for col in cursor.description]
                pg_tours = []
                for row in cursor.fetchall():
                    pg_tours.append(dict(zip(columns, row)))
                    
            result = self._validate_result_sets(
                f"fun_getexttourjobneed (p={scenario['people_id']})",
                orm_tours,
                pg_tours,
                key_field='id'
            )
            self.validation_results.append(result)
            
    def validate_business_unit_functions(self):
        """Validate business unit function data integrity"""
        print("\n=== Validating Business Unit Functions ===")
        
        test_scenarios = [
            {'bu_id': 1, 'cus': True, 'si': True},
            {'bu_id': 1, 'cus': True, 'si': False},
            {'bu_id': 1, 'cus': False, 'si': True},
            {'bu_id': 1, 'cus': False, 'si': False},
        ]
        
        for scenario in test_scenarios:
            orm_result = BtManagerORM.get_bulist_basedon_idnf(
                scenario['bu_id'],
                scenario['cus'],
                scenario['si']
            )
            
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT fn_getbulist_basedon_idnf(%s, %s, %s)",
                    [scenario['bu_id'], scenario['cus'], scenario['si']]
                )
                pg_result = cursor.fetchone()[0] or ''
                
            # Compare ID sets
            orm_ids = set(orm_result.split()) if orm_result else set()
            pg_ids = set(pg_result.split()) if pg_result else set()
            
            result = {
                'function': f"fn_getbulist_basedon_idnf (cus={scenario['cus']}, si={scenario['si']})",
                'passed': orm_ids == pg_ids,
                'orm_count': len(orm_ids),
                'pg_count': len(pg_ids),
                'differences': []
            }
            
            if not result['passed']:
                result['differences'] = {
                    'missing_in_orm': list(pg_ids - orm_ids),
                    'extra_in_orm': list(orm_ids - pg_ids)
                }
                
            self.validation_results.append(result)
            
    def validate_capability_functions(self):
        """Validate capability function data integrity"""
        print("\n=== Validating Capability Functions ===")
        
        # Get ORM results
        orm_caps = Capability.objects.get_web_caps_for_client_orm()
        
        # Get PostgreSQL results
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
            
        # Compare structures
        result = {
            'function': 'get_web_caps_for_client',
            'passed': len(orm_caps) == len(pg_caps),
            'orm_count': len(orm_caps),
            'pg_count': len(pg_caps),
            'differences': []
        }
        
        if len(orm_caps) == len(pg_caps):
            # Deep comparison
            for i, (orm_cap, pg_row) in enumerate(zip(orm_caps, pg_caps)):
                if (orm_cap.id != pg_row[0] or 
                    orm_cap.capscode != pg_row[2] or
                    orm_cap.depth != pg_row[5]):
                    result['passed'] = False
                    result['differences'].append({
                        'index': i,
                        'orm': {'id': orm_cap.id, 'code': orm_cap.capscode, 'depth': orm_cap.depth},
                        'pg': {'id': pg_row[0], 'code': pg_row[2], 'depth': pg_row[5]}
                    })
                    
        self.validation_results.append(result)
        
    def _validate_result_sets(
        self, 
        function_name: str,
        orm_results: List[Dict],
        pg_results: List[Dict],
        key_field: str = 'id'
    ) -> Dict:
        """Validate two result sets for consistency"""
        
        result = {
            'function': function_name,
            'passed': True,
            'orm_count': len(orm_results),
            'pg_count': len(pg_results),
            'differences': []
        }
        
        # Quick count check
        if len(orm_results) != len(pg_results):
            result['passed'] = False
            
        # Convert to dictionaries keyed by ID
        orm_dict = {r[key_field]: r for r in orm_results if key_field in r}
        pg_dict = {r[key_field]: r for r in pg_results if key_field in r}
        
        # Check for missing/extra records
        orm_ids = set(orm_dict.keys())
        pg_ids = set(pg_dict.keys())
        
        missing_in_orm = pg_ids - orm_ids
        extra_in_orm = orm_ids - pg_ids
        
        if missing_in_orm or extra_in_orm:
            result['passed'] = False
            result['differences'].append({
                'type': 'id_mismatch',
                'missing_in_orm': list(missing_in_orm),
                'extra_in_orm': list(extra_in_orm)
            })
            
        # Deep field comparison for matching records
        common_ids = orm_ids & pg_ids
        field_mismatches = []
        
        for record_id in common_ids:
            orm_rec = orm_dict[record_id]
            pg_rec = pg_dict[record_id]
            
            # Compare all fields
            for field in pg_rec.keys():
                if field in orm_rec:
                    orm_val = orm_rec[field]
                    pg_val = pg_rec[field]
                    
                    # Normalize for comparison
                    if isinstance(pg_val, datetime) and isinstance(orm_val, datetime):
                        # Compare timestamps with tolerance
                        if abs((pg_val - orm_val).total_seconds()) > 1:
                            field_mismatches.append({
                                'id': record_id,
                                'field': field,
                                'orm': str(orm_val),
                                'pg': str(pg_val)
                            })
                    elif str(orm_val) != str(pg_val):
                        # Handle None/null differences
                        if not (orm_val is None and pg_val is None):
                            field_mismatches.append({
                                'id': record_id,
                                'field': field,
                                'orm': str(orm_val),
                                'pg': str(pg_val)
                            })
                            
        if field_mismatches:
            result['passed'] = False
            result['differences'].append({
                'type': 'field_mismatch',
                'mismatches': field_mismatches[:10]  # Limit to first 10
            })
            
        return result
        
    def print_validation_report(self):
        """Print comprehensive validation report"""
        print("\n" + "=" * 80)
        print("VALIDATION REPORT")
        print("=" * 80)
        
        total_tests = len(self.validation_results)
        passed_tests = sum(1 for r in self.validation_results if r['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Validations: {total_tests}")
        print(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
        print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        
        # Detailed results
        print("\nDetailed Results:")
        print("-" * 80)
        
        for result in self.validation_results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"\n{result['function']}: {status}")
            print(f"  Records: ORM={result['orm_count']}, PG={result['pg_count']}")
            
            if not result['passed'] and result['differences']:
                print("  Issues:")
                for diff in result['differences']:
                    if isinstance(diff, dict):
                        if 'missing_in_orm' in diff:
                            if diff['missing_in_orm']:
                                print(f"    - Missing in ORM: {diff['missing_in_orm'][:5]}...")
                            if diff['extra_in_orm']:
                                print(f"    - Extra in ORM: {diff['extra_in_orm'][:5]}...")
                        elif diff.get('type') == 'field_mismatch':
                            print(f"    - Field mismatches: {len(diff['mismatches'])} fields")
                            for m in diff['mismatches'][:3]:
                                print(f"      ID {m['id']}, {m['field']}: ORM={m['orm']}, PG={m['pg']}")
                                
        # Summary recommendations
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS:")
        
        if failed_tests == 0:
            print("✅ All validations passed! Data integrity confirmed.")
            print("   Safe to proceed with ORM implementation rollout.")
        else:
            print("⚠️  Data inconsistencies detected!")
            print("   Review failed validations before enabling ORM implementations.")
            print("\n   Common issues to check:")
            print("   - Timezone handling differences")
            print("   - Null/None value handling")
            print("   - Array field serialization")
            print("   - JSON field extraction")
            
        # Save detailed report
        self._save_detailed_report()
        
    def _save_detailed_report(self):
        """Save detailed validation report"""
        filename = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': len(self.validation_results),
                'passed': sum(1 for r in self.validation_results if r['passed']),
                'failed': sum(1 for r in self.validation_results if not r['passed'])
            },
            'results': self.validation_results
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, cls=DjangoJSONEncoder)
            
        print(f"\n📁 Detailed report saved to: {filename}")


def main():
    """Run data validation"""
    try:
        print("Starting data validation...")
        validator = DataValidator()
        validator.validate_all()
        
    except Exception as e:
        print(f"Error during validation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()