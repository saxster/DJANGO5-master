"""
Priority Alert Celery Tasks

Run every 10 minutes to find tasks at risk.
Send friendly notifications.

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling
- Celery Configuration Guide: Proper decorator usage

Created: 2025-11-07
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import DatabaseError
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.models.sla_prediction import SLAPrediction
from apps.y_helpdesk.services.priority_alert_service import PriorityAlertService

logger = logging.getLogger(__name__)


@shared_task(
    name='y_helpdesk.check_priority_alerts',
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    queue='default'
)
def check_priority_alerts(self):
    """
    Run every 10 minutes to find tasks at risk.
    Send friendly notifications.
    
    Returns:
        str: Summary of checks performed
    """
    try:
        service = PriorityAlertService()
        
        # Check open tickets with tenant isolation
        tickets = Ticket.objects.filter(
            status__in=['NEW', 'OPEN'],
            is_active=True
        ).select_related(
            'assignedtopeople',
            'ticketcategory',
            'bu',
            'client'
        )
        
        alerts_sent = 0
        predictions_updated = 0
        
        for ticket in tickets:
            try:
                # Calculate risk
                risk = service.check_ticket_risk(ticket)
                
                # Update or create prediction
                prediction, created = SLAPrediction.objects.update_or_create(
                    item_type='Ticket',
                    item_id=ticket.id,
                    defaults={
                        'risk_level': risk['risk_level'],
                        'confidence': risk['score'],
                        'risk_factors': risk['risk_factors'],
                        'suggested_actions': risk['suggestions'],
                        'tenant': ticket.tenant,
                        'bu': ticket.bu,
                        'client': ticket.client,
                        'cuser': ticket.cuser,
                        'muser': ticket.muser
                    }
                )
                predictions_updated += 1
                
                # Send notification if HIGH risk and not acknowledged
                if risk['risk_level'] == 'high' and not prediction.is_acknowledged:
                    # Don't spam - only send if we haven't sent recently
                    if not prediction.alert_sent_at or \
                       (timezone.now() - prediction.alert_sent_at) > timedelta(hours=2):
                        send_priority_alert.delay(ticket.id, risk)
                        prediction.alert_sent_at = timezone.now()
                        prediction.save(update_fields=['alert_sent_at'])
                        alerts_sent += 1
            
            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error processing ticket {ticket.id}: {e}", exc_info=True)
                continue
            except (ValueError, TypeError, AttributeError) as e:
                logger.error(f"Error processing ticket {ticket.id}: {e}", exc_info=True)
                continue
        
        summary = f"Checked {tickets.count()} tickets, updated {predictions_updated} predictions, sent {alerts_sent} alerts"
        logger.info(summary)
        return summary
    
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error in check_priority_alerts: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Unexpected error in check_priority_alerts: {e}", exc_info=True)
        raise


@shared_task(
    name='y_helpdesk.send_priority_alert',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='notifications'
)
def send_priority_alert(self, ticket_id: int, risk_info: dict):
    """
    Send user-friendly alert.
    
    Args:
        ticket_id: Ticket ID
        risk_info: Risk assessment data
        
    Returns:
        str: Status message
    """
    try:
        ticket = Ticket.objects.select_related(
            'assignedtopeople',
            'bu',
            'client'
        ).get(id=ticket_id)
        
        # Email to assignee
        if ticket.assignedtopeople and ticket.assignedtopeople.email:
            assignee_name = ticket.assignedtopeople.peoplename or ticket.assignedtopeople.email
            
            # Build risk factors message
            risk_factors_text = '\n'.join([
                f"  • {factor['message']}"
                for factor in risk_info.get('risk_factors', [])
            ])
            
            # Build suggestions message
            suggestions_text = '\n'.join([
                f"  {i+1}. {suggestion['text']}"
                for i, suggestion in enumerate(risk_info.get('suggestions', []))
            ])
            
            email_body = f"""
Hi {assignee_name},

This ticket might miss its deadline:

{ticket.ticketdesc[:200]}{'...' if len(ticket.ticketdesc) > 200 else ''}

Here's why we're worried:
{risk_factors_text or '  • Time is running out'}

What you can do:
{suggestions_text or '  1. Review and take action'}

View ticket: {settings.SITE_URL}/admin/y_helpdesk/ticket/{ticket.id}/change/

Need help? Reply to this email.

---
This is an automated alert from the Priority Alert system.
"""
            
            try:
                send_mail(
                    subject=f"⚠️ Ticket #{ticket.ticketno} needs attention",
                    message=email_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[ticket.assignedtopeople.email],
                    fail_silently=False
                )
                logger.info(f"Priority alert sent for ticket {ticket.ticketno} to {ticket.assignedtopeople.email}")
                return f"Alert sent to {ticket.assignedtopeople.email}"
            
            except Exception as e:
                logger.error(f"Error sending email for ticket {ticket.ticketno}: {e}", exc_info=True)
                raise self.retry(exc=e)
        else:
            logger.warning(f"No assignee or email for ticket {ticket.ticketno}")
            return "No assignee to notify"
    
    except Ticket.DoesNotExist:
        logger.error(f"Ticket {ticket_id} not found")
        return f"Ticket {ticket_id} not found"
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error sending alert for ticket {ticket_id}: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Unexpected error sending alert for ticket {ticket_id}: {e}", exc_info=True)
        raise


@shared_task(
    name='y_helpdesk.cleanup_old_predictions',
    queue='low_priority'
)
def cleanup_old_predictions():
    """
    Clean up old predictions for closed/resolved tickets.
    Run daily.
    
    Returns:
        str: Cleanup summary
    """
    try:
        # Delete predictions for tickets resolved/closed > 30 days ago
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_predictions = SLAPrediction.objects.filter(
            item_type='Ticket',
            last_checked__lt=cutoff_date
        )
        
        # Verify tickets are actually closed
        from django.db.models import Q
        closed_ticket_ids = Ticket.objects.filter(
            id__in=old_predictions.values_list('item_id', flat=True),
            status__in=['RESOLVED', 'CLOSED', 'CANCEL']
        ).values_list('id', flat=True)
        
        deleted_count, _ = SLAPrediction.objects.filter(
            item_type='Ticket',
            item_id__in=closed_ticket_ids,
            last_checked__lt=cutoff_date
        ).delete()
        
        summary = f"Cleaned up {deleted_count} old predictions"
        logger.info(summary)
        return summary
    
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error cleaning up predictions: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error cleaning up predictions: {e}", exc_info=True)
        raise
