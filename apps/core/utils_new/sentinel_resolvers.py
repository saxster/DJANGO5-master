"""
Sentinel ID resolver utilities.

This module provides safe methods to handle sentinel/placeholder IDs
that are used throughout the application to represent "NONE" or "SYSTEM"
records. This prevents FK integrity violations and provides consistent
handling of placeholder records.

Purpose:
- Replace hardcoded sentinel IDs (-1, 1) with proper record references
- Ensure FK integrity is maintained
- Provide consistent way to handle "NONE" placeholders
- Enable proper database migrations and constraints
"""

import logging
from typing import Optional, Union
from django.db import transaction, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from apps.core.constants import DatabaseConstants, JobConstants, AssetConstants
from apps.core.utils_new.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


__all__ = [
    'SentinelResolver',
    'get_none_job',
    'get_none_asset',
    'get_none_jobneed',
    'resolve_parent_job',
    'resolve_asset',
    'is_none_record',
    'is_root_record',
]


class SentinelResolver:
    """
    Resolvers for handling sentinel/placeholder records.

    These methods provide safe access to placeholder records that are used
    when a "NONE" or "SYSTEM" value is needed instead of NULL.
    """

    @staticmethod
    @transaction.atomic
    def get_none_job() -> 'Job':
        """
        Get or create the NONE job placeholder record.

        This job serves as a placeholder for parent relationships
        where a "NONE" parent is semantically meaningful.

        Returns:
            Job: The NONE job instance

        Raises:
            IntegrityError: If database constraints are violated
            Exception: For other database errors
        """
        from apps.activity.models.job_model import Job

        try:
            # Try to get existing NONE job
            none_job = Job.objects.filter(
                id=DatabaseConstants.ID_SYSTEM,
                code=DatabaseConstants.DEFAULT_CODE
            ).first()

            if none_job:
                return none_job

            # Create NONE job if it doesn't exist
            none_job = Job.objects.create(
                id=DatabaseConstants.ID_SYSTEM,
                code=DatabaseConstants.DEFAULT_CODE,
                name=DatabaseConstants.DEFAULT_NAME,
                description="System placeholder job - do not delete",
                identifier=JobConstants.Identifier.TASK,
                fromdate="2020-01-01 00:00:00",
                uptodate="2099-12-31 23:59:59",
                planduration=0,
                gracetime=0,
                expirytime=0,
                cron="0 0 1 1 *",  # Never execute (Jan 1st only)
                multifactor=1,
                priority=1,
                parent=None,
                asset=None,
                qset=None
            )

            logger.info(f"Created NONE job placeholder with ID {none_job.id}")
            return none_job

        except IntegrityError as e:
            logger.error(f"Failed to create/get NONE job: {e}")
            # If creation fails due to ID conflict, try to get existing
            try:
                return Job.objects.get(id=DatabaseConstants.ID_SYSTEM)
            except ObjectDoesNotExist:
                raise
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Unexpected error in get_none_job: {e}")
            ErrorHandler.handle_database_error(e, "get_none_job")
            raise

    @staticmethod
    @transaction.atomic
    def get_none_asset() -> 'Asset':
        """
        Get or create the NONE asset placeholder record.

        Returns:
            Asset: The NONE asset instance

        Raises:
            IntegrityError: If database constraints are violated
            Exception: For other database errors
        """
        from apps.activity.models.asset_model import Asset

        try:
            # Try to get existing NONE asset
            none_asset = Asset.objects.filter(
                id=DatabaseConstants.ID_SYSTEM,
                code=DatabaseConstants.DEFAULT_CODE
            ).first()

            if none_asset:
                return none_asset

            # Create NONE asset if it doesn't exist
            none_asset = Asset.objects.create(
                id=DatabaseConstants.ID_SYSTEM,
                code=DatabaseConstants.DEFAULT_CODE,
                name=DatabaseConstants.DEFAULT_NAME,
                description="System placeholder asset - do not delete",
                identifier=AssetConstants.Identifier.ASSET,
                assettype="SYSTEM",
                assetstatus="ACTIVE"
            )

            logger.info(f"Created NONE asset placeholder with ID {none_asset.id}")
            return none_asset

        except IntegrityError as e:
            logger.error(f"Failed to create/get NONE asset: {e}")
            try:
                return Asset.objects.get(id=DatabaseConstants.ID_SYSTEM)
            except ObjectDoesNotExist:
                raise
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Unexpected error in get_none_asset: {e}")
            ErrorHandler.handle_database_error(e, "get_none_asset")
            raise

    @staticmethod
    @transaction.atomic
    def get_none_jobneed() -> 'Jobneed':
        """
        Get or create the NONE jobneed placeholder record.

        Returns:
            Jobneed: The NONE jobneed instance

        Raises:
            IntegrityError: If database constraints are violated
            Exception: For other database errors
        """
        from apps.activity.models.job_model import Jobneed

        try:
            # Try to get existing NONE jobneed
            none_jobneed = Jobneed.objects.filter(
                id=DatabaseConstants.ID_SYSTEM,
                code=DatabaseConstants.DEFAULT_CODE
            ).first()

            if none_jobneed:
                return none_jobneed

            # Get NONE job as parent
            none_job = SentinelResolver.get_none_job()

            # Create NONE jobneed if it doesn't exist
            none_jobneed = Jobneed.objects.create(
                id=DatabaseConstants.ID_SYSTEM,
                code=DatabaseConstants.DEFAULT_CODE,
                name=DatabaseConstants.DEFAULT_NAME,
                description="System placeholder jobneed - do not delete",
                identifier=JobConstants.Identifier.TASK,
                job=none_job,
                plandatetime="2020-01-01 00:00:00",
                expirydatetime="2099-12-31 23:59:59",
                jobstatus="PENDING",
                parent=None  # Top-level placeholder
            )

            logger.info(f"Created NONE jobneed placeholder with ID {none_jobneed.id}")
            return none_jobneed

        except IntegrityError as e:
            logger.error(f"Failed to create/get NONE jobneed: {e}")
            try:
                return Jobneed.objects.get(id=DatabaseConstants.ID_SYSTEM)
            except ObjectDoesNotExist:
                raise
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Unexpected error in get_none_jobneed: {e}")
            ErrorHandler.handle_database_error(e, "get_none_jobneed")
            raise

    @staticmethod
    def resolve_job_parent(parent_id: Union[int, str, None]) -> Optional['Job']:
        """
        Resolve a parent_id to proper Job instance.

        Args:
            parent_id: The parent ID to resolve (-1, 1, None, or valid ID)

        Returns:
            Job instance or None for proper null parent
        """
        if parent_id in (DatabaseConstants.ID_ROOT, -1, None, ""):
            return None  # Proper null parent
        elif parent_id in (DatabaseConstants.ID_SYSTEM, 1):
            return SentinelResolver.get_none_job()
        else:
            # Valid parent ID - let Django handle FK resolution
            return parent_id

    @staticmethod
    def resolve_asset_reference(asset_id: Union[int, str, None]) -> Optional['Asset']:
        """
        Resolve an asset_id to proper Asset instance.

        Args:
            asset_id: The asset ID to resolve (-1, 1, None, or valid ID)

        Returns:
            Asset instance or None
        """
        if asset_id in (DatabaseConstants.ID_ROOT, -1, None, ""):
            return None  # No asset
        elif asset_id in (DatabaseConstants.ID_SYSTEM, 1):
            return SentinelResolver.get_none_asset()
        else:
            # Valid asset ID - let Django handle FK resolution
            return asset_id

    @staticmethod
    def is_none_record(record_id: Union[int, str, None]) -> bool:
        """
        Check if the given ID represents a NONE/placeholder record.

        Args:
            record_id: The ID to check

        Returns:
            bool: True if this is a NONE placeholder
        """
        return record_id in (DatabaseConstants.ID_SYSTEM, 1)

    @staticmethod
    def is_root_record(record_id: Union[int, str, None]) -> bool:
        """
        Check if the given ID represents a ROOT/null record.

        Args:
            record_id: The ID to check

        Returns:
            bool: True if this represents null/root
        """
        return record_id in (DatabaseConstants.ID_ROOT, -1, None, "")


# Convenience functions for common use cases
def get_none_job():
    """Convenience function to get NONE job."""
    return SentinelResolver.get_none_job()


def get_none_asset():
    """Convenience function to get NONE asset."""
    return SentinelResolver.get_none_asset()


def get_none_jobneed():
    """Convenience function to get NONE jobneed."""
    return SentinelResolver.get_none_jobneed()


def resolve_parent_job(parent_id):
    """Convenience function to resolve job parent."""
    return SentinelResolver.resolve_job_parent(parent_id)


def resolve_asset(asset_id):
    """Convenience function to resolve asset reference."""
    return SentinelResolver.resolve_asset_reference(asset_id)

def is_none_record(record_id):
    """Convenience function to check if ID is a NONE record."""
    return SentinelResolver.is_none_record(record_id)


def is_root_record(record_id):
    """Convenience function to check if ID is a ROOT record."""
    return SentinelResolver.is_root_record(record_id)
