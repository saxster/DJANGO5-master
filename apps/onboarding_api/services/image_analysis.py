"""
Image Analysis Service for Site Onboarding - Vision API wrapper.

This service provides comprehensive image analysis capabilities including
object detection, hazard identification, label detection, and landmark recognition
using Google Cloud Vision API.

Features:
- Object and entity detection
- Safety hazard identification
- Security equipment recognition
- Label and logo detection
- Confidence scoring

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling (no bare except)
"""

import logging
from typing import Dict, Any, List, Optional
from django.core.files.uploadedfile import UploadedFile
from apps.onboarding_api.services.pii_integration import get_pii_service

logger = logging.getLogger(__name__)


class ImageAnalysisService:
    """
    Image analysis service using Google Cloud Vision API.

    Provides object detection, hazard identification, and comprehensive
    image understanding for site security auditing.
    """

    # Security equipment keywords
    SECURITY_EQUIPMENT = {
        'camera', 'cctv', 'surveillance', 'dvr', 'nvr', 'recorder',
        'alarm', 'sensor', 'detector', 'keypad', 'access control',
        'biometric', 'fingerprint', 'card reader', 'turnstile',
        'metal detector', 'x-ray', 'scanner', 'intercom',
        'barrier', 'gate', 'bollard', 'fence', 'lighting'
    }

    # Hazard keywords
    HAZARD_KEYWORDS = {
        'fire', 'smoke', 'damage', 'broken', 'cracked', 'blocked',
        'obstructed', 'missing', 'exposed', 'loose', 'unlocked',
        'open', 'unsecured', 'debris', 'clutter', 'leak', 'wet'
    }

    # Safety equipment
    SAFETY_EQUIPMENT = {
        'fire extinguisher', 'fire alarm', 'smoke detector',
        'emergency exit', 'exit sign', 'first aid', 'aed',
        'emergency light', 'sprinkler', 'hydrant', 'hose reel'
    }

    def __init__(self):
        """Initialize Vision API client."""
        self.vision_client = None
        self._initialize_vision_client()
        self.pii_service = get_pii_service()  # PII redaction for image labels/text (Rule #15 compliance)

    def _initialize_vision_client(self):
        """Initialize Google Cloud Vision client."""
        try:
            from google.cloud import vision
            self.vision_client = vision.ImageAnnotatorClient()
            logger.info("Vision API client initialized successfully")
        except ImportError:
            logger.warning("google-cloud-vision not installed, using mock data")
            self.vision_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Vision API: {str(e)}")
            self.vision_client = None

    def analyze_image(
        self,
        photo: UploadedFile,
        zone_type: str = None
    ) -> Dict[str, Any]:
        """
        Comprehensive image analysis.

        Args:
            photo: Uploaded image file
            zone_type: Type of zone for context-aware analysis

        Returns:
            {
                'success': bool,
                'objects': List[str],
                'labels': List[Dict],
                'safety_concerns': List[str],
                'security_equipment': List[str],
                'text': str,
                'confidence': float,
                'error': str | None
            }
        """
        result = {
            'success': False,
            'objects': [],
            'labels': [],
            'safety_concerns': [],
            'security_equipment': [],
            'text': None,
            'confidence': 0.0,
            'error': None
        }

        if not self.vision_client:
            return self._mock_image_analysis(zone_type)

        try:
            image_content = photo.read()

            from google.cloud import vision
            image = vision.Image(content=image_content)

            # Perform multiple detection types
            features = [
                {'type_': vision.Feature.Type.OBJECT_LOCALIZATION},
                {'type_': vision.Feature.Type.LABEL_DETECTION},
                {'type_': vision.Feature.Type.TEXT_DETECTION},
                {'type_': vision.Feature.Type.SAFE_SEARCH_DETECTION},
            ]

            request = {
                'image': image,
                'features': features
            }

            response = self.vision_client.annotate_image(request)

            if response.error.message:
                result['error'] = response.error.message
                logger.error(f"Vision API error: {response.error.message}")
                return result

            # Process objects
            if response.localized_object_annotations:
                result['objects'] = [
                    obj.name for obj in response.localized_object_annotations
                ]

            # Process labels
            if response.label_annotations:
                raw_labels = [
                    {'name': label.description, 'confidence': label.score}
                    for label in response.label_annotations[:10]
                ]
                # CRITICAL: Apply PII redaction to labels (Rule #15 compliance)
                result['labels'] = self.pii_service.sanitize_image_analysis_labels(
                    labels=raw_labels,
                    session_id='image_analysis'
                )

            # Extract text
            if response.text_annotations:
                raw_text = response.text_annotations[0].description
                # CRITICAL: Apply PII redaction to extracted text (Rule #15 compliance)
                pii_result = self.pii_service.sanitize_user_input(
                    user_input=raw_text,
                    session_id='image_analysis',
                    input_type='image_text'
                )
                result['text'] = pii_result['sanitized_input']
                result['text_pii_redacted'] = pii_result['redaction_metadata']['redactions_count'] > 0

            # Identify security equipment and hazards
            all_detected = result['objects'] + [
                label['name'].lower() for label in result['labels']
            ]
            if result['text']:
                all_detected.append(result['text'].lower())

            result['security_equipment'] = self._identify_security_equipment(
                all_detected
            )
            result['safety_concerns'] = self._identify_hazards(
                all_detected,
                zone_type
            )

            # Calculate overall confidence
            if result['labels']:
                avg_confidence = sum(l['confidence'] for l in result['labels'])
                result['confidence'] = avg_confidence / len(result['labels'])
            else:
                result['confidence'] = 0.5

            result['success'] = True
            logger.info(
                f"Image analysis complete: {len(result['objects'])} objects, "
                f"{len(result['labels'])} labels, "
                f"{len(result['security_equipment'])} security items"
            )

        except (IOError, OSError) as e:
            logger.error(f"File operation error in image analysis: {str(e)}")
            result['error'] = f"File error: {str(e)}"
        except ValueError as e:
            logger.error(f"Value error in image analysis: {str(e)}")
            result['error'] = f"Processing error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in image analysis: {str(e)}", exc_info=True)
            result['error'] = f"Analysis failed: {str(e)}"

        return result

    def detect_objects(self, photo: UploadedFile) -> List[Dict[str, Any]]:
        """
        Detect objects in image with bounding boxes.

        Returns:
            [{'name': str, 'confidence': float, 'bbox': {...}}]
        """
        if not self.vision_client:
            return self._mock_objects()

        try:
            image_content = photo.read()

            from google.cloud import vision
            image = vision.Image(content=image_content)

            response = self.vision_client.object_localization(image=image)

            if response.error.message:
                logger.error(f"Object detection error: {response.error.message}")
                return []

            objects = []
            for obj in response.localized_object_annotations:
                objects.append({
                    'name': obj.name,
                    'confidence': obj.score,
                    'bbox': {
                        'vertices': [
                            {'x': vertex.x, 'y': vertex.y}
                            for vertex in obj.bounding_poly.normalized_vertices
                        ]
                    }
                })

            logger.info(f"Detected {len(objects)} objects")
            return objects

        except (IOError, OSError, ValueError) as e:
            logger.error(f"Error in object detection: {str(e)}")
            return []

    def detect_hazards(
        self,
        photo: UploadedFile,
        zone_type: str
    ) -> List[str]:
        """
        Detect safety hazards specific to zone type.

        Args:
            photo: Image to analyze
            zone_type: Zone context (gate/vault/perimeter/etc.)

        Returns:
            List of identified hazards
        """
        analysis = self.analyze_image(photo, zone_type)
        return analysis.get('safety_concerns', [])

    def _identify_security_equipment(
        self,
        detected_items: List[str]
    ) -> List[str]:
        """Identify security equipment from detected items."""
        equipment = []
        detected_lower = [item.lower() for item in detected_items]

        for item in detected_lower:
            for keyword in self.SECURITY_EQUIPMENT:
                if keyword in item and keyword not in equipment:
                    equipment.append(keyword)

        return equipment

    def _identify_hazards(
        self,
        detected_items: List[str],
        zone_type: str = None
    ) -> List[str]:
        """Identify safety hazards from detected items."""
        hazards = []
        detected_lower = [item.lower() for item in detected_items]

        # Check for hazard keywords
        for item in detected_lower:
            for keyword in self.HAZARD_KEYWORDS:
                if keyword in item:
                    hazards.append(f"Potential hazard detected: {keyword}")

        # Zone-specific checks
        if zone_type == 'emergency_exit':
            if any('blocked' in item or 'obstructed' in item for item in detected_lower):
                hazards.append("Emergency exit appears blocked")

        elif zone_type == 'vault':
            if any('open' in item or 'unlocked' in item for item in detected_lower):
                hazards.append("Vault door not secured")

        elif zone_type == 'perimeter':
            if any('breach' in item or 'gap' in item for item in detected_lower):
                hazards.append("Potential perimeter breach")

        # Check for missing safety equipment
        has_fire_safety = any(
            equip in item
            for item in detected_lower
            for equip in ['fire extinguisher', 'fire alarm', 'smoke detector']
        )

        if zone_type in ['control_room', 'server_room'] and not has_fire_safety:
            hazards.append("No fire safety equipment visible")

        return list(set(hazards))  # Remove duplicates

    def _mock_image_analysis(self, zone_type: str = None) -> Dict[str, Any]:
        """Mock image analysis for development."""
        mock_data = {
            'gate': {
                'objects': ['Gate', 'Fence', 'Camera', 'Barrier'],
                'security_equipment': ['camera', 'barrier', 'gate'],
                'safety_concerns': []
            },
            'vault': {
                'objects': ['Door', 'Safe', 'Camera', 'Keypad'],
                'security_equipment': ['camera', 'keypad', 'safe'],
                'safety_concerns': []
            },
            'control_room': {
                'objects': ['Monitor', 'Camera', 'Computer', 'Fire Extinguisher'],
                'security_equipment': ['camera', 'alarm'],
                'safety_concerns': []
            }
        }

        data = mock_data.get(zone_type, mock_data['gate'])

        return {
            'success': True,
            'objects': data['objects'],
            'labels': [
                {'name': obj, 'confidence': 0.85 + (i * 0.02)}
                for i, obj in enumerate(data['objects'])
            ],
            'safety_concerns': data['safety_concerns'],
            'security_equipment': data['security_equipment'],
            'text': f"[MOCK] Text detected in {zone_type or 'zone'}",
            'confidence': 0.87,
            'error': None
        }

    def _mock_objects(self) -> List[Dict[str, Any]]:
        """Mock object detection for development."""
        return [
            {
                'name': 'Camera',
                'confidence': 0.92,
                'bbox': {'vertices': [
                    {'x': 0.1, 'y': 0.1},
                    {'x': 0.3, 'y': 0.1},
                    {'x': 0.3, 'y': 0.3},
                    {'x': 0.1, 'y': 0.3}
                ]}
            },
            {
                'name': 'Fire Extinguisher',
                'confidence': 0.88,
                'bbox': {'vertices': [
                    {'x': 0.7, 'y': 0.4},
                    {'x': 0.85, 'y': 0.4},
                    {'x': 0.85, 'y': 0.8},
                    {'x': 0.7, 'y': 0.8}
                ]}
            }
        ]


# Factory function
def get_image_analysis_service() -> ImageAnalysisService:
    """Factory function to get image analysis service instance."""
    return ImageAnalysisService()