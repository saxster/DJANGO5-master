#!/usr/bin/env python
"""
Monitor Django ORM performance and cache statistics in real-time.
Provides a dashboard view of query performance, cache hits, and recommendations.
"""

import os
import sys
import django
import time
import json
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.db import connection, reset_queries
from django.core.cache import cache
from django.conf import settings

# Import ORM implementations
from apps.activity.managers.asset_manager_orm import AssetManagerORM
from apps.activity.managers.job_manager_orm import JobneedManagerORM
from apps.onboarding.bt_manager_orm import BtManagerORM
from apps.peoples.models import Capability
from apps.activity.models.job_model import Jobneed


class ORMPerformanceMonitor:
    """Real-time ORM performance monitoring"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.cache_stats = {'hits': 0, 'misses': 0}
        
    def measure_query(self, name, func, *args, **kwargs):
        """Measure query performance"""
        # Reset query logging
        reset_queries()
        
        # Measure execution time
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        
        # Get query count
        query_count = len(connection.queries)
        
        # Store metrics
        self.metrics[name].append({
            'duration': duration,
            'queries': query_count,
            'timestamp': datetime.now()
        })
        
        return result, duration, query_count
    
    def test_cache_performance(self):
        """Test cache hit/miss rates"""
        test_key = 'test_monitor_key'
        test_value = {'data': 'test', 'timestamp': str(datetime.now())}
        
        # Test cache miss
        cache.delete(test_key)
        start = time.time()
        result = cache.get(test_key)
        miss_time = time.time() - start
        
        # Set cache
        cache.set(test_key, test_value, 60)
        
        # Test cache hit
        start = time.time()
        result = cache.get(test_key)
        hit_time = time.time() - start
        
        return {
            'miss_time': miss_time * 1000,  # Convert to ms
            'hit_time': hit_time * 1000,
            'speedup': miss_time / hit_time if hit_time > 0 else 0
        }
    
    def get_redis_stats(self):
        """Get Redis cache statistics"""
        try:
            from django_redis import get_redis_connection
            conn = get_redis_connection("default")
            info = conn.info()
            
            return {
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(
                    info.get('keyspace_hits', 0),
                    info.get('keyspace_misses', 0)
                )
            }
        except:
            return {
                'error': 'Redis not available or django-redis not installed'
            }
    
    def _calculate_hit_rate(self, hits, misses):
        """Calculate cache hit rate percentage"""
        total = hits + misses
        if total == 0:
            return 0
        return round((hits / total) * 100, 2)
    
    def run_performance_tests(self):
        """Run performance tests on all ORM functions"""
        print("\n" + "=" * 80)
        print("ORM PERFORMANCE MONITORING DASHBOARD")
        print("=" * 80)
        print(f"Started at: {datetime.now()}")
        print("=" * 80)
        
        # Test parameters
        test_bu_id = 1
        test_client_id = 1
        test_people_id = 1
        test_date = datetime.now() - timedelta(days=30)
        
        tests = [
            {
                'name': 'Asset Details',
                'func': AssetManagerORM.get_asset_details,
                'args': [test_date, test_bu_id]
            },
            {
                'name': 'Asset Question Sets',
                'func': AssetManagerORM.get_asset_vs_questionset,
                'args': [test_bu_id, '1', '']
            },
            {
                'name': 'Job Needs',
                'func': JobneedManagerORM.get_job_needs,
                'args': [Jobneed.objects, test_people_id, test_bu_id, test_client_id]
            },
            {
                'name': 'External Tours',
                'func': JobneedManagerORM.get_external_tour_job_needs,
                'args': [Jobneed.objects, test_people_id, test_bu_id, test_client_id]
            },
            {
                'name': 'BU List by Identifier',
                'func': BtManagerORM.get_bulist_basedon_idnf,
                'args': [test_bu_id, True, True]
            },
        ]
        
        # Run tests
        results = []
        for test in tests:
            print(f"\nTesting: {test['name']}")
            print("-" * 40)
            
            try:
                result, duration, queries = self.measure_query(
                    test['name'],
                    test['func'],
                    *test['args']
                )
                
                print(f"✓ Duration: {duration*1000:.2f}ms")
                print(f"✓ Queries: {queries}")
                print(f"✓ Records: {len(result) if hasattr(result, '__len__') else 'N/A'}")
                
                results.append({
                    'name': test['name'],
                    'success': True,
                    'duration': duration,
                    'queries': queries
                })
                
            except Exception as e:
                print(f"✗ Error: {str(e)}")
                results.append({
                    'name': test['name'],
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def print_summary(self):
        """Print performance summary"""
        print("\n" + "=" * 80)
        print("PERFORMANCE SUMMARY")
        print("=" * 80)
        
        # Cache statistics
        cache_stats = self.test_cache_performance()
        redis_stats = self.get_redis_stats()
        
        print("\nCache Performance:")
        print("-" * 40)
        print(f"Cache Hit Time: {cache_stats['hit_time']:.2f}ms")
        print(f"Cache Miss Time: {cache_stats['miss_time']:.2f}ms")
        print(f"Cache Speedup: {cache_stats['speedup']:.1f}x")
        
        if 'error' not in redis_stats:
            print(f"\nRedis Statistics:")
            print("-" * 40)
            print(f"Memory Usage: {redis_stats['used_memory_human']}")
            print(f"Connected Clients: {redis_stats['connected_clients']}")
            print(f"Hit Rate: {redis_stats['hit_rate']:.1f}%")
            print(f"Total Hits: {redis_stats['keyspace_hits']:,}")
            print(f"Total Misses: {redis_stats['keyspace_misses']:,}")
        
        # Query performance by function
        print(f"\nQuery Performance by Function:")
        print("-" * 40)
        print(f"{'Function':<25} {'Avg Time':<12} {'Queries':<10} {'Samples'}")
        print("-" * 40)
        
        for func_name, metrics in self.metrics.items():
            if metrics:
                avg_duration = statistics.mean([m['duration'] for m in metrics])
                avg_queries = statistics.mean([m['queries'] for m in metrics])
                
                print(f"{func_name:<25} {avg_duration*1000:<12.2f}ms {avg_queries:<10.1f} {len(metrics)}")
        
        # Recommendations
        self.print_recommendations()
    
    def print_recommendations(self):
        """Print performance recommendations"""
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        
        recommendations = []
        
        # Analyze slow queries
        for func_name, metrics in self.metrics.items():
            if metrics:
                avg_duration = statistics.mean([m['duration'] for m in metrics])
                avg_queries = statistics.mean([m['queries'] for m in metrics])
                
                if avg_duration > 0.1:  # > 100ms
                    recommendations.append({
                        'function': func_name,
                        'issue': 'Slow query',
                        'duration': avg_duration,
                        'solution': 'Enable caching or add database indexes'
                    })
                
                if avg_queries > 10:
                    recommendations.append({
                        'function': func_name,
                        'issue': 'Too many queries',
                        'queries': avg_queries,
                        'solution': 'Use select_related/prefetch_related'
                    })
        
        # Check cache configuration
        if not hasattr(settings, 'CACHES') or settings.CACHES['default']['BACKEND'] == 'django.core.cache.backends.locmem.LocMemCache':
            recommendations.append({
                'function': 'Cache',
                'issue': 'Not using Redis',
                'solution': 'Configure Redis cache backend for better performance'
            })
        
        # Print recommendations
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                print(f"\n{i}. {rec['function']}: {rec['issue']}")
                if 'duration' in rec:
                    print(f"   Current: {rec['duration']*1000:.1f}ms")
                if 'queries' in rec:
                    print(f"   Queries: {rec['queries']:.0f}")
                print(f"   Solution: {rec['solution']}")
        else:
            print("\n✅ No critical performance issues detected!")
            print("   Consider enabling caching for even better performance.")
    
    def continuous_monitoring(self, interval=60):
        """Run continuous monitoring"""
        print("\nStarting continuous monitoring (Ctrl+C to stop)...")
        print(f"Interval: {interval} seconds")
        
        try:
            while True:
                # Clear screen (Unix/Linux)
                os.system('clear' if os.name == 'posix' else 'cls')
                
                # Run tests
                self.run_performance_tests()
                self.print_summary()
                
                # Wait
                print(f"\nNext update in {interval} seconds...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            self.save_metrics()
    
    def save_metrics(self):
        """Save metrics to file"""
        filename = f"orm_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'metrics': dict(self.metrics),
            'summary': {
                func_name: {
                    'avg_duration': statistics.mean([m['duration'] for m in metrics]),
                    'avg_queries': statistics.mean([m['queries'] for m in metrics]),
                    'samples': len(metrics)
                }
                for func_name, metrics in self.metrics.items()
                if metrics
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"\nMetrics saved to: {filename}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor Django ORM performance')
    parser.add_argument('--continuous', '-c', action='store_true', 
                       help='Run continuous monitoring')
    parser.add_argument('--interval', '-i', type=int, default=60,
                       help='Monitoring interval in seconds (default: 60)')
    
    args = parser.parse_args()
    
    monitor = ORMPerformanceMonitor()
    
    if args.continuous:
        monitor.continuous_monitoring(args.interval)
    else:
        # Run once
        monitor.run_performance_tests()
        monitor.print_summary()
        
        # Save metrics
        response = input("\nSave metrics to file? (y/n): ")
        if response.lower() == 'y':
            monitor.save_metrics()


if __name__ == "__main__":
    main()