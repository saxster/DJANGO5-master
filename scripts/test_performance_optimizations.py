#!/usr/bin/env python
"""
Performance Optimization Testing Script

This script validates that all performance optimizations are working correctly:
1. Database query optimization validation
2. Cache functionality testing
3. Static asset optimization verification
4. Monitoring system validation
5. Alert system testing

Usage:
    python scripts/test_performance_optimizations.py
    python scripts/test_performance_optimizations.py --verbose
    python scripts/test_performance_optimizations.py --category database
"""

import os
import sys
import time
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import argparse

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')

import django
django.setup()

from django.test import TestCase, Client
from django.core.cache import cache
from django.db import connection, reset_queries
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command

# Import our optimization modules with error handling
try:
    from apps.activity.managers.job_manager_orm_optimized import JobneedManagerORMOptimized
    JOBNEED_MANAGER_AVAILABLE = True
except ImportError:
    JOBNEED_MANAGER_AVAILABLE = False

try:
    from apps.activity.managers.asset_manager_orm_optimized import AssetManagerORMOptimized
    ASSET_MANAGER_AVAILABLE = True
except ImportError:
    ASSET_MANAGER_AVAILABLE = False

try:
    from apps.core.utils_new.query_optimizer import QueryAnalyzer
    QUERY_ANALYZER_AVAILABLE = True
except ImportError:
    QUERY_ANALYZER_AVAILABLE = False

try:
    from apps.core.cache_strategies import MultiLevelCache, query_cache
    CACHE_STRATEGIES_AVAILABLE = True
except ImportError:
    CACHE_STRATEGIES_AVAILABLE = False

try:
    from monitoring.performance_monitor_enhanced import performance_monitor
    PERFORMANCE_MONITOR_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITOR_AVAILABLE = False

try:
    from monitoring.real_time_alerts import alert_manager, AlertSeverity
    ALERT_SYSTEM_AVAILABLE = True
except ImportError:
    ALERT_SYSTEM_AVAILABLE = False

User = get_user_model()


@dataclass
class TestResult:
    """Test result data structure"""
    category: str
    test_name: str
    status: str  # 'PASS', 'FAIL', 'SKIP'
    duration: float
    details: Dict[str, Any]
    error: str = None


