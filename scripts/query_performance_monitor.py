#!/usr/bin/env python
"""
Query performance monitoring tool for Django ORM.
Tracks query execution times and provides insights.
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from apps.core.constants.datetime_constants import LOG_DATETIME_FORMAT
import time
import json
from collections import defaultdict

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

from django.db import connection
from django.test.utils import override_settings
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


class QueryPerformanceMonitor:
    """Monitor and analyze query performance"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'queries': [],
            'summary': {
                'total_queries': 0,
                'total_time': 0,
                'slow_queries': 0,
                'cached_hits': 0
            },
            'patterns': defaultdict(list)
        }
        
        self.SLOW_THRESHOLD = 0.05  # 50ms
    
    def print_header(self, text, level=1):
        """Print formatted header"""
        if level == 1:
            print(f"\n{Fore.BLUE}{'=' * 80}")
            print(f"{Fore.BLUE}{text.center(80)}")
            print(f"{Fore.BLUE}{'=' * 80}{Style.RESET_ALL}\n")
        else:
            print(f"\n{Fore.CYAN}{text}")
            print(f"{Fore.CYAN}{'-' * len(text)}{Style.RESET_ALL}")
    
    @override_settings(DEBUG=True)
    def monitor_query(self, name: str, func, *args, **kwargs):
        """Monitor a single query execution"""
        # Reset query log
        connection.queries_log.clear()
        
        # Execute query
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Get query details
        queries = list(connection.queries)
        
        query_info = {
            'name': name,
            'execution_time': execution_time,
            'query_count': len(queries),
            'queries': queries,
            'slow': execution_time > self.SLOW_THRESHOLD
        }
        
        self.results['queries'].append(query_info)
        self.results['summary']['total_queries'] += len(queries)
        self.results['summary']['total_time'] += execution_time
        
        if query_info['slow']:
            self.results['summary']['slow_queries'] += 1
        
        # Categorize by pattern
        if 'capability' in name.lower():
            self.results['patterns']['hierarchy'].append(query_info)
        elif 'ticket' in name.lower():
            self.results['patterns']['ticketing'].append(query_info)
        elif 'report' in name.lower():
            self.results['patterns']['reporting'].append(query_info)
        
        return result, query_info
    
    def benchmark_critical_queries(self):
        """Benchmark all critical queries"""
        from apps.core.queries import QueryRepository, ReportQueryRepository
        from apps.core.cache_manager import cache
        
        self.print_header("BENCHMARKING CRITICAL QUERIES", 1)
        
        # Clear cache for accurate benchmarking
        cache.clear()
        
        benchmarks = [
            # Hierarchy queries
            {
                'name': 'Web Capabilities Tree',
                'func': QueryRepository.get_web_caps_for_client,
                'args': [],
                'expected_queries': 1
            },
            {
                'name': 'BT Children Hierarchy',
                'func': QueryRepository.get_childrens_of_bt,
                'args': [1],
                'expected_queries': 1
            },
            # Operational queries
            {
                'name': 'Ticket Escalation List',
                'func': QueryRepository.get_ticketlist_for_escalation,
                'args': [],
                'expected_queries': 1
            },
            {
                'name': 'Site Report List',
                'func': QueryRepository.sitereportlist,
                'args': [[1, 2, 3], 1],
                'expected_queries': 2  # Main query + count
            },
            # Report queries
            {
                'name': 'Task Summary Report',
                'func': ReportQueryRepository.tasksummary_report,
                'kwargs': {
                    'timezone_str': 'UTC',
                    'siteids': [1, 2, 3],
                    'from_date': datetime.now() - timedelta(days=7),
                    'upto_date': datetime.now()
                },
                'expected_queries': 1
            }
        ]
        
        for benchmark in benchmarks:
            print(f"\nBenchmarking: {benchmark['name']}")
            
            # First run (cold cache)
            args = benchmark.get('args', [])
            kwargs = benchmark.get('kwargs', {})
            
            try:
                result, info = self.monitor_query(
                    f"{benchmark['name']} (cold)",
                    benchmark['func'],
                    *args,
                    **kwargs
                )
                
                self._print_query_info(info)
                
                # Second run (warm cache)
                result2, info2 = self.monitor_query(
                    f"{benchmark['name']} (cached)",
                    benchmark['func'],
                    *args,
                    **kwargs
                )
                
                if info2['execution_time'] < info['execution_time'] * 0.1:
                    print(f"  {Fore.GREEN}✓ Cache working: {info2['execution_time']:.3f}s (cached){Style.RESET_ALL}")
                    self.results['summary']['cached_hits'] += 1
                
                # Check query count
                if info['query_count'] != benchmark.get('expected_queries', 1):
                    print(f"  {Fore.YELLOW}⚠ Expected {benchmark.get('expected_queries', 1)} queries, got {info['query_count']}{Style.RESET_ALL}")
                
            except Exception as e:
                print(f"  {Fore.RED}✗ Error: {str(e)}{Style.RESET_ALL}")
    
    def _print_query_info(self, info: Dict):
        """Print query execution info"""
        status = "SLOW" if info['slow'] else "OK"
        color = Fore.RED if info['slow'] else Fore.GREEN
        
        print(f"  Execution time: {color}{info['execution_time']:.3f}s{Style.RESET_ALL} ({status})")
        print(f"  Query count: {info['query_count']}")
        
        if info['slow'] and info['queries']:
            print(f"  {Fore.YELLOW}Slow query detected!{Style.RESET_ALL}")
            for i, query in enumerate(info['queries'][:2]):  # Show first 2 queries
                print(f"    Query {i+1}: {query['time']}s")
                if float(query['time']) > 0.01:  # Queries over 10ms
                    print(f"    SQL: {query['sql'][:100]}...")
    
    def analyze_patterns(self):
        """Analyze query patterns"""
        self.print_header("QUERY PATTERN ANALYSIS", 2)
        
        for pattern_name, queries in self.results['patterns'].items():
            if not queries:
                continue
            
            print(f"\n{pattern_name.upper()} Queries:")
            
            total_time = sum(q['execution_time'] for q in queries)
            avg_time = total_time / len(queries) if queries else 0
            slow_count = sum(1 for q in queries if q['slow'])
            
            print(f"  Total queries: {len(queries)}")
            print(f"  Average time: {avg_time:.3f}s")
            print(f"  Slow queries: {slow_count}")
            
            # Find slowest
            if queries:
                slowest = max(queries, key=lambda x: x['execution_time'])
                print(f"  Slowest: {slowest['name']} ({slowest['execution_time']:.3f}s)")
    
    def check_cache_effectiveness(self):
        """Check cache hit rates"""
        self.print_header("CACHE EFFECTIVENESS", 2)
        
        from apps.core.cache_manager import cache
        from django.core.cache import caches
        
        # Try to get cache stats (implementation depends on cache backend)
        try:
            if hasattr(cache, '_cache'):
                # For Redis backend
                if hasattr(cache._cache, 'info'):
                    info = cache._cache.info()
                    print(f"Cache Backend: {cache.__class__.__name__}")
                    print(f"Cache Hits: {info.get('keyspace_hits', 'N/A')}")
                    print(f"Cache Misses: {info.get('keyspace_misses', 'N/A')}")
                    
                    if 'keyspace_hits' in info and 'keyspace_misses' in info:
                        hits = info['keyspace_hits']
                        misses = info['keyspace_misses']
                        hit_rate = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0
                        print(f"Hit Rate: {hit_rate:.1f}%")
        except:
            print("Cache statistics not available for current backend")
        
        print(f"\nCached query hits in this session: {self.results['summary']['cached_hits']}")
    
    def generate_recommendations(self):
        """Generate performance recommendations"""
        self.print_header("PERFORMANCE RECOMMENDATIONS", 2)
        
        recommendations = []
        
        # Check for slow queries
        if self.results['summary']['slow_queries'] > 0:
            slow_pct = (self.results['summary']['slow_queries'] / len(self.results['queries']) * 100)
            recommendations.append({
                'severity': 'HIGH' if slow_pct > 20 else 'MEDIUM',
                'message': f"{slow_pct:.1f}% of queries are slow (>{self.SLOW_THRESHOLD*1000}ms)",
                'action': "Review slow queries and add appropriate indexes"
            })
        
        # Check query count
        for query in self.results['queries']:
            if query['query_count'] > 5:
                recommendations.append({
                    'severity': 'HIGH',
                    'message': f"{query['name']} executes {query['query_count']} queries",
                    'action': "Use select_related() or prefetch_related() to reduce queries"
                })
        
        # Check cache usage
        if self.results['summary']['cached_hits'] < len(self.results['queries']) * 0.3:
            recommendations.append({
                'severity': 'MEDIUM',
                'message': "Low cache hit rate detected",
                'action': "Implement caching for frequently accessed queries"
            })
        
        # Print recommendations
        if recommendations:
            high_severity = [r for r in recommendations if r['severity'] == 'HIGH']
            medium_severity = [r for r in recommendations if r['severity'] == 'MEDIUM']
            
            if high_severity:
                print(f"\n{Fore.RED}HIGH SEVERITY:{Style.RESET_ALL}")
                for rec in high_severity:
                    print(f"  • {rec['message']}")
                    print(f"    Action: {rec['action']}")
            
            if medium_severity:
                print(f"\n{Fore.YELLOW}MEDIUM SEVERITY:{Style.RESET_ALL}")
                for rec in medium_severity:
                    print(f"  • {rec['message']}")
                    print(f"    Action: {rec['action']}")
        else:
            print(f"{Fore.GREEN}✓ No significant performance issues detected!{Style.RESET_ALL}")
    
    def generate_report(self):
        """Generate performance report"""
        report_path = project_root / 'reports' / 'query_performance_monitor.json'
        
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Generate summary
        self.print_header("PERFORMANCE SUMMARY", 1)
        
        print(f"Total queries executed: {self.results['summary']['total_queries']}")
        print(f"Total execution time: {self.results['summary']['total_time']:.3f}s")
        
        if self.results['summary']['total_queries'] > 0:
            avg_time = self.results['summary']['total_time'] / self.results['summary']['total_queries']
            print(f"Average query time: {avg_time*1000:.1f}ms")
        
        print(f"Slow queries: {self.results['summary']['slow_queries']}")
        print(f"Cache hits: {self.results['summary']['cached_hits']}")
        
        print(f"\nDetailed report saved to: {report_path}")
    
    def run_monitoring(self):
        """Run complete performance monitoring"""
        self.print_header("DJANGO ORM PERFORMANCE MONITORING", 1)
        
        print(f"Monitoring started: {datetime.now().strftime(LOG_DATETIME_FORMAT)}")
        print(f"Slow query threshold: {self.SLOW_THRESHOLD*1000}ms\n")
        
        # Run benchmarks
        self.benchmark_critical_queries()
        
        # Analyze patterns
        self.analyze_patterns()
        
        # Check cache
        self.check_cache_effectiveness()
        
        # Generate recommendations
        self.generate_recommendations()
        
        # Generate report
        self.generate_report()
        
        return self.results['summary']['slow_queries'] == 0


def main():
    """Main entry point"""
    monitor = QueryPerformanceMonitor()
    success = monitor.run_monitoring()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())