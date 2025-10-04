"""
Non-Negotiables Daily Evaluation Tasks.

Celery tasks for automated daily scorecard generation and violation monitoring.
Follows .claude/rules.md Rule #11 (specific exception handling).
"""

import logging
from datetime import date, timedelta
from typing import List, Dict, Any

from celery import Task
from django.db import DatabaseError
from django.utils import timezone

from apps.core.tasks.base import IdempotentTask
from apps.noc.security_intelligence.services import NonNegotiablesService
from apps.noc.security_intelligence.models import NonNegotiablesScorecard
from apps.onboarding.models import Bt
from apps.tenants.models import Tenant

logger = logging.getLogger('background_tasks.non_negotiables')


class EvaluateNonNegotiablesTask(IdempotentTask):
    """
    Daily evaluation of non-negotiables for all active clients.

    Runs at 6:00 AM daily to generate scorecards and create alerts.
    Uses IdempotentTask to prevent duplicate evaluations.
    """

    name = 'evaluate_non_negotiables'
    idempotency_scope = 'global'  # One evaluation per day globally
    idempotency_ttl = 3600 * 20  # 20 hours (prevents re-run within same day)

    def run(self, check_date_str=None, tenant_id=None, client_ids=None):
        """
        Execute daily non-negotiables evaluation.

        Args:
            check_date_str: Date to evaluate (YYYY-MM-DD), defaults to today
            tenant_id: Optional tenant ID to limit evaluation
            client_ids: Optional list of client IDs to evaluate

        Returns:
            dict: Summary of evaluation results
        """
        try:
            # Parse check_date
            if check_date_str:
                from datetime import datetime
                check_date = datetime.strptime(check_date_str, '%Y-%m-%d').date()
            else:
                check_date = date.today()

            logger.info(f"Starting non-negotiables evaluation for {check_date}")

            # Get tenants to evaluate
            if tenant_id:
                tenants = Tenant.objects.filter(id=tenant_id)
            else:
                tenants = Tenant.objects.filter(is_active=True)

            results = {
                'check_date': check_date.isoformat(),
                'tenants_evaluated': 0,
                'clients_evaluated': 0,
                'scorecards_generated': 0,
                'alerts_created': 0,
                'errors': [],
            }

            service = NonNegotiablesService()

            for tenant in tenants:
                try:
                    # Get active clients for this tenant
                    if client_ids:
                        clients = Bt.objects.filter(
                            tenant=tenant,
                            id__in=client_ids,
                            isactive=True
                        )
                    else:
                        # Get all top-level clients (not sites)
                        clients = Bt.objects.filter(
                            tenant=tenant,
                            isactive=True,
                            client_id__isnull=True  # Only top-level clients
                        )

                    results['tenants_evaluated'] += 1

                    for client in clients:
                        try:
                            # Generate scorecard
                            scorecard = service.generate_scorecard(
                                tenant=tenant,
                                client=client,
                                check_date=check_date
                            )

                            results['clients_evaluated'] += 1
                            results['scorecards_generated'] += 1
                            results['alerts_created'] += len(scorecard.auto_escalated_alerts)

                            logger.info(
                                f"Generated scorecard for {client.buname}: "
                                f"{scorecard.overall_health_status} ({scorecard.overall_health_score}/100)"
                            )

                        except DatabaseError as e:
                            error_msg = f"Database error for client {client.buname}: {e}"
                            logger.error(error_msg, exc_info=True)
                            results['errors'].append(error_msg)

                except DatabaseError as e:
                    error_msg = f"Database error for tenant {tenant.name}: {e}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'].append(error_msg)

            logger.info(
                f"Completed non-negotiables evaluation: "
                f"{results['scorecards_generated']} scorecards, "
                f"{results['alerts_created']} alerts, "
                f"{len(results['errors'])} errors"
            )

            return results

        except ValueError as e:
            logger.error(f"Invalid parameters: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error in non-negotiables evaluation: {e}", exc_info=True)
            raise


# Create task instance
evaluate_non_negotiables = EvaluateNonNegotiablesTask()