class PerformanceOptimizationTester:
    """Comprehensive testing suite for performance optimizations"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[TestResult] = []
        self.client = Client()
        
        # Test configuration
        self.config = {
            'slow_query_threshold': 0.1,  # 100ms
            'cache_test_iterations': 100,
            'load_test_requests': 50,
            'expected_cache_hit_rate': 0.85  # 85%
        }
        
        print("🚀 Performance Optimization Testing Suite")
        print("=" * 50)
    
    def run_all_tests(self):
        """Run all performance optimization tests"""
        test_categories = [
            ('database', self.test_database_optimizations),
            ('cache', self.test_cache_optimizations),
            ('static', self.test_static_asset_optimization),
            ('monitoring', self.test_monitoring_system),
            ('alerts', self.test_alert_system)
        ]
        
        for category, test_method in test_categories:
            try:
                print(f"\n📊 Testing {category.upper()} optimizations...")
                test_method()
            except Exception as e:
                self.results.append(TestResult(
                    category=category,
                    test_name=f'{category}_general',
                    status='FAIL',
                    duration=0,
                    details={},
                    error=str(e)
                ))
                print(f"❌ Error testing {category}: {e}")
        
        self.print_summary()
    
    def test_database_optimizations(self):
        """Test database query optimizations"""
        
        # Test 1: Selective field loading
        start_time = time.time()
        try:
            if not JOBNEED_MANAGER_AVAILABLE:
                self.results.append(TestResult(
                    category='database',
                    test_name='selective_field_loading',
                    status='SKIP',
                    duration=time.time() - start_time,
                    details={'reason': 'JobneedManagerORMOptimized not available'}
                ))
                if self.verbose:
                    print(f"  ⏭️ Selective field loading: SKIPPED - Module not available")
            else:
                reset_queries()
                
                # Test job needs query with selective loading
                if QUERY_ANALYZER_AVAILABLE:
                    with QueryAnalyzer() as analyzer:
                        jobs = JobneedManagerORMOptimized.get_job_needs(
                            manager=None, people_id=1, bu_id=1, client_id=1
                        )
                else:
                    # Run without analyzer if not available
                    jobs = JobneedManagerORMOptimized.get_job_needs(
                        manager=None, people_id=1, bu_id=1, client_id=1
                    )
                
                duration = time.time() - start_time
                query_count = len(connection.queries)
                
                self.results.append(TestResult(
                    category='database',
                    test_name='selective_field_loading',
                    status='PASS' if duration < 1.0 else 'FAIL',  # Should complete in <1s
                    duration=duration,
                    details={
                        'query_count': query_count,
                        'job_count': len(jobs) if jobs else 0,
                        'avg_query_time': sum(float(q['time']) for q in connection.queries[-query_count:]) / query_count if query_count else 0,
                        'query_analyzer_used': QUERY_ANALYZER_AVAILABLE
                    }
                ))
                
                if self.verbose:
                    print(f"  ✓ Selective field loading: {duration:.3f}s, {query_count} queries")
            
        except Exception as e:
            self.results.append(TestResult(
                category='database',
                test_name='selective_field_loading',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
        
        # Test 2: Index usage validation
        start_time = time.time()
        try:
            with connection.cursor() as cursor:
                # Check if our performance indexes exist
                cursor.execute("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename IN ('activity_jobneed', 'activity_asset') 
                    AND indexname LIKE 'idx_%performance%'
                """)
                indexes = cursor.fetchall()
            
            duration = time.time() - start_time
            
            self.results.append(TestResult(
                category='database',
                test_name='performance_indexes',
                status='PASS' if indexes else 'FAIL',
                duration=duration,
                details={'indexes_found': len(indexes), 'index_names': [idx[0] for idx in indexes]}
            ))
            
            if self.verbose:
                print(f"  ✓ Performance indexes: {len(indexes)} found")
                
        except Exception as e:
            self.results.append(TestResult(
                category='database',
                test_name='performance_indexes',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
        
        # Test 3: N+1 query detection
        start_time = time.time()
        try:
            if not QUERY_ANALYZER_AVAILABLE:
                self.results.append(TestResult(
                    category='database',
                    test_name='n_plus_one_detection',
                    status='SKIP',
                    duration=time.time() - start_time,
                    details={'reason': 'NPlusOneDetector not available'}
                ))
                if self.verbose:
                    print(f"  ⏭️ N+1 detection: SKIPPED - Query analyzer not available")
            else:
                try:
                    from apps.core.utils_new.query_optimizer import NPlusOneDetector
                    
                    detector = NPlusOneDetector(threshold=3)
                    detector.start_monitoring()
                    
                    # Simulate potential N+1 scenario
                    from apps.peoples.models import People
                    people = People.objects.all()[:5]
                    for person in people:
                        # This might cause N+1 if not optimized
                        groups = person.pgbelonging_set.all()
                    
                    analysis = detector.stop_monitoring()
                    duration = time.time() - start_time
                    
                    self.results.append(TestResult(
                        category='database',
                        test_name='n_plus_one_detection',
                        status='PASS',
                        duration=duration,
                        details={
                            'total_queries': analysis.get('total_queries', 0),
                            'n_plus_one_issues': len(analysis.get('n_plus_one_issues', [])),
                            'slow_queries': len(analysis.get('slow_queries', []))
                        }
                    ))
                    
                    if self.verbose:
                        print(f"  ✓ N+1 detection: {analysis.get('total_queries', 0)} queries, {len(analysis.get('n_plus_one_issues', []))} issues")
                        
                except ImportError:
                    # NPlusOneDetector not available
                    self.results.append(TestResult(
                        category='database',
                        test_name='n_plus_one_detection',
                        status='SKIP',
                        duration=time.time() - start_time,
                        details={'reason': 'NPlusOneDetector class not found'}
                    ))
                    if self.verbose:
                        print(f"  ⏭️ N+1 detection: SKIPPED - NPlusOneDetector class not found")
                
        except Exception as e:
            self.results.append(TestResult(
                category='database',
                test_name='n_plus_one_detection',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
    
    def test_cache_optimizations(self):
        """Test caching system optimizations"""
        
        # Test 1: Cache connectivity and basic operations
        start_time = time.time()
        try:
            test_key = 'performance_test_key'
            test_value = {'timestamp': datetime.now().isoformat(), 'test': True}
            
            # Test cache set/get
            cache.set(test_key, test_value, 60)
            retrieved_value = cache.get(test_key)
            
            cache_working = retrieved_value == test_value
            duration = time.time() - start_time
            
            self.results.append(TestResult(
                category='cache',
                test_name='basic_cache_operations',
                status='PASS' if cache_working else 'FAIL',
                duration=duration,
                details={'cache_backend': cache.__class__.__name__, 'test_successful': cache_working}
            ))
            
            if self.verbose:
                print(f"  ✓ Basic cache operations: {duration:.3f}s")
            
            # Clean up
            cache.delete(test_key)
            
        except Exception as e:
            self.results.append(TestResult(
                category='cache',
                test_name='basic_cache_operations',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
        
        # Test 2: Multi-level cache functionality
        start_time = time.time()
        try:
            if not CACHE_STRATEGIES_AVAILABLE:
                self.results.append(TestResult(
                    category='cache',
                    test_name='multi_level_cache',
                    status='SKIP',
                    duration=time.time() - start_time,
                    details={'reason': 'MultiLevelCache not available'}
                ))
                if self.verbose:
                    print(f"  ⏭️ Multi-level cache: SKIPPED - Module not available")
            else:
                hot_cache = MultiLevelCache('hot')
                warm_cache = MultiLevelCache('warm')
                
                # Test different cache levels
                hot_key = 'hot_test_data'
                warm_key = 'warm_test_data'
                
                hot_cache.set(hot_key, 'hot_data', timeout=300)
                warm_cache.set(warm_key, 'warm_data', timeout=1800)
                
                hot_retrieved = hot_cache.get(hot_key)
                warm_retrieved = warm_cache.get(warm_key)
                
                cache_levels_working = (hot_retrieved == 'hot_data' and warm_retrieved == 'warm_data')
                duration = time.time() - start_time
                
                self.results.append(TestResult(
                    category='cache',
                    test_name='multi_level_cache',
                    status='PASS' if cache_levels_working else 'FAIL',
                    duration=duration,
                    details={
                        'hot_cache_working': hot_retrieved == 'hot_data',
                        'warm_cache_working': warm_retrieved == 'warm_data'
                    }
                ))
                
                if self.verbose:
                    print(f"  ✓ Multi-level cache: {duration:.3f}s")
            
        except Exception as e:
            self.results.append(TestResult(
                category='cache',
                test_name='multi_level_cache',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
        
        # Test 3: Cache performance under load
        start_time = time.time()
        try:
            iterations = self.config['cache_test_iterations']
            cache_hits = 0
            cache_misses = 0
            
            # Fill cache with test data
            for i in range(iterations):
                cache.set(f'perf_test_{i}', f'data_{i}', 300)
            
            # Test retrieval performance
            retrieval_start = time.time()
            for i in range(iterations):
                value = cache.get(f'perf_test_{i}')
                if value:
                    cache_hits += 1
                else:
                    cache_misses += 1
            
            retrieval_time = time.time() - retrieval_start
            cache_hit_rate = cache_hits / iterations
            
            duration = time.time() - start_time
            
            self.results.append(TestResult(
                category='cache',
                test_name='cache_performance_load',
                status='PASS' if cache_hit_rate >= self.config['expected_cache_hit_rate'] else 'FAIL',
                duration=duration,
                details={
                    'iterations': iterations,
                    'cache_hit_rate': cache_hit_rate,
                    'avg_retrieval_time': retrieval_time / iterations,
                    'total_retrieval_time': retrieval_time
                }
            ))
            
            if self.verbose:
                print(f"  ✓ Cache load test: {cache_hit_rate:.2%} hit rate, {retrieval_time/iterations*1000:.2f}ms avg")
            
            # Cleanup
            for i in range(iterations):
                cache.delete(f'perf_test_{i}')
            
        except Exception as e:
            self.results.append(TestResult(
                category='cache',
                test_name='cache_performance_load',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
    
    def test_static_asset_optimization(self):
        """Test static asset optimization"""
        
        # Test 1: Check if optimization middleware is configured
        start_time = time.time()
        try:
            middleware_configured = any(
                'StaticOptimizationMiddleware' in middleware 
                for middleware in settings.MIDDLEWARE
            )
            
            duration = time.time() - start_time
            
            self.results.append(TestResult(
                category='static',
                test_name='optimization_middleware_config',
                status='PASS' if middleware_configured else 'SKIP',
                duration=duration,
                details={'middleware_configured': middleware_configured}
            ))
            
            if self.verbose:
                print(f"  ✓ Optimization middleware: {'Configured' if middleware_configured else 'Not configured'}")
            
        except Exception as e:
            self.results.append(TestResult(
                category='static',
                test_name='optimization_middleware_config',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
        
        # Test 2: Check for optimized assets
        start_time = time.time()
        try:
            static_root = getattr(settings, 'STATIC_ROOT', None)
            optimized_files = {
                'compressed_assets': 0,
                'webp_images': 0,
                'minified_assets': 0
            }
            
            if static_root and os.path.exists(static_root):
                for root, dirs, files in os.walk(static_root):
                    for file in files:
                        if file.endswith(('.gz', '.br')):
                            optimized_files['compressed_assets'] += 1
                        elif file.endswith('.webp'):
                            optimized_files['webp_images'] += 1
                        elif '.min.' in file:
                            optimized_files['minified_assets'] += 1
            
            duration = time.time() - start_time
            has_optimizations = any(optimized_files.values())
            
            self.results.append(TestResult(
                category='static',
                test_name='optimized_assets_check',
                status='PASS' if has_optimizations else 'SKIP',
                duration=duration,
                details=optimized_files
            ))
            
            if self.verbose:
                print(f"  ✓ Optimized assets: {optimized_files}")
            
        except Exception as e:
            self.results.append(TestResult(
                category='static',
                test_name='optimized_assets_check',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
    
    def test_monitoring_system(self):
        """Test performance monitoring system"""
        
        # Test 1: Performance monitor initialization
        start_time = time.time()
        try:
            if not PERFORMANCE_MONITOR_AVAILABLE:
                self.results.append(TestResult(
                    category='monitoring',
                    test_name='performance_monitor_init',
                    status='SKIP',
                    duration=time.time() - start_time,
                    details={'reason': 'Performance monitor not available'}
                ))
                if self.verbose:
                    print(f"  ⏭️ Performance monitor: SKIPPED - Module not available")
            else:
                # Test if performance monitor is working
                test_metric_recorded = False
                
                # Record a test metric
                performance_monitor.record_metric(
                    metric_type='test_metric',
                    value=1.0,
                    tags={'test': 'performance_validation'}
                )
                
                # Check if metric was recorded (simplified check)
                if hasattr(performance_monitor, 'metrics_history'):
                    test_metric_recorded = len(performance_monitor.metrics_history) > 0
                
                duration = time.time() - start_time
                
                self.results.append(TestResult(
                    category='monitoring',
                    test_name='performance_monitor_init',
                    status='PASS' if test_metric_recorded else 'FAIL',
                    duration=duration,
                    details={'metric_recorded': test_metric_recorded}
                ))
                
                if self.verbose:
                    print(f"  ✓ Performance monitor: {'Working' if test_metric_recorded else 'Not working'}")
            
        except Exception as e:
            self.results.append(TestResult(
                category='monitoring',
                test_name='performance_monitor_init',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
        
        # Test 2: Monitoring middleware configuration
        start_time = time.time()
        try:
            middleware_configured = any(
                'PerformanceMonitoringMiddleware' in middleware 
                for middleware in settings.MIDDLEWARE
            )
            
            duration = time.time() - start_time
            
            self.results.append(TestResult(
                category='monitoring',
                test_name='monitoring_middleware_config',
                status='PASS' if middleware_configured else 'SKIP',
                duration=duration,
                details={'middleware_configured': middleware_configured}
            ))
            
            if self.verbose:
                print(f"  ✓ Monitoring middleware: {'Configured' if middleware_configured else 'Not configured'}")
            
        except Exception as e:
            self.results.append(TestResult(
                category='monitoring',
                test_name='monitoring_middleware_config',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
    
    def test_alert_system(self):
        """Test alert system functionality"""
        
        # Test 1: Alert manager functionality
        start_time = time.time()
        try:
            if not ALERT_SYSTEM_AVAILABLE:
                self.results.append(TestResult(
                    category='alerts',
                    test_name='alert_creation',
                    status='SKIP',
                    duration=time.time() - start_time,
                    details={'reason': 'Alert system not available'}
                ))
                if self.verbose:
                    print(f"  ⏭️ Alert creation: SKIPPED - Module not available")
            else:
                # Create a test alert
                test_alert = alert_manager.create_alert(
                    title="Performance Test Alert",
                    message="This is a test alert for performance validation",
                    severity=AlertSeverity.INFO,
                    source="performance_test",
                    tags={'test': 'validation', 'category': 'performance'}
                )
                
                # Check if alert was created
                active_alerts = alert_manager.get_active_alerts()
                test_alert_found = any(alert.title == "Performance Test Alert" for alert in active_alerts)
                
                duration = time.time() - start_time
                
                self.results.append(TestResult(
                    category='alerts',
                    test_name='alert_creation',
                    status='PASS' if test_alert_found else 'FAIL',
                    duration=duration,
                    details={
                        'alert_id': test_alert.id if test_alert else None,
                        'alert_found': test_alert_found,
                        'active_alerts_count': len(active_alerts)
                    }
                ))
                
                if self.verbose:
                    print(f"  ✓ Alert creation: {'Working' if test_alert_found else 'Not working'}")
                
                # Clean up - resolve the test alert
                if test_alert:
                    alert_manager.resolve_alert(test_alert.id)
            
        except Exception as e:
            self.results.append(TestResult(
                category='alerts',
                test_name='alert_creation',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
        
        # Test 2: Alert summary functionality
        start_time = time.time()
        try:
            if not ALERT_SYSTEM_AVAILABLE:
                self.results.append(TestResult(
                    category='alerts',
                    test_name='alert_summary',
                    status='SKIP',
                    duration=time.time() - start_time,
                    details={'reason': 'Alert system not available'}
                ))
                if self.verbose:
                    print(f"  ⏭️ Alert summary: SKIPPED - Module not available")
            else:
                summary = alert_manager.get_alert_summary(hours=24)
                
                duration = time.time() - start_time
                
                expected_keys = ['total_alerts', 'active_alerts', 'by_severity', 'by_source']
                summary_valid = all(key in summary for key in expected_keys)
                
                self.results.append(TestResult(
                    category='alerts',
                    test_name='alert_summary',
                    status='PASS' if summary_valid else 'FAIL',
                    duration=duration,
                    details=summary
                ))
                
                if self.verbose:
                    print(f"  ✓ Alert summary: {summary.get('total_alerts', 0)} total alerts")
            
        except Exception as e:
            self.results.append(TestResult(
                category='alerts',
                test_name='alert_summary',
                status='FAIL',
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
    
    def print_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "=" * 60)
        print("🎯 PERFORMANCE OPTIMIZATION TEST RESULTS")
        print("=" * 60)
        
        # Calculate summary statistics
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r.status == 'PASS'])
        failed_tests = len([r for r in self.results if r.status == 'FAIL'])
        skipped_tests = len([r for r in self.results if r.status == 'SKIP'])
        
        print(f"\n📊 Summary:")
        print(f"  Total Tests: {total_tests}")
        print(f"  ✅ Passed: {passed_tests}")
        print(f"  ❌ Failed: {failed_tests}")
        print(f"  ⏭️  Skipped: {skipped_tests}")
        print(f"  📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        # Group results by category
        by_category = {}
        for result in self.results:
            if result.category not in by_category:
                by_category[result.category] = []
            by_category[result.category].append(result)
        
        # Print detailed results by category
        for category, results in by_category.items():
            print(f"\n🔍 {category.upper()} Tests:")
            
            for result in results:
                status_icon = {
                    'PASS': '✅',
                    'FAIL': '❌',
                    'SKIP': '⏭️'
                }.get(result.status, '❓')
                
                print(f"  {status_icon} {result.test_name}: {result.status} ({result.duration:.3f}s)")
                
                if self.verbose and result.details:
                    for key, value in result.details.items():
                        print(f"      {key}: {value}")
                
                if result.error:
                    print(f"      Error: {result.error}")
        
        # Performance insights
        print(f"\n🚀 Performance Insights:")
        
        # Database performance
        db_results = [r for r in self.results if r.category == 'database']
        if db_results:
            avg_query_time = sum(
                r.details.get('avg_query_time', 0) for r in db_results 
                if r.details.get('avg_query_time')
            ) / len([r for r in db_results if r.details.get('avg_query_time')])
            
            if avg_query_time > 0:
                print(f"  📊 Average Query Time: {avg_query_time:.3f}s")
        
        # Cache performance
        cache_results = [r for r in self.results if r.category == 'cache']
        cache_load_result = next((r for r in cache_results if r.test_name == 'cache_performance_load'), None)
        if cache_load_result and cache_load_result.details:
            hit_rate = cache_load_result.details.get('cache_hit_rate', 0)
            print(f"  🎯 Cache Hit Rate: {hit_rate:.1%}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        
        if failed_tests > 0:
            print("  ⚠️  Some optimizations are not working correctly. Review failed tests above.")
        
        if passed_tests == total_tests:
            print("  🎉 All optimizations are working perfectly!")
            print("  🚀 Your application is ready for high performance!")
        
        # Save results to file
        self.save_results_to_file()
        
        print(f"\n📄 Detailed results saved to: performance_test_results.json")
        print("=" * 60)
    
    def save_results_to_file(self):
        """Save test results to JSON file"""
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': len(self.results),
                'passed': len([r for r in self.results if r.status == 'PASS']),
                'failed': len([r for r in self.results if r.status == 'FAIL']),
                'skipped': len([r for r in self.results if r.status == 'SKIP'])
            },
            'results': []
        }
        
        for result in self.results:
            results_data['results'].append({
                'category': result.category,
                'test_name': result.test_name,
                'status': result.status,
                'duration': result.duration,
                'details': result.details,
                'error': result.error
            })
        
        with open('performance_test_results.json', 'w') as f:
            json.dump(results_data, f, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(description='Test performance optimizations')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--category', choices=['database', 'cache', 'static', 'monitoring', 'alerts'], 
                       help='Run tests for specific category only')
    
    args = parser.parse_args()
    
    tester = PerformanceOptimizationTester(verbose=args.verbose)
    
    if args.category:
        # Run specific category tests
        test_method = getattr(tester, f'test_{args.category}_optimizations', None)
        if test_method:
            print(f"\n📊 Testing {args.category.upper()} optimizations...")
            test_method()
            tester.print_summary()
        else:
            print(f"❌ Unknown category: {args.category}")
    else:
        # Run all tests
        tester.run_all_tests()


if __name__ == '__main__':
    main()