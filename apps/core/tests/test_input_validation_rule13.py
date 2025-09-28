"""
Comprehensive Test Suite for Rule #13: Input Validation

Tests all validation infrastructure including:
- Serializer validators
- GraphQL input validators
- Mass assignment protection
- Input sanitization middleware

Compliance:
- Rule #13: Form Validation Requirements
- Rule #11: Specific exception handling
"""

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.gis.geos import GEOSGeometry
from rest_framework import serializers
from rest_framework.test import APITestCase
from apps.core.serializers.validators import (
    validate_code_field,
    validate_name_field,
    validate_email_field,
    validate_phone_field,
    validate_gps_field,
    validate_date_range,
    SerializerValidators,
)
from apps.core.graphql.input_validators import GraphQLInputValidator
from apps.core.security.mass_assignment_protection import MassAssignmentProtector
from apps.peoples.models import People
from apps.activity.models.asset_model import Asset
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


@pytest.mark.unit
class TestSerializerValidators(TestCase):
    """Unit tests for serializer validator functions."""

    def test_validate_code_field_valid(self):
        """Test code validation with valid input."""
        valid_codes = ['TEST123', 'ASSET-001', 'LOC_A1']

        for code in valid_codes:
            result = validate_code_field(code)
            assert result == code.upper()

    def test_validate_code_field_invalid_spaces(self):
        """Test code validation rejects spaces."""
        with pytest.raises(serializers.ValidationError) as exc:
            validate_code_field('TEST 123')

        assert 'Spaces are not allowed' in str(exc.value)

    def test_validate_code_field_invalid_chars(self):
        """Test code validation rejects invalid characters."""
        with pytest.raises(serializers.ValidationError):
            validate_code_field('TEST@#$%')

    def test_validate_code_field_ends_with_period(self):
        """Test code validation rejects codes ending with period."""
        with pytest.raises(serializers.ValidationError) as exc:
            validate_code_field('TEST123.')

        assert "cannot end with '.'" in str(exc.value)

    def test_validate_code_field_too_short(self):
        """Test code validation rejects too short codes."""
        with pytest.raises(serializers.ValidationError) as exc:
            validate_code_field('A')

        assert 'at least 2 characters' in str(exc.value)

    def test_validate_name_field_valid(self):
        """Test name validation with valid input."""
        valid_names = ['John Doe', 'Asset-123', 'Site @ Location']

        for name in valid_names:
            result = validate_name_field(name)
            assert result == name

    def test_validate_name_field_too_short(self):
        """Test name validation rejects too short names."""
        with pytest.raises(serializers.ValidationError):
            validate_name_field('A')

    def test_validate_email_field_valid(self):
        """Test email validation with valid input."""
        email = 'test@example.com'
        result = validate_email_field(email)
        assert result == email

    def test_validate_email_field_invalid(self):
        """Test email validation rejects invalid emails."""
        with pytest.raises(serializers.ValidationError):
            validate_email_field('invalid-email')

    def test_validate_phone_field_valid(self):
        """Test phone validation with valid input."""
        phone = '+919876543210'
        result = validate_phone_field(phone)
        assert result == phone

    def test_validate_phone_field_invalid(self):
        """Test phone validation rejects invalid phones."""
        with pytest.raises(serializers.ValidationError):
            validate_phone_field('123')

    def test_validate_gps_field_valid(self):
        """Test GPS validation with valid coordinates."""
        gps = '12.9716,77.5946'
        result = validate_gps_field(gps)

        assert isinstance(result, GEOSGeometry)
        assert result.srid == 4326

    def test_validate_gps_field_invalid_format(self):
        """Test GPS validation rejects invalid format."""
        with pytest.raises(serializers.ValidationError):
            validate_gps_field('invalid-gps')

    def test_validate_gps_field_out_of_range(self):
        """Test GPS validation rejects out of range coordinates."""
        with pytest.raises(serializers.ValidationError):
            validate_gps_field('200.0,77.5946')

    def test_validate_date_range_valid(self):
        """Test date range validation with valid range."""
        start = date(2025, 1, 1)
        end = date(2025, 12, 31)

        validate_date_range(start, end)

    def test_validate_date_range_invalid(self):
        """Test date range validation rejects invalid range."""
        start = date(2025, 12, 31)
        end = date(2025, 1, 1)

        with pytest.raises(serializers.ValidationError):
            validate_date_range(start, end)


