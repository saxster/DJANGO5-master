"""
NFC Service Layer for Asset Management (Sprint 4.2)

Provides business logic for NFC tag operations:
- Tag binding to assets
- Tag scanning and verification
- Scan logging and audit trail
- Tag status management

Author: Development Team
Date: October 2025
"""

import logging
from typing import Dict, Any, Optional
from datetime import timedelta
from django.db import transaction, DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils import timezone

from apps.activity.models import NFCTag, NFCDevice, NFCScanLog, Asset

logger = logging.getLogger(__name__)


class NFCService:
    """
    Service for NFC tag operations.

    Provides comprehensive NFC tag management including binding,
    scanning, and audit trail.
    """

    def bind_tag_to_asset(
        self,
        tag_uid: str,
        asset_id: int,
        tenant_id: int,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Bind an NFC tag to an asset.

        Args:
            tag_uid: Unique NFC tag identifier (hexadecimal)
            asset_id: Asset ID to bind to
            tenant_id: Tenant ID for multi-tenancy
            metadata: Optional metadata (tag type, manufacturer, etc.)

        Returns:
            Dictionary with binding result:
                - success: Boolean
                - nfc_tag: NFCTag instance (if successful)
                - message: Status message
        """
        try:
            # Validate tag UID format (hex)
            tag_uid = tag_uid.upper().strip()
            if not all(c in '0123456789ABCDEF' for c in tag_uid):
                return {
                    'success': False,
                    'message': 'Invalid tag UID format (must be hexadecimal)'
                }

            # Verify asset exists
            try:
                asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            except Asset.DoesNotExist:
                return {
                    'success': False,
                    'message': f'Asset not found: {asset_id}'
                }

            # Check if tag already exists
            existing_tag = NFCTag.objects.filter(tag_uid=tag_uid).first()
            if existing_tag:
                if existing_tag.asset.id == asset_id:
                    return {
                        'success': True,
                        'nfc_tag': existing_tag,
                        'message': 'Tag already bound to this asset'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Tag already bound to asset: {existing_tag.asset.assetname}'
                    }

            # Create NFC tag binding
            with transaction.atomic():
                nfc_tag = NFCTag.objects.create(
                    tag_uid=tag_uid,
                    asset=asset,
                    tenant_id=tenant_id,
                    status='ACTIVE',
                    metadata=metadata or {},
                    scan_count=0
                )

                logger.info(f"NFC tag {tag_uid} bound to asset {asset.assetname}")

                return {
                    'success': True,
                    'nfc_tag': nfc_tag,
                    'message': 'Tag successfully bound to asset'
                }

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error binding NFC tag: {e}")
            return {
                'success': False,
                'message': 'Database error during tag binding'
            }

        except Exception as e:
            logger.error(f"Unexpected error binding NFC tag: {e}")
            return {
                'success': False,
                'message': 'Internal error during tag binding'
            }

    def record_nfc_scan(
        self,
        tag_uid: str,
        device_id: str,
        tenant_id: int,
        scanned_by_id: Optional[int] = None,
        scan_type: str = 'INSPECTION',
        location_id: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Record an NFC tag scan.

        Args:
            tag_uid: NFC tag UID that was scanned
            device_id: Device ID that performed the scan
            tenant_id: Tenant ID
            scanned_by_id: User ID who performed scan (optional)
            scan_type: Type of scan (CHECKIN, CHECKOUT, INSPECTION, etc.)
            location_id: Location where scan occurred (optional)
            metadata: Additional scan metadata (RSSI, quality, etc.)

        Returns:
            Dictionary with scan result:
                - success: Boolean
                - scan_log: NFCScanLog instance (if successful)
                - asset: Asset information
                - message: Status message
        """
        try:
            # Get NFC tag
            try:
                nfc_tag = NFCTag.objects.select_related('asset').get(
                    tag_uid=tag_uid.upper().strip(),
                    tenant_id=tenant_id
                )
            except NFCTag.DoesNotExist:
                return {
                    'success': False,
                    'message': f'NFC tag not found: {tag_uid}',
                    'scan_result': 'INVALID_TAG'
                }

            # Get NFC device
            try:
                nfc_device = NFCDevice.objects.get(
                    device_id=device_id,
                    tenant_id=tenant_id
                )
            except NFCDevice.DoesNotExist:
                return {
                    'success': False,
                    'message': f'NFC device not found: {device_id}'
                }

            # Check tag status
            if nfc_tag.status != 'ACTIVE':
                return {
                    'success': False,
                    'message': f'Tag status is {nfc_tag.status} (not ACTIVE)',
                    'scan_result': 'INVALID_TAG'
                }

            # Record scan in transaction
            with transaction.atomic():
                scan_log = NFCScanLog.objects.create(
                    tag=nfc_tag,
                    device=nfc_device,
                    scanned_by_id=scanned_by_id,
                    scan_type=scan_type,
                    scan_location_id=location_id,
                    scan_result='SUCCESS',
                    tenant_id=tenant_id,
                    metadata=metadata or {},
                    response_time_ms=metadata.get('response_time_ms') if metadata else None
                )

                # Update tag last_scan and scan_count
                nfc_tag.last_scan = timezone.now()
                nfc_tag.scan_count += 1
                nfc_tag.save(update_fields=['last_scan', 'scan_count'])

                # Update device last_active
                nfc_device.last_active = timezone.now()
                nfc_device.save(update_fields=['last_active'])

                logger.info(
                    f"NFC scan recorded: Tag={tag_uid}, Asset={nfc_tag.asset.assetname}, "
                    f"Type={scan_type}"
                )

                return {
                    'success': True,
                    'scan_log': scan_log,
                    'asset': {
                        'id': nfc_tag.asset.id,
                        'code': nfc_tag.asset.assetcode,
                        'name': nfc_tag.asset.assetname,
                        'status': nfc_tag.asset.runningstatus
                    },
                    'message': 'Scan recorded successfully',
                    'scan_result': 'SUCCESS'
                }

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error recording NFC scan: {e}")
            return {
                'success': False,
                'message': 'Database error during scan recording',
                'scan_result': 'FAILED'
            }

        except Exception as e:
            logger.error(f"Unexpected error recording NFC scan: {e}")
            return {
                'success': False,
                'message': 'Internal error during scan recording',
                'scan_result': 'FAILED'
            }

    def get_scan_history(
        self,
        tag_uid: Optional[str] = None,
        asset_id: Optional[int] = None,
        tenant_id: int = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get scan history for a tag or asset.

        Args:
            tag_uid: NFC tag UID (optional)
            asset_id: Asset ID (optional)
            tenant_id: Tenant ID
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with scan history:
                - scans: List of scan records
                - total_scans: Total scan count
                - date_range: Date range queried
        """
        try:
            # Build query
            since_date = timezone.now() - timedelta(days=days)
            query = NFCScanLog.objects.filter(
                tenant_id=tenant_id,
                cdtz__gte=since_date
            ).select_related('tag', 'device', 'scanned_by')

            if tag_uid:
                query = query.filter(tag__tag_uid=tag_uid.upper().strip())
            if asset_id:
                query = query.filter(tag__asset_id=asset_id)

            scans = query.order_by('-cdtz')[:100]  # Limit to 100 most recent

            scan_list = [
                {
                    'scan_id': scan.id,
                    'tag_uid': scan.tag.tag_uid,
                    'asset_name': scan.tag.asset.assetname,
                    'device_name': scan.device.device_name,
                    'scanned_by': scan.scanned_by.username if scan.scanned_by else None,
                    'scan_type': scan.scan_type,
                    'scan_time': scan.cdtz.isoformat(),
                    'scan_result': scan.scan_result
                }
                for scan in scans
            ]

            return {
                'scans': scan_list,
                'total_scans': query.count(),
                'date_range': {
                    'from': since_date.isoformat(),
                    'to': timezone.now().isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error retrieving scan history: {e}")
            return {
                'scans': [],
                'total_scans': 0,
                'error': str(e)
            }

    def update_tag_status(
        self,
        tag_uid: str,
        new_status: str,
        tenant_id: int
    ) -> Dict[str, Any]:
        """
        Update NFC tag status.

        Args:
            tag_uid: NFC tag UID
            new_status: New status (ACTIVE, INACTIVE, DAMAGED, LOST, DECOMMISSIONED)
            tenant_id: Tenant ID

        Returns:
            Dictionary with update result
        """
        try:
            nfc_tag = NFCTag.objects.get(
                tag_uid=tag_uid.upper().strip(),
                tenant_id=tenant_id
            )

            old_status = nfc_tag.status
            nfc_tag.status = new_status
            nfc_tag.save(update_fields=['status'])

            logger.info(f"NFC tag {tag_uid} status updated: {old_status} → {new_status}")

            return {
                'success': True,
                'message': f'Tag status updated to {new_status}',
                'old_status': old_status,
                'new_status': new_status
            }

        except NFCTag.DoesNotExist:
            return {
                'success': False,
                'message': f'NFC tag not found: {tag_uid}'
            }

        except Exception as e:
            logger.error(f"Error updating tag status: {e}")
            return {
                'success': False,
                'message': 'Error updating tag status'
            }
