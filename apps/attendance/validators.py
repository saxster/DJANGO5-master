"""
Attendance field validators and JSON schema validation

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive field validation
"""

import json
import logging
from typing import Dict, Any, Optional
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class AttendanceValidationError(ValidationError):
    """Custom exception for attendance validation errors"""
    pass


class JSONSchemaValidator:
    """
    Validates peventlogextras JSON field structure and content.

    Ensures data integrity and prevents corruption during concurrent updates.
    """

    SCHEMA = {
        "type": "object",
        "properties": {
            # Face Recognition Data
            "verified_in": {"type": "boolean"},
            "distance_in": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "verified_out": {"type": "boolean"},
            "distance_out": {"type": ["number", "null"], "minimum": 0, "maximum": 1},

            # Model Configuration
            "threshold": {"type": "string", "pattern": r"^\d+(\.\d+)?$"},
            "model": {"type": "string", "enum": ["Facenet512", "VGGFace", "OpenFace"]},
            "similarity_metric": {"type": "string", "enum": ["cosine", "euclidean", "manhattan"]},

            # Geofence Status
            "isStartLocationInGeofence": {"type": "boolean"},
            "isEndLocationInGeofence": {"type": "boolean"},

            # Processing Metadata
            "processing_timestamp": {"type": "string"},
            "verification_attempts": {"type": "integer", "minimum": 0, "maximum": 5},
            "error_logs": {"type": "array", "items": {"type": "string"}},

            # Quality Metrics
            "face_quality_score": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "location_accuracy": {"type": ["number", "null"], "minimum": 0}
        },
        "required": ["verified_in", "verified_out", "threshold", "model", "similarity_metric"],
        "additionalProperties": False
    }

    @classmethod
    def validate_json_structure(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate JSON structure against schema.

        Args:
            value: JSON data to validate

        Returns:
            Validated and sanitized JSON data

        Raises:
            AttendanceValidationError: If validation fails
        """
        if not isinstance(value, dict):
            raise AttendanceValidationError("peventlogextras must be a dictionary")

        # Check required fields
        required_fields = cls.SCHEMA["required"]
        missing_fields = [field for field in required_fields if field not in value]
        if missing_fields:
            raise AttendanceValidationError(
                f"Missing required fields: {missing_fields}"
            )

        # Validate each field
        validated_data = {}
        schema_props = cls.SCHEMA["properties"]

        for field, field_value in value.items():
            if field not in schema_props:
                logger.warning(f"Unknown field in peventlogextras: {field}")
                continue

            try:
                validated_data[field] = cls._validate_field(
                    field, field_value, schema_props[field]
                )
            except (ValueError, TypeError) as e:
                raise AttendanceValidationError(
                    f"Invalid value for field '{field}': {str(e)}"
                ) from e

        return validated_data

    @classmethod
    def _validate_field(cls, field_name: str, value: Any, schema: Dict[str, Any]) -> Any:
        """Validate individual field against its schema"""
        field_type = schema["type"]

        # Handle nullable types
        if isinstance(field_type, list) and "null" in field_type:
            if value is None:
                return None
            field_type = [t for t in field_type if t != "null"][0]

        # Type validation
        if field_type == "boolean" and not isinstance(value, bool):
            raise ValueError(f"Expected boolean, got {type(value).__name__}")

        elif field_type == "number" and not isinstance(value, (int, float)):
            raise ValueError(f"Expected number, got {type(value).__name__}")

        elif field_type == "integer" and not isinstance(value, int):
            raise ValueError(f"Expected integer, got {type(value).__name__}")

        elif field_type == "string" and not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value).__name__}")

        elif field_type == "array" and not isinstance(value, list):
            raise ValueError(f"Expected array, got {type(value).__name__}")

        # Range validation
        if "minimum" in schema and isinstance(value, (int, float)):
            if value < schema["minimum"]:
                raise ValueError(f"Value {value} below minimum {schema['minimum']}")

        if "maximum" in schema and isinstance(value, (int, float)):
            if value > schema["maximum"]:
                raise ValueError(f"Value {value} above maximum {schema['maximum']}")

        # Enum validation
        if "enum" in schema and value not in schema["enum"]:
            raise ValueError(f"Value '{value}' not in allowed values: {schema['enum']}")

        # Pattern validation for strings
        if "pattern" in schema and isinstance(value, str):
            import re
            if not re.match(schema["pattern"], value):
                raise ValueError(f"Value '{value}' does not match pattern {schema['pattern']}")

        return value

    @classmethod
    def get_default_extras(cls) -> Dict[str, Any]:
        """Get default peventlogextras structure"""
        return {
            "verified_in": False,
            "distance_in": None,
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine",
            "verification_attempts": 0,
            "error_logs": []
        }


def validate_peventlog_extras(value: Any) -> Dict[str, Any]:
    """
    Django field validator for peventlogextras JSON field.

    Args:
        value: JSON data to validate

    Returns:
        Validated JSON data

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        return JSONSchemaValidator.get_default_extras()

    try:
        return JSONSchemaValidator.validate_json_structure(value)
    except AttendanceValidationError as e:
        raise ValidationError(
            _("Invalid peventlogextras data: %(error)s"),
            params={"error": str(e)}
        ) from e


def validate_face_recognition_distance(value: Optional[float]) -> Optional[float]:
    """
    Validate face recognition distance score.

    Args:
        value: Distance value (0.0 to 1.0, lower is better match)

    Returns:
        Validated distance value

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        return None

    if not isinstance(value, (int, float)):
        raise ValidationError("Face recognition distance must be a number")

    if not 0.0 <= value <= 1.0:
        raise ValidationError(
            "Face recognition distance must be between 0.0 and 1.0"
        )

    return float(value)


def validate_geofence_coordinates(lat: float, lon: float) -> tuple[float, float]:
    """
    Validate geographic coordinates.

    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)

    Returns:
        Validated coordinates tuple

    Raises:
        ValidationError: If coordinates are invalid
    """
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError) as e:
        raise ValidationError("Coordinates must be numeric") from e

    if not -90.0 <= lat <= 90.0:
        raise ValidationError(f"Latitude {lat} must be between -90 and 90")

    if not -180.0 <= lon <= 180.0:
        raise ValidationError(f"Longitude {lon} must be between -180 and 180")

    return lat, lon