"""
Portfolio Metrics Aggregation Service

Aggregates real-time metrics across the YOUTILITY5 platform for executive
portfolio-level visibility and RAG health scoring.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
- Rule #14: SQL injection prevention (Django ORM only)
"""

import hashlib
import logging
from typing import Dict, List

from django.db.models import Count, Q
from django.utils import timezone

from apps.activity.models.job_model import Jobneed
from apps.attendance.models import PeopleEventlog
from apps.core.serializers.scope_serializers import ScopeConfig
from apps.core.services.base_service import BaseService
from apps.work_order_management.models import Wom
from apps.y_helpdesk.models import Ticket

logger = logging.getLogger(__name__)

__all__ = ['PortfolioMetricsService']


class PortfolioMetricsService(BaseService):
    """Aggregates portfolio-level metrics across all operational domains."""

    CACHE_TTL = 60
    CACHE_PREFIX = "portfolio"

    def get_service_name(self) -> str:
        return "PortfolioMetricsService"

    def get_portfolio_summary(self, scope: ScopeConfig) -> Dict:
        """Get comprehensive portfolio summary with caching."""
        cache_key = self._build_cache_key(scope)
        cached = self.get_cached_data(cache_key, ttl=self.CACHE_TTL)
        if cached:
            return cached
        summary = {
            "attendance": self.get_attendance_metrics(scope),
            "tours": self.get_tours_metrics(scope),
            "tickets": self.get_tickets_metrics(scope),
            "work_orders": self.get_work_orders_metrics(scope),
            "top_sites": self._calculate_top_sites(scope),
            "generated_at": timezone.now().isoformat()}
        self.set_cached_data(cache_key, summary, ttl=self.CACHE_TTL)
        return summary

    def get_attendance_metrics(self, scope: ScopeConfig) -> Dict:
        """Get attendance compliance metrics."""
        qs = self._filter_by_scope(PeopleEventlog.objects, scope, 'datefor')
        agg = qs.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(punchouttime__isnull=False)))
        compliance = agg['present'] / agg['total'] if agg['total'] else 0.0
        return {
            "compliance_rate": round(compliance, 2), "present": agg['present'],
            "absent": agg['total'] - agg['present'], "total_expected": agg['total']}

    def get_tours_metrics(self, scope: ScopeConfig) -> Dict:
        """Get tours adherence metrics."""
        qs = self._filter_by_scope(
            Jobneed.objects.filter(identifier__in=['INTERNALTOUR', 'EXTERNALTOUR']),
            scope, 'plandatetime__date')
        agg = qs.aggregate(
            scheduled=Count('id'),
            completed=Count('id', filter=Q(jobstatus='COMPLETED')),
            on_time=Count('id', filter=Q(jobstatus='COMPLETED', deviation=False)))
        adherence = agg['on_time'] / agg['scheduled'] if agg['scheduled'] else 0.0
        return {
            "adherence_rate": round(adherence, 2), "scheduled": agg['scheduled'],
            "completed_on_time": agg['on_time'], "completed": agg['completed']}

    def get_tickets_metrics(self, scope: ScopeConfig) -> Dict:
        """Get ticket status breakdown."""
        qs = self._filter_by_scope(Ticket.objects, scope, 'cdtz__date')
        status_counts = qs.values('status').annotate(count=Count('id'))
        return {
            "open": qs.filter(status='OPEN').count(),
            "by_status": {item['status']: item['count'] for item in status_counts},
            "sla_at_risk": qs.filter(
                priority='HIGH', status__in=['NEW', 'OPEN']).count()}

    def get_work_orders_metrics(self, scope: ScopeConfig) -> Dict:
        """Get work order status metrics."""
        qs = self._filter_by_scope(Wom.objects, scope, 'plandatetime__date')
        status_counts = qs.values('workstatus').annotate(count=Count('id'))
        return {
            "by_status": {item['workstatus']: item['count'] for item in status_counts},
            "overdue": qs.filter(
                expirydatetime__lt=timezone.now(),
                workstatus__in=['ASSIGNED', 'INPROGRESS']).count()}

    def calculate_site_rag_status(self, bu_id: int, scope: ScopeConfig) -> str:
        """Calculate RAG health status for a site."""
        site_scope = ScopeConfig(
            tenant_id=scope.tenant_id, bu_ids=[bu_id], time_range=scope.time_range,
            date_from=scope.date_from, date_to=scope.date_to, tz=scope.tz)
        att = self.get_attendance_metrics(site_scope)["compliance_rate"]
        tour = self.get_tours_metrics(site_scope)["adherence_rate"]
        if att >= 0.90 and tour >= 0.90:
            return "GREEN"
        if att < 0.70 or tour < 0.70:
            return "RED"
        return "AMBER"

    def _calculate_top_sites(self, scope: ScopeConfig) -> List[Dict]:
        """Calculate top sites by health score."""
        if not scope.bu_ids:
            return []
        sites = [{"bu_id": bu_id, "rag": self.calculate_site_rag_status(bu_id, scope)}
                 for bu_id in scope.bu_ids[:10]]
        priority = {"GREEN": 0, "AMBER": 1, "RED": 2}
        sites.sort(key=lambda x: priority.get(x["rag"], 3))
        return sites[:5]

    def _build_cache_key(self, scope: ScopeConfig) -> str:
        """Build cache key from scope hash."""
        scope_hash = hashlib.md5(scope.json().encode()).hexdigest()[:8]
        return f"{self.CACHE_PREFIX}:summary:{scope_hash}"

    def _filter_by_scope(self, queryset, scope: ScopeConfig, date_field: str):
        """Apply scope filters to queryset."""
        qs = queryset.filter(tenant_id=scope.tenant_id)
        if scope.bu_ids:
            qs = qs.filter(bu_id__in=scope.bu_ids)
        if scope.date_from:
            qs = qs.filter(**{f"{date_field}__gte": scope.date_from})
        if scope.date_to:
            qs = qs.filter(**{f"{date_field}__lte": scope.date_to})
        return qs
