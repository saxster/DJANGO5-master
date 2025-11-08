"""
Bandwidth Optimization Service for Mobile Sync

Implements compression, delta sync, and adaptive batch sizing
to minimize network bandwidth usage.

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
"""

import logging
import gzip
import json
from typing import Dict, Any, List, Literal, Optional
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

NetworkQuality = Literal['excellent', 'good', 'fair', 'poor']


class BandwidthOptimizationService:
    """
    Optimizes sync bandwidth through compression and smart batching.

    Features:
    - Adaptive gzip compression based on payload size
    - Delta sync (only changed fields)
    - Network-aware batch sizing
    - Priority-based item ordering
    """

    COMPRESSION_THRESHOLD_BYTES = 1024
    MIN_COMPRESSION_RATIO = 0.8

    BATCH_SIZES = {
        'excellent': 100,
        'good': 50,
        'fair': 25,
        'poor': 10,
    }

    PRIORITY_WEIGHTS = {
        'high': 3,
        'medium': 2,
        'low': 1,
    }

    def compress_payload(
        self,
        data: Dict[str, Any],
        compression_level: Literal['adaptive', 'always', 'never'] = 'adaptive'
    ) -> Dict[str, Any]:
        """
        Compress JSON payload using gzip.

        Args:
            data: Payload to compress
            compression_level: 'adaptive', 'always', or 'never'

        Returns:
            {
                compressed: bool,
                data: compressed_bytes or original_data,
                original_size: int,
                compressed_size: int,
                compression_ratio: float
            }
        """
        try:
            json_str = json.dumps(data)
            original_size = len(json_str.encode('utf-8'))

            if compression_level == 'never':
                return self._no_compression_result(data, original_size)

            if compression_level == 'adaptive' and original_size < self.COMPRESSION_THRESHOLD_BYTES:
                return self._no_compression_result(data, original_size)

            compressed_bytes = gzip.compress(json_str.encode('utf-8'), compresslevel=6)
            compressed_size = len(compressed_bytes)
            compression_ratio = compressed_size / original_size

            if compression_ratio >= self.MIN_COMPRESSION_RATIO:
                logger.debug(f"Compression not beneficial: {compression_ratio:.2%}")
                return self._no_compression_result(data, original_size)

            logger.info(
                f"Payload compressed: {original_size} → {compressed_size} bytes "
                f"({compression_ratio:.2%})"
            )

            return {
                'compressed': True,
                'data': compressed_bytes,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio
            }

        except (TypeError, ValueError) as e:
            logger.error(f"Compression failed: {e}")
            raise ValidationError(f"Failed to compress payload: {e}")

    def _no_compression_result(self, data: Dict[str, Any], size: int) -> Dict[str, Any]:
        """Return uncompressed payload result."""
        return {
            'compressed': False,
            'data': data,
            'original_size': size,
            'compressed_size': size,
            'compression_ratio': 1.0
        }

    def calculate_delta(
        self,
        server_version: Dict[str, Any],
        client_version: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate delta between server and client versions.

        Returns only changed fields to minimize payload size.

        Args:
            server_version: Current server state
            client_version: Client's local state

        Returns:
            {
                mobile_id: str,
                version: int,
                delta: {field: new_value, ...},
                fields_changed: int
            }
        """
        try:
            delta = {}

            for key, client_value in client_version.items():
                if key in ['mobile_id', 'version']:
                    continue

                server_value = server_version.get(key)

                if server_value != client_value:
                    delta[key] = client_value

            return {
                'mobile_id': client_version.get('mobile_id'),
                'version': client_version.get('version'),
                'delta': delta,
                'fields_changed': len(delta)
            }

        except (KeyError, TypeError) as e:
            logger.error(f"Delta calculation failed: {e}")
            raise ValidationError(f"Invalid version data: {e}")

    def adaptive_batch_sizing(
        self,
        items: List[Dict[str, Any]],
        network_quality: NetworkQuality
    ) -> List[List[Dict[str, Any]]]:
        """
        Split items into batches based on network quality.

        Args:
            items: List of items to batch
            network_quality: 'excellent', 'good', 'fair', 'poor'

        Returns:
            List of batches
        """
        try:
            batch_size = self.BATCH_SIZES.get(network_quality, 25)

            batches = [
                items[i:i + batch_size]
                for i in range(0, len(items), batch_size)
            ]

            logger.info(
                f"Created {len(batches)} batches for {len(items)} items "
                f"(network: {network_quality}, batch_size: {batch_size})"
            )

            return batches

        except (TypeError, ValueError) as e:
            logger.error(f"Batch sizing failed: {e}")
            raise ValidationError(f"Invalid items for batching: {e}")

    def prioritize_items(
        self,
        items: List[Dict[str, Any]],
        priority_field: str = 'priority'
    ) -> List[Dict[str, Any]]:
        """
        Sort items by priority (high → medium → low).

        Args:
            items: Items to prioritize
            priority_field: Field name containing priority

        Returns:
            Sorted items list
        """
        try:
            def get_priority_weight(item: Dict[str, Any]) -> int:
                priority = item.get(priority_field, 'medium')
                return self.PRIORITY_WEIGHTS.get(priority, 2)

            sorted_items = sorted(items, key=get_priority_weight, reverse=True)

            logger.debug(f"Prioritized {len(sorted_items)} items")

            return sorted_items

        except (TypeError, KeyError) as e:
            logger.error(f"Prioritization failed: {e}")
            raise ValidationError(f"Invalid items for prioritization: {e}")