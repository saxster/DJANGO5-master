"""
NOC WebSocket Consumers Package

Real-time communication consumers for NOC dashboard and monitoring.
"""

from .noc_dashboard_consumer import NOCDashboardConsumer
from .presence_monitor_consumer import PresenceMonitorConsumer

__all__ = [
    'NOCDashboardConsumer',
    'PresenceMonitorConsumer',
]
