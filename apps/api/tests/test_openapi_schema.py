"""
Tests for OpenAPI Schema Generation

Validates consolidated OpenAPI schema endpoint and content.

Compliance with .claude/rules.md:
- Rule #11: Specific exception testing
- Ensures schema validation and structure
"""

import pytest
import json
from django.test import TestCase, Client, override_settings
from django.urls import reverse


@pytest.mark.integration
class TestOpenAPISchemaGeneration(TestCase):
    """Test OpenAPI schema generation and endpoints."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_schema_json_endpoint_accessible(self):
        """Test /api/schema/swagger.json is publicly accessible."""
        response = self.client.get('/api/schema/swagger.json')

        # Should be accessible without authentication
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.oai.openapi+json')

    def test_schema_yaml_endpoint_accessible(self):
        """Test /api/schema/swagger.yaml is publicly accessible."""
        response = self.client.get('/api/schema/swagger.yaml')

        # Should be accessible without authentication
        self.assertEqual(response.status_code, 200)
        self.assertIn('yaml', response['Content-Type'].lower())

    def test_schema_metadata_endpoint(self):
        """Test /api/schema/metadata/ returns discovery information."""
        response = self.client.get('/api/schema/metadata/')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify metadata structure
        self.assertIn('version', data)
        self.assertIn('endpoints', data)
        self.assertIn('mobile_codegen_supported', data)
        self.assertTrue(data['mobile_codegen_supported'])

    def test_swagger_ui_endpoint(self):
        """Test /api/schema/swagger/ serves Swagger UI."""
        response = self.client.get('/api/schema/swagger/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])

    def test_redoc_ui_endpoint(self):
        """Test /api/schema/redoc/ serves ReDoc UI."""
        response = self.client.get('/api/schema/redoc/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])


@pytest.mark.unit
class TestOpenAPISchemaStructure(TestCase):
    """Test OpenAPI schema content and structure."""

    def setUp(self):
        """Set up test client and fetch schema."""
        self.client = Client()
        response = self.client.get('/api/schema/swagger.json')
        self.schema = response.json()

    def test_schema_has_required_fields(self):
        """Test schema contains required OpenAPI 3.0 fields."""
        required_fields = ['openapi', 'info', 'paths', 'components']
        for field in required_fields:
            self.assertIn(field, self.schema)

    def test_schema_version_is_3_0(self):
        """Test schema uses OpenAPI 3.0.x."""
        openapi_version = self.schema.get('openapi', '')
        self.assertTrue(openapi_version.startswith('3.0'))

    def test_schema_info_section(self):
        """Test schema info section has proper metadata."""
        info = self.schema.get('info', {})

        self.assertIn('title', info)
        self.assertEqual(info['title'], 'YOUTILITY5 Enterprise API')

        self.assertIn('version', info)
        self.assertIn('description', info)
        self.assertIn('contact', info)

    def test_schema_has_v1_endpoints(self):
        """Test schema includes v1 endpoints."""
        paths = self.schema.get('paths', {})

        # Check for v1 sync endpoints
        v1_paths = [path for path in paths.keys() if '/api/v1/' in path]
        self.assertGreater(len(v1_paths), 0, "No v1 endpoints found in schema")

    def test_schema_has_v2_endpoints(self):
        """Test schema includes v2 endpoints."""
        paths = self.schema.get('paths', {})

        # Check for v2 sync endpoints
        v2_paths = [path for path in paths.keys() if '/api/v2/' in path]
        self.assertGreater(len(v2_paths), 0, "No v2 endpoints found in schema")

    def test_schema_has_security_definitions(self):
        """Test schema includes security schemes."""
        components = self.schema.get('components', {})
        security_schemes = components.get('securitySchemes', {})

        # Should have Bearer (JWT) and ApiKey
        self.assertIn('Bearer', security_schemes)
        self.assertIn('ApiKey', security_schemes)

        # Verify Bearer scheme
        bearer = security_schemes['Bearer']
        self.assertEqual(bearer['type'], 'http')
        self.assertEqual(bearer['scheme'], 'bearer')
        self.assertEqual(bearer['bearerFormat'], 'JWT')

    def test_schema_has_mobile_metadata(self):
        """Test schema includes Kotlin codegen metadata (added by postprocessor)."""
        # Check x-kotlin-package extension
        self.assertIn('x-kotlin-package', self.schema)
        self.assertEqual(self.schema['x-kotlin-package'], 'com.youtility.api')

        self.assertIn('x-mobile-compatible', self.schema)
        self.assertTrue(self.schema['x-mobile-compatible'])

    def test_schema_has_idempotency_docs(self):
        """Test schema includes idempotency documentation (added by postprocessor)."""
        components = self.schema.get('components', {})
        idempotency = components.get('x-idempotency', {})

        self.assertTrue(idempotency.get('enabled'))
        self.assertEqual(idempotency.get('ttl_hours'), 24)
        self.assertEqual(idempotency.get('header_name'), 'Idempotency-Key')

    def test_schema_has_tags(self):
        """Test schema includes organized tags."""
        tags = self.schema.get('tags', [])

        tag_names = [tag['name'] for tag in tags]
        expected_tags = ['Authentication', 'Mobile Sync', 'Tasks', 'Assets']

        for expected in expected_tags:
            self.assertIn(expected, tag_names)

    def test_voice_sync_endpoint_documented(self):
        """Test VoiceSyncView is documented in schema."""
        paths = self.schema.get('paths', {})

        # Find v2 voice sync endpoint
        voice_sync_paths = [
            path for path in paths.keys()
            if 'voice' in path.lower() and '/api/v2/' in path
        ]

        self.assertGreater(len(voice_sync_paths), 0, "Voice sync endpoint not documented")

        # Verify POST method exists
        for path in voice_sync_paths:
            methods = paths[path]
            self.assertIn('post', methods, f"POST method missing for {path}")

    def test_batch_sync_endpoint_documented(self):
        """Test BatchSyncView is documented in schema."""
        paths = self.schema.get('paths', {})

        # Find v2 batch sync endpoint
        batch_sync_paths = [
            path for path in paths.keys()
            if 'batch' in path.lower() and '/api/v2/' in path
        ]

        self.assertGreater(len(batch_sync_paths), 0, "Batch sync endpoint not documented")

    def test_request_body_has_pydantic_validation(self):
        """Test request bodies include Pydantic validation rules."""
        paths = self.schema.get('paths', {})

        # Find a v2 endpoint with request body
        for path, methods in paths.items():
            if '/api/v2/sync/voice/' in path and 'post' in methods:
                operation = methods['post']
                request_body = operation.get('requestBody', {})
                content = request_body.get('content', {})
                json_content = content.get('application/json', {})
                schema_ref = json_content.get('schema', {})

                # Should have schema definition
                self.assertTrue(
                    '$ref' in schema_ref or 'properties' in schema_ref,
                    "Request body missing schema"
                )
                break


@pytest.mark.unit
class TestV2EndpointSchemaValidation(TestCase):
    """Test that all v2 endpoints are properly documented in OpenAPI schema."""

    def setUp(self):
        """Set up test client and fetch schema."""
        self.client = Client()
        response = self.client.get('/api/schema/swagger.json')
        self.schema = response.json()
        self.paths = self.schema.get('paths', {})

    def test_all_v2_sync_endpoints_documented(self):
        """Test all v2 sync endpoints are in OpenAPI schema."""
        expected_v2_endpoints = [
            '/api/v2/sync/voice/',
            '/api/v2/sync/batch/',
        ]

        for endpoint in expected_v2_endpoints:
            self.assertIn(endpoint, self.paths, f"Missing v2 endpoint: {endpoint}")

    def test_all_v2_device_endpoints_documented(self):
        """Test all v2 device endpoints are in OpenAPI schema."""
        expected_device_endpoints = [
            '/api/v2/devices/',
            '/api/v2/devices/register/',
        ]

        for endpoint in expected_device_endpoints:
            self.assertIn(endpoint, self.paths, f"Missing device endpoint: {endpoint}")

    def test_v2_voice_sync_has_request_schema(self):
        """Test v2 voice sync endpoint has proper request schema."""
        voice_sync_path = '/api/v2/sync/voice/'
        self.assertIn(voice_sync_path, self.paths)

        operation = self.paths[voice_sync_path].get('post', {})
        request_body = operation.get('requestBody', {})

        # Should have request body
        self.assertIn('content', request_body)
        self.assertIn('application/json', request_body['content'])

        # Should have schema
        schema = request_body['content']['application/json'].get('schema', {})
        self.assertTrue('$ref' in schema or 'properties' in schema)

    def test_v2_voice_sync_has_response_schema(self):
        """Test v2 voice sync endpoint has proper response schema."""
        voice_sync_path = '/api/v2/sync/voice/'
        self.assertIn(voice_sync_path, self.paths)

        operation = self.paths[voice_sync_path].get('post', {})
        responses = operation.get('responses', {})

        # Should have 200 response
        self.assertIn('200', responses)

        # Should have response schema
        response_200 = responses['200']
        content = response_200.get('content', {})
        self.assertIn('application/json', content)

    def test_v2_device_register_has_request_schema(self):
        """Test v2 device register endpoint has proper request schema."""
        register_path = '/api/v2/devices/register/'
        self.assertIn(register_path, self.paths)

        operation = self.paths[register_path].get('post', {})
        request_body = operation.get('requestBody', {})

        # Should have request body
        self.assertIn('content', request_body)
        self.assertIn('application/json', request_body['content'])

    def test_v2_endpoints_require_authentication(self):
        """Test v2 endpoints specify authentication requirement."""
        v2_paths = [path for path in self.paths.keys() if '/api/v2/' in path]

        for path in v2_paths:
            # Skip version endpoint (public)
            if 'version' in path.lower():
                continue

            methods = self.paths[path]
            for method, operation in methods.items():
                if isinstance(operation, dict):
                    # Should have security requirement or be marked as public
                    has_security = 'security' in operation or 'security' in self.schema
                    self.assertTrue(
                        has_security,
                        f"Endpoint {method.upper()} {path} missing security definition"
                    )

    def test_v2_endpoints_have_tags(self):
        """Test v2 endpoints are properly tagged for organization."""
        v2_paths = [path for path in self.paths.keys() if '/api/v2/' in path]

        for path in v2_paths:
            methods = self.paths[path]
            for method, operation in methods.items():
                if isinstance(operation, dict):
                    self.assertIn(
                        'tags',
                        operation,
                        f"Endpoint {method.upper()} {path} missing tags"
                    )


@pytest.mark.unit
class TestSchemaGeneration(TestCase):
    """Test schema generation utilities and management commands."""

    def test_spectacular_command_available(self):
        """Test manage.py spectacular command is available."""
        from django.core.management import call_command
        import tempfile
        import os

        # Generate schema to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            call_command('spectacular', '--file', temp_path, '--validate')
            self.assertTrue(os.path.exists(temp_path))
            self.assertGreater(os.path.getsize(temp_path), 100)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
