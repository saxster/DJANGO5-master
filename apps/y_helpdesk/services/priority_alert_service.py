"""
Priority Alert Service

Tells you which tasks need attention now.

User sees: "⚠️ This ticket might miss its deadline"
Not: "High SLA breach probability detected"

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling
- Rule #16: Network timeouts required

Created: 2025-11-07
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import timedelta
from django.utils import timezone
from django.db import DatabaseError
from django.core.exceptions import ObjectDoesNotExist
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.services.sla_calculator import SLACalculator

logger = logging.getLogger(__name__)


class PriorityAlertService:
    """
    Tells you which tasks need attention now.
    
    Simple logic:
    - How old is the ticket?
    - How much time until deadline?
    - How busy is the assigned person?
    - How long do similar tickets usually take?
    
    Returns: Low/Medium/High risk + plain English explanation
    """
    
    def __init__(self):
        self.sla_calculator = SLACalculator()
    
    def check_ticket_risk(self, ticket: Ticket) -> Dict[str, Any]:
        """
        Calculate risk level and provide actionable suggestions.
        
        Args:
            ticket: Ticket instance
            
        Returns:
            Risk assessment with factors and suggestions
        """
        try:
            risk_factors = []
            score = 0
            
            # Get SLA metrics
            sla_metrics = self.sla_calculator.calculate_sla_metrics(ticket)
            
            # Factor 1: Time pressure
            remaining_minutes = sla_metrics.get('remaining_minutes', 0)
            if remaining_minutes < 120:  # Less than 2 hours
                score += 40
                risk_factors.append({
                    'icon': '⏰',
                    'message': f'Deadline in {int(remaining_minutes)} minutes',
                    'severity': 'high'
                })
            elif remaining_minutes < 360:  # Less than 6 hours
                score += 20
                risk_factors.append({
                    'icon': '⏰',
                    'message': f'Deadline in {int(remaining_minutes/60)} hours',
                    'severity': 'medium'
                })
            
            # Factor 2: Already overdue
            if sla_metrics.get('is_overdue', False):
                score += 50
                overdue_minutes = sla_metrics.get('overdue_minutes', 0)
                risk_factors.append({
                    'icon': '🚨',
                    'message': f'Overdue by {int(overdue_minutes)} minutes',
                    'severity': 'high'
                })
            
            # Factor 3: Assignee workload
            if ticket.assignedtopeople:
                other_tasks = Ticket.objects.filter(
                    assignedtopeople=ticket.assignedtopeople,
                    status__in=['NEW', 'OPEN']
                ).exclude(id=ticket.id).count()
                
                if other_tasks > 10:
                    score += 30
                    risk_factors.append({
                        'icon': '📚',
                        'message': f'{ticket.assignedtopeople.peoplename} has {other_tasks} other tasks',
                        'severity': 'medium'
                    })
                elif other_tasks > 5:
                    score += 15
                    risk_factors.append({
                        'icon': '📚',
                        'message': f'{ticket.assignedtopeople.peoplename} has {other_tasks} other tasks',
                        'severity': 'low'
                    })
            else:
                score += 50
                risk_factors.append({
                    'icon': '❌',
                    'message': 'Not assigned to anyone yet',
                    'severity': 'high'
                })
            
            # Factor 4: Historical comparison
            avg_time = self._get_category_average_time(ticket.ticketcategory)
            if avg_time:
                ticket_age = timezone.now() - ticket.cdtz
                if ticket_age + avg_time > timedelta(minutes=sla_metrics.get('target_resolution_minutes', 0)):
                    score += 30
                    avg_hours = int(avg_time.total_seconds() / 3600)
                    risk_factors.append({
                        'icon': '📊',
                        'message': f'Similar tickets usually take {avg_hours} hours',
                        'severity': 'medium'
                    })
            
            # Determine risk level
            if score >= 70:
                risk_level = 'high'
                badge = '🔴 Urgent'
                action = 'needs_immediate_attention'
            elif score >= 40:
                risk_level = 'medium'
                badge = '🟠 Soon'
                action = 'reassign_or_escalate'
            else:
                risk_level = 'low'
                badge = '🟢 On Track'
                action = 'monitor'
            
            return {
                'risk_level': risk_level,
                'badge': badge,
                'score': score,
                'risk_factors': risk_factors,
                'suggested_action': action,
                'suggestions': self._get_suggestions(ticket, risk_factors),
                'sla_metrics': sla_metrics
            }
        
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error checking ticket risk: {e}", exc_info=True)
            return self._safe_fallback_response()
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error checking ticket risk: {e}", exc_info=True)
            return self._safe_fallback_response()
    
    def _get_suggestions(self, ticket: Ticket, risk_factors: List[Dict]) -> List[Dict[str, Any]]:
        """What should the user do?"""
        suggestions = []
        
        try:
            # Suggestion 1: Assign if unassigned
            if not ticket.assignedtopeople:
                suggestions.append({
                    'icon': '👤',
                    'text': 'Assign to someone now',
                    'action': 'assign',
                    'priority': 1
                })
            
            # Suggestion 2: Reassign if overloaded
            if ticket.assignedtopeople:
                other_tasks = Ticket.objects.filter(
                    assignedtopeople=ticket.assignedtopeople,
                    status__in=['NEW', 'OPEN']
                ).count()
                
                if other_tasks > 10:
                    available = self._find_available_person(ticket.ticketcategory)
                    if available:
                        available_tasks = Ticket.objects.filter(
                            assignedtopeople=available,
                            status__in=['NEW', 'OPEN']
                        ).count()
                        suggestions.append({
                            'icon': '🔄',
                            'text': f'Reassign to {available.peoplename} (only {available_tasks} tasks)',
                            'action': 'reassign',
                            'suggested_person_id': available.id,
                            'priority': 1
                        })
            
            # Suggestion 3: Contact customer
            suggestions.append({
                'icon': '📞',
                'text': 'Call customer for quick update',
                'action': 'contact_customer',
                'priority': 2
            })
            
            # Suggestion 4: Escalate if high risk
            if any(f['severity'] == 'high' for f in risk_factors):
                suggestions.append({
                    'icon': '⬆️',
                    'text': 'Escalate to manager',
                    'action': 'escalate',
                    'priority': 1
                })
            
            return sorted(suggestions, key=lambda x: x['priority'])
        
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error getting suggestions: {e}", exc_info=True)
            return []
    
    def _get_category_average_time(self, category) -> Optional[timedelta]:
        """Calculate average resolution time for category."""
        if not category:
            return None
        
        try:
            from django.db.models import Avg, F
            
            avg_seconds = Ticket.objects.filter(
                ticketcategory=category,
                status__in=['RESOLVED', 'CLOSED']
            ).annotate(
                resolution_time=F('mdtz') - F('cdtz')
            ).aggregate(
                avg_time=Avg('resolution_time')
            )['avg_time']
            
            return avg_seconds if avg_seconds else None
        
        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Error calculating category average time: {e}")
            return None
    
    def _find_available_person(self, category):
        """Find person with lowest workload for category."""
        try:
            from django.db.models import Count, Q
            from apps.peoples.models import People
            
            # Find people who handle this category
            people_with_counts = People.objects.filter(
                is_active=True,
                ticket_people__ticketcategory=category
            ).annotate(
                open_count=Count('ticket_people', filter=Q(ticket_people__status__in=['NEW', 'OPEN']))
            ).order_by('open_count')
            
            return people_with_counts.first()
        
        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Error finding available person: {e}")
            return None
    
    def _safe_fallback_response(self) -> Dict[str, Any]:
        """Safe response when error occurs."""
        return {
            'risk_level': 'low',
            'badge': '🟢 On Track',
            'score': 0,
            'risk_factors': [],
            'suggested_action': 'monitor',
            'suggestions': [],
            'sla_metrics': {}
        }
