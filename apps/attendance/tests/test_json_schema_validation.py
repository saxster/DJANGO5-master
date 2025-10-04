"""
Comprehensive tests for JSON schema validation in attendance system

Tests the validators.py module functionality including edge cases
and error handling scenarios.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError

from apps.attendance.validators import (
    JSONSchemaValidator,
    validate_peventlog_extras,
    validate_face_recognition_distance,
    validate_geofence_coordinates,
    AttendanceValidationError
)


class TestJSONSchemaValidator(TestCase):
    """Test JSON schema validation for peventlogextras field"""

    def test_valid_json_structure(self):
        """Test validation of valid JSON structure"""
        valid_data = {
            "verified_in": True,
            "distance_in": 0.2,
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine",
            "verification_attempts": 1,
            "error_logs": ["Test error"]
        }

        result = JSONSchemaValidator.validate_json_structure(valid_data)
        self.assertEqual(result["verified_in"], True)
        self.assertEqual(result["distance_in"], 0.2)
        self.assertEqual(result["model"], "Facenet512")

    def test_invalid_json_type(self):
        """Test validation fails for non-dict input"""
        with self.assertRaises(AttendanceValidationError) as ctx:
            JSONSchemaValidator.validate_json_structure("not a dict")

        self.assertIn("must be a dictionary", str(ctx.exception))

    def test_missing_required_fields(self):
        """Test validation fails for missing required fields"""
        incomplete_data = {
            "verified_in": True,
            # Missing required fields
        }

        with self.assertRaises(AttendanceValidationError) as ctx:
            JSONSchemaValidator.validate_json_structure(incomplete_data)

        self.assertIn("Missing required fields", str(ctx.exception))

    def test_invalid_field_types(self):
        """Test validation fails for incorrect field types"""
        invalid_data = {
            "verified_in": "not a boolean",  # Should be boolean
            "distance_in": "not a number",   # Should be number or null
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine"
        }

        with self.assertRaises(AttendanceValidationError) as ctx:
            JSONSchemaValidator.validate_json_structure(invalid_data)

        self.assertIn("Invalid value for field", str(ctx.exception))

    def test_invalid_enum_values(self):
        """Test validation fails for invalid enum values"""
        invalid_data = {
            "verified_in": True,
            "distance_in": 0.2,
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "InvalidModel",  # Not in enum
            "similarity_metric": "cosine"
        }

        with self.assertRaises(AttendanceValidationError) as ctx:
            JSONSchemaValidator.validate_json_structure(invalid_data)

        self.assertIn("not in allowed values", str(ctx.exception))

    def test_out_of_range_values(self):
        """Test validation fails for out-of-range values"""
        invalid_data = {
            "verified_in": True,
            "distance_in": 2.0,  # Should be 0-1
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine",
            "verification_attempts": 10  # Should be 0-5
        }

        with self.assertRaises(AttendanceValidationError) as ctx:
            JSONSchemaValidator.validate_json_structure(invalid_data)

        self.assertIn("above maximum", str(ctx.exception))

    def test_pattern_validation(self):
        """Test string pattern validation"""
        invalid_data = {
            "verified_in": True,
            "distance_in": 0.2,
            "verified_out": False,
            "distance_out": None,
            "threshold": "invalid_pattern",  # Should match numeric pattern
            "model": "Facenet512",
            "similarity_metric": "cosine"
        }

        with self.assertRaises(AttendanceValidationError) as ctx:
            JSONSchemaValidator.validate_json_structure(invalid_data)

        self.assertIn("does not match pattern", str(ctx.exception))

    def test_nullable_fields(self):
        """Test nullable field handling"""
        valid_data = {
            "verified_in": True,
            "distance_in": None,  # Nullable field
            "verified_out": False,
            "distance_out": None,  # Nullable field
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine",
            "face_quality_score": None,  # Nullable field
            "location_accuracy": None    # Nullable field
        }

        result = JSONSchemaValidator.validate_json_structure(valid_data)
        self.assertIsNone(result["distance_in"])
        self.assertIsNone(result["distance_out"])

    def test_unknown_fields_warning(self):
        """Test handling of unknown fields (should log warning but not fail)"""
        data_with_unknown = {
            "verified_in": True,
            "distance_in": 0.2,
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine",
            "unknown_field": "should be ignored"
        }

        # Should not raise exception, but unknown field should be filtered out
        result = JSONSchemaValidator.validate_json_structure(data_with_unknown)
        self.assertNotIn("unknown_field", result)

    def test_get_default_extras(self):
        """Test default extras structure"""
        defaults = JSONSchemaValidator.get_default_extras()

        self.assertIsInstance(defaults, dict)
        self.assertIn("verified_in", defaults)
        self.assertIn("verified_out", defaults)
        self.assertIn("model", defaults)
        self.assertEqual(defaults["verified_in"], False)
        self.assertEqual(defaults["verified_out"], False)
        self.assertEqual(defaults["model"], "Facenet512")


class TestValidationFunctions(TestCase):
    """Test standalone validation functions"""

    def test_validate_peventlog_extras_none(self):
        """Test validation with None input returns defaults"""
        result = validate_peventlog_extras(None)
        self.assertIsInstance(result, dict)
        self.assertIn("verified_in", result)

    def test_validate_peventlog_extras_valid(self):
        """Test validation with valid input"""
        valid_data = {
            "verified_in": True,
            "distance_in": 0.2,
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine"
        }

        result = validate_peventlog_extras(valid_data)
        self.assertEqual(result["verified_in"], True)
        self.assertEqual(result["distance_in"], 0.2)

    def test_validate_peventlog_extras_invalid(self):
        """Test validation with invalid input raises ValidationError"""
        invalid_data = {"invalid": "structure"}

        with self.assertRaises(ValidationError):
            validate_peventlog_extras(invalid_data)

    def test_validate_face_recognition_distance_valid(self):
        """Test face recognition distance validation with valid values"""
        self.assertEqual(validate_face_recognition_distance(0.0), 0.0)
        self.assertEqual(validate_face_recognition_distance(0.5), 0.5)
        self.assertEqual(validate_face_recognition_distance(1.0), 1.0)
        self.assertIsNone(validate_face_recognition_distance(None))

    def test_validate_face_recognition_distance_invalid(self):
        """Test face recognition distance validation with invalid values"""
        with self.assertRaises(ValidationError):
            validate_face_recognition_distance(-0.1)

        with self.assertRaises(ValidationError):
            validate_face_recognition_distance(1.1)

        with self.assertRaises(ValidationError):
            validate_face_recognition_distance("not a number")

    def test_validate_geofence_coordinates_valid(self):
        """Test geofence coordinate validation with valid values"""
        lat, lon = validate_geofence_coordinates(40.7128, -74.0060)  # NYC coordinates
        self.assertEqual(lat, 40.7128)
        self.assertEqual(lon, -74.0060)

    def test_validate_geofence_coordinates_boundary_values(self):
        """Test geofence coordinate validation at boundaries"""
        # Valid boundary values
        validate_geofence_coordinates(90.0, 180.0)   # North pole, antimeridian
        validate_geofence_coordinates(-90.0, -180.0) # South pole, antimeridian

    def test_validate_geofence_coordinates_invalid(self):
        """Test geofence coordinate validation with invalid values"""
        # Invalid latitude
        with self.assertRaises(ValidationError):
            validate_geofence_coordinates(91.0, 0.0)

        with self.assertRaises(ValidationError):
            validate_geofence_coordinates(-91.0, 0.0)

        # Invalid longitude
        with self.assertRaises(ValidationError):
            validate_geofence_coordinates(0.0, 181.0)

        with self.assertRaises(ValidationError):
            validate_geofence_coordinates(0.0, -181.0)

        # Non-numeric values
        with self.assertRaises(ValidationError):
            validate_geofence_coordinates("not a number", 0.0)


class TestEdgeCases(TestCase):
    """Test edge cases and error conditions"""

    def test_large_error_logs_array(self):
        """Test handling of very large error logs array"""
        large_logs = [f"Error {i}" for i in range(1000)]
        data = {
            "verified_in": True,
            "distance_in": 0.2,
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine",
            "error_logs": large_logs
        }

        # Should validate successfully (no size limit in schema)
        result = JSONSchemaValidator.validate_json_structure(data)
        self.assertEqual(len(result["error_logs"]), 1000)

    def test_extreme_distance_values(self):
        """Test extreme but valid distance values"""
        data = {
            "verified_in": True,
            "distance_in": 0.0000001,  # Very small but valid
            "verified_out": False,
            "distance_out": 0.9999999,  # Very large but valid
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine"
        }

        result = JSONSchemaValidator.validate_json_structure(data)
        self.assertEqual(result["distance_in"], 0.0000001)
        self.assertEqual(result["distance_out"], 0.9999999)

    def test_unicode_in_error_logs(self):
        """Test unicode characters in error logs"""
        data = {
            "verified_in": True,
            "distance_in": 0.2,
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine",
            "error_logs": ["Error with unicode: 🚨 警告 ⚠️"]
        }

        result = JSONSchemaValidator.validate_json_structure(data)
        self.assertIn("🚨 警告 ⚠️", result["error_logs"][0])


@pytest.mark.performance
class TestValidationPerformance(TestCase):
    """Performance tests for validation operations"""

    def test_large_json_validation_performance(self):
        """Test validation performance with large JSON structures"""
        import time

        # Create large but valid JSON structure
        large_data = {
            "verified_in": True,
            "distance_in": 0.2,
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine",
            "error_logs": [f"Error log entry {i}" for i in range(100)]
        }

        start_time = time.time()
        for _ in range(100):  # Run 100 validations
            JSONSchemaValidator.validate_json_structure(large_data)
        end_time = time.time()

        # Should complete 100 validations in less than 1 second
        self.assertLess(end_time - start_time, 1.0)

    def test_validation_memory_usage(self):
        """Test that validation doesn't cause memory leaks"""
        import gc

        data = {
            "verified_in": True,
            "distance_in": 0.2,
            "verified_out": False,
            "distance_out": None,
            "threshold": "0.3",
            "model": "Facenet512",
            "similarity_metric": "cosine"
        }

        # Force garbage collection before test
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Run many validations
        for _ in range(1000):
            JSONSchemaValidator.validate_json_structure(data)

        # Force garbage collection after test
        gc.collect()
        final_objects = len(gc.get_objects())

        # Object count should not grow significantly (allow 10% increase)
        growth_ratio = final_objects / initial_objects
        self.assertLess(growth_ratio, 1.1, "Memory usage grew too much during validation")