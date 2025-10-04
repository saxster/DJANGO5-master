"""Idempotency Service - batch and item-level deduplication for mobile sync."""

import hashlib
import json
import logging
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError
from django.utils import timezone
from typing import Dict, Any, Optional

from apps.core.models.sync_idempotency import SyncIdempotencyRecord

logger = logging.getLogger(__name__)


class IdempotencyService:
    """Manages idempotency keys for sync operations with 24-hour TTL."""

    @staticmethod
    def generate_idempotency_key(operation_type: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        """Generate SHA256 idempotency key from operation data."""
        payload = {
            'operation': operation_type,
            'data': data,
            'context': context or {}
        }

        # Create deterministic JSON string
        payload_str = json.dumps(payload, sort_keys=True, default=str)

        # Generate SHA256 hash
        hash_obj = hashlib.sha256(payload_str.encode('utf-8'))
        return hash_obj.hexdigest()[:64]

    @staticmethod
    def check_duplicate(idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Check if key was processed before. Returns cached response or None."""
        try:
            record = SyncIdempotencyRecord.objects.filter(
                idempotency_key=idempotency_key,
                expires_at__gt=timezone.now()
            ).first()

            if record:
                # Update hit tracking
                record.hit_count += 1
                record.last_hit_at = timezone.now()
                record.save(update_fields=['hit_count', 'last_hit_at'])

                logger.info(
                    f"Duplicate request detected: {idempotency_key[:16]}... (hit #{record.hit_count})"
                )
                return record.response_data

            return None

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error checking idempotency: {e}", exc_info=True)
            return None

    @staticmethod
    def store_response(idempotency_key: str, request_hash: str, response_data: Dict[str, Any],
                      user_id: Optional[str] = None, device_id: Optional[str] = None,
                      endpoint: str = '', scope: str = 'batch') -> bool:
        """Store response for future idempotency checks."""
        try:
            SyncIdempotencyRecord.objects.create(
                idempotency_key=idempotency_key,
                scope=scope,
                request_hash=request_hash,
                response_data=response_data,
                user_id=user_id,
                device_id=device_id,
                endpoint=endpoint
            )

            logger.debug(f"Stored idempotency record: {idempotency_key[:16]}...")
            return True

        except IntegrityError:
            # Duplicate key - another concurrent request beat us to it
            logger.debug(f"Idempotency record already exists: {idempotency_key[:16]}...")
            return False
        except (DatabaseError, ValidationError) as e:
            logger.error(f"Failed to store idempotency record: {e}", exc_info=True)
            return False

    @staticmethod
    def cleanup_expired_records() -> int:
        """Remove expired idempotency records."""
        try:
            return SyncIdempotencyRecord.cleanup_expired()
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Failed to cleanup expired records: {e}", exc_info=True)
            return 0