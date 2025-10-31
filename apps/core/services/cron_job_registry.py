"""
CronJobRegistry Core Service

Central orchestrator for the unified cron management system.
Handles job registration, scheduling, execution coordination, and health monitoring.

Key Features:
- Unified job registration from multiple sources
- Schedule calculation and management
- Integration with existing infrastructure
- Health monitoring and alerting
- Tenant-aware operations

Compliance:
- Rule #7: Service < 150 lines (split into focused methods)
- Rule #11: Specific exception handling
- Rule #15: No PII in logs
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from django.core.management import get_commands
from django.db import transaction, DatabaseError
from django.utils import timezone
from django.conf import settings

from apps.core.services.base_service import BaseService
from apps.core.models.cron_job_definition import CronJobDefinition
from apps.core.models.cron_job_execution import CronJobExecution
from apps.core.utils_new.cron_utilities import validate_cron_expression
from apps.scheduler.services.cron_calculation_service import CronCalculationService

logger = logging.getLogger(__name__)


class CronJobRegistry(BaseService):
    """
    Central registry and orchestrator for cron jobs.

    Provides unified management of cron jobs across the application,
    including registration, scheduling, and health monitoring.
    """

    def __init__(self):
        super().__init__()
        self.cron_calculator = CronCalculationService()
        self._command_cache = {}

    def get_service_name(self) -> str:
        """Return service name for logging and monitoring."""
        return "CronJobRegistry"

    def register_management_command(
        self,
        command_name: str,
        cron_expression: str,
        description: str = "",
        tenant=None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Register a Django management command as a cron job.

        Args:
            command_name: Name of the management command
            cron_expression: Cron schedule expression
            description: Job description
            tenant: Tenant instance (if multi-tenant)
            **kwargs: Additional job configuration

        Returns:
            Dict containing registration result
        """
        try:
            # Validate command exists
            if not self._validate_management_command(command_name):
                raise ValueError(f"Management command '{command_name}' not found")

            # Validate cron expression
            cron_validation = validate_cron_expression(cron_expression)
            if not cron_validation['valid']:
                raise ValueError(f"Invalid cron expression: {cron_validation['error']}")

            # Create or update job definition
            with transaction.atomic():
                job_def, created = CronJobDefinition.objects.update_or_create(
                    tenant=tenant,
                    name=f"mgmt_cmd_{command_name}",
                    defaults={
                        'description': description or f"Management command: {command_name}",
                        'cron_expression': cron_expression,
                        'job_type': 'management_command',
                        'command_name': command_name,
                        'command_args': kwargs.get('args', []),
                        'command_kwargs': kwargs.get('command_kwargs', {}),
                        'timeout_seconds': kwargs.get('timeout_seconds', 3600),
                        'max_retries': kwargs.get('max_retries', 3),
                        'priority': kwargs.get('priority', 'normal'),
                        'tags': kwargs.get('tags', ['management_command']),
                        'created_by': 'cron_registry_auto',
                        'is_enabled': True,
                        'status': 'active'
                    }
                )

                # Calculate next execution time
                self._update_next_execution_time(job_def)

            logger.info(
                f"Management command registered as cron job",
                extra={
                    'command_name': command_name,
                    'job_id': job_def.id,
                    'created': created,
                    'cron_expression': cron_expression
                }
            )

            return {
                'success': True,
                'job_id': job_def.id,
                'created': created,
                'next_execution': job_def.next_execution_time
            }

        except (ValueError, DatabaseError) as e:
            logger.error(
                f"Failed to register management command",
                extra={
                    'command_name': command_name,
                    'error': str(e)
                }
            )
            return {
                'success': False,
                'error': str(e)
            }

    def discover_and_register_commands(self, tenant=None) -> Dict[str, Any]:
        """
        Auto-discover management commands suitable for cron scheduling.

        Args:
            tenant: Tenant instance for multi-tenant setup

        Returns:
            Dict containing discovery results
        """
        try:
            # Commands suitable for cron scheduling
            schedulable_commands = {
                'cleanup_expired_uploads': {
                    'cron': '0 * * * *',  # Hourly
                    'description': 'Clean up expired upload sessions',
                    'timeout_seconds': 1800,
                    'tags': ['cleanup', 'maintenance']
                },
                'warm_caches': {
                    'cron': '*/15 * * * *',  # Every 15 minutes
                    'description': 'Warm application caches',
                    'timeout_seconds': 300,
                    'tags': ['performance', 'cache']
                },
                'rate_limit_cleanup': {
                    'cron': '0 0 * * *',  # Daily at midnight
                    'description': 'Clean up rate limiting records',
                    'timeout_seconds': 600,
                    'tags': ['cleanup', 'security']
                },
                'generate_compliance_report': {
                    'cron': '0 2 * * 1',  # Weekly on Monday at 2 AM
                    'description': 'Generate weekly compliance report',
                    'timeout_seconds': 3600,
                    'tags': ['reporting', 'compliance']
                },
                'monitor_encryption_health': {
                    'cron': '*/30 * * * *',  # Every 30 minutes
                    'description': 'Monitor encryption system health',
                    'timeout_seconds': 600,
                    'tags': ['monitoring', 'security']
                }
            }

            registered_count = 0
            skipped_count = 0
            errors = []

            available_commands = set(get_commands().keys())

            for cmd_name, config in schedulable_commands.items():
                if cmd_name not in available_commands:
                    skipped_count += 1
                    continue

                try:
                    result = self.register_management_command(
                        command_name=cmd_name,
                        cron_expression=config['cron'],
                        description=config['description'],
                        tenant=tenant,
                        timeout_seconds=config['timeout_seconds'],
                        tags=config['tags']
                    )

                    if result['success']:
                        registered_count += 1
                    else:
                        errors.append(f"{cmd_name}: {result['error']}")

                except ValueError as e:
                    errors.append(f"{cmd_name}: {str(e)}")
                    skipped_count += 1

            logger.info(
                f"Command auto-discovery completed",
                extra={
                    'registered': registered_count,
                    'skipped': skipped_count,
                    'errors': len(errors)
                }
            )

            return {
                'success': True,
                'registered_count': registered_count,
                'skipped_count': skipped_count,
                'errors': errors
            }

        except DatabaseError as e:
            logger.error(f"Auto-discovery failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_jobs_ready_for_execution(self, tenant=None) -> List[CronJobDefinition]:
        """
        Get all jobs that are ready for execution.

        Args:
            tenant: Tenant to filter by (optional)

        Returns:
            List of job definitions ready for execution
        """
        try:
            queryset = CronJobDefinition.objects.filter(
                is_enabled=True,
                status='active',
                next_execution_time__lte=timezone.now()
            )

            if tenant:
                queryset = queryset.filter(tenant=tenant)

            return list(queryset.select_related('tenant'))

        except DatabaseError as e:
            logger.error(f"Failed to get jobs ready for execution: {e}")
            return []

    def create_execution_record(
        self,
        job_definition: CronJobDefinition,
        execution_context: str = 'scheduled'
    ) -> Optional[CronJobExecution]:
        """
        Create an execution record for a job.

        Args:
            job_definition: Job definition to execute
            execution_context: Context (scheduled, manual, retry, etc.)

        Returns:
            Created execution record or None if failed
        """
        try:
            execution = CronJobExecution.objects.create(
                tenant=job_definition.tenant,
                job_definition=job_definition,
                execution_id=str(uuid.uuid4()),
                status='pending',
                execution_context=execution_context,
                scheduled_time=job_definition.next_execution_time or timezone.now()
            )

            logger.debug(
                f"Execution record created",
                extra={
                    'job_name': job_definition.name,
                    'execution_id': execution.execution_id,
                    'context': execution_context
                }
            )

            return execution

        except DatabaseError as e:
            logger.error(
                f"Failed to create execution record",
                extra={
                    'job_name': job_definition.name,
                    'error': str(e)
                }
            )
            return None

    def update_job_schedules(self, tenant=None) -> Dict[str, Any]:
        """
        Update next execution times for all active jobs.

        Args:
            tenant: Tenant to filter by (optional)

        Returns:
            Dict containing update results
        """
        try:
            queryset = CronJobDefinition.objects.filter(
                is_enabled=True,
                status='active'
            )

            if tenant:
                queryset = queryset.filter(tenant=tenant)

            updated_count = 0
            error_count = 0

            for job_def in queryset:
                try:
                    self._update_next_execution_time(job_def)
                    updated_count += 1
                except ValueError as e:
                    logger.error(
                        f"Failed to update schedule for job",
                        extra={
                            'job_name': job_def.name,
                            'error': str(e)
                        }
                    )
                    error_count += 1

            return {
                'success': True,
                'updated_count': updated_count,
                'error_count': error_count
            }

        except DatabaseError as e:
            logger.error(f"Failed to update job schedules: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _update_next_execution_time(self, job_def: CronJobDefinition):
        """Update next execution time for a job definition."""
        try:
            now = timezone.now()
            calculation_result = self.cron_calculator.calculate_next_occurrences(
                cron_expression=job_def.cron_expression,
                start_date=now,
                end_date=now + timedelta(days=1),
                max_occurrences=1
            )

            if calculation_result['status'] == 'success' and calculation_result['occurrences']:
                next_time = calculation_result['occurrences'][0]
                if isinstance(next_time, str):
                    next_time = datetime.fromisoformat(next_time.replace('Z', '+00:00'))

                job_def.next_execution_time = next_time
                job_def.save(update_fields=['next_execution_time'])

        except (ValueError, DatabaseError) as e:
            logger.error(
                f"Failed to calculate next execution time",
                extra={
                    'job_name': job_def.name,
                    'cron_expression': job_def.cron_expression,
                    'error': str(e)
                }
            )
            raise

    def _validate_management_command(self, command_name: str) -> bool:
        """Validate that a management command exists."""
        if command_name in self._command_cache:
            return self._command_cache[command_name]

        available_commands = get_commands()
        exists = command_name in available_commands

        # Cache result for performance
        self._command_cache[command_name] = exists
        return exists


# Global registry instance
cron_registry = CronJobRegistry()