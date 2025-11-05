"""
Enhanced Performance Monitoring System with Automatic Slow Query Detection

This module provides comprehensive performance monitoring including:
1. Real-time slow query detection and alerting
2. Performance regression detection
3. Resource usage monitoring
4. Automatic performance alerts
5. Query optimization suggestions

Key features:
- Automatic detection of queries >100ms
- Performance regression alerts (30% slower than baseline)
- Memory usage monitoring
- Cache hit rate tracking
- Intelligent alerting with rate limiting
"""

import time
import json
import logging
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict, deque
from threading import Lock, Timer
from dataclasses import dataclass, field

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.template.loader import render_to_string

from apps.core.utils_new.performance import NPlusOneDetector

logger = logging.getLogger('performance_monitor')


@dataclass
class PerformanceMetric:
    """Represents a performance metric data point"""
    timestamp: datetime
    metric_type: str
    value: float
    tags: Dict[str, Any] = field(default_factory=dict)
    details: Optional[Dict[str, Any]] = None


@dataclass
class SlowQueryAlert:
    """Represents a slow query alert"""
    timestamp: datetime
    sql: str
    duration: float
    stack_trace: Optional[List[str]]
    request_path: Optional[str]
    user_id: Optional[int]
    optimization_suggestions: List[str] = field(default_factory=list)


@dataclass
class PerformanceBaseline:
    """Stores performance baselines for regression detection"""
    endpoint: str
    avg_response_time: float
    p95_response_time: float
    avg_query_count: int
    avg_query_time: float
    last_updated: datetime
    sample_count: int = 0


