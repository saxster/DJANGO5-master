from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional, Dict, Any


class ThreatEventSchema(BaseModel):
    """Schema for threat event data."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    description: str
    category: str
    severity: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    
    location_name: Optional[str] = None
    country_code: Optional[str] = None
    impact_radius_km: Optional[float] = None
    
    event_start_time: datetime
    event_end_time: Optional[datetime] = None
    forecast_window_hours: Optional[int] = None
    
    keywords: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    
    created_at: datetime


class IntelligenceAlertSchema(BaseModel):
    """Schema for intelligence alert delivered to tenant."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    threat_event: ThreatEventSchema
    
    severity: str
    urgency_level: str
    distance_km: float
    
    delivery_status: str
    delivery_channels: List[str] = Field(default_factory=list)
    delivered_at: Optional[datetime] = None
    
    tenant_response: str
    response_timestamp: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    
    work_order_created: bool
    
    created_at: datetime


class AlertListResponseSchema(BaseModel):
    """Response for list of alerts."""
    
    alerts: List[IntelligenceAlertSchema]
    total_count: int
    unacknowledged_count: int
    critical_count: int


class AlertFeedbackSchema(BaseModel):
    """Schema for submitting feedback on alerts."""
    
    response_type: str = Field(
        ...,
        description="One of: ACTIONABLE, NOTED, FALSE_POSITIVE, MISSED, TOO_SENSITIVE"
    )
    notes: Optional[str] = None


class TenantProfileSchema(BaseModel):
    """Schema for tenant intelligence profile configuration."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    threat_categories: List[str]
    minimum_severity: str
    minimum_confidence: float
    buffer_radius_km: float
    
    alert_urgency_critical: str
    alert_urgency_high: str
    alert_urgency_medium: str
    alert_urgency_low: str
    
    enable_websocket: bool
    enable_sms: bool
    enable_email: bool
    enable_work_order_creation: bool
    
    is_active: bool


class TenantProfileUpdateSchema(BaseModel):
    """Schema for updating tenant profile."""
    
    threat_categories: Optional[List[str]] = None
    minimum_severity: Optional[str] = None
    minimum_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    buffer_radius_km: Optional[float] = Field(None, gt=0)
    
    alert_urgency_critical: Optional[str] = None
    alert_urgency_high: Optional[str] = None
    alert_urgency_medium: Optional[str] = None
    alert_urgency_low: Optional[str] = None
    
    enable_websocket: Optional[bool] = None
    enable_sms: Optional[bool] = None
    enable_email: Optional[bool] = None
    enable_work_order_creation: Optional[bool] = None


class LearningMetricsSchema(BaseModel):
    """Schema for ML learning metrics per tenant."""
    model_config = ConfigDict(from_attributes=True)
    
    total_alerts_received: int
    total_actionable: int
    total_false_positives: int
    actionable_rate: float
    false_positive_rate: float
    
    average_response_time_minutes: float
    effective_monitoring_radius_km: Optional[float] = None
    
    last_retrained_at: Optional[datetime] = None
    model_accuracy_score: Optional[float] = None


class CollectivePatternSchema(BaseModel):
    """Schema for collective intelligence patterns."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    pattern_type: str
    threat_category: str
    pattern_description: str
    
    sample_size: int
    confidence_score: float
    
    recommended_actions: List[str]
    effectiveness_metrics: Dict[str, Any]
    
    helpfulness_ratio: float
    times_applied: int
