"""
Unit test configuration and fixtures.

IMPORTANT: Sets SECRET_KEY before Django import to prevent configuration errors.
"""

import os

# Set SECRET_KEY before any Django imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

import pytest


@pytest.fixture(scope='session', autouse=True)
def setup_test_environment():
    """
    Set up the test environment before running unit tests.
    This fixture runs automatically for all unit tests.
    """
    yield
    # Cleanup if needed