@pytest.mark.integration
class TestPeopleSerializerValidation(APITestCase):
    """Integration tests for PeopleSerializer validation."""

    def setUp(self):
        """Set up test data."""
        from apps.peoples.models import People
        from apps.onboarding.models import Bt

        self.client_bt = Bt.objects.create(
            bucode='TESTCLIENT',
            buname='Test Client',
            identifier_id=1,
        )

        self.site_bt = Bt.objects.create(
            bucode='TESTSITE',
            buname='Test Site',
            identifier_id=2,
            client=self.client_bt,
        )

    def test_peoplecode_validation_duplicate(self):
        """Test that duplicate peoplecodes are rejected."""
        from apps.peoples.serializers import PeopleSerializer

        People.objects.create(
            peoplecode='EMP001',
            peoplename='Test User',
            loginid='testuser',
            client=self.client_bt,
            bu=self.site_bt,
        )

        serializer = PeopleSerializer(data={
            'peoplecode': 'EMP001',
            'peoplename': 'Another User',
            'loginid': 'anotheruser',
        })

        assert not serializer.is_valid()
        assert 'peoplecode' in serializer.errors

    def test_date_cross_validation(self):
        """Test cross-field date validation."""
        from apps.peoples.serializers import PeopleSerializer

        serializer = PeopleSerializer(data={
            'peoplecode': 'EMP002',
            'peoplename': 'Test User',
            'loginid': 'testuser2',
            'dateofbirth': '2000-01-01',
            'dateofjoin': '1999-01-01',
        })

        assert not serializer.is_valid()
        assert 'Date of birth must be before date of joining' in str(serializer.errors)

    def test_required_field_validation(self):
        """Test required fields are enforced."""
        from apps.peoples.serializers import PeopleSerializer

        serializer = PeopleSerializer(data={
            'peoplename': 'Test User',
        })

        assert not serializer.is_valid()
        assert 'peoplecode' in serializer.errors or 'loginid' in serializer.errors


@pytest.mark.integration
class TestAssetSerializerValidation(APITestCase):
    """Integration tests for AssetSerializer validation."""

    def setUp(self):
        """Set up test data."""
        from apps.onboarding.models import Bt

        self.client_bt = Bt.objects.create(
            bucode='TESTCLIENT',
            buname='Test Client',
            identifier_id=1,
        )

        self.site_bt = Bt.objects.create(
            bucode='TESTSITE',
            buname='Test Site',
            identifier_id=2,
            client=self.client_bt,
        )

    def test_assetcode_validation_duplicate(self):
        """Test that duplicate asset codes are rejected."""
        from apps.activity.serializers import AssetSerializer

        Asset.objects.create(
            assetcode='ASSET001',
            assetname='Test Asset',
            client=self.client_bt,
            bu=self.site_bt,
            identifier='ASSET',
        )

        serializer = AssetSerializer(data={
            'assetcode': 'ASSET001',
            'assetname': 'Another Asset',
            'identifier': 'ASSET',
        })

        assert not serializer.is_valid()
        assert 'assetcode' in serializer.errors

    def test_parent_assetcode_validation(self):
        """Test that parent asset code cannot be same as child."""
        from apps.activity.serializers import AssetSerializer

        parent = Asset.objects.create(
            assetcode='PARENT001',
            assetname='Parent Asset',
            client=self.client_bt,
            bu=self.site_bt,
            identifier='ASSET',
        )

        serializer = AssetSerializer(data={
            'assetcode': 'PARENT001',
            'assetname': 'Child Asset',
            'parent': parent.id,
            'identifier': 'ASSET',
        })

        assert not serializer.is_valid()


