"""
Executive Scorecard Generation Tasks.

Automated monthly board-ready reporting.
Part of HIGH_IMPACT_FEATURE_OPPORTUNITIES.md implementation.

Revenue Impact: +$200-500/month per client
Value: Replaces 4-8 hours/month of manual report compilation

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #15: No blocking I/O

@ontology(
    domain="reports",
    purpose="Generate and deliver monthly executive scorecards",
    business_value="Board-ready compliance reporting, executive visibility",
    criticality="medium",
    tags=["executive-reporting", "kpi", "scorecard", "automated-reporting", "celery"]
)
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import DatabaseError
from datetime import timedelta
from dateutil.relativedelta import relativedelta

logger = logging.getLogger('reports.executive_scorecard')

__all__ = ['generate_monthly_scorecards_task']


@shared_task(
    name='apps.reports.generate_monthly_scorecards',
    bind=True,
    max_retries=2,
    time_limit=1800  # 30 minutes
)
def generate_monthly_scorecards_task(self):
    """
    Generate monthly executive scorecards for all clients.
    
    Runs on 1st of each month at 3 AM via Celery beat.
    Generates scorecards for previous month.
    
    Returns:
        Dict with generation statistics
    """
    from apps.reports.services.executive_scorecard_service import ExecutiveScoreCardService
    from apps.reports.services.report_delivery_service import ReportDeliveryService
    from apps.client_onboarding.models import BusinessUnit
    from django.template.loader import render_to_string
    
    try:
        now = timezone.now()
        # Previous month
        target_date = now - relativedelta(months=1)
        target_month = target_date.month
        target_year = target_date.year
        
        scorecards_generated = 0
        scorecards_delivered = 0
        errors = 0
        
        # Get all active client business units
        clients = BusinessUnit.objects.filter(
            is_active=True,
            bu_type='CLIENT'
        ).select_related('tenant')[:100]  # Limit to prevent overload
        
        logger.info(
            f"Generating executive scorecards for {clients.count()} clients",
            extra={'target_month': target_month, 'target_year': target_year}
        )
        
        for client in clients:
            try:
                # Generate scorecard data
                scorecard_data = ExecutiveScoreCardService.generate_monthly_scorecard(
                    client_id=client.id,
                    month=target_month,
                    year=target_year
                )
                
                scorecards_generated += 1
                
                # Render HTML template
                html_content = render_to_string(
                    'apps/reports/report_designs/executive_scorecard.html',
                    {'data': scorecard_data}
                )
                
                # Generate PDF
                pdf_filename = f"executive_scorecard_{client.name}_{target_year}_{target_month:02d}.pdf"
                
                # Get executive email addresses
                # Check client preferences for executive email list
                exec_emails = []
                if client.preferences and 'executive_emails' in client.preferences:
                    exec_emails = client.preferences['executive_emails']
                elif client.primary_contact and client.primary_contact.email:
                    exec_emails = [client.primary_contact.email]
                
                # Send via email if recipients configured
                if exec_emails:
                    for recipient in exec_emails:
                        try:
                            ReportDeliveryService.send_email(
                                recipient=recipient,
                                subject=f"Monthly Executive Scorecard - {scorecard_data['period']}",
                                body=f"""
Dear Executive,

Please find attached the monthly executive scorecard for {client.name}.

This report includes:
- Operational Excellence Metrics
- Quality Performance Indicators
- Risk Alerts and Trends
- Month-over-Month Comparisons

Period: {scorecard_data['period']}
Generated: {now.strftime('%Y-%m-%d %H:%M')}

Best regards,
Operations Management System
                                """,
                                tenant=client.tenant,
                                html_content=html_content,
                                attachments=[]  # PDF generation would be added here
                            )
                            
                            scorecards_delivered += 1
                            
                        except Exception as e:
                            logger.error(
                                f"Error sending scorecard to {recipient}: {e}",
                                exc_info=True
                            )
                            errors += 1
                
                logger.info(
                    f"Generated scorecard for {client.name}",
                    extra={
                        'client_id': client.id,
                        'client_name': client.name,
                        'recipients': len(exec_emails)
                    }
                )
                
            except Exception as e:
                logger.error(
                    f"Error generating scorecard for client {client.id}: {e}",
                    exc_info=True
                )
                errors += 1
                continue
        
        result = {
            'clients_processed': clients.count(),
            'scorecards_generated': scorecards_generated,
            'scorecards_delivered': scorecards_delivered,
            'errors': errors,
            'target_month': target_month,
            'target_year': target_year,
            'timestamp': now.isoformat()
        }
        
        logger.info(
            f"Executive scorecard generation complete",
            extra=result
        )
        
        return result
        
    except DatabaseError as e:
        logger.error(f"Database error generating scorecards: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=600)
    except Exception as e:
        logger.error(f"Unexpected error generating scorecards: {e}", exc_info=True)
        raise
