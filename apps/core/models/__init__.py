"""
Core Models Package - Backward Compatibility Layer

This module provides 100% backward compatibility for the refactored core models.
All model classes are re-exported from their new locations in domain-focused modules.

Migration Date: 2025-10-10
Original File: apps/core/models.py (907 lines)
New Structure: 27 domain-focused modules + __init__.py

Usage:
    # Old import (still works):
    from apps.core.models import CSPViolation, APIKey, SessionForensics

    # New import (recommended):
    from apps.core.models.security_models import CSPViolation
    from apps.core.models.api_authentication import APIKey
"""

from django.contrib.auth import get_user_model
from apps.tenants.models import TenantAwareModel

# Enhanced base models and mixins
from .enhanced_base_model import (
    TimestampMixin,
    AuditMixin,
    MobileSyncMixin,
    ActiveStatusMixin,
    EnhancedBaseModel,
    EnhancedSyncModel,
    EnhancedTenantModel,
    EnhancedTenantSyncModel,
    BaseModelCompat,
)
BaseModel = BaseModelCompat

# Admin help system
from .admin_help import AdminHelpTopic

# Admin mentor system
from .admin_mentor import AdminMentorSession, AdminMentorTip

# Cron job management
from .cron_job_definition import CronJobDefinition
from .cron_job_execution import CronJobExecution

# Image metadata and EXIF (refactored into 4 modules)
from .image_metadata_core import ImageMetadata
from .photo_authenticity import PhotoAuthenticityLog
from .camera_fingerprint import CameraFingerprint
from .image_quality import ImageQualityAssessment

# Security and audit models
from .security_models import (
    CSPViolation,
    SessionForensics,
)

# API authentication and access logging
from .api_authentication import (
    APIKey,
    APIAccessLog,
)

# Encryption key management
from .encryption_models import EncryptionKeyMetadata

# Token management
from .refresh_token_blacklist import RefreshTokenBlacklist

# State machine audit
from .state_transition_audit import StateTransitionAudit

# Rate limiting
from .rate_limiting import (
    RateLimitBlockedIP,
    RateLimitTrustedIP,
)

# Cache analytics
from .cache_analytics import (
    CacheMetrics,
    CacheAnomalyLog,
)

# Health monitoring
from .health_monitoring import (
    HealthCheckLog,
    ServiceAvailability,
    AlertThreshold,
)

# API deprecation tracking
from .api_deprecation import (
    APIDeprecation,
    APIDeprecationUsage,
)

# Upload session management
from .upload_session import UploadSession

# Sync conflict resolution
from .sync_conflict_policy import (
    TenantConflictPolicy,
    ConflictResolutionLog,
)

# Sync analytics
from .sync_analytics import (
    SyncAnalyticsSnapshot,
    SyncDeviceHealth,
)

# Query performance monitoring
from .query_performance import (
    QueryPerformanceSnapshot,
    SlowQueryAlert,
    QueryPattern,
)

# Query execution plans
from .query_execution_plans import (
    QueryExecutionPlan,
    PlanRegressionAlert,
)

# Sync idempotency
from .sync_idempotency import SyncIdempotencyRecord

# Sync mixins (additional sync-related functionality)
from .sync_mixins import (
    SyncableModelMixin,
    ConflictTrackingMixin,
    FullSyncMixin,
    SyncMetricsMixin,
)

# Audit models
from .audit import (
    AuditLog,
    BulkOperationAudit,
    PermissionDenialAudit,
)

# Device registry
from .device_registry import UserDevice, DeviceSyncState

# Push notifications
from .push_subscription import PushSubscription

# Monitoring API key
from .monitoring_api_key import MonitoringAPIKey

# Task failure tracking
from .task_failure_record import TaskFailureRecord

# Transaction monitoring
from .transaction_monitoring import (
    TransactionFailureLog,
    TransactionMetrics,
    SagaExecutionLog,
    TransactionHealthCheck,
)

# Saga state persistence (Sprint 3)
from .saga_state import SagaState

# LLM usage tracking (Sprint 7-8)
from .llm_usage import LLMUsageLog, LLMQuota

# Recommendation engine
from .recommendation import (
    UserBehaviorProfile,
    NavigationRecommendation,
    ContentRecommendation,
    RecommendationImplementation,
    UserSimilarity,
    RecommendationFeedback,
)

