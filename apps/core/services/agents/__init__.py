"""
Dashboard Agent Services

AI-powered agents for dashboard intelligence:
- TaskBot: Task management and prioritization
- TourBot: Route optimization and SOP compliance
- AlertBot: System health and data validation
- AssetBot: Asset lifecycle management
- AttendanceBot: Attendance and staffing optimization

All agents use Google Gemini as primary LLM with Claude fallback.
"""

from .base_agent_service import BaseAgentService
from .task_agent_service import TaskAgentService
from .tour_agent_service import TourAgentService
from .alert_agent_service import AlertAgentService
from .asset_agent_service import AssetAgentService
from .attendance_agent_service import AttendanceAgentService
from .route_agent_service import RouteAgentService
from .incident_agent_service import IncidentAgentService

__all__ = [
    'BaseAgentService',
    'TaskAgentService',
    'TourAgentService',
    'AlertAgentService',
    'AssetAgentService',
    'AttendanceAgentService',
    'RouteAgentService',
    'IncidentAgentService',
]
