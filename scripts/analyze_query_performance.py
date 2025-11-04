#!/usr/bin/env python
"""
Query performance analysis tool for Django ORM migration.
Analyzes query patterns and recommends database indexes.
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple, Any
from collections import defaultdict, Counter
import time

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

from django.db import connection
from django.db.models import Count, Avg, Sum, Max, Min
from django.apps import apps
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


class QueryPerformanceAnalyzer:
    """Analyze query performance and recommend optimizations"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'query_patterns': defaultdict(list),
            'slow_queries': [],
            'frequent_queries': Counter(),
            'index_recommendations': [],
            'optimization_opportunities': [],
            'performance_metrics': {}
        }
        
        # Performance thresholds
        self.SLOW_QUERY_THRESHOLD = 0.1  # 100ms
        self.VERY_SLOW_QUERY_THRESHOLD = 0.5  # 500ms
        
        # Critical query patterns from our ORM migration
        self.critical_queries = {
            'capability_tree': {
                'models': ['core.Capability'],
                'fields': ['parent_id', 'cfor'],
                'description': 'Capability tree traversal queries'
            },
            'bt_hierarchy': {
                'models': ['onboarding.Bt'],
                'fields': ['parent_id', 'identifier_id', 'bucode'],
                'description': 'Business unit hierarchy queries'
            },
            'ticket_escalation': {
                'models': ['y_helpdesk.Ticket'],
                'fields': ['status_id', 'createdon', 'site_id', 'assignedto_id'],
                'description': 'Ticket escalation and filtering'
            },
            'attendance_reports': {
                'models': ['attendance.Attendance'],
                'fields': ['people_id', 'site_id', 'checkin_time', 'checkout_time'],
                'description': 'Attendance reporting queries'
            },
            'task_scheduling': {
                'models': ['activity.TaskSchedule'],
                'fields': ['site_id', 'scheduledon', 'completedon', 'task_id'],
                'description': 'Task scheduling and completion'
            },
            'asset_tracking': {
                'models': ['activity.Asset'],
                'fields': ['site_id', 'assettype_id', 'status_id'],
                'description': 'Asset status and location tracking'
            }
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
    
    def analyze_query_patterns(self):
        """Analyze common query patterns from Django ORM"""
        self.print_header("Analyzing Query Patterns", 2)
        
        for pattern_name, pattern_info in self.critical_queries.items():
            print(f"\nAnalyzing {pattern_name}: {pattern_info['description']}")
            
            for model_path in pattern_info['models']:
                try:
                    app_label, model_name = model_path.split('.')
                    model = apps.get_model(app_label, model_name)
                    
                    # Analyze table size
                    table_size = model.objects.count()
                    print(f"  {model_path}: {table_size:,} records")
                    
                    # Check existing indexes
                    existing_indexes = self.get_existing_indexes(model)
                    
                    # Recommend indexes based on query patterns
                    for field in pattern_info['fields']:
                        if self.should_create_index(model, field, existing_indexes):
                            self.results['index_recommendations'].append({
                                'model': model_path,
                                'field': field,
                                'pattern': pattern_name,
                                'reason': f"Frequent filtering/joining on {field}",
                                'table_size': table_size,
                                'priority': 'HIGH' if table_size > 10000 else 'MEDIUM'
                            })
                    
                except Exception as e:
                    print(f"  {Fore.YELLOW}Error analyzing {model_path}: {str(e)}{Style.RESET_ALL}")
    
    def get_existing_indexes(self, model) -> List[str]:
        """Get list of existing indexes on a model"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = %s
            """, [model._meta.db_table])
            
            indexes = []
            for row in cursor.fetchall():
                indexes.append(row[0])
            
            return indexes
    
    def should_create_index(self, model, field_name: str, existing_indexes: List[str]) -> bool:
        """Determine if an index should be created for a field"""
        # Check if field exists
        try:
            field = model._meta.get_field(field_name)
        except:
            return False
        
        # Skip if already indexed
        if field.db_index or field.primary_key or field.unique:
            return False
        
        # Check if index already exists in database
        index_name = f"{model._meta.db_table}_{field_name}"
        if any(index_name in idx for idx in existing_indexes):
            return False
        
        # Foreign keys usually benefit from indexes
        if field.many_to_one or field.one_to_one:
            return True
        
        # Date/time fields used in filtering benefit from indexes
        if field.__class__.__name__ in ['DateField', 'DateTimeField']:
            return True
        
        # Status/type fields with limited choices benefit from indexes
        if hasattr(field, 'choices') and field.choices:
            return True
        
        return True  # Recommend by default for fields in critical queries
    
    def benchmark_critical_queries(self):
        """Benchmark performance of critical queries"""
        self.print_header("Benchmarking Critical Queries", 2)
        
        benchmarks = [
            {
                'name': 'Capability Tree Traversal',
                'query': lambda: self._benchmark_capability_tree()
            },
            {
                'name': 'BT Hierarchy Traversal',
                'query': lambda: self._benchmark_bt_hierarchy()
            },
            {
                'name': 'Ticket Escalation Query',
                'query': lambda: self._benchmark_ticket_escalation()
            },
            {
                'name': 'Attendance Summary',
                'query': lambda: self._benchmark_attendance_summary()
            },
            {
                'name': 'Task Summary Report',
                'query': lambda: self._benchmark_task_summary()
            }
        ]
        
        for benchmark in benchmarks:
            print(f"\nBenchmarking: {benchmark['name']}")
            try:
                exec_time, result_count = benchmark['query']()
                
                status = "SLOW" if exec_time > self.SLOW_QUERY_THRESHOLD else "OK"
                color = Fore.RED if status == "SLOW" else Fore.GREEN
                
                print(f"  Execution time: {color}{exec_time:.3f}s{Style.RESET_ALL}")
                print(f"  Result count: {result_count}")
                
                if exec_time > self.SLOW_QUERY_THRESHOLD:
                    self.results['slow_queries'].append({
                        'query': benchmark['name'],
                        'execution_time': exec_time,
                        'result_count': result_count,
                        'status': 'VERY_SLOW' if exec_time > self.VERY_SLOW_QUERY_THRESHOLD else 'SLOW'
                    })
                
                self.results['performance_metrics'][benchmark['name']] = {
                    'execution_time': exec_time,
                    'result_count': result_count
                }
                
            except Exception as e:
                print(f"  {Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    
    def _benchmark_capability_tree(self) -> Tuple[float, int]:
        """Benchmark capability tree query"""
        from apps.core.models import Capability
        
        start_time = time.time()
        
        # Simulate tree traversal
        capabilities = Capability.objects.filter(cfor='WEB').select_related('parent')
        all_caps = list(capabilities)
        
        # Build tree structure
        cap_dict = {cap.id: cap for cap in all_caps}
        tree = []
        for cap in all_caps:
            if cap.parent_id is None:
                tree.append(cap)
        
        exec_time = time.time() - start_time
        return exec_time, len(all_caps)
    
    def _benchmark_bt_hierarchy(self) -> Tuple[float, int]:
        """Benchmark BT hierarchy query"""
        from apps.client_onboarding.models import Bt
        
        start_time = time.time()
        
        # Get all BTs with parent relationships
        bts = Bt.objects.select_related('parent', 'identifier').filter(
            identifier__tacode='SITE'
        )
        result_count = bts.count()
        
        exec_time = time.time() - start_time
        return exec_time, result_count
    
    def _benchmark_ticket_escalation(self) -> Tuple[float, int]:
        """Benchmark ticket escalation query"""
        from apps.y_helpdesk.models import Ticket
        from django.utils import timezone
        
        start_time = time.time()
        
        # Escalation query
        tickets = Ticket.objects.select_related(
            'status', 'site', 'assignedto', 'createdby'
        ).filter(
            status__tacode__in=['NEW', 'OPEN'],
            createdon__lt=timezone.now() - timedelta(hours=24)
        )
        result_count = tickets.count()
        
        exec_time = time.time() - start_time
        return exec_time, result_count
    
    def _benchmark_attendance_summary(self) -> Tuple[float, int]:
        """Benchmark attendance summary query"""
        from apps.attendance.models import Attendance
        
        start_time = time.time()
        
        # Attendance summary for last 30 days
        summary = Attendance.objects.filter(
            checkin_time__gte=datetime.now() - timedelta(days=30)
        ).values('site_id').annotate(
            total_hours=Sum('total_time'),
            avg_hours=Avg('total_time'),
            total_attendance=Count('id')
        )
        result_count = len(list(summary))
        
        exec_time = time.time() - start_time
        return exec_time, result_count
    
    def _benchmark_task_summary(self) -> Tuple[float, int]:
        """Benchmark task summary report query"""
        from apps.activity.models import TaskSchedule
        
        start_time = time.time()
        
        # Task summary for reporting
        tasks = TaskSchedule.objects.select_related(
            'task', 'site', 'assignedto'
        ).filter(
            scheduledon__gte=datetime.now() - timedelta(days=30)
        ).values('site_id', 'task__name').annotate(
            total_scheduled=Count('id'),
            completed=Count('completedon'),
            avg_completion_time=Avg('completedon')
        )
        result_count = len(list(tasks))
        
        exec_time = time.time() - start_time
        return exec_time, result_count
    
    def generate_optimization_sql(self):
        """Generate SQL scripts for recommended optimizations"""
        self.print_header("Generating Optimization Scripts", 2)
        
        scripts = []
        
        # Group recommendations by model
        model_indexes = defaultdict(list)
        for rec in self.results['index_recommendations']:
            model_indexes[rec['model']].append(rec)
        
        for model_path, recommendations in model_indexes.items():
            app_label, model_name = model_path.split('.')
            model = apps.get_model(app_label, model_name)
            table_name = model._meta.db_table
            
            script = f"-- Indexes for {model_path}\n"
            script += f"-- Table: {table_name}\n\n"
            
            for rec in recommendations:
                index_name = f"idx_{table_name}_{rec['field']}"
                script += f"-- {rec['reason']} (Priority: {rec['priority']})\n"
                script += f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}\n"
                script += f"ON {table_name} ({rec['field']});\n\n"
            
            scripts.append(script)
        
        # Add composite indexes for common query patterns
        composite_indexes = [
            {
                'table': 'y_helpdesk_ticket',
                'fields': ['status_id', 'createdon'],
                'reason': 'Ticket escalation queries'
            },
            {
                'table': 'attendance_attendance',
                'fields': ['people_id', 'checkin_time'],
                'reason': 'Attendance reports by person and date'
            },
            {
                'table': 'activity_taskschedule',
                'fields': ['site_id', 'scheduledon'],
                'reason': 'Task scheduling by site and date'
            },
            {
                'table': 'onboarding_bt',
                'fields': ['parent_id', 'identifier_id'],
                'reason': 'BT hierarchy traversal'
            }
        ]
        
        script = "-- Composite Indexes for Common Query Patterns\n\n"
        for idx in composite_indexes:
            index_name = f"idx_{idx['table']}_{'_'.join(idx['fields'])}"
            script += f"-- {idx['reason']}\n"
            script += f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}\n"
            script += f"ON {idx['table']} ({', '.join(idx['fields'])});\n\n"
        
        scripts.append(script)
        
        # Save optimization scripts
        script_path = project_root / 'scripts' / 'database_optimizations.sql'
        with open(script_path, 'w') as f:
            f.write("-- Database Optimization Scripts\n")
            f.write(f"-- Generated: {datetime.now()}\n")
            f.write("-- Review and test before applying to production\n\n")
            f.write("-- Note: Using CONCURRENTLY to avoid table locks\n")
            f.write("-- This requires PostgreSQL and may take longer\n\n")
            
            for script in scripts:
                f.write(script)
                f.write("\n" + "-" * 60 + "\n\n")
            
            # Add analysis queries
            f.write("-- Query to check index usage after creation\n")
            f.write("SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read\n")
            f.write("FROM pg_stat_user_indexes\n")
            f.write("WHERE idx_scan > 0\n")
            f.write("ORDER BY idx_scan DESC;\n\n")
            
            f.write("-- Query to find missing indexes\n")
            f.write("SELECT schemaname, tablename, attname, n_distinct, correlation\n")
            f.write("FROM pg_stats\n")
            f.write("WHERE schemaname = 'public'\n")
            f.write("AND n_distinct > 100\n")
            f.write("AND correlation < 0.1\n")
            f.write("ORDER BY n_distinct DESC;\n")
        
        print(f"Optimization scripts saved to: {script_path}")
        
        return scripts
    
    def analyze_query_plans(self):
        """Analyze query execution plans for critical queries"""
        self.print_header("Analyzing Query Execution Plans", 2)
        
        critical_queries = [
            {
                'name': 'Recursive capability query (old)',
                'sql': """
                    WITH RECURSIVE cap AS (
                        SELECT id, capsname, parent_id, 1 as depth
                        FROM core_capability
                        WHERE parent_id IS NULL AND cfor = 'WEB'
                        UNION ALL
                        SELECT c.id, c.capsname, c.parent_id, cap.depth + 1
                        FROM core_capability c
                        INNER JOIN cap ON cap.id = c.parent_id
                    )
                    SELECT * FROM cap;
                """
            },
            {
                'name': 'Simple capability query (new)',
                'sql': """
                    SELECT id, capsname, parent_id, cfor
                    FROM core_capability
                    WHERE cfor = 'WEB'
                    ORDER BY id;
                """
            }
        ]
        
        with connection.cursor() as cursor:
            for query_info in critical_queries:
                print(f"\n{query_info['name']}:")
                try:
                    cursor.execute(f"EXPLAIN ANALYZE {query_info['sql']}")
                    plan = cursor.fetchall()
                    
                    # Extract key metrics
                    total_time = None
                    for line in plan:
                        line_str = line[0]
                        if 'Execution Time:' in line_str:
                            total_time = float(line_str.split(':')[1].strip().split()[0])
                        
                        # Highlight slow operations
                        if any(x in line_str for x in ['Seq Scan', 'Nested Loop', 'Sort']):
                            print(f"  {Fore.YELLOW}{line_str}{Style.RESET_ALL}")
                        else:
                            print(f"  {line_str}")
                    
                    if total_time:
                        color = Fore.RED if total_time > 100 else Fore.GREEN
                        print(f"\n  Total execution time: {color}{total_time:.2f}ms{Style.RESET_ALL}")
                
                except Exception as e:
                    print(f"  {Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    
    def generate_report(self):
        """Generate comprehensive performance analysis report"""
        report_path = project_root / 'reports' / 'query_performance_analysis.md'
        
        with open(report_path, 'w') as f:
            f.write("# Query Performance Analysis Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Executive Summary
            f.write("## Executive Summary\n\n")
            f.write(f"- Total slow queries found: {len(self.results['slow_queries'])}\n")
            f.write(f"- Index recommendations: {len(self.results['index_recommendations'])}\n")
            f.write(f"- Critical query patterns analyzed: {len(self.critical_queries)}\n\n")
            
            # Slow Queries
            if self.results['slow_queries']:
                f.write("## Slow Queries\n\n")
                f.write("| Query | Execution Time | Status | Result Count |\n")
                f.write("|-------|----------------|--------|-------------|\n")
                
                for query in self.results['slow_queries']:
                    f.write(f"| {query['query']} | {query['execution_time']:.3f}s | "
                           f"{query['status']} | {query['result_count']} |\n")
                f.write("\n")
            
            # Index Recommendations
            f.write("## Index Recommendations\n\n")
            
            # Group by priority
            high_priority = [r for r in self.results['index_recommendations'] if r['priority'] == 'HIGH']
            medium_priority = [r for r in self.results['index_recommendations'] if r['priority'] == 'MEDIUM']
            
            if high_priority:
                f.write("### High Priority Indexes\n\n")
                f.write("| Model | Field | Reason | Table Size |\n")
                f.write("|-------|-------|--------|------------|\n")
                
                for rec in high_priority:
                    f.write(f"| {rec['model']} | {rec['field']} | "
                           f"{rec['reason']} | {rec['table_size']:,} |\n")
                f.write("\n")
            
            if medium_priority:
                f.write("### Medium Priority Indexes\n\n")
                f.write("| Model | Field | Reason | Table Size |\n")
                f.write("|-------|-------|--------|------------|\n")
                
                for rec in medium_priority:
                    f.write(f"| {rec['model']} | {rec['field']} | "
                           f"{rec['reason']} | {rec['table_size']:,} |\n")
                f.write("\n")
            
            # Performance Metrics
            f.write("## Performance Metrics\n\n")
            f.write("| Query | Execution Time | Result Count |\n")
            f.write("|-------|----------------|-------------|\n")
            
            for query_name, metrics in self.results['performance_metrics'].items():
                f.write(f"| {query_name} | {metrics['execution_time']:.3f}s | "
                       f"{metrics['result_count']} |\n")
            
            # Optimization Recommendations
            f.write("\n## Optimization Recommendations\n\n")
            f.write("1. **Apply recommended indexes**: Start with high-priority indexes on large tables\n")
            f.write("2. **Use Django's select_related()**: For queries with foreign key lookups\n")
            f.write("3. **Use prefetch_related()**: For reverse foreign key and many-to-many relationships\n")
            f.write("4. **Enable query caching**: For frequently accessed, rarely changing data\n")
            f.write("5. **Consider database views**: For complex report queries\n")
            f.write("6. **Monitor slow query log**: Set up PostgreSQL slow query logging\n\n")
            
            f.write("## Next Steps\n\n")
            f.write("1. Review and test the generated optimization scripts\n")
            f.write("2. Apply indexes in staging environment first\n")
            f.write("3. Monitor query performance after index creation\n")
            f.write("4. Set up continuous query performance monitoring\n")
        
        print(f"\nPerformance analysis report saved to: {report_path}")
    
    def run_analysis(self):
        """Run complete performance analysis"""
        self.print_header("QUERY PERFORMANCE ANALYSIS", 1)
        
        print(f"Database: {connection.settings_dict['NAME']}")
        print(f"Analysis started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Run analysis steps
        self.analyze_query_patterns()
        self.benchmark_critical_queries()
        self.analyze_query_plans()
        
        # Generate outputs
        self.generate_optimization_sql()
        self.generate_report()
        
        # Summary
        self.print_header("ANALYSIS SUMMARY", 1)
        
        print(f"Slow queries identified: {len(self.results['slow_queries'])}")
        print(f"Index recommendations: {len(self.results['index_recommendations'])}")
        
        if self.results['slow_queries']:
            print(f"\n{Fore.YELLOW}Top slow queries to optimize:{Style.RESET_ALL}")
            for query in self.results['slow_queries'][:3]:
                print(f"  - {query['query']}: {query['execution_time']:.3f}s")
        
        if self.results['index_recommendations']:
            print(f"\n{Fore.GREEN}Top index recommendations:{Style.RESET_ALL}")
            for rec in self.results['index_recommendations'][:5]:
                print(f"  - {rec['model']}.{rec['field']} ({rec['priority']} priority)")
        
        # Save results
        results_path = project_root / 'scripts' / 'performance_analysis_results.json'
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nDetailed results saved to: {results_path}")
        
        return len(self.results['slow_queries']) == 0


def main():
    """Main entry point"""
    analyzer = QueryPerformanceAnalyzer()
    success = analyzer.run_analysis()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())