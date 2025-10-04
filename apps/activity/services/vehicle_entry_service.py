"""
Vehicle Entry Service - AI/ML-powered license plate recognition and vehicle tracking.

This service processes vehicle images to extract license plate information
for access control, visitor management, and security monitoring.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization where applicable
"""

import logging
import hashlib
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from django.db import transaction, DatabaseError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.conf import settings

from apps.activity.models import Location, VehicleEntry, VehicleSecurityAlert
from apps.onboarding_api.services.ocr_service import get_ocr_service
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class VehicleEntryService:
    """
    Service for processing vehicle license plates via AI/ML image analysis.

    Handles license plate recognition, vehicle tracking, access control,
    and security monitoring with comprehensive validation.
    """

    # US state license plate patterns (expandable)
    STATE_PATTERNS = {
        'CA': [r'[0-9][A-Z]{3}[0-9]{3}', r'[A-Z]{3}[0-9]{4}'],
        'NY': [r'[A-Z]{3}[0-9]{4}', r'[0-9]{3}[A-Z]{3}'],
        'TX': [r'[A-Z]{3}[0-9]{4}', r'[0-9]{3}[A-Z]{3}'],
        'FL': [r'[A-Z]{3}[0-9]{3}', r'[0-9]{3}[A-Z]{3}'],
        'DEFAULT': [r'[A-Z0-9]{3,8}']  # Generic pattern
    }

    def __init__(self):
        """Initialize the vehicle entry service."""
        self.ocr_service = get_ocr_service()

    def process_vehicle_image(
        self,
        photo: UploadedFile,
        gate_location: Optional[Location] = None,
        entry_type: str = 'ENTRY',
        detection_zone: str = '',
        captured_by: Optional[People] = None,
        visitor_info: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Process vehicle image to extract license plate and create entry record.

        Args:
            photo: Uploaded image of vehicle/license plate
            gate_location: Gate or entrance location
            entry_type: Type of entry (ENTRY, EXIT, VISITOR, etc.)
            detection_zone: Specific zone identifier
            captured_by: User who captured the image
            visitor_info: Dictionary with visitor details if applicable

        Returns:
            Complete processing results with validation
        """
        result = {
            'success': False,
            'vehicle_entry': None,
            'license_plate': None,
            'confidence': 0.0,
            'alerts': [],
            'validation_issues': [],
            'error': None
        }

        try:
            # Check for duplicate image first
            image_hash = self._calculate_image_hash(photo)
            if self._is_duplicate_image(image_hash):
                result['error'] = "Duplicate image - entry already processed"
                return result

            # Extract license plate using OCR
            ocr_result = self._extract_license_plate(photo)

            if not ocr_result['success']:
                result['error'] = ocr_result.get('error', 'License plate extraction failed')
                return result

            license_plate = ocr_result['license_plate']
            result['license_plate'] = license_plate
            result['confidence'] = ocr_result['confidence']

            # Validate license plate format
            validation_result = self._validate_license_plate(license_plate)
            result['validation_issues'] = validation_result.get('issues', [])

            # Create vehicle entry record
            with transaction.atomic():
                vehicle_entry = self._create_vehicle_entry(
                    license_plate=license_plate,
                    ocr_result=ocr_result,
                    gate_location=gate_location,
                    entry_type=entry_type,
                    detection_zone=detection_zone,
                    captured_by=captured_by,
                    visitor_info=visitor_info or {},
                    image_hash=image_hash
                )

                # Save image if configured
                if hasattr(settings, 'VEHICLE_ENTRY_STORE_IMAGES') and settings.VEHICLE_ENTRY_STORE_IMAGES:
                    image_path = self._save_vehicle_image(photo, vehicle_entry)
                    vehicle_entry.image_path = image_path
                    vehicle_entry.save(update_fields=['image_path'])

                result['vehicle_entry'] = vehicle_entry
                result['success'] = True

                # Check for security alerts
                alerts = self._check_security_alerts(vehicle_entry)
                result['alerts'] = alerts

                logger.info(
                    f"Vehicle entry processed: {license_plate} at {gate_location.locationname if gate_location else 'unknown'}"
                )

        except ValidationError as e:
            logger.error(f"Validation error in vehicle processing: {str(e)}")
            result['error'] = f"Validation error: {str(e)}"
        except DatabaseError as e:
            logger.error(f"Database error in vehicle processing: {str(e)}")
            result['error'] = f"Database error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in vehicle processing: {str(e)}", exc_info=True)
            result['error'] = f"Processing error: {str(e)}"

        return result

    def record_exit(
        self,
        license_plate: str,
        gate_location: Optional[Location] = None,
        captured_by: Optional[People] = None
    ) -> Dict[str, Any]:
        """Record vehicle exit by matching with existing entry."""
        try:
            # Find active entry for this license plate
            license_plate_clean = re.sub(r'[^\w]', '', license_plate.upper())

            active_entry = VehicleEntry.objects.filter(
                license_plate_clean=license_plate_clean,
                entry_type=VehicleEntry.EntryType.ENTRY,
                exit_timestamp__isnull=True,
                status=VehicleEntry.Status.APPROVED
            ).order_by('-entry_timestamp').first()

            if not active_entry:
                return {
                    'success': False,
                    'error': f'No active entry found for license plate {license_plate}'
                }

            # Record exit
            active_entry.record_exit(
                exit_timestamp=timezone.now(),
                captured_by=captured_by
            )

            logger.info(f"Vehicle exit recorded: {license_plate}")

            return {
                'success': True,
                'vehicle_entry': active_entry,
                'duration': active_entry.actual_duration
            }

        except Exception as e:
            logger.error(f"Error recording vehicle exit: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_vehicle_history(
        self,
        license_plate: str,
        days_back: int = 30,
        limit: int = 50
    ) -> List[VehicleEntry]:
        """Get historical entries for a license plate."""
        try:
            license_plate_clean = re.sub(r'[^\w]', '', license_plate.upper())
            cutoff_date = timezone.now() - timedelta(days=days_back)

            return list(
                VehicleEntry.objects.filter(
                    license_plate_clean=license_plate_clean,
                    entry_timestamp__gte=cutoff_date
                )
                .select_related('gate_location', 'captured_by', 'associated_person')
                .order_by('-entry_timestamp')[:limit]
            )

        except Exception as e:
            logger.error(f"Error fetching vehicle history for {license_plate}: {str(e)}")
            return []

    def get_active_vehicles(self, gate_location: Optional[Location] = None) -> List[VehicleEntry]:
        """Get currently active vehicle entries (no exit recorded)."""
        try:
            queryset = VehicleEntry.objects.filter(
                entry_type=VehicleEntry.EntryType.ENTRY,
                exit_timestamp__isnull=True,
                status=VehicleEntry.Status.APPROVED
            )

            if gate_location:
                queryset = queryset.filter(gate_location=gate_location)

            return list(
                queryset
                .select_related('gate_location', 'captured_by', 'associated_person')
                .order_by('-entry_timestamp')
            )

        except Exception as e:
            logger.error(f"Error fetching active vehicles: {str(e)}")
            return []

    def approve_entry(
        self,
        entry_id: int,
        approver: People,
        notes: str = ""
    ) -> bool:
        """Approve a vehicle entry."""
        try:
            with transaction.atomic():
                entry = VehicleEntry.objects.select_for_update().get(id=entry_id)

                entry.status = VehicleEntry.Status.APPROVED
                entry.approved_by = approver
                entry.approved_at = timezone.now()
                entry.notes = f"{entry.notes}\n\nApproved: {notes}".strip()

                entry.save()

                logger.info(f"Vehicle entry {entry_id} approved by {approver.peoplename}")
                return True

        except VehicleEntry.DoesNotExist:
            logger.error(f"Vehicle entry {entry_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error approving entry {entry_id}: {str(e)}")
            return False

    def _extract_license_plate(self, photo: UploadedFile) -> Dict[str, Any]:
        """Extract license plate from image using OCR with specialized patterns."""
        try:
            # Use existing OCR service but with license plate optimization
            ocr_result = self.ocr_service.extract_meter_reading(
                photo=photo,
                meter_type='license_plate',  # Special type for license plates
                expected_unit=None
            )

            if not ocr_result['success']:
                return ocr_result

            # Extract license plate from OCR text
            raw_text = ocr_result.get('raw_text', '')
            license_plate = self._parse_license_plate_from_text(raw_text)

            if not license_plate:
                return {
                    'success': False,
                    'error': 'Could not extract valid license plate from image'
                }

            return {
                'success': True,
                'license_plate': license_plate,
                'confidence': ocr_result.get('confidence', 0.0),
                'raw_text': raw_text,
                'processing_metadata': ocr_result
            }

        except Exception as e:
            logger.error(f"Error extracting license plate: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _parse_license_plate_from_text(self, text: str) -> Optional[str]:
        """Parse license plate from OCR text using pattern matching."""
        if not text:
            return None

        # Clean text and split into potential license plate components
        lines = [line.strip().upper() for line in text.split('\n') if line.strip()]

        for line in lines:
            # Remove common OCR artifacts and clean
            cleaned = re.sub(r'[^\w\s]', '', line)
            cleaned = re.sub(r'\s+', '', cleaned)

            # Try different license plate patterns
            for state, patterns in self.STATE_PATTERNS.items():
                for pattern in patterns:
                    matches = re.findall(pattern, cleaned)
                    if matches:
                        return matches[0]

            # Fallback: look for any alphanumeric sequence of reasonable length
            fallback_matches = re.findall(r'[A-Z0-9]{4,8}', cleaned)
            if fallback_matches:
                return fallback_matches[0]

        return None

    def _validate_license_plate(self, license_plate: str) -> Dict[str, Any]:
        """Validate license plate format and check for issues."""
        issues = []

        if not license_plate:
            issues.append('EMPTY_LICENSE_PLATE')
            return {'passed': False, 'issues': issues}

        # Length validation
        if len(license_plate) < 3:
            issues.append('TOO_SHORT')
        elif len(license_plate) > 12:
            issues.append('TOO_LONG')

        # Character validation
        if not re.match(r'^[A-Z0-9\s-]+$', license_plate.upper()):
            issues.append('INVALID_CHARACTERS')

        # Pattern validation (basic)
        clean_plate = re.sub(r'[^\w]', '', license_plate.upper())
        if not re.match(r'^[A-Z0-9]{3,8}$', clean_plate):
            issues.append('INVALID_FORMAT')

        return {
            'passed': len(issues) == 0,
            'issues': issues
        }

    def _create_vehicle_entry(
        self,
        license_plate: str,
        ocr_result: Dict[str, Any],
        gate_location: Optional[Location],
        entry_type: str,
        detection_zone: str,
        captured_by: Optional[People],
        visitor_info: Dict[str, str],
        image_hash: str
    ) -> VehicleEntry:
        """Create VehicleEntry instance from processing results."""

        # Map entry type to enum
        entry_type_mapping = {
            'entry': VehicleEntry.EntryType.ENTRY,
            'exit': VehicleEntry.EntryType.EXIT,
            'parking': VehicleEntry.EntryType.PARKING,
            'visitor': VehicleEntry.EntryType.VISITOR,
        }

        vehicle_entry = VehicleEntry(
            license_plate=license_plate,
            license_plate_clean=re.sub(r'[^\w]', '', license_plate.upper()),
            entry_type=entry_type_mapping.get(entry_type.lower(), VehicleEntry.EntryType.ENTRY),
            gate_location=gate_location,
            detection_zone=detection_zone,
            capture_method=VehicleEntry.CaptureMethod.AI_CAMERA,
            confidence_score=ocr_result.get('confidence', 0.0),
            image_hash=image_hash,
            raw_ocr_text=ocr_result.get('raw_text', ''),
            processing_metadata={
                'ocr_result': ocr_result,
                'processing_version': '1.0'
            },
            captured_by=captured_by,
            visitor_name=visitor_info.get('name', ''),
            visitor_company=visitor_info.get('company', ''),
            purpose_of_visit=visitor_info.get('purpose', ''),
            notes=visitor_info.get('notes', '')
        )

        # Set initial status
        if vehicle_entry.is_blacklisted:
            vehicle_entry.status = VehicleEntry.Status.DENIED
        elif ocr_result.get('confidence', 0) < 0.6:
            vehicle_entry.status = VehicleEntry.Status.FLAGGED
            vehicle_entry.validation_flags = ['LOW_CONFIDENCE']
        else:
            vehicle_entry.status = VehicleEntry.Status.APPROVED

        vehicle_entry.full_clean()
        vehicle_entry.save()

        return vehicle_entry

    def _check_security_alerts(self, vehicle_entry: VehicleEntry) -> List[VehicleSecurityAlert]:
        """Check for security alerts and create them if needed."""
        alerts = []

        try:
            # Blacklisted vehicle alert
            if vehicle_entry.is_blacklisted:
                alert = VehicleSecurityAlert.objects.create(
                    vehicle_entry=vehicle_entry,
                    alert_type=VehicleSecurityAlert.AlertType.BLACKLISTED_VEHICLE,
                    severity=VehicleSecurityAlert.Severity.CRITICAL,
                    message=f"Blacklisted vehicle detected: {vehicle_entry.license_plate}",
                    license_plate=vehicle_entry.license_plate,
                    location=vehicle_entry.gate_location.locationname if vehicle_entry.gate_location else ''
                )
                alerts.append(alert)

            # Low confidence alert
            if vehicle_entry.confidence_score and vehicle_entry.confidence_score < 0.5:
                alert = VehicleSecurityAlert.objects.create(
                    vehicle_entry=vehicle_entry,
                    alert_type=VehicleSecurityAlert.AlertType.LOW_CONFIDENCE,
                    severity=VehicleSecurityAlert.Severity.MEDIUM,
                    message=f"Low confidence license plate recognition: {vehicle_entry.license_plate} ({vehicle_entry.confidence_score:.2f})",
                    license_plate=vehicle_entry.license_plate,
                    location=vehicle_entry.gate_location.locationname if vehicle_entry.gate_location else ''
                )
                alerts.append(alert)

            # Multiple entries alert (same license plate within short timeframe)
            recent_entries = VehicleEntry.objects.filter(
                license_plate_clean=vehicle_entry.license_plate_clean,
                entry_timestamp__gte=timezone.now() - timedelta(minutes=30)
            ).count()

            if recent_entries > 1:
                alert = VehicleSecurityAlert.objects.create(
                    vehicle_entry=vehicle_entry,
                    alert_type=VehicleSecurityAlert.AlertType.MULTIPLE_ENTRIES,
                    severity=VehicleSecurityAlert.Severity.MEDIUM,
                    message=f"Multiple entries detected for {vehicle_entry.license_plate} within 30 minutes",
                    license_plate=vehicle_entry.license_plate,
                    location=vehicle_entry.gate_location.locationname if vehicle_entry.gate_location else ''
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Error creating security alerts: {str(e)}")

        return alerts

    def _calculate_image_hash(self, photo: UploadedFile) -> str:
        """Calculate SHA256 hash of the uploaded image."""
        try:
            photo.seek(0)
            content = photo.read()
            photo.seek(0)
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.warning(f"Error calculating image hash: {str(e)}")
            return hashlib.sha256(str(datetime.now()).encode()).hexdigest()

    def _is_duplicate_image(self, image_hash: str) -> bool:
        """Check if this image has already been processed recently."""
        cutoff_time = timezone.now() - timedelta(minutes=5)  # 5-minute window
        return VehicleEntry.objects.filter(
            image_hash=image_hash,
            created_at__gte=cutoff_time
        ).exists()

    def _save_vehicle_image(self, photo: UploadedFile, entry: VehicleEntry) -> str:
        """Save the vehicle image to storage."""
        try:
            # Create directory structure
            upload_dir = os.path.join(
                settings.MEDIA_ROOT,
                'vehicle_entries',
                str(entry.business_unit_id) if hasattr(entry, 'business_unit_id') else 'default',
                str(entry.entry_timestamp.year),
                str(entry.entry_timestamp.month)
            )
            os.makedirs(upload_dir, exist_ok=True)

            # Generate filename
            timestamp = entry.entry_timestamp.strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{entry.license_plate_clean}_{entry.id}.jpg"
            file_path = os.path.join(upload_dir, filename)

            # Save file
            with open(file_path, 'wb') as f:
                for chunk in photo.chunks():
                    f.write(chunk)

            # Return relative path
            return os.path.relpath(file_path, settings.MEDIA_ROOT)

        except Exception as e:
            logger.error(f"Error saving vehicle image: {str(e)}")
            return ""


# Factory function
def get_vehicle_entry_service() -> VehicleEntryService:
    """Factory function to get vehicle entry service instance."""
    return VehicleEntryService()