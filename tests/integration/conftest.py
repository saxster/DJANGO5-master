"""
Integration test configuration and fixtures.

IMPORTANT: Sets SECRET_KEY before Django import to prevent configuration errors.
"""

import os

# Set SECRET_KEY before any Django imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-integration-tests')

import pytest


@pytest.fixture(scope='session', autouse=True)
def setup_test_environment():
    """
    Set up the test environment before running integration tests.
    This fixture runs automatically for all integration tests.
    """
    yield
    # Cleanup if needed
