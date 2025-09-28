"""
Mobile Sync Engine Service

Processes WebSocket sync batches and persists data to database.
Handles voice, behavioral, session, and metrics data from mobile clients.

Compliance:
- Rule #7: Service class <150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management for multi-step operations
"""

import logging
from django.db import transaction, DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils import timezone
from typing import Dict, Any, List

from apps.voice_recognition.models import VoiceVerificationLog
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class SyncEngineService:
    """
    Core sync engine for processing mobile client data batches.

    Returns per-batch item results for client reconciliation:
    {synced_items: int, failed_items: int, errors: []}
    """

    def sync_voice_data(self, user_id: str, payload: Dict[str, Any], device_id: str) -> Dict[str, Any]:
        """
        Sync voice verification data from mobile client.

        Args:
            user_id: User ID performing sync
            payload: {'voice_data': [...]} with verification logs
            device_id: Client device identifier

        Returns:
            dict: {synced_items, failed_items, errors[]}
        """
        try:
            voice_data = payload.get('voice_data', [])
            synced = 0
            failed = 0
            errors = []

            with transaction.atomic(using=get_current_db_name()):
                for item in voice_data:
                    try:
                        self._process_voice_item(user_id, item, device_id)
                        synced += 1
                    except (ValidationError, IntegrityError) as e:
                        failed += 1
                        errors.append({
                            'item_id': item.get('id'),
                            'error': str(e)
                        })
                        logger.warning(f"Voice data sync failed for item {item.get('id')}: {e}")

            logger.info(f"Voice data sync completed: {synced} synced, {failed} failed")
            return {'synced_items': synced, 'failed_items': failed, 'errors': errors}

        except DatabaseError as e:
            logger.error(f"Database error during voice sync: {e}", exc_info=True)
            return {'synced_items': 0, 'failed_items': len(voice_data), 'errors': [{'error': 'Database unavailable'}]}

    def sync_behavioral_data(self, user_id: str, payload: Dict[str, Any], device_id: str) -> Dict[str, Any]:
        """Sync behavioral analytics data from mobile client."""
        try:
            behavioral_data = payload.get('behavioral_data', [])
            synced = 0
            failed = 0
            errors = []

            # TODO: Implement behavioral data model and persistence
            # For now, log and return placeholder
            logger.info(f"Behavioral data sync placeholder: {len(behavioral_data)} items from device {device_id}")

            return {'synced_items': synced, 'failed_items': 0, 'errors': errors}

        except (DatabaseError, IntegrityError, ValidationError) as e:
            logger.error(f"Behavioral sync error: {e}", exc_info=True)
            return {'synced_items': 0, 'failed_items': len(behavioral_data), 'errors': [{'error': str(e)}]}

    def sync_session_data(self, user_id: str, payload: Dict[str, Any], device_id: str) -> Dict[str, Any]:
        """Sync session data from mobile client."""
        try:
            sessions = payload.get('sessions', [])
            synced = 0
            failed = 0
            errors = []

            # TODO: Implement session data model and persistence
            # For now, log and return placeholder
            logger.info(f"Session data sync placeholder: {len(sessions)} sessions from device {device_id}")

            return {'synced_items': synced, 'failed_items': 0, 'errors': errors}

        except (DatabaseError, IntegrityError, ValidationError) as e:
            logger.error(f"Session sync error: {e}", exc_info=True)
            return {'synced_items': 0, 'failed_items': len(sessions), 'errors': [{'error': str(e)}]}

    def sync_metrics_data(self, user_id: str, payload: Dict[str, Any], device_id: str) -> Dict[str, Any]:
        """Sync metrics data from mobile client."""
        try:
            metrics = payload.get('metrics', [])
            synced = 0
            failed = 0
            errors = []

            # TODO: Implement metrics data model and persistence
            # For now, log and return placeholder
            logger.info(f"Metrics data sync placeholder: {len(metrics)} metrics from device {device_id}")

            return {'synced_items': synced, 'failed_items': 0, 'errors': errors}

        except (DatabaseError, IntegrityError, ValidationError) as e:
            logger.error(f"Metrics sync error: {e}", exc_info=True)
            return {'synced_items': 0, 'failed_items': len(metrics), 'errors': [{'error': str(e)}]}

    def _process_voice_item(self, user_id: str, item: Dict[str, Any], device_id: str):
        """
        Process and persist single voice verification item.

        Raises:
            ValidationError: If item data is invalid
            IntegrityError: If duplicate or constraint violation
        """
        # Validate required fields
        required_fields = ['verification_id', 'timestamp', 'verified']
        for field in required_fields:
            if field not in item:
                raise ValidationError(f"Missing required field: {field}")

        # Check for duplicate
        if VoiceVerificationLog.objects.filter(verification_id=item['verification_id']).exists():
            logger.debug(f"Duplicate voice verification {item['verification_id']} - skipping")
            return

        # Create voice verification log
        VoiceVerificationLog.objects.create(
            verification_id=item['verification_id'],
            user_id=user_id,
            device_id=device_id,
            verified=item['verified'],
            confidence_score=item.get('confidence_score'),
            quality_score=item.get('quality_score'),
            processing_time_ms=item.get('processing_time_ms'),
            created_at=timezone.now()
        )


# Singleton instance for import by mobile_consumers.py
sync_engine = SyncEngineService()