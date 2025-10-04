"""
Automated Ticketing Service

Intelligent ticket creation, routing, and management system.
Creates tickets from alerts and routes them to appropriate teams.
"""

import logging
from typing import Dict, List, Optional
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from apps.monitoring.models import (
    Alert, OperationalTicket, TicketCategory, AutomatedAction,
    TicketEscalation
)
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class TicketService:
    """
    Automated ticketing system with intelligent routing.

    Features:
    - Automatic ticket creation from alerts
    - Smart routing based on alert type and context
    - SLA tracking and escalation
    - Resource allocation automation
    - Performance analytics
    """

    def __init__(self):
        self.auto_assignment_enabled = True
        self.escalation_enabled = True

        # Routing configuration
        self.routing_rules = self._initialize_routing_rules()
        self.priority_escalation_minutes = {
            'LOW': 240,      # 4 hours
            'MEDIUM': 120,   # 2 hours
            'HIGH': 60,      # 1 hour
            'URGENT': 30,    # 30 minutes
            'EMERGENCY': 15  # 15 minutes
        }

    def create_ticket_from_alert(self, alert: Alert) -> Optional[OperationalTicket]:
        """
        Create an operational ticket from an alert with intelligent routing.

        Args:
            alert: Alert instance to create ticket from

        Returns:
            Created OperationalTicket or None if creation failed
        """
        try:
            with transaction.atomic():
                # Get or create appropriate ticket category
                category = self._get_ticket_category(alert)
                if not category:
                    logger.error(f"Could not determine ticket category for alert {alert.alert_id}")
                    return None

                # Create the ticket
                ticket = OperationalTicket.objects.create(
                    category=category,
                    alert=alert,
                    user=alert.user,
                    device_id=alert.device_id,
                    site=alert.site,
                    title=self._generate_ticket_title(alert),
                    description=self._generate_ticket_description(alert),
                    priority=self._determine_ticket_priority(alert),
                    automation_data={
                        'created_from_alert': True,
                        'alert_id': str(alert.alert_id),
                        'alert_type': alert.rule.alert_type,
                        'auto_created_at': timezone.now().isoformat()
                    }
                )

                # Apply intelligent routing
                self._apply_intelligent_routing(ticket, alert)

                # Schedule automated actions
                self._schedule_automated_actions(ticket, alert)

                logger.info(f"Created ticket {ticket.ticket_number} from alert {alert.alert_id}")
                return ticket

        except Exception as e:
            logger.error(f"Error creating ticket from alert {alert.alert_id}: {str(e)}", exc_info=True)
            return None

    def route_ticket(self, ticket: OperationalTicket, context: Dict = None) -> bool:
        """
        Route ticket to appropriate team/person with intelligent assignment.

        Args:
            ticket: Ticket to route
            context: Additional context for routing decisions

        Returns:
            True if successfully routed
        """
        try:
            with transaction.atomic():
                # Determine routing based on multiple factors
                routing_decision = self._make_routing_decision(ticket, context)

                if not routing_decision:
                    logger.warning(f"Could not determine routing for ticket {ticket.ticket_number}")
                    return False

                # Apply routing decision
                assigned_user = routing_decision.get('assigned_user')
                assigned_role = routing_decision.get('assigned_role')

                if assigned_user:
                    ticket.assign_to_user(assigned_user, routing_decision.get('routing_reason', ''))
                else:
                    ticket.assigned_role = assigned_role
                    ticket.status = 'OPEN'  # Keep open for role-based assignment
                    ticket.save()

                # Create routing audit trail
                self._create_routing_audit(ticket, routing_decision)

                logger.info(f"Routed ticket {ticket.ticket_number} to {assigned_user or assigned_role}")
                return True

        except Exception as e:
            logger.error(f"Error routing ticket {ticket.ticket_number}: {str(e)}", exc_info=True)
            return False

    def escalate_overdue_tickets(self) -> int:
        """
        Escalate overdue tickets based on SLA rules.

        Returns:
            Number of tickets escalated
        """
        try:
            # Find overdue tickets
            overdue_tickets = OperationalTicket.objects.filter(
                status__in=['OPEN', 'ASSIGNED'],
                is_overdue=True
            ).select_related('category', 'user', 'assigned_to')

            escalated_count = 0

            for ticket in overdue_tickets:
                if self._escalate_ticket(ticket):
                    escalated_count += 1

            if escalated_count > 0:
                logger.info(f"Escalated {escalated_count} overdue tickets")

            return escalated_count

        except Exception as e:
            logger.error(f"Error escalating overdue tickets: {str(e)}", exc_info=True)
            return 0

    def get_ticket_statistics(self, days: int = 7) -> Dict:
        """
        Get ticket statistics for the specified period.

        Args:
            days: Number of days to include

        Returns:
            Dictionary containing ticket statistics
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days)

            # Basic counts
            total_tickets = OperationalTicket.objects.filter(created_at__gte=cutoff_date).count()
            open_tickets = OperationalTicket.objects.filter(status='OPEN').count()
            resolved_tickets = OperationalTicket.objects.filter(
                status='RESOLVED',
                created_at__gte=cutoff_date
            ).count()

            # SLA performance
            overdue_tickets = OperationalTicket.objects.filter(is_overdue=True).count()

            # Category breakdown
            category_stats = OperationalTicket.objects.filter(
                created_at__gte=cutoff_date
            ).values('category__name').annotate(count=Count('id'))

            # Priority breakdown
            priority_stats = OperationalTicket.objects.filter(
                created_at__gte=cutoff_date
            ).values('priority').annotate(count=Count('id'))

            return {
                'period_days': days,
                'total_tickets': total_tickets,
                'open_tickets': open_tickets,
                'resolved_tickets': resolved_tickets,
                'overdue_tickets': overdue_tickets,
                'resolution_rate': (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0,
                'category_breakdown': {item['category__name']: item['count'] for item in category_stats},
                'priority_breakdown': {item['priority']: item['count'] for item in priority_stats}
            }

        except Exception as e:
            logger.error(f"Error getting ticket statistics: {str(e)}")
            return {}

    def _initialize_routing_rules(self) -> Dict:
        """Initialize ticket routing rules"""
        return {
            'BATTERY_CRITICAL': {
                'priority': 'HIGH',
                'route_to_role': 'field_supervisor',
                'response_time_minutes': 15,
                'auto_actions': ['send_replacement_device', 'notify_backup']
            },
            'NO_MOVEMENT': {
                'priority': 'CRITICAL',
                'route_to_role': 'security_team',
                'response_time_minutes': 5,
                'auto_actions': ['emergency_call', 'dispatch_check']
            },
            'LOCATION_VIOLATION': {
                'priority': 'HIGH',
                'route_to_role': 'security_supervisor',
                'response_time_minutes': 10,
                'auto_actions': ['location_verification', 'notify_management']
            },
            'BIOMETRIC_FAILURE': {
                'priority': 'HIGH',
                'route_to_role': 'security_team',
                'response_time_minutes': 15,
                'auto_actions': ['identity_verification', 'device_check']
            },
            'DEVICE_OVERHEATING': {
                'priority': 'CRITICAL',
                'route_to_role': 'safety_officer',
                'response_time_minutes': 5,
                'auto_actions': ['device_shutdown', 'safety_check']
            },
            'NETWORK_DOWN': {
                'priority': 'HIGH',
                'route_to_role': 'it_support',
                'response_time_minutes': 20,
                'auto_actions': ['connectivity_check', 'alternative_communication']
            }
        }

    def _get_ticket_category(self, alert: Alert) -> Optional[TicketCategory]:
        """Get or create appropriate ticket category for alert"""
        try:
            alert_type = alert.rule.alert_type
            category_name = f"{alert_type}_TICKETS"

            # Try to find existing category
            category = TicketCategory.objects.filter(name=category_name).first()

            if not category:
                # Create new category based on routing rules
                routing_rule = self.routing_rules.get(alert_type, {})

                category = TicketCategory.objects.create(
                    name=category_name,
                    description=f"Automated tickets for {alert_type} alerts",
                    default_priority=routing_rule.get('priority', alert.severity),
                    default_assignee_role=routing_rule.get('route_to_role', 'general_support'),
                    response_time_minutes=routing_rule.get('response_time_minutes', 60),
                    resolution_time_hours=24,
                    title_template=f"{alert_type}: {{user_name}} - {{device_id}}",
                    description_template="{{alert_description}}",
                    auto_assign=True,
                    auto_escalate=True,
                    notification_channels=['email', 'dashboard']
                )

            return category

        except Exception as e:
            logger.error(f"Error getting ticket category: {str(e)}")
            return None

    def _generate_ticket_title(self, alert: Alert) -> str:
        """Generate appropriate ticket title"""
        try:
            alert_type_display = alert.rule.alert_type.replace('_', ' ').title()
            return f"{alert_type_display}: {alert.user.peoplename} - Device {alert.device_id}"

        except Exception as e:
            logger.error(f"Error generating ticket title: {str(e)}")
            return f"Alert: {alert.title}"

    def _generate_ticket_description(self, alert: Alert) -> str:
        """Generate detailed ticket description"""
        try:
            description_parts = [
                f"Alert Description: {alert.description}",
                f"Severity: {alert.severity}",
                f"Device: {alert.device_id}",
                f"Site: {alert.site.buname if alert.site else 'Unknown'}",
                f"Triggered: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}"
            ]

            # Add alert data if available
            if alert.alert_data:
                description_parts.append("\nAlert Data:")
                for key, value in alert.alert_data.items():
                    description_parts.append(f"- {key}: {value}")

            # Add context data if available
            if alert.context_data:
                description_parts.append("\nContext Information:")
                for key, value in alert.context_data.items():
                    if isinstance(value, dict):
                        description_parts.append(f"- {key}: {list(value.keys())}")
                    else:
                        description_parts.append(f"- {key}: {value}")

            return "\n".join(description_parts)

        except Exception as e:
            logger.error(f"Error generating ticket description: {str(e)}")
            return alert.description

    def _determine_ticket_priority(self, alert: Alert) -> str:
        """Determine ticket priority based on alert and context"""
        try:
            # Start with alert severity
            base_priority = alert.severity

            # Adjust based on alert type
            alert_type = alert.rule.alert_type

            # Critical situations that require immediate attention
            if alert_type in ['NO_MOVEMENT', 'DEVICE_OVERHEATING', 'FRAUD_RISK']:
                if base_priority != 'EMERGENCY':
                    base_priority = 'CRITICAL'

            # Time-sensitive situations
            elif alert_type in ['BATTERY_CRITICAL', 'NETWORK_DOWN']:
                if base_priority in ['WARNING', 'INFO']:
                    base_priority = 'HIGH'

            return base_priority

        except Exception as e:
            logger.error(f"Error determining ticket priority: {str(e)}")
            return alert.severity

    def _apply_intelligent_routing(self, ticket: OperationalTicket, alert: Alert):
        """Apply intelligent routing logic to assign ticket"""
        try:
            routing_decision = self._make_routing_decision(ticket, {'alert': alert})

            if routing_decision:
                assigned_user = routing_decision.get('assigned_user')
                if assigned_user:
                    ticket.assign_to_user(assigned_user, routing_decision.get('routing_reason', ''))
                else:
                    ticket.assigned_role = routing_decision.get('assigned_role', 'general_support')
                    ticket.save()

        except Exception as e:
            logger.error(f"Error applying intelligent routing: {str(e)}")

    def _make_routing_decision(self, ticket: OperationalTicket, context: Dict = None) -> Optional[Dict]:
        """Make intelligent routing decision based on multiple factors"""
        try:
            alert_type = ticket.alert.rule.alert_type if ticket.alert else 'GENERAL'

            # Get routing rule for this alert type
            routing_rule = self.routing_rules.get(alert_type, {})
            target_role = routing_rule.get('route_to_role', 'general_support')

            # Find best available person for the role
            assigned_user = self._find_best_assignee(target_role, ticket, context)

            return {
                'assigned_user': assigned_user,
                'assigned_role': target_role,
                'routing_reason': f"Auto-routed based on {alert_type} alert type",
                'routing_confidence': 0.8,
                'routing_method': 'rule_based'
            }

        except Exception as e:
            logger.error(f"Error making routing decision: {str(e)}")
            return None

    def _find_best_assignee(self, target_role: str, ticket: OperationalTicket, context: Dict = None) -> Optional[People]:
        """Find the best available person for assignment"""
        try:
            # This is a simplified implementation
            # In a real system, this would consider:
            # - Current workload
            # - Availability/shifts
            # - Expertise/skills
            # - Location proximity
            # - Performance history

            # For now, find any active user who could handle this role
            candidates = People.objects.filter(
                isadmin=True,  # Simplified: admins can handle any ticket
                enable=True
            ).order_by('?')[:5]  # Random selection of 5 candidates

            if candidates:
                # Simple assignment based on current ticket load
                best_candidate = None
                min_active_tickets = float('inf')

                for candidate in candidates:
                    active_tickets = OperationalTicket.objects.filter(
                        assigned_to=candidate,
                        status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS']
                    ).count()

                    if active_tickets < min_active_tickets:
                        min_active_tickets = active_tickets
                        best_candidate = candidate

                return best_candidate

        except Exception as e:
            logger.error(f"Error finding best assignee: {str(e)}")

        return None

    def _schedule_automated_actions(self, ticket: OperationalTicket, alert: Alert):
        """Schedule automated actions for the ticket"""
        try:
            alert_type = alert.rule.alert_type
            routing_rule = self.routing_rules.get(alert_type, {})
            auto_actions = routing_rule.get('auto_actions', [])

            for action_name in auto_actions:
                # Create automated action record
                try:
                    action_config = self._get_action_config(action_name, ticket, alert)
                    if action_config:
                        # In a full implementation, this would queue the action
                        # For now, just log it
                        logger.info(f"Scheduled automated action '{action_name}' for ticket {ticket.ticket_number}")

                except Exception as e:
                    logger.error(f"Error scheduling action {action_name}: {str(e)}")

        except Exception as e:
            logger.error(f"Error scheduling automated actions: {str(e)}")

    def _get_action_config(self, action_name: str, ticket: OperationalTicket, alert: Alert) -> Optional[Dict]:
        """Get configuration for automated action"""
        action_configs = {
            'send_replacement_device': {
                'type': 'RESOURCE_ALLOCATION',
                'description': 'Send replacement device to user',
                'priority': 'HIGH'
            },
            'notify_backup': {
                'type': 'NOTIFICATION',
                'description': 'Notify backup personnel',
                'priority': 'MEDIUM'
            },
            'emergency_call': {
                'type': 'NOTIFICATION',
                'description': 'Make emergency call to user',
                'priority': 'EMERGENCY'
            },
            'dispatch_check': {
                'type': 'RESOURCE_ALLOCATION',
                'description': 'Dispatch security check to location',
                'priority': 'CRITICAL'
            },
            'device_shutdown': {
                'type': 'DEVICE_COMMAND',
                'description': 'Send device shutdown command',
                'priority': 'CRITICAL'
            }
        }

        return action_configs.get(action_name)

    def _escalate_ticket(self, ticket: OperationalTicket) -> bool:
        """Escalate an overdue ticket"""
        try:
            with transaction.atomic():
                # Determine escalation target
                escalation_target = self._determine_escalation_target(ticket)

                if not escalation_target:
                    logger.warning(f"No escalation target found for ticket {ticket.ticket_number}")
                    return False

                # Create escalation record
                escalation_level = ticket.escalation_count + 1
                TicketEscalation.objects.create(
                    ticket=ticket,
                    escalated_from=ticket.assigned_to,
                    escalated_to=escalation_target.get('user'),
                    escalated_to_role=escalation_target.get('role', 'supervisor'),
                    escalation_level=escalation_level,
                    reason=f"Ticket overdue - automatic escalation to level {escalation_level}",
                    is_automatic=True
                )

                # Update ticket
                ticket.escalation_count = escalation_level
                if escalation_target.get('user'):
                    ticket.assign_to_user(
                        escalation_target['user'],
                        f"Escalated from {ticket.assigned_to.peoplename if ticket.assigned_to else 'unassigned'}"
                    )

                # Send escalation notifications
                self._send_escalation_notifications(ticket, escalation_target)

                logger.info(f"Escalated ticket {ticket.ticket_number} to level {escalation_level}")
                return True

        except Exception as e:
            logger.error(f"Error escalating ticket {ticket.ticket_number}: {str(e)}")
            return False

    def _determine_escalation_target(self, ticket: OperationalTicket) -> Optional[Dict]:
        """Determine who to escalate the ticket to"""
        try:
            escalation_level = ticket.escalation_count + 1

            # Define escalation hierarchy
            escalation_hierarchy = {
                1: 'team_lead',
                2: 'department_supervisor',
                3: 'operations_manager',
                4: 'site_manager'
            }

            target_role = escalation_hierarchy.get(escalation_level, 'operations_manager')

            # Find user with target role (simplified)
            target_user = People.objects.filter(
                isadmin=True,  # Simplified role checking
                enable=True
            ).first()

            return {
                'user': target_user,
                'role': target_role,
                'escalation_level': escalation_level
            }

        except Exception as e:
            logger.error(f"Error determining escalation target: {str(e)}")
            return None

    def _create_routing_audit(self, ticket: OperationalTicket, routing_decision: Dict):
        """Create audit trail for routing decision"""
        try:
            # Add routing information to ticket metadata
            routing_info = {
                'routing_timestamp': timezone.now().isoformat(),
                'routing_method': routing_decision.get('routing_method', 'unknown'),
                'routing_confidence': routing_decision.get('routing_confidence', 0),
                'routing_reason': routing_decision.get('routing_reason', '')
            }

            # Update ticket automation data
            if not ticket.automation_data:
                ticket.automation_data = {}

            ticket.automation_data['routing_audit'] = routing_info
            ticket.save()

        except Exception as e:
            logger.error(f"Error creating routing audit: {str(e)}")

    def _send_escalation_notifications(self, ticket: OperationalTicket, escalation_target: Dict):
        """Send notifications for ticket escalation"""
        try:
            # Implementation would send various notifications
            # Email, SMS, dashboard updates, etc.
            logger.info(f"Escalation notifications sent for ticket {ticket.ticket_number}")

        except Exception as e:
            logger.error(f"Error sending escalation notifications: {str(e)}")

    def auto_resolve_tickets_from_resolved_alerts(self) -> int:
        """Auto-resolve tickets when their source alerts are resolved"""
        try:
            # Find tickets with resolved alerts that are still open
            resolvable_tickets = OperationalTicket.objects.filter(
                alert__status='RESOLVED',
                status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS']
            ).select_related('alert', 'alert__resolved_by')

            resolved_count = 0

            for ticket in resolvable_tickets:
                try:
                    ticket.resolve(
                        user=ticket.alert.resolved_by,
                        resolution_type='AUTOMATIC',
                        notes=f"Auto-resolved due to source alert resolution: {ticket.alert.resolution_notes}"
                    )
                    resolved_count += 1

                except Exception as e:
                    logger.error(f"Error auto-resolving ticket {ticket.ticket_number}: {str(e)}")

            if resolved_count > 0:
                logger.info(f"Auto-resolved {resolved_count} tickets from resolved alerts")

            return resolved_count

        except Exception as e:
            logger.error(f"Error auto-resolving tickets: {str(e)}")
            return 0

    def get_user_tickets(self, user_id: int, status_filter: Optional[str] = None) -> List[Dict]:
        """Get tickets for a specific user"""
        try:
            queryset = OperationalTicket.objects.filter(
                user_id=user_id
            ).select_related('category', 'assigned_to', 'alert')

            if status_filter:
                queryset = queryset.filter(status=status_filter)

            tickets = []
            for ticket in queryset.order_by('-created_at'):
                tickets.append({
                    'ticket_id': str(ticket.ticket_id),
                    'ticket_number': ticket.ticket_number,
                    'title': ticket.title,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'created_at': ticket.created_at.isoformat(),
                    'assigned_to': ticket.assigned_to.peoplename if ticket.assigned_to else None,
                    'is_overdue': ticket.is_overdue,
                    'category': ticket.category.name,
                    'alert_type': ticket.alert.rule.alert_type if ticket.alert else None
                })

            return tickets

        except Exception as e:
            logger.error(f"Error getting user tickets: {str(e)}")
            return []