"""
NOC Celery Tasks.

Background tasks for NOC operations including:
- Baseline threshold updates (dynamic anomaly detection tuning)
- Metric downsampling (multi-resolution time-series storage)
- Alert processing and correlation
- Incident lifecycle management
- Automated playbook execution (SOAR-lite)

@ontology(
    domain="noc",
    purpose="Celery background tasks for NOC operations and anomaly detection",
    tasks=[
        "UpdateBaselineThresholdsTask - Dynamic threshold tuning based on FP rates",
        "DownsampleMetricsHourlyTask - Aggregate 5-min to 1-hour metrics",
        "DownsampleMetricsDailyTask - Aggregate 1-hour to 1-day metrics",
        "ExecutePlaybookTask - Automated remediation playbook execution"
    ],
    criticality="high",
    tags=["celery", "noc", "background-tasks", "anomaly-detection", "metrics", "soar"]
)
"""

from .baseline_tasks import UpdateBaselineThresholdsTask
from .metric_downsampling_tasks import DownsampleMetricsHourlyTask, DownsampleMetricsDailyTask
from .playbook_tasks import ExecutePlaybookTask

__all__ = [
    'UpdateBaselineThresholdsTask',
    'DownsampleMetricsHourlyTask',
    'DownsampleMetricsDailyTask',
    'ExecutePlaybookTask',
]
