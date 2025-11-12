"""
Task Priority Re-Queuing Service

Intelligent task priority calculation and dynamic queue assignment based on:
- Business criticality rules
- Task failure history
- SLA requirements
- System load conditions
- Customer tier/priority

Features:
- Automatic priority escalation for aging tasks
- Business-rule-based priority calculation
- SLA-aware re-queuing
- Load-balanced queue assignment

Usage:
    from apps.core.services.task_priority_service import priority_service
from apps.core.exceptions.patterns import CELERY_EXCEPTIONS

    
    priority = priority_service.calculate_priority(
        task_name='process_payment',
        context={'customer_tier': 'premium', 'age_hours': 2}
    )
    
    # Re-queue task with calculated priority
    priority_service.requeue_task(task_id, priority=priority)

Related Files:
- apps/core/models/task_failure_record.py - DLQ model
- background_tasks/dead_letter_queue.py - DLQ handler
- apps/core/tasks/failure_taxonomy.py - Failure classification
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_MINUTE

logger = logging.getLogger('celery.priority')


# ============================================================================
# Priority Definitions
# ============================================================================

class TaskPriority(Enum):
    """
    Task priority levels matching Celery queue structure.
    
    Priority scores (0-10):
    - 10: CRITICAL - System integrity, safety-critical operations
    - 8:  HIGH - User-facing operations, time-sensitive
    - 6:  MEDIUM - Background reports, analytics
    - 4:  LOW - Maintenance, cleanup operations
    - 2:  DEFERRED - Non-urgent background work
    """
    CRITICAL = (10, 'critical')           # Safety, security, system integrity
    HIGH = (8, 'high_priority')           # User-facing, time-sensitive
    MEDIUM = (6, 'reports')               # Reports, analytics
    LOW = (4, 'maintenance')              # Maintenance, cleanup
    DEFERRED = (2, 'maintenance')         # Can wait for off-peak hours
    
    def __init__(self, score: int, queue: str):
        self.score = score
        self.queue = queue


@dataclass
class PriorityCalculationResult:
    """
    Result of priority calculation with rationale.
    
    Attributes:
        priority: Calculated TaskPriority enum
        score: Numeric priority score (0-10)
        queue: Target Celery queue name
        rationale: Human-readable explanation
        adjustments: Dict of factors that influenced priority
        escalated: Whether priority was escalated from base
    """
    priority: TaskPriority
    score: int
    queue: str
    rationale: str
    adjustments: Dict[str, Any]
    escalated: bool


# ============================================================================
# Business Rules Configuration
# ============================================================================

class PriorityRules:
    """
    Centralized business rules for task priority calculation.
    
    Rules are defined as functions that return (score_adjustment, reason).
    Positive adjustments increase priority, negative decrease it.
    """
    
    # Task type base priorities (task_name pattern → base priority)
    TASK_BASE_PRIORITIES = {
        # Critical system operations
        'crisis_': TaskPriority.CRITICAL,
        'security_': TaskPriority.CRITICAL,
        'alert_': TaskPriority.CRITICAL,
        
        # High priority user-facing
        'process_payment': TaskPriority.HIGH,
        'create_job': TaskPriority.HIGH,
        'ticket_escalation': TaskPriority.HIGH,
        'autoclose_job': TaskPriority.HIGH,
        
        # Medium priority background
        'create_scheduled_reports': TaskPriority.MEDIUM,
        'generate_analytics': TaskPriority.MEDIUM,
        
        # Low priority maintenance
        'cleanup_': TaskPriority.LOW,
        'move_media_': TaskPriority.LOW,
    }
    
    # SLA thresholds (minutes) by customer tier
    SLA_THRESHOLDS = {
        'enterprise': 15,      # 15 minute SLA
        'premium': 30,         # 30 minute SLA
        'standard': 120,       # 2 hour SLA
        'basic': 480,          # 8 hour SLA
    }
    
    # Aging escalation thresholds (hours)
    AGING_ESCALATION = {
        24: 2,   # +2 priority after 24 hours
        12: 1,   # +1 priority after 12 hours
        6: 0.5,  # +0.5 priority after 6 hours
    }


# ============================================================================
# Task Priority Service
# ============================================================================

class TaskPriorityService:
    """
    Intelligent task priority calculation and queue management.
    
    Calculates task priority based on:
    - Task type and business criticality
    - Customer tier and SLA requirements
    - Task age and retry history
    - System load conditions
    - Failure type and urgency
    """
    
    def __init__(self):
        """Initialize priority service."""
        self.rules = PriorityRules()
        self.cache_prefix = 'task_priority:'
    
    def calculate_priority(
        self,
        task_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> PriorityCalculationResult:
        """
        Calculate optimal task priority based on business rules.
        
        Args:
            task_name: Name of the Celery task
            context: Task execution context
                - customer_tier: 'enterprise', 'premium', 'standard', 'basic'
                - age_hours: Task age in hours (for aging escalation)
                - retry_count: Number of retry attempts
                - failure_type: Type of failure (from taxonomy)
                - business_unit_id: Business unit identifier
                - is_safety_critical: Boolean flag
        
        Returns:
            PriorityCalculationResult with calculated priority
        
        Example:
            >>> priority = service.calculate_priority(
            ...     'process_payment',
            ...     {'customer_tier': 'enterprise', 'age_hours': 2}
            ... )
            >>> logger.info(priority.priority)  # TaskPriority.CRITICAL
            >>> logger.info(priority.rationale)  # "Escalated: Enterprise SLA + aging"
        """
        context = context or {}
        
        # Step 1: Get base priority from task type
        base_priority = self._get_base_priority(task_name)
        score = base_priority.score
        adjustments = {'base': base_priority.score}
        
        # Step 2: Apply business rules
        
        # Safety-critical flag (absolute priority)
        if context.get('is_safety_critical'):
            score = TaskPriority.CRITICAL.score
            adjustments['safety_critical'] = +10
        
        # Customer tier and SLA
        customer_tier = context.get('customer_tier', 'standard')
        sla_adjustment = self._calculate_sla_adjustment(
            customer_tier,
            context.get('age_hours', 0)
        )
        score += sla_adjustment
        if sla_adjustment != 0:
            adjustments['sla'] = sla_adjustment
        
        # Aging escalation
        age_hours = context.get('age_hours', 0)
        if age_hours > 0:
            aging_adjustment = self._calculate_aging_adjustment(age_hours)
            score += aging_adjustment
            if aging_adjustment > 0:
                adjustments['aging'] = aging_adjustment
        
        # Retry count escalation (persistent failures)
        retry_count = context.get('retry_count', 0)
        if retry_count >= 5:
            retry_adjustment = 1.0  # +1 priority after 5 retries
            score += retry_adjustment
            adjustments['retry_escalation'] = retry_adjustment
        
        # Failure type urgency
        failure_type = context.get('failure_type')
        if failure_type:
            failure_adjustment = self._get_failure_urgency(failure_type)
            score += failure_adjustment
            if failure_adjustment != 0:
                adjustments['failure_urgency'] = failure_adjustment
        
        # Step 3: Normalize score and determine priority
        score = max(2, min(10, score))  # Clamp to 2-10 range
        final_priority = self._score_to_priority(score)
        
        # Step 4: Build rationale
        escalated = final_priority.score > base_priority.score
        rationale = self._build_rationale(
            base_priority,
            final_priority,
            adjustments,
            context
        )
        
        # Step 5: Log priority decision
        logger.info(
            f"Priority calculated for {task_name}: {final_priority.name} (score: {score:.1f})",
            extra={
                'task_name': task_name,
                'priority': final_priority.name,
                'score': score,
                'escalated': escalated,
                'adjustments': adjustments,
            }
        )
        
        return PriorityCalculationResult(
            priority=final_priority,
            score=int(score),
            queue=final_priority.queue,
            rationale=rationale,
            adjustments=adjustments,
            escalated=escalated
        )
    
    def requeue_task(
        self,
        task_id: str,
        task_name: str,
        task_args: tuple = (),
        task_kwargs: Optional[Dict] = None,
        priority: Optional[TaskPriority] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Re-queue a task with calculated or explicit priority.
        
        Args:
            task_id: Original task ID
            task_name: Task function name
            task_args: Task positional arguments
            task_kwargs: Task keyword arguments
            priority: Explicit priority (if not provided, will calculate)
            context: Context for priority calculation
        
        Returns:
            Dict with new_task_id, priority, queue, rationale
        
        Example:
            >>> result = service.requeue_task(
            ...     task_id='abc-123',
            ...     task_name='process_payment',
            ...     task_args=(payment_id,),
            ...     context={'customer_tier': 'enterprise'}
            ... )
            >>> logger.info(result['new_task_id'])  # New Celery task ID
        """
        from celery import current_app
        
        task_kwargs = task_kwargs or {}
        
        # Calculate priority if not provided
        if priority is None:
            calc_result = self.calculate_priority(task_name, context)
            priority = calc_result.priority
            rationale = calc_result.rationale
        else:
            rationale = f"Explicit priority: {priority.name}"
        
        # Get task function
        try:
            task_func = current_app.tasks.get(task_name)
            if not task_func:
                raise ValueError(f"Task {task_name} not found in Celery registry")
        except CELERY_EXCEPTIONS as exc:
            logger.error(f"Failed to get task {task_name}: {exc}")
            return {
                'success': False,
                'error': f"Task not found: {task_name}"
            }
        
        # Queue task with priority
        try:
            result = task_func.apply_async(
                args=task_args,
                kwargs=task_kwargs,
                queue=priority.queue,
                priority=priority.score,
            )
            
            logger.info(
                f"Re-queued task {task_name} with priority {priority.name}",
                extra={
                    'original_task_id': task_id,
                    'new_task_id': result.id,
                    'priority': priority.name,
                    'queue': priority.queue,
                }
            )
            
            return {
                'success': True,
                'new_task_id': result.id,
                'priority': priority.name,
                'queue': priority.queue,
                'rationale': rationale,
            }
            
        except CELERY_EXCEPTIONS as exc:
            logger.error(f"Failed to re-queue task {task_name}: {exc}", exc_info=True)
            return {
                'success': False,
                'error': str(exc)
            }
    
    def _get_base_priority(self, task_name: str) -> TaskPriority:
        """Get base priority from task name pattern matching."""
        for pattern, priority in self.rules.TASK_BASE_PRIORITIES.items():
            if pattern in task_name or task_name.startswith(pattern.rstrip('_')):
                return priority
        
        # Default to MEDIUM priority
        return TaskPriority.MEDIUM
    
    def _calculate_sla_adjustment(self, customer_tier: str, age_hours: float) -> float:
        """Calculate priority adjustment based on SLA."""
        sla_minutes = self.rules.SLA_THRESHOLDS.get(customer_tier, 120)
        age_minutes = age_hours * 60
        
        if age_minutes > sla_minutes:
            # SLA breached - escalate priority
            breach_ratio = age_minutes / sla_minutes
            if breach_ratio > 2:
                return 2.0  # Severe SLA breach
            elif breach_ratio > 1.5:
                return 1.0  # Moderate SLA breach
            else:
                return 0.5  # Minor SLA breach
        
        # Within SLA, but premium customers get slight boost
        if customer_tier in ('enterprise', 'premium') and age_minutes > (sla_minutes * 0.8):
            return 0.25  # Approaching SLA limit
        
        return 0.0
    
    def _calculate_aging_adjustment(self, age_hours: float) -> float:
        """Calculate priority escalation based on task age."""
        for threshold_hours, adjustment in sorted(
            self.rules.AGING_ESCALATION.items(),
            reverse=True
        ):
            if age_hours >= threshold_hours:
                return adjustment
        return 0.0
    
    def _get_failure_urgency(self, failure_type: str) -> float:
        """Get priority adjustment based on failure type urgency."""
        urgency_map = {
            'SYSTEM_OUT_OF_MEMORY': 2.0,      # Critical system issue
            'SYSTEM_DISK_FULL': 2.0,          # Critical system issue
            'PERMANENT_PERMISSION': 1.0,      # Security issue, needs attention
            'EXTERNAL_API_DOWN': 0.5,         # May resolve soon
            'TRANSIENT_NETWORK': 0.0,         # Will auto-retry
            'TRANSIENT_DATABASE': 0.0,        # Will auto-retry
        }
        return urgency_map.get(failure_type, 0.0)
    
    def _score_to_priority(self, score: float) -> TaskPriority:
        """Convert numeric score to TaskPriority enum."""
        if score >= 9:
            return TaskPriority.CRITICAL
        elif score >= 7:
            return TaskPriority.HIGH
        elif score >= 5:
            return TaskPriority.MEDIUM
        elif score >= 3:
            return TaskPriority.LOW
        else:
            return TaskPriority.DEFERRED
    
    def _build_rationale(
        self,
        base_priority: TaskPriority,
        final_priority: TaskPriority,
        adjustments: Dict[str, float],
        context: Dict[str, Any]
    ) -> str:
        """Build human-readable rationale for priority decision."""
        parts = [f"Base: {base_priority.name}"]
        
        if adjustments.get('safety_critical'):
            parts.append("SAFETY CRITICAL")
        if adjustments.get('sla'):
            parts.append(f"SLA breach (+{adjustments['sla']:.1f})")
        if adjustments.get('aging'):
            parts.append(f"Aged {context.get('age_hours', 0):.1f}h (+{adjustments['aging']:.1f})")
        if adjustments.get('retry_escalation'):
            parts.append(f"Retry #{context.get('retry_count', 0)}")
        if adjustments.get('failure_urgency'):
            parts.append(f"Urgent failure type")
        
        if final_priority.score > base_priority.score:
            parts.append(f"→ ESCALATED to {final_priority.name}")
        elif final_priority.score < base_priority.score:
            parts.append(f"→ Reduced to {final_priority.name}")
        
        return " | ".join(parts)


# ============================================================================
# Global Service Instance
# ============================================================================

priority_service = TaskPriorityService()
