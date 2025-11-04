"""
Data Retention and Archival Service

Manages data lifecycle for attendance records.

Retention Policy:
- Active: 2 years (payroll reconciliation)
- Archived: 5 additional years (tax compliance = 7 years total)
- GPS Location: 90 days active, then purged
- Photos: 90 days retention
- Biometric Templates: Delete 30 days after employee departure

Compliance:
- Tax record retention: 7 years
- Payroll records: 2 years active
- Privacy laws: Minimize data retention
"""

from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from typing import Dict, Any, List
from apps.attendance.models import PeopleEventlog
from apps.attendance.models.attendance_photo import AttendancePhoto
from apps.attendance.models.user_behavior_profile import UserBehaviorProfile
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
import logging

logger = logging.getLogger(__name__)


class DataRetentionService:
    """Service for managing attendance data retention lifecycle"""

    # Retention periods (days)
    ACTIVE_RETENTION_DAYS = 730  # 2 years
    ARCHIVE_RETENTION_DAYS = 1825  # 5 additional years (7 total)
    GPS_HISTORY_RETENTION_DAYS = 90
    PHOTO_RETENTION_DAYS = 90
    BIOMETRIC_AFTER_TERMINATION_DAYS = 30

    @classmethod
    def archive_old_records(cls, batch_size: int = 1000, dry_run: bool = False) -> Dict[str, int]:
        """
        Archive attendance records older than active retention period.

        Args:
            batch_size: Number of records to process per batch
            dry_run: Preview without making changes

        Returns:
            Dict with archival statistics
        """
        cutoff_date = timezone.now() - timedelta(days=cls.ACTIVE_RETENTION_DAYS)

        # Find records to archive
        to_archive = PeopleEventlog.objects.filter(
            datefor__lt=cutoff_date.date(),
            is_archived=False  # Assuming we add this field
        )

        total_to_archive = to_archive.count()

        if dry_run:
            logger.info(f"DRY RUN: Would archive {total_to_archive} records")
            return {'total': total_to_archive, 'archived': 0, 'failed': 0}

        archived_count = 0
        failed_count = 0

        # Process in batches
        for i in range(0, total_to_archive, batch_size):
            batch = to_archive[i:i + batch_size]

            try:
                with transaction.atomic():
                    for record in batch:
                        # Archive logic: could move to separate table or mark as archived
                        # For now, we'll just mark it
                        record.is_archived = True
                        record.archived_at = timezone.now()
                        record.save(update_fields=['is_archived', 'archived_at'])

                        archived_count += 1

                logger.info(f"Archived batch {i // batch_size + 1}: {len(batch)} records")

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Failed to archive batch: {e}")
                failed_count += len(batch)

        logger.info(f"Archival complete: archived={archived_count}, failed={failed_count}")
        return {'total': total_to_archive, 'archived': archived_count, 'failed': failed_count}

    @classmethod
    def purge_gps_history(cls, batch_size: int = 1000, dry_run: bool = False) -> Dict[str, int]:
        """
        Purge GPS location data older than retention period.

        Keeps attendance records but removes GPS coordinates.

        Args:
            batch_size: Records per batch
            dry_run: Preview without changes

        Returns:
            Purge statistics
        """
        cutoff_date = timezone.now() - timedelta(days=cls.GPS_HISTORY_RETENTION_DAYS)

        # Find records with GPS data older than retention
        to_purge = PeopleEventlog.objects.filter(
            datefor__lt=cutoff_date.date()
        ).exclude(
            startlocation__isnull=True,
            endlocation__isnull=True
        )

        total_to_purge = to_purge.count()

        if dry_run:
            logger.info(f"DRY RUN: Would purge GPS from {total_to_purge} records")
            return {'total': total_to_purge, 'purged': 0, 'failed': 0}

        purged_count = 0

        try:
            # Bulk update to remove GPS data
            updated = to_purge.update(
                startlocation=None,
                endlocation=None,
                journeypath=None,
                accuracy=None
            )

            purged_count = updated
            logger.info(f"Purged GPS data from {purged_count} records")

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to purge GPS data: {e}")

        return {'total': total_to_purge, 'purged': purged_count, 'failed': 0}

    @classmethod
    def delete_old_photos(cls, batch_size: int = 100, dry_run: bool = False) -> Dict[str, int]:
        """
        Delete photos past retention period.

        Args:
            batch_size: Photos per batch
            dry_run: Preview without changes

        Returns:
            Deletion statistics
        """
        # Find photos past delete_after date
        to_delete = AttendancePhoto.objects.filter(
            delete_after__lt=timezone.now(),
            is_deleted=False
        )

        total_to_delete = to_delete.count()

        if dry_run:
            logger.info(f"DRY RUN: Would delete {total_to_delete} photos")
            return {'total': total_to_delete, 'deleted': 0, 'failed': 0}

        deleted_count = 0
        failed_count = 0

        # Delete in batches
        for i in range(0, total_to_delete, batch_size):
            batch = list(to_delete[i:i + batch_size])

            for photo in batch:
                try:
                    photo.hard_delete()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete photo {photo.id}: {e}")
                    failed_count += 1

        logger.info(f"Photo deletion complete: deleted={deleted_count}, failed={failed_count}")
        return {'total': total_to_delete, 'deleted': deleted_count, 'failed': failed_count}

    @classmethod
    def delete_terminated_employee_data(cls, employee_id: int) -> Dict[str, Any]:
        """
        Delete biometric and sensitive data for terminated employee.

        Runs 30 days after termination.

        Args:
            employee_id: Employee ID

        Returns:
            Deletion statistics
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            employee = User.objects.get(id=employee_id)

            # Check if employee is inactive
            if employee.is_active:
                logger.warning(f"Employee {employee_id} is still active, skipping deletion")
                return {'deleted': False, 'reason': 'Employee still active'}

            # Delete biometric behavior profile
            try:
                profile = UserBehaviorProfile.objects.get(employee=employee)
                profile.delete()
                logger.info(f"Deleted behavior profile for {employee.username}")
            except UserBehaviorProfile.DoesNotExist:
                pass

            # Purge biometric templates from attendance records
            attendance_records = PeopleEventlog.objects.filter(people=employee)
            biometric_purged = attendance_records.update(
                peventlogextras={},  # Clear biometric data
                facerecognitionin=False,
                facerecognitionout=False
            )

            # Delete all photos
            photos = AttendancePhoto.objects.filter(employee=employee)
            photo_count = photos.count()
            for photo in photos:
                photo.hard_delete()

            logger.info(
                f"Deleted terminated employee data for {employee.username}: "
                f"biometric_records={biometric_purged}, photos={photo_count}"
            )

            return {
                'deleted': True,
                'biometric_records_purged': biometric_purged,
                'photos_deleted': photo_count,
                'behavior_profile_deleted': True,
            }

        except User.DoesNotExist:
            logger.error(f"Employee {employee_id} not found")
            return {'deleted': False, 'reason': 'Employee not found'}
        except Exception as e:
            logger.error(f"Failed to delete terminated employee data: {e}", exc_info=True)
            return {'deleted': False, 'reason': str(e)}
