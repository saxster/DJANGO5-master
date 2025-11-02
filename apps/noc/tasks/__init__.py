"""
NOC Celery Tasks.

Background tasks for NOC operations including:
- Baseline threshold updates (dynamic anomaly detection tuning)
- Alert processing and correlation
- Incident lifecycle management

@ontology(
    domain="noc",
    purpose="Celery background tasks for NOC operations and anomaly detection",
    tasks=[
        "UpdateBaselineThresholdsTask - Dynamic threshold tuning based on FP rates"
    ],
    criticality="high",
    tags=["celery", "noc", "background-tasks", "anomaly-detection"]
)
"""

from .baseline_tasks import UpdateBaselineThresholdsTask

__all__ = ['UpdateBaselineThresholdsTask']
