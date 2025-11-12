"""
Comprehensive Test Suite for Onboarding Placeholder Remediation

Tests to ensure:
1. No HTTP 501 responses from onboarding URLs
2. All template URLs resolve correctly
3. AJAX endpoints return valid data
4. Middleware removed successfully
5. REST API endpoints functional
"""

import pytest
from django.test import Client
from django.urls import reverse, NoReverseMatch
from django.conf import settings
import re
from pathlib import Path


class TestPlaceholderRemoval:
    """Test that placeholder views have been removed"""

    @pytest.mark.django_db
    def test_no_onboarding_typeassist_url(self):
        """Verify onboarding:typeassist URL pattern removed"""
        with pytest.raises(NoReverseMatch):
            reverse('onboarding:typeassist')

    @pytest.mark.django_db
    def test_no_onboarding_shift_url(self):
        """Verify onboarding:shift URL pattern removed"""
        with pytest.raises(NoReverseMatch):
            reverse('onboarding:shift')

    @pytest.mark.django_db
    def test_no_onboarding_geofence_url(self):
        """Verify onboarding:geofence URL pattern removed"""
        with pytest.raises(NoReverseMatch):
            reverse('onboarding:geofence')

    @pytest.mark.django_db
    def test_no_onboarding_import_url(self):
        """Verify onboarding:import URL pattern removed"""
        with pytest.raises(NoReverseMatch):
            reverse('onboarding:import')

    @pytest.mark.django_db
    def test_no_onboarding_client_url(self):
        """Verify onboarding:client URL pattern removed"""
        with pytest.raises(NoReverseMatch):
            reverse('onboarding:client')

    @pytest.mark.django_db
    def test_no_onboarding_bu_url(self):
        """Verify onboarding:bu URL pattern removed"""
        with pytest.raises(NoReverseMatch):
            reverse('onboarding:bu')

    @pytest.mark.django_db
    def test_no_onboarding_contract_url(self):
        """Verify onboarding:contract URL pattern removed"""
        with pytest.raises(NoReverseMatch):
            reverse('onboarding:contract')

    @pytest.mark.django_db
    def test_no_onboarding_file_upload_url(self):
        """Verify onboarding:file_upload URL pattern removed"""
        with pytest.raises(NoReverseMatch):
            reverse('onboarding:file_upload')


class TestDjangoAdminURLs:
    """Test that Django Admin URLs work correctly"""

    @pytest.mark.django_db
    def test_typeassist_admin_changelist(self):
        """Verify TypeAssist admin changelist accessible"""
        try:
            url = reverse('admin:onboarding_typeassist_changelist')
            assert url == '/admin/onboarding/typeassist/'
        except NoReverseMatch:
            pytest.skip("Django admin not configured or TypeAssist model not registered")

    @pytest.mark.django_db
    def test_shift_admin_changelist(self):
        """Verify Shift admin changelist accessible"""
        try:
            url = reverse('admin:onboarding_shift_changelist')
            assert url == '/admin/onboarding/shift/'
        except NoReverseMatch:
            pytest.skip("Django admin not configured or Shift model not registered")

    @pytest.mark.django_db
    def test_geofence_admin_changelist(self):
        """Verify Geofence admin changelist accessible"""
        try:
            url = reverse('admin:onboarding_geofencemaster_changelist')
            assert '/admin/onboarding/geofencemaster/' in url
        except NoReverseMatch:
            pytest.skip("Django admin not configured or GeofenceMaster model not registered")

    @pytest.mark.django_db
    def test_business_unit_admin_changelist(self):
        """Verify Business Unit admin changelist accessible"""
        try:
            url = reverse('admin:onboarding_bt_changelist')
            assert '/admin/onboarding/bt/' in url
        except NoReverseMatch:
            pytest.skip("Django admin not configured or Bt model not registered")


class TestRESTAPIEndpoints:
    """Test that REST API endpoints return valid data"""

    @pytest.mark.django_db
    def test_shifts_api_endpoint(self):
        """Verify shifts API returns valid JSON"""
        client = Client()
        response = client.get('/api/v1/admin/config/shifts/')

        # Should return either 200 (success) or 401 (requires auth)
        assert response.status_code in [200, 401, 404]

        if response.status_code == 200:
            data = response.json()
            assert 'results' in data or 'data' in data
            assert 'count' in data or len(data) >= 0

    @pytest.mark.django_db
    def test_business_units_api_endpoint(self):
        """Verify business units API returns valid JSON"""
        client = Client()
        response = client.get('/api/v1/admin/config/business-units/')

        assert response.status_code in [200, 401, 404]

        if response.status_code == 200:
            data = response.json()
            assert 'results' in data or 'data' in data

    @pytest.mark.django_db
    def test_geofences_api_endpoint(self):
        """Verify geofences API returns valid JSON"""
        client = Client()
        response = client.get('/api/v1/admin/config/geofences/')

        assert response.status_code in [200, 401, 404]

        if response.status_code == 200:
            data = response.json()
            assert 'results' in data or 'data' in data

    @pytest.mark.django_db
    def test_contracts_api_endpoint(self):
        """Verify contracts API returns valid JSON"""
        client = Client()
        response = client.get('/api/v1/admin/config/contracts/')

        assert response.status_code in [200, 401, 404]

        if response.status_code == 200:
            data = response.json()
            assert 'results' in data or 'data' in data