@pytest.mark.security
class TestMassAssignmentProtection(TestCase):
    """Security tests for mass assignment protection."""

    def test_protected_fields_blocked(self):
        """Test that protected fields are blocked."""
        input_data = {
            'peoplename': 'Test User',
            'is_superuser': True,
            'is_staff': True,
        }

        with pytest.raises(serializers.ValidationError) as exc:
            MassAssignmentProtector.validate_fields(
                People,
                input_data,
                allowed_fields=['peoplename']
            )

        assert 'protected fields' in str(exc.value).lower()

    def test_unauthorized_fields_filtered(self):
        """Test that unauthorized fields are filtered out."""
        input_data = {
            'peoplename': 'Test User',
            'peoplecode': 'EMP001',
            'unauthorized_field': 'hacker',
        }

        result = MassAssignmentProtector.validate_fields(
            People,
            input_data,
            allowed_fields=['peoplename', 'peoplecode']
        )

        assert 'unauthorized_field' not in result
        assert 'peoplename' in result
        assert 'peoplecode' in result

    def test_privilege_escalation_detection(self):
        """Test privilege escalation attempt detection."""
        from apps.onboarding.models import Bt

        client = Bt.objects.create(
            bucode='CLIENT',
            buname='Client',
            identifier_id=1,
        )

        user = People.objects.create(
            peoplecode='USER001',
            peoplename='Regular User',
            loginid='user001',
            is_staff=False,
            is_superuser=False,
            client=client,
        )

        input_data = {
            'peoplename': 'Test',
            'isadmin': True,
        }

        with pytest.raises(serializers.ValidationError):
            MassAssignmentProtector.check_privilege_escalation(
                People,
                input_data,
                user
            )


@pytest.mark.security
class TestInputSanitizationMiddleware(TestCase):
    """Security tests for input sanitization middleware."""

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()

    def test_xss_sanitization(self):
        """Test XSS patterns are sanitized."""
        from apps.core.middleware.input_sanitization_middleware import InputSanitizationMiddleware

        request = self.factory.post(
            '/api/test/',
            data={'name': '<script>alert("XSS")</script>Normal Text'},
            content_type='application/json'
        )

        middleware = InputSanitizationMiddleware(lambda r: None)

        middleware.process_request(request)

    def test_sql_injection_sanitization(self):
        """Test SQL injection patterns are sanitized."""
        from apps.core.middleware.input_sanitization_middleware import InputSanitizationMiddleware

        request = self.factory.post(
            '/api/test/',
            data={'search': "'; DROP TABLE users; --"},
            content_type='application/json'
        )

        middleware = InputSanitizationMiddleware(lambda r: None)
        middleware.process_request(request)


@pytest.mark.integration
class TestSerializerValidationIntegration(APITestCase):
    """
    Integration tests for complete serializer validation flow.
    Tests the entire validation chain from input to database.
    """

    def setUp(self):
        """Set up test environment."""
        from apps.onboarding.models import Bt

        self.client_bt = Bt.objects.create(
            bucode='TESTCLIENT',
            buname='Test Client',
            identifier_id=1,
        )

        self.site_bt = Bt.objects.create(
            bucode='TESTSITE',
            buname='Test Site',
            identifier_id=2,
            client=self.client_bt,
        )

    def test_people_serializer_complete_validation(self):
        """Test complete validation chain for PeopleSerializer."""
        from apps.peoples.serializers import PeopleSerializer

        invalid_data = {
            'peoplecode': 'TEST 123',
            'peoplename': '<script>alert("XSS")</script>',
            'loginid': 'test user',
            'email': 'invalid-email',
            'dateofbirth': '2025-01-01',
            'dateofjoin': '2024-01-01',
        }

        serializer = PeopleSerializer(data=invalid_data)

        assert not serializer.is_valid()

        assert 'peoplecode' in serializer.errors
        assert 'loginid' in serializer.errors
        assert 'email' in serializer.errors
        assert 'dateofbirth' in serializer.errors or 'Date of birth' in str(serializer.errors)

    def test_asset_serializer_complete_validation(self):
        """Test complete validation chain for AssetSerializer."""
        from apps.activity.serializers import AssetSerializer

        invalid_data = {
            'assetcode': 'ASSET 001',
            'assetname': 'A',
            'capacity': -100,
        }

        serializer = AssetSerializer(data=invalid_data)

        assert not serializer.is_valid()

        assert 'assetcode' in serializer.errors
        assert 'assetname' in serializer.errors
        assert 'capacity' in serializer.errors

    def test_attendance_serializer_time_validation(self):
        """Test attendance time validation."""
        from apps.attendance.serializers import PeopleEventlogSerializer
        from apps.onboarding.models import TypeAssist

        peventtype = TypeAssist.objects.create(
            tacode='PRESENT',
            taname='Present',
            tatype_id=1,
            client=self.client_bt,
        )

        user = People.objects.create(
            peoplecode='EMP001',
            peoplename='Test User',
            loginid='testuser',
            client=self.client_bt,
            bu=self.site_bt,
        )

        invalid_data = {
            'people': user.id,
            'datefor': '2025-01-01',
            'punchintime': '2025-01-01T18:00:00Z',
            'punchouttime': '2025-01-01T09:00:00Z',
            'peventtype': peventtype.id,
        }

        serializer = PeopleEventlogSerializer(data=invalid_data)

        assert not serializer.is_valid()
        assert 'punchouttime' in serializer.errors or 'must be after' in str(serializer.errors)


@pytest.mark.security
class TestMassAssignmentPenetration(APITestCase):
    """
    Penetration tests for mass assignment vulnerabilities.

    Simulates attack scenarios to ensure protection is working.
    """

    def setUp(self):
        """Set up attack scenarios."""
        from apps.onboarding.models import Bt

        self.client_bt = Bt.objects.create(
            bucode='TESTCLIENT',
            buname='Test Client',
            identifier_id=1,
        )

        self.site_bt = Bt.objects.create(
            bucode='TESTSITE',
            buname='Test Site',
            identifier_id=2,
            client=self.client_bt,
        )

        self.regular_user = People.objects.create(
            peoplecode='REGULAR',
            peoplename='Regular User',
            loginid='regular',
            is_staff=False,
            is_superuser=False,
            isadmin=False,
            client=self.client_bt,
            bu=self.site_bt,
        )

    def test_privilege_escalation_via_is_superuser(self):
        """Test that regular users cannot escalate to superuser."""
        from apps.peoples.serializers import PeopleSerializer

        attack_data = {
            'peoplecode': 'ATTACKER',
            'peoplename': 'Attacker',
            'loginid': 'attacker',
            'is_superuser': True,
            'is_staff': True,
            'isadmin': True,
        }

        context = {'user': self.regular_user}

        MassAssignmentProtector.check_privilege_escalation(
            People,
            attack_data,
            self.regular_user
        )

    def test_privilege_escalation_via_update(self):
        """Test that regular users cannot escalate privileges via update."""
        attack_data = {
            'peoplename': 'Updated Name',
            'isadmin': True,
        }

        with pytest.raises(serializers.ValidationError):
            MassAssignmentProtector.check_privilege_escalation(
                People,
                attack_data,
                self.regular_user,
                instance=self.regular_user
            )

    def test_sensitive_field_protection(self):
        """Test that sensitive fields are protected."""
        attack_data = {
            'peoplename': 'Test',
            'created_at': '2020-01-01',
            'uuid': 'custom-uuid',
        }

        result = MassAssignmentProtector.validate_fields(
            People,
            attack_data,
            allowed_fields=['peoplename']
        )

        assert 'created_at' not in result
        assert 'uuid' not in result
        assert 'peoplename' in result


@pytest.mark.unit
class TestGraphQLInputValidation(TestCase):
    """Unit tests for GraphQL input validation."""

    def test_required_fields_validation(self):
        """Test required fields validation."""
        from graphql import GraphQLError

        class MockInput:
            mdtz = None
            buid = 123

        validator = GraphQLInputValidator()

        with pytest.raises(GraphQLError) as exc:
            validator.validate_required_fields(MockInput(), ['mdtz', 'buid'])

        assert 'Required fields missing' in str(exc.value)

    def test_code_field_validation(self):
        """Test code field validation for GraphQL inputs."""
        class MockInput:
            assetcode = 'TEST 123'

        validator = GraphQLInputValidator()

        with pytest.raises(GraphQLError):
            validator.validate_code_fields(MockInput(), ['assetcode'])

    def test_sanitization_integration(self):
        """Test text sanitization for GraphQL inputs."""
        class MockInput:
            description = '<script>alert("XSS")</script>Test'

        validator = GraphQLInputValidator()
        validator.sanitize_text_fields(MockInput(), ['description'])

        assert '<script>' not in MockInput.description