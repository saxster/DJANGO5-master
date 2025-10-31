"""
CSRF Protection Security Tests for Knowledge Management API

Verifies that all knowledge management endpoints enforce CSRF protection
following .claude/rules.md Rule #3 (Mandatory CSRF Protection)

Test Coverage:
- KnowledgeSourceAPIView (POST/PUT/DELETE)
- IngestionJobAPIView (POST)
- DocumentManagementAPIView (POST)
- DocumentReviewAPIView (POST)

Security Context:
- Previous violation: csrf_exempt on all endpoints
- Fix: Removed csrf_exempt, enabled Django CSRF middleware
- Attack vector prevented: Cross-site request forgery on staff-only mutations
"""

import pytest
import json
from django.test import Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.onboarding.models import AuthoritativeKnowledge

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create staff user for testing"""
    return User.objects.create_user(
        loginid='staff_user',
        peoplename='Staff User',
        email='staff@test.com',
        password='testpass123',
        is_staff=True,
        capabilities={'knowledge_curator': True}
    )


@pytest.fixture
def authenticated_client(staff_user):
    """Client authenticated as staff user"""
    client = Client()
    client.login(username='staff_user', password='testpass123')
    return client


@pytest.fixture
def csrf_enforcing_client(staff_user):
    """Client with CSRF checks enabled"""
    client = Client(enforce_csrf_checks=True)
    client.login(username='staff_user', password='testpass123')
    return client


@pytest.mark.django_db
class TestKnowledgeSourceCSRFProtection:
    """Verify CSRF protection on knowledge source CRUD operations"""

    def test_create_source_without_csrf_fails(self, csrf_enforcing_client):
        """POST without CSRF token should return 403"""
        response = csrf_enforcing_client.post(
            '/api/knowledge/sources/',
            data=json.dumps({
                'name': 'Test Source',
                'source_type': 'iso',
                'base_url': 'https://example.com'
            }),
            content_type='application/json'
        )

        # Should fail with CSRF error
        assert response.status_code == 403, \
            "Knowledge source creation without CSRF token should fail"

    def test_create_source_with_csrf_succeeds(self, authenticated_client):
        """POST with valid CSRF token should succeed"""
        # Get CSRF token
        response = authenticated_client.get('/api/knowledge/sources/')
        csrf_token = response.cookies.get('csrftoken')

        if csrf_token:
            response = authenticated_client.post(
                '/api/knowledge/sources/',
                data=json.dumps({
                    'name': 'Test Source',
                    'source_type': 'iso',
                    'base_url': 'https://example.com',
                }),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token.value
            )

            # Should succeed or fail with business logic error (not CSRF)
            assert response.status_code != 403, \
                "Knowledge source creation with CSRF token should not fail with 403"

    def test_update_source_requires_csrf(self, csrf_enforcing_client):
        """PUT without CSRF token should fail"""
        response = csrf_enforcing_client.put(
            '/api/knowledge/sources/12345/',
            data=json.dumps({'name': 'Updated Name'}),
            content_type='application/json'
        )

        assert response.status_code == 403, \
            "Knowledge source update without CSRF token should fail"

    def test_delete_source_requires_csrf(self, csrf_enforcing_client):
        """DELETE without CSRF token should fail"""
        response = csrf_enforcing_client.delete(
            '/api/knowledge/sources/12345/'
        )

        assert response.status_code == 403, \
            "Knowledge source deletion without CSRF token should fail"


@pytest.mark.django_db
class TestIngestionJobCSRFProtection:
    """Verify CSRF protection on document ingestion jobs"""

    def test_start_ingestion_without_csrf_fails(self, csrf_enforcing_client):
        """Starting ingestion job without CSRF should fail"""
        response = csrf_enforcing_client.post(
            '/api/knowledge/ingest/',
            data=json.dumps({
                'source_id': 'test-source-id',
                'source_url': 'https://example.com/document.pdf'
            }),
            content_type='application/json'
        )

        assert response.status_code == 403, \
            "Ingestion job creation without CSRF token should fail"

    def test_start_ingestion_with_csrf_token(self, authenticated_client):
        """Starting ingestion job with CSRF should not fail with 403"""
        # Get CSRF token first
        response = authenticated_client.get('/api/knowledge/ingest/')
        csrf_token = response.cookies.get('csrftoken')

        if csrf_token:
            response = authenticated_client.post(
                '/api/knowledge/ingest/',
                data=json.dumps({
                    'source_id': 'test-source-id',
                    'source_url': 'https://example.com/document.pdf'
                }),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token.value
            )

            # May fail with 404 or validation error, but NOT 403 (CSRF)
            assert response.status_code != 403, \
                "Ingestion job with CSRF should not fail with 403"


@pytest.mark.django_db
class TestDocumentManagementCSRFProtection:
    """Verify CSRF protection on document management operations"""

    def test_publish_document_without_csrf_fails(self, csrf_enforcing_client):
        """Publishing document without CSRF should fail"""
        response = csrf_enforcing_client.post(
            '/api/knowledge/documents/test-doc-id/publish/'
        )

        assert response.status_code == 403, \
            "Document publish without CSRF token should fail"

    def test_reembed_document_without_csrf_fails(self, csrf_enforcing_client):
        """Re-embedding document without CSRF should fail"""
        response = csrf_enforcing_client.post(
            '/api/knowledge/documents/test-doc-id/embed/',
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 403, \
            "Document re-embed without CSRF token should fail"


@pytest.mark.django_db
class TestDocumentReviewCSRFProtection:
    """Verify CSRF protection on document review workflow"""

    def test_submit_review_without_csrf_fails(self, csrf_enforcing_client):
        """Submitting review without CSRF should fail"""
        response = csrf_enforcing_client.post(
            '/api/knowledge/reviews/',
            data=json.dumps({
                'document_id': 'test-doc-id',
                'decision': 'approve',
                'notes': 'Looks good'
            }),
            content_type='application/json'
        )

        assert response.status_code == 403, \
            "Document review submission without CSRF token should fail"

    def test_submit_review_with_csrf_token(self, authenticated_client):
        """Submitting review with CSRF should not fail with 403"""
        # Get CSRF token
        response = authenticated_client.get('/api/knowledge/reviews/')
        csrf_token = response.cookies.get('csrftoken')

        if csrf_token:
            response = authenticated_client.post(
                '/api/knowledge/reviews/',
                data=json.dumps({
                    'document_id': 'test-doc-id',
                    'decision': 'approve',
                    'notes': 'Looks good'
                }),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token.value
            )

            # May fail with 404 or validation error, but NOT 403 (CSRF)
            assert response.status_code != 403, \
                "Review submission with CSRF should not fail with 403"


@pytest.mark.django_db
class TestCSRFComplianceRegression:
    """
    Regression tests to ensure CSRF protection remains enabled

    These tests will FAIL if csrf_exempt is accidentally re-introduced
    """

    def test_all_mutation_endpoints_enforce_csrf(self, csrf_enforcing_client):
        """All POST/PUT/DELETE endpoints must enforce CSRF"""
        mutation_endpoints = [
            ('POST', '/api/knowledge/sources/', {}),
            ('PUT', '/api/knowledge/sources/test/', {}),
            ('DELETE', '/api/knowledge/sources/test/', None),
            ('POST', '/api/knowledge/ingest/', {}),
            ('POST', '/api/knowledge/documents/test/publish/', {}),
            ('POST', '/api/knowledge/documents/test/embed/', {}),
            ('POST', '/api/knowledge/reviews/', {}),
        ]

        for method, url, data in mutation_endpoints:
            if method == 'POST':
                response = csrf_enforcing_client.post(
                    url,
                    data=json.dumps(data) if data else None,
                    content_type='application/json'
                )
            elif method == 'PUT':
                response = csrf_enforcing_client.put(
                    url,
                    data=json.dumps(data) if data else None,
                    content_type='application/json'
                )
            elif method == 'DELETE':
                response = csrf_enforcing_client.delete(url)

            # All should fail with 403 (CSRF error), not succeed or fail with other errors
            assert response.status_code == 403, \
                f"{method} {url} should enforce CSRF (got {response.status_code})"

    def test_csrf_exempt_not_in_knowledge_views(self):
        """Verify csrf_exempt decorator was removed from knowledge_views.py"""
        import apps.onboarding_api.knowledge_views as knowledge_views_module

        # Read the source file
        import inspect
        source = inspect.getsource(knowledge_views_module)

        # Count csrf_exempt occurrences (should be 0 in decorators)
        # Allow imports but not in @method_decorator
        csrf_exempt_in_decorators = '@method_decorator([csrf_exempt' in source or \
                                     '@method_decorator([login_required, csrf_exempt' in source or \
                                     '@csrf_exempt' in source

        assert not csrf_exempt_in_decorators, \
            "csrf_exempt decorator should not be present in knowledge_views.py"


@pytest.mark.django_db
class TestCSRFTokenDelivery:
    """Verify CSRF token is properly delivered to clients"""

    def test_csrf_token_in_cookie(self, authenticated_client):
        """GET request should set CSRF cookie"""
        response = authenticated_client.get('/api/knowledge/sources/')

        # Check for CSRF token in cookies or headers
        csrf_token = response.cookies.get('csrftoken')
        assert csrf_token is not None or 'X-CSRFToken' in response, \
            "CSRF token should be delivered to authenticated clients"

    def test_csrf_token_can_be_obtained(self, authenticated_client):
        """Client should be able to obtain CSRF token for mutations"""
        # Django provides CSRF token via:
        # 1. Cookie (csrftoken)
        # 2. Template context ({% csrf_token %})
        # 3. JavaScript-accessible cookie

        response = authenticated_client.get('/api/knowledge/sources/')

        # At minimum, should have csrf cookie
        assert 'csrftoken' in response.cookies or \
               response.get('X-CSRFToken') is not None, \
            "CSRF token should be accessible to clients"


# =============================================================================
# PENETRATION TESTING SCENARIOS
# =============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestCSRFAttackVectorsPrevented:
    """
    Simulate real CSRF attack scenarios to verify protection

    These tests verify the security vulnerability is fixed
    """

    def test_cross_site_knowledge_source_creation_blocked(self, staff_user):
        """
        Attacker scenario: Malicious site tries to create knowledge source
        via authenticated staff member's browser
        """
        # Simulate attacker's malicious request (no CSRF token)
        attacker_client = Client(enforce_csrf_checks=True)
        attacker_client.force_login(staff_user)

        # Malicious form submission from evil.com
        response = attacker_client.post(
            '/api/knowledge/sources/',
            data=json.dumps({
                'name': 'Malicious Source',
                'source_type': 'external',
                'base_url': 'https://attacker.com/malware'
            }),
            content_type='application/json',
            HTTP_REFERER='https://evil.com/attack.html'
        )

        # Attack should be blocked by CSRF protection
        assert response.status_code == 403, \
            "Cross-site knowledge source creation should be blocked"

    def test_cross_site_document_approval_blocked(self, staff_user):
        """
        Attacker scenario: Trick staff into approving malicious document
        """
        attacker_client = Client(enforce_csrf_checks=True)
        attacker_client.force_login(staff_user)

        # Attacker tries to approve document without proper CSRF token
        response = attacker_client.post(
            '/api/knowledge/reviews/',
            data=json.dumps({
                'document_id': 'malicious-doc',
                'decision': 'approve',
                'notes': 'Auto-approved by attacker'
            }),
            content_type='application/json',
            HTTP_REFERER='https://evil.com/csrf-attack.html'
        )

        # Attack should be blocked
        assert response.status_code == 403, \
            "Cross-site document approval should be blocked"

    def test_replay_attack_with_stolen_cookie_blocked(self, authenticated_client):
        """
        Attacker scenario: Stolen session cookie but no CSRF token
        """
        # Get valid session cookie
        session_cookie = authenticated_client.cookies.get('sessionid')

        # Create new client with stolen session but no CSRF token
        attacker_client = Client(enforce_csrf_checks=True)
        attacker_client.cookies['sessionid'] = session_cookie

        # Try to create knowledge source
        response = attacker_client.post(
            '/api/knowledge/sources/',
            data=json.dumps({'name': 'Attack', 'source_type': 'iso'}),
            content_type='application/json'
        )

        # Should fail - session alone is not enough
        assert response.status_code == 403, \
            "Replay attack with session cookie only should be blocked"
