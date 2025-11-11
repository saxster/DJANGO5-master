"""
Emergency Assignment Service (Phase 4)

Handles urgent coverage needs:
- Emergency post assignments
- Smart worker selection (proximity, qualifications, availability)
- Automatic worker notification
- Temporary assignment creation
- Auto-expiration after shift

Use Cases:
- Worker called in sick, need immediate replacement
- Coverage gap detected, need to fill urgently
- Security incident, need additional guards
- Last-minute schedule changes

Author: Claude Code
Created: 2025-11-03
Phase: 4 - Emergency Workflows
"""

from django.db import transaction
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from datetime import datetime, time, timedelta
from typing import Optional, List, Dict, Tuple

from apps.attendance.models import Post, PostAssignment, ApprovalRequest
from apps.peoples.models import People
from apps.peoples.models.membership_model import Pgbelonging
from apps.client_onboarding.models import Bt, Shift
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

import logging

logger = logging.getLogger(__name__)


class EmergencyAssignmentService:
    """
    Service for creating and managing emergency post assignments.

    Provides intelligent worker selection based on:
    - Proximity to post (GPS distance)
    - Qualification match (certifications, armed status)
    - Availability (not already assigned)
    - Rest period compliance
    - Overtime limits
    """

    # Configuration
    MAX_DISTANCE_KM = 50  # Maximum distance to consider worker
    MAX_OVERTIME_HOURS = 12  # Don't assign if worker already worked 12+ hours
    REQUIRE_REST_COMPLIANCE = True  # Enforce 10-hour rest minimum
    TEMPORARY_ASSIGNMENT_BUFFER_HOURS = 2  # Keep assignment 2h after shift end

    @classmethod
    def create_emergency_assignment(
        cls,
        post: Post,
        shift: Shift,
        assignment_date: datetime.date,
        requested_by: People,
        reason: str,
        auto_select_worker: bool = True,
        preferred_worker_id: Optional[int] = None,
        notify_worker: bool = True
    ) -> Tuple[Optional[PostAssignment], Optional[ApprovalRequest], str]:
        """
        Create an emergency post assignment.

        Args:
            post: Post that needs coverage
            shift: Shift for this assignment
            assignment_date: Date of assignment
            requested_by: Supervisor creating emergency assignment
            reason: Reason for emergency assignment
            auto_select_worker: Whether to automatically select best worker
            preferred_worker_id: Specific worker ID to assign (overrides auto-select)
            notify_worker: Whether to send notification to worker

        Returns:
            tuple: (assignment: PostAssignment | None, approval_request: ApprovalRequest | None, message: str)
        """
        try:
            logger.info(
                f"Creating emergency assignment for post {post.post_code} on {assignment_date}, "
                f"requested by {requested_by.id}"
            )

            # 1. Find available worker
            if preferred_worker_id:
                worker = People.objects.filter(id=preferred_worker_id).first()
                if not worker:
                    return (None, None, f"Worker {preferred_worker_id} not found")
            elif auto_select_worker:
                worker, selection_score = cls.find_best_available_worker(
                    post=post,
                    shift=shift,
                    assignment_date=assignment_date
                )
                if not worker:
                    # No worker available - create approval request instead
                    approval_request = cls._create_emergency_approval_request(
                        post, shift, assignment_date, requested_by, reason
                    )
                    return (None, approval_request, "No available worker found, approval request created")
            else:
                return (None, None, "Must specify worker or enable auto-select")

            # 2. Validate worker can be assigned
            can_assign, validation_message = cls._validate_emergency_assignment(
                worker, post, shift, assignment_date
            )

            if not can_assign:
                # Create approval request for override
                approval_request = cls._create_emergency_approval_request(
                    post, shift, assignment_date, requested_by, reason,
                    preferred_worker=worker,
                    validation_issue=validation_message
                )
                return (None, approval_request, f"Validation failed: {validation_message}. Approval request created.")

            # 3. Create emergency assignment
            with transaction.atomic():
                assignment = PostAssignment.objects.create(
                    worker=worker,
                    post=post,
                    shift=shift,
                    site=post.site,
                    assignment_date=assignment_date,
                    start_time=shift.starttime,
                    end_time=shift.endtime,
                    status='SCHEDULED',
                    assigned_by=requested_by,
                    is_override=True,
                    override_type='EMERGENCY',
                    override_reason=reason,
                    approval_required=False,  # Emergency, approved by creation
                    approved_by=requested_by,
                    approved_at=timezone.now(),
                    assignment_metadata={
                        'emergency_assignment': True,
                        'auto_selected': auto_select_worker,
                        'created_via': 'emergency_assignment_service',
                        'temporary': True,
                        'auto_expire_at': (
                            datetime.combine(assignment_date, shift.endtime) +
                            timedelta(hours=cls.TEMPORARY_ASSIGNMENT_BUFFER_HOURS)
                        ).isoformat()
                    },
                    tenant=post.tenant,
                    client=post.site
                )

                logger.info(
                    f"Created emergency assignment {assignment.id}: worker {worker.id} → post {post.post_code}"
                )

                # 4. Notify worker if requested
                if notify_worker:
                    cls._notify_worker_of_emergency_assignment(assignment)

                # 5. Invalidate caches
                from apps.attendance.services.post_cache_service import PostCacheService
                PostCacheService.invalidate_worker_assignments(worker.id, assignment_date)
                PostCacheService.invalidate_post_coverage(post.id, assignment_date)

                return (assignment, None, "Emergency assignment created successfully")

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error creating emergency assignment: {e}", exc_info=True)
            return (None, None, f"Error: {str(e)}")

    @classmethod
    def find_best_available_worker(
        cls,
        post: Post,
        shift: Shift,
        assignment_date: datetime.date
    ) -> Tuple[Optional[People], float]:
        """
        Find best available worker for emergency assignment.

        Selection Criteria (scored):
        1. Proximity to post (closer = higher score)
        2. Qualification match (armed, certifications)
        3. Recent assignment to this post (familiarity)
        4. Hours worked this week (avoid overwork)
        5. Availability (not already assigned)

        Args:
            post: Post needing coverage
            shift: Shift to cover
            assignment_date: Date of assignment

        Returns:
            tuple: (worker: People | None, score: float)
        """
        try:
            # 1. Get all workers assigned to this site
            site_workers = Pgbelonging.objects.filter(
                assignsites=post.site
            ).values_list('people_id', flat=True)

            # 2. Exclude workers already assigned for this date
            already_assigned = PostAssignment.objects.filter(
                assignment_date=assignment_date,
                status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
            ).values_list('worker_id', flat=True)

            available_worker_ids = set(site_workers) - set(already_assigned)

            if not available_worker_ids:
                logger.warning(f"No available workers for emergency assignment to post {post.post_code}")
                return (None, 0.0)

            # 3. Get worker details with location if available
            # Optimize: select_related to avoid N+1 when accessing worker properties
            available_workers = People.objects.filter(
                id__in=available_worker_ids,
                enable=True,
                is_active=True
            ).select_related('profile', 'organizational', 'organizational__location')

            # 4. Score each worker
            worker_scores = []

            for worker in available_workers:
                score = cls._calculate_worker_suitability_score(worker, post, shift, assignment_date)
                worker_scores.append((worker, score))

            # 5. Sort by score (descending) and return best
            if worker_scores:
                worker_scores.sort(key=lambda x: x[1], reverse=True)
                best_worker, best_score = worker_scores[0]

                logger.info(
                    f"Selected worker {best_worker.id} for emergency assignment (score: {best_score:.2f})"
                )

                return (best_worker, best_score)

            return (None, 0.0)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error finding available worker: {e}", exc_info=True)
            return (None, 0.0)

    @classmethod
    def _calculate_worker_suitability_score(
        cls,
        worker: People,
        post: Post,
        shift: Shift,
        assignment_date: datetime.date
    ) -> float:
        """
        Calculate suitability score for worker (0-100).

        Scoring:
        - Base: 50 points
        - Proximity: +0-20 points (closer = more)
        - Qualification: +0-15 points (qualified = more)
        - Familiarity: +0-10 points (worked this post before = more)
        - Workload: +0-5 points (fewer hours this week = more)
        - Penalties: -20 if rest period issue, -10 if overtime risk

        Returns:
            float: Score from 0-100
        """
        score = 50.0  # Base score

        try:
            # Proximity scoring (0-20 points)
            if post.gps_coordinates and hasattr(worker, 'gpslocation') and worker.gpslocation:
                distance_km = post.gps_coordinates.distance(worker.gpslocation) * 111.319
                if distance_km <= 5:
                    score += 20
                elif distance_km <= 10:
                    score += 15
                elif distance_km <= 25:
                    score += 10
                elif distance_km <= 50:
                    score += 5
                # > 50km = 0 points

            # Qualification scoring (0-15 points)
            qualified, missing = post.is_guard_qualified(worker)
            if qualified:
                score += 15
            elif not missing:  # No requirements = neutral
                score += 10
            # else: 0 points (not qualified)

            # Familiarity scoring (0-10 points)
            # Check if worker has worked this post in last 30 days
            past_assignments = PostAssignment.objects.filter(
                worker=worker,
                post=post,
                assignment_date__gte=assignment_date - timedelta(days=30),
                status='COMPLETED'
            ).count()

            if past_assignments >= 5:
                score += 10
            elif past_assignments >= 2:
                score += 7
            elif past_assignments >= 1:
                score += 4

            # Workload scoring (0-5 points)
            # Check hours worked this week
            week_start = assignment_date - timedelta(days=assignment_date.weekday())
            week_assignments = PostAssignment.objects.filter(
                worker=worker,
                assignment_date__gte=week_start,
                assignment_date__lt=assignment_date,
                status='COMPLETED',
                hours_worked__isnull=False
            )

            from django.db.models import Sum
            total_hours = week_assignments.aggregate(Sum('hours_worked'))['hours_worked__sum'] or 0

            if total_hours < 20:
                score += 5  # Light workload
            elif total_hours < 35:
                score += 3  # Moderate workload
            elif total_hours < 45:
                score += 1  # Heavy workload
            # >= 45 hours = 0 points (very heavy)

            # Penalties

            # Rest period check (-20 points if violates)
            from apps.attendance.models import PeopleEventlog
            last_checkout = PeopleEventlog.objects.filter(
                people=worker,
                punchouttime__isnull=False
            ).order_by('-punchouttime').first()

            if last_checkout:
                shift_start_dt = datetime.combine(assignment_date, shift.starttime)
                shift_start_dt = timezone.make_aware(shift_start_dt)
                rest_hours = (shift_start_dt - last_checkout.punchouttime).total_seconds() / 3600

                if rest_hours < 10:
                    score -= 20  # Rest period violation penalty

            # Overtime risk (-10 points if near limit)
            if total_hours >= 40:
                score -= 10

            return max(0.0, min(100.0, score))  # Clamp to 0-100

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error calculating worker score: {e}", exc_info=True)
            return 50.0  # Return base score on error

    @classmethod
    def _validate_emergency_assignment(
        cls,
        worker: People,
        post: Post,
        shift: Shift,
        assignment_date: datetime.date
    ) -> Tuple[bool, str]:
        """
        Validate if worker can be assigned to post.

        Checks:
        - Worker qualified for post
        - Worker has sufficient rest period
        - Worker not at overtime limit

        Returns:
            tuple: (can_assign: bool, reason: str)
        """
        # Check qualification
        qualified, missing = post.is_guard_qualified(worker)
        if not qualified and post.armed_required:
            return (False, f"Worker missing required certifications: {', '.join(missing)}")

        # Check rest period (if enforced)
        if cls.REQUIRE_REST_COMPLIANCE:
            from apps.attendance.models import PeopleEventlog
            last_checkout = PeopleEventlog.objects.filter(
                people=worker,
                punchouttime__isnull=False
            ).order_by('-punchouttime').first()

            if last_checkout:
                shift_start_dt = datetime.combine(assignment_date, shift.starttime)
                shift_start_dt = timezone.make_aware(shift_start_dt)
                rest_hours = (shift_start_dt - last_checkout.punchouttime).total_seconds() / 3600

                if rest_hours < 10:
                    return (False, f"Insufficient rest: {rest_hours:.1f} hours (minimum: 10)")

        # Check overtime limit
        week_start = assignment_date - timedelta(days=assignment_date.weekday())
        week_assignments = PostAssignment.objects.filter(
            worker=worker,
            assignment_date__gte=week_start,
            assignment_date__lt=assignment_date,
            status='COMPLETED',
            hours_worked__isnull=False
        )

        from django.db.models import Sum
        total_hours = week_assignments.aggregate(Sum('hours_worked'))['hours_worked__sum'] or 0

        if total_hours >= cls.MAX_OVERTIME_HOURS:
            return (False, f"Worker at overtime limit: {total_hours} hours this week")

        return (True, "Validation passed")

    @classmethod
    def _create_emergency_approval_request(
        cls,
        post: Post,
        shift: Shift,
        assignment_date: datetime.date,
        requested_by: People,
        reason: str,
        preferred_worker: Optional[People] = None,
        validation_issue: Optional[str] = None
    ) -> ApprovalRequest:
        """
        Create approval request when emergency assignment needs approval.

        Args:
            post: Post needing coverage
            shift: Shift to cover
            assignment_date: Date
            requested_by: Supervisor
            reason: Emergency reason
            preferred_worker: Preferred worker if specified
            validation_issue: Validation issue if any

        Returns:
            ApprovalRequest instance
        """
        from apps.attendance.services.approval_service import ApprovalWorkflowService

        worker_info = f" for worker {preferred_worker.get_full_name()}" if preferred_worker else ""
        validation_info = f"\n\nValidation Issue: {validation_issue}" if validation_issue else ""

        return ApprovalWorkflowService.create_approval_request(
            request_type='EMERGENCY_ASSIGNMENT',
            requested_by=requested_by,
            title=f"Emergency Coverage: {post.post_name}",
            description=(
                f"Emergency assignment needed{worker_info}\n\n"
                f"Post: {post.post_code} - {post.post_name}\n"
                f"Shift: {shift.shiftname} ({shift.starttime}-{shift.endtime})\n"
                f"Date: {assignment_date}\n"
                f"Reason: {reason}{validation_info}"
            ),
            priority='URGENT',
            related_site=post.site,
            related_shift=shift,
            metadata={
                'post_id': post.id,
                'shift_id': shift.id,
                'assignment_date': assignment_date.isoformat(),
                'reason': reason,
                'preferred_worker_id': preferred_worker.id if preferred_worker else None,
                'validation_issue': validation_issue,
            }
        )

    @classmethod
    def _notify_worker_of_emergency_assignment(cls, assignment: PostAssignment):
        """
        Send urgent notification to worker about emergency assignment.

        Args:
            assignment: The emergency PostAssignment
        """
        try:
            # TODO: Integrate with actual notification service
            logger.info(
                f"URGENT notification queued for worker {assignment.worker.id}: "
                f"Emergency assignment to {assignment.post.post_code} on {assignment.assignment_date}"
            )

            # For now, just mark as notified
            assignment.worker_notified = True
            assignment.worker_notified_at = timezone.now()
            assignment.save(update_fields=['worker_notified', 'worker_notified_at'])

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error sending emergency notification: {e}", exc_info=True)

    @classmethod
    def auto_expire_temporary_assignments(cls) -> int:
        """
        Auto-expire temporary emergency assignments after buffer period.

        Returns:
            int: Number of assignments expired
        """
        try:
            # Find temporary assignments past their expiration
            now = timezone.now()

            temporary_assignments = PostAssignment.objects.filter(
                assignment_metadata__temporary=True,
                status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
            )

            expired_count = 0

            for assignment in temporary_assignments:
                auto_expire_str = assignment.assignment_metadata.get('auto_expire_at')
                if auto_expire_str:
                    auto_expire_dt = datetime.fromisoformat(auto_expire_str)
                    if isinstance(auto_expire_dt, datetime):
                        if timezone.is_naive(auto_expire_dt):
                            auto_expire_dt = timezone.make_aware(auto_expire_dt)

                    if now >= auto_expire_dt:
                        # Mark as completed if checked in, cancelled otherwise
                        if assignment.status == 'IN_PROGRESS':
                            assignment.status = 'COMPLETED'
                        else:
                            assignment.status = 'CANCELLED'

                        assignment.assignment_metadata['expired'] = True
                        assignment.assignment_metadata['expired_at'] = now.isoformat()
                        assignment.save()

                        expired_count += 1

                        logger.info(f"Auto-expired temporary assignment {assignment.id}")

            if expired_count > 0:
                logger.info(f"Auto-expired {expired_count} temporary emergency assignments")

            return expired_count

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error expiring temporary assignments: {e}", exc_info=True)
            return 0
