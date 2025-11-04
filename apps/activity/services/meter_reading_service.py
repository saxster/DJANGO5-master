"""
Meter Reading Service - AI/ML-powered meter data capture and processing.

This service integrates the OCR service with Asset models to provide
complete meter reading functionality with validation and analytics.

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization where applicable
"""

import logging
import hashlib
import os
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from django.db import transaction, DatabaseError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.conf import settings

from apps.activity.models import Asset, MeterReading, MeterReadingAlert
from apps.core_onboarding.services.ocr_service import get_ocr_service
from apps.peoples.models import People
from apps.ml_training.integrations import track_meter_reading_result

logger = logging.getLogger(__name__)


class MeterReadingService:
    """
    Service for processing meter readings via AI/ML image analysis.

    Integrates OCR service with meter tracking, validation, and analytics.
    """

    def __init__(self):
        """Initialize the meter reading service."""
        self.ocr_service = get_ocr_service()

    def process_meter_photo(
        self,
        asset_id: int,
        photo: UploadedFile,
        user: People,
        expected_range: Optional[Tuple[float, float]] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Process a meter photo to extract and store reading.

        Args:
            asset_id: ID of the asset/meter
            photo: Uploaded photo of the meter
            user: User who captured the photo
            expected_range: Optional (min, max) range for validation
            notes: Additional notes

        Returns:
            Complete processing results with validation
        """
        result = {
            'success': False,
            'meter_reading': None,
            'ocr_result': None,
            'validation_issues': [],
            'anomaly_detected': False,
            'error': None
        }

        try:
            # Get and validate asset
            asset = self._get_and_validate_asset(asset_id)
            if not asset:
                result['error'] = f"Asset {asset_id} not found or not a meter"
                return result

            # Determine meter type from asset data
            meter_type = self._determine_meter_type(asset)

            # Check for duplicate image
            image_hash = self._calculate_image_hash(photo)
            if self._is_duplicate_image(asset, image_hash):
                result['error'] = "Duplicate image - reading already exists"
                return result

            # Extract reading using OCR
            ocr_result = self.ocr_service.extract_meter_reading(
                photo=photo,
                meter_type=meter_type,
                expected_unit=self._get_expected_unit(meter_type),
                validation_range=expected_range
            )
            result['ocr_result'] = ocr_result

            if not ocr_result['success']:
                result['error'] = ocr_result.get('error', 'OCR processing failed')
                return result

            # Create meter reading record
            with transaction.atomic():
                meter_reading = self._create_meter_reading(
                    asset=asset,
                    ocr_result=ocr_result,
                    meter_type=meter_type,
                    user=user,
                    image_hash=image_hash,
                    notes=notes
                )

                # Save image if configured
                if hasattr(settings, 'METER_READING_STORE_IMAGES') and settings.METER_READING_STORE_IMAGES:
                    image_path = self._save_meter_image(photo, meter_reading)
                    meter_reading.image_path = image_path
                    meter_reading.save(update_fields=['image_path'])

                result['meter_reading'] = meter_reading
                result['success'] = True

                # ML Training Integration: Track low-confidence readings for model improvement
                # Only capture uncertain predictions (confidence < 0.7) to focus on hard cases
                if ocr_result['confidence'] < 0.7:
                    try:
                        track_meter_reading_result(
                            meter_reading=meter_reading,
                            confidence_score=ocr_result['confidence'],
                            raw_ocr_text=ocr_result.get('raw_text', '')
                        )
                        logger.debug(
                            f"Low-confidence meter reading tracked for ML training: "
                            f"confidence={ocr_result['confidence']:.2f}"
                        )
                    except Exception as e:
                        # Non-critical: Log but don't fail the main operation
                        logger.warning(f"Failed to track meter reading for ML training: {e}")

                # Check for anomalies and create alerts
                if meter_reading.is_anomaly:
                    result['anomaly_detected'] = True
                    self._create_anomaly_alert(meter_reading)

                # Collect validation issues
                result['validation_issues'] = meter_reading.validation_flags or []

                logger.info(
                    f"Meter reading processed successfully: {asset.assetname} = "
                    f"{meter_reading.reading_value} {meter_reading.unit}"
                )

        except ValidationError as e:
            logger.error(f"Validation error in meter reading: {str(e)}")
            result['error'] = f"Validation error: {str(e)}"
        except DatabaseError as e:
            logger.error(f"Database error in meter reading: {str(e)}")
            result['error'] = f"Database error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in meter reading: {str(e)}", exc_info=True)
            result['error'] = f"Processing error: {str(e)}"

        return result

    def validate_reading(
        self,
        reading_id: int,
        validator: People,
        approved: bool,
        notes: str = ""
    ) -> bool:
        """
        Validate a pending meter reading.

        Args:
            reading_id: ID of the meter reading
            validator: User performing validation
            approved: Whether reading is approved
            notes: Validation notes

        Returns:
            Success status
        """
        try:
            with transaction.atomic():
                reading = MeterReading.objects.select_for_update().get(
                    id=reading_id
                )

                if approved:
                    reading.status = MeterReading.ReadingStatus.VALIDATED
                else:
                    reading.status = MeterReading.ReadingStatus.REJECTED

                reading.validated_by = validator
                reading.validated_at = timezone.now()
                reading.notes = f"{reading.notes}\n\nValidation: {notes}".strip()

                reading.save()

                logger.info(
                    f"Reading {reading_id} {'approved' if approved else 'rejected'} "
                    f"by {validator.peoplename}"
                )

                return True

        except MeterReading.DoesNotExist:
            logger.error(f"Reading {reading_id} not found for validation")
            return False
        except Exception as e:
            logger.error(f"Error validating reading {reading_id}: {str(e)}")
            return False

    def get_asset_readings(
        self,
        asset_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[MeterReading]:
        """Get readings for an asset within date range."""
        try:
            queryset = MeterReading.objects.filter(asset_id=asset_id)

            if start_date:
                queryset = queryset.filter(reading_timestamp__gte=start_date)
            if end_date:
                queryset = queryset.filter(reading_timestamp__lte=end_date)

            return list(
                queryset
                .select_related('asset', 'captured_by', 'validated_by')
                .order_by('-reading_timestamp')[:limit]
            )

        except Exception as e:
            logger.error(f"Error fetching readings for asset {asset_id}: {str(e)}")
            return []

    def get_consumption_analytics(
        self,
        asset_id: int,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Generate consumption analytics for an asset."""
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=period_days)

            readings = MeterReading.objects.filter(
                asset_id=asset_id,
                status=MeterReading.ReadingStatus.VALIDATED,
                reading_timestamp__range=[start_date, end_date]
            ).order_by('reading_timestamp')

            if len(readings) < 2:
                return {'error': 'Insufficient data for analytics'}

            first_reading = readings[0]
            last_reading = readings[len(readings) - 1]

            total_consumption = last_reading.reading_value - first_reading.reading_value
            time_span = (last_reading.reading_timestamp - first_reading.reading_timestamp).days

            daily_average = float(total_consumption) / max(time_span, 1) if time_span > 0 else 0

            # Calculate trend
            trend_data = []
            for reading in readings:
                trend_data.append({
                    'timestamp': reading.reading_timestamp.isoformat(),
                    'value': float(reading.reading_value),
                    'consumption': float(reading.consumption_since_last or 0)
                })

            return {
                'period_days': period_days,
                'total_consumption': float(total_consumption),
                'daily_average': daily_average,
                'unit': last_reading.unit,
                'reading_count': len(readings),
                'trend_data': trend_data,
                'estimated_monthly': daily_average * 30,
            }

        except Exception as e:
            logger.error(f"Error generating analytics for asset {asset_id}: {str(e)}")
            return {'error': str(e)}

    def detect_anomalies_batch(self, asset_ids: List[int] = None) -> int:
        """Run anomaly detection on recent readings."""
        try:
            # Get recent unprocessed readings
            cutoff_date = timezone.now() - timedelta(hours=24)
            queryset = MeterReading.objects.filter(
                created_at__gte=cutoff_date,
                status=MeterReading.ReadingStatus.PENDING
            )

            if asset_ids:
                queryset = queryset.filter(asset_id__in=asset_ids)

            processed_count = 0
            for reading in queryset:
                try:
                    # Re-run anomaly detection
                    reading._detect_anomalies()
                    reading.save()

                    if reading.is_anomaly:
                        self._create_anomaly_alert(reading)

                    processed_count += 1

                except Exception as e:
                    logger.warning(f"Error processing reading {reading.id}: {str(e)}")
                    continue

            logger.info(f"Processed {processed_count} readings for anomaly detection")
            return processed_count

        except Exception as e:
            logger.error(f"Error in batch anomaly detection: {str(e)}")
            return 0

    def _get_and_validate_asset(self, asset_id: int) -> Optional[Asset]:
        """Get asset and validate it's a meter."""
        try:
            asset = Asset.objects.get(id=asset_id, enable=True)

            # Check if asset is configured as a meter
            asset_data = asset.json_data or {}
            if not asset_data.get('ismeter', False):
                logger.warning(f"Asset {asset_id} is not configured as a meter")
                return None

            return asset

        except Asset.DoesNotExist:
            logger.error(f"Asset {asset_id} not found")
            return None

    def _determine_meter_type(self, asset: Asset) -> str:
        """Determine meter type from asset data."""
        asset_data = asset.json_data or {}
        meter_info = asset_data.get('meter', '').lower()

        # Map asset meter info to our meter types
        type_mapping = {
            'electric': 'electricity',
            'electricity': 'electricity',
            'water': 'water',
            'gas': 'gas',
            'diesel': 'diesel',
            'fuel': 'diesel',
            'temperature': 'temperature',
            'temp': 'temperature',
            'pressure': 'pressure',
            'fire': 'fire_pressure',
            'generator': 'generator_hours',
            'gen': 'generator_hours'
        }

        for key, meter_type in type_mapping.items():
            if key in meter_info:
                return meter_type

        return 'other'

    def _get_expected_unit(self, meter_type: str) -> str:
        """Get expected unit for meter type."""
        unit_mapping = {
            'electricity': 'kWh',
            'water': 'L',
            'gas': 'm³',
            'diesel': 'L',
            'temperature': '°C',
            'pressure': 'psi',
            'fire_pressure': 'psi',
            'generator_hours': 'hrs'
        }
        return unit_mapping.get(meter_type, '')

    def _calculate_image_hash(self, photo: UploadedFile) -> str:
        """Calculate SHA256 hash of the uploaded image."""
        try:
            photo.seek(0)  # Reset file pointer
            content = photo.read()
            photo.seek(0)  # Reset again for later use
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.warning(f"Error calculating image hash: {str(e)}")
            return hashlib.sha256(str(datetime.now()).encode()).hexdigest()

    def _is_duplicate_image(self, asset: Asset, image_hash: str) -> bool:
        """Check if this image has already been processed."""
        return MeterReading.objects.filter(
            asset=asset,
            image_hash=image_hash
        ).exists()

    def _create_meter_reading(
        self,
        asset: Asset,
        ocr_result: Dict[str, Any],
        meter_type: str,
        user: People,
        image_hash: str,
        notes: str
    ) -> MeterReading:
        """Create a MeterReading instance from OCR results."""
        # Map meter type to enum value
        meter_type_mapping = {
            'electricity': MeterReading.MeterType.ELECTRICITY,
            'water': MeterReading.MeterType.WATER,
            'gas': MeterReading.MeterType.GAS,
            'diesel': MeterReading.MeterType.DIESEL,
            'temperature': MeterReading.MeterType.TEMPERATURE,
            'pressure': MeterReading.MeterType.PRESSURE,
            'fire_pressure': MeterReading.MeterType.FIRE_PRESSURE,
            'generator_hours': MeterReading.MeterType.GENERATOR_HOURS,
        }

        meter_reading = MeterReading(
            asset=asset,
            meter_type=meter_type_mapping.get(meter_type, MeterReading.MeterType.OTHER),
            reading_value=ocr_result['value'],
            unit=ocr_result['unit'] or self._get_expected_unit(meter_type),
            reading_timestamp=timezone.now(),
            capture_method=MeterReading.CaptureMethod.AI_CAMERA,
            confidence_score=ocr_result['confidence'],
            image_hash=image_hash,
            raw_ocr_text=ocr_result['raw_text'],
            processing_metadata={
                'ocr_result': ocr_result,
                'processing_version': '1.0'
            },
            captured_by=user,
            notes=notes
        )

        # Set initial status based on validation
        validation_result = ocr_result.get('validation', {})
        if validation_result.get('passed', False):
            meter_reading.status = MeterReading.ReadingStatus.VALIDATED
        else:
            meter_reading.status = MeterReading.ReadingStatus.FLAGGED
            meter_reading.validation_flags = validation_result.get('issues', [])

        meter_reading.full_clean()
        meter_reading.save()

        return meter_reading

    def _save_meter_image(self, photo: UploadedFile, reading: MeterReading) -> str:
        """Save the meter image to storage."""
        try:
            # Create directory structure
            upload_dir = os.path.join(
                settings.MEDIA_ROOT,
                'meter_readings',
                str(reading.asset.business_unit_id),
                str(reading.asset.id),
                str(reading.reading_timestamp.year),
                str(reading.reading_timestamp.month)
            )
            os.makedirs(upload_dir, exist_ok=True)

            # Generate filename
            timestamp = reading.reading_timestamp.strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{reading.id}.jpg"
            file_path = os.path.join(upload_dir, filename)

            # Save file
            with open(file_path, 'wb') as f:
                for chunk in photo.chunks():
                    f.write(chunk)

            # Return relative path
            return os.path.relpath(file_path, settings.MEDIA_ROOT)

        except Exception as e:
            logger.error(f"Error saving meter image: {str(e)}")
            return ""

    def _create_anomaly_alert(self, reading: MeterReading) -> None:
        """Create an alert for anomalous readings."""
        try:
            MeterReadingAlert.objects.create(
                reading=reading,
                asset=reading.asset,
                alert_type=MeterReadingAlert.AlertType.ANOMALY,
                severity=MeterReadingAlert.Severity.HIGH,
                message=f"Anomalous reading detected: {reading.reading_value} {reading.unit}",
                actual_value=reading.reading_value
            )
        except Exception as e:
            logger.error(f"Error creating anomaly alert: {str(e)}")


# Factory function
def get_meter_reading_service() -> MeterReadingService:
    """Factory function to get meter reading service instance."""
    return MeterReadingService()