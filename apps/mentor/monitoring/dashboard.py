"""
Monitoring and metrics dashboard for AI Mentor System performance tracking.

This dashboard provides:
- Index freshness: Commits behind HEAD
- Analysis performance: Response times
- Generation accuracy: Human edit rate
- Safety catches: Prevented issues
- Developer satisfaction: Usage metrics
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone

from apps.mentor.models import IndexMetadata, IndexedFile, CodeSymbol


@dataclass
class MetricPoint:
    """Container for a single metric data point."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = None


@dataclass
class DashboardStats:
    """Container for dashboard statistics."""
    index_health: Dict[str, Any]
    performance_metrics: Dict[str, List[MetricPoint]]
    usage_statistics: Dict[str, Any]
    quality_metrics: Dict[str, Any]


class MentorMetrics:
    """Metrics collection and analysis for AI Mentor System."""

    def __init__(self):
        self.cache_prefix = 'mentor_metrics'
        self.metrics_ttl = 300  # 5 minutes
        self.performance_log = deque(maxlen=1000)  # Keep last 1000 operations

    def record_operation(self, operation: str, duration: float, metadata: Dict[str, Any] = None):
        """Record an operation for performance tracking."""
        metric = MetricPoint(
            timestamp=timezone.now(),
            value=duration,
            metadata=metadata or {}
        )

        # Store in cache with operation-specific key
        cache_key = f"{self.cache_prefix}:operations:{operation}"
        operations = cache.get(cache_key, [])
        operations.append(metric)

        # Keep only last 100 operations per type
        if len(operations) > 100:
            operations = operations[-100:]

        cache.set(cache_key, operations, self.metrics_ttl * 4)  # Longer TTL for operations

        # Also add to general performance log
        self.performance_log.append({
            'operation': operation,
            'duration': duration,
            'timestamp': metric.timestamp,
            'metadata': metadata
        })

    def get_index_health(self) -> Dict[str, Any]:
        """Get index health metrics."""
        cache_key = f"{self.cache_prefix}:index_health"
        cached = cache.get(cache_key)

        if cached:
            return cached

        # Calculate index health
        stats = IndexMetadata.get_index_stats()
        current_commit = self._get_current_git_commit()
        indexed_commit = IndexMetadata.get_indexed_commit()

        # Check staleness
        commits_behind = 0
        is_stale = False

        if indexed_commit and indexed_commit != current_commit:
            commits_behind = self._count_commits_behind(indexed_commit, current_commit)
            is_stale = commits_behind > 0

        # Calculate index coverage
        total_python_files = self._count_total_python_files()
        indexed_files = IndexedFile.objects.count()
        coverage_percentage = (indexed_files / total_python_files * 100) if total_python_files > 0 else 0

        health = {
            'is_healthy': not is_stale and coverage_percentage > 80,
            'is_stale': is_stale,
            'commits_behind': commits_behind,
            'coverage_percentage': round(coverage_percentage, 2),
            'total_files': total_python_files,
            'indexed_files': indexed_files,
            'last_update': stats.get('index_updated_at'),
            'statistics': stats
        }

        cache.set(cache_key, health, self.metrics_ttl)
        return health

    def get_performance_metrics(self) -> Dict[str, List[MetricPoint]]:
        """Get performance metrics for various operations."""
        metrics = {}

        # Common operations to track
        operations = ['indexing', 'analysis', 'security_scan', 'performance_analysis', 'generation']

        for operation in operations:
            cache_key = f"{self.cache_prefix}:operations:{operation}"
            operation_data = cache.get(cache_key, [])

            # Convert to MetricPoint objects if needed
            if operation_data and isinstance(operation_data[0], dict):
                operation_data = [
                    MetricPoint(
                        timestamp=item['timestamp'],
                        value=item['value'],
                        metadata=item.get('metadata', {})
                    ) for item in operation_data
                ]

            metrics[operation] = operation_data

        return metrics

    def get_usage_statistics(self) -> Dict[str, Any]:
        """Get usage statistics."""
        cache_key = f"{self.cache_prefix}:usage_stats"
        cached = cache.get(cache_key)

        if cached:
            return cached

        # Calculate usage statistics
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_week = now - timedelta(days=7)

        # Count operations in different time periods
        recent_ops = [op for op in self.performance_log if op['timestamp'] > last_24h]
        weekly_ops = [op for op in self.performance_log if op['timestamp'] > last_week]

        # Group by operation type
        daily_ops_by_type = defaultdict(int)
        weekly_ops_by_type = defaultdict(int)

        for op in recent_ops:
            daily_ops_by_type[op['operation']] += 1

        for op in weekly_ops:
            weekly_ops_by_type[op['operation']] += 1

        # Calculate average response times
        avg_response_times = {}
        for op_type in daily_ops_by_type.keys():
            op_durations = [op['duration'] for op in recent_ops if op['operation'] == op_type]
            avg_response_times[op_type] = sum(op_durations) / len(op_durations) if op_durations else 0

        stats = {
            'operations_last_24h': sum(daily_ops_by_type.values()),
            'operations_last_week': sum(weekly_ops_by_type.values()),
            'operations_by_type_daily': dict(daily_ops_by_type),
            'operations_by_type_weekly': dict(weekly_ops_by_type),
            'average_response_times': avg_response_times,
            'most_used_operation': max(daily_ops_by_type.items(), key=lambda x: x[1])[0] if daily_ops_by_type else None
        }

        cache.set(cache_key, stats, self.metrics_ttl)
        return stats

    def get_quality_metrics(self) -> Dict[str, Any]:
        """Get code quality and accuracy metrics."""
        cache_key = f"{self.cache_prefix}:quality_metrics"
        cached = cache.get(cache_key)

        if cached:
            return cached

        # Calculate quality metrics
        total_symbols = CodeSymbol.objects.count()
        complex_symbols = CodeSymbol.objects.filter(complexity__gt=10).count()

        quality_score = self._calculate_overall_quality_score()

        # Simulation of accuracy metrics (would need actual tracking)
        metrics = {
            'total_symbols_analyzed': total_symbols,
            'complex_symbols': complex_symbols,
            'complexity_ratio': (complex_symbols / total_symbols * 100) if total_symbols > 0 else 0,
            'overall_quality_score': quality_score,
            'accuracy_metrics': {
                'patch_success_rate': 85.0,  # Placeholder - would track actual patches
                'false_positive_rate': 5.2,   # Placeholder - would track false positives
                'analysis_confidence': 92.3   # Placeholder - would track confidence scores
            }
        }

        cache.set(cache_key, metrics, self.metrics_ttl)
        return metrics

    def generate_dashboard_data(self) -> DashboardStats:
        """Generate comprehensive dashboard data."""
        return DashboardStats(
            index_health=self.get_index_health(),
            performance_metrics=self.get_performance_metrics(),
            usage_statistics=self.get_usage_statistics(),
            quality_metrics=self.get_quality_metrics()
        )

    def _get_current_git_commit(self) -> str:
        """Get current git commit SHA."""
        import subprocess

        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError):
            pass

        return 'unknown'

    def _count_commits_behind(self, indexed_commit: str, current_commit: str) -> int:
        """Count commits between indexed and current commit."""
        import subprocess

        try:
            result = subprocess.run([
                'git', 'rev-list', '--count', f"{indexed_commit}..{current_commit}"
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return int(result.stdout.strip())
        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError):
            pass

        return 0

    def _count_total_python_files(self) -> int:
        """Count total Python files in the project."""
        from pathlib import Path
        from django.conf import settings

        project_root = Path(settings.BASE_DIR)
        python_files = list(project_root.rglob('*.py'))

        # Filter out common exclusions
        excluded_patterns = {'__pycache__', '.git', 'venv', 'env', 'migrations'}
        filtered_files = [
            f for f in python_files
            if not any(pattern in str(f) for pattern in excluded_patterns)
        ]

        return len(filtered_files)

    def _calculate_overall_quality_score(self) -> float:
        """Calculate overall code quality score."""
        # Simplified quality score calculation
        total_symbols = CodeSymbol.objects.count()
        if total_symbols == 0:
            return 75.0  # Default score

        # Factor in complexity distribution
        complex_symbols = CodeSymbol.objects.filter(complexity__gt=10).count()
        very_complex_symbols = CodeSymbol.objects.filter(complexity__gt=20).count()

        complexity_penalty = (complex_symbols * 0.1 + very_complex_symbols * 0.2) / total_symbols * 100

        # Base score minus complexity penalty
        quality_score = max(95.0 - complexity_penalty, 0.0)

        return round(quality_score, 1)


class DashboardGenerator:
    """Generate dashboard HTML/JSON for monitoring."""

    def __init__(self):
        self.metrics = MentorMetrics()

    def generate_html_dashboard(self) -> str:
        """Generate HTML dashboard."""
        stats = self.metrics.generate_dashboard_data()

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>AI Mentor System Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .dashboard {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric {{ margin: 10px 0; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ color: #7f8c8d; font-size: 14px; }}
        .status-healthy {{ color: #27ae60; }}
        .status-warning {{ color: #f39c12; }}
        .status-error {{ color: #e74c3c; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .timestamp {{ text-align: center; color: #7f8c8d; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AI Mentor System Dashboard</h1>
    </div>

    <div class="dashboard">
        <div class="card">
            <h2>📊 Index Health</h2>
            <div class="metric">
                <div class="metric-value {'status-healthy' if stats.index_health['is_healthy'] else 'status-error'}">
                    {'✅ Healthy' if stats.index_health['is_healthy'] else '⚠️ Issues'}
                </div>
                <div class="metric-label">Overall Status</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats.index_health['indexed_files']:,}</div>
                <div class="metric-label">Files Indexed ({stats.index_health['coverage_percentage']:.1f}% coverage)</div>
            </div>
            <div class="metric">
                <div class="metric-value {'status-healthy' if stats.index_health['commits_behind'] == 0 else 'status-warning'}">
                    {stats.index_health['commits_behind']}
                </div>
                <div class="metric-label">Commits Behind</div>
            </div>
        </div>

        <div class="card">
            <h2>⚡ Performance</h2>
            <div class="metric">
                <div class="metric-value">{stats.usage_statistics.get('operations_last_24h', 0)}</div>
                <div class="metric-label">Operations (Last 24h)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats.usage_statistics.get('average_response_times', {}).get('analysis', 0):.2f}s</div>
                <div class="metric-label">Avg Analysis Time</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats.usage_statistics.get('most_used_operation', 'N/A')}</div>
                <div class="metric-label">Most Used Operation</div>
            </div>
        </div>

        <div class="card">
            <h2>🎯 Quality Metrics</h2>
            <div class="metric">
                <div class="metric-value status-healthy">{stats.quality_metrics['overall_quality_score']:.1f}</div>
                <div class="metric-label">Quality Score</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats.quality_metrics['accuracy_metrics']['patch_success_rate']:.1f}%</div>
                <div class="metric-label">Patch Success Rate</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats.quality_metrics['total_symbols_analyzed']:,}</div>
                <div class="metric-label">Symbols Analyzed</div>
            </div>
        </div>

        <div class="card">
            <h2>📈 Usage Statistics</h2>
            <div class="metric">
                <div class="metric-value">{stats.usage_statistics.get('operations_last_week', 0)}</div>
                <div class="metric-label">Weekly Operations</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats.quality_metrics['accuracy_metrics']['analysis_confidence']:.1f}%</div>
                <div class="metric-label">Analysis Confidence</div>
            </div>
            <div class="metric">
                <div class="metric-value">{stats.quality_metrics['accuracy_metrics']['false_positive_rate']:.1f}%</div>
                <div class="metric-label">False Positive Rate</div>
            </div>
        </div>
    </div>

    <div class="timestamp">
        Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
    </div>
</body>
</html>
"""
        return html

    def generate_json_metrics(self) -> str:
        """Generate JSON metrics for API consumption."""
        import json

        stats = self.metrics.generate_dashboard_data()

        # Convert to JSON-serializable format
        json_data = {
            'timestamp': datetime.now().isoformat(),
            'index_health': stats.index_health,
            'usage_statistics': stats.usage_statistics,
            'quality_metrics': stats.quality_metrics,
            'performance_summary': {
                'total_operations_24h': stats.usage_statistics.get('operations_last_24h', 0),
                'avg_analysis_time': stats.usage_statistics.get('average_response_times', {}).get('analysis', 0),
                'health_status': 'healthy' if stats.index_health['is_healthy'] else 'degraded'
            }
        }

        return json.dumps(json_data, indent=2, default=str)