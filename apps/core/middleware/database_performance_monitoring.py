"""
Enhanced Database Performance Monitoring Middleware

This middleware provides comprehensive monitoring of database performance including:
- Query analysis and N+1 detection
- Performance regression alerts
- Connection pool monitoring with alerts
- Integration with pg_stat_statements
- Real-time performance analytics

Features:
- Connection saturation monitoring
- Slow query detection and alerting
- Historical performance tracking
- Automatic performance optimization recommendations
"""

import time
import logging
import threading
from collections import defaultdict
from typing import Dict, List, Optional
from django.conf import settings
from django.db import connection, connections
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve
from django.urls.exceptions import Resolver404
from django.core.exceptions import SuspiciousOperation
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger('db_performance')


class ConnectionPoolMonitor:
    """
    Monitors database connection pool status and alerts on saturation.

    Tracks connection usage patterns and provides early warning
    when connection limits are approaching.
    """

    def __init__(self):
        self.alert_thresholds = {
            'connection_usage_warning': 0.8,   # 80% of max connections
            'connection_usage_critical': 0.95, # 95% of max connections
        }

    def get_connection_stats(self, database_alias='default') -> Dict[str, any]:
        """Get current connection pool statistics."""
        try:
            db_conn = connections[database_alias]
            db_config = db_conn.settings_dict.get('OPTIONS', {})
            max_conns = db_config.get('MAX_CONNS', 20)
            min_conns = db_config.get('MIN_CONNS', 2)

            # Query PostgreSQL for current connection statistics
            with db_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        count(*) as active_connections,
                        count(*) FILTER (WHERE state = 'active') as executing_queries,
                        count(*) FILTER (WHERE state = 'idle') as idle_connections,
                        count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                        count(*) FILTER (WHERE backend_type = 'client backend') as client_connections
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                        AND pid != pg_backend_pid();
                """)

                row = cursor.fetchone()
                if row:
                    active_connections = row[0]
                    executing_queries = row[1]
                    idle_connections = row[2]
                    idle_in_transaction = row[3]
                    client_connections = row[4]
                else:
                    active_connections = executing_queries = idle_connections = 0
                    idle_in_transaction = client_connections = 0

            usage_percentage = (active_connections / max_conns) * 100 if max_conns > 0 else 0

            stats = {
                'database_alias': database_alias,
                'active_connections': active_connections,
                'executing_queries': executing_queries,
                'idle_connections': idle_connections,
                'idle_in_transaction': idle_in_transaction,
                'client_connections': client_connections,
                'max_connections': max_conns,
                'min_connections': min_conns,
                'usage_percentage': round(usage_percentage, 1),
                'is_healthy': usage_percentage < 90,
                'timestamp': time.time()
            }

            # Check for alerts
            self.check_connection_alerts(stats)

            return stats

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error getting connection pool stats: {e}",
                exc_info=True,
                extra={'database_alias': database_alias}
            )
            return {'error': str(e)}
        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                f"Configuration error in connection pool stats: {e}",
                exc_info=True,
                extra={'database_alias': database_alias}
            )
            return {'error': str(e)}

    def check_connection_alerts(self, stats: Dict[str, any]) -> None:
        """Check connection statistics and log alerts."""
        usage_pct = stats.get('usage_percentage', 0)

        if usage_pct >= self.alert_thresholds['connection_usage_critical']:
            logger.critical(
                f"CRITICAL: Database connection pool at {usage_pct}% capacity "
                f"({stats['active_connections']}/{stats['max_connections']}). "
                f"Immediate action required to prevent connection exhaustion."
            )
        elif usage_pct >= self.alert_thresholds['connection_usage_warning']:
            logger.warning(
                f"WARNING: Database connection pool at {usage_pct}% capacity "
                f"({stats['active_connections']}/{stats['max_connections']}). "
                f"Consider investigating high connection usage."
            )

        # Alert on excessive idle-in-transaction connections
        idle_in_tx = stats.get('idle_in_transaction', 0)
        if idle_in_tx > 5:
            logger.warning(
                f"WARNING: {idle_in_tx} connections idle in transaction. "
                f"This may indicate transaction leaks or long-running transactions."
            )

    def cache_connection_stats(self, stats: Dict[str, any], timeout=60) -> None:
        """Cache connection statistics for dashboard access."""
        if 'error' not in stats:
            cache_key = f"db_connection_stats:{stats['database_alias']}"
            cache.set(cache_key, stats, timeout)


class DatabasePerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Enhanced middleware for monitoring database performance with:
    - Query count tracking per request
    - N+1 query detection
    - Slow query monitoring
    - Performance regression detection
    - Connection pool monitoring and alerts
    - Integration with pg_stat_statements
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

        # Thread-local storage for request-specific data
        self.local = threading.local()

        # Initialize connection pool monitor
        self.connection_monitor = ConnectionPoolMonitor()

        # Configuration from settings
        self.enabled = getattr(settings, 'ENABLE_DB_PERFORMANCE_MONITORING', settings.DEBUG)
        self.connection_monitoring_enabled = getattr(settings, 'ENABLE_CONNECTION_MONITORING', True)
        self.slow_query_threshold = getattr(settings, 'SLOW_QUERY_THRESHOLD_MS', 100)
        self.excessive_query_threshold = getattr(settings, 'EXCESSIVE_QUERY_THRESHOLD', 20)
        self.n_plus_one_threshold = getattr(settings, 'N_PLUS_ONE_THRESHOLD', 5)

        # Performance baseline tracking
        self.performance_baselines = {}

        # Connection monitoring frequency (monitor every N requests to reduce overhead)
        self.connection_monitor_frequency = 5
        self.request_counter = 0

    def process_request(self, request):
        """Initialize performance monitoring for the request"""
        if not self.enabled:
            return

        # Initialize thread-local storage
        self.local.start_time = time.time()
        self.local.start_queries = len(connection.queries)
        self.local.query_details = []
        self.local.similar_queries = defaultdict(list)
        self.local.request_path = request.path
        self.local.view_name = self._get_view_name(request)

        # Clear query log for this request
        connection.queries_log.clear() if hasattr(connection, 'queries_log') else None

    def process_response(self, request, response):
        """Analyze performance and log findings"""
        if not self.enabled:
            return response

        try:
            self._analyze_request_performance(request, response)

            # Monitor connection pool (with frequency control to reduce overhead)
            if self.connection_monitoring_enabled:
                self.request_counter += 1
                if self.request_counter % self.connection_monitor_frequency == 0:
                    self._monitor_connection_pool()

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error in performance monitoring: {e}",
                exc_info=True,
                extra={'path': getattr(request, 'path', 'unknown')}
            )
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.warning(
                f"Data processing error in performance monitoring: {e}",
                exc_info=True,
                extra={'path': getattr(request, 'path', 'unknown')}
            )
        except SuspiciousOperation as e:
            logger.warning(
                f"Suspicious operation in performance monitoring: {e}",
                extra={'path': getattr(request, 'path', 'unknown')}
            )

        return response

    def _get_view_name(self, request) -> str:
        """Extract view name from request"""
        try:
            resolver_match = resolve(request.path)
            return f"{resolver_match.app_name}.{resolver_match.view_name}" if resolver_match.app_name else resolver_match.view_name
        except Resolver404:
            # Normal case - URL doesn't match any pattern (e.g., 404s, static files)
            return request.path
        except AttributeError as e:
            logger.debug(f"Request object malformed during view name resolution: {e}")
            return request.path
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(
                f"Data error resolving view name for {request.path}: {e}",
                extra={'path': request.path}
            )
            return request.path

    def _analyze_request_performance(self, request, response):
        """Comprehensive performance analysis"""
        end_time = time.time()
        total_time = (end_time - self.local.start_time) * 1000  # Convert to milliseconds

        # Query analysis
        end_queries = len(connection.queries)
        query_count = end_queries - self.local.start_queries

        # Collect query details
        recent_queries = connection.queries[self.local.start_queries:] if hasattr(connection, 'queries') else []

        # Analyze queries
        analysis_results = self._analyze_queries(recent_queries, total_time)

        # Check for performance regressions
        regression_info = self._check_performance_regression(
            self.local.view_name,
            query_count,
            total_time,
            analysis_results
        )

        # Log performance metrics
        self._log_performance_metrics(
            request, response, total_time, query_count, analysis_results, regression_info
        )

        # Store performance baseline
        self._update_performance_baseline(self.local.view_name, query_count, total_time)

    def _analyze_queries(self, queries: List[Dict], total_time: float) -> Dict:
        """Analyze query patterns for optimization opportunities"""
        analysis = {
            'slow_queries': [],
            'similar_queries': defaultdict(list),
            'n_plus_one_detected': False,
            'total_db_time': 0,
            'query_patterns': defaultdict(int),
            'missing_indexes_suspected': []
        }

        for query_info in queries:
            sql = query_info['sql']
            time_ms = float(query_info['time']) * 1000
            analysis['total_db_time'] += time_ms

            # Detect slow queries
            if time_ms > self.slow_query_threshold:
                analysis['slow_queries'].append({
                    'sql': sql[:200] + '...' if len(sql) > 200 else sql,
                    'time_ms': time_ms,
                    'suspected_issues': self._detect_query_issues(sql)
                })

            # Group similar queries for N+1 detection
            normalized_sql = self._normalize_sql(sql)
            analysis['similar_queries'][normalized_sql].append({
                'sql': sql,
                'time_ms': time_ms
            })

            # Categorize query patterns
            analysis['query_patterns'][self._categorize_query(sql)] += 1

        # Detect N+1 queries
        for normalized_sql, similar_queries in analysis['similar_queries'].items():
            if len(similar_queries) >= self.n_plus_one_threshold:
                analysis['n_plus_one_detected'] = True
                logger.warning(
                    f"N+1 query detected: {len(similar_queries)} similar queries for pattern: {normalized_sql[:100]}"
                )

        return analysis

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL for pattern detection"""
        import re
        # Remove parameter values but keep structure
        normalized = re.sub(r'\b\d+\b', '?', sql)
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        normalized = re.sub(r'"[^"]*"', '"?"', normalized)
        return normalized

    def _categorize_query(self, sql: str) -> str:
        """Categorize query type"""
        sql_upper = sql.upper().strip()
        if sql_upper.startswith('SELECT'):
            if 'JOIN' in sql_upper:
                return 'SELECT_WITH_JOIN'
            else:
                return 'SELECT_SIMPLE'
        elif sql_upper.startswith('INSERT'):
            return 'INSERT'
        elif sql_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif sql_upper.startswith('DELETE'):
            return 'DELETE'
        else:
            return 'OTHER'

    def _detect_query_issues(self, sql: str) -> List[str]:
        """Detect potential performance issues in SQL"""
        issues = []
        sql_upper = sql.upper()

        if 'SELECT *' in sql_upper:
            issues.append('SELECT_ALL_COLUMNS')

        if sql_upper.count('LEFT JOIN') > 3:
            issues.append('EXCESSIVE_JOINS')

        if 'ORDER BY' in sql_upper and 'LIMIT' not in sql_upper:
            issues.append('UNBOUNDED_ORDER_BY')

        if 'LIKE' in sql_upper and sql.count('%') > 0:
            issues.append('INEFFICIENT_LIKE_PATTERN')

        if 'IN (' in sql_upper and sql.count(',') > 10:
            issues.append('LARGE_IN_CLAUSE')

        return issues

    def _check_performance_regression(self, view_name: str, query_count: int,
                                    total_time: float, analysis: Dict) -> Dict:
        """Check for performance regressions against baseline"""
        baseline = self.performance_baselines.get(view_name)
        if not baseline:
            return {'is_regression': False}

        regression_info = {
            'is_regression': False,
            'query_count_increase': 0,
            'time_increase': 0,
            'severity': 'none'
        }

        # Check query count regression
        query_increase = ((query_count - baseline['avg_query_count']) / baseline['avg_query_count']) * 100
        time_increase = ((total_time - baseline['avg_time']) / baseline['avg_time']) * 100

        if query_increase > 50 or time_increase > 100:  # 50% more queries or 100% more time
            regression_info['is_regression'] = True
            regression_info['query_count_increase'] = query_increase
            regression_info['time_increase'] = time_increase

            if query_increase > 100 or time_increase > 200:
                regression_info['severity'] = 'critical'
            elif query_increase > 75 or time_increase > 150:
                regression_info['severity'] = 'high'
            else:
                regression_info['severity'] = 'medium'

        return regression_info

    def _update_performance_baseline(self, view_name: str, query_count: int, total_time: float):
        """Update performance baseline with exponential moving average"""
        if view_name not in self.performance_baselines:
            self.performance_baselines[view_name] = {
                'avg_query_count': query_count,
                'avg_time': total_time,
                'sample_count': 1
            }
        else:
            baseline = self.performance_baselines[view_name]
            alpha = 0.1  # Smoothing factor
            baseline['avg_query_count'] = (1 - alpha) * baseline['avg_query_count'] + alpha * query_count
            baseline['avg_time'] = (1 - alpha) * baseline['avg_time'] + alpha * total_time
            baseline['sample_count'] += 1

    def _log_performance_metrics(self, request, response, total_time: float,
                               query_count: int, analysis: Dict, regression_info: Dict):
        """Log comprehensive performance metrics"""

        # Determine log level based on performance
        log_level = logging.INFO
        if analysis['n_plus_one_detected'] or regression_info['is_regression']:
            log_level = logging.WARNING
        if len(analysis['slow_queries']) > 0:
            log_level = logging.WARNING
        if query_count > self.excessive_query_threshold:
            log_level = logging.ERROR

        # Create performance summary
        performance_summary = {
            'view': self.local.view_name,
            'path': self.local.request_path,
            'method': request.method,
            'status_code': response.status_code,
            'total_time_ms': round(total_time, 2),
            'db_time_ms': round(analysis['total_db_time'], 2),
            'db_time_percentage': round((analysis['total_db_time'] / total_time) * 100, 1) if total_time > 0 else 0,
            'query_count': query_count,
            'slow_queries_count': len(analysis['slow_queries']),
            'n_plus_one_detected': analysis['n_plus_one_detected'],
            'query_patterns': dict(analysis['query_patterns'])
        }

        # Add regression info if detected
        if regression_info['is_regression']:
            performance_summary['regression'] = regression_info

        # Log with appropriate level
        logger.log(log_level, f"Database Performance: {performance_summary}")

        # Log slow queries details
        for slow_query in analysis['slow_queries']:
            logger.warning(f"Slow Query Detected: {slow_query}")

        # Cache performance metrics for dashboard/monitoring
        cache_key = f"db_perf:{self.local.view_name}:latest"
        cache.set(cache_key, performance_summary, 300)  # 5 minutes

        # Store in performance history (last 10 requests)
        history_key = f"db_perf:{self.local.view_name}:history"
        history = cache.get(history_key, [])
        history.append(performance_summary)
        if len(history) > 10:
            history = history[-10:]
        cache.set(history_key, history, 3600)  # 1 hour

    def _monitor_connection_pool(self):
        """Monitor connection pool and cache statistics."""
        try:
            # Monitor default database
            conn_stats = self.connection_monitor.get_connection_stats('default')
            if conn_stats and 'error' not in conn_stats:
                self.connection_monitor.cache_connection_stats(conn_stats)

            # Monitor additional databases if configured
            for alias in connections:
                if alias != 'default':
                    try:
                        conn_stats = self.connection_monitor.get_connection_stats(alias)
                        if conn_stats and 'error' not in conn_stats:
                            self.connection_monitor.cache_connection_stats(conn_stats)
                    except DATABASE_EXCEPTIONS as e:
                        logger.debug(
                            f"Database error monitoring connection pool for {alias}: {e}",
                            extra={'database_alias': alias}
                        )
                    except (KeyError, ValueError, TypeError) as e:
                        logger.debug(
                            f"Configuration error monitoring connection pool for {alias}: {e}",
                            extra={'database_alias': alias}
                        )

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error in connection pool monitoring: {e}",
                exc_info=True
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                f"Configuration error in connection pool monitoring: {e}",
                exc_info=True
            )


class QueryOptimizationRecommendations:
    """Generate optimization recommendations based on query patterns"""

    @staticmethod
    def analyze_and_recommend(queries: List[Dict]) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []

        # Analysis patterns
        select_star_count = sum(1 for q in queries if 'SELECT *' in q['sql'].upper())
        if select_star_count > 0:
            recommendations.append(
                f"Consider using specific field selection instead of SELECT * "
                f"({select_star_count} queries found)"
            )

        # Check for missing select_related/prefetch_related
        orm_queries = [q for q in queries if 'django_' in q['sql']]
        if len(orm_queries) > 10:
            recommendations.append(
                "High number of ORM queries detected. Consider using "
                "select_related() or prefetch_related() to reduce N+1 queries"
            )

        # Check for inefficient LIKE patterns
        like_queries = [q for q in queries if 'LIKE' in q['sql'].upper() and q['sql'].count('%') > 0]
        if like_queries:
            recommendations.append(
                f"Consider using full-text search or indexes for LIKE queries "
                f"({len(like_queries)} queries found)"
            )

        return recommendations