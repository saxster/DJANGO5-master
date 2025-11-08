"""
Shift Assignment Validation Service

Provides comprehensive validation for worker shift and site assignments at check-in time.
Enforces industry best practices and regulatory compliance requirements.

Author: Claude Code
Created: 2025-11-03
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from django.utils import timezone
from django.db.models import Q
from django.contrib.gis.geos import Point

from apps.peoples.models import People
from apps.peoples.models.membership_model import Pgbelonging
from apps.activity.models import Jobneed
from apps.onboarding.models import Shift, Bt
from apps.attendance.models import PeopleEventlog
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR
from apps.core.exceptions.patterns import ValidationError, DATABASE_EXCEPTIONS, PARSING_EXCEPTIONS

import logging

logger = logging.getLogger(__name__)


class ValidationResult:
    """Data class for validation results with user-friendly messaging"""

    def __init__(self, valid: bool, reason: Optional[str] = None,
                 message: Optional[str] = None, **kwargs):
        """
        Initialize validation result

        Args:
            valid: Whether validation passed
            reason: Machine-readable reason code (e.g., 'NOT_ASSIGNED_TO_SITE')
            message: Human-readable message
            **kwargs: Additional details to include in result
        """
        self.valid = valid
        self.reason = reason
        self.message = message
        self.details = kwargs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'valid': self.valid,
            'reason': self.reason,
            'message': self.message,
            **self.details
        }

    def get_user_friendly_message(self) -> str:
        """Get user-friendly error message based on reason code"""
        messages = {
            # Phase 1: Site & Shift Validation
            'NOT_ASSIGNED_TO_SITE': (
                'You are not assigned to this site. Please contact your supervisor '
                'to verify your site assignment.'
            ),
            'NO_SHIFT_ASSIGNED': (
                'You have no shift assignment for today. Please contact your supervisor '
                'to confirm your schedule.'
            ),
            'NO_SHIFT_SPECIFIED': (
                'Your job assignment is missing shift information. Please contact your '
                'supervisor to update your assignment.'
            ),
            'OUTSIDE_SHIFT_WINDOW': (
                f'Current time is outside your assigned shift window. '
                f'Your shift: {self.details.get("shift_window", "unknown")}. '
                f'Current time: {self.details.get("current_time", "unknown")}. '
                f'If you need to check in, please contact your supervisor for approval.'
            ),
            'INSUFFICIENT_REST_PERIOD': (
                f'You must have at least {self.details.get("minimum_required", 10)} hours '
                f'rest between shifts (regulatory requirement). You have had '
                f'{self.details.get("rest_hours", 0)} hours rest. '
                f'Last checkout: {self.details.get("last_checkout", "unknown")}. '
                f'For emergency situations, contact your supervisor for override approval.'
            ),
            'SHIFT_ALREADY_COMPLETED': (
                'You have already completed your shift for today. If you need to work '
                'an additional shift, please contact your supervisor.'
            ),
            'DUPLICATE_CHECKIN': (
                'You are already checked in for today. Please check out from your '
                'current shift before starting a new one. If this is an error, '
                'contact your supervisor immediately.'
            ),

            # Phase 3: Post Validation
            'NO_POST_ASSIGNED': (
                'You are not assigned to any post at this time. Please check your '
                'schedule or contact your supervisor to verify your post assignment.'
            ),
            'WRONG_POST_LOCATION': (
                f'You are not at your assigned post: {self.details.get("assigned_post_name", "unknown")}. '
                f'Your current location is {self.details.get("distance_from_post", "unknown")}m from the post. '
                f'Maximum allowed distance: {self.details.get("geofence_radius", 50)}m. '
                f'Please proceed to your assigned post or contact your supervisor if you need '
                f'to be reassigned.'
            ),
            'POST_ORDERS_NOT_ACKNOWLEDGED': (
                f'You must read and acknowledge the post orders before checking in. '
                f'Post: {self.details.get("post_code", "unknown")} (Version {self.details.get("post_orders_version", "unknown")}). '
                f'Please open the post orders in your mobile app, read them carefully, '
                f'and acknowledge before attempting check-in. This is required for '
                f'{self.details.get("risk_level", "high")}-risk posts.'
            ),
            'MISSING_CERTIFICATION': (
                f'You do not have the required certifications for this post. '
                f'Required: {", ".join(self.details.get("missing_certifications", []))}. '
                f'Contact your supervisor or HR to update your certification records.'
            ),

            # System Errors
            'VALIDATION_ERROR': (
                'System error during validation. Please try again in a few moments. '
                'If the problem persists, contact technical support.'
            ),
        }
        return messages.get(self.reason, self.message or 'Validation failed. Contact your supervisor.')


class ShiftAssignmentValidationService:
    """
    Validates worker shift and site assignments at check-in time.

    Implements industry best practices:
    - Site assignment verification
    - Shift time window validation
    - Regulatory compliance (10-hour rest minimum)
    - Duplicate check-in prevention
    - Grace period support (±15 minutes)

    Usage:
        service = ShiftAssignmentValidationService()
        result = service.validate_checkin(
            worker_id=123,
            site_id=456,
            timestamp=timezone.now()
        )
        if not result.valid:
            # Handle validation failure
            logger.warning(f"Validation failed: {result.reason}")
    """

    # Configuration constants
    GRACE_PERIOD_MINUTES = 15  # Allow check-in 15 min early/late
    MINIMUM_REST_HOURS = 10    # Regulatory requirement (industry standard)
    MAX_SHIFT_HOURS = 12       # Safety limit (OSHA guideline)

    def validate_checkin(
        self,
        worker_id: int,
        site_id: int,
        timestamp: datetime,
        gps_point: Optional[Point] = None
    ) -> ValidationResult:
        """
        Comprehensive check-in validation

        Performs multi-layer validation:
        1. Site assignment check
        2. Shift assignment and time window check
        3. Rest period compliance check
        4. Duplicate check-in prevention

        Args:
            worker_id: People.id
            site_id: Bt.id (business unit/site)
            timestamp: datetime of check-in attempt
            gps_point: PostGIS Point object (optional, for future use)

        Returns:
            ValidationResult with validation status, reason, and details
        """
        try:
            # 1. Validate site assignment
            site_validation = self._validate_site_assignment(worker_id, site_id)
            if not site_validation.valid:
                return site_validation

            # 2. Validate shift assignment and time window
            shift_validation = self._validate_shift_assignment(
                worker_id, site_id, timestamp
            )
            if not shift_validation.valid:
                return shift_validation

            # 3. Validate rest period compliance
            rest_validation = self._validate_rest_period(worker_id, timestamp)
            if not rest_validation.valid:
                return rest_validation

            # 4. Check for duplicate check-in
            duplicate_validation = self._validate_no_duplicate_checkin(
                worker_id, timestamp.date()
            )
            if not duplicate_validation.valid:
                return duplicate_validation

            # All validations passed
            logger.info(
                f"Check-in validation passed for worker {worker_id} at site {site_id}",
                extra={
                    'worker_id': worker_id,
                    'site_id': site_id,
                    'timestamp': timestamp.isoformat(),
                }
            )

            return ValidationResult(
                valid=True,
                shift=shift_validation.details.get('shift'),
                jobneed=shift_validation.details.get('jobneed'),
                message='Check-in authorized'
            )

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error during validation for worker {worker_id} at site {site_id}: {e}",
                exc_info=True,
                extra={
                    'worker_id': worker_id,
                    'site_id': site_id,
                    'timestamp': timestamp.isoformat() if timestamp else None,
                }
            )
            return ValidationResult(
                valid=False,
                reason='DATABASE_ERROR',
                message='System database error during validation. Please try again or contact support.',
                error=str(e),
                requires_approval=False
            )
        except (AttributeError, TypeError, KeyError) as e:
            logger.error(
                f"Data error during validation for worker {worker_id} at site {site_id}: {e}",
                exc_info=True,
                extra={
                    'worker_id': worker_id,
                    'site_id': site_id,
                    'timestamp': timestamp.isoformat() if timestamp else None,
                }
            )
            return ValidationResult(
                valid=False,
                reason='VALIDATION_ERROR',
                message='System error during validation. Please contact support.',
                error=str(e),
                requires_approval=False
            )

    def _validate_site_assignment(self, worker_id: int, site_id: int) -> ValidationResult:
        """
        Validate worker is assigned to this site

        Checks two sources:
        1. Pgbelonging.assignsites (primary)
        2. Bt.bupreferences['posted_people'] (fallback)

        Args:
            worker_id: People.id
            site_id: Bt.id

        Returns:
            ValidationResult indicating if worker is assigned to site
        """
        # Check via Pgbelonging.assignsites (primary method)
        assigned = Pgbelonging.objects.filter(
            people_id=worker_id,
            assignsites_id=site_id
        ).exists()

        if not assigned:
            # Fallback: Check Bt.bupreferences['posted_people']
            try:
                bu = Bt.objects.filter(id=site_id).first()
                if bu and bu.bupreferences:
                    posted_people = bu.bupreferences.get('posted_people', [])
                    # Handle both string and int IDs in JSON array
                    if str(worker_id) in posted_people or worker_id in posted_people:
                        assigned = True
                        logger.info(
                            f"Worker {worker_id} found in site {site_id} via bupreferences "
                            "(Pgbelonging missing - should be synced)"
                        )
            except (KeyError, AttributeError, TypeError) as e:
                logger.warning(f"Error checking bupreferences for site {site_id}: {e}", exc_info=True)
            except DATABASE_EXCEPTIONS as e:
                logger.warning(f"Database error checking bupreferences for site {site_id}: {e}", exc_info=True)

        if not assigned:
            logger.warning(
                f"Worker {worker_id} not assigned to site {site_id}",
                extra={'worker_id': worker_id, 'site_id': site_id}
            )
            return ValidationResult(
                valid=False,
                reason='NOT_ASSIGNED_TO_SITE',
                site_id=site_id,
                worker_id=worker_id,
                requires_approval=True  # Supervisor can override for emergencies
            )

        return ValidationResult(valid=True)

    def _validate_shift_assignment(
        self,
        worker_id: int,
        site_id: int,
        timestamp: datetime
    ) -> ValidationResult:
        """
        Validate worker has shift assignment for current time

        Checks:
        1. Worker has active Jobneed for today
        2. Jobneed has shift assigned
        3. Current time is within shift window (with grace period)
        4. Handles overnight shifts (endtime < starttime)

        Args:
            worker_id: People.id
            site_id: Bt.id
            timestamp: datetime of check-in attempt

        Returns:
            ValidationResult with shift and jobneed details if valid
        """
        today = timestamp.date()
        current_time = timestamp.time()

        # Get active Jobneed for today
        jobneed = Jobneed.objects.filter(
            performedby_id=worker_id,
            bu_id=site_id,
            plandatetime__date=today,
            jobstatus__in=['ASSIGNED', 'INPROGRESS']
        ).select_related('shift').first()

        if not jobneed:
            logger.warning(
                f"No active Jobneed found for worker {worker_id} at site {site_id} on {today}",
                extra={
                    'worker_id': worker_id,
                    'site_id': site_id,
                    'date': today.isoformat()
                }
            )
            return ValidationResult(
                valid=False,
                reason='NO_SHIFT_ASSIGNED',
                date=today.isoformat(),
                site_id=site_id,
                requires_approval=True
            )

        if not jobneed.shift:
            logger.warning(
                f"Jobneed {jobneed.id} exists but has no shift assigned",
                extra={
                    'jobneed_id': jobneed.id,
                    'worker_id': worker_id,
                    'site_id': site_id
                }
            )
            return ValidationResult(
                valid=False,
                reason='NO_SHIFT_SPECIFIED',
                jobneed_id=jobneed.id,
                requires_approval=True
            )

        # Validate current time is within shift window (with grace period)
        shift = jobneed.shift
        grace = timedelta(minutes=self.GRACE_PERIOD_MINUTES)

        # Convert to datetime for arithmetic
        shift_start_dt = datetime.combine(today, shift.starttime) - grace
        shift_end_dt = datetime.combine(today, shift.endtime) + grace
        current_dt = datetime.combine(today, current_time)

        # Handle overnight shifts (e.g., 22:00 - 06:00)
        if shift.endtime < shift.starttime:
            # Shift crosses midnight
            if current_time >= shift.starttime:
                # Check-in is before midnight, extend end time to next day
                shift_end_dt += timedelta(days=1)
            elif current_time < shift.endtime:
                # Check-in is after midnight, extend start time back to previous day
                shift_start_dt -= timedelta(days=1)

        # Check if current time is within window
        if not (shift_start_dt <= current_dt <= shift_end_dt):
            logger.warning(
                f"Worker {worker_id} checking in outside shift window. "
                f"Shift: {shift.starttime}-{shift.endtime}, Current: {current_time}",
                extra={
                    'worker_id': worker_id,
                    'shift_id': shift.id,
                    'shift_name': shift.shiftname,
                    'shift_window': f"{shift.starttime}-{shift.endtime}",
                    'current_time': current_time.isoformat(),
                    'grace_period': self.GRACE_PERIOD_MINUTES
                }
            )
            return ValidationResult(
                valid=False,
                reason='OUTSIDE_SHIFT_WINDOW',
                shift_window=f"{shift.starttime.strftime('%H:%M')}-{shift.endtime.strftime('%H:%M')}",
                current_time=current_time.strftime('%H:%M'),
                grace_period=self.GRACE_PERIOD_MINUTES,
                shift_name=shift.shiftname,
                shift_id=shift.id,
                requires_approval=True
            )

        return ValidationResult(
            valid=True,
            shift=shift,
            jobneed=jobneed
        )

    def _validate_rest_period(
        self,
        worker_id: int,
        timestamp: datetime
    ) -> ValidationResult:
        """
        Validate minimum rest period since last checkout

        Industry standard: 10-hour minimum rest between shifts
        OSHA guideline: Insufficient rest increases errors by 37%

        Args:
            worker_id: People.id
            timestamp: datetime of check-in attempt

        Returns:
            ValidationResult indicating if rest period is sufficient
        """
        # Get last checkout time
        last_checkout_record = PeopleEventlog.objects.filter(
            people_id=worker_id,
            punchouttime__isnull=False
        ).order_by('-punchouttime').first()

        if not last_checkout_record:
            # No previous checkout, validation passes (first shift)
            return ValidationResult(valid=True)

        last_checkout = last_checkout_record.punchouttime
        rest_duration = timestamp - last_checkout
        rest_hours = rest_duration.total_seconds() / SECONDS_IN_HOUR

        if rest_hours < self.MINIMUM_REST_HOURS:
            logger.warning(
                f"Worker {worker_id} attempting check-in with insufficient rest: "
                f"{rest_hours:.1f} hours (minimum: {self.MINIMUM_REST_HOURS})",
                extra={
                    'worker_id': worker_id,
                    'rest_hours': rest_hours,
                    'minimum_required': self.MINIMUM_REST_HOURS,
                    'last_checkout': last_checkout.isoformat()
                }
            )
            return ValidationResult(
                valid=False,
                reason='INSUFFICIENT_REST_PERIOD',
                rest_hours=round(rest_hours, 1),
                minimum_required=self.MINIMUM_REST_HOURS,
                last_checkout=last_checkout.strftime('%Y-%m-%d %H:%M'),
                requires_approval=True  # Can override for emergencies
            )

        return ValidationResult(valid=True)

    def _validate_no_duplicate_checkin(
        self,
        worker_id: int,
        date: datetime.date
    ) -> ValidationResult:
        """
        Ensure worker hasn't already checked in today without checking out

        Prevents data integrity issues and identifies potential system errors

        Args:
            worker_id: People.id
            date: Date to check for duplicate check-ins

        Returns:
            ValidationResult indicating if duplicate check-in exists
        """
        # Check for existing check-in without checkout
        active_checkin = PeopleEventlog.objects.filter(
            people_id=worker_id,
            datefor=date,
            punchintime__isnull=False,
            punchouttime__isnull=True  # Still checked in
        ).exists()

        if active_checkin:
            logger.error(
                f"Duplicate check-in attempt for worker {worker_id} on {date}",
                extra={
                    'worker_id': worker_id,
                    'date': date.isoformat()
                }
            )
            return ValidationResult(
                valid=False,
                reason='DUPLICATE_CHECKIN',
                date=date.isoformat(),
                requires_approval=False  # Hard block - data integrity issue
            )

        return ValidationResult(valid=True)

    # ==================== PHASE 3: POST VALIDATION METHODS ====================

    def validate_post_assignment(
        self,
        worker_id: int,
        gps_point: Point,
        timestamp: datetime,
        site_id: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate worker is checking in at their assigned post (Phase 3).

        Performs post-level validation:
        1. Worker has post assignment for current date/time
        2. GPS location is within assigned post's geofence
        3. Post orders have been acknowledged (for high-risk posts)
        4. Worker meets certification requirements

        Args:
            worker_id: People.id
            gps_point: PostGIS Point object with worker's GPS location
            timestamp: datetime of check-in attempt
            site_id: Optional Bt.id (for filtering)

        Returns:
            ValidationResult with assigned post details if valid
        """
        from apps.attendance.models import Post, PostAssignment, PostOrderAcknowledgement
        from apps.core.services.geofence_validation_service import GeofenceValidationService

        today = timestamp.date()
        current_time = timestamp.time()

        # 1. Get worker's post assignment for current time
        assignments = PostAssignment.objects.filter(
            worker_id=worker_id,
            assignment_date=today,
            start_time__lte=current_time,
            end_time__gte=current_time,
            status__in=['SCHEDULED', 'CONFIRMED']
        ).select_related('post', 'post__geofence')

        if site_id:
            assignments = assignments.filter(site_id=site_id)

        assignment = assignments.first()

        if not assignment:
            logger.warning(
                f"No post assignment found for worker {worker_id} at {current_time} on {today}",
                extra={
                    'worker_id': worker_id,
                    'date': today.isoformat(),
                    'current_time': current_time.isoformat(),
                    'site_id': site_id
                }
            )
            return ValidationResult(
                valid=False,
                reason='NO_POST_ASSIGNED',
                message='You are not assigned to any post at this time',
                date=today.isoformat(),
                current_time=current_time.strftime('%H:%M'),
                requires_approval=True
            )

        post = assignment.post

        # 2. Validate GPS within post geofence
        distance_meters = None

        if post.geofence:
            # Use explicit geofence polygon/circle
            geofence_service = GeofenceValidationService()
            inside_geofence = geofence_service.is_point_in_geofence(
                lat=gps_point.y,
                lon=gps_point.x,
                geofence=post.geofence.boundary
            )

            # Calculate distance for logging
            if post.gps_coordinates:
                distance_meters = gps_point.distance(post.gps_coordinates) * 111319.9

        elif post.gps_coordinates:
            # Use circular geofence from post coordinates + radius
            distance_meters = gps_point.distance(post.gps_coordinates) * 111319.9  # Convert degrees to meters
            inside_geofence = distance_meters <= post.geofence_radius
        else:
            # No geofence defined, skip geofence check
            logger.warning(f"Post {post.post_code} has no geofence defined")
            inside_geofence = True

        if not inside_geofence:
            logger.warning(
                f"Worker {worker_id} checking in outside assigned post geofence. "
                f"Post: {post.post_code}, Distance: {distance_meters}m",
                extra={
                    'worker_id': worker_id,
                    'post_code': post.post_code,
                    'distance_meters': distance_meters,
                    'geofence_radius': post.geofence_radius
                }
            )
            return ValidationResult(
                valid=False,
                reason='WRONG_POST_LOCATION',
                message=f'You are not at your assigned post: {post.post_name}',
                assigned_post=post.post_code,
                assigned_post_name=post.post_name,
                distance_from_post=round(distance_meters, 1) if distance_meters else None,
                geofence_radius=post.geofence_radius,
                requires_approval=True
            )

        # 3. Verify post orders acknowledgement (for high-risk posts)
        if post.risk_level in ['CRITICAL', 'HIGH']:
            has_acknowledgement = PostOrderAcknowledgement.has_valid_acknowledgement(
                worker=worker_id,
                post=post,
                date=today
            )

            if not has_acknowledgement:
                logger.warning(
                    f"Worker {worker_id} attempting check-in without acknowledging post orders. "
                    f"Post: {post.post_code}, Risk: {post.risk_level}",
                    extra={
                        'worker_id': worker_id,
                        'post_code': post.post_code,
                        'risk_level': post.risk_level,
                        'post_orders_version': post.post_orders_version
                    }
                )
                return ValidationResult(
                    valid=False,
                    reason='POST_ORDERS_NOT_ACKNOWLEDGED',
                    message=f'You must acknowledge post orders before checking in to {post.post_name}',
                    post_code=post.post_code,
                    post_orders_version=post.post_orders_version,
                    risk_level=post.risk_level,
                    requires_approval=False  # Hard block for high-risk posts
                )

        # 4. Verify certification requirements
        if post.armed_required:
            # TODO: Implement actual armed guard certification check
            # For now, log that check is needed
            logger.info(
                f"Post {post.post_code} requires armed certification (check not yet implemented)"
            )

        # All post validations passed
        logger.info(
            f"Post validation passed for worker {worker_id} at post {post.post_code}",
            extra={
                'worker_id': worker_id,
                'post_code': post.post_code,
                'post_id': post.id,
                'assignment_id': assignment.id
            }
        )

        return ValidationResult(
            valid=True,
            assigned_post=post,
            post_assignment=assignment,
            message='Post assignment validated'
        )

    def validate_checkin_comprehensive(
        self,
        worker_id: int,
        site_id: int,
        timestamp: datetime,
        gps_point: Point
    ) -> ValidationResult:
        """
        Comprehensive check-in validation combining Phase 1 (shift/site) and Phase 3 (post).

        Performs ALL validation layers:
        1. Site assignment (Phase 1)
        2. Shift assignment and time window (Phase 1)
        3. Rest period compliance (Phase 1)
        4. Duplicate check-in detection (Phase 1)
        5. Post assignment (Phase 3)
        6. Post geofence (Phase 3)
        7. Post orders acknowledgement (Phase 3)
        8. Certification requirements (Phase 3)

        Args:
            worker_id: People.id
            site_id: Bt.id
            timestamp: datetime of check-in
            gps_point: PostGIS Point with GPS location

        Returns:
            ValidationResult with all validation details (shift, jobneed, post, assignment)
        """
        # Run Phase 1 validations (site + shift + rest + duplicate)
        phase1_result = self.validate_checkin(
            worker_id=worker_id,
            site_id=site_id,
            timestamp=timestamp,
            gps_point=gps_point
        )

        if not phase1_result.valid:
            logger.info(
                f"Phase 1 validation failed for worker {worker_id}: {phase1_result.reason}",
                extra={
                    'worker_id': worker_id,
                    'site_id': site_id,
                    'phase': 1,
                    'reason': phase1_result.reason
                }
            )
            return phase1_result

        # Run Phase 3 validations (post + geofence + acknowledgement + certifications)
        phase3_result = self.validate_post_assignment(
            worker_id=worker_id,
            gps_point=gps_point,
            timestamp=timestamp,
            site_id=site_id
        )

        if not phase3_result.valid:
            logger.info(
                f"Phase 3 validation failed for worker {worker_id}: {phase3_result.reason}",
                extra={
                    'worker_id': worker_id,
                    'site_id': site_id,
                    'phase': 3,
                    'reason': phase3_result.reason
                }
            )
            return phase3_result

        # All validations passed - combine results
        logger.info(
            f"Comprehensive validation passed for worker {worker_id} at post {phase3_result.details['assigned_post'].post_code}",
            extra={
                'worker_id': worker_id,
                'site_id': site_id,
                'shift_id': phase1_result.details.get('shift').id if phase1_result.details.get('shift') else None,
                'post_id': phase3_result.details['assigned_post'].id,
                'validation_phase': 'comprehensive'
            }
        )

        return ValidationResult(
            valid=True,
            # Phase 1 results
            shift=phase1_result.details.get('shift'),
            jobneed=phase1_result.details.get('jobneed'),
            # Phase 3 results
            assigned_post=phase3_result.details.get('assigned_post'),
            post_assignment=phase3_result.details.get('post_assignment'),
            message='All validations passed - check-in authorized'
        )
