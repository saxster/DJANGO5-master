#!/usr/bin/env python
"""
Detailed query result comparison tool for Django ORM migration.
Provides side-by-side comparison and detailed analysis of differences.
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta
import json
import difflib
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
from tabulate import tabulate

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

from django.db import connection
from django.utils import timezone
from colorama import init, Fore, Style

# Import query methods
from apps.core.raw_queries import get_query as get_raw_query
from apps.core.report_queries import get_query as get_report_query
from apps.core.queries import QueryRepository, ReportQueryRepository
from apps.core.utils import runrawsql

# Initialize colorama
init(autoreset=True)


class QueryResultComparator:
    """Compare query results in detail"""
    
    def __init__(self):
        self.comparison_results = []
        self.output_dir = project_root / 'tests' / 'query_comparisons'
        self.output_dir.mkdir(exist_ok=True)
    
    def print_header(self, text, level=1):
        """Print formatted header"""
        if level == 1:
            print(f"\n{Fore.BLUE}{'=' * 80}")
            print(f"{Fore.BLUE}{text.center(80)}")
            print(f"{Fore.BLUE}{'=' * 80}{Style.RESET_ALL}\n")
        else:
            print(f"\n{Fore.CYAN}{text}")
            print(f"{Fore.CYAN}{'-' * len(text)}{Style.RESET_ALL}")
    
    def dict_to_dataframe(self, data: List[Dict]) -> pd.DataFrame:
        """Convert list of dicts to DataFrame for easier comparison"""
        if not data:
            return pd.DataFrame()
        
        # Normalize the data
        normalized = []
        for item in data:
            if isinstance(item, dict):
                normalized.append(item)
            else:
                # Convert objects to dicts
                if hasattr(item, '__dict__'):
                    normalized.append(item.__dict__)
                else:
                    normalized.append({'value': item})
        
        return pd.DataFrame(normalized)
    
    def compare_dataframes(self, df1: pd.DataFrame, df2: pd.DataFrame, key_columns: Optional[List[str]] = None) -> Dict:
        """Compare two dataframes and return differences"""
        comparison = {
            'identical': False,
            'shape_match': df1.shape == df2.shape,
            'df1_shape': df1.shape,
            'df2_shape': df2.shape,
            'column_differences': {},
            'row_differences': {},
            'missing_in_df2': [],
            'extra_in_df2': []
        }
        
        # Check if completely identical
        if df1.shape == df2.shape and len(df1) > 0:
            try:
                if df1.equals(df2):
                    comparison['identical'] = True
                    return comparison
            except:
                pass  # Different types, continue with detailed comparison
        
        # Compare columns
        cols1 = set(df1.columns)
        cols2 = set(df2.columns)
        
        comparison['column_differences'] = {
            'missing_in_df2': list(cols1 - cols2),
            'extra_in_df2': list(cols2 - cols1),
            'common': list(cols1 & cols2)
        }
        
        # If we have key columns, do row-by-row comparison
        if key_columns and all(col in cols1 & cols2 for col in key_columns):
            df1_indexed = df1.set_index(key_columns)
            df2_indexed = df2.set_index(key_columns)
            
            # Find missing/extra rows
            idx1 = set(df1_indexed.index)
            idx2 = set(df2_indexed.index)
            
            comparison['missing_in_df2'] = list(idx1 - idx2)
            comparison['extra_in_df2'] = list(idx2 - idx1)
            
            # Compare common rows
            common_idx = idx1 & idx2
            if common_idx:
                differences = []
                for idx in list(common_idx)[:10]:  # Limit to first 10 differences
                    row1 = df1_indexed.loc[idx]
                    row2 = df2_indexed.loc[idx]
                    
                    row_diff = {}
                    for col in comparison['column_differences']['common']:
                        val1 = row1.get(col) if col in row1 else None
                        val2 = row2.get(col) if col in row2 else None
                        
                        if pd.isna(val1) and pd.isna(val2):
                            continue
                        elif str(val1) != str(val2):
                            row_diff[col] = {'df1': val1, 'df2': val2}
                    
                    if row_diff:
                        differences.append({'key': idx, 'differences': row_diff})
                
                comparison['row_differences'] = differences
        
        return comparison
    
    def visualize_differences(self, query_name: str, raw_data: List, orm_data: List, 
                            key_columns: Optional[List[str]] = None):
        """Create visual representation of differences"""
        print(f"\n{Fore.YELLOW}Detailed Comparison for {query_name}:{Style.RESET_ALL}")
        
        # Convert to DataFrames
        df_raw = self.dict_to_dataframe(raw_data)
        df_orm = self.dict_to_dataframe(orm_data)
        
        # Basic stats
        print(f"\nBasic Statistics:")
        print(f"  Raw SQL: {len(df_raw)} rows, {len(df_raw.columns)} columns")
        print(f"  Django ORM: {len(df_orm)} rows, {len(df_orm.columns)} columns")
        
        if len(df_raw) == 0 and len(df_orm) == 0:
            print(f"{Fore.GREEN}Both queries returned empty results{Style.RESET_ALL}")
            return
        
        # Compare
        comparison = self.compare_dataframes(df_raw, df_orm, key_columns)
        
        if comparison['identical']:
            print(f"{Fore.GREEN}✓ Results are identical!{Style.RESET_ALL}")
            return
        
        # Show differences
        print(f"\n{Fore.RED}Differences found:{Style.RESET_ALL}")
        
        # Column differences
        if comparison['column_differences']['missing_in_df2']:
            print(f"\nColumns missing in ORM result:")
            for col in comparison['column_differences']['missing_in_df2']:
                print(f"  - {col}")
        
        if comparison['column_differences']['extra_in_df2']:
            print(f"\nExtra columns in ORM result:")
            for col in comparison['column_differences']['extra_in_df2']:
                print(f"  - {col}")
        
        # Row differences
        if comparison['missing_in_df2']:
            print(f"\n{len(comparison['missing_in_df2'])} rows missing in ORM result")
            if len(comparison['missing_in_df2']) <= 5:
                print("  Keys:", comparison['missing_in_df2'])
        
        if comparison['extra_in_df2']:
            print(f"\n{len(comparison['extra_in_df2'])} extra rows in ORM result")
            if len(comparison['extra_in_df2']) <= 5:
                print("  Keys:", comparison['extra_in_df2'])
        
        # Field differences
        if comparison['row_differences']:
            print(f"\nField differences in common rows (showing first 5):")
            for i, row_diff in enumerate(comparison['row_differences'][:5]):
                print(f"\n  Row {row_diff['key']}:")
                for field, values in row_diff['differences'].items():
                    print(f"    {field}:")
                    print(f"      Raw SQL: {values['df1']}")
                    print(f"      ORM:     {values['df2']}")
        
        # Save detailed comparison
        self.save_comparison(query_name, df_raw, df_orm, comparison)
    
    def save_comparison(self, query_name: str, df_raw: pd.DataFrame, 
                       df_orm: pd.DataFrame, comparison: Dict):
        """Save detailed comparison to file"""
        output_file = self.output_dir / f"{query_name}_comparison.txt"
        
        with open(output_file, 'w') as f:
            f.write(f"Query Comparison: {query_name}\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("Summary:\n")
            f.write(f"  Raw SQL Shape: {df_raw.shape}\n")
            f.write(f"  ORM Shape: {df_orm.shape}\n")
            f.write(f"  Identical: {comparison['identical']}\n\n")
            
            if not comparison['identical']:
                f.write("Differences:\n")
                f.write(json.dumps(comparison, indent=2, default=str))
                f.write("\n\n")
                
                # Write sample data
                f.write("Sample Raw SQL Data (first 5 rows):\n")
                f.write(df_raw.head().to_string())
                f.write("\n\n")
                
                f.write("Sample ORM Data (first 5 rows):\n")
                f.write(df_orm.head().to_string())
        
        print(f"\nDetailed comparison saved to: {output_file}")
    
    def compare_specific_query(self, query_name: str, params: Dict = None):
        """Compare a specific query with detailed analysis"""
        self.print_header(f"Comparing: {query_name}", 2)
        
        try:
            # Define query mappings
            query_mappings = {
                'get_web_caps_for_client': {
                    'raw': lambda: runrawsql(get_raw_query("get_web_caps_for_client")),
                    'orm': lambda: QueryRepository.get_web_caps_for_client(),
                    'key_columns': ['id']
                },
                'get_childrens_of_bt': {
                    'raw': lambda: runrawsql(get_raw_query("get_childrens_of_bt"), [params.get('bt_id', 1)]),
                    'orm': lambda: QueryRepository.get_childrens_of_bt(params.get('bt_id', 1)),
                    'key_columns': ['id']
                },
                'get_ticketlist_for_escalation': {
                    'raw': lambda: runrawsql(get_raw_query("get_ticketlist_for_escalation")),
                    'orm': lambda: QueryRepository.get_ticketlist_for_escalation(),
                    'key_columns': ['id']
                },
                'TASKSUMMARY': {
                    'raw': lambda: runrawsql(
                        get_report_query("TASKSUMMARY"),
                        args={
                            'timezone': params.get('timezone', 'UTC'),
                            'siteids': ','.join(map(str, params.get('siteids', [1]))),
                            'from': params.get('from_date', datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),
                            'upto': params.get('to_date', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
                        },
                        named_params=True
                    ),
                    'orm': lambda: ReportQueryRepository.tasksummary_report(
                        timezone_str=params.get('timezone', 'UTC'),
                        siteids=params.get('siteids', [1]),
                        from_date=params.get('from_date', datetime.now() - timedelta(days=7)),
                        upto_date=params.get('to_date', datetime.now())
                    ),
                    'key_columns': ['planned_date']
                }
            }
            
            if query_name not in query_mappings:
                print(f"{Fore.RED}Unknown query: {query_name}{Style.RESET_ALL}")
                return
            
            mapping = query_mappings[query_name]
            
            # Execute queries
            print("Executing raw SQL query...")
            raw_results = mapping['raw']()
            print(f"  Retrieved {len(raw_results) if raw_results else 0} records")
            
            print("Executing ORM query...")
            orm_results = mapping['orm']()
            print(f"  Retrieved {len(orm_results) if orm_results else 0} records")
            
            # Compare results
            self.visualize_differences(
                query_name, 
                raw_results, 
                orm_results,
                mapping.get('key_columns')
            )
            
            # Store for summary
            self.comparison_results.append({
                'query': query_name,
                'raw_count': len(raw_results) if raw_results else 0,
                'orm_count': len(orm_results) if orm_results else 0,
                'match': len(raw_results) == len(orm_results) if raw_results and orm_results else True
            })
            
        except Exception as e:
            print(f"{Fore.RED}Error comparing {query_name}: {str(e)}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
    
    def run_all_comparisons(self):
        """Run comparisons for all queries"""
        self.print_header("COMPREHENSIVE QUERY COMPARISON", 1)
        
        # Test parameters
        test_params = {
            'bt_id': 1,
            'timezone': 'UTC',
            'siteids': [1],
            'from_date': datetime.now() - timedelta(days=30),
            'to_date': datetime.now()
        }
        
        # List of queries to compare
        queries_to_compare = [
            'get_web_caps_for_client',
            'get_childrens_of_bt',
            'get_ticketlist_for_escalation',
            'TASKSUMMARY'
        ]
        
        # Compare each query
        for query in queries_to_compare:
            self.compare_specific_query(query, test_params)
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate comparison summary"""
        self.print_header("COMPARISON SUMMARY", 1)
        
        if not self.comparison_results:
            print("No comparisons performed")
            return
        
        # Create summary table
        headers = ['Query', 'Raw Count', 'ORM Count', 'Match']
        rows = []
        
        for result in self.comparison_results:
            match_str = f"{Fore.GREEN}✓{Style.RESET_ALL}" if result['match'] else f"{Fore.RED}✗{Style.RESET_ALL}"
            rows.append([
                result['query'],
                result['raw_count'],
                result['orm_count'],
                match_str
            ])
        
        print(tabulate(rows, headers=headers, tablefmt='grid'))
        
        # Calculate statistics
        total = len(self.comparison_results)
        matches = sum(1 for r in self.comparison_results if r['match'])
        
        print(f"\nTotal Queries Compared: {total}")
        print(f"Matching Results: {matches}")
        print(f"Mismatches: {total - matches}")
        
        if matches == total:
            print(f"\n{Fore.GREEN}✓ All queries produce matching record counts!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}✗ Found {total - matches} queries with mismatches{Style.RESET_ALL}")
            print(f"Check {self.output_dir} for detailed comparisons")


def analyze_single_query(query_name: str):
    """Analyze a single query in detail"""
    comparator = QueryResultComparator()
    
    print(f"\nAnalyzing query: {query_name}")
    
    # Default test parameters
    test_params = {
        'bt_id': 1,
        'timezone': 'UTC',
        'siteids': [1],
        'from_date': datetime.now() - timedelta(days=7),
        'to_date': datetime.now()
    }
    
    comparator.compare_specific_query(query_name, test_params)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Compare Django ORM query results with raw SQL')
    parser.add_argument('--query', help='Specific query to analyze')
    parser.add_argument('--all', action='store_true', help='Compare all queries')
    
    args = parser.parse_args()
    
    comparator = QueryResultComparator()
    
    if args.query:
        analyze_single_query(args.query)
    else:
        comparator.run_all_comparisons()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())