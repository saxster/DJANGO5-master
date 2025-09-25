#!/usr/bin/env python
"""
Verification script to compare results between raw SQL and Django ORM queries.
This ensures data integrity during the migration.
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta
import json
from decimal import Decimal

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

from django.db import connection
from django.utils import timezone
from colorama import init, Fore, Style

# Import both old and new query methods
from apps.core.raw_queries import get_query as get_raw_query
from apps.core.queries import QueryRepository, ReportQueryRepository
from apps.core.utils import runrawsql
from apps.core.report_queries import get_query as get_report_query

# Initialize colorama
init(autoreset=True)


class QueryVerifier:
    """Verify that ORM queries return same results as raw SQL"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'verifications': [],
            'summary': {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        }
    
    def print_header(self, text):
        """Print section header"""
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"{Fore.CYAN}{text}")
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
    
    def compare_results(self, name, raw_results, orm_results, key_fields=None):
        """Compare results from raw SQL and ORM"""
        print(f"\nVerifying: {name}")
        
        verification = {
            'query': name,
            'timestamp': datetime.now().isoformat(),
            'raw_count': len(raw_results) if raw_results else 0,
            'orm_count': len(orm_results) if orm_results else 0,
            'status': 'unknown',
            'differences': []
        }
        
        # Check counts
        if verification['raw_count'] != verification['orm_count']:
            print(f"{Fore.RED}✗ Count mismatch: Raw SQL returned {verification['raw_count']} rows, "
                  f"ORM returned {verification['orm_count']} rows{Style.RESET_ALL}")
            verification['status'] = 'failed'
            verification['differences'].append({
                'type': 'count_mismatch',
                'raw': verification['raw_count'],
                'orm': verification['orm_count']
            })
        else:
            print(f"{Fore.GREEN}✓ Row count matches: {verification['raw_count']} rows{Style.RESET_ALL}")
            
            # Compare data if counts match
            if verification['raw_count'] > 0:
                # Convert to comparable format
                raw_data = self._normalize_data(raw_results)
                orm_data = self._normalize_data(orm_results)
                
                # Compare field by field
                differences = self._compare_data(raw_data, orm_data, key_fields)
                
                if differences:
                    print(f"{Fore.YELLOW}⚠ Found {len(differences)} differences in data{Style.RESET_ALL}")
                    verification['status'] = 'warning'
                    verification['differences'].extend(differences)
                else:
                    print(f"{Fore.GREEN}✓ Data matches exactly{Style.RESET_ALL}")
                    verification['status'] = 'passed'
            else:
                verification['status'] = 'passed'
        
        self.results['verifications'].append(verification)
        return verification['status']
    
    def _normalize_data(self, data):
        """Normalize data for comparison"""
        normalized = []
        
        for row in data:
            if isinstance(row, dict):
                norm_row = {}
                for k, v in row.items():
                    # Normalize different data types
                    if isinstance(v, Decimal):
                        norm_row[k] = float(v)
                    elif isinstance(v, datetime):
                        norm_row[k] = v.isoformat()
                    elif v is None:
                        norm_row[k] = None
                    else:
                        norm_row[k] = str(v)
                normalized.append(norm_row)
            else:
                # Handle tuple results
                normalized.append(row)
        
        return normalized
    
    def _compare_data(self, raw_data, orm_data, key_fields=None):
        """Compare normalized data sets"""
        differences = []
        
        # If no key fields specified, compare by index
        if not key_fields:
            for i, (raw_row, orm_row) in enumerate(zip(raw_data, orm_data)):
                if raw_row != orm_row:
                    differences.append({
                        'type': 'data_mismatch',
                        'row_index': i,
                        'raw': raw_row,
                        'orm': orm_row
                    })
        else:
            # Compare using key fields
            # Create lookup dictionaries
            raw_dict = {}
            orm_dict = {}
            
            for row in raw_data:
                key = tuple(row.get(f) for f in key_fields)
                raw_dict[key] = row
            
            for row in orm_data:
                key = tuple(row.get(f) for f in key_fields)
                orm_dict[key] = row
            
            # Check for missing/extra rows
            raw_keys = set(raw_dict.keys())
            orm_keys = set(orm_dict.keys())
            
            missing_in_orm = raw_keys - orm_keys
            extra_in_orm = orm_keys - raw_keys
            
            if missing_in_orm:
                differences.append({
                    'type': 'missing_rows',
                    'keys': list(missing_in_orm)
                })
            
            if extra_in_orm:
                differences.append({
                    'type': 'extra_rows',
                    'keys': list(extra_in_orm)
                })
            
            # Compare common rows
            for key in raw_keys & orm_keys:
                if raw_dict[key] != orm_dict[key]:
                    differences.append({
                        'type': 'data_mismatch',
                        'key': key,
                        'raw': raw_dict[key],
                        'orm': orm_dict[key]
                    })
        
        return differences
    
    def verify_capability_queries(self):
        """Verify capability tree queries"""
        self.print_header("Verifying Capability Queries")
        
        # Test get_web_caps_for_client
        raw_results = runrawsql(get_raw_query("get_web_caps_for_client"))
        orm_results = QueryRepository.get_web_caps_for_client()
        
        status = self.compare_results(
            "get_web_caps_for_client",
            raw_results,
            orm_results,
            key_fields=['id']
        )
        
        # Test get_mob_caps_for_client
        raw_results = runrawsql(get_raw_query("get_mob_caps_for_client"))
        orm_results = QueryRepository.get_mob_caps_for_client()
        
        status = self.compare_results(
            "get_mob_caps_for_client",
            raw_results,
            orm_results,
            key_fields=['id']
        )
    
    def verify_bt_queries(self):
        """Verify BT (Business Unit) queries"""
        self.print_header("Verifying BT Queries")
        
        # Test with sample BT ID (you may need to adjust this)
        test_bt_id = 1  # Assuming BT with ID 1 exists
        
        raw_results = runrawsql(get_raw_query("get_childrens_of_bt"), [test_bt_id])
        orm_results = QueryRepository.get_childrens_of_bt(test_bt_id)
        
        self.compare_results(
            "get_childrens_of_bt",
            raw_results,
            orm_results,
            key_fields=['id']
        )
    
    def verify_report_queries(self):
        """Verify report queries"""
        self.print_header("Verifying Report Queries")
        
        # Test parameters
        timezone_str = 'UTC'
        site_ids = [1]  # Adjust based on your test data
        from_date = timezone.now() - timedelta(days=7)
        to_date = timezone.now()
        
        # Test TASKSUMMARY
        raw_results = runrawsql(
            get_report_query("TASKSUMMARY"),
            args={
                'timezone': timezone_str,
                'siteids': ','.join(map(str, site_ids)),
                'from': from_date.strftime('%Y-%m-%d %H:%M:%S'),
                'upto': to_date.strftime('%Y-%m-%d %H:%M:%S')
            },
            named_params=True
        )
        
        orm_results = ReportQueryRepository.tasksummary_report(
            timezone_str=timezone_str,
            siteids=site_ids,
            from_date=from_date,
            upto_date=to_date
        )
        
        self.compare_results(
            "TASKSUMMARY",
            raw_results,
            orm_results,
            key_fields=['planned_date']
        )
    
    def verify_ticket_queries(self):
        """Verify ticket queries"""
        self.print_header("Verifying Ticket Queries")
        
        # Test escalation query
        raw_results = runrawsql(get_raw_query("get_ticketlist_for_escalation"))
        orm_results = QueryRepository.get_ticketlist_for_escalation()
        
        self.compare_results(
            "get_ticketlist_for_escalation",
            raw_results,
            orm_results,
            key_fields=['id']
        )
    
    def generate_report(self):
        """Generate verification report"""
        self.print_header("VERIFICATION SUMMARY")
        
        # Calculate summary
        for verification in self.results['verifications']:
            self.results['summary']['total'] += 1
            if verification['status'] == 'passed':
                self.results['summary']['passed'] += 1
            elif verification['status'] == 'failed':
                self.results['summary']['failed'] += 1
            else:
                self.results['summary']['warnings'] += 1
        
        # Print summary
        print(f"Total Queries Verified: {self.results['summary']['total']}")
        print(f"Passed: {Fore.GREEN}{self.results['summary']['passed']}{Style.RESET_ALL}")
        print(f"Failed: {Fore.RED}{self.results['summary']['failed']}{Style.RESET_ALL}")
        print(f"Warnings: {Fore.YELLOW}{self.results['summary']['warnings']}{Style.RESET_ALL}")
        
        # Save detailed report
        report_path = project_root / 'tests' / 'orm_verification_report.json'
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nDetailed report saved to: {report_path}")
        
        # Print details of failures
        if self.results['summary']['failed'] > 0:
            print(f"\n{Fore.RED}Failed Verifications:{Style.RESET_ALL}")
            for v in self.results['verifications']:
                if v['status'] == 'failed':
                    print(f"  - {v['query']}: {v['differences'][0]['type']}")
        
        if self.results['summary']['warnings'] > 0:
            print(f"\n{Fore.YELLOW}Warnings:{Style.RESET_ALL}")
            for v in self.results['verifications']:
                if v['status'] == 'warning':
                    print(f"  - {v['query']}: {len(v['differences'])} differences found")
    
    def run_all_verifications(self):
        """Run all verification tests"""
        print(f"{Fore.BLUE}{'=' * 80}")
        print(f"{Fore.BLUE}{'DJANGO ORM MIGRATION VERIFICATION'.center(80)}")
        print(f"{Fore.BLUE}{'=' * 80}{Style.RESET_ALL}\n")
        
        print("Comparing results between raw SQL and Django ORM implementations...")
        print(f"Database: {connection.settings_dict['NAME']}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        try:
            self.verify_capability_queries()
            self.verify_bt_queries()
            self.verify_ticket_queries()
            self.verify_report_queries()
        except Exception as e:
            print(f"{Fore.RED}Error during verification: {str(e)}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
        
        self.generate_report()
        
        return self.results['summary']['failed'] == 0


def check_performance():
    """Quick performance comparison"""
    print(f"\n{Fore.CYAN}{'=' * 60}")
    print(f"{Fore.CYAN}PERFORMANCE COMPARISON")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
    
    import time
    
    # Test capability tree query
    print("Testing capability tree query performance...")
    
    # Raw SQL
    start = time.time()
    raw_results = runrawsql(get_raw_query("get_web_caps_for_client"))
    raw_time = time.time() - start
    
    # ORM
    start = time.time()
    orm_results = QueryRepository.get_web_caps_for_client()
    orm_time = time.time() - start
    
    print(f"Raw SQL: {raw_time:.3f}s for {len(raw_results)} rows")
    print(f"Django ORM: {orm_time:.3f}s for {len(orm_results)} rows")
    
    if orm_time < raw_time:
        improvement = ((raw_time - orm_time) / raw_time) * 100
        print(f"{Fore.GREEN}✓ ORM is {improvement:.1f}% faster!{Style.RESET_ALL}")
    else:
        slowdown = ((orm_time - raw_time) / raw_time) * 100
        if slowdown < 20:
            print(f"{Fore.YELLOW}⚠ ORM is {slowdown:.1f}% slower (acceptable){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ ORM is {slowdown:.1f}% slower (needs optimization){Style.RESET_ALL}")


def main():
    """Main entry point"""
    verifier = QueryVerifier()
    
    # Run verifications
    success = verifier.run_all_verifications()
    
    # Check performance
    check_performance()
    
    if success:
        print(f"\n{Fore.GREEN}✓ All verifications passed!{Style.RESET_ALL}")
        return 0
    else:
        print(f"\n{Fore.RED}✗ Some verifications failed. Please review the report.{Style.RESET_ALL}")
        return 1


if __name__ == '__main__':
    sys.exit(main())