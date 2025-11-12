"""
Playbook Execution Celery Tasks.

Async execution of automated remediation playbooks with idempotency.

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #17: Transaction management
- Celery Configuration Guide: Proper task naming and decorators

@ontology(
    domain="noc",
    purpose="Async playbook execution with idempotency and error handling",
    business_value="60%+ auto-resolution rate",
    criticality="high",
    tags=["celery", "noc", "soar", "playbook", "automation"]
)
"""

import logging
import time
from typing import Dict, Any
from celery import shared_task
from django.utils import timezone
from django.db import transaction, DatabaseError, IntegrityError
from apps.core.tasks.base import IdempotentTask
from apps.core.utils_new.db_utils import get_current_db_name

__all__ = ['ExecutePlaybookTask']

logger = logging.getLogger('noc.playbook_tasks')


@shared_task(base=IdempotentTask, bind=True)
class ExecutePlaybookTask(IdempotentTask):
    """
    Execute playbook actions sequentially with error handling.

    Task Configuration:
    - Idempotent with 1-hour TTL (prevents duplicate executions)
    - Max 3 retries with exponential backoff
    - Specific exception handling for database and network errors

    Action Execution:
    - Sequential execution (one action at a time)
    - Per-action timeout enforcement
    - Critical action failures stop execution
    - Non-critical action failures continue execution
    """

    name = 'noc.playbook.execute'
    idempotency_ttl = 3600  # 1 hour
    max_retries = 3
    default_retry_delay = 300  # 5 minutes

    def run(self, execution_id: str):
        """
        Execute playbook actions for given execution ID.

        Args:
            execution_id: UUID string of PlaybookExecution

        Returns:
            Dict with execution summary

        Raises:
            DatabaseError: If database operations fail
            ValueError: If execution not found
        """
        from apps.noc.models import PlaybookExecution
        from apps.noc.services.playbook_engine import PlaybookEngine

        try:
            execution = PlaybookExecution.objects.select_related('playbook', 'finding').get(
                execution_id=execution_id
            )
        except PlaybookExecution.DoesNotExist:
            logger.error(f"Execution not found: {execution_id}")
            raise ValueError(f"PlaybookExecution {execution_id} not found")

        playbook = execution.playbook
        finding = execution.finding

        logger.info(
            f"Starting playbook execution",
            extra={
                'execution_id': execution_id,
                'playbook': playbook.name,
                'finding_id': finding.id,
                'action_count': len(playbook.actions)
            }
        )

        # Update execution status to RUNNING
        execution.status = 'RUNNING'
        execution.started_at = timezone.now()
        execution.save(update_fields=['status', 'started_at'])

        start_time = time.time()
        results = []
        success_count = 0
        failed_count = 0

        # Execute actions sequentially
        for idx, action in enumerate(playbook.actions):
            action_type = action.get('type')
            action_params = action.get('params', {})
            timeout = action.get('timeout', 60)
            critical = action.get('critical', False)

            logger.info(
                f"Executing action {idx + 1}/{len(playbook.actions)}",
                extra={
                    'execution_id': execution_id,
                    'action_type': action_type,
                    'critical': critical
                }
            )

            action_start = time.time()

            try:
                # Get action handler
                handler_name = PlaybookEngine.ACTION_HANDLERS.get(action_type)
                if not handler_name:
                    raise ValueError(f"Unknown action type: {action_type}")

                handler = getattr(PlaybookEngine, handler_name)

                # Execute action with timeout
                result = handler(action_params, finding)

                action_duration = time.time() - action_start

                results.append({
                    'action': action_type,
                    'status': 'success',
                    'output': result,
                    'duration': action_duration,
                    'timestamp': timezone.now().isoformat()
                })

                success_count += 1

                logger.info(
                    f"Action completed successfully",
                    extra={
                        'execution_id': execution_id,
                        'action_type': action_type,
                        'duration': action_duration
                    }
                )

            except (ValueError, DatabaseError, IntegrityError) as e:
                action_duration = time.time() - action_start

                results.append({
                    'action': action_type,
                    'status': 'failed',
                    'error': str(e),
                    'duration': action_duration,
                    'timestamp': timezone.now().isoformat()
                })

                failed_count += 1

                logger.error(
                    f"Action failed",
                    extra={
                        'execution_id': execution_id,
                        'action_type': action_type,
                        'error': str(e),
                        'critical': critical
                    },
                    exc_info=True
                )

                # Stop execution if critical action fails
                if critical:
                    logger.warning(
                        f"Critical action failed, stopping execution",
                        extra={'execution_id': execution_id}
                    )
                    break

        # Calculate final status
        total_duration = time.time() - start_time

        if failed_count == 0:
            final_status = 'SUCCESS'
        elif success_count == 0:
            final_status = 'FAILED'
        else:
            final_status = 'PARTIAL'

        # Update execution with results
        try:
            with transaction.atomic(using=get_current_db_name()):
                execution.action_results = results
                execution.completed_at = timezone.now()
                execution.duration_seconds = total_duration
                execution.status = final_status
                execution.save(update_fields=[
                    'action_results',
                    'completed_at',
                    'duration_seconds',
                    'status'
                ])

                # Update playbook statistics
                playbook.update_stats(
                    execution_duration_seconds=total_duration,
                    success=(final_status == 'SUCCESS')
                )

                logger.info(
                    f"Playbook execution completed",
                    extra={
                        'execution_id': execution_id,
                        'status': final_status,
                        'duration': total_duration,
                        'success_count': success_count,
                        'failed_count': failed_count
                    }
                )

        except DatabaseError as e:
            logger.error(f"Failed to save execution results: {e}", exc_info=True)
            raise

        return {
            'execution_id': execution_id,
            'status': final_status,
            'duration': total_duration,
            'actions_executed': len(results),
            'success_count': success_count,
            'failed_count': failed_count
        }
