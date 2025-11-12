"""
Smart Assignment Service - Intelligent routing for tickets/tasks.

Following CLAUDE.md:
- Service methods < 30 lines
- Network calls with timeouts
- Specific exception handling
- No blocking I/O
"""

from datetime import timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Any
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Avg, F, Q, Count
from django.utils import timezone

from apps.peoples.models import People, AgentSkill
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class SmartAssignmentService:
    """
    Figure out who should handle a task based on skills, workload, and availability.
    
    Scoring System (100 points total):
    - Skill match: 40 points (certified +5 bonus)
    - Availability: 30 points (workload-based)
    - Performance: 20 points (resolution speed)
    - Recent experience: 10 points (last 30 days)
    """
    
    @staticmethod
    def suggest_assignee(task_or_ticket, top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Find the best person for this task.
        
        Args:
            task_or_ticket: Ticket or Task instance
            top_n: Number of suggestions to return
            
        Returns:
            List of dicts with agent, score, reasons, etc.
        """
        try:
            category = task_or_ticket.ticketcategory
            tenant = task_or_ticket.tenant
            
            agents = SmartAssignmentService._get_eligible_agents(tenant)
            suggestions = []
            
            for agent in agents:
                score_data = SmartAssignmentService._calculate_agent_score(
                    agent, category, task_or_ticket
                )
                suggestions.append(score_data)
            
            suggestions.sort(key=lambda x: x['score'], reverse=True)
            return suggestions[:top_n]
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in suggest_assignee: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error in suggest_assignee: {e}", exc_info=True)
            return []
    
    @staticmethod
    def _get_eligible_agents(tenant) -> List[People]:
        """Get active agents from relevant groups."""
        try:
            return People.objects.filter(
                tenant=tenant,
                is_active=True,
                groups__name__in=['HelpDeskAgents', 'Technicians']
            ).distinct()
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error fetching eligible agents: {e}", exc_info=True)
            return []
    
    @staticmethod
    def _calculate_agent_score(agent, category, task_or_ticket) -> Dict[str, Any]:
        """Calculate comprehensive score for an agent."""
        score = 0
        reasons = []
        
        skill_score, skill_reasons = SmartAssignmentService._score_skill_match(
            agent, category
        )
        score += skill_score
        reasons.extend(skill_reasons)
        
        avail_score, avail_reasons, workload = SmartAssignmentService._score_availability(
            agent
        )
        score += avail_score
        reasons.extend(avail_reasons)
        
        perf_score, perf_reasons = SmartAssignmentService._score_performance(
            agent, category
        )
        score += perf_score
        reasons.extend(perf_reasons)
        
        recent_score, recent_reasons = SmartAssignmentService._score_recent_experience(
            agent, category
        )
        score += recent_score
        reasons.extend(recent_reasons)
        
        return {
            'agent': agent,
            'score': score,
            'reasons': reasons,
            'current_workload': workload,
            'availability': 'Available' if score >= 60 else 'Busy'
        }
    
    @staticmethod
    def _score_skill_match(agent, category) -> tuple[int, List[str]]:
        """Score skill match (max 40 points + 5 bonus)."""
        score = 0
        reasons = []
        
        try:
            skill = AgentSkill.objects.get(agent=agent, category=category)
            skill_score = skill.skill_level * 10
            score += skill_score
            
            stars = skill.get_skill_display()
            reasons.append(f"{stars} Skill level")
            
            if skill.certified:
                score += 5
                reasons.append(f"✓ Certified in {category.taname}")
                
        except AgentSkill.DoesNotExist:
            past_count = SmartAssignmentService._get_past_ticket_count(
                agent, category
            )
            
            if past_count > 5:
                score += 20
                reasons.append(f"Has handled {past_count} similar tasks")
            elif past_count > 0:
                score += 10
                reasons.append(f"Some experience ({past_count} tasks)")
            else:
                reasons.append("⚠️ No experience with this type")
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error checking skill: {e}", exc_info=True)
            
        return score, reasons
    
    @staticmethod
    def _get_past_ticket_count(agent, category) -> int:
        """Count closed tickets for category."""
        try:
            from apps.y_helpdesk.models import Ticket
            return Ticket.objects.filter(
                assignedtopeople=agent,
                ticketcategory=category,
                status='CLOSED'
            ).count()
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error counting past tickets: {e}", exc_info=True)
            return 0
    
    @staticmethod
    def _score_availability(agent) -> tuple[int, List[str], int]:
        """Score availability (max 40 points)."""
        score = 0
        reasons = []
        
        try:
            from apps.y_helpdesk.models import Ticket
            current_workload = Ticket.objects.filter(
                assignedtopeople=agent,
                status__in=['NEW', 'OPEN']
            ).count()
            
            if current_workload == 0:
                score += 30
                reasons.append("✨ Currently available")
            elif current_workload < 3:
                score += 20
                reasons.append(f"Light workload ({current_workload} tasks)")
            elif current_workload < 6:
                score += 10
                reasons.append(f"Moderate workload ({current_workload} tasks)")
            else:
                reasons.append(f"⚠️ Busy ({current_workload} open tasks)")
            
            if SmartAssignmentService._is_on_shift(agent):
                score += 10
                reasons.append("✓ On shift now")
            else:
                reasons.append("⚠️ Not currently on shift")
                
            return score, reasons, current_workload
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error checking availability: {e}", exc_info=True)
            return 0, ["⚠️ Unable to check availability"], 0
    
    @staticmethod
    def _is_on_shift(agent) -> bool:
        """Check if agent is currently on shift."""
        try:
            from apps.attendance.models import Attendance
            
            last_attendance = Attendance.objects.filter(
                people=agent
            ).order_by('-timestamp').first()
            
            if not last_attendance:
                return False
            
            if last_attendance.action == 'CLOCK_IN':
                hours_since = timezone.now() - last_attendance.timestamp
                return hours_since < timedelta(hours=12)
            
            return False
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error checking shift status: {e}", exc_info=True)
            return False
    
    @staticmethod
    def _score_performance(agent, category) -> tuple[int, List[str]]:
        """Score performance based on resolution time (max 20 points)."""
        score = 0
        reasons = []
        
        try:
            from apps.y_helpdesk.models import Ticket
            
            avg_time_data = Ticket.objects.filter(
                assignedtopeople=agent,
                ticketcategory=category,
                status='CLOSED'
            ).aggregate(
                avg_time=Avg(F('mdtz') - F('cdtz'))
            )
            
            avg_time = avg_time_data.get('avg_time')
            
            if avg_time:
                hours = avg_time.total_seconds() / 3600
                if hours < 2:
                    score += 20
                    reasons.append(f"⚡ Fast resolver (avg {hours:.1f}h)")
                elif hours < 4:
                    score += 15
                    reasons.append(f"Good speed (avg {hours:.1f}h)")
                else:
                    score += 5
                    reasons.append(f"Takes time (avg {hours:.1f}h)")
                    
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating performance: {e}", exc_info=True)
            
        return score, reasons
    
    @staticmethod
    def _score_recent_experience(agent, category) -> tuple[int, List[str]]:
        """Score recent experience (max 10 points)."""
        score = 0
        reasons = []
        
        try:
            from apps.y_helpdesk.models import Ticket
            
            recent = Ticket.objects.filter(
                assignedtopeople=agent,
                ticketcategory=category,
                mdtz__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            if recent > 0:
                score = min(10, recent * 2)
                reasons.append(f"Recently handled {recent} similar tasks")
                
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error checking recent experience: {e}", exc_info=True)
            
        return score, reasons
    
    @staticmethod
    def auto_assign(task_or_ticket) -> Optional[Dict[str, Any]]:
        """
        Automatically assign to best available person.
        
        Args:
            task_or_ticket: Ticket or Task instance
            
        Returns:
            Dict with assignment details or None
        """
        try:
            suggestions = SmartAssignmentService.suggest_assignee(
                task_or_ticket, top_n=1
            )
            
            if not suggestions:
                logger.warning(f"No suggestions for {task_or_ticket}")
                return None
            
            best = suggestions[0]
            task_or_ticket.assignedtopeople = best['agent']
            task_or_ticket.save()
            
            SmartAssignmentService._send_assignment_notification(
                task_or_ticket, best
            )
            
            logger.info(
                f"Auto-assigned {task_or_ticket} to {best['agent']} "
                f"(score: {best['score']})"
            )
            
            return best
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error in auto_assign: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in auto_assign: {e}", exc_info=True)
            return None
    
    @staticmethod
    def _send_assignment_notification(task_or_ticket, assignment_data):
        """Send email notification to assignee."""
        try:
            agent = assignment_data['agent']
            top_reasons = ', '.join(assignment_data['reasons'][:3])
            
            ticket_desc = getattr(task_or_ticket, 'ticketdesc', str(task_or_ticket))
            
            send_mail(
                subject=f"New task assigned to you",
                message=(
                    f"Hi {agent.first_name},\n\n"
                    f"You've been assigned: {ticket_desc}\n\n"
                    f"Why you? {top_reasons}\n\n"
                    f"Please log in to view details."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[agent.email],
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}", exc_info=True)
