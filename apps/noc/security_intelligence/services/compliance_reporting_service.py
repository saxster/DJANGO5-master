"""
Compliance Reporting Service.

Generates compliance metrics and reports for tasks and tours.
Provides SLA performance analytics.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q, F

logger = logging.getLogger('noc.security_intelligence')


class ComplianceReportingService:
    """Generates compliance reports and metrics."""

    @classmethod
    def get_task_compliance_summary(cls, tenant, days=30):
        """
        Get task compliance summary for period.

        Args:
            tenant: Tenant instance
            days: Days to analyze

        Returns:
            dict: Compliance metrics
        """
        from apps.activity.models import Jobneed

        try:
            since = timezone.now() - timedelta(days=days)

            tasks = Jobneed.objects.filter(
                tenant=tenant,
                cdtz__gte=since
            )

            total = tasks.count()
            completed = tasks.filter(status='COMPLETED').count()
            overdue = tasks.filter(
                status__in=['PENDING', 'IN_PROGRESS'],
                cdtz__lt=timezone.now() - timedelta(hours=1)
            ).count()

            return {
                'period_days': days,
                'total_tasks': total,
                'completed_tasks': completed,
                'overdue_tasks': overdue,
                'completion_rate': (completed / total * 100) if total > 0 else 0,
                'overdue_rate': (overdue / total * 100) if total > 0 else 0,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Task compliance summary error: {e}", exc_info=True)
            return {}

    @classmethod
    def get_tour_compliance_summary(cls, tenant, days=30):
        """
        Get tour compliance summary for period.

        Args:
            tenant: Tenant instance
            days: Days to analyze

        Returns:
            dict: Tour compliance metrics
        """
        from apps.noc.security_intelligence.models import TourComplianceLog

        try:
            since = timezone.now() - timedelta(days=days)

            tours = TourComplianceLog.objects.filter(
                tenant=tenant,
                scheduled_date__gte=since.date()
            )

            total = tours.count()
            compliant = tours.filter(compliance_status='COMPLIANT').count()
            missed = tours.filter(status='MISSED').count()
            partial = tours.filter(compliance_status='PARTIAL_COMPLETION').count()

            return {
                'period_days': days,
                'total_tours': total,
                'compliant_tours': compliant,
                'missed_tours': missed,
                'partial_tours': partial,
                'compliance_rate': (compliant / total * 100) if total > 0 else 0,
                'missed_rate': (missed / total * 100) if total > 0 else 0,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Tour compliance summary error: {e}", exc_info=True)
            return {}

    @classmethod
    def get_site_compliance_ranking(cls, tenant, days=7, limit=10):
        """
        Get sites ranked by compliance performance.

        Args:
            tenant: Tenant instance
            days: Days to analyze
            limit: Number of sites to return

        Returns:
            list: Top/bottom performing sites
        """
        from apps.noc.security_intelligence.models import TourComplianceLog

        try:
            since = timezone.now() - timedelta(days=days)

            site_performance = TourComplianceLog.objects.filter(
                tenant=tenant,
                scheduled_date__gte=since.date()
            ).values('site__name').annotate(
                total_tours=Count('id'),
                compliant_tours=Count('id', filter=Q(compliance_status='COMPLIANT')),
                missed_tours=Count('id', filter=Q(status='MISSED'))
            ).order_by('-compliant_tours')[:limit]

            results = []
            for site in site_performance:
                compliance_rate = (
                    site['compliant_tours'] / site['total_tours'] * 100
                ) if site['total_tours'] > 0 else 0

                results.append({
                    'site_name': site['site__name'],
                    'total_tours': site['total_tours'],
                    'compliant_tours': site['compliant_tours'],
                    'missed_tours': site['missed_tours'],
                    'compliance_rate': round(compliance_rate, 2),
                })

            return results

        except (ValueError, AttributeError) as e:
            logger.error(f"Site ranking error: {e}", exc_info=True)
            return []

    @classmethod
    def get_guard_compliance_ranking(cls, tenant, days=7, limit=10):
        """
        Get guards ranked by compliance performance.

        Args:
            tenant: Tenant instance
            days: Days to analyze
            limit: Number of guards to return

        Returns:
            list: Top/bottom performing guards
        """
        from apps.noc.security_intelligence.models import TourComplianceLog

        try:
            since = timezone.now() - timedelta(days=days)

            guard_performance = TourComplianceLog.objects.filter(
                tenant=tenant,
                scheduled_date__gte=since.date()
            ).values('person__peoplename').annotate(
                total_tours=Count('id'),
                compliant_tours=Count('id', filter=Q(compliance_status='COMPLIANT')),
                missed_tours=Count('id', filter=Q(status='MISSED'))
            ).order_by('-compliant_tours')[:limit]

            results = []
            for guard in guard_performance:
                compliance_rate = (
                    guard['compliant_tours'] / guard['total_tours'] * 100
                ) if guard['total_tours'] > 0 else 0

                results.append({
                    'guard_name': guard['person__peoplename'],
                    'total_tours': guard['total_tours'],
                    'compliant_tours': guard['compliant_tours'],
                    'missed_tours': guard['missed_tours'],
                    'compliance_rate': round(compliance_rate, 2),
                })

            return results

        except (ValueError, AttributeError) as e:
            logger.error(f"Guard ranking error: {e}", exc_info=True)
            return []