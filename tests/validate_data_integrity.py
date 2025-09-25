#!/usr/bin/env python
"""
Data integrity validation for Django ORM migration.
Compares results between raw SQL and Django ORM queries to ensure accuracy.
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta
import json
import hashlib
from typing import Dict, List, Any, Tuple
from decimal import Decimal
import time

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
from apps.core.report_queries import get_query as get_report_query
from apps.core.queries import QueryRepository, ReportQueryRepository
from apps.core.utils import runrawsql

# Initialize colorama
init(autoreset=True)


class DataIntegrityValidator:
    """Validate data integrity between raw SQL and ORM queries"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'validations': [],
            'performance_comparisons': [],
            'summary': {
                'total_queries': 0,
                'exact_matches': 0,
                'data_mismatches': 0,
                'performance_improvements': 0,
                'performance_regressions': 0
            }
        }
        
        # Test parameters
        self.test_params = {
            'timezone': 'UTC',
            'test_site_ids': [1, 2, 3],
            'test_people_id': 1,
            'test_client_id': 1,
            'test_bt_id': 1,
            'test_ticket_id': 1,
            'test_asset_id': 1,
            'date_from': timezone.now() - timedelta(days=30),
            'date_to': timezone.now()
        }
    
    def print_header(self, text, level=1):
        """Print formatted header"""
        if level == 1:
            print(f"\n{Fore.BLUE}{'=' * 80}")
            print(f"{Fore.BLUE}{text.center(80)}")
            print(f"{Fore.BLUE}{'=' * 80}{Style.RESET_ALL}\n")
        else:
            print(f"\n{Fore.CYAN}{text}")
            print(f"{Fore.CYAN}{'-' * len(text)}{Style.RESET_ALL}")
    
    def normalize_data(self, data: Any) -> Any:
        """Normalize data for comparison"""
        if data is None:
            return None
        elif isinstance(data, (list, tuple)):
            return [self.normalize_data(item) for item in data]
        elif isinstance(data, dict):
            return {k: self.normalize_data(v) for k, v in sorted(data.items())}
        elif isinstance(data, Decimal):
            return float(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        elif hasattr(data, '__dict__'):
            # Handle model instances
            return self.normalize_data(data.__dict__)
        else:
            return str(data)
    
    def compute_data_hash(self, data: Any) -> str:
        """Compute hash of normalized data for comparison"""
        normalized = self.normalize_data(data)
        data_str = json.dumps(normalized, sort_keys=True, default=str)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def compare_query_results(self, query_name: str, raw_results: Any, orm_results: Any) -> Dict:
        """Compare results from raw SQL and ORM"""
        validation = {
            'query': query_name,
            'timestamp': datetime.now().isoformat(),
            'raw_count': len(raw_results) if raw_results else 0,
            'orm_count': len(orm_results) if orm_results else 0,
            'status': 'unknown',
            'details': {}
        }
        
        # Compare counts
        if validation['raw_count'] != validation['orm_count']:
            validation['status'] = 'count_mismatch'
            validation['details']['difference'] = abs(validation['raw_count'] - validation['orm_count'])
        else:
            # Compare data content
            raw_hash = self.compute_data_hash(raw_results)
            orm_hash = self.compute_data_hash(orm_results)
            
            if raw_hash == orm_hash:
                validation['status'] = 'exact_match'
            else:
                validation['status'] = 'data_mismatch'
                validation['details']['raw_hash'] = raw_hash
                validation['details']['orm_hash'] = orm_hash
                
                # Find specific differences
                if validation['raw_count'] > 0:
                    validation['details']['sample_differences'] = self.find_differences(
                        raw_results[:5], orm_results[:5]
                    )
        
        return validation
    
    def find_differences(self, raw_data: List, orm_data: List) -> List[Dict]:
        """Find specific differences between datasets"""
        differences = []
        
        for i, (raw_item, orm_item) in enumerate(zip(raw_data, orm_data)):
            raw_norm = self.normalize_data(raw_item)
            orm_norm = self.normalize_data(orm_item)
            
            if raw_norm != orm_norm:
                diff = {
                    'index': i,
                    'fields': []
                }
                
                # Compare field by field if both are dicts
                if isinstance(raw_norm, dict) and isinstance(orm_norm, dict):
                    all_keys = set(raw_norm.keys()) | set(orm_norm.keys())
                    for key in all_keys:
                        raw_val = raw_norm.get(key)
                        orm_val = orm_norm.get(key)
                        if raw_val != orm_val:
                            diff['fields'].append({
                                'field': key,
                                'raw': raw_val,
                                'orm': orm_val
                            })
                else:
                    diff['raw'] = raw_norm
                    diff['orm'] = orm_norm
                
                differences.append(diff)
        
        return differences
    
    def measure_performance(self, query_func, *args, **kwargs) -> Tuple[Any, float]:
        """Measure query execution time"""
        start_time = time.time()
        result = query_func(*args, **kwargs)
        execution_time = time.time() - start_time
        return result, execution_time
    
    def validate_capability_queries(self):
        """Validate capability tree queries"""
        self.print_header("Validating Capability Queries", 2)
        
        # Test get_web_caps_for_client
        print("Testing get_web_caps_for_client...")
        
        raw_results, raw_time = self.measure_performance(
            runrawsql, get_raw_query("get_web_caps_for_client")
        )
        orm_results, orm_time = self.measure_performance(
            QueryRepository.get_web_caps_for_client
        )
        
        validation = self.compare_query_results("get_web_caps_for_client", raw_results, orm_results)
        self.results['validations'].append(validation)
        
        # Performance comparison
        perf_comparison = {
            'query': 'get_web_caps_for_client',
            'raw_time': raw_time,
            'orm_time': orm_time,
            'improvement': ((raw_time - orm_time) / raw_time) * 100 if raw_time > 0 else 0
        }
        self.results['performance_comparisons'].append(perf_comparison)
        
        # Print results
        if validation['status'] == 'exact_match':
            print(f"{Fore.GREEN}✓ Data matches exactly ({validation['raw_count']} records){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Data mismatch: {validation['status']}{Style.RESET_ALL}")
        
        print(f"  Raw SQL: {raw_time:.3f}s, ORM: {orm_time:.3f}s ({perf_comparison['improvement']:.1f}% improvement)")
        
        # Test get_mob_caps_for_client
        print("\nTesting get_mob_caps_for_client...")
        
        raw_results, raw_time = self.measure_performance(
            runrawsql, get_raw_query("get_mob_caps_for_client")
        )
        orm_results, orm_time = self.measure_performance(
            QueryRepository.get_mob_caps_for_client
        )
        
        validation = self.compare_query_results("get_mob_caps_for_client", raw_results, orm_results)
        self.results['validations'].append(validation)
        
        if validation['status'] == 'exact_match':
            print(f"{Fore.GREEN}✓ Data matches exactly ({validation['raw_count']} records){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Data mismatch: {validation['status']}{Style.RESET_ALL}")
    
    def validate_bt_queries(self):
        """Validate BT (Business Unit) queries"""
        self.print_header("Validating BT Queries", 2)
        
        # Test get_childrens_of_bt
        print(f"Testing get_childrens_of_bt (bt_id={self.test_params['test_bt_id']})...")
        
        raw_results, raw_time = self.measure_performance(
            runrawsql, get_raw_query("get_childrens_of_bt"), [self.test_params['test_bt_id']]
        )
        orm_results, orm_time = self.measure_performance(
            QueryRepository.get_childrens_of_bt, self.test_params['test_bt_id']
        )
        
        validation = self.compare_query_results("get_childrens_of_bt", raw_results, orm_results)
        self.results['validations'].append(validation)
        
        if validation['status'] == 'exact_match':
            print(f"{Fore.GREEN}✓ Data matches exactly ({validation['raw_count']} records){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Data mismatch: {validation['status']}{Style.RESET_ALL}")
            if 'sample_differences' in validation['details']:
                print("  Sample differences:")
                for diff in validation['details']['sample_differences'][:2]:
                    print(f"    {diff}")
    
    def validate_ticket_queries(self):
        """Validate ticket queries"""
        self.print_header("Validating Ticket Queries", 2)
        
        # Test get_ticketlist_for_escalation
        print("Testing get_ticketlist_for_escalation...")
        
        raw_results, raw_time = self.measure_performance(
            runrawsql, get_raw_query("get_ticketlist_for_escalation")
        )
        orm_results, orm_time = self.measure_performance(
            QueryRepository.get_ticketlist_for_escalation
        )
        
        validation = self.compare_query_results("get_ticketlist_for_escalation", raw_results, orm_results)
        self.results['validations'].append(validation)
        
        if validation['status'] == 'exact_match':
            print(f"{Fore.GREEN}✓ Data matches exactly ({validation['raw_count']} records){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Data mismatch: {validation['status']}{Style.RESET_ALL}")
        
        # Test ticketmail
        if self.test_params['test_ticket_id']:
            print(f"\nTesting ticketmail (ticket_id={self.test_params['test_ticket_id']})...")
            
            raw_results, raw_time = self.measure_performance(
                runrawsql, get_raw_query("ticketmail"), [self.test_params['test_ticket_id']]
            )
            orm_results, orm_time = self.measure_performance(
                QueryRepository.ticketmail, self.test_params['test_ticket_id']
            )
            
            validation = self.compare_query_results("ticketmail", raw_results, orm_results)
            self.results['validations'].append(validation)
            
            if validation['status'] == 'exact_match':
                print(f"{Fore.GREEN}✓ Data matches exactly{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ Data mismatch: {validation['status']}{Style.RESET_ALL}")
    
    def validate_report_queries(self):
        """Validate report queries"""
        self.print_header("Validating Report Queries", 2)
        
        # Prepare test parameters
        report_params = {
            'timezone': self.test_params['timezone'],
            'siteids': ','.join(map(str, self.test_params['test_site_ids'])),
            'from': self.test_params['date_from'].strftime('%Y-%m-%d %H:%M:%S'),
            'upto': self.test_params['date_to'].strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Test TASKSUMMARY
        print("Testing TASKSUMMARY report...")
        
        raw_results, raw_time = self.measure_performance(
            runrawsql, get_report_query("TASKSUMMARY"), args=report_params, named_params=True
        )
        orm_results, orm_time = self.measure_performance(
            ReportQueryRepository.tasksummary_report,
            timezone_str=self.test_params['timezone'],
            siteids=self.test_params['test_site_ids'],
            from_date=self.test_params['date_from'],
            upto_date=self.test_params['date_to']
        )
        
        validation = self.compare_query_results("TASKSUMMARY", raw_results, orm_results)
        self.results['validations'].append(validation)
        
        if validation['status'] == 'exact_match':
            print(f"{Fore.GREEN}✓ Data matches exactly ({validation['raw_count']} records){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Data mismatch: {validation['status']}{Style.RESET_ALL}")
        
        print(f"  Performance: Raw SQL {raw_time:.3f}s vs ORM {orm_time:.3f}s")
        
        # Test TOURSUMMARY
        print("\nTesting TOURSUMMARY report...")
        
        raw_results, raw_time = self.measure_performance(
            runrawsql, get_report_query("TOURSUMMARY"), args=report_params, named_params=True
        )
        orm_results, orm_time = self.measure_performance(
            ReportQueryRepository.toursummary_report,
            timezone_str=self.test_params['timezone'],
            siteids=self.test_params['test_site_ids'],
            from_date=self.test_params['date_from'],
            upto_date=self.test_params['date_to']
        )
        
        validation = self.compare_query_results("TOURSUMMARY", raw_results, orm_results)
        self.results['validations'].append(validation)
        
        if validation['status'] == 'exact_match':
            print(f"{Fore.GREEN}✓ Data matches exactly ({validation['raw_count']} records){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Data mismatch: {validation['status']}{Style.RESET_ALL}")
    
    def validate_asset_queries(self):
        """Validate asset queries"""
        self.print_header("Validating Asset Queries", 2)
        
        # Test asset_status_period
        print(f"Testing asset_status_period (asset_id={self.test_params['test_asset_id']})...")
        
        try:
            raw_results, raw_time = self.measure_performance(
                runrawsql, get_raw_query("asset_status_period"), 
                ['ACTIVE', 'ACTIVE', self.test_params['test_asset_id']]
            )
            orm_results, orm_time = self.measure_performance(
                QueryRepository.asset_status_period,
                old_status='ACTIVE',
                new_status='ACTIVE',
                asset_id=self.test_params['test_asset_id']
            )
            
            validation = self.compare_query_results("asset_status_period", raw_results, orm_results)
            self.results['validations'].append(validation)
            
            if validation['status'] == 'exact_match':
                print(f"{Fore.GREEN}✓ Data matches exactly{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ Data mismatch: {validation['status']}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Error testing asset_status_period: {str(e)}{Style.RESET_ALL}")
    
    def validate_critical_queries(self):
        """Validate the most critical queries used throughout the system"""
        self.print_header("Validating Critical System Queries", 2)
        
        critical_queries = [
            {
                'name': 'sitereportlist',
                'raw_func': lambda: runrawsql(
                    get_raw_query("sitereportlist"), 
                    [self.test_params['test_site_ids'], self.test_params['test_people_id']]
                ),
                'orm_func': lambda: QueryRepository.sitereportlist(
                    sitegroupids=self.test_params['test_site_ids'],
                    peopleid=self.test_params['test_people_id']
                )
            }
        ]
        
        for query_def in critical_queries:
            print(f"\nTesting {query_def['name']}...")
            
            try:
                raw_results, raw_time = self.measure_performance(query_def['raw_func'])
                orm_results, orm_time = self.measure_performance(query_def['orm_func'])
                
                validation = self.compare_query_results(query_def['name'], raw_results, orm_results)
                self.results['validations'].append(validation)
                
                if validation['status'] == 'exact_match':
                    print(f"{Fore.GREEN}✓ Data matches exactly ({validation['raw_count']} records){Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}✗ Data mismatch: {validation['status']}{Style.RESET_ALL}")
                
            except Exception as e:
                print(f"{Fore.YELLOW}⚠ Error: {str(e)}{Style.RESET_ALL}")
    
    def generate_detailed_report(self):
        """Generate detailed validation report"""
        report_path = project_root / 'tests' / 'data_integrity_report.md'
        
        with open(report_path, 'w') as f:
            f.write("# Data Integrity Validation Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary
            f.write("## Summary\n\n")
            f.write(f"- Total Queries Validated: {self.results['summary']['total_queries']}\n")
            f.write(f"- Exact Matches: {self.results['summary']['exact_matches']}\n")
            f.write(f"- Data Mismatches: {self.results['summary']['data_mismatches']}\n")
            f.write(f"- Performance Improvements: {self.results['summary']['performance_improvements']}\n")
            f.write(f"- Performance Regressions: {self.results['summary']['performance_regressions']}\n\n")
            
            # Validation Details
            f.write("## Validation Details\n\n")
            
            for validation in self.results['validations']:
                f.write(f"### {validation['query']}\n\n")
                f.write(f"- Status: **{validation['status']}**\n")
                f.write(f"- Raw SQL Records: {validation['raw_count']}\n")
                f.write(f"- ORM Records: {validation['orm_count']}\n")
                
                if validation['status'] != 'exact_match' and validation['details']:
                    f.write("\n**Details:**\n")
                    if 'sample_differences' in validation['details']:
                        f.write("```json\n")
                        f.write(json.dumps(validation['details']['sample_differences'], indent=2))
                        f.write("\n```\n")
                
                f.write("\n---\n\n")
            
            # Performance Analysis
            f.write("## Performance Analysis\n\n")
            f.write("| Query | Raw SQL (s) | ORM (s) | Improvement |\n")
            f.write("|-------|-------------|---------|-------------|\n")
            
            for perf in self.results['performance_comparisons']:
                improvement = f"{perf['improvement']:.1f}%" if perf['improvement'] > 0 else f"({abs(perf['improvement']):.1f}%)"
                f.write(f"| {perf['query']} | {perf['raw_time']:.3f} | {perf['orm_time']:.3f} | {improvement} |\n")
        
        print(f"\nDetailed report saved to: {report_path}")
    
    def run_validation(self):
        """Run complete data integrity validation"""
        self.print_header("DATA INTEGRITY VALIDATION", 1)
        
        print(f"Database: {connection.settings_dict['NAME']}")
        print(f"Test Period: {self.test_params['date_from'].date()} to {self.test_params['date_to'].date()}")
        print(f"Test Sites: {self.test_params['test_site_ids']}\n")
        
        # Run validations
        self.validate_capability_queries()
        self.validate_bt_queries()
        self.validate_ticket_queries()
        self.validate_report_queries()
        self.validate_asset_queries()
        self.validate_critical_queries()
        
        # Calculate summary
        for validation in self.results['validations']:
            self.results['summary']['total_queries'] += 1
            if validation['status'] == 'exact_match':
                self.results['summary']['exact_matches'] += 1
            else:
                self.results['summary']['data_mismatches'] += 1
        
        for perf in self.results['performance_comparisons']:
            if perf['improvement'] > 0:
                self.results['summary']['performance_improvements'] += 1
            else:
                self.results['summary']['performance_regressions'] += 1
        
        # Generate reports
        self.print_header("VALIDATION SUMMARY", 1)
        
        print(f"Total Queries Validated: {self.results['summary']['total_queries']}")
        print(f"Exact Matches: {Fore.GREEN}{self.results['summary']['exact_matches']}{Style.RESET_ALL}")
        print(f"Data Mismatches: {Fore.RED}{self.results['summary']['data_mismatches']}{Style.RESET_ALL}")
        
        # Performance summary
        avg_improvement = sum(p['improvement'] for p in self.results['performance_comparisons']) / len(self.results['performance_comparisons']) if self.results['performance_comparisons'] else 0
        
        print(f"\nPerformance Summary:")
        print(f"Average Improvement: {Fore.GREEN if avg_improvement > 0 else Fore.RED}{avg_improvement:.1f}%{Style.RESET_ALL}")
        print(f"Queries Faster: {self.results['summary']['performance_improvements']}")
        print(f"Queries Slower: {self.results['summary']['performance_regressions']}")
        
        # Save JSON report
        json_report_path = project_root / 'tests' / 'data_integrity_validation.json'
        with open(json_report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Generate detailed report
        self.generate_detailed_report()
        
        if self.results['summary']['data_mismatches'] == 0:
            print(f"\n{Fore.GREEN}✓ All queries return identical data!{Style.RESET_ALL}")
            return True
        else:
            print(f"\n{Fore.RED}✗ Found {self.results['summary']['data_mismatches']} data mismatches{Style.RESET_ALL}")
            return False


def check_sample_data():
    """Quick check with sample data"""
    print(f"\n{Fore.CYAN}Sample Data Check:{Style.RESET_ALL}\n")
    
    # Check a simple query
    try:
        from apps.core.models import Capability
        
        # Count capabilities
        cap_count = Capability.objects.filter(cfor='WEB').count()
        print(f"Web Capabilities: {cap_count}")
        
        # Test tree traversal
        caps = QueryRepository.get_web_caps_for_client()
        print(f"Tree Traversal Result: {len(caps)} nodes")
        
        if caps:
            # Show sample
            print("\nSample capability:")
            sample = caps[0]
            for key, value in list(sample.items())[:5]:
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"{Fore.RED}Error in sample check: {str(e)}{Style.RESET_ALL}")


def main():
    """Main entry point"""
    validator = DataIntegrityValidator()
    
    # Quick sample check
    check_sample_data()
    
    # Run full validation
    success = validator.run_validation()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())