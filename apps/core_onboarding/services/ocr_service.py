"""
OCR Service for Site Onboarding - Extract text from meters and registers.

This service provides optical character recognition for meter readings,
logbooks, and register entries using Google Cloud Vision API.

Features:
- Meter reading extraction with validation
- Register entry extraction with structured parsing
- Confidence scoring and error handling
- Support for multiple meter types (electricity, water, diesel, etc.)

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling (no bare except)
- Rule #12: Query optimization where applicable
"""

import re
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, List
from datetime import datetime
from django.core.files.uploadedfile import UploadedFile
from apps.core_onboarding.services.pii_integration import get_pii_service

logger = logging.getLogger(__name__)


class OCRService:
    """
    OCR service for extracting structured data from images.

    Uses Google Cloud Vision API (same credentials as speech service).
    """

    def __init__(self):
        """Initialize OCR service with Vision API client."""
        self.vision_client = None
        self._initialize_vision_client()
        self.pii_service = get_pii_service()  # PII redaction for OCR results (Rule #15 compliance)

    def _initialize_vision_client(self):
        """Initialize Google Cloud Vision client."""
        try:
            from google.cloud import vision
            self.vision_client = vision.ImageAnnotatorClient()
            logger.info("Google Cloud Vision API client initialized successfully")
        except ImportError:
            logger.warning("google-cloud-vision not installed, OCR will return mock data")
            self.vision_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Vision API client: {str(e)}")
            self.vision_client = None

    def extract_register_entry(
        self,
        photo: UploadedFile,
        register_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Extract structured data from register/logbook photo.

        Args:
            photo: Uploaded image file of register entry
            register_type: Type of register (visitor/incident/maintenance/general)

        Returns:
            {
                'success': bool,
                'text': str,
                'fields': {
                    'date': str,
                    'time': str,
                    'entry_by': str,
                    'description': str,
                    'signatures': List[str]
                },
                'confidence': float,
                'error': str | None
            }
        """
        result = {
            'success': False,
            'text': None,
            'fields': {},
            'confidence': 0.0,
            'error': None
        }

        if not self.vision_client:
            return self._mock_register_extraction(register_type)

        try:
            # Read image content
            image_content = photo.read()

            # Prepare Vision API request
            from google.cloud import vision
            image = vision.Image(content=image_content)

            # Perform OCR
            response = self.vision_client.document_text_detection(image=image)

            if response.error.message:
                result['error'] = response.error.message
                logger.error(f"Vision API error: {response.error.message}")
                return result

            # Extract full text
            if response.full_text_annotation:
                full_text = response.full_text_annotation.text

                # CRITICAL: Apply PII redaction before storing/logging (Rule #15 compliance)
                pii_result = self.pii_service.sanitize_ocr_result(
                    ocr_text=full_text,
                    session_id='ocr_extraction',  # Can be passed as parameter
                    document_type=register_type
                )

                # Use sanitized text for storage and processing
                sanitized_text = pii_result['sanitized_text']

                result['text'] = sanitized_text
                result['confidence'] = self._calculate_text_confidence(
                    response.full_text_annotation
                )

                # Parse structured fields from sanitized text
                result['fields'] = self._parse_register_fields(
                    sanitized_text,
                    register_type
                )
                result['success'] = True
                result['pii_redacted'] = pii_result['redaction_metadata']['redactions_count'] > 0
                result['safe_for_storage'] = pii_result['safe_for_llm']

                logger.info(
                    f"Register extraction successful (PII-sanitized): {len(sanitized_text)} chars, "
                    f"confidence={result['confidence']:.2f}, pii_redactions={pii_result['redaction_metadata']['redactions_count']}"
                )
            else:
                result['error'] = "No text detected in image"
                logger.warning("No text detected in register photo")

        except (IOError, OSError) as e:
            logger.error(f"File operation error during OCR: {str(e)}")
            result['error'] = f"File error: {str(e)}"
        except ValueError as e:
            logger.error(f"Value error during OCR: {str(e)}")
            result['error'] = f"Processing error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in register extraction: {str(e)}", exc_info=True)
            result['error'] = f"OCR failed: {str(e)}"

        return result

    def extract_meter_reading(
        self,
        photo: UploadedFile,
        meter_type: str,
        expected_unit: str = None,
        validation_range: tuple = None
    ) -> Dict[str, Any]:
        """
        Extract and validate meter reading from photo.

        Args:
            photo: Uploaded image file of meter
            meter_type: Type of meter (electricity/water/diesel/etc.)
            expected_unit: Expected unit (kWh, liters, °C, etc.)
            validation_range: (min, max) tuple for validation

        Returns:
            {
                'success': bool,
                'value': Decimal | None,
                'unit': str | None,
                'timestamp': str,
                'confidence': float,
                'validation': {
                    'passed': bool,
                    'issues': List[str]
                },
                'raw_text': str,
                'error': str | None
            }
        """
        result = {
            'success': False,
            'value': None,
            'unit': expected_unit,
            'timestamp': datetime.now().isoformat(),
            'confidence': 0.0,
            'validation': {'passed': False, 'issues': []},
            'raw_text': None,
            'error': None
        }

        if not self.vision_client:
            return self._mock_meter_reading(meter_type, expected_unit)

        try:
            # Read image content
            image_content = photo.read()

            # Prepare Vision API request
            from google.cloud import vision
            image = vision.Image(content=image_content)

            # Perform OCR
            response = self.vision_client.text_detection(image=image)

            if response.error.message:
                result['error'] = response.error.message
                logger.error(f"Vision API error: {response.error.message}")
                return result

            # Extract text
            if response.text_annotations:
                raw_text = response.text_annotations[0].description

                # CRITICAL: Apply PII redaction before storing (Rule #15 compliance)
                pii_result = self.pii_service.sanitize_ocr_result(
                    ocr_text=raw_text,
                    session_id='meter_reading',  # Can be passed as parameter
                    document_type=meter_type
                )
                sanitized_text = pii_result['sanitized_text']
                result['raw_text'] = sanitized_text
                result['pii_redacted'] = pii_result['redaction_metadata']['redactions_count'] > 0

                # Extract numeric value from sanitized text
                extracted_value, extracted_unit = self._extract_numeric_value(
                    sanitized_text,  # Use sanitized text for extraction
                    meter_type
                )

                if extracted_value is not None:
                    result['value'] = extracted_value
                    result['unit'] = extracted_unit or expected_unit
                    result['confidence'] = self._calculate_detection_confidence(
                        response.text_annotations
                    )

                    # Validate reading
                    validation_result = self._validate_meter_reading(
                        extracted_value,
                        meter_type,
                        validation_range
                    )
                    result['validation'] = validation_result
                    result['success'] = validation_result['passed']

                    logger.info(
                        f"Meter reading extracted (PII-sanitized): {extracted_value} {result['unit']}, "
                        f"confidence={result['confidence']:.2f}, "
                        f"valid={validation_result['passed']}, "
                        f"pii_redactions={pii_result['redaction_metadata']['redactions_count']}"
                    )
                else:
                    result['error'] = "No numeric value detected in meter image"
                    logger.warning("Failed to extract numeric value from meter")
            else:
                result['error'] = "No text detected in meter image"
                logger.warning("No text detected in meter photo")

        except (IOError, OSError) as e:
            logger.error(f"File operation error during meter OCR: {str(e)}")
            result['error'] = f"File error: {str(e)}"
        except (ValueError, InvalidOperation) as e:
            logger.error(f"Value processing error: {str(e)}")
            result['error'] = f"Processing error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in meter reading: {str(e)}", exc_info=True)
            result['error'] = f"OCR failed: {str(e)}"

        return result

    def _extract_numeric_value(
        self,
        text: str,
        meter_type: str
    ) -> tuple:
        """Extract numeric value and unit from OCR text."""
        # Special handling for license plates
        if meter_type == 'license_plate':
            license_plate = self._extract_license_plate_value(text)
            return (license_plate, None) if license_plate else (None, None)

        # Patterns for different meter types
        patterns = {
            'electricity': r'(\d+\.?\d*)\s*(kWh|kwh|KWH)?',
            'water': r'(\d+\.?\d*)\s*(L|l|liters?|Liters?|m³)?',
            'diesel': r'(\d+\.?\d*)\s*(L|l|liters?|Liters?)?',
            'temperature': r'(\d+\.?\d*)\s*[°]?\s*[CcFf]?',
            'fire_pressure': r'(\d+\.?\d*)\s*(psi|PSI|bar|Bar)?',
            'generator_hours': r'(\d+\.?\d*)\s*(hrs?|hours?)?',
        }

        pattern = patterns.get(meter_type, r'(\d+\.?\d*)')
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            try:
                value = Decimal(match.group(1))
                unit = match.group(2) if len(match.groups()) > 1 else None
                return value, unit
            except (InvalidOperation, ValueError) as e:
                logger.warning(f"Failed to parse numeric value: {str(e)}")
                return None, None

        return None, None

    def _extract_license_plate_value(self, text: str) -> Optional[str]:
        """Extract license plate from OCR text using pattern matching."""
        if not text:
            return None

        # US license plate patterns (common formats)
        patterns = [
            r'[A-Z]{3}[0-9]{4}',     # ABC1234
            r'[0-9]{3}[A-Z]{3}',     # 123ABC
            r'[A-Z]{2}[0-9]{5}',     # AB12345
            r'[A-Z][0-9]{2}[A-Z]{3}', # A12BCD
            r'[0-9][A-Z]{3}[0-9]{3}', # 1ABC123
            r'[A-Z]{4}[0-9]{3}',     # ABCD123
            r'[A-Z0-9]{4,8}',        # Generic alphanumeric
        ]

        # Clean and prepare text
        lines = [line.strip().upper() for line in text.split('\n') if line.strip()]

        for line in lines:
            # Remove common OCR artifacts and non-alphanumeric chars
            cleaned = re.sub(r'[^\w\s]', '', line)
            cleaned = re.sub(r'\s+', '', cleaned)

            # Try each pattern
            for pattern in patterns:
                matches = re.findall(pattern, cleaned)
                if matches:
                    # Return first match that meets minimum length
                    for match in matches:
                        if 4 <= len(match) <= 8:
                            return match

        return None

    def _validate_meter_reading(
        self,
        value: Decimal,
        meter_type: str,
        validation_range: tuple = None
    ) -> Dict[str, Any]:
        """Validate meter reading against expected ranges."""
        issues = []

        # Range validation
        if validation_range:
            min_val, max_val = validation_range
            if value < Decimal(str(min_val)):
                issues.append(f"Value {value} below minimum {min_val}")
            if value > Decimal(str(max_val)):
                issues.append(f"Value {value} exceeds maximum {max_val}")

        # Type-specific validation
        if meter_type == 'temperature':
            if value < Decimal('-50') or value > Decimal('100'):
                issues.append(f"Temperature {value}°C outside reasonable range")
        elif meter_type == 'fire_pressure':
            if value < Decimal('0') or value > Decimal('200'):
                issues.append(f"Pressure {value} psi outside typical range")

        return {
            'passed': len(issues) == 0,
            'issues': issues
        }

    def _parse_register_fields(
        self,
        text: str,
        register_type: str
    ) -> Dict[str, Any]:
        """Parse structured fields from register text."""
        fields = {}

        # Extract date (various formats)
        date_match = re.search(
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            text
        )
        if date_match:
            fields['date'] = date_match.group(1)

        # Extract time
        time_match = re.search(
            r'(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)',
            text
        )
        if time_match:
            fields['time'] = time_match.group(1)

        # Extract names (common patterns)
        name_keywords = ['name:', 'by:', 'officer:', 'guard:']
        for keyword in name_keywords:
            match = re.search(
                rf'{keyword}\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                text,
                re.IGNORECASE
            )
            if match:
                fields['entry_by'] = match.group(1)
                break

        # Extract description (usually longest text block)
        lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 20]
        if lines:
            fields['description'] = lines[0]

        return fields

    def _calculate_text_confidence(self, annotation) -> float:
        """Calculate overall confidence from document annotation."""
        if not annotation.pages:
            return 0.0

        confidences = []
        for page in annotation.pages:
            for block in page.blocks:
                if hasattr(block, 'confidence'):
                    confidences.append(block.confidence)

        return sum(confidences) / len(confidences) if confidences else 0.0

    def _calculate_detection_confidence(self, annotations: List) -> float:
        """Calculate confidence from text annotations."""
        if len(annotations) < 2:
            return 0.0

        # First annotation is full text, skip it
        confidences = [
            ann.confidence for ann in annotations[1:]
            if hasattr(ann, 'confidence')
        ]

        return sum(confidences) / len(confidences) if confidences else 0.0

    def _mock_register_extraction(self, register_type: str) -> Dict[str, Any]:
        """Mock register extraction for development without Vision API."""
        return {
            'success': True,
            'text': f"[MOCK] Register entry - Type: {register_type}\nDate: 28/09/2025\nTime: 10:30 AM\nOfficer: John Doe\nEntry: Routine inspection completed",
            'fields': {
                'date': '28/09/2025',
                'time': '10:30 AM',
                'entry_by': 'John Doe',
                'description': 'Routine inspection completed'
            },
            'confidence': 0.85,
            'error': None
        }

    def _mock_meter_reading(
        self,
        meter_type: str,
        expected_unit: str
    ) -> Dict[str, Any]:
        """Mock meter reading for development without Vision API."""
        mock_values = {
            'electricity': (Decimal('12345.67'), 'kWh'),
            'water': (Decimal('9876.5'), 'L'),
            'diesel': (Decimal('543.2'), 'L'),
            'temperature': (Decimal('24.5'), '°C'),
            'fire_pressure': (Decimal('85'), 'psi'),
            'generator_hours': (Decimal('1234'), 'hrs'),
        }

        value, unit = mock_values.get(meter_type, (Decimal('100'), expected_unit))

        return {
            'success': True,
            'value': value,
            'unit': unit,
            'timestamp': datetime.now().isoformat(),
            'confidence': 0.90,
            'validation': {'passed': True, 'issues': []},
            'raw_text': f"[MOCK] {value} {unit}",
            'error': None
        }


# Factory function
def get_ocr_service() -> OCRService:
    """Factory function to get OCR service instance."""
    return OCRService()