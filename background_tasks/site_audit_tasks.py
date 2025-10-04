"""
Site Audit Celery Tasks.

Multi-cadence site auditing tasks:
- Heartbeat (5 min): Critical signal checks
- Comprehensive (15 min): Full site audit with evidence
- Deep (1 hour): Pattern analysis and baseline updates

Follows .claude/rules.md Rule #11 (specific exception handling).
"""

import logging
from datetime import timedelta
from typing import List, Dict, Any

from celery import Task
from django.db import DatabaseError
from django.utils import timezone

from apps.core.tasks.base import IdempotentTask
from apps.noc.security_intelligence.models import SiteAuditSchedule
from apps.noc.security_intelligence.services.real_time_audit_orchestrator import RealTimeAuditOrchestrator
from apps.noc.security_intelligence.services.baseline_calculator import BaselineCalculator
from apps.noc.security_intelligence.services.anomaly_detector import AnomalyDetector
from apps.onboarding.models import Bt
from apps.tenants.models import Tenant

logger = logging.getLogger('background_tasks.site_audit')


class SiteHeartbeatTask(IdempotentTask):
    """
    5-minute heartbeat check for critical signals.

    Checks phone activity, GPS updates, panic events for all enabled sites.
    """

    name = 'site_heartbeat_5min'
    idempotency_scope = 'global'
    idempotency_ttl = 300  # 5 minutes

    def run(self, tenant_id=None):
        """
        Execute heartbeat checks for all enabled sites.

        Args:
            tenant_id: Optional tenant ID to limit checks

        Returns:
            dict: Summary of checks and findings
        """
        try:
            logger.info("Starting site heartbeat checks")

            # Get enabled sites
            schedules = SiteAuditSchedule.objects.filter(enabled=True).select_related('site', 'tenant')

            if tenant_id:
                schedules = schedules.filter(tenant_id=tenant_id)

            orchestrator = RealTimeAuditOrchestrator()

            results = {
                'sites_checked': 0,
                'total_findings': 0,
                'critical_findings': 0,
                'errors': []
            }

            for schedule in schedules:
                try:
                    # Check if heartbeat is due
                    if schedule.last_heartbeat_at:
                        minutes_since = (timezone.now() - schedule.last_heartbeat_at).total_seconds() / 60
                        if minutes_since < schedule.heartbeat_frequency_minutes:
                            continue  # Skip - not due yet

                    findings = orchestrator.run_heartbeat_check(schedule.site)

                    results['sites_checked'] += 1
                    results['total_findings'] += len(findings)
                    results['critical_findings'] += sum(
                        1 for f in findings if f.severity == 'CRITICAL'
                    )

                    if findings:
                        logger.info(
                            f"Heartbeat check for {schedule.site.buname}: "
                            f"{len(findings)} findings"
                        )

                except DatabaseError as e:
                    error_msg = f"Heartbeat error for {schedule.site.buname}: {e}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'].append(error_msg)

            logger.info(
                f"Heartbeat checks complete: {results['sites_checked']} sites, "
                f"{results['total_findings']} findings"
            )

            return results

        except (ValueError, AttributeError) as e:
            logger.error(f"Heartbeat task error: {e}", exc_info=True)
            raise


class SiteComprehensiveAuditTask(IdempotentTask):
    """
    15-minute comprehensive site audit.

    Evaluates all 7 pillars, collects evidence, creates alerts.
    """

    name = 'site_audit_15min'
    idempotency_scope = 'global'
    idempotency_ttl = 900  # 15 minutes

    def run(self, tenant_id=None, site_ids=None):
        """
        Execute comprehensive audits for all enabled sites.

        Args:
            tenant_id: Optional tenant ID to limit audits
            site_ids: Optional list of site IDs to audit

        Returns:
            dict: Summary of audits and findings
        """
        try:
            logger.info("Starting comprehensive site audits")

            # Get enabled sites
            schedules = SiteAuditSchedule.objects.filter(enabled=True).select_related('site', 'tenant')

            if tenant_id:
                schedules = schedules.filter(tenant_id=tenant_id)

            if site_ids:
                schedules = schedules.filter(site_id__in=site_ids)

            orchestrator = RealTimeAuditOrchestrator()

            results = {
                'sites_audited': 0,
                'total_findings': 0,
                'alerts_created': 0,
                'errors': []
            }

            for schedule in schedules:
                try:
                    findings = orchestrator.run_comprehensive_audit(schedule.site)

                    results['sites_audited'] += 1
                    results['total_findings'] += len(findings)
                    results['alerts_created'] += sum(
                        1 for f in findings if f.noc_alert_id is not None
                    )

                    if findings:
                        logger.info(
                            f"Comprehensive audit for {schedule.site.buname}: "
                            f"{len(findings)} findings, "
                            f"{results['alerts_created']} alerts"
                        )

                except DatabaseError as e:
                    error_msg = f"Audit error for {schedule.site.buname}: {e}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'].append(error_msg)

            logger.info(
                f"Comprehensive audits complete: {results['sites_audited']} sites, "
                f"{results['total_findings']} findings, "
                f"{results['alerts_created']} alerts"
            )

            return results

        except (ValueError, AttributeError) as e:
            logger.error(f"Comprehensive audit task error: {e}", exc_info=True)
            raise


class SiteDeepAnalysisTask(IdempotentTask):
    """
    1-hour deep pattern analysis.

    Updates baselines, detects anomalies, performs trend analysis.
    """

    name = 'site_deep_analysis_1hour'
    idempotency_scope = 'global'
    idempotency_ttl = 3600  # 1 hour

    def run(self, tenant_id=None):
        """
        Execute deep analysis for all enabled sites.

        Args:
            tenant_id: Optional tenant ID to limit analysis

        Returns:
            dict: Summary of analysis
        """
        try:
            logger.info("Starting deep site analysis")

            # Get enabled sites
            schedules = SiteAuditSchedule.objects.filter(enabled=True).select_related('site', 'tenant')

            if tenant_id:
                schedules = schedules.filter(tenant_id=tenant_id)

            results = {
                'sites_analyzed': 0,
                'baselines_updated': 0,
                'anomalies_detected': 0,
                'errors': []
            }

            for schedule in schedules:
                try:
                    # Update baselines with recent data
                    baseline_summary = BaselineCalculator.calculate_baselines_for_site(
                        site=schedule.site,
                        days_lookback=7  # Last 7 days for incremental updates
                    )

                    results['baselines_updated'] += baseline_summary.get('baselines_updated', 0)

                    # Detect anomalies
                    anomaly_findings = AnomalyDetector.detect_anomalies_for_site(schedule.site)
                    results['anomalies_detected'] += len(anomaly_findings)

                    results['sites_analyzed'] += 1

                    if anomaly_findings:
                        logger.info(
                            f"Deep analysis for {schedule.site.buname}: "
                            f"{len(anomaly_findings)} anomalies"
                        )

                except DatabaseError as e:
                    error_msg = f"Deep analysis error for {schedule.site.buname}: {e}"
                    logger.error(error_msg, exc_info=True)
                    results['errors'].append(error_msg)

            logger.info(
                f"Deep analysis complete: {results['sites_analyzed']} sites, "
                f"{results['baselines_updated']} baselines updated, "
                f"{results['anomalies_detected']} anomalies"
            )

            return results

        except (ValueError, AttributeError) as e:
            logger.error(f"Deep analysis task error: {e}", exc_info=True)
            raise


# Create task instances
site_heartbeat_5min = SiteHeartbeatTask()
site_audit_15min = SiteComprehensiveAuditTask()
site_deep_analysis_1hour = SiteDeepAnalysisTask()
