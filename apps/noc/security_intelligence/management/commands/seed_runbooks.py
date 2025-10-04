"""
Management Command: Seed Finding Runbooks.

Creates comprehensive set of 20+ runbooks for common finding types.
Run: python manage.py seed_runbooks

Follows .claude/rules.md standards.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.noc.security_intelligence.models import FindingRunbook
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = 'Seed finding runbooks for all tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Seed runbooks for specific tenant ID only'
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant_id')

        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id)
        else:
            tenants = Tenant.objects.all()

        total_created = 0

        for tenant in tenants:
            created = self.seed_runbooks_for_tenant(tenant)
            total_created += created
            self.stdout.write(
                self.style.SUCCESS(f'Created {created} runbooks for tenant: {tenant.name}')
            )

        self.stdout.write(
            self.style.SUCCESS(f'\nTotal runbooks created: {total_created}')
        )

    @transaction.atomic
    def seed_runbooks_for_tenant(self, tenant):
        """Seed all runbooks for a tenant."""
        runbooks_data = self.get_runbooks_data()
        created_count = 0

        for rb_data in runbooks_data:
            runbook, created = FindingRunbook.objects.get_or_create(
                tenant=tenant,
                finding_type=rb_data['finding_type'],
                defaults=rb_data
            )

            if created:
                created_count += 1

        return created_count

    def get_runbooks_data(self):
        """Get comprehensive runbook data (20+ runbooks)."""
        return [
            # SECURITY Category
            {
                'finding_type': 'TOUR_OVERDUE',
                'title': 'Mandatory Tour Overdue',
                'category': 'SECURITY',
                'severity': 'HIGH',
                'description': 'Mandatory tour not completed within grace period',
                'evidence_required': ['tour_log', 'location_history', 'guard_status'],
                'steps': [
                    '1. Verify guard location via GPS',
                    '2. Contact guard immediately via phone/SMS',
                    '3. If no response in 5 minutes, dispatch supervisor',
                    '4. Document reason for delay',
                    '5. Complete tour manually if guard cannot',
                ],
                'escalation_sla_minutes': 15,
                'escalate_to_role': 'supervisor',
                'auto_actions': ['send_sms', 'create_ticket'],
            },
            {
                'finding_type': 'CORRELATION_TOUR_ABANDONMENT',
                'title': 'Tour Abandoned Mid-Execution',
                'category': 'SECURITY',
                'severity': 'HIGH',
                'description': 'Tour started but not completed, guard location left site',
                'evidence_required': ['tour_log', 'location_trail', 'guard_status'],
                'steps': [
                    '1. Contact guard immediately to determine reason',
                    '2. Review GPS trail to verify guard left site',
                    '3. Investigate if emergency or personal issue',
                    '4. Complete tour manually or assign to another guard',
                    '5. Document incident and provide retraining if needed',
                ],
                'escalation_sla_minutes': 10,
                'escalate_to_role': 'security_supervisor',
                'auto_actions': ['send_sms', 'create_ticket', 'escalate'],
            },
            {
                'finding_type': 'CHECKPOINT_COVERAGE_LOW',
                'title': 'Low Checkpoint Scan Coverage',
                'category': 'SECURITY',
                'severity': 'MEDIUM',
                'description': 'Tour checkpoint scanning below minimum threshold',
                'evidence_required': ['tour_log', 'checkpoint_coverage'],
                'steps': [
                    '1. Review which checkpoints were missed',
                    '2. Verify checkpoint hardware (NFC/beacon) is functional',
                    '3. Check if guard is intentionally skipping checkpoints',
                    '4. Provide retraining on checkpoint scanning procedures',
                ],
                'escalation_sla_minutes': 30,
                'escalate_to_role': 'supervisor',
                'auto_actions': [],
            },
            {
                'finding_type': 'CORRELATION_PHANTOM_GUARD',
                'title': 'Phantom Guard Pattern',
                'category': 'SECURITY',
                'severity': 'MEDIUM',
                'description': 'Guard showing location activity but no work completed',
                'evidence_required': ['location_history', 'task_logs', 'guard_status'],
                'steps': [
                    '1. Verify guard is performing assigned duties',
                    '2. Check if tasks are being logged correctly',
                    '3. Review guard schedule - are tasks actually assigned?',
                    '4. Investigate potential productivity issues',
                    '5. Consider disciplinary action if pattern continues',
                ],
                'escalation_sla_minutes': 60,
                'escalate_to_role': 'operations_manager',
                'auto_actions': [],
            },

            # OPERATIONAL Category
            {
                'finding_type': 'CORRELATION_SILENT_SITE',
                'title': 'Silent Site Detected',
                'category': 'OPERATIONAL',
                'severity': 'CRITICAL',
                'description': 'Site showing no activity - no phone, GPS, or task activity',
                'evidence_required': ['guard_status', 'location_history', 'task_logs'],
                'steps': [
                    '1. Attempt to contact guard immediately (call/SMS)',
                    '2. Check last known location and timestamp',
                    '3. Dispatch supervisor to site if no response within 5 min',
                    '4. Verify device battery and connectivity',
                    '5. Check shift schedule - is guard on duty?',
                    '6. Escalate to management if guard safety concern',
                ],
                'escalation_sla_minutes': 5,
                'escalate_to_role': 'operations_manager',
                'auto_actions': ['send_sms', 'create_ticket', 'escalate'],
            },
            {
                'finding_type': 'CORRELATION_SLA_STORM',
                'title': 'SLA Storm - Systemic Failure',
                'category': 'OPERATIONAL',
                'severity': 'CRITICAL',
                'description': 'Multiple simultaneous failures: overdue tasks, delayed tours, high alerts',
                'evidence_required': ['task_logs', 'tour_logs', 'alert_history'],
                'steps': [
                    '1. URGENT: Escalate to operations manager immediately',
                    '2. Review staffing levels - are guards adequate?',
                    '3. Check for systemic issues (power outage, network down)',
                    '4. Prioritize critical tasks and tours',
                    '5. Consider dispatching additional resources',
                    '6. Schedule post-incident review',
                ],
                'escalation_sla_minutes': 2,
                'escalate_to_role': 'operations_manager',
                'auto_actions': ['escalate', 'create_ticket'],
            },
            {
                'finding_type': 'SLA_BREACH',
                'title': 'Task SLA Breach',
                'category': 'OPERATIONAL',
                'severity': 'HIGH',
                'description': 'Task exceeded SLA threshold',
                'evidence_required': ['task_log', 'guard_status'],
                'steps': [
                    '1. Contact assigned guard to determine delay reason',
                    '2. Verify guard is on site and has resources',
                    '3. Reassign task if guard cannot complete',
                    '4. Document delay reason',
                    '5. Review task prioritization if recurring',
                ],
                'escalation_sla_minutes': 30,
                'escalate_to_role': 'supervisor',
                'auto_actions': ['send_sms'],
            },
            {
                'finding_type': 'FIELD_SUPPORT_DELAYED',
                'title': 'Field Support Ticket Overdue',
                'category': 'OPERATIONAL',
                'severity': 'MEDIUM',
                'description': 'Field support ticket (uniform/equipment) open >72 hours',
                'evidence_required': ['ticket_log'],
                'steps': [
                    '1. Contact logistics team for status update',
                    '2. Expedite delivery if critical (uniform, safety equipment)',
                    '3. Provide temporary alternative if available',
                    '4. Update guard with expected delivery date',
                ],
                'escalation_sla_minutes': 120,
                'escalate_to_role': 'logistics_manager',
                'auto_actions': [],
            },

            # DEVICE_HEALTH Category
            {
                'finding_type': 'CRITICAL_SIGNAL_PHONE_EVENTS_LOW',
                'title': 'Low Phone Activity',
                'category': 'DEVICE_HEALTH',
                'severity': 'HIGH',
                'description': 'Guard phone activity below threshold',
                'evidence_required': ['guard_status', 'location_history'],
                'steps': [
                    '1. Check last known location and timestamp',
                    '2. Attempt to call guard directly',
                    '3. Verify guard checked in at shift start',
                    '4. Dispatch supervisor if no response',
                    '5. Investigate device battery/connectivity issues',
                ],
                'escalation_sla_minutes': 10,
                'escalate_to_role': 'supervisor',
                'auto_actions': ['send_sms'],
            },
            {
                'finding_type': 'CRITICAL_SIGNAL_LOCATION_UPDATES_LOW',
                'title': 'Low GPS Activity',
                'category': 'DEVICE_HEALTH',
                'severity': 'HIGH',
                'description': 'GPS location updates below threshold',
                'evidence_required': ['location_history', 'guard_status'],
                'steps': [
                    '1. Check if phone events are still active',
                    '2. Verify GPS permissions on device',
                    '3. Ask guard to enable location services',
                    '4. Test GPS accuracy manually',
                    '5. Replace device if hardware failure suspected',
                ],
                'escalation_sla_minutes': 15,
                'escalate_to_role': 'supervisor',
                'auto_actions': ['send_sms'],
            },
            {
                'finding_type': 'CORRELATION_DEVICE_GPS_FAILURE',
                'title': 'GPS Hardware/Software Failure',
                'category': 'DEVICE_HEALTH',
                'severity': 'HIGH',
                'description': 'Phone active but no GPS updates',
                'evidence_required': ['guard_status', 'phone_events', 'location_history'],
                'steps': [
                    '1. Check GPS permissions on guard device',
                    '2. Verify location services enabled',
                    '3. Restart location services/app',
                    '4. Test GPS accuracy manually',
                    '5. Replace device if hardware failure confirmed',
                ],
                'escalation_sla_minutes': 20,
                'escalate_to_role': 'supervisor',
                'auto_actions': ['send_sms', 'create_ticket'],
            },
            {
                'finding_type': 'CORRELATION_DEVICE_PHONE_FAILURE',
                'title': 'Mobile App/Phone Failure',
                'category': 'DEVICE_HEALTH',
                'severity': 'HIGH',
                'description': 'GPS active but no phone/app events',
                'evidence_required': ['guard_status', 'location_history'],
                'steps': [
                    '1. Check if mobile app is running',
                    '2. Verify app permissions',
                    '3. Ask guard to restart app or device',
                    '4. Check for app crashes in logs',
                    '5. Reinstall app if persistent issues',
                ],
                'escalation_sla_minutes': 20,
                'escalate_to_role': 'supervisor',
                'auto_actions': ['send_sms', 'create_ticket'],
            },

            # COMPLIANCE Category
            {
                'finding_type': 'COMPLIANCE_REPORT_MISSING',
                'title': 'Compliance Report Missing',
                'category': 'COMPLIANCE',
                'severity': 'HIGH',
                'description': 'Required compliance report not generated on time',
                'evidence_required': ['report_schedule'],
                'steps': [
                    '1. Generate report immediately',
                    '2. Verify report generation schedule is correct',
                    '3. Check for background task failures',
                    '4. Deliver report to client/authorities',
                    '5. Document delay reason',
                ],
                'escalation_sla_minutes': 60,
                'escalate_to_role': 'compliance_manager',
                'auto_actions': ['create_ticket'],
            },
            {
                'finding_type': 'COMPLIANCE_REPORT_NEVER_GENERATED',
                'title': 'Critical Compliance Gap',
                'category': 'COMPLIANCE',
                'severity': 'CRITICAL',
                'description': 'Required compliance report has never been run',
                'evidence_required': ['report_schedule'],
                'steps': [
                    '1. URGENT: Generate all missing reports immediately',
                    '2. Notify compliance team of gap',
                    '3. Review legal/regulatory risk exposure',
                    '4. Fix report generation schedule',
                    '5. Implement monitoring to prevent recurrence',
                ],
                'escalation_sla_minutes': 30,
                'escalate_to_role': 'compliance_manager',
                'auto_actions': ['escalate', 'create_ticket'],
            },
            {
                'finding_type': 'DAILY_REPORT_MISSING',
                'title': 'Daily Report Not Generated',
                'category': 'COMPLIANCE',
                'severity': 'MEDIUM',
                'description': 'Expected daily report not generated',
                'evidence_required': ['report_schedule'],
                'steps': [
                    '1. Generate report manually',
                    '2. Check background task execution',
                    '3. Verify report schedule is active',
                    '4. Deliver report to client if applicable',
                ],
                'escalation_sla_minutes': 120,
                'escalate_to_role': 'operations_manager',
                'auto_actions': [],
            },

            # ANOMALY Findings
            {
                'finding_type': 'ANOMALY_PHONE_EVENTS_BELOW',
                'title': 'Anomalous Phone Activity (Low)',
                'category': 'OPERATIONAL',
                'severity': 'MEDIUM',
                'description': 'Phone activity significantly below baseline',
                'evidence_required': ['baseline_profile', 'guard_status'],
                'steps': [
                    '1. Review hour-of-week baseline for context',
                    '2. Check for environmental factors (events, holidays)',
                    '3. Verify guard schedule - is guard on duty?',
                    '4. If persistent, investigate further',
                ],
                'escalation_sla_minutes': 30,
                'escalate_to_role': 'supervisor',
                'auto_actions': [],
            },
            {
                'finding_type': 'ANOMALY_TOUR_CHECKPOINTS_BELOW',
                'title': 'Low Tour Checkpoint Scans (Anomalous)',
                'category': 'SECURITY',
                'severity': 'HIGH',
                'description': 'Tour checkpoint scanning below baseline',
                'evidence_required': ['baseline_profile', 'tour_logs', 'location_history'],
                'steps': [
                    '1. Check tour compliance logs for specific tours missed',
                    '2. Verify checkpoint hardware is functional',
                    '3. Review guard patrol route via GPS trail',
                    '4. Investigate if guard is skipping checkpoints',
                    '5. Retrain guard on checkpoint scanning',
                ],
                'escalation_sla_minutes': 20,
                'escalate_to_role': 'security_supervisor',
                'auto_actions': ['create_ticket'],
            },
            {
                'finding_type': 'ANOMALY_TASKS_COMPLETED_BELOW',
                'title': 'Low Task Completion Rate (Anomalous)',
                'category': 'OPERATIONAL',
                'severity': 'MEDIUM',
                'description': 'Task completions significantly below normal',
                'evidence_required': ['baseline_profile', 'task_logs', 'guard_status'],
                'steps': [
                    '1. Review pending task backlog',
                    '2. Check if guard has enough time for assigned tasks',
                    '3. Verify tasks are properly assigned',
                    '4. Investigate productivity issues if persistent',
                ],
                'escalation_sla_minutes': 60,
                'escalate_to_role': 'operations_manager',
                'auto_actions': [],
            },

            # SAFETY Category
            {
                'finding_type': 'EMERGENCY_ESCALATION_DELAYED',
                'title': 'Emergency Escalation Delayed',
                'category': 'SAFETY',
                'severity': 'CRITICAL',
                'description': 'Crisis ticket escalation exceeded 2-minute SLA',
                'evidence_required': ['ticket_log', 'escalation_log'],
                'steps': [
                    '1. CRITICAL: Escalate immediately to senior management',
                    '2. Verify guard safety and status',
                    '3. Dispatch emergency response if needed',
                    '4. Document incident in detail',
                    '5. Review and improve escalation procedures',
                ],
                'escalation_sla_minutes': 0,  # Immediate
                'escalate_to_role': 'senior_manager',
                'auto_actions': ['escalate'],
            },
            {
                'finding_type': 'EMERGENCY_TICKET_UNASSIGNED',
                'title': 'Crisis Ticket Unassigned',
                'category': 'SAFETY',
                'severity': 'CRITICAL',
                'description': 'Crisis ticket unassigned for >5 minutes',
                'evidence_required': ['ticket_log'],
                'steps': [
                    '1. CRITICAL: Assign to on-call manager immediately',
                    '2. Verify guard safety',
                    '3. Dispatch emergency response',
                    '4. Follow crisis response protocol',
                ],
                'escalation_sla_minutes': 0,
                'escalate_to_role': 'on_call_manager',
                'auto_actions': ['escalate'],
            },

            # Generic Fallback
            {
                'finding_type': 'GENERIC',
                'title': 'Generic Finding',
                'category': 'OPERATIONAL',
                'severity': 'MEDIUM',
                'description': 'Generic finding requiring investigation',
                'evidence_required': ['finding_details'],
                'steps': [
                    '1. Review finding details and evidence',
                    '2. Determine appropriate action',
                    '3. Contact relevant stakeholders',
                    '4. Document resolution',
                ],
                'escalation_sla_minutes': 60,
                'escalate_to_role': 'supervisor',
                'auto_actions': [],
            },
        ]
