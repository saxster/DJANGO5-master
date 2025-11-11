"""Mobile Sync Engine Service - processes WebSocket sync batches and persists to DB."""

import logging
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.models import (
    BehavioralSyncEvent,
    DeviceMetricSnapshot,
    SessionSyncEvent,
    SyncDeviceHealth,
)
from apps.core.utils_new.db_utils import get_current_db_name
from apps.streamlab.services.pii_redactor import pii_redactor
from apps.voice_recognition.models import VoiceVerificationLog

logger = logging.getLogger(__name__)


class SyncEngineService:
    """Core sync engine for mobile client data batches."""

    def sync_voice_data(self, user_id: str, payload: Dict[str, Any], device_id: str) -> Dict[str, Any]:
        """Sync voice verification data from mobile client."""
        voice_data = self._ensure_list(payload.get('voice_data', []), 'voice_data')
        synced = 0
        failed = 0
        errors: List[Dict[str, Any]] = []
        db_alias = get_current_db_name()
        user_pk = self._normalize_user_id(user_id)

        try:
            with transaction.atomic(using=db_alias):
                for item in voice_data:
                    try:
                        self._process_voice_item(db_alias, user_pk, item, device_id)
                        synced += 1
                    except (ValidationError, IntegrityError) as exc:
                        failed += 1
                        errors.append({'item_id': item.get('id'), 'error': str(exc)})
                        logger.warning(
                            "Voice data sync failed for item %s: %s", item.get('id'), exc
                        )

                self._update_device_health(db_alias, user_pk, device_id, synced, failed)

        except DatabaseError as exc:
            logger.error("Database error during voice sync: %s", exc, exc_info=True)
            raise

        logger.info("Voice data sync completed: %s synced, %s failed", synced, failed)
        return {'synced_items': synced, 'failed_items': failed, 'errors': errors}

    def sync_behavioral_data(self, user_id: str, payload: Dict[str, Any], device_id: str) -> Dict[str, Any]:
        """Sync behavioral analytics data from mobile client."""
        behavioral_data = self._ensure_list(payload.get('behavioral_data', []), 'behavioral_data')
        synced = 0
        failed = 0
        errors: List[Dict[str, Any]] = []
        db_alias = get_current_db_name()
        user_pk = self._normalize_user_id(user_id)

        try:
            with transaction.atomic(using=db_alias):
                for item in behavioral_data:
                    try:
                        sanitized = self._sanitize_payload(item, 'behavioral_data')
                        event_timestamp = self._require_timestamp(
                            sanitized.get('timestamp'), field_name='timestamp'
                        )

                        BehavioralSyncEvent.objects.using(db_alias).create(
                            user_id=user_pk,
                            device_id=device_id,
                            client_event_id=sanitized.get('event_id') or sanitized.get('id'),
                            event_type=str(sanitized.get('event_type') or 'unknown'),
                            timestamp=event_timestamp,
                            session_duration_ms=self._safe_positive_int(
                                sanitized.get('session_duration_ms')
                            ),
                            interaction_count=self._safe_non_negative_int(
                                sanitized.get('interaction_count'), default=0
                            ),
                            performance_score=self._safe_float(
                                sanitized.get('performance_score')
                            ),
                            metadata=sanitized,
                            schema_hash=self._calculate_schema_hash(sanitized),
                        )
                        synced += 1
                    except (ValidationError, IntegrityError, ValueError, TypeError) as exc:
                        failed += 1
                        errors.append({
                            'item_id': item.get('id') or item.get('event_id'),
                            'error': str(exc),
                        })
                        logger.warning("Behavioral data sync failed: %s", exc)

                self._update_device_health(db_alias, user_pk, device_id, synced, failed)

        except DatabaseError as exc:
            logger.error("Behavioral sync database error: %s", exc, exc_info=True)
            raise

        logger.info("Behavioral data sync completed: %s synced, %s failed", synced, failed)
        return {'synced_items': synced, 'failed_items': failed, 'errors': errors}

    def sync_session_data(self, user_id: str, payload: Dict[str, Any], device_id: str) -> Dict[str, Any]:
        """Sync session data from mobile client."""
        sessions = self._ensure_list(payload.get('sessions', []), 'sessions')
        synced = 0
        failed = 0
        errors: List[Dict[str, Any]] = []
        db_alias = get_current_db_name()
        user_pk = self._normalize_user_id(user_id)

        try:
            with transaction.atomic(using=db_alias):
                for item in sessions:
                    try:
                        sanitized = self._sanitize_payload(item, 'session_data')
                        session_id = sanitized.get('session_id') or sanitized.get('id')
                        session_start = self._coerce_optional_timestamp(
                            sanitized.get('session_start')
                        )
                        session_end = self._coerce_optional_timestamp(
                            sanitized.get('session_end')
                        )

                        defaults = {
                            'device_id': device_id,
                            'session_start': session_start,
                            'session_end': session_end,
                            'duration_ms': self._safe_positive_int(sanitized.get('duration_ms')),
                            'event_count': self._safe_non_negative_int(
                                sanitized.get('event_count'), default=0
                            ),
                            'status': sanitized.get('status') or '',
                            'metadata': sanitized,
                            'schema_hash': self._calculate_schema_hash(sanitized),
                        }

                        manager = SessionSyncEvent.objects.using(db_alias)
                        if session_id:
                            manager.update_or_create(
                                user_id=user_pk,
                                session_id=session_id,
                                defaults=defaults,
                            )
                        else:
                            manager.create(user_id=user_pk, session_id=None, **defaults)

                        synced += 1
                    except (ValidationError, IntegrityError, ValueError, TypeError) as exc:
                        failed += 1
                        errors.append({
                            'item_id': item.get('session_id') or item.get('id'),
                            'error': str(exc),
                        })
                        logger.warning("Session data sync failed: %s", exc)

                self._update_device_health(db_alias, user_pk, device_id, synced, failed)

        except DatabaseError as exc:
            logger.error("Session sync database error: %s", exc, exc_info=True)
            raise

        logger.info("Session data sync completed: %s synced, %s failed", synced, failed)
        return {'synced_items': synced, 'failed_items': failed, 'errors': errors}

    def sync_metrics_data(self, user_id: str, payload: Dict[str, Any], device_id: str) -> Dict[str, Any]:
        """Sync metrics data from mobile client."""
        metrics = self._ensure_list(payload.get('metrics', []), 'metrics')
        synced = 0
        failed = 0
        errors: List[Dict[str, Any]] = []
        db_alias = get_current_db_name()
        user_pk = self._normalize_user_id(user_id)

        try:
            with transaction.atomic(using=db_alias):
                for item in metrics:
                    try:
                        sanitized = self._sanitize_payload(item, 'metrics')
                        metric_name = sanitized.get('metric_name')
                        if not metric_name:
                            raise ValidationError("metric_name is required")

                        recorded_at = self._coerce_optional_timestamp(
                            sanitized.get('timestamp'), default=timezone.now()
                        )

                        DeviceMetricSnapshot.objects.using(db_alias).create(
                            user_id=user_pk,
                            device_id=device_id,
                            metric_name=str(metric_name),
                            metric_value=self._safe_float(
                                sanitized.get('value'), allow_none=False
                            ),
                            unit=sanitized.get('unit', ''),
                            aggregation_type=sanitized.get('aggregation_type', ''),
                            recorded_at=recorded_at,
                            metadata=sanitized,
                            schema_hash=self._calculate_schema_hash(sanitized),
                        )
                        synced += 1
                    except (ValidationError, IntegrityError, ValueError, TypeError) as exc:
                        failed += 1
                        errors.append({
                            'item_id': metric_name or item.get('id'),
                            'error': str(exc),
                        })
                        logger.warning("Metrics data sync failed: %s", exc)

                self._update_device_health(db_alias, user_pk, device_id, synced, failed)

        except DatabaseError as exc:
            logger.error("Metrics sync database error: %s", exc, exc_info=True)
            raise

        logger.info("Metrics data sync completed: %s synced, %s failed", synced, failed)
        return {'synced_items': synced, 'failed_items': failed, 'errors': errors}

    def _process_voice_item(
        self,
        db_alias: str,
        user_id: int,
        item: Dict[str, Any],
        device_id: str,
    ):
        """Process and persist single voice verification item."""
        # Validate required fields
        required_fields = ['verification_id', 'timestamp', 'verified']
        for field in required_fields:
            if field not in item:
                raise ValidationError(f"Missing required field: {field}")

        # Check for duplicate
        if VoiceVerificationLog.objects.using(db_alias).filter(
            verification_id=item['verification_id']
        ).exists():
            logger.debug(f"Duplicate voice verification {item['verification_id']} - skipping")
            return

        # Create voice verification log
        VoiceVerificationLog.objects.using(db_alias).create(
            verification_id=item['verification_id'],
            user_id=user_id,
            device_id=device_id,
            verified=item['verified'],
            confidence_score=item.get('confidence_score'),
            quality_score=item.get('quality_score'),
            processing_time_ms=item.get('processing_time_ms'),
            created_at=timezone.now()
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_list(self, value: Any, field_name: str) -> List[Any]:
        if isinstance(value, list):
            return value
        raise ValidationError(f"{field_name} must be a list")

    def _normalize_user_id(self, user_id: Any) -> int:
        try:
            return int(user_id)
        except (TypeError, ValueError):
            raise ValidationError("Invalid user identifier for sync request")

    def _sanitize_payload(self, payload: Any, data_type: str) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError(f"{data_type} entries must be objects")
        return pii_redactor.redact(payload, data_type)

    def _require_timestamp(self, raw: Any, field_name: str) -> timezone.datetime:
        timestamp = self._coerce_optional_timestamp(raw)
        if timestamp is None:
            raise ValidationError(f"{field_name} is required")
        return timestamp

    def _coerce_optional_timestamp(
        self,
        raw: Any,
        default: Optional[timezone.datetime] = None,
    ) -> Optional[timezone.datetime]:
        if raw is None:
            return default
        if isinstance(raw, timezone.datetime):
            return raw if timezone.is_aware(raw) else timezone.make_aware(raw)
        parsed = parse_datetime(str(raw))
        if parsed is None:
            raise ValidationError(f"Invalid timestamp value: {raw}")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed

    def _safe_non_negative_int(self, value: Any, default: int = 0) -> int:
        if value is None:
            return default
        coerced = int(value)
        if coerced < 0:
            raise ValidationError("Value must be non-negative")
        return coerced

    def _safe_positive_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        coerced = int(value)
        if coerced < 0:
            raise ValidationError("Value must be non-negative")
        return coerced

    def _safe_float(self, value: Any, allow_none: bool = True) -> Optional[float]:
        if value is None:
            if allow_none:
                return None
            raise ValidationError("Value is required")
        return float(value)

    def _calculate_schema_hash(self, payload: Dict[str, Any]) -> str:
        try:
            return pii_redactor.calculate_schema_hash(payload)
        except Exception:  # pragma: no cover - defensive
            return ''

    def _update_device_health(
        self,
        db_alias: str,
        user_id: int,
        device_id: str,
        synced: int,
        failed: int,
    ) -> None:
        if synced == 0 and failed == 0:
            return

        now = timezone.now()
        manager = SyncDeviceHealth.objects.using(db_alias)
        health, created = manager.get_or_create(
            device_id=device_id,
            user_id=user_id,
            defaults={
                'last_sync_at': now,
                'total_syncs': synced,
                'failed_syncs_count': failed,
                'avg_sync_duration_ms': 0.0,
                'conflicts_encountered': 0,
            },
        )

        if not created:
            health.total_syncs += synced
            health.failed_syncs_count += failed
            health.last_sync_at = now
            health.save(
                using=db_alias,
                update_fields=['total_syncs', 'failed_syncs_count', 'last_sync_at'],
            )

        health.update_health_score()


# Singleton instance for import by mobile_consumers.py
sync_engine = SyncEngineService()
