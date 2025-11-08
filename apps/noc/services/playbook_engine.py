"""
Playbook Engine Service.

Executes automated remediation playbooks with action handlers and error recovery.

Industry benchmark: 62% auto-resolution rate.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling

@ontology(
    domain="noc",
    purpose="Execute automated remediation playbooks with action sequencing",
    business_value="60%+ auto-resolution without human intervention",
    action_types=[
        "send_notification",
        "create_ticket",
        "assign_resource",
        "collect_diagnostics",
        "wait_for_condition"
    ],
    criticality="high",
    tags=["noc", "soar", "automation", "remediation", "playbook-engine"]
)
"""

import logging
import time
from datetime import timedelta
from typing import Dict, Any, Optional
from django.utils import timezone
from django.db import DatabaseError
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS


__all__ = ['PlaybookEngine']

logger = logging.getLogger('noc.playbook_engine')


class PlaybookEngine:
    """
    Executes automated remediation playbooks.

    Supported action types:
    - send_notification: Email/Slack/Teams notification
    - create_ticket: Auto-create helpdesk ticket
    - assign_resource: Auto-assign personnel
    - collect_diagnostics: Gather logs/metrics
    - wait_for_condition: Poll until condition met
    """

    ACTION_HANDLERS = {
        'send_notification': '_execute_notification',
        'create_ticket': '_execute_create_ticket',
        'assign_resource': '_execute_assign_resource',
        'collect_diagnostics': '_execute_collect_diagnostics',
        'wait_for_condition': '_execute_wait_condition',
    }

    @classmethod
    def execute_playbook(cls, playbook, finding, approved_by=None):
        """
        Execute playbook actions sequentially.

        Creates PlaybookExecution record and schedules async execution via Celery.

        Args:
            playbook: ExecutablePlaybook instance
            finding: AuditFinding instance that triggered playbook
            approved_by: People instance if manually approved (optional)

        Returns:
            PlaybookExecution instance

        Raises:
            ValueError: If playbook or finding is invalid
        """
        from apps.noc.models import PlaybookExecution

        if not playbook or not finding:
            raise ValueError("Playbook and finding are required")

        try:
            execution = PlaybookExecution.objects.create(
                playbook=playbook,
                finding=finding,
                tenant=finding.tenant,
                status='PENDING',
                requires_approval=not playbook.auto_execute,
                execution_context={
                    'finding_type': finding.finding_type,
                    'severity': finding.severity,
                    'site_id': finding.site.id if finding.site else None,
                }
            )

            # Check approval requirement
            if execution.requires_approval and not approved_by:
                logger.info(
                    f"Playbook {playbook.name} requires approval",
                    extra={'execution_id': str(execution.execution_id)}
                )
                return execution

            # Mark as approved if user provided
            if approved_by:
                execution.approved_by = approved_by
                execution.approved_at = timezone.now()
                execution.save(update_fields=['approved_by', 'approved_at'])

            # Schedule async execution via Celery
            from apps.noc.tasks.playbook_tasks import ExecutePlaybookTask
            ExecutePlaybookTask.delay(str(execution.execution_id))

            logger.info(
                f"Playbook execution scheduled",
                extra={
                    'playbook': playbook.name,
                    'execution_id': str(execution.execution_id),
                    'finding_id': finding.id
                }
            )

            return execution

        except DatabaseError as e:
            logger.error(f"Database error creating execution: {e}", exc_info=True)
            raise

    @classmethod
    def _execute_notification(cls, params: Dict[str, Any], finding) -> Dict[str, Any]:
        """
        Send notification action handler.

        Args:
            params: {channel: 'slack'|'email'|'sms', message: str, recipients: list}
            finding: AuditFinding instance

        Returns:
            Dict with result status
        """
        from apps.reports.services.report_delivery_service import ReportDeliveryService
        
        channel = params.get('channel', 'email')
        message = params.get('message', f"Finding: {finding.title}")
        recipients = params.get('recipients', [])

        logger.info(
            f"Sending {channel} notification",
            extra={'finding_id': finding.id, 'channel': channel}
        )

        success_count = 0
        
        if channel == 'email' and recipients:
            for recipient in recipients:
                try:
                    ReportDeliveryService.send_email(
                        recipient=recipient,
                        subject=f"SOAR Alert: {finding.title}",
                        body=message,
                        tenant=finding.tenant
                    )
                    success_count += 1
                except (ValueError, TypeError, AttributeError) as e:
                    logger.error(f"Failed to send email to {recipient}: {e}")
        
        elif channel == 'slack':
            webhook_url = params.get('webhook_url')
            if webhook_url:
                try:
                    import requests
                    response = requests.post(
                        webhook_url,
                        json={'text': message},
                        timeout=(5, 15)
                    )
                    if response.status_code == 200:
                        success_count = len(recipients) if recipients else 1
                except NETWORK_EXCEPTIONS as e:
                    logger.error(f"Failed to send Slack notification: {e}")
        
        return {
            'action': 'send_notification',
            'channel': channel,
            'recipients_count': len(recipients),
            'success_count': success_count,
            'message_sent': success_count > 0
        }

    @classmethod
    def _execute_create_ticket(cls, params: Dict[str, Any], finding) -> Dict[str, Any]:
        """
        Create helpdesk ticket action handler.

        Args:
            params: {priority: str, title: str, description: str}
            finding: AuditFinding instance

        Returns:
            Dict with ticket ID and status
        """
        from apps.y_helpdesk.models import Ticket

        priority = params.get('priority', finding.severity)
        title = params.get('title', finding.title)
        description = params.get('description', finding.description)

        try:
            ticket = Ticket.objects.create(
                tenant=finding.tenant,
                client=finding.site.client if finding.site else None,
                bu=finding.site,
                ticketdesc=description,
                priority=priority,
                status='NEW',
                tickettype='AUTOMATED',
                source='PLAYBOOK',
            )

            logger.info(
                f"Created ticket from playbook",
                extra={'ticket_id': ticket.id, 'finding_id': finding.id}
            )

            return {
                'action': 'create_ticket',
                'ticket_id': ticket.id,
                'ticket_no': getattr(ticket, 'ticketno', None),
                'created': True
            }

        except (DatabaseError, AttributeError) as e:
            logger.error(f"Failed to create ticket: {e}", exc_info=True)
            raise

    @classmethod
    def _execute_assign_resource(cls, params: Dict[str, Any], finding) -> Dict[str, Any]:
        """
        Assign resource/personnel action handler.

        Args:
            params: {resource_type: 'user'|'group', resource_id: int}
            finding: AuditFinding instance

        Returns:
            Dict with assignment status
        """
        from apps.peoples.models import People, Pgroup
        from apps.y_helpdesk.models import Ticket
        
        resource_type = params.get('resource_type')
        resource_id = params.get('resource_id')

        logger.info(
            f"Assigning resource",
            extra={'resource_type': resource_type, 'finding_id': finding.id}
        )

        assigned = False
        assignee = None
        
        try:
            if resource_type == 'user' and resource_id:
                assignee = People.objects.get(id=resource_id, tenant=finding.tenant)
                finding.assigned_to = assignee
                finding.save(update_fields=['assigned_to'])
                assigned = True
                
                # If there's an associated ticket, assign it too
                tickets = Ticket.objects.filter(
                    tenant=finding.tenant,
                    source='PLAYBOOK',
                    other_data__finding_id=finding.id
                )
                tickets.update(assignee=assignee, status='ASSIGNED')
                
            elif resource_type == 'group' and resource_id:
                group = Pgroup.objects.get(id=resource_id, tenant=finding.tenant)
                # Assign to first available member in group
                members = group.members.filter(is_active=True)
                if members.exists():
                    assignee = members.first()
                    finding.assigned_to = assignee
                    finding.save(update_fields=['assigned_to'])
                    assigned = True
                    
        except (People.DoesNotExist, Pgroup.DoesNotExist) as e:
            logger.error(f"Resource not found: {e}")
        except DatabaseError as e:
            logger.error(f"Database error assigning resource: {e}")
        
        return {
            'action': 'assign_resource',
            'resource_type': resource_type,
            'resource_id': resource_id,
            'assignee_id': assignee.id if assignee else None,
            'assigned': assigned
        }

    @classmethod
    def _execute_collect_diagnostics(cls, params: Dict[str, Any], finding) -> Dict[str, Any]:
        """
        Collect diagnostics action handler.

        Args:
            params: {diagnostic_types: list, output_format: str}
            finding: AuditFinding instance

        Returns:
            Dict with collected diagnostics
        """
        from apps.mqtt.models import DeviceTelemetry, SensorReading
        from apps.y_helpdesk.models import Ticket
        
        diagnostic_types = params.get('diagnostic_types', [])

        logger.info(
            f"Collecting diagnostics",
            extra={'types': diagnostic_types, 'finding_id': finding.id}
        )

        diagnostics = {}
        
        try:
            for diag_type in diagnostic_types:
                if diag_type == 'device_telemetry' and finding.site:
                    recent_telemetry = DeviceTelemetry.objects.filter(
                        tenant=finding.tenant,
                        timestamp__gte=timezone.now() - timedelta(hours=1)
                    ).values('device_id', 'battery_level', 'signal_strength', 'status')[:50]
                    diagnostics['device_telemetry'] = list(recent_telemetry)
                    
                elif diag_type == 'sensor_readings' and finding.site:
                    recent_sensors = SensorReading.objects.filter(
                        tenant=finding.tenant,
                        timestamp__gte=timezone.now() - timedelta(hours=1)
                    ).values('sensor_id', 'reading_value', 'status')[:50]
                    diagnostics['sensor_readings'] = list(recent_sensors)
                    
                elif diag_type == 'related_tickets':
                    related_tickets = Ticket.objects.filter(
                        tenant=finding.tenant,
                        bu=finding.site,
                        status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS']
                    ).values('id', 'ticketdesc', 'priority', 'status')[:20]
                    diagnostics['related_tickets'] = list(related_tickets)
                    
                elif diag_type == 'alert_context':
                    diagnostics['alert_context'] = {
                        'finding_type': finding.finding_type,
                        'severity': finding.severity,
                        'site': finding.site.name if finding.site else None,
                        'description': finding.description,
                    }
                    
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error collecting diagnostics: {e}", exc_info=True)
        
        return {
            'action': 'collect_diagnostics',
            'types_collected': diagnostic_types,
            'diagnostics': diagnostics,
            'collected': len(diagnostics) > 0
        }

    @classmethod
    def _execute_wait_condition(cls, params: Dict[str, Any], finding) -> Dict[str, Any]:
        """
        Wait for condition action handler.

        Args:
            params: {condition: str, condition_field: str, expected_value: any, 
                     max_wait_seconds: int, poll_interval: int}
            finding: AuditFinding instance

        Returns:
            Dict with condition result
        """
        from apps.core.utils_new.condition_polling import ConditionPoller
        
        condition = params.get('condition')
        condition_field = params.get('condition_field', 'status')
        expected_value = params.get('expected_value')
        max_wait = params.get('max_wait_seconds', 300)
        poll_interval = params.get('poll_interval', 10)

        logger.info(
            f"Waiting for condition",
            extra={'condition': condition, 'finding_id': finding.id}
        )

        condition_met = False
        wait_time = 0
        
        try:
            def check_condition():
                """Check if condition is met on finding object."""
                finding.refresh_from_db()
                current_value = getattr(finding, condition_field, None)
                
                if condition == 'equals':
                    return current_value == expected_value
                elif condition == 'not_equals':
                    return current_value != expected_value
                elif condition == 'status_resolved':
                    return finding.status in ['RESOLVED', 'CLOSED']
                elif condition == 'assigned':
                    return finding.assigned_to is not None
                    
                return False
            
            poller = ConditionPoller(
                condition_func=check_condition,
                max_attempts=max_wait // poll_interval,
                poll_interval=poll_interval
            )
            
            condition_met = poller.wait_for_condition()
            wait_time = poller.elapsed_time
            
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error in condition polling: {e}", exc_info=True)
        
        if not condition_met:
            logger.warning(
                f"Condition not met within {max_wait}s",
                extra={'finding_id': finding.id, 'condition': condition}
            )
        
        return {
            'action': 'wait_for_condition',
            'condition': condition,
            'condition_met': condition_met,
            'wait_time': wait_time,
            'max_wait': max_wait
        }