class PerformanceMonitor:
    """Enhanced performance monitoring with real-time alerting"""
    
    def __init__(self):
        self.metrics_history = deque(maxlen=10000)  # Keep last 10k metrics
        self.slow_queries = deque(maxlen=1000)      # Keep last 1k slow queries
        self.baselines = {}                         # Performance baselines
        self.alert_state = defaultdict(int)         # Alert rate limiting
        self.lock = Lock()
        
        # Configuration
        self.config = {
            'slow_query_threshold': getattr(settings, 'SLOW_QUERY_THRESHOLD', 0.1),  # 100ms
            'critical_query_threshold': getattr(settings, 'CRITICAL_QUERY_THRESHOLD', 1.0),  # 1s
            'response_time_threshold': getattr(settings, 'RESPONSE_TIME_THRESHOLD', 2.0),  # 2s
            'memory_threshold': getattr(settings, 'MEMORY_THRESHOLD', 80),  # 80%
            'regression_threshold': getattr(settings, 'REGRESSION_THRESHOLD', 0.3),  # 30% slower
            'alert_cooldown': 300,  # 5 minutes between similar alerts
            'baseline_sample_size': 100,  # Samples to calculate baseline
        }
        
        # N+1 query detector
        self.n_plus_one_detector = NPlusOneDetector(threshold=5)
        
        # Start background monitoring
        self._start_background_monitoring()
    
    def record_metric(self, metric_type: str, value: float, tags: Dict[str, Any] = None, 
                     details: Dict[str, Any] = None):
        """Record a performance metric"""
        metric = PerformanceMetric(
            timestamp=timezone.now(),
            metric_type=metric_type,
            value=value,
            tags=tags or {},
            details=details
        )
        
        with self.lock:
            self.metrics_history.append(metric)
        
        # Check for alerts
        self._check_metric_alert(metric)
    
    def record_slow_query(self, sql: str, duration: float, request_path: str = None,
                         user_id: int = None, stack_trace: List[str] = None):
        """Record a slow query for analysis"""
        alert = SlowQueryAlert(
            timestamp=timezone.now(),
            sql=sql,
            duration=duration,
            request_path=request_path,
            user_id=user_id,
            stack_trace=stack_trace,
            optimization_suggestions=self._get_query_suggestions(sql)
        )
        
        with self.lock:
            self.slow_queries.append(alert)
        
        # Trigger alert if critical
        if duration >= self.config['critical_query_threshold']:
            self._send_critical_query_alert(alert)
        
        logger.warning(
            f"Slow query detected: {duration:.3f}s - {sql[:100]}..."
            + (f" (Path: {request_path})" if request_path else "")
        )
    
    def update_baseline(self, endpoint: str, response_time: float, query_count: int, 
                       avg_query_time: float):
        """Update performance baseline for an endpoint"""
        with self.lock:
            if endpoint not in self.baselines:
                self.baselines[endpoint] = PerformanceBaseline(
                    endpoint=endpoint,
                    avg_response_time=response_time,
                    p95_response_time=response_time,
                    avg_query_count=query_count,
                    avg_query_time=avg_query_time,
                    last_updated=timezone.now(),
                    sample_count=1
                )
            else:
                baseline = self.baselines[endpoint]
                baseline.sample_count += 1
                
                # Update rolling averages
                weight = 1.0 / min(baseline.sample_count, self.config['baseline_sample_size'])
                baseline.avg_response_time = (
                    baseline.avg_response_time * (1 - weight) + response_time * weight
                )
                baseline.avg_query_count = int(
                    baseline.avg_query_count * (1 - weight) + query_count * weight
                )
                baseline.avg_query_time = (
                    baseline.avg_query_time * (1 - weight) + avg_query_time * weight
                )
                baseline.last_updated = timezone.now()
    
    def check_performance_regression(self, endpoint: str, response_time: float, 
                                   query_count: int, avg_query_time: float) -> bool:
        """Check if current performance shows regression from baseline"""
        if endpoint not in self.baselines:
            return False
        
        baseline = self.baselines[endpoint]
        threshold = self.config['regression_threshold']
        
        # Check various regression indicators
        response_regression = (
            response_time > baseline.avg_response_time * (1 + threshold)
        )
        query_count_regression = (
            query_count > baseline.avg_query_count * (1 + threshold)
        )
        query_time_regression = (
            avg_query_time > baseline.avg_query_time * (1 + threshold)
        )
        
        if any([response_regression, query_count_regression, query_time_regression]):
            self._send_regression_alert(endpoint, baseline, {
                'current_response_time': response_time,
                'current_query_count': query_count,
                'current_avg_query_time': avg_query_time,
            })
            return True
        
        return False
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for the last N hours"""
        cutoff = timezone.now() - timedelta(hours=hours)
        
        with self.lock:
            recent_metrics = [
                m for m in self.metrics_history 
                if m.timestamp >= cutoff
            ]
            recent_slow_queries = [
                q for q in self.slow_queries 
                if q.timestamp >= cutoff
            ]
        
        if not recent_metrics:
            return {'error': 'No metrics available'}
        
        # Aggregate metrics by type
        metrics_by_type = defaultdict(list)
        for metric in recent_metrics:
            metrics_by_type[metric.metric_type].append(metric.value)
        
        summary = {
            'period_hours': hours,
            'total_requests': len([m for m in recent_metrics if m.metric_type == 'response_time']),
            'slow_queries_count': len(recent_slow_queries),
            'metrics': {}
        }
        
        # Calculate statistics for each metric type
        for metric_type, values in metrics_by_type.items():
            if values:
                summary['metrics'][metric_type] = {
                    'count': len(values),
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'p95': self._percentile(values, 95),
                    'p99': self._percentile(values, 99)
                }
        
        # Top slow queries
        if recent_slow_queries:
            summary['top_slow_queries'] = [
                {
                    'sql': q.sql[:200] + ('...' if len(q.sql) > 200 else ''),
                    'duration': q.duration,
                    'timestamp': q.timestamp.isoformat(),
                    'request_path': q.request_path
                }
                for q in sorted(recent_slow_queries, key=lambda x: x.duration, reverse=True)[:10]
            ]
        
        return summary
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system resource metrics"""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Database connections
            db_queries_count = len(connection.queries)
            
            return {
                'timestamp': timezone.now().isoformat(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'memory_total_gb': memory.total / (1024**3),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024**3),
                'db_queries_count': db_queries_count,
                'active_connections': len(connection.queries_log) if hasattr(connection, 'queries_log') else 0
            }
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {'error': str(e)}
    
    def _check_metric_alert(self, metric: PerformanceMetric):
        """Check if a metric should trigger an alert"""
        alert_key = f"{metric.metric_type}_{metric.tags.get('endpoint', 'global')}"
        
        # Rate limiting
        if self._should_suppress_alert(alert_key):
            return
        
        # Check thresholds
        should_alert = False
        alert_level = 'warning'
        
        if metric.metric_type == 'response_time':
            if metric.value > self.config['response_time_threshold']:
                should_alert = True
                alert_level = 'critical' if metric.value > self.config['response_time_threshold'] * 2 else 'warning'
        
        elif metric.metric_type == 'memory_percent':
            if metric.value > self.config['memory_threshold']:
                should_alert = True
                alert_level = 'critical' if metric.value > 90 else 'warning'
        
        elif metric.metric_type == 'error_rate':
            if metric.value > 0.1:  # 10% error rate
                should_alert = True
                alert_level = 'critical'
        
        if should_alert:
            self._send_metric_alert(metric, alert_level)
            self.alert_state[alert_key] = int(time.time())
    
    def _should_suppress_alert(self, alert_key: str) -> bool:
        """Check if alert should be suppressed due to rate limiting"""
        last_alert = self.alert_state.get(alert_key, 0)
        return (time.time() - last_alert) < self.config['alert_cooldown']
    
    def _send_critical_query_alert(self, alert: SlowQueryAlert):
        """Send alert for critical slow queries"""
        if self._should_suppress_alert(f"critical_query_{alert.request_path or 'unknown'}"):
            return
        
        subject = f"[CRITICAL] Slow Query Alert - {alert.duration:.2f}s"
        
        context = {
            'alert': alert,
            'threshold': self.config['critical_query_threshold'],
            'suggestions': alert.optimization_suggestions
        }
        
        try:
            message = render_to_string('monitoring/slow_query_alert.txt', context)
            self._send_alert_email(subject, message, level='critical')
        except Exception as e:
            logger.error(f"Failed to send critical query alert: {e}")
    
    def _send_regression_alert(self, endpoint: str, baseline: PerformanceBaseline, 
                              current_metrics: Dict[str, float]):
        """Send performance regression alert"""
        if self._should_suppress_alert(f"regression_{endpoint}"):
            return
        
        subject = f"[WARNING] Performance Regression Detected - {endpoint}"
        
        context = {
            'endpoint': endpoint,
            'baseline': baseline,
            'current': current_metrics,
            'regression_threshold': self.config['regression_threshold'] * 100
        }
        
        try:
            message = render_to_string('monitoring/regression_alert.txt', context)
            self._send_alert_email(subject, message, level='warning')
        except Exception as e:
            logger.error(f"Failed to send regression alert: {e}")
    
    def _send_metric_alert(self, metric: PerformanceMetric, level: str):
        """Send generic metric alert"""
        subject = f"[{level.upper()}] Performance Alert - {metric.metric_type}"
        
        message = f"""
Performance Alert Triggered

Metric: {metric.metric_type}
Value: {metric.value}
Timestamp: {metric.timestamp}
Tags: {metric.tags}
Level: {level}

Please investigate the performance issue.
"""
        
        try:
            self._send_alert_email(subject, message, level=level)
        except Exception as e:
            logger.error(f"Failed to send metric alert: {e}")
    
    def _send_alert_email(self, subject: str, message: str, level: str = 'warning'):
        """Send alert email to administrators"""
        if not getattr(settings, 'ADMINS', None):
            return
        
        recipients = [admin[1] for admin in settings.ADMINS]
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False
            )
            logger.info(f"Sent {level} alert email: {subject}")
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")
    
    def _get_query_suggestions(self, sql: str) -> List[str]:
        """Get optimization suggestions for a slow query"""
        suggestions = []
        sql_lower = sql.lower()
        
        if 'select' in sql_lower and 'join' not in sql_lower and 'where' in sql_lower:
            suggestions.append("Consider adding appropriate indexes for WHERE conditions")
        
        if 'order by' in sql_lower and 'limit' not in sql_lower:
            suggestions.append("Consider adding LIMIT to ORDER BY queries")
        
        if 'select *' in sql_lower:
            suggestions.append("Avoid SELECT * - specify only needed columns")
        
        if sql_lower.count('select') > 3:
            suggestions.append("Multiple subqueries detected - consider query optimization")
        
        if 'in (select' in sql_lower:
            suggestions.append("Consider using JOIN instead of IN with subquery")
        
        return suggestions
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * percentile / 100
        f = int(k)
        c = k - f
        
        if f == len(sorted_values) - 1:
            return sorted_values[f]
        return sorted_values[f] * (1 - c) + sorted_values[f + 1] * c
    
    def _start_background_monitoring(self):
        """Start background system monitoring"""
        def monitor_system():
            try:
                metrics = self.get_system_metrics()
                if 'error' not in metrics:
                    self.record_metric('cpu_percent', metrics['cpu_percent'])
                    self.record_metric('memory_percent', metrics['memory_percent'])
                    self.record_metric('disk_percent', metrics['disk_percent'])
                    self.record_metric('db_queries_count', metrics['db_queries_count'])
            except Exception as e:
                logger.error(f"Error in background monitoring: {e}")
            
            # Schedule next run
            Timer(60, monitor_system).start()  # Every minute
        
        # Start the monitoring
        Timer(60, monitor_system).start()


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """Middleware for automatic performance monitoring"""
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.monitor = PerformanceMonitor()
    
    def process_request(self, request):
        """Process request start"""
        request._monitoring_start_time = time.time()
        request._monitoring_start_queries = len(connection.queries)
        
        # Start N+1 detection if debug mode
        if settings.DEBUG:
            self.monitor.n_plus_one_detector.start_monitoring()
    
    def process_response(self, request, response):
        """Process request completion"""
        if not hasattr(request, '_monitoring_start_time'):
            return response
        
        # Calculate metrics
        end_time = time.time()
        response_time = end_time - request._monitoring_start_time
        
        query_count = len(connection.queries) - request._monitoring_start_queries
        
        # Calculate average query time
        avg_query_time = 0
        if query_count > 0:
            total_query_time = sum(
                float(q['time']) for q in connection.queries[-query_count:]
            )
            avg_query_time = total_query_time / query_count
        
        # Record metrics
        endpoint = f"{request.method} {request.path}"
        tags = {
            'endpoint': endpoint,
            'method': request.method,
            'status_code': response.status_code,
            'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None
        }
        
        self.monitor.record_metric('response_time', response_time, tags)
        self.monitor.record_metric('query_count', query_count, tags)
        
        if query_count > 0:
            self.monitor.record_metric('avg_query_time', avg_query_time, tags)
        
        # Check for slow queries
        for query in connection.queries[-query_count:]:
            query_time = float(query['time'])
            if query_time >= self.monitor.config['slow_query_threshold']:
                self.monitor.record_slow_query(
                    sql=query['sql'],
                    duration=query_time,
                    request_path=request.path,
                    user_id=tags['user_id']
                )
        
        # Update baseline and check for regressions
        self.monitor.update_baseline(endpoint, response_time, query_count, avg_query_time)
        self.monitor.check_performance_regression(endpoint, response_time, query_count, avg_query_time)
        
        # Check for N+1 queries if in debug mode
        if settings.DEBUG and hasattr(self.monitor, 'n_plus_one_detector'):
            try:
                analysis = self.monitor.n_plus_one_detector.stop_monitoring()
                if analysis.get('n_plus_one_issues'):
                    logger.warning(f"N+1 queries detected in {endpoint}: {len(analysis['n_plus_one_issues'])} issues")
            except Exception as e:
                logger.error(f"Error in N+1 detection: {e}")
        
        return response


# Global monitor instance
performance_monitor = PerformanceMonitor()

# Convenience functions
def record_metric(metric_type: str, value: float, tags: Dict[str, Any] = None):
    """Record a performance metric"""
    performance_monitor.record_metric(metric_type, value, tags)

def get_performance_summary(hours: int = 24) -> Dict[str, Any]:
    """Get performance summary"""
    return performance_monitor.get_performance_summary(hours)

def get_system_metrics() -> Dict[str, Any]:
    """Get current system metrics"""
    return performance_monitor.get_system_metrics()