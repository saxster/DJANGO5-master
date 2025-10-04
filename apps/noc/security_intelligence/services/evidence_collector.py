"""
Evidence Collector Service.

Collects comprehensive evidence for audit findings from multiple data sources.
Links events, locations, tasks, tours, and alerts to build evidence trail.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger('noc.evidence_collector')


class EvidenceCollector:
    """
    Collects evidence for audit findings.

    Evidence types:
    - Location history (GPS trail)
    - Task logs (completed/pending tasks)
    - Tour logs (checkpoint scans, completion status)
    - Alert history (related NOC alerts)
    - Guard status (last seen, phone activity)
    """

    @classmethod
    def collect_evidence(cls, finding, lookback_minutes=120):
        """
        Collect comprehensive evidence for a finding.

        Args:
            finding: AuditFinding instance
            lookback_minutes: How far back to collect evidence

        Returns:
            dict: Evidence structure
        """
        try:
            end_time = finding.detected_at
            start_time = end_time - timedelta(minutes=lookback_minutes)

            evidence = {
                'collection_window': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'duration_minutes': lookback_minutes,
                },
                'location_history': cls._collect_location_history(finding.site, start_time, end_time),
                'task_logs': cls._collect_task_logs(finding.site, start_time, end_time),
                'tour_logs': cls._collect_tour_logs(finding.site, start_time, end_time),
                'alert_history': cls._collect_alert_history(finding.site, start_time, end_time),
                'guard_status': cls._collect_guard_status(finding.site, end_time),
            }

            return evidence

        except (ValueError, AttributeError) as e:
            logger.error(f"Evidence collection error: {e}", exc_info=True)
            return {}

    @classmethod
    def _collect_location_history(cls, site, start_time, end_time):
        """Collect GPS location updates."""
        from apps.activity.models import Location

        try:
            locations = Location.objects.filter(
                bu=site,
                cdtz__gte=start_time,
                cdtz__lte=end_time,
                gpslocation__isnull=False
            ).order_by('cdtz').values(
                'id', 'people__peoplename', 'gpslocation', 'cdtz', 'accuracy'
            )[:50]  # Limit to 50 most recent

            return list(locations)

        except (ValueError, AttributeError) as e:
            logger.error(f"Location history collection error: {e}", exc_info=True)
            return []

    @classmethod
    def _collect_task_logs(cls, site, start_time, end_time):
        """Collect task completion and status logs."""
        from apps.activity.models import Jobneed

        try:
            tasks = Jobneed.objects.filter(
                bu=site,
                cdtz__gte=start_time,
                cdtz__lte=end_time
            ).order_by('-cdtz').values(
                'id', 'status', 'priority', 'people__peoplename', 'cdtz', 'mdtz'
            )[:20]

            return list(tasks)

        except (ValueError, AttributeError) as e:
            logger.error(f"Task log collection error: {e}", exc_info=True)
            return []

    @classmethod
    def _collect_tour_logs(cls, site, start_time, end_time):
        """Collect tour completion and checkpoint logs."""
        from apps.noc.security_intelligence.models import TourComplianceLog

        try:
            tours = TourComplianceLog.objects.filter(
                site=site,
                scheduled_datetime__gte=start_time,
                scheduled_datetime__lte=end_time
            ).order_by('-scheduled_datetime').values(
                'id', 'tour_type', 'status', 'person__peoplename',
                'checkpoint_count', 'checkpoints_scanned', 'completed_at'
            )[:10]

            return list(tours)

        except (ValueError, AttributeError) as e:
            logger.error(f"Tour log collection error: {e}", exc_info=True)
            return []

    @classmethod
    def _collect_alert_history(cls, site, start_time, end_time):
        """Collect related NOC alerts."""
        from apps.noc.models import NOCAlertEvent

        try:
            alerts = NOCAlertEvent.objects.filter(
                bu=site,
                first_seen__gte=start_time,
                first_seen__lte=end_time
            ).order_by('-first_seen').values(
                'id', 'alert_type', 'severity', 'status', 'message', 'first_seen'
            )[:10]

            return list(alerts)

        except (ValueError, AttributeError) as e:
            logger.error(f"Alert history collection error: {e}", exc_info=True)
            return []

    @classmethod
    def _collect_guard_status(cls, site, check_time):
        """Collect current guard status information."""
        from apps.peoples.models import People
        from apps.activity.models import Location

        try:
            # Get active people for this site
            guards = People.objects.filter(
                tenant=site.tenant,
                peopleorganizational__bu=site,
                isactive=True
            ).values('id', 'peoplename', 'mobno')[:10]

            guard_status = []
            lookback = check_time - timedelta(hours=2)

            for guard in guards:
                # Get last location
                last_location = Location.objects.filter(
                    people_id=guard['id'],
                    cdtz__gte=lookback,
                    cdtz__lte=check_time
                ).order_by('-cdtz').first()

                # Get last phone activity (simplified)
                last_seen = last_location.cdtz if last_location else None

                guard_status.append({
                    'people_id': guard['id'],
                    'name': guard['peoplename'],
                    'last_seen': last_seen.isoformat() if last_seen else None,
                    'phone_active': bool(last_seen and (check_time - last_seen).total_seconds() < 3600),
                    'last_location': {
                        'lat': last_location.gpslocation.y if last_location and last_location.gpslocation else None,
                        'lon': last_location.gpslocation.x if last_location and last_location.gpslocation else None,
                    } if last_location else None,
                })

            return guard_status

        except (ValueError, AttributeError) as e:
            logger.error(f"Guard status collection error: {e}", exc_info=True)
            return []

    @classmethod
    def link_to_finding(cls, finding, evidence_key, entity_type, entity_id):
        """
        Link specific entity to finding evidence.

        Args:
            finding: AuditFinding instance
            evidence_key: String key in evidence dict
            entity_type: String entity type (e.g., 'tour', 'task', 'location')
            entity_id: Integer entity ID

        Returns:
            bool: Success
        """
        try:
            if evidence_key not in finding.evidence:
                finding.evidence[evidence_key] = []

            finding.evidence[evidence_key].append({
                'entity_type': entity_type,
                'entity_id': entity_id,
                'linked_at': timezone.now().isoformat(),
            })

            finding.save(update_fields=['evidence'])
            logger.info(f"Linked {entity_type}:{entity_id} to finding {finding.id}")
            return True

        except (ValueError, AttributeError) as e:
            logger.error(f"Evidence linking error: {e}", exc_info=True)
            return False
