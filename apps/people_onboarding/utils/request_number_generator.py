"""
Request Number Generator Utility

Provides atomic request number generation using PostgreSQL sequences
to prevent race conditions in concurrent onboarding scenarios.

Author: Ultrathink Phase 7 Remediation
Date: 2025-11-11
"""
from django.db import connection
from django.utils import timezone


def generate_request_number() -> str:
    """
    Generate unique request number using PostgreSQL sequence.

    Format: ONB-YYYY-XXXXX where XXXXX is atomic sequence number.
    Thread-safe and race condition-free in production (PostgreSQL).

    For SQLite (testing only): Falls back to count() + 1 (not thread-safe).

    Returns:
        str: Generated request number (e.g., 'ONB-2025-00001')

    Raises:
        DatabaseError: If sequence doesn't exist (run migrations)

    Examples:
        >>> number = generate_request_number()
        >>> print(number)
        'ONB-2025-00001'

    Notes:
        - PostgreSQL sequence provides atomic counter (no locks needed)
        - Sequence may skip numbers on transaction rollback (acceptable)
        - SQLite fallback for test environments only (single-threaded)
    """
    year = timezone.now().year

    # PostgreSQL: Use atomic sequence
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval('onboarding_request_number_seq')")
            seq_value = cursor.fetchone()[0]
        return f'ONB-{year}-{seq_value:05d}'

    # SQLite (test database): Fallback to count() + 1
    # Note: This is NOT thread-safe but acceptable for single-threaded tests
    else:
        # Import here to avoid circular dependency
        from apps.people_onboarding.models import OnboardingRequest
        count = OnboardingRequest.objects.count() + 1
        return f'ONB-{year}-{count:05d}'
