"""
SLA Breach Prevention Tasks.

Proactive SLA breach prediction and auto-escalation.
Part of HIGH_IMPACT_FEATURE_OPPORTUNITIES.md implementation.

Revenue Impact: +$75-150/month per site
ROI: Prevent 2 breaches/month = $2,000-10,000 saved

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #15: No blocking I/O
- Rule #16: Network timeouts required

@ontology(
    domain="helpdesk",
    purpose="Predict and prevent SLA breaches 2 hours in advance",
    business_value="95%+ on-time resolution, prevent SLA penalties",
    criticality="high",
    tags=["sla", "prediction", "proactive", "escalation", "celery"]
)
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import DatabaseError
from django.conf import settings
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('sla.prevention')

__all__ = ['predict_sla_breaches_task', 'auto_escalate_at_risk_tickets']


@shared_task(
    name='apps.helpdesk.predict_sla_breaches',
    bind=True,
    max_retries=3,
    time_limit=300
)
def predict_sla_breaches_task(self):
    """
    Run SLA breach prediction on open tickets.
    Create proactive alerts for high-risk tickets.
    
    Runs every 15 minutes via Celery beat.
    
    Returns:
        Dict with prediction counts and escalations
    """
    from apps.y_helpdesk.models import Ticket
    from apps.noc.ml.predictive_models.sla_breach_predictor import SLABreachPredictor
    from apps.noc.models import NOCAlertEvent
    
    try:
        tickets_analyzed = 0
        high_risk_count = 0
        escalated_count = 0
        
        # Get open tickets with SLA policy
        tickets = Ticket.objects.filter(
            status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS'],
            sla_policy__isnull=False
        ).select_related('sla_policy', 'assignee', 'bu', 'client', 'tenant')[:500]
        
        logger.info(f"Analyzing {tickets.count()} tickets for SLA breach risk")
        
        for ticket in tickets:
            tickets_analyzed += 1
            
            try:
                # Predict breach probability
                probability, features = SLABreachPredictor.predict_breach(ticket)
                
                # Store prediction in ticket metadata
                if not ticket.other_data:
                    ticket.other_data = {}
                ticket.other_data['sla_risk_score'] = probability
                ticket.other_data['sla_risk_features'] = features
                ticket.other_data['sla_risk_checked_at'] = timezone.now().isoformat()
                
                # High risk threshold: 70%
                if probability >= 0.70:
                    high_risk_count += 1
                    
                    # Create proactive NOC alert
                    NOCAlertEvent.objects.create(
                        tenant=ticket.tenant,
                        client=ticket.client,
                        bu=ticket.bu,
                        alert_type='SLA_BREACH_RISK',
                        severity='HIGH' if probability >= 0.85 else 'MEDIUM',
                        title=f"SLA Breach Risk: {ticket.ticketdesc[:50]}",
                        description=f"Ticket #{ticket.id} has {probability:.0%} probability of SLA breach. "
                                   f"Time remaining: {features.get('time_until_sla_deadline_minutes', 0):.0f} minutes. "
                                   f"Assigned: {ticket.assignee.get_full_name() if ticket.assignee else 'Unassigned'}",
                        source='SLA_PREDICTOR',
                        status='NEW',
                        other_data={
                            'ticket_id': ticket.id,
                            'breach_probability': probability,
                            'features': features
                        }
                    )
                    
                    # Auto-escalate if very high risk (80%+) and still unassigned
                    if probability >= 0.80:
                        if not ticket.assignee or ticket.status == 'NEW':
                            ticket.status = 'ASSIGNED'
                            ticket.priority = 'CRITICAL'
                            escalated_count += 1
                            
                            logger.warning(
                                f"Auto-escalated ticket {ticket.id}",
                                extra={
                                    'ticket_id': ticket.id,
                                    'breach_probability': probability,
                                    'time_remaining': features.get('time_until_sla_deadline_minutes')
                                }
                            )
                    
                ticket.save(update_fields=['other_data', 'status', 'priority'])

            except (ValueError, TypeError, KeyError, AttributeError) as e:
                logger.error(
                    f"Validation error predicting SLA breach for ticket {ticket.id}: {e}",
                    exc_info=True
                )
                continue
            except DATABASE_EXCEPTIONS as e:
                logger.error(
                    f"Database error predicting SLA breach for ticket {ticket.id}: {e}",
                    exc_info=True
                )
                continue
        
        result = {
            'tickets_analyzed': tickets_analyzed,
            'high_risk_count': high_risk_count,
            'escalated_count': escalated_count,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(
            f"SLA prediction complete",
            extra=result
        )
        
        return result

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error in SLA prediction: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        logger.error(
            f"Validation error in SLA prediction: {e}",
            exc_info=True,
            extra={'error_type': type(e).__name__}
        )
        raise


@shared_task(
    name='apps.helpdesk.auto_escalate_at_risk_tickets',
    bind=True,
    max_retries=2
)
def auto_escalate_at_risk_tickets(self):
    """
    Escalate tickets with high SLA breach risk.
    
    Runs every 30 minutes via Celery beat.
    
    Returns:
        Dict with escalation counts
    """
    from apps.y_helpdesk.models import Ticket
    from apps.peoples.models import People
    
    try:
        escalated = 0
        
        # Find tickets with high risk score
        tickets = Ticket.objects.filter(
            status__in=['NEW', 'ASSIGNED'],
            other_data__sla_risk_score__gte=0.75
        ).select_related('assignee', 'tenant')[:100]
        
        for ticket in tickets:
            try:
                # Escalate priority
                if ticket.priority not in ['HIGH', 'CRITICAL']:
                    ticket.priority = 'HIGH'
                    ticket.save(update_fields=['priority'])
                    escalated += 1
                    
                    logger.info(
                        f"Escalated ticket {ticket.id} priority to HIGH",
                        extra={'ticket_id': ticket.id, 'risk_score': ticket.other_data.get('sla_risk_score')}
                    )

            except (ValueError, TypeError, KeyError, AttributeError) as e:
                logger.error(
                    f"Validation error escalating ticket {ticket.id}: {e}",
                    exc_info=True
                )
                continue
            except DATABASE_EXCEPTIONS as e:
                logger.error(
                    f"Database error escalating ticket {ticket.id}: {e}",
                    exc_info=True
                )
                continue
        
        return {
            'escalated_count': escalated,
            'timestamp': timezone.now().isoformat()
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error in auto-escalation: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        logger.error(
            f"Validation error in auto-escalation: {e}",
            exc_info=True,
            extra={'error_type': type(e).__name__}
        )
        raise
