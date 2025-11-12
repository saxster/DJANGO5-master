"""Pytest configuration for performance tests.

Note: Phase 2+ tests require Django initialization to test integrated services.
Phase 1 baseline tests can run without Django.
"""

import os
import pytest
import django


def pytest_configure(config):
    """Configure pytest for performance tests."""
    # Set environment variables
    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-performance-tests')
    os.environ.setdefault('DATABASE_URL', 'sqlite://:memory:')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.test')

    # Initialize Django for tests that need it
    try:
        django.setup()
    except RuntimeError:
        # Django already configured
        pass


@pytest.fixture
def test_tenant(db):
    """Create test tenant for Phase 3 performance tests."""
    from apps.tenants.models import Tenant

    tenant, created = Tenant.objects.get_or_create(
        subdomain_prefix='test',
        defaults={
            'tenantname': 'Test Tenant',
            'is_active': True,
        }
    )
    return tenant
