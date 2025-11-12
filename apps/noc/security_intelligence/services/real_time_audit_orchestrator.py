"""
Real-Time Audit Orchestrator Service.

Coordinates multi-cadence site audits: 5-min heartbeats, 15-min comprehensive, 1-hour deep analysis.
Detects findings, collects evidence, creates alerts, and applies runbooks.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction, DatabaseError

from apps.noc.security_intelligence.models import (
    SiteAuditSchedule,
    AuditFinding,
    FindingRunbook
)
from apps.noc.security_intelligence.services.evidence_collector import EvidenceCollector
from apps.noc.security_intelligence.services.task_compliance_monitor import TaskComplianceMonitor
from apps.noc.security_intelligence.services.activity_signal_collector import ActivitySignalCollector
from apps.noc.security_intelligence.services.signal_correlation_service import SignalCorrelationService
from apps.noc.services import AlertCorrelationService
from apps.noc.services.websocket_service import NOCWebSocketService
from apps.noc.services.audit_escalation_service import AuditEscalationService

logger = logging.getLogger('noc.audit_orchestrator')


class RealTimeAuditOrchestrator:
    """
    Orchestrates real-time site auditing with multi-cadence execution.

    Cadences:
    - Heartbeat (5 min): Critical signals (phone, GPS, panic)
    - Comprehensive (15 min): Full 7-pillar audit with evidence
    - Deep (1 hour): Pattern analysis and anomaly detection
    """

    def __init__(self):
        self.evidence_collector = EvidenceCollector()

    def run_heartbeat_check(self, site):
        """
        Run critical signal heartbeat check (5-min cadence).

        Checks:
        - Phone activity exists
        - GPS updates present
        - No panic/duress events

        Args:
            site: Bt instance (business unit)

        Returns:
            list: Findings detected
        """
        try:
            schedule = SiteAuditSchedule.objects.filter(site=site, enabled=True).first()
            if not schedule:
                logger.warning(f"No audit schedule for site {site.buname}")
                return []

            findings = []

            # Check critical signals
            critical_signals = schedule.critical_signals or ['phone_events', 'location_updates']

            for signal_type in critical_signals:
                finding = self._check_critical_signal(site, signal_type, schedule)
                if finding:
                    findings.append(finding)

            schedule.last_heartbeat_at = timezone.now()
            schedule.save(update_fields=['last_heartbeat_at'])

            return findings

        except (DatabaseError, AttributeError) as e:
            logger.error(f"Heartbeat check error for {site.buname}: {e}", exc_info=True)
            return []

    def _check_critical_signal(self, site, signal_type, schedule):
        """
        Check single critical signal.

        Args:
            site: Bt instance
            signal_type: String signal type
            schedule: SiteAuditSchedule instance

        Returns:
            AuditFinding or None
        """
        try:
            threshold = schedule.signal_thresholds.get(signal_type, {})
            min_count = threshold.get('min_count', 1)
            window_minutes = threshold.get('window_minutes', 60)

            # Get active people for this site
            from apps.peoples.models import People
            active_people = People.objects.filter(
                tenant=site.tenant,
                peopleorganizational__bu=site,
                isactive=True
            ).first()

            if not active_people:
                return None

            # Collect signal data
            signals = ActivitySignalCollector.collect_all_signals(
                person=active_people,
                site=site,
                window_minutes=window_minutes
            )

            # Correlate signals with existing alerts
            try:
                SignalCorrelationService.correlate_signals_with_alerts(
                    person=active_people,
                    site=site,
                    signals=signals,
                    window_minutes=window_minutes
                )
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Signal correlation failed: {e}")

            signal_count = signals.get(f'{signal_type}_count', 0)

            if signal_count < min_count:
                return self._create_finding(
                    site=site,
                    finding_type=f'CRITICAL_SIGNAL_{signal_type.upper()}_LOW',
                    category='DEVICE_HEALTH',
                    severity='HIGH',
                    title=f'Low {signal_type} activity detected',
                    description=f'Only {signal_count} {signal_type} in last {window_minutes} minutes (expected >= {min_count})',
                    evidence={'signal_data': signals, 'threshold': threshold}
                )

            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"Critical signal check error: {e}", exc_info=True)
            return None

    def run_comprehensive_audit(self, site):
        """
        Run comprehensive 15-min audit.

        Evaluates:
        - Task compliance (SLA, tours)
        - Activity signals (phone, GPS, tasks)
        - Alert patterns
        - Guard presence

        Args:
            site: Bt instance

        Returns:
            list: Findings detected
        """
        try:
            schedule = SiteAuditSchedule.objects.filter(site=site, enabled=True).first()
            if not schedule or not schedule.should_run_audit():
                return []

            findings = []

            # Run compliance checks
            compliance_findings = self._check_task_compliance(site)
            findings.extend(compliance_findings)

            # Collect evidence for all findings
            if schedule.collect_evidence:
                for finding in findings:
                    evidence = self.evidence_collector.collect_evidence(
                        finding=finding,
                        lookback_minutes=schedule.evidence_lookback_minutes
                    )
                    finding.evidence.update(evidence)
                    finding.save(update_fields=['evidence'])

            # Create NOC alerts if enabled
            if schedule.alert_on_finding:
                self._create_alerts_for_findings(findings, schedule)

            schedule.update_audit_stats(findings_count=len(findings))

            return findings

        except (DatabaseError, AttributeError) as e:
            logger.error(f"Comprehensive audit error for {site.buname}: {e}", exc_info=True)
            return []

    def _check_task_compliance(self, site):
        """Check task and tour compliance using existing monitor."""
        from apps.noc.security_intelligence.models import TaskComplianceConfig

        try:
            config = TaskComplianceConfig.get_config_for_site(site.tenant, site)
            if not config:
                return []

            monitor = TaskComplianceMonitor(config)

            # Check tours
            tour_violations = monitor.check_tour_compliance(site.tenant)

            findings = []
            for violation in tour_violations:
                finding = self._create_finding(
                    site=site,
                    finding_type='TOUR_OVERDUE',
                    category='SECURITY',
                    severity=violation['severity'],
                    title=f"Tour overdue by {violation['overdue_minutes']:.0f} minutes",
                    description=f"Mandatory tour missed - Guard: {violation['tour'].person.peoplename if violation['tour'].person else 'Unknown'}",
                    evidence={'tour_violation': violation}
                )
                findings.append(finding)

            return findings

        except (ValueError, AttributeError) as e:
            logger.error(f"Task compliance check error: {e}", exc_info=True)
            return []

    @transaction.atomic
    def _create_finding(self, site, finding_type, category, severity, title, description, evidence=None):
        """Create audit finding with runbook integration."""
        try:
            runbook = FindingRunbook.get_for_finding_type(finding_type, site.tenant)

            finding = AuditFinding.objects.create(
                tenant=site.tenant,
                site=site,
                finding_type=finding_type,
                category=category,
                severity=severity,
                title=title,
                description=description,
                evidence=evidence or {},
                runbook_id=runbook,
                recommended_actions=runbook.steps if runbook else []
            )

            logger.info(f"Created finding: {finding}")

            # Broadcast finding to WebSocket clients
            try:
                NOCWebSocketService.broadcast_finding(finding)
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to broadcast finding {finding.id}: {e}")

            # Escalate high-severity findings to tickets
            try:
                ticket = AuditEscalationService.escalate_finding_to_ticket(finding)
                if ticket:
                    logger.info(f"Finding {finding.id} escalated to ticket {ticket.id}")
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to escalate finding {finding.id}: {e}")

            # Execute matching playbooks (Enhancement #2: Automated Playbook Execution)
            try:
                self._execute_matching_playbooks(finding)
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to execute playbooks for finding {finding.id}: {e}")

            return finding

        except (DatabaseError, ValueError) as e:
            logger.error(f"Finding creation error: {e}", exc_info=True)
            return None

    def _create_alerts_for_findings(self, findings, schedule):
        """Create NOC alerts for findings based on severity threshold."""
        severity_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        threshold = severity_order.get(schedule.alert_severity_threshold, 2)

        for finding in findings:
            if severity_order.get(finding.severity, 0) >= threshold:
                self._create_alert_for_finding(finding)

    def _create_alert_for_finding(self, finding):
        """Create NOC alert for a finding."""
        try:
            alert_data = {
                'tenant': finding.tenant,
                'client': finding.site.get_client_parent() if finding.site else None,
                'bu': finding.site,
                'alert_type': 'SECURITY_ANOMALY',
                'severity': finding.severity,
                'message': f"[{finding.category}] {finding.title}",
                'entity_type': 'audit_finding',
                'entity_id': finding.id,
                'metadata': {
                    'finding_id': finding.id,
                    'finding_type': finding.finding_type,
                    'category': finding.category,
                    'runbook_steps': finding.recommended_actions,
                }
            }

            alert = AlertCorrelationService.process_alert(alert_data)
            if alert:
                finding.noc_alert = alert
                finding.save(update_fields=['noc_alert'])
                logger.info(f"Created alert {alert.id} for finding {finding.id}")

        except (DatabaseError, ValueError) as e:
            logger.error(f"Alert creation error for finding {finding.id}: {e}", exc_info=True)

    def _execute_matching_playbooks(self, finding):
        """
        Execute matching playbooks for a finding (Enhancement #2: SOAR-lite).

        Finds playbooks that match:
        - Finding type in playbook.finding_types
        - Finding severity >= playbook.severity_threshold
        - Playbook is active

        Args:
            finding: AuditFinding instance

        Auto-executes if playbook.auto_execute=True, otherwise creates pending execution.
        """
        from apps.noc.models import ExecutablePlaybook
        from apps.noc.services import PlaybookEngine

        try:
            # Find matching playbooks
            severity_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
            finding_severity_score = severity_order.get(finding.severity, 0)

            matching_playbooks = ExecutablePlaybook.objects.filter(
                tenant=finding.tenant,
                is_active=True,
                finding_types__contains=[finding.finding_type]
            )

            executed_count = 0
            for playbook in matching_playbooks:
                # Check severity threshold
                playbook_threshold = severity_order.get(playbook.severity_threshold, 0)
                if finding_severity_score < playbook_threshold:
                    continue

                # Execute playbook
                execution = PlaybookEngine.execute_playbook(
                    playbook=playbook,
                    finding=finding,
                    approved_by=None  # Auto-execute if playbook.auto_execute=True
                )

                if execution:
                    executed_count += 1
                    logger.info(
                        f"Playbook {'auto-executed' if playbook.auto_execute else 'pending approval'}",
                        extra={
                            'playbook': playbook.name,
                            'finding_id': finding.id,
                            'execution_id': str(execution.execution_id)
                        }
                    )

            if executed_count > 0:
                logger.info(f"Executed {executed_count} playbooks for finding {finding.id}")

        except (DatabaseError, ValueError) as e:
            logger.error(f"Playbook execution error for finding {finding.id}: {e}", exc_info=True)
