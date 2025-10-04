"""
Journal Services Package

Consolidated service layer for journal functionality:
- analytics_service: Comprehensive analytics and insights
- workflow_orchestrator: Multi-step operation coordination
- task_monitor: Background task monitoring and health checks
- pattern_analyzer: Pattern recognition and immediate analysis (refactored)

This package provides a clean, testable service layer that follows
Single Responsibility Principle and reduces code duplication.
"""

# Import main services for easy access
from .analytics_service import JournalAnalyticsService
from .workflow_orchestrator import JournalWorkflowOrchestrator
from .task_monitor import JournalTaskMonitor, task_monitor
from .pattern_analyzer import JournalPatternAnalyzer

# Expose services for external use
__all__ = [
    'JournalAnalyticsService',
    'JournalWorkflowOrchestrator',
    'JournalTaskMonitor',
    'task_monitor',
    'JournalPatternAnalyzer'
]

# Service factory functions for dependency injection
def get_analytics_service():
    """Get analytics service instance"""
    return JournalAnalyticsService()

def get_workflow_orchestrator():
    """Get workflow orchestrator instance"""
    return JournalWorkflowOrchestrator()

def get_task_monitor():
    """Get task monitor instance"""
    return task_monitor

def get_pattern_analyzer():
    """Get pattern analyzer instance"""
    return JournalPatternAnalyzer()