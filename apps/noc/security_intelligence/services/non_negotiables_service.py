"""
Non-Negotiables Service.

Evaluates 7 operational pillars for security & facility management.
Generates daily scorecards and auto-creates NOC alerts for violations.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from typing import Dict, List, Any, Tuple
from django.utils import timezone
from django.db import transaction, models
from dataclasses import dataclass

from apps.core.services import BaseService
from apps.noc.services import AlertCorrelationService
from apps.noc.security_intelligence.models import (
    NonNegotiablesScorecard,
    TaskComplianceConfig,
    TourComplianceLog
)
from apps.noc.security_intelligence.services.task_compliance_monitor import TaskComplianceMonitor
from apps.schedhuler.services.schedule_coordinator import ScheduleCoordinator

logger = logging.getLogger('noc.non_negotiables')


@dataclass
class PillarEvaluation:
    """Result of a single pillar evaluation."""
    pillar_id: int
    score: int  # 0-100
    status: str  # GREEN, AMBER, RED
    violations: List[Dict[str, Any]]
    recommendations: List[str]


class NonNegotiablesService(BaseService):
    """
    Evaluates 7 non-negotiable operational pillars and generates scorecards.

    Pillars:
    1. Right Guard at Right Post (coverage & attendance)
    2. Supervise Relentlessly (tours & spot checks)
    3. 24/7 Control Desk (alert response & escalation)
    4. Legal & Professional (compliance & payroll)
    5. Support the Field (logistics & uniforms)
    6. Record Everything (reporting & documentation)
    7. Respond to Emergencies (crisis response & SLA)
    """

    def __init__(self):
        super().__init__()
        self.schedule_coordinator = ScheduleCoordinator()

    @transaction.atomic
    def generate_scorecard(self, tenant, client, check_date=None) -> NonNegotiablesScorecard:
        """
        Generate comprehensive scorecard for all 7 pillars.

        Args:
            tenant: Tenant instance
            client: Client/BU instance
            check_date: Date to evaluate (defaults to today)

        Returns:
            NonNegotiablesScorecard instance
        """
        if check_date is None:
            check_date = timezone.now().date()

        try:
            # Evaluate all 7 pillars
            pillar_results = []
            pillar_results.append(self._evaluate_pillar_1_guard_coverage(tenant, client, check_date))
            pillar_results.append(self._evaluate_pillar_2_supervision(tenant, client, check_date))
            pillar_results.append(self._evaluate_pillar_3_control_desk(tenant, client, check_date))
            pillar_results.append(self._evaluate_pillar_4_legal_compliance(tenant, client, check_date))
            pillar_results.append(self._evaluate_pillar_5_field_support(tenant, client, check_date))
            pillar_results.append(self._evaluate_pillar_6_record_keeping(tenant, client, check_date))
            pillar_results.append(self._evaluate_pillar_7_emergency_response(tenant, client, check_date))

            # Calculate overall health
            overall_score, overall_status = self._calculate_overall_health(pillar_results)
            total_violations = sum(len(p.violations) for p in pillar_results)
            critical_violations = sum(
                len([v for v in p.violations if v.get('severity') == 'CRITICAL'])
                for p in pillar_results
            )

            # Aggregate recommendations
            all_recommendations = []
            for result in pillar_results:
                all_recommendations.extend(result.recommendations)

            # Create or update scorecard
            scorecard, created = NonNegotiablesScorecard.objects.update_or_create(
                tenant=tenant,
                client=client,
                check_date=check_date,
                defaults={
                    'overall_health_score': overall_score,
                    'overall_health_status': overall_status,
                    'total_violations': total_violations,
                    'critical_violations': critical_violations,
                    'pillar_1_score': pillar_results[0].score,
                    'pillar_1_status': pillar_results[0].status,
                    'pillar_2_score': pillar_results[1].score,
                    'pillar_2_status': pillar_results[1].status,
                    'pillar_3_score': pillar_results[2].score,
                    'pillar_3_status': pillar_results[2].status,
                    'pillar_4_score': pillar_results[3].score,
                    'pillar_4_status': pillar_results[3].status,
                    'pillar_5_score': pillar_results[4].score,
                    'pillar_5_status': pillar_results[4].status,
                    'pillar_6_score': pillar_results[5].score,
                    'pillar_6_status': pillar_results[5].status,
                    'pillar_7_score': pillar_results[6].score,
                    'pillar_7_status': pillar_results[6].status,
                    'violations_detail': {
                        f'pillar_{i+1}': result.violations
                        for i, result in enumerate(pillar_results)
                    },
                    'recommendations': all_recommendations,
                }
            )

            # Auto-create NOC alerts for critical violations
            auto_escalated = self._auto_create_alerts(tenant, client, pillar_results)

            # Update scorecard with alert IDs
            scorecard.auto_escalated_alerts = auto_escalated
            scorecard.save(update_fields=['auto_escalated_alerts'])

            logger.info(
                f"Generated scorecard for {client.buname} on {check_date}: {overall_status} "
                f"({overall_score}/100, {critical_violations} critical violations, "
                f"{len(auto_escalated)} alerts created)"
            )

            return scorecard

        except (ValueError, AttributeError) as e:
            logger.error(f"Error generating scorecard: {e}", exc_info=True)
            raise

    def _evaluate_pillar_1_guard_coverage(self, tenant, client, check_date) -> PillarEvaluation:
        """
        Pillar 1: Right Guard at Right Post.

        Checks: Schedule coverage, attendance compliance, geofence verification.
        """
        violations = []
        recommendations = []

        # Use existing schedule health scoring
        try:
            health_analysis = self.schedule_coordinator.analyze_schedule_health()
            schedule_health_score = health_analysis.get('overall_health', 100)

            # Check for coverage gaps
            hotspots = health_analysis.get('hotspots', [])
            if hotspots:
                for hotspot in hotspots[:3]:  # Top 3 hotspots
                    violations.append({
                        'type': 'SCHEDULE_HOTSPOT',
                        'severity': 'HIGH' if hotspot['load_score'] > 0.8 else 'MEDIUM',
                        'description': f"Schedule hotspot at {hotspot['time_slot']}: {len(hotspot['tasks'])} concurrent tasks",
                        'time_slot': hotspot['time_slot'],
                    })
                recommendations.append("Distribute schedule loads to avoid worker contention")

        except (ImportError, AttributeError) as e:
            logger.warning(f"Could not analyze schedule health: {e}")
            schedule_health_score = 100

        # Determine score and status
        score = schedule_health_score
        if score >= 90:
            status = 'GREEN'
        elif score >= 70:
            status = 'AMBER'
        else:
            status = 'RED'

        return PillarEvaluation(
            pillar_id=1,
            score=score,
            status=status,
            violations=violations,
            recommendations=recommendations
        )

    def _evaluate_pillar_2_supervision(self, tenant, client, check_date) -> PillarEvaluation:
        """
        Pillar 2: Supervise Relentlessly (tours & spot checks).

        Checks:
        - Mandatory tour completion
        - Checkpoint coverage percentage
        - Overdue tours beyond grace period
        """
        from apps.noc.security_intelligence.models import TaskComplianceConfig

        violations = []
        recommendations = []

        try:
            # Get compliance configuration
            config = TaskComplianceConfig.get_config_for_site(tenant, client)
            if not config:
                # Create default config if missing
                config = TaskComplianceConfig.objects.create(
                    tenant=tenant,
                    scope='TENANT',
                    cuser=tenant.cuser if hasattr(tenant, 'cuser') else None
                )

            # Use existing TaskComplianceMonitor
            monitor = TaskComplianceMonitor(config)
            tour_violations = monitor.check_tour_compliance(tenant, check_date)

            # Process tour violations
            for violation in tour_violations:
                tour = violation['tour']
                violations.append({
                    'type': 'TOUR_OVERDUE',
                    'severity': violation['severity'],
                    'description': (
                        f"{tour.tour_type} tour missed by {violation['overdue_minutes']:.0f} minutes - "
                        f"Guard: {tour.person.peoplename}, Site: {tour.site.buname}"
                    ),
                    'tour_id': tour.id,
                    'overdue_minutes': violation['overdue_minutes'],
                    'guard_present': violation['guard_present'],
                })

            # Calculate checkpoint coverage across all tours
            from apps.noc.security_intelligence.models import TourComplianceLog
            all_tours = TourComplianceLog.objects.filter(
                tenant=tenant,
                scheduled_date=check_date,
                is_mandatory=True
            )

            if all_tours.exists():
                avg_checkpoint_coverage = all_tours.aggregate(
                    models.Avg('checkpoint_coverage_percent')
                )['checkpoint_coverage_percent__avg'] or 100.0

                if avg_checkpoint_coverage < config.min_checkpoint_percentage:
                    violations.append({
                        'type': 'CHECKPOINT_COVERAGE_LOW',
                        'severity': 'MEDIUM',
                        'description': f"Average checkpoint coverage {avg_checkpoint_coverage:.1f}% below minimum {config.min_checkpoint_percentage}%",
                        'avg_coverage': avg_checkpoint_coverage,
                    })
                    recommendations.append(
                        f"Improve checkpoint coverage - current avg: {avg_checkpoint_coverage:.1f}%, "
                        f"required: {config.min_checkpoint_percentage}%"
                    )

            # Calculate score based on violations
            if len(violations) == 0:
                score = 100
                status = 'GREEN'
            elif len(violations) <= 2 and all(v['severity'] != 'CRITICAL' for v in violations):
                score = 85
                status = 'AMBER'
                recommendations.append("Address minor tour compliance issues to maintain GREEN status")
            else:
                score = max(50, 100 - (len(violations) * 15))  # Decrease score per violation
                status = 'RED' if any(v['severity'] == 'CRITICAL' for v in violations) else 'AMBER'
                recommendations.append("URGENT: Multiple tour violations detected - immediate supervisor intervention required")

        except (ValueError, AttributeError) as e:
            logger.error(f"Pillar 2 evaluation error: {e}", exc_info=True)
            score = 100
            status = 'GREEN'

        return PillarEvaluation(
            pillar_id=2,
            score=score,
            status=status,
            violations=violations,
            recommendations=recommendations
        )

    def _evaluate_pillar_3_control_desk(self, tenant, client, check_date) -> PillarEvaluation:
        """
        Pillar 3: 24/7 Control Desk (alert response & escalation).

        Checks:
        - CRITICAL alerts acknowledged within 15 minutes
        - HIGH alerts acknowledged within 30 minutes
        - Stale alerts that need escalation
        """
        from apps.noc.models import NOCAlertEvent
        from apps.noc.constants import DEFAULT_ESCALATION_DELAYS
        from datetime import datetime

        violations = []
        recommendations = []

        try:
            # Get all alerts for this client on check_date
            start_datetime = datetime.combine(check_date, datetime.min.time())
            end_datetime = datetime.combine(check_date, datetime.max.time())

            # Make timezone aware
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)

            alerts = NOCAlertEvent.objects.filter(
                tenant=tenant,
                client=client,
                cdtz__gte=start_datetime,
                cdtz__lte=end_datetime
            ).select_related('acknowledged_by', 'assigned_to', 'escalated_to')

            # Check acknowledgment SLA compliance
            for alert in alerts:
                if alert.severity in ['CRITICAL', 'HIGH']:
                    sla_minutes = DEFAULT_ESCALATION_DELAYS.get(alert.severity)

                    if alert.status == 'NEW':
                        # Alert never acknowledged
                        age_minutes = (timezone.now() - alert.cdtz).total_seconds() / 60
                        if age_minutes > sla_minutes:
                            violations.append({
                                'type': 'ALERT_NOT_ACKNOWLEDGED',
                                'severity': 'CRITICAL' if alert.severity == 'CRITICAL' else 'HIGH',
                                'description': (
                                    f"{alert.severity} alert not acknowledged in {sla_minutes} minutes - "
                                    f"Alert: {alert.alert_type} (age: {age_minutes:.0f} min)"
                                ),
                                'alert_id': alert.id,
                                'age_minutes': age_minutes,
                                'sla_minutes': sla_minutes,
                            })

                    elif alert.acknowledged_at:
                        # Alert acknowledged - check SLA
                        time_to_ack_minutes = (alert.acknowledged_at - alert.cdtz).total_seconds() / 60
                        if time_to_ack_minutes > sla_minutes:
                            violations.append({
                                'type': 'ALERT_ACK_SLA_BREACH',
                                'severity': 'HIGH' if alert.severity == 'CRITICAL' else 'MEDIUM',
                                'description': (
                                    f"{alert.severity} alert acknowledged late: {time_to_ack_minutes:.0f} minutes "
                                    f"(SLA: {sla_minutes} min) - {alert.alert_type}"
                                ),
                                'alert_id': alert.id,
                                'time_to_ack': time_to_ack_minutes,
                                'sla_minutes': sla_minutes,
                            })

            # Calculate score based on violations
            if len(violations) == 0:
                score = 100
                status = 'GREEN'
            elif len(violations) <= 2 and all(v['severity'] != 'CRITICAL' for v in violations):
                score = 85
                status = 'AMBER'
                recommendations.append("Minor alert SLA breaches detected - review control desk procedures")
            else:
                critical_count = sum(1 for v in violations if v['severity'] == 'CRITICAL')
                score = max(40, 100 - (len(violations) * 12))
                status = 'RED' if critical_count > 0 else 'AMBER'
                recommendations.append(
                    f"CRITICAL: {len(violations)} alert SLA breaches detected - control desk requires immediate attention"
                )
                if critical_count > 0:
                    recommendations.append(
                        f"{critical_count} CRITICAL alerts not acknowledged within SLA - escalate to management"
                    )

        except (ValueError, AttributeError) as e:
            logger.error(f"Pillar 3 evaluation error: {e}", exc_info=True)
            score = 100
            status = 'GREEN'

        return PillarEvaluation(
            pillar_id=3,
            score=score,
            status=status,
            violations=violations,
            recommendations=recommendations
        )

    def _evaluate_pillar_4_legal_compliance(self, tenant, client, check_date) -> PillarEvaluation:
        """
        Pillar 4: Legal & Professional (PF/ESIC/UAN, payroll, compliance).

        Checks:
        - Required compliance reports generated on time
        - Payroll reports completed
        - Attendance summary reports available
        """
        from apps.reports.models import ScheduleReport
        from datetime import datetime

        violations = []
        recommendations = []

        try:
            # Define compliance-critical report types
            compliance_reports = [
                'PEOPLEATTENDANCESUMMARY',  # Payroll/attendance compliance
            ]

            # Check if compliance reports were generated on check_date
            start_datetime = datetime.combine(check_date, datetime.min.time())
            end_datetime = datetime.combine(check_date, datetime.max.time())
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)

            for report_type in compliance_reports:
                scheduled = ScheduleReport.objects.filter(
                    client=client,
                    report_type=report_type,
                    enable=True
                ).first()

                if scheduled:
                    # Check if report was generated on check_date
                    if scheduled.lastgeneratedon:
                        if not (start_datetime <= scheduled.lastgeneratedon <= end_datetime):
                            # Report not generated on check_date
                            violations.append({
                                'type': 'COMPLIANCE_REPORT_MISSING',
                                'severity': 'HIGH',
                                'description': f"Compliance report '{scheduled.report_name}' not generated on {check_date}",
                                'report_type': report_type,
                                'last_generated': scheduled.lastgeneratedon.date().isoformat() if scheduled.lastgeneratedon else 'Never',
                            })
                    else:
                        # Report never generated
                        violations.append({
                            'type': 'COMPLIANCE_REPORT_NEVER_GENERATED',
                            'severity': 'CRITICAL',
                            'description': f"Compliance report '{scheduled.report_name}' has never been generated",
                            'report_type': report_type,
                        })
                        recommendations.append(f"Immediate action required: Setup and run '{scheduled.report_name}' for compliance")

            # Calculate score
            if len(violations) == 0:
                score = 100
                status = 'GREEN'
            elif len(violations) == 1 and violations[0]['severity'] != 'CRITICAL':
                score = 80
                status = 'AMBER'
                recommendations.append("One compliance report missing - generate immediately to avoid legal issues")
            else:
                score = max(30, 100 - (len(violations) * 25))
                status = 'RED'
                recommendations.append("CRITICAL: Multiple compliance reports missing - legal risk exposure")

        except (ValueError, AttributeError) as e:
            logger.error(f"Pillar 4 evaluation error: {e}", exc_info=True)
            score = 100
            status = 'GREEN'

        return PillarEvaluation(
            pillar_id=4,
            score=score,
            status=status,
            violations=violations,
            recommendations=recommendations
        )

    def _evaluate_pillar_5_field_support(self, tenant, client, check_date) -> PillarEvaluation:
        """
        Pillar 5: Support the Field (uniforms, logistics, work orders).

        Checks:
        - Open field support tickets exceeding 72 hours
        - Unresolved uniform/equipment requests
        - Work order backlogs
        """
        from apps.y_helpdesk.models import Ticket
        from datetime import datetime

        violations = []
        recommendations = []

        try:
            # Define field support ticket categories (uniforms, equipment, logistics)
            field_support_categories = ['TC_UNIFORM', 'TC_EQUIPMENT', 'TC_LOGISTICS']

            # Check for stale field support tickets (open > 72 hours)
            stale_threshold = timezone.now() - timedelta(hours=72)

            stale_tickets = Ticket.objects.filter(
                client=client,
                status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS'],
                cdtz__lte=stale_threshold
            ).select_related('assignedtopeople', 'ticketcategory')

            for ticket in stale_tickets:
                age_hours = (timezone.now() - ticket.cdtz).total_seconds() / 3600
                violations.append({
                    'type': 'FIELD_SUPPORT_DELAYED',
                    'severity': 'HIGH' if age_hours > 120 else 'MEDIUM',  # 5 days = HIGH
                    'description': f"Field support ticket #{ticket.ticketno} open for {age_hours:.0f} hours - {ticket.ticketdesc[:50]}",
                    'ticket_id': ticket.id,
                    'age_hours': age_hours,
                })

            # Calculate score
            if len(violations) == 0:
                score = 100
                status = 'GREEN'
            elif len(violations) <= 3:
                score = 85
                status = 'AMBER'
                recommendations.append(f"{len(violations)} field support tickets pending - prioritize resolution")
            else:
                score = max(50, 100 - (len(violations) * 8))
                status = 'RED' if len(violations) > 10 else 'AMBER'
                recommendations.append(
                    f"URGENT: {len(violations)} field support tickets overdue - guards lacking critical resources"
                )

        except (ValueError, AttributeError) as e:
            logger.error(f"Pillar 5 evaluation error: {e}", exc_info=True)
            score = 100
            status = 'GREEN'

        return PillarEvaluation(
            pillar_id=5,
            score=score,
            status=status,
            violations=violations,
            recommendations=recommendations
        )

    def _evaluate_pillar_6_record_keeping(self, tenant, client, check_date) -> PillarEvaluation:
        """
        Pillar 6: Record Everything (daily/weekly/monthly reports).

        Checks:
        - Daily reports generated on time
        - Weekly reports delivered
        - Monthly reports completed
        """
        from apps.reports.models import ScheduleReport
        from datetime import datetime

        violations = []
        recommendations = []

        try:
            # Check daily reports
            daily_reports = ScheduleReport.objects.filter(
                client=client,
                enable=True,
                crontype__icontains='DAILY'
            )

            start_datetime = datetime.combine(check_date, datetime.min.time())
            end_datetime = datetime.combine(check_date, datetime.max.time())
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)

            for report in daily_reports:
                if report.lastgeneratedon:
                    if not (start_datetime <= report.lastgeneratedon <= end_datetime):
                        days_overdue = (check_date - report.lastgeneratedon.date()).days
                        violations.append({
                            'type': 'DAILY_REPORT_MISSING',
                            'severity': 'MEDIUM',
                            'description': f"Daily report '{report.report_name}' not generated for {check_date} (last: {report.lastgeneratedon.date()})",
                            'report_id': report.id,
                            'days_overdue': days_overdue,
                        })

            # Calculate score
            if len(violations) == 0:
                score = 100
                status = 'GREEN'
            elif len(violations) <= 2:
                score = 85
                status = 'AMBER'
                recommendations.append("Some reports delayed - ensure reporting automation is functioning")
            else:
                score = max(60, 100 - (len(violations) * 10))
                status = 'RED' if len(violations) > 5 else 'AMBER'
                recommendations.append(f"{len(violations)} reports missing - check background task execution")

        except (ValueError, AttributeError) as e:
            logger.error(f"Pillar 6 evaluation error: {e}", exc_info=True)
            score = 100
            status = 'GREEN'

        return PillarEvaluation(
            pillar_id=6,
            score=score,
            status=status,
            violations=violations,
            recommendations=recommendations
        )

    def _evaluate_pillar_7_emergency_response(self, tenant, client, check_date) -> PillarEvaluation:
        """
        Pillar 7: Respond to Emergencies (crisis response, IVR, panic button).

        Checks:
        - Crisis tickets auto-created from PeopleEventlog
        - Emergency escalation within 2 minutes
        - Panic button/IVR response times
        """
        from apps.y_helpdesk.models import Ticket
        from apps.attendance.models import PeopleEventlog
        from datetime import datetime

        violations = []
        recommendations = []

        try:
            # Check for crisis events on check_date
            start_datetime = datetime.combine(check_date, datetime.min.time())
            end_datetime = datetime.combine(check_date, datetime.max.time())
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)

            # Get crisis tickets created on check_date
            crisis_tickets = Ticket.objects.filter(
                client=client,
                ticketsource='SYSTEMGENERATED',
                priority='HIGH',
                cdtz__gte=start_datetime,
                cdtz__lte=end_datetime
            ).select_related('assignedtopeople')

            # Check escalation response time for crisis tickets
            for ticket in crisis_tickets:
                if ticket.isescalated and ticket.escalatedon:
                    escalation_time_minutes = (ticket.escalatedon - ticket.cdtz).total_seconds() / 60

                    # Emergency tickets should escalate within 2 minutes if not assigned
                    if escalation_time_minutes > 2:
                        violations.append({
                            'type': 'EMERGENCY_ESCALATION_DELAYED',
                            'severity': 'CRITICAL',
                            'description': (
                                f"Crisis ticket #{ticket.ticketno} escalated after {escalation_time_minutes:.0f} minutes "
                                f"(SLA: 2 min) - {ticket.ticketdesc[:50]}"
                            ),
                            'ticket_id': ticket.id,
                            'escalation_time': escalation_time_minutes,
                        })
                elif not ticket.assignedtopeople and not ticket.isescalated:
                    # Crisis ticket not assigned and not escalated
                    age_minutes = (timezone.now() - ticket.cdtz).total_seconds() / 60
                    if age_minutes > 5:  # Unassigned crisis ticket > 5 minutes
                        violations.append({
                            'type': 'EMERGENCY_TICKET_UNASSIGNED',
                            'severity': 'CRITICAL',
                            'description': f"Crisis ticket #{ticket.ticketno} unassigned for {age_minutes:.0f} minutes - {ticket.ticketdesc[:50]}",
                            'ticket_id': ticket.id,
                            'age_minutes': age_minutes,
                        })

            # Calculate score
            if len(violations) == 0:
                score = 100
                status = 'GREEN'
            elif len(violations) == 1:
                score = 70
                status = 'RED'  # Any emergency response failure is RED
                recommendations.append("CRITICAL: Emergency response delay detected - review crisis protocols")
            else:
                score = max(30, 100 - (len(violations) * 20))
                status = 'RED'
                recommendations.append(
                    f"CRITICAL: {len(violations)} emergency response failures - immediate protocol review required"
                )
                recommendations.append("Escalate to senior management - life safety risk")

        except (ValueError, AttributeError) as e:
            logger.error(f"Pillar 7 evaluation error: {e}", exc_info=True)
            score = 100
            status = 'GREEN'

        return PillarEvaluation(
            pillar_id=7,
            score=score,
            status=status,
            violations=violations,
            recommendations=recommendations
        )

    def _calculate_overall_health(self, pillar_results: List[PillarEvaluation]) -> Tuple[int, str]:
        """Calculate overall health score and status from pillar results."""
        # Weighted average (all pillars equal weight for now)
        total_score = sum(p.score for p in pillar_results)
        overall_score = total_score // len(pillar_results)

        # Overall status: RED if any RED, AMBER if any AMBER, else GREEN
        statuses = [p.status for p in pillar_results]
        if 'RED' in statuses:
            overall_status = 'RED'
        elif 'AMBER' in statuses:
            overall_status = 'AMBER'
        else:
            overall_status = 'GREEN'

        return overall_score, overall_status

    def _auto_create_alerts(self, tenant, client, pillar_results: List[PillarEvaluation]) -> List[int]:
        """
        Auto-create NOC alerts for CRITICAL and HIGH severity violations.

        Args:
            tenant: Tenant instance
            client: Client/BU instance
            pillar_results: List of pillar evaluation results

        Returns:
            List of alert IDs created
        """
        created_alert_ids = []

        pillar_names = {
            1: "Right Guard at Right Post",
            2: "Supervise Relentlessly",
            3: "24/7 Control Desk",
            4: "Legal & Professional",
            5: "Support the Field",
            6: "Record Everything",
            7: "Respond to Emergencies",
        }

        for pillar in pillar_results:
            for violation in pillar.violations:
                # Only create alerts for CRITICAL and HIGH severity
                if violation.get('severity') in ['CRITICAL', 'HIGH']:
                    try:
                        alert_data = {
                            'tenant': tenant,
                            'client': client,
                            'bu': client,
                            'alert_type': violation['type'],
                            'severity': violation['severity'],
                            'message': f"[Pillar {pillar.pillar_id}: {pillar_names[pillar.pillar_id]}] {violation['description']}",
                            'entity_type': 'non_negotiable_violation',
                            'entity_id': pillar.pillar_id,
                            'metadata': {
                                'pillar_id': pillar.pillar_id,
                                'pillar_name': pillar_names[pillar.pillar_id],
                                'violation_type': violation['type'],
                                'violation_data': violation,
                            }
                        }

                        alert = AlertCorrelationService.process_alert(alert_data)
                        if alert:
                            created_alert_ids.append(alert.id)
                            logger.info(
                                f"Auto-created alert {alert.id} for {violation['type']} "
                                f"(Pillar {pillar.pillar_id}, Severity: {violation['severity']})"
                            )

                    except Exception as e:
                        logger.error(f"Error creating alert for violation: {e}", exc_info=True)

        return created_alert_ids