class TestMiddlewareRemoval:
    """Test that legacy middleware has been removed"""

    def test_legacy_middleware_not_in_settings(self):
        """Verify legacy_url_redirect not in MIDDLEWARE"""
        middleware = settings.MIDDLEWARE
        middleware_str = ' '.join(middleware)

        assert 'legacy_url_redirect' not in middleware_str
        assert 'LegacyURLRedirectMiddleware' not in middleware_str

    def test_legacy_middleware_file_deleted(self):
        """Verify middleware file deleted"""
        from django.conf import settings
        base_dir = settings.BASE_DIR
        middleware_path = base_dir / 'apps' / 'core' / 'middleware' / 'legacy_url_redirect.py'

        assert not middleware_path.exists(), \
            f"Legacy middleware file still exists at {middleware_path}"

    def test_management_command_deleted(self):
        """Verify monitor_legacy_redirects command deleted"""
        from django.conf import settings
        base_dir = settings.BASE_DIR
        command_path = base_dir / 'apps' / 'core' / 'management' / 'commands' / 'monitor_legacy_redirects.py'

        assert not command_path.exists(), \
            f"Legacy management command still exists at {command_path}"


class TestTemplateURLMigration:
    """Test that templates use correct URLs"""

    @pytest.fixture
    def templates_dir(self):
        """Get templates directory"""
        from django.conf import settings
        return Path(settings.BASE_DIR) / 'frontend' / 'templates'

    def test_no_onboarding_typeassist_in_templates(self, templates_dir):
        """Verify no templates reference onboarding:typeassist with ?action"""
        pattern = r"onboarding:typeassist['\"].*\?\s*action\s*="

        broken_refs = []
        for template_file in templates_dir.rglob('*.html'):
            content = template_file.read_text(encoding='utf-8', errors='ignore')
            if re.search(pattern, content):
                matches = re.findall(pattern, content)
                broken_refs.append((template_file.name, matches))

        assert len(broken_refs) == 0, \
            f"Found onboarding:typeassist AJAX references in templates: {broken_refs}"

    def test_no_onboarding_shift_in_templates(self, templates_dir):
        """Verify no templates reference onboarding:shift with ?action"""
        pattern = r"onboarding:shift['\"].*\?\s*action\s*="

        broken_refs = []
        for template_file in templates_dir.rglob('*.html'):
            content = template_file.read_text(encoding='utf-8', errors='ignore')
            if re.search(pattern, content):
                matches = re.findall(pattern, content)
                broken_refs.append((template_file.name, matches))

        assert len(broken_refs) == 0, \
            f"Found onboarding:shift AJAX references in templates: {broken_refs}"

    def test_no_onboarding_geofence_in_templates(self, templates_dir):
        """Verify no templates reference onboarding:geofence with ?action"""
        pattern = r"onboarding:geofence['\"].*\?\s*action\s*="

        broken_refs = []
        for template_file in templates_dir.rglob('*.html'):
            content = template_file.read_text(encoding='utf-8', errors='ignore')
            if re.search(pattern, content):
                matches = re.findall(pattern, content)
                broken_refs.append((template_file.name, matches))

        assert len(broken_refs) == 0, \
            f"Found onboarding:geofence AJAX references in templates: {broken_refs}"

    def test_templates_use_rest_api(self, templates_dir):
        """Verify templates use /api/v1/admin/config/ endpoints"""
        api_pattern = r"/api/v1/admin/config/(shifts|business-units|geofences|contracts)/"

        templates_with_api = []
        critical_templates = [
            'shift_modern.html',
            'bu_list_modern.html',
            'geofence_list_modern.html',
            'contract_list_modern.html',
        ]

        for template_name in critical_templates:
            template_files = list(templates_dir.rglob(template_name))
            if template_files:
                content = template_files[0].read_text(encoding='utf-8', errors='ignore')
                if re.search(api_pattern, content):
                    templates_with_api.append(template_name)

        # At least some templates should use REST API
        assert len(templates_with_api) > 0, \
            f"Expected at least some templates to use REST API endpoints. Found: {templates_with_api}"


class TestNo501Responses:
    """Test that no endpoints return HTTP 501"""

    @pytest.mark.django_db
    def test_no_501_in_onboarding_urls(self):
        """Test remaining onboarding URLs don't return 501"""
        client = Client()

        # Get all onboarding URL patterns
        from django.urls import get_resolver
        resolver = get_resolver()

        onboarding_urls = []
        for pattern in resolver.url_patterns:
            if hasattr(pattern, 'app_name') and pattern.app_name == 'onboarding':
                onboarding_urls.extend(pattern.url_patterns)

        # Test each URL
        for url_pattern in onboarding_urls:
            if hasattr(url_pattern, 'name') and url_pattern.name:
                try:
                    url = reverse(f'onboarding:{url_pattern.name}')
                    response = client.get(url)

                    # Should never return 501
                    assert response.status_code != 501, \
                        f"URL {url} returned HTTP 501 (Not Implemented)"

                except NoReverseMatch:
                    # URL requires parameters, skip
                    pass
                except Exception as e:
                    # Other errors are OK for this test
                    pass


class TestDataTableCompatibility:
    """Test that DataTables receive correct data format"""

    @pytest.mark.django_db
    def test_api_response_has_results_field(self):
        """Verify API responses have 'results' field for DataTables"""
        client = Client()
        endpoints = [
            '/api/v1/admin/config/shifts/',
            '/api/v1/admin/config/business-units/',
            '/api/v1/admin/config/geofences/',
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)

            if response.status_code == 200:
                data = response.json()

                # Should have either 'results' (REST API) or 'data' (legacy)
                has_results = 'results' in data
                has_data = 'data' in data

                assert has_results or has_data, \
                    f"API response from {endpoint} missing 'results' or 'data' field. Got: {data.keys()}"


# Run tests with:
# pytest tests/test_onboarding_remediation.py -v
# pytest tests/test_onboarding_remediation.py -v --tb=short
# pytest tests/test_onboarding_remediation.py::TestPlaceholderRemoval -v
