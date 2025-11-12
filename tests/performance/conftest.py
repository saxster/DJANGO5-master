"""Pytest configuration for performance tests.

These tests don't require Django initialization - they test the baseline
script functions directly.
"""

import os
import pytest


def pytest_configure(config):
    """Configure pytest to skip Django setup for performance tests."""
    # Set a dummy SECRET_KEY to prevent Django configuration errors
    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-performance-tests')
    os.environ.setdefault('DATABASE_URL', 'sqlite://:memory:')
