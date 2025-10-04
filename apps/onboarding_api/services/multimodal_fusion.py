"""
Multimodal Fusion Service - Correlate voice + photo + GPS data.

This service combines multiple data sources (voice transcripts, images, GPS
coordinates) to create holistic observations with cross-validation and
inconsistency detection.

Features:
- Voice + photo + GPS correlation
- Cross-modal consistency checking
- Coverage map tracking
- Confidence aggregation
- Gap detection

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization with prefetch/select_related
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Count, Q

from apps.onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    Observation,
    SitePhoto
)

logger = logging.getLogger(__name__)


class MultimodalFusionService:
    """
    Fuses multiple data modalities into unified observations.

    Correlates voice, images, and GPS to validate consistency and
    track site coverage progress.
    """

    # Distance threshold for GPS correlation (meters)
    GPS_CORRELATION_THRESHOLD = 50.0

    # Confidence thresholds
    MIN_VOICE_CONFIDENCE = 0.7
    MIN_VISION_CONFIDENCE = 0.75
    CROSS_MODAL_BOOST = 0.1  # Boost when multiple modalities agree

    def correlate_observation(
        self,
        voice_data: Dict[str, Any],
        photo_data: Dict[str, Any] = None,
        gps_data: Dict[str, float] = None,
        zone_hint: str = None,
        site: OnboardingSite = None
    ) -> Dict[str, Any]:
        """
        Correlate multimodal inputs into unified observation.

        Args:
            voice_data: {transcript_en, transcript_original, confidence, ...}
            photo_data: {objects, labels, security_equipment, ...}
            gps_data: {latitude, longitude}
            zone_hint: Operator's zone suggestion
            site: OnboardingSite instance

        Returns:
            {
                'unified_observation': Dict,
                'confidence_score': Decimal,
                'inconsistencies': List[str],
                'identified_zone': OnboardingZone | None,
                'cross_modal_validation': Dict
            }
        """
        result = {
            'unified_observation': {},
            'confidence_score': Decimal('0.0'),
            'inconsistencies': [],
            'identified_zone': None,
            'cross_modal_validation': {}
        }

        try:
            # Build unified observation
            unified = self._build_unified_observation(
                voice_data,
                photo_data,
                gps_data
            )
            result['unified_observation'] = unified

            # Identify zone from multiple signals
            if site:
                identified_zone = self._identify_zone(
                    site=site,
                    gps_data=gps_data,
                    voice_data=voice_data,
                    photo_data=photo_data,
                    zone_hint=zone_hint
                )
                result['identified_zone'] = identified_zone

            # Cross-validate modalities
            validation = self._cross_validate_modalities(
                voice_data,
                photo_data,
                gps_data
            )
            result['cross_modal_validation'] = validation
            result['inconsistencies'] = validation.get('inconsistencies', [])

            # Calculate aggregated confidence
            result['confidence_score'] = self._calculate_aggregated_confidence(
                voice_data,
                photo_data,
                validation
            )

            logger.info(
                f"Multimodal fusion complete: confidence={result['confidence_score']}, "
                f"inconsistencies={len(result['inconsistencies'])}"
            )

        except (ValueError, TypeError) as e:
            logger.error(f"Data error in multimodal fusion: {str(e)}")
            result['inconsistencies'].append(f"Processing error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in multimodal fusion: {str(e)}", exc_info=True)
            result['inconsistencies'].append(f"Fusion failed: {str(e)}")

        return result

    def track_coverage(
        self,
        site: OnboardingSite
    ) -> Dict[str, Any]:
        """
        Track site audit coverage progress.

        Returns:
            {
                'total_zones': int,
                'zones_visited': int,
                'coverage_percentage': Decimal,
                'critical_gaps': List[str],
                'zones_needing_attention': List[Dict]
            }
        """
        try:
            # Get all zones with observation counts
            zones = site.zones.annotate(
                observation_count=Count('observations')
            ).select_related('site')

            total_zones = zones.count()
            zones_visited = zones.filter(observation_count__gt=0).count()

            coverage_percentage = (
                Decimal(zones_visited) / Decimal(total_zones) * Decimal('100')
                if total_zones > 0
                else Decimal('0')
            )

            # Identify critical gaps
            critical_gaps = []
            critical_zones = zones.filter(
                importance_level__in=['critical', 'high']
            )

            for zone in critical_zones:
                if zone.observation_count == 0:
                    critical_gaps.append(
                        f"{zone.zone_name} ({zone.zone_type}) - "
                        f"{zone.importance_level} importance"
                    )

            # Zones needing more attention
            zones_needing_attention = []
            for zone in zones:
                if zone.importance_level == 'critical' and zone.observation_count < 2:
                    zones_needing_attention.append({
                        'zone_id': str(zone.zone_id),
                        'zone_name': zone.zone_name,
                        'zone_type': zone.zone_type,
                        'importance': zone.importance_level,
                        'current_observations': zone.observation_count,
                        'recommended_observations': 3
                    })

            logger.info(
                f"Coverage tracking: {zones_visited}/{total_zones} zones visited "
                f"({coverage_percentage:.1f}%), {len(critical_gaps)} critical gaps"
            )

            return {
                'total_zones': total_zones,
                'zones_visited': zones_visited,
                'coverage_percentage': coverage_percentage,
                'critical_gaps': critical_gaps,
                'zones_needing_attention': zones_needing_attention
            }

        except Exception as e:
            logger.error(f"Error tracking coverage: {str(e)}", exc_info=True)
            return {
                'total_zones': 0,
                'zones_visited': 0,
                'coverage_percentage': Decimal('0'),
                'critical_gaps': [f"Coverage tracking failed: {str(e)}"],
                'zones_needing_attention': []
            }

    def _build_unified_observation(
        self,
        voice_data: Dict[str, Any],
        photo_data: Optional[Dict[str, Any]],
        gps_data: Optional[Dict[str, float]]
    ) -> Dict[str, Any]:
        """Build unified observation from multiple modalities."""
        unified = {
            'timestamp': datetime.now().isoformat(),
            'modalities': []
        }

        # Voice modality
        if voice_data:
            unified['modalities'].append('voice')
            unified['transcript'] = voice_data.get('transcript_en')
            unified['transcript_original'] = voice_data.get('transcript_original')
            unified['voice_confidence'] = voice_data.get('confidence', 0.0)

        # Photo modality
        if photo_data:
            unified['modalities'].append('photo')
            unified['detected_objects'] = photo_data.get('objects', [])
            unified['security_equipment'] = photo_data.get('security_equipment', [])
            unified['safety_concerns'] = photo_data.get('safety_concerns', [])
            unified['vision_confidence'] = photo_data.get('confidence', 0.0)

        # GPS modality
        if gps_data and 'latitude' in gps_data and 'longitude' in gps_data:
            unified['modalities'].append('gps')
            unified['gps_coordinates'] = gps_data

        return unified

    def _identify_zone(
        self,
        site: OnboardingSite,
        gps_data: Optional[Dict[str, float]],
        voice_data: Dict[str, Any],
        photo_data: Optional[Dict[str, Any]],
        zone_hint: Optional[str]
    ) -> Optional[OnboardingZone]:
        """Identify zone from multiple signals."""
        candidate_zones = []

        # GPS-based zone identification
        if gps_data and 'latitude' in gps_data and 'longitude' in gps_data:
            point = Point(gps_data['longitude'], gps_data['latitude'], srid=4326)

            nearby_zones = site.zones.filter(
                gps_coordinates__distance_lte=(
                    point,
                    D(m=self.GPS_CORRELATION_THRESHOLD)
                )
            ).order_by('gps_coordinates__distance')

            if nearby_zones.exists():
                candidate_zones.append(('gps', nearby_zones.first()))

        # Voice-based zone identification (keyword matching)
        if voice_data and voice_data.get('transcript_en'):
            transcript = voice_data['transcript_en'].lower()

            # Try to match zone names or types
            for zone in site.zones.all():
                if zone.zone_name.lower() in transcript or zone.zone_type in transcript:
                    candidate_zones.append(('voice', zone))
                    break

        # Photo-based zone identification (object patterns)
        if photo_data and photo_data.get('objects'):
            objects = [obj.lower() for obj in photo_data['objects']]

            # Match zone types by typical objects
            zone_object_patterns = {
                'vault': ['safe', 'vault', 'door', 'lock'],
                'gate': ['gate', 'barrier', 'fence'],
                'control_room': ['monitor', 'computer', 'desk', 'chair'],
                'atm': ['atm', 'cash machine', 'dispenser'],
                'parking': ['car', 'vehicle', 'parking']
            }

            for zone_type, patterns in zone_object_patterns.items():
                if any(pattern in obj for obj in objects for pattern in patterns):
                    matching_zone = site.zones.filter(zone_type=zone_type).first()
                    if matching_zone:
                        candidate_zones.append(('photo', matching_zone))
                        break

        # Zone hint from operator
        if zone_hint:
            hint_zone = site.zones.filter(
                Q(zone_name__icontains=zone_hint) | Q(zone_type=zone_hint)
            ).first()
            if hint_zone:
                candidate_zones.append(('hint', hint_zone))

        # Select best candidate (prefer GPS, then hint, then voice, then photo)
        priority_order = ['gps', 'hint', 'voice', 'photo']
        for priority in priority_order:
            for source, zone in candidate_zones:
                if source == priority:
                    logger.info(f"Zone identified by {source}: {zone.zone_name}")
                    return zone

        return None

    def _cross_validate_modalities(
        self,
        voice_data: Dict[str, Any],
        photo_data: Optional[Dict[str, Any]],
        gps_data: Optional[Dict[str, float]]
    ) -> Dict[str, Any]:
        """Cross-validate data across modalities for consistency."""
        validation = {
            'is_consistent': True,
            'inconsistencies': [],
            'agreements': []
        }

        # Validate voice vs photo
        if voice_data and photo_data:
            voice_transcript = voice_data.get('transcript_en', '').lower()
            photo_objects = [obj.lower() for obj in photo_data.get('objects', [])]

            # Check for contradictions
            if 'no camera' in voice_transcript and 'camera' in ' '.join(photo_objects):
                validation['inconsistencies'].append(
                    "Voice states 'no camera' but camera detected in photo"
                )
                validation['is_consistent'] = False

            # Check for agreements
            security_terms = ['camera', 'alarm', 'sensor', 'detector']
            for term in security_terms:
                if term in voice_transcript and any(term in obj for obj in photo_objects):
                    validation['agreements'].append(
                        f"Both voice and photo confirm presence of {term}"
                    )

        # Validate confidence levels
        if voice_data:
            voice_conf = voice_data.get('confidence', 0.0)
            if voice_conf < self.MIN_VOICE_CONFIDENCE:
                validation['inconsistencies'].append(
                    f"Low voice confidence: {voice_conf:.2f} < {self.MIN_VOICE_CONFIDENCE}"
                )

        if photo_data:
            vision_conf = photo_data.get('confidence', 0.0)
            if vision_conf < self.MIN_VISION_CONFIDENCE:
                validation['inconsistencies'].append(
                    f"Low vision confidence: {vision_conf:.2f} < {self.MIN_VISION_CONFIDENCE}"
                )

        return validation

    def _calculate_aggregated_confidence(
        self,
        voice_data: Dict[str, Any],
        photo_data: Optional[Dict[str, Any]],
        validation: Dict[str, Any]
    ) -> Decimal:
        """Calculate aggregated confidence from multiple modalities."""
        confidences = []

        if voice_data and 'confidence' in voice_data:
            confidences.append(voice_data['confidence'])

        if photo_data and 'confidence' in photo_data:
            confidences.append(photo_data['confidence'])

        if not confidences:
            return Decimal('0.0')

        # Average confidence
        avg_confidence = sum(confidences) / len(confidences)

        # Boost if cross-modal validation passed
        if validation.get('is_consistent', False) and len(confidences) > 1:
            avg_confidence += self.CROSS_MODAL_BOOST

        # Cap at 1.0
        return Decimal(str(min(avg_confidence, 1.0)))


# Factory function
def get_multimodal_fusion_service() -> MultimodalFusionService:
    """Factory function to get multimodal fusion service instance."""
    return MultimodalFusionService()