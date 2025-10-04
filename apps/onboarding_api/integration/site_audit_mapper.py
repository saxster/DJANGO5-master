"""
Site Audit to System Configuration Mapper (Phase D).

Maps completed site audits to operational system configurations:
- Coverage plans → Shift schedules
- SOPs → TypeAssist configurations
- Zone requirements → Shift assignments

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling (no bare except)
- Rule #17: transaction.atomic() for all writes
- Rule #12: Query optimization with select_related/prefetch_related
"""

import logging
from datetime import time as datetime_time
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError, DatabaseError
from django.utils import timezone

from apps.onboarding.models import (
    OnboardingSite,
    CoveragePlan,
    SOP,
    Shift,
    TypeAssist,
    Bt
)
from apps.onboarding.models import AIChangeSet, AIChangeRecord
from apps.core.utils_new.db_utils import get_current_db_name
from .mapper import IntegrationAdapter

logger = logging.getLogger(__name__)


class SiteAuditMapper(IntegrationAdapter):
    """
    Extends IntegrationAdapter to map site audit results to system configuration.

    Provides safe, idempotent mapping from security audit data to operational
    shifts, patrol assignments, and SOP-based TypeAssist configurations.
    """

    def map_coverage_plan_to_shifts(
        self,
        coverage_plan: CoveragePlan,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Convert a CoveragePlan into Shift objects.

        Args:
            coverage_plan: CoveragePlan instance with shift_assignments
            dry_run: If True, validate but don't create shifts

        Returns:
            {
                'shifts_created': int,
                'shifts': List[Shift],
                'conflicts': List[Dict],
                'validation_errors': List[str]
            }
        """
        result = {
            'shifts_created': 0,
            'shifts': [],
            'conflicts': [],
            'validation_errors': []
        }

        try:
            shift_assignments = coverage_plan.shift_assignments
            if not shift_assignments:
                result['validation_errors'].append("No shift assignments in coverage plan")
                return result

            site = coverage_plan.site
            client = site.business_unit

            for shift_data in shift_assignments:
                try:
                    shift_result = self._create_shift_from_assignment(
                        shift_data,
                        client,
                        coverage_plan,
                        dry_run
                    )

                    if shift_result['created']:
                        result['shifts_created'] += 1
                        result['shifts'].append(shift_result['shift'])

                    if shift_result['conflicts']:
                        result['conflicts'].extend(shift_result['conflicts'])

                except (ValueError, ValidationError) as e:
                    result['validation_errors'].append(
                        f"Shift {shift_data.get('shift_name', 'unknown')}: {str(e)}"
                    )
                    logger.warning(f"Failed to create shift: {str(e)}")

            logger.info(
                f"Mapped coverage plan to {result['shifts_created']} shifts "
                f"(dry_run={dry_run})"
            )

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error mapping coverage plan: {str(e)}", exc_info=True)
            result['validation_errors'].append(f"Database error: {str(e)}")

        return result

    def _create_shift_from_assignment(
        self,
        shift_data: Dict[str, Any],
        client: Bt,
        coverage_plan: CoveragePlan,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Create or update Shift from shift assignment data."""
        shift_name = shift_data.get('shift_name', 'Unnamed Shift')
        start_time_str = shift_data.get('start_time', '00:00')
        end_time_str = shift_data.get('end_time', '23:59')

        start_time = self._parse_time(start_time_str)
        end_time = self._parse_time(end_time_str)

        staffing = shift_data.get('staffing', {})
        people_count = staffing.get('count', 1)

        existing_shifts = Shift.objects.filter(
            client=client,
            shiftname=shift_name
        ).select_related('client', 'bu')

        conflicts = self._validate_shift_conflicts(
            start_time,
            end_time,
            existing_shifts,
            shift_name
        )

        if dry_run:
            return {
                'created': True,
                'shift': None,
                'conflicts': conflicts
            }

        shift_obj, was_created = self._create_with_idempotency(
            model_class=Shift,
            create_data={
                'shiftname': shift_name,
                'starttime': start_time,
                'endtime': end_time,
                'peoplecount': people_count,
                'client': client,
                'bu': client,
                'enable': True,
                'shift_data': {
                    'source': 'site_audit',
                    'coverage_plan_id': str(coverage_plan.plan_id),
                    'posts_covered': shift_data.get('posts_covered', []),
                    'created_at': timezone.now().isoformat()
                }
            },
            unique_fields=['shiftname', 'client'],
            update_fields=['starttime', 'endtime', 'peoplecount', 'shift_data']
        )

        return {
            'created': was_created,
            'shift': shift_obj,
            'conflicts': conflicts
        }

    def _validate_shift_conflicts(
        self,
        start_time: datetime_time,
        end_time: datetime_time,
        existing_shifts,
        new_shift_name: str
    ) -> List[Dict[str, Any]]:
        """Check for time conflicts with existing shifts."""
        conflicts = []

        for existing in existing_shifts:
            if existing.shiftname == new_shift_name:
                continue

            if self._times_overlap(start_time, end_time, existing.starttime, existing.endtime):
                conflicts.append({
                    'type': 'time_overlap',
                    'existing_shift': existing.shiftname,
                    'existing_time': f"{existing.starttime}-{existing.endtime}",
                    'new_time': f"{start_time}-{end_time}",
                    'resolution': 'review_required'
                })

        return conflicts

    def _times_overlap(
        self,
        start1: datetime_time,
        end1: datetime_time,
        start2: datetime_time,
        end2: datetime_time
    ) -> bool:
        """Check if two time ranges overlap."""
        return start1 < end2 and end1 > start2

    def _parse_time(self, time_str: str) -> datetime_time:
        """Parse time string to datetime.time object."""
        try:
            hours, minutes = map(int, time_str.split(':'))
            return datetime_time(hour=hours, minute=minutes)
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid time format '{time_str}': {e}")
            return datetime_time(hour=0, minute=0)

    def map_sops_to_typeassist(
        self,
        sops: List[SOP],
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Generate TypeAssist configurations from SOPs.

        Creates task types for:
        - SOP-based routine tasks (patrol, inspection, meter reading)
        - Zone-specific checks
        - Asset maintenance tasks

        Args:
            sops: List of SOP instances
            dry_run: If True, validate but don't create TypeAssist entries

        Returns:
            {
                'typeassists_created': int,
                'typeassists': List[TypeAssist],
                'sop_mapping': Dict[str, str]  # sop_id → typeassist_id
            }
        """
        result = {
            'typeassists_created': 0,
            'typeassists': [],
            'sop_mapping': {}
        }

        if not sops:
            logger.info("No SOPs provided for TypeAssist mapping")
            return result

        client = sops[0].site.business_unit

        for sop in sops:
            try:
                ta_result = self._create_typeassist_from_sop(sop, client, dry_run)

                if ta_result['created']:
                    result['typeassists_created'] += 1
                    result['typeassists'].append(ta_result['typeassist'])
                    result['sop_mapping'][str(sop.sop_id)] = str(ta_result['typeassist'].id)

            except (ValueError, ValidationError, DatabaseError) as e:
                logger.error(f"Failed to create TypeAssist from SOP {sop.sop_id}: {str(e)}")

        logger.info(
            f"Mapped {len(sops)} SOPs to {result['typeassists_created']} TypeAssist configs"
        )

        return result

    def _create_typeassist_from_sop(
        self,
        sop: SOP,
        client: Bt,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Create TypeAssist configuration from SOP."""
        ta_code = self._generate_typeassist_code(sop)
        ta_name = sop.sop_title[:100]

        if dry_run:
            return {
                'created': True,
                'typeassist': None
            }

        ta_obj, was_created = self._create_with_idempotency(
            model_class=TypeAssist,
            create_data={
                'tacode': ta_code,
                'taname': ta_name,
                'client': client,
                'bu': client,
                'enable': True,
                'ta_data': {
                    'source': 'sop',
                    'sop_id': str(sop.sop_id),
                    'frequency': sop.frequency,
                    'steps': sop.steps,
                    'compliance_references': sop.compliance_references,
                    'staffing_required': sop.staffing_required
                }
            },
            unique_fields=['tacode', 'client'],
            update_fields=['taname', 'ta_data']
        )

        return {
            'created': was_created,
            'typeassist': ta_obj
        }

    def _generate_typeassist_code(self, sop: SOP) -> str:
        """Generate unique TypeAssist code from SOP."""
        zone_prefix = sop.zone.zone_type[:4].upper() if sop.zone else "GEN"
        frequency_map = {
            'hourly': 'HR',
            'shift': 'SH',
            'daily': 'DY',
            'weekly': 'WK',
            'monthly': 'MO',
            'as_needed': 'AN'
        }
        freq_code = frequency_map.get(sop.frequency, 'XX')

        return f"SOP_{zone_prefix}_{freq_code}_{sop.sop_id.hex[:6].upper()}"

    def apply_site_configuration(
        self,
        site: OnboardingSite,
        changeset: Optional[AIChangeSet] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Apply complete site audit configuration to system.

        Maps coverage plan to shifts and SOPs to TypeAssist, with full
        audit trail via AIChangeSet.

        Args:
            site: OnboardingSite with coverage_plan and sops
            changeset: Optional AIChangeSet for tracking changes
            dry_run: If True, validate but don't apply changes

        Returns:
            {
                'bt_created': List[str],
                'shifts_created': int,
                'typeassists_created': int,
                'audit_trail': List[Dict],
                'errors': List[str]
            }
        """
        result = {
            'bt_created': [],
            'shifts_created': 0,
            'typeassists_created': 0,
            'audit_trail': [],
            'errors': []
        }

        try:
            with transaction.atomic(using=get_current_db_name()):
                if hasattr(site, 'coverage_plan') and site.coverage_plan:
                    shift_result = self.map_coverage_plan_to_shifts(
                        site.coverage_plan,
                        dry_run=dry_run
                    )
                    result['shifts_created'] = shift_result['shifts_created']
                    result['errors'].extend(shift_result['validation_errors'])

                    if changeset and not dry_run:
                        for shift in shift_result['shifts']:
                            self.track_change(
                                changeset=changeset,
                                action=AIChangeRecord.ActionChoices.CREATE,
                                model_instance=shift,
                                sequence_order=len(result['audit_trail'])
                            )
                            result['audit_trail'].append({
                                'action': 'shift_created',
                                'shift_name': shift.shiftname
                            })

                sops = list(site.sops.filter(approved_at__isnull=False))
                if sops:
                    ta_result = self.map_sops_to_typeassist(sops, dry_run=dry_run)
                    result['typeassists_created'] = ta_result['typeassists_created']

                    if changeset and not dry_run:
                        for ta in ta_result['typeassists']:
                            self.track_change(
                                changeset=changeset,
                                action=AIChangeRecord.ActionChoices.CREATE,
                                model_instance=ta,
                                sequence_order=len(result['audit_trail'])
                            )
                            result['audit_trail'].append({
                                'action': 'typeassist_created',
                                'ta_code': ta.tacode
                            })

                if changeset and not dry_run:
                    changeset.status = AIChangeSet.StatusChoices.APPLIED
                    changeset.applied_at = timezone.now()
                    changeset.total_changes = len(result['audit_trail'])
                    changeset.successful_changes = len(result['audit_trail'])
                    changeset.save()

                logger.info(
                    f"Applied site configuration: {result['shifts_created']} shifts, "
                    f"{result['typeassists_created']} typeassists (dry_run={dry_run})"
                )

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Failed to apply site configuration: {str(e)}", exc_info=True)
            result['errors'].append(f"Transaction failed: {str(e)}")
            if changeset:
                changeset.status = AIChangeSet.StatusChoices.FAILED
                changeset.save()

        return result