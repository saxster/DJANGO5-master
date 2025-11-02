"""
Signal Correlation Service.

Cross-references activity signals with existing NOC alerts to identify
root causes and operational patterns.

Follows .claude/rules.md Rule #8: All methods < 50 lines.
"""

import logging
from datetime import timedelta
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Q

from apps.noc.models import NOCAlertEvent, CorrelatedIncident
from apps.noc.security_intelligence.services.activity_signal_collector import ActivitySignalCollector

logger = logging.getLogger(__name__)


class SignalCorrelationService:
    """
    Service for correlating activity signals with NOC alerts.

    Identifies patterns and root causes by matching signals with alerts
    based on time proximity and entity relationships.
    """

    DEFAULT_CORRELATION_WINDOW = 15  # minutes

    @classmethod
    def correlate_signals_with_alerts(
        cls,
        person,
        site,
        signals: Dict[str, Any],
        window_minutes: int = None
    ) -> Optional[CorrelatedIncident]:
        """
        Correlate activity signals with existing NOC alerts.

        Creates a CorrelatedIncident if signals match alerts within
        time window for the same person/site.

        Args:
            person: People instance
            site: Site (Bt) instance
            signals: Activity signals from ActivitySignalCollector
            window_minutes: Correlation time window (default 15min)

        Returns:
            CorrelatedIncident if correlation found, None otherwise
        """
        if window_minutes is None:
            window_minutes = cls.DEFAULT_CORRELATION_WINDOW

        try:
            # Find related alerts within time window
            now = timezone.now()
            time_start = now - timedelta(minutes=window_minutes)
            time_end = now + timedelta(minutes=window_minutes)

            related_alerts = cls._find_matching_alerts(
                person=person,
                site=site,
                time_start=time_start,
                time_end=time_end
            )

            if not related_alerts.exists():
                logger.debug(
                    f"No alerts found for correlation: {person.peoplename} @ {site.name}"
                )
                return None

            # Create correlated incident
            incident = cls._create_correlated_incident(
                person=person,
                site=site,
                signals=signals,
                related_alerts=related_alerts,
                window_minutes=window_minutes
            )

            logger.info(
                f"Created correlated incident {incident.incident_id} with "
                f"{related_alerts.count()} alerts for {person.peoplename}"
            )

            return incident

        except Exception as e:
            logger.error(
                f"Error correlating signals for {person.peoplename}: {e}",
                exc_info=True
            )
            return None

    @classmethod
    def _find_matching_alerts(
        cls,
        person,
        site,
        time_start,
        time_end
    ):
        """
        Find NOC alerts matching person/site within time window.

        Args:
            person: People instance
            site: Site instance
            time_start: Start of time window
            time_end: End of time window

        Returns:
            QuerySet of matching NOCAlertEvent instances
        """
        # Match alerts for same person OR same site within time window
        matching_alerts = NOCAlertEvent.objects.filter(
            Q(
                created_at__gte=time_start,
                created_at__lte=time_end
            ) & (
                Q(person=person) |  # Same person
                Q(site=site)        # Same site
            )
        ).select_related('person', 'site').order_by('-created_at')

        return matching_alerts

    @classmethod
    def _create_correlated_incident(
        cls,
        person,
        site,
        signals: Dict[str, Any],
        related_alerts,
        window_minutes: int
    ) -> CorrelatedIncident:
        """
        Create correlated incident with signals and alerts.

        Args:
            person: People instance
            site: Site instance
            signals: Activity signals dict
            related_alerts: QuerySet of related alerts
            window_minutes: Correlation window used

        Returns:
            Created CorrelatedIncident instance
        """
        # Create incident
        incident = CorrelatedIncident.objects.create(
            person=person,
            site=site,
            tenant=person.tenant,
            signals=signals,
            correlation_window_minutes=window_minutes,
            correlation_type='TIME_ENTITY'
        )

        # Link related alerts
        incident.related_alerts.set(related_alerts)

        # Calculate severity and correlation score
        incident.calculate_combined_severity()
        incident.calculate_correlation_score()

        return incident

    @classmethod
    def find_incident_by_person_time(
        cls,
        person,
        time_window_minutes: int = 60
    ) -> List[CorrelatedIncident]:
        """
        Find recent correlated incidents for a person.

        Args:
            person: People instance
            time_window_minutes: How far back to search

        Returns:
            List of CorrelatedIncident instances
        """
        cutoff_time = timezone.now() - timedelta(minutes=time_window_minutes)

        incidents = CorrelatedIncident.objects.filter(
            person=person,
            detected_at__gte=cutoff_time
        ).prefetch_related('related_alerts').order_by('-detected_at')

        return list(incidents)

    @classmethod
    def find_unresolved_incidents(
        cls,
        site=None,
        min_severity: str = 'MEDIUM'
    ) -> List[CorrelatedIncident]:
        """
        Find unresolved correlated incidents.

        Args:
            site: Optional site filter
            min_severity: Minimum severity ('MEDIUM', 'HIGH', 'CRITICAL')

        Returns:
            List of unresolved CorrelatedIncident instances
        """
        severity_order = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        min_severity_index = severity_order.index(min_severity)
        qualifying_severities = severity_order[min_severity_index:]

        query = Q(
            investigated=False,
            combined_severity__in=qualifying_severities
        )

        if site:
            query &= Q(site=site)

        incidents = CorrelatedIncident.objects.filter(query).select_related(
            'person', 'site'
        ).prefetch_related('related_alerts').order_by('-combined_severity', '-detected_at')

        return list(incidents)

    @classmethod
    def mark_incident_investigated(
        cls,
        incident_id,
        investigator,
        notes: str = "",
        root_cause: str = ""
    ) -> bool:
        """
        Mark incident as investigated with findings.

        Args:
            incident_id: CorrelatedIncident UUID
            investigator: People instance (investigator)
            notes: Investigation notes
            root_cause: Root cause description

        Returns:
            bool: True if successful
        """
        try:
            incident = CorrelatedIncident.objects.get(incident_id=incident_id)
            incident.investigated = True
            incident.investigated_by = investigator
            incident.investigated_at = timezone.now()
            incident.investigation_notes = notes

            if root_cause:
                incident.root_cause_identified = True
                incident.root_cause_description = root_cause

            incident.save()

            logger.info(
                f"Incident {incident_id} marked investigated by {investigator.peoplename}"
            )
            return True

        except CorrelatedIncident.DoesNotExist:
            logger.error(f"Incident {incident_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error marking incident investigated: {e}", exc_info=True)
            return False
