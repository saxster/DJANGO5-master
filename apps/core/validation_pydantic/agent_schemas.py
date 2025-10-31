"""
Pydantic Validation Schemas for Agent Recommendations

Type-safe validation for dashboard agent recommendations.
Ensures data integrity before database persistence.

Following CLAUDE.md:
- Rule #7: <150 lines
- Type-safe API contracts
- Integration with existing Pydantic infrastructure

Dashboard Agent Intelligence - Phase 1.2
"""

from pydantic import BaseModel, Field, validator, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SeverityLevel(str, Enum):
    """Severity levels for recommendations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(str, Enum):
    """Action types for recommendation buttons"""
    WORKFLOW_TRIGGER = "workflow_trigger"
    LINK = "link"
    MODAL = "modal"


class ModuleType(str, Enum):
    """Dashboard modules"""
    TASKS = "tasks"
    TOURS = "tours"
    ALERTS = "alerts"
    ASSETS = "assets"
    ATTENDANCE = "attendance"
    ROUTES = "routes"


class ActionSchema(BaseModel):
    """Action button configuration"""
    label: str = Field(..., min_length=1, max_length=100)
    type: ActionType
    endpoint: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    url: Optional[str] = None

    @model_validator(mode='after')
    def validate_action_requirements(self):
        """Validate action type-specific requirements"""
        if self.type == ActionType.WORKFLOW_TRIGGER and not self.endpoint:
            raise ValueError("workflow_trigger actions require 'endpoint'")
        if self.type == ActionType.LINK and not self.url:
            raise ValueError("link actions require 'url'")

        return self


class DetailSchema(BaseModel):
    """Entity-specific detail in recommendation"""
    entity_id: str = Field(..., description="Task ID, tour ID, etc.")
    reason: str = Field(..., min_length=1)
    priority: str
    suggested_action: str = Field(..., min_length=1)

    # Optional fields for flexibility
    metadata: Optional[Dict[str, Any]] = None


class ContextMetricsSchema(BaseModel):
    """Context metrics - flexible structure per module"""
    # Common metrics
    completed: Optional[int] = None
    pending: Optional[int] = None
    autoclosed: Optional[int] = None
    scheduled: Optional[int] = None
    overdue: Optional[int] = None

    # Allow additional arbitrary metrics
    class Config:
        extra = "allow"


class ContextSchema(BaseModel):
    """Recommendation context"""
    module: ModuleType
    site: str = Field(..., description="Site/Business Unit name or ID")
    time_range: str = Field(..., description="Human-readable time range")
    metrics: ContextMetricsSchema


class RecommendationContentSchema(BaseModel):
    """Recommendation content"""
    summary: str = Field(..., min_length=10, max_length=500)
    details: List[DetailSchema] = Field(default_factory=list)

    @validator('details')
    def validate_details_count(cls, v):
        """Ensure reasonable number of details"""
        if len(v) > 100:
            raise ValueError("Too many details (max 100)")
        return v


class AgentRecommendationSchema(BaseModel):
    """
    Complete agent recommendation schema

    Used to validate recommendations before database persistence
    """
    agent_id: str = Field(..., pattern=r'^[a-z]+bot-\d+$')
    agent_name: str = Field(..., min_length=1, max_length=100)
    timestamp: datetime
    context: ContextSchema
    recommendation: RecommendationContentSchema
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: SeverityLevel
    actions: List[ActionSchema] = Field(default_factory=list)
    status: str = "pending_review"
    human_feedback: Optional[str] = None
    llm_provider: str = Field(default="gemini", description="LLM provider used")

    @validator('actions')
    def validate_actions_count(cls, v):
        """Ensure reasonable number of actions"""
        if len(v) > 5:
            raise ValueError("Too many actions (max 5 per recommendation)")
        if len(v) == 0:
            raise ValueError("At least one action required")
        return v

    class Config:
        # Allow datetime objects
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        # Strict validation
        validate_assignment = True
