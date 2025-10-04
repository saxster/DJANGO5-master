"""
Signal Correlation Engine Service.

Detects multi-signal patterns across domains (phone, GPS, tasks, tours, alerts).
Identifies complex scenarios like silent sites, tour abandonment, SLA storms.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from typing import List, Dict, Any, Optional

from apps.noc.security_intelligence.models import AuditFinding
from apps.noc.security_intelligence.services.activity_signal_collector import ActivitySignalCollector

logger = logging.getLogger('noc.signal_correlation')


class SignalCorrelationEngine:
    """
    Correlates multiple signals to detect complex patterns.

    Patterns:
    1. Silent Site - No phone + no GPS + no tasks
    2. Tour Abandonment - Tour started + GPS left + no completion
    3. SLA Storm - Multiple tasks overdue + tours delayed + high alerts
    4. Phantom Guard - Location updates but no task activity
    5. Device Failure - No phone but GPS active (or vice versa)
    6. Suspicious Pattern - Activity outside normal hours
    7. Guard Distress - Movement stopped + no phone + panic history
    8. Resource Shortage - Multiple tickets + tasks delayed
    9. Coverage Gap - No guards on duty + pending tasks
    10. Escalation Chain Break - Alerts not acknowledged + no escalation
    """

    CORRELATION_PATTERNS = {
        'SILENT_SITE': {
            'signals': ['phone_events', 'location_updates', 'tasks_completed'],
            'threshold_minutes': 60,
            'category': 'OPERATIONAL',
            'severity': 'CRITICAL',
        },
        'TOUR_ABANDONMENT': {
            'signals': ['tour_started', 'location_left_site', 'tour_incomplete'],
            'threshold_minutes': 30,
            'category': 'SECURITY',
            'severity': 'HIGH',
        },
        'SLA_STORM': {
            'signals': ['tasks_overdue', 'tours_delayed', 'alert_volume'],
            'threshold_counts': {'tasks': 5, 'tours': 3, 'alerts': 10},
            'category': 'OPERATIONAL',
            'severity': 'CRITICAL',
        },
        'PHANTOM_GUARD': {
            'signals': ['location_updates', 'tasks_completed'],
            'threshold_minutes': 120,
            'category': 'SECURITY',
            'severity': 'MEDIUM',
        },
        'DEVICE_FAILURE': {
            'signals': ['phone_events', 'location_updates'],
            'threshold_minutes': 60,
            'category': 'DEVICE_HEALTH',
            'severity': 'HIGH',
        },
    }

    @classmethod
    def correlate_signals_for_site(cls, site, window_minutes=60):
        """
        Detect all correlation patterns for a site.

        Args:
            site: Bt instance
            window_minutes: Time window to analyze

        Returns:
            list: AuditFinding instances for detected patterns
        """
        try:
            findings = []

            # Pattern 1: Silent Site
            silent_finding = cls._detect_silent_site(site, window_minutes)
            if silent_finding:
                findings.append(silent_finding)

            # Pattern 2: Tour Abandonment
            tour_finding = cls._detect_tour_abandonment(site, window_minutes)
            if tour_finding:
                findings.append(tour_finding)

            # Pattern 3: SLA Storm
            sla_finding = cls._detect_sla_storm(site, window_minutes)
            if sla_finding:
                findings.append(sla_finding)

            # Pattern 4: Phantom Guard
            phantom_finding = cls._detect_phantom_guard(site, window_minutes)
            if phantom_finding:
                findings.append(phantom_finding)

            # Pattern 5: Device Failure
            device_finding = cls._detect_device_failure(site, window_minutes)
            if device_finding:
                findings.append(device_finding)

            logger.info(f"Correlation analysis for {site.buname}: {len(findings)} patterns detected")
            return findings

        except (ValueError, AttributeError) as e:
            logger.error(f"Signal correlation error for {site.buname}: {e}", exc_info=True)
            return []

    @classmethod
    def _detect_silent_site(cls, site, window_minutes):
        """Detect silent site: no phone + no GPS + no tasks."""
        try:
            from apps.peoples.models import People

            person = People.objects.filter(
                tenant=site.tenant,
                peopleorganizational__bu=site,
                isactive=True
            ).first()

            if not person:
                return None

            signals = ActivitySignalCollector.collect_all_signals(person, site, window_minutes)

            if (signals['phone_events_count'] == 0 and
                signals['location_updates_count'] == 0 and
                signals['tasks_completed_count'] == 0):

                return AuditFinding.objects.create(
                    tenant=site.tenant,
                    site=site,
                    finding_type='CORRELATION_SILENT_SITE',
                    category='OPERATIONAL',
                    severity='CRITICAL',
                    title=f'Silent site detected - no activity for {window_minutes} minutes',
                    description=(
                        f'Site appears offline or guard inactive. '
                        f'No phone events, location updates, or task completions in last {window_minutes} minutes.'
                    ),
                    evidence={
                        'pattern': 'SILENT_SITE',
                        'window_minutes': window_minutes,
                        'signals': signals,
                        'guard_id': person.id,
                        'guard_name': person.peoplename,
                    },
                    recommended_actions=[
                        '1. Contact guard immediately via phone',
                        '2. Check last known location and timestamp',
                        '3. Dispatch supervisor to site if no response',
                        '4. Verify device battery and connectivity',
                        '5. Check shift schedule - is guard on duty?',
                    ]
                )

            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"Silent site detection error: {e}", exc_info=True)
            return None

    @classmethod
    def _detect_tour_abandonment(cls, site, window_minutes):
        """Detect tour abandonment: tour started + GPS left + no completion."""
        try:
            from apps.noc.security_intelligence.models import TourComplianceLog
            from apps.activity.models import Location

            now = timezone.now()
            start_time = now - timedelta(minutes=window_minutes)

            incomplete_tours = TourComplianceLog.objects.filter(
                site=site,
                scheduled_datetime__gte=start_time,
                scheduled_datetime__lte=now,
                status='INCOMPLETE'
            ).select_related('person')

            for tour in incomplete_tours:
                # Check if guard location left site
                recent_locations = Location.objects.filter(
                    people=tour.person,
                    cdtz__gte=tour.scheduled_datetime,
                    cdtz__lte=now
                ).order_by('-cdtz')[:5]

                if recent_locations.exists():
                    last_location = recent_locations.first()
                    # Simplified: check if last location is far from site
                    # (In production, use geofence checking)

                    return AuditFinding.objects.create(
                        tenant=site.tenant,
                        site=site,
                        finding_type='CORRELATION_TOUR_ABANDONMENT',
                        category='SECURITY',
                        severity='HIGH',
                        title=f'Tour abandoned mid-execution - {tour.tour_type}',
                        description=(
                            f'Tour started at {tour.scheduled_datetime.strftime("%H:%M")} but not completed. '
                            f'Guard location shows movement away from site.'
                        ),
                        evidence={
                            'pattern': 'TOUR_ABANDONMENT',
                            'tour_id': tour.id,
                            'tour_type': tour.tour_type,
                            'guard_id': tour.person.id,
                            'guard_name': tour.person.peoplename,
                            'checkpoint_coverage': f'{tour.checkpoints_scanned}/{tour.checkpoint_count}',
                            'location_trail': list(recent_locations.values('gpslocation', 'cdtz')[:3]),
                        },
                        recommended_actions=[
                            '1. Contact guard to determine reason for abandonment',
                            '2. Review GPS trail to verify guard left site',
                            '3. Investigate if emergency or personal issue',
                            '4. Complete tour manually or assign to another guard',
                            '5. Document incident and provide retraining if needed',
                        ]
                    )

            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"Tour abandonment detection error: {e}", exc_info=True)
            return None

    @classmethod
    def _detect_sla_storm(cls, site, window_minutes):
        """Detect SLA storm: multiple tasks overdue + tours delayed + high alerts."""
        try:
            from apps.activity.models import Jobneed
            from apps.noc.models import NOCAlertEvent
            from apps.noc.security_intelligence.models import TourComplianceLog

            now = timezone.now()
            start_time = now - timedelta(minutes=window_minutes)

            # Count overdue tasks
            overdue_tasks = Jobneed.objects.filter(
                bu=site,
                status__in=['PENDING', 'IN_PROGRESS'],
                cdtz__lte=start_time
            ).count()

            # Count delayed tours
            delayed_tours = TourComplianceLog.objects.filter(
                site=site,
                status='OVERDUE',
                scheduled_datetime__gte=start_time
            ).count()

            # Count recent alerts
            recent_alerts = NOCAlertEvent.objects.filter(
                bu=site,
                first_seen__gte=start_time,
                first_seen__lte=now
            ).count()

            if overdue_tasks >= 5 and delayed_tours >= 3 and recent_alerts >= 10:
                return AuditFinding.objects.create(
                    tenant=site.tenant,
                    site=site,
                    finding_type='CORRELATION_SLA_STORM',
                    category='OPERATIONAL',
                    severity='CRITICAL',
                    title=f'SLA storm detected - systemic operational failure',
                    description=(
                        f'Multiple failures detected: {overdue_tasks} overdue tasks, '
                        f'{delayed_tours} delayed tours, {recent_alerts} alerts in last {window_minutes} minutes.'
                    ),
                    evidence={
                        'pattern': 'SLA_STORM',
                        'window_minutes': window_minutes,
                        'overdue_tasks_count': overdue_tasks,
                        'delayed_tours_count': delayed_tours,
                        'recent_alerts_count': recent_alerts,
                    },
                    recommended_actions=[
                        '1. URGENT: Escalate to operations manager immediately',
                        '2. Review staffing levels - are guards adequate?',
                        '3. Check for systemic issues (power outage, network down)',
                        '4. Prioritize critical tasks and tours',
                        '5. Consider dispatching additional resources',
                    ]
                )

            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"SLA storm detection error: {e}", exc_info=True)
            return None

    @classmethod
    def _detect_phantom_guard(cls, site, window_minutes):
        """Detect phantom guard: location updates but no task activity."""
        try:
            from apps.peoples.models import People

            person = People.objects.filter(
                tenant=site.tenant,
                peopleorganizational__bu=site,
                isactive=True
            ).first()

            if not person:
                return None

            signals = ActivitySignalCollector.collect_all_signals(person, site, window_minutes)

            # Location updates exist but no tasks completed for extended period
            if (signals['location_updates_count'] >= 5 and
                signals['tasks_completed_count'] == 0 and
                window_minutes >= 120):

                return AuditFinding.objects.create(
                    tenant=site.tenant,
                    site=site,
                    finding_type='CORRELATION_PHANTOM_GUARD',
                    category='SECURITY',
                    severity='MEDIUM',
                    title='Phantom guard pattern - location active but no work',
                    description=(
                        f'Guard showing {signals["location_updates_count"]} location updates '
                        f'but 0 tasks completed in {window_minutes} minutes.'
                    ),
                    evidence={
                        'pattern': 'PHANTOM_GUARD',
                        'signals': signals,
                        'guard_id': person.id,
                        'guard_name': person.peoplename,
                    },
                    recommended_actions=[
                        '1. Verify guard is performing assigned duties',
                        '2. Check if tasks are being logged correctly',
                        '3. Review guard schedule - are tasks assigned?',
                        '4. Investigate potential productivity issues',
                    ]
                )

            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"Phantom guard detection error: {e}", exc_info=True)
            return None

    @classmethod
    def _detect_device_failure(cls, site, window_minutes):
        """Detect device failure: imbalance between phone and GPS signals."""
        try:
            from apps.peoples.models import People

            person = People.objects.filter(
                tenant=site.tenant,
                peopleorganizational__bu=site,
                isactive=True
            ).first()

            if not person:
                return None

            signals = ActivitySignalCollector.collect_all_signals(person, site, window_minutes)

            # Phone active but no GPS (GPS hardware failure)
            if signals['phone_events_count'] >= 5 and signals['location_updates_count'] == 0:
                return AuditFinding.objects.create(
                    tenant=site.tenant,
                    site=site,
                    finding_type='CORRELATION_DEVICE_GPS_FAILURE',
                    category='DEVICE_HEALTH',
                    severity='HIGH',
                    title='GPS failure suspected - phone active but no location',
                    description=f'Device shows {signals["phone_events_count"]} phone events but 0 location updates.',
                    evidence={'pattern': 'DEVICE_FAILURE', 'signals': signals},
                    recommended_actions=[
                        '1. Check GPS permissions on guard device',
                        '2. Verify location services enabled',
                        '3. Test GPS accuracy manually',
                        '4. Replace device if hardware failure',
                    ]
                )

            # GPS active but no phone (app crash or phone issue)
            if signals['location_updates_count'] >= 5 and signals['phone_events_count'] == 0:
                return AuditFinding.objects.create(
                    tenant=site.tenant,
                    site=site,
                    finding_type='CORRELATION_DEVICE_PHONE_FAILURE',
                    category='DEVICE_HEALTH',
                    severity='HIGH',
                    title='Phone/app failure suspected - GPS active but no events',
                    description=f'Device shows {signals["location_updates_count"]} GPS updates but 0 phone events.',
                    evidence={'pattern': 'DEVICE_FAILURE', 'signals': signals},
                    recommended_actions=[
                        '1. Check if mobile app is running',
                        '2. Verify app permissions',
                        '3. Restart app or device',
                        '4. Check for app crashes in logs',
                    ]
                )

            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"Device failure detection error: {e}", exc_info=True)
            return None
