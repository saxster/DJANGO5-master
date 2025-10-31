#!/usr/bin/env python
"""
Performance benchmark script for Django ORM vs PostgreSQL functions.
Measures execution time, memory usage, and query counts.
"""

import os
import sys
import django
import time
import gc
import psutil
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.db import connection, reset_queries
from django.conf import settings
from django.test.utils import override_settings

# Import implementations
from apps.activity.managers.asset_manager_orm import AssetManagerORM
from apps.activity.managers.job_manager_orm import JobneedManagerORM
from apps.onboarding.bt_manager_orm import BtManagerORM
from apps.peoples.models import Capability
from apps.activity.models.job_model import Jobneed
from apps.onboarding.models import Bt


class PerformanceBenchmark:
    """Performance benchmarking for ORM migrations"""
    
    def __init__(self, iterations: int = 10, warmup: int = 2):
        self.iterations = iterations
        self.warmup = warmup
        self.results = {}
        
    def benchmark_function(self, name: str, orm_func, pg_func, *args, **kwargs):
        """Benchmark a single function comparison"""
        print(f"\nBenchmarking: {name}")
        print("-" * 50)
        
        # Warmup runs
        print(f"Warming up ({self.warmup} iterations)...")
        for _ in range(self.warmup):
            orm_func(*args, **kwargs)
            pg_func(*args, **kwargs)
            
        # Clear caches
        gc.collect()
        
        # ORM benchmarks
        orm_times = []
        orm_queries = []
        orm_memory = []
        
        print(f"Testing ORM ({self.iterations} iterations)...")
        for i in range(self.iterations):
            # Reset query tracking
            reset_queries()
            
            # Memory before
            process = psutil.Process()
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Time execution
            start = time.perf_counter()
            result = orm_func(*args, **kwargs)
            end = time.perf_counter()
            
            # Memory after
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            
            # Record metrics
            orm_times.append(end - start)
            orm_queries.append(len(connection.queries))
            orm_memory.append(mem_after - mem_before)
            
            # Progress
            if (i + 1) % 5 == 0:
                print(f"  Progress: {i + 1}/{self.iterations}")
                
        # PostgreSQL benchmarks
        pg_times = []
        pg_memory = []
        
        print(f"Testing PostgreSQL ({self.iterations} iterations)...")
        for i in range(self.iterations):
            # Memory before
            process = psutil.Process()
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Time execution
            start = time.perf_counter()
            result = pg_func(*args, **kwargs)
            end = time.perf_counter()
            
            # Memory after
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            
            # Record metrics
            pg_times.append(end - start)
            pg_memory.append(mem_after - mem_before)
            
            # Progress
            if (i + 1) % 5 == 0:
                print(f"  Progress: {i + 1}/{self.iterations}")
                
        # Calculate statistics
        self.results[name] = {
            'orm': {
                'mean_time': statistics.mean(orm_times),
                'median_time': statistics.median(orm_times),
                'std_time': statistics.stdev(orm_times) if len(orm_times) > 1 else 0,
                'min_time': min(orm_times),
                'max_time': max(orm_times),
                'mean_queries': statistics.mean(orm_queries),
                'mean_memory': statistics.mean(orm_memory),
            },
            'postgresql': {
                'mean_time': statistics.mean(pg_times),
                'median_time': statistics.median(pg_times),
                'std_time': statistics.stdev(pg_times) if len(pg_times) > 1 else 0,
                'min_time': min(pg_times),
                'max_time': max(pg_times),
                'mean_queries': 1,  # Always 1 for stored procedures
                'mean_memory': statistics.mean(pg_memory),
            }
        }
        
        # Print immediate results
        orm_stats = self.results[name]['orm']
        pg_stats = self.results[name]['postgresql']
        
        print(f"\nResults for {name}:")
        print(f"  ORM Mean Time: {orm_stats['mean_time']*1000:.2f}ms")
        print(f"  PG Mean Time: {pg_stats['mean_time']*1000:.2f}ms")
        print(f"  Speed Ratio: {orm_stats['mean_time']/pg_stats['mean_time']:.2f}x")
        print(f"  ORM Queries: {orm_stats['mean_queries']:.1f}")
        print(f"  Memory Diff: ORM={orm_stats['mean_memory']:.2f}MB, PG={pg_stats['mean_memory']:.2f}MB")
        
    def run_benchmarks(self):
        """Run all benchmarks"""
        print("=" * 80)
        print("DJANGO ORM PERFORMANCE BENCHMARKS")
        print("=" * 80)
        print(f"Iterations: {self.iterations}")
        print(f"Warmup: {self.warmup}")
        print(f"Database: {connection.settings_dict['NAME']}")
        print("=" * 80)
        
        # Get test data
        test_bu_id = 1
        test_client_id = 1
        test_people_id = 1
        test_date = datetime.now() - timedelta(days=30)
        
        # Benchmark 1: Asset functions
        self.benchmark_function(
            "fn_getassetvsquestionset",
            lambda: AssetManagerORM.get_asset_vs_questionset(test_bu_id, '1', ''),
            lambda: self._run_pg_function("SELECT fn_getassetvsquestionset(%s, %s, %s)", 
                                        [test_bu_id, '1', ''])
        )
        
        self.benchmark_function(
            "fn_getassetdetails",
            lambda: AssetManagerORM.get_asset_details(test_date, test_bu_id),
            lambda: self._run_pg_function("SELECT * FROM fn_getassetdetails(%s, %s)", 
                                        [test_date, test_bu_id])
        )
        
        # Benchmark 2: Job functions
        self.benchmark_function(
            "fun_getjobneed",
            lambda: JobneedManagerORM.get_job_needs(
                Jobneed.objects, test_people_id, test_bu_id, test_client_id
            ),
            lambda: self._run_pg_function(
                "SELECT * FROM fun_getjobneed(%s, %s, %s)",
                [test_people_id, test_bu_id, test_client_id]
            )
        )
        
        # Benchmark 3: Business unit functions
        self.benchmark_function(
            "fn_getbulist_basedon_idnf",
            lambda: BtManagerORM.get_bulist_basedon_idnf(test_bu_id, True, True),
            lambda: self._run_pg_function(
                "SELECT fn_getbulist_basedon_idnf(%s, %s, %s)",
                [test_bu_id, True, True]
            )
        )
        
        # Print summary
        self._print_summary()
        
    def _run_pg_function(self, sql: str, params: List):
        """Execute PostgreSQL function"""
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
            
    def _print_summary(self):
        """Print benchmark summary"""
        print("\n" + "=" * 80)
        print("BENCHMARK SUMMARY")
        print("=" * 80)
        
        # Overall statistics
        total_orm_time = sum(r['orm']['mean_time'] for r in self.results.values())
        total_pg_time = sum(r['postgresql']['mean_time'] for r in self.results.values())
        
        print(f"\nTotal Mean Time:")
        print(f"  ORM: {total_orm_time*1000:.2f}ms")
        print(f"  PostgreSQL: {total_pg_time*1000:.2f}ms")
        print(f"  Overall Ratio: {total_orm_time/total_pg_time:.2f}x")
        
        # Detailed comparison table
        print("\nDetailed Comparison:")
        print("-" * 80)
        print(f"{'Function':<30} {'ORM (ms)':<12} {'PG (ms)':<12} {'Ratio':<8} {'Queries':<10}")
        print("-" * 80)
        
        for name, stats in self.results.items():
            orm_time = stats['orm']['mean_time'] * 1000
            pg_time = stats['postgresql']['mean_time'] * 1000
            ratio = orm_time / pg_time
            queries = stats['orm']['mean_queries']
            
            print(f"{name:<30} {orm_time:<12.2f} {pg_time:<12.2f} {ratio:<8.2f} {queries:<10.1f}")
            
        print("-" * 80)
        
        # Performance recommendations
        print("\nPERFORMANCE ANALYSIS:")
        
        slow_functions = []
        for name, stats in self.results.items():
            ratio = stats['orm']['mean_time'] / stats['postgresql']['mean_time']
            if ratio > 2.0:
                slow_functions.append((name, ratio))
                
        if slow_functions:
            print("\n⚠️  Functions with significant performance impact:")
            for func, ratio in slow_functions:
                print(f"   - {func}: {ratio:.2f}x slower")
                print(f"     Consider: Caching, query optimization, or keeping PG function")
        else:
            print("\n✅ All functions perform within acceptable range (< 2x slower)")
            
        # Query count analysis
        print("\n📊 Query Count Analysis:")
        for name, stats in self.results.items():
            queries = stats['orm']['mean_queries']
            if queries > 5:
                print(f"   - {name}: {queries:.0f} queries (consider optimization)")
                
        # Memory analysis
        print("\n💾 Memory Usage Analysis:")
        for name, stats in self.results.items():
            orm_mem = stats['orm']['mean_memory']
            pg_mem = stats['postgresql']['mean_memory']
            if orm_mem > pg_mem * 2:
                print(f"   - {name}: ORM uses {orm_mem:.2f}MB vs PG {pg_mem:.2f}MB")
                
        # Save results to file
        self._save_results()
        
    def _save_results(self):
        """Save benchmark results to JSON file"""
        filename = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'settings': {
                    'iterations': self.iterations,
                    'warmup': self.warmup,
                    'database': connection.settings_dict['NAME'],
                },
                'results': self.results
            }, f, indent=2)
            
        print(f"\n📁 Results saved to: {filename}")


def main():
    """Run performance benchmarks"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Benchmark Django ORM vs PostgreSQL functions')
    parser.add_argument('--iterations', type=int, default=10, help='Number of iterations (default: 10)')
    parser.add_argument('--warmup', type=int, default=2, help='Number of warmup runs (default: 2)')
    
    args = parser.parse_args()
    
    # Ensure debug mode is off for accurate benchmarks
    if settings.DEBUG:
        print("⚠️  Warning: DEBUG mode is ON. Results may not be accurate.")
        print("   Consider running with DEBUG=False for production-like results.")
        print()
        
    try:
        benchmark = PerformanceBenchmark(
            iterations=args.iterations,
            warmup=args.warmup
        )
        benchmark.run_benchmarks()
        
    except Exception as e:
        print(f"Error running benchmarks: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