# Agent Intelligence (Dashboard Agent Recommendations)
from .agent_recommendation import AgentRecommendation

# Encrypted Secrets Management
from .encrypted_secret import EncryptedSecret

# User scope and saved views (Command Center - Phase 1)
from .user_scope import UserScope
from .dashboard_saved_view import DashboardSavedView

# Quality metrics tracking (Phase 7)
from .quality_metrics import QualityMetric

# Quick Actions (Runbooks/Playbooks)
from .quick_action import QuickAction, QuickActionExecution, QuickActionChecklist

# Admin Panel Enhancements
from .admin_runbook import Runbook, RunbookExecution
from .admin_approval import ApprovalRequest, ApprovalAction
from .operations_queue import OperationsQueueItem
from .sla_prediction import SLAPrediction

# Explicit __all__ for clarity and documentation
__all__ = [
    # Enhanced base models and mixins
    "TenantAwareModel",
    "BaseModel",
    "TimestampMixin",
    "AuditMixin",
    "MobileSyncMixin",
    "ActiveStatusMixin",
    "EnhancedBaseModel",
    "EnhancedSyncModel",
    "EnhancedTenantModel",
    "EnhancedTenantSyncModel",
    "BaseModelCompat",
    # Cron management
    "CronJobDefinition",
    "CronJobExecution",
    # Image metadata
    "ImageMetadata",
    "PhotoAuthenticityLog",
    "CameraFingerprint",
    "ImageQualityAssessment",
    # Security models
    "CSPViolation",
    "SessionForensics",
    # API authentication
    "APIKey",
    "APIAccessLog",
    # Encryption
    "EncryptionKeyMetadata",
    # Token management
    "RefreshTokenBlacklist",
    # State machine
    "StateTransitionAudit",
    # Rate limiting
    "RateLimitBlockedIP",
    "RateLimitTrustedIP",
    # Cache analytics
    "CacheMetrics",
    "CacheAnomalyLog",
    # Health monitoring
    "HealthCheckLog",
    "ServiceAvailability",
    "AlertThreshold",
    # API deprecation
    "APIDeprecation",
    "APIDeprecationUsage",
    # Upload session
    "UploadSession",
    # Sync conflict
    "TenantConflictPolicy",
    "ConflictResolutionLog",
    # Sync analytics
    "SyncAnalyticsSnapshot",
    "SyncDeviceHealth",
    # Query performance
    "QueryPerformanceSnapshot",
    "SlowQueryAlert",
    "QueryPattern",
    # Query execution
    "QueryExecutionPlan",
    "PlanRegressionAlert",
    # Sync idempotency
    "SyncIdempotencyRecord",
    # Sync mixins
    "SyncableModelMixin",
    "ConflictTrackingMixin",
    "FullSyncMixin",
    "SyncMetricsMixin",
    # Audit
    "AuditLog",
    "BulkOperationAudit",
    "PermissionDenialAudit",
    # Device registry
    "UserDevice",
    "DeviceSyncState",
    # Push notifications
    "PushSubscription",
    # Monitoring API
    "MonitoringAPIKey",
    # Task failure
    "TaskFailureRecord",
    # Transaction monitoring
    "TransactionFailureLog",
    "TransactionMetrics",
    "SagaExecutionLog",
    "TransactionHealthCheck",
    # Saga state (Sprint 3)
    "SagaState",
    # LLM usage (Sprint 7-8)
    "LLMUsageLog",
    "LLMQuota",
    # Recommendation
    "UserBehaviorProfile",
    "NavigationRecommendation",
    "ContentRecommendation",
    "RecommendationImplementation",
    "UserSimilarity",
    "RecommendationFeedback",
    # Agent Intelligence
    "AgentRecommendation",
    # Encrypted Secrets
    "EncryptedSecret",
    # User scope (Command Center - Phase 1)
    "UserScope",
    "DashboardSavedView",
    # Quality metrics (Phase 7)
    "QualityMetric",
    # Quick Actions (Runbooks/Playbooks)
    "QuickAction",
    "QuickActionExecution",
    "QuickActionChecklist",
    # Admin Panel Enhancements
    "Runbook",
    "RunbookExecution",
    "ApprovalRequest",
    "ApprovalAction",
    "OperationsQueueItem",
    "SLAPrediction",
]
