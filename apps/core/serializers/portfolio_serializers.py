"""
Portfolio API Serializers
=========================
Pydantic models for portfolio/multi-site overview API responses.

Follows .claude/rules.md:
- Rule #6: Serializer < 100 lines
- Type-safe API contracts for Kotlin/Swift codegen
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AttendanceMetrics(BaseModel):
    """Attendance metrics"""
    compliance_rate: float = Field(..., ge=0.0, le=1.0, description="Compliance rate (0.0-1.0)")
    present: int = Field(..., ge=0, description="Present count")
    absent: int = Field(..., ge=0, description="Absent count")
    total_expected: int = Field(..., ge=0, description="Total expected")
    exceptions: Dict[str, int] = Field(default_factory=dict, description="Exception breakdown")
    trend: List[Dict[str, Any]] = Field(default_factory=list, description="7-day trend data")


class ToursMetrics(BaseModel):
    """Tours/inspections adherence metrics"""
    adherence_rate: float = Field(..., ge=0.0, le=1.0, description="Adherence rate (0.0-1.0)")
    scheduled: int = Field(..., ge=0, description="Total scheduled tours")
    completed_on_time: int = Field(..., ge=0, description="Completed on time")
    completed_late: int = Field(..., ge=0, description="Completed late")
    missed: int = Field(..., ge=0, description="Missed tours")
    deviation_count: int = Field(..., ge=0, description="Tours with path deviations")


class TicketsMetrics(BaseModel):
    """Ticket/helpdesk metrics"""
    open: int = Field(..., ge=0, description="Open tickets")
    by_status: Dict[str, int] = Field(default_factory=dict, description="Count by status")
    by_priority: Dict[str, int] = Field(default_factory=dict, description="Count by priority")
    sla_at_risk: int = Field(..., ge=0, description="Tickets at SLA risk")


class WorkOrdersMetrics(BaseModel):
    """Work order metrics"""
    by_status: Dict[str, int] = Field(default_factory=dict, description="Count by status")
    overdue: int = Field(..., ge=0, description="Overdue work orders")
    avg_cycle_time_hours: Optional[float] = Field(None, description="Average cycle time in hours")


class TopSite(BaseModel):
    """Site health summary for portfolio view"""
    bu_id: int = Field(..., description="Site/BU ID")
    bu_name: Optional[str] = Field(None, description="Site/BU name")
    attendance: float = Field(..., ge=0.0, le=1.0, description="Attendance compliance")
    tours: float = Field(..., ge=0.0, le=1.0, description="Tours adherence")
    open_tickets: int = Field(..., ge=0, description="Open tickets count")
    overdue_wos: int = Field(..., ge=0, description="Overdue work orders")
    rag: str = Field(..., description="Health status", pattern="^(GREEN|AMBER|RED)$")


class PortfolioSummaryResponse(BaseModel):
    """Complete portfolio summary response"""
    attendance: AttendanceMetrics
    tours: ToursMetrics
    tickets: TicketsMetrics
    work_orders: WorkOrdersMetrics
    top_sites: List[TopSite]
    scope: Dict[str, Any] = Field(..., description="Applied scope")
    generated_at: str = Field(..., description="ISO timestamp")
    cached: bool = Field(default=False, description="Whether data was from cache")


class SiteHealthScore(BaseModel):
    """Detailed health score for single site"""
    bu_id: int
    bu_name: str
    overall_rag: str = Field(..., pattern="^(GREEN|AMBER|RED)$")
    attendance_compliance: float = Field(..., ge=0.0, le=1.0)
    tours_adherence: float = Field(..., ge=0.0, le=1.0)
    open_tickets: int = Field(..., ge=0)
    critical_alerts: int = Field(..., ge=0)
    overdue_tasks: int = Field(..., ge=0)
    overdue_wos: int = Field(..., ge=0)


__all__ = [
    "AttendanceMetrics",
    "ToursMetrics",
    "TicketsMetrics",
    "WorkOrdersMetrics",
    "TopSite",
    "PortfolioSummaryResponse",
    "SiteHealthScore",
]
