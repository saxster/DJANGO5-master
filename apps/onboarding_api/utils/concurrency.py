"""
Concurrency control utilities for Conversational Onboarding API

Provides PostgreSQL advisory locks and other concurrency primitives
to prevent race conditions in critical sections.
"""
import hashlib
import logging
from contextlib import contextmanager
from typing import Generator, Union

from django.db import connection, transaction
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()


def _generate_lock_id(user_id: int, client_id: Union[int, str], lock_type: str = "session") -> int:
    """
    Generate a consistent advisory lock ID for a user+client combination

    Args:
        user_id: User ID
        client_id: Client ID (can be int or string)
        lock_type: Type of lock (session, approval, etc.)

    Returns:
        Integer lock ID suitable for PostgreSQL advisory locks
    """
    # Create a consistent string representation
    lock_string = f"{lock_type}:{user_id}:{client_id}"

    # Generate a hash and convert to a 32-bit signed integer
    # PostgreSQL advisory locks use bigint, but we'll use a smaller space for safety
    hash_bytes = hashlib.sha256(lock_string.encode()).digest()
    lock_id = int.from_bytes(hash_bytes[:4], byteorder='big', signed=True)

    return lock_id


@contextmanager
def advisory_lock(
    user: User,
    client_id: Union[int, str, None] = None,
    lock_type: str = "session",
    timeout_seconds: int = 10
) -> Generator[bool, None, None]:
    """
    PostgreSQL advisory lock context manager for preventing race conditions

    This uses PostgreSQL's pg_try_advisory_lock() function to create
    application-level locks that prevent concurrent operations on the
    same user+client combination.

    Args:
        user: User instance
        client_id: Client ID (defaults to user.client.id if available)
        lock_type: Type of operation being locked
        timeout_seconds: How long to wait for lock acquisition

    Yields:
        bool: True if lock was acquired successfully, False otherwise

    Example:
        with advisory_lock(user, client_id, "session") as acquired:
            if acquired:
                # Critical section - safe to check and create sessions
                existing = ConversationSession.objects.filter(...)
                if not existing:
                    ConversationSession.objects.create(...)
            else:
                # Lock not acquired - handle accordingly
                return error_response
    """
    if client_id is None:
        if hasattr(user, 'client') and user.client:
            client_id = user.client.id
        else:
            raise ValueError("client_id must be provided or user must have associated client")

    lock_id = _generate_lock_id(user.id, client_id, lock_type)
    acquired = False

    try:
        with connection.cursor() as cursor:
            # Try to acquire the advisory lock
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
            acquired = cursor.fetchone()[0]

            logger.debug(
                f"Advisory lock {'acquired' if acquired else 'failed'} for "
                f"user {user.id}, client {client_id}, type {lock_type}, lock_id {lock_id}"
            )

        yield acquired

    finally:
        # Always release the lock if we acquired it
        if acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
                    released = cursor.fetchone()[0]

                    if not released:
                        logger.warning(
                            f"Failed to release advisory lock {lock_id} for "
                            f"user {user.id}, client {client_id}, type {lock_type}"
                        )
                    else:
                        logger.debug(
                            f"Advisory lock released for user {user.id}, "
                            f"client {client_id}, type {lock_type}, lock_id {lock_id}"
                        )
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Error releasing advisory lock {lock_id}: {str(e)}"
                )


@contextmanager
def advisory_lock_with_timeout(
    user: User,
    client_id: Union[int, str, None] = None,
    lock_type: str = "session",
    timeout_seconds: int = 10
) -> Generator[bool, None, None]:
    """
    Advisory lock with timeout support using pg_advisory_lock with timeout

    This is similar to advisory_lock but will wait up to timeout_seconds
    for the lock to become available rather than failing immediately.

    Args:
        user: User instance
        client_id: Client ID (defaults to user.client.id if available)
        lock_type: Type of operation being locked
        timeout_seconds: How long to wait for lock acquisition

    Yields:
        bool: True if lock was acquired successfully, False if timeout
    """
    if client_id is None:
        if hasattr(user, 'client') and user.client:
            client_id = user.client.id
        else:
            raise ValueError("client_id must be provided or user must have associated client")

    lock_id = _generate_lock_id(user.id, client_id, lock_type)
    acquired = False

    try:
        # Use a transaction with a statement timeout
        with transaction.atomic():
            with connection.cursor() as cursor:
                # SECURITY FIX: Sanitize timeout_seconds to prevent SQL injection
                # Force integer conversion and clamp to safe bounds (1-60 seconds)
                try:
                    safe_timeout = max(1, min(int(timeout_seconds), 60))
                except (ValueError, TypeError):
                    safe_timeout = 10  # Default fallback
                    logger.warning(
                        f"Invalid timeout_seconds value: {timeout_seconds}, using default {safe_timeout}s"
                    )

                # Set statement timeout for this lock acquisition (now safe from injection)
                cursor.execute(f"SET statement_timeout = '{safe_timeout}s'")

                try:
                    # This will block until lock is acquired or timeout
                    cursor.execute("SELECT pg_advisory_lock(%s)", [lock_id])
                    acquired = True
                    logger.debug(
                        f"Advisory lock with timeout acquired for "
                        f"user {user.id}, client {client_id}, type {lock_type}"
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Advisory lock timeout for user {user.id}, "
                        f"client {client_id}, type {lock_type}: {str(e)}"
                    )
                finally:
                    # Reset statement timeout
                    cursor.execute("SET statement_timeout = 0")

        yield acquired

    finally:
        # Always release the lock if we acquired it
        if acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
                    released = cursor.fetchone()[0]

                    if not released:
                        logger.warning(
                            f"Failed to release advisory lock {lock_id} for "
                            f"user {user.id}, client {client_id}, type {lock_type}"
                        )
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Error releasing advisory lock {lock_id}: {str(e)}"
                )


def check_lock_status(user: User, client_id: Union[int, str, None] = None, lock_type: str = "session") -> dict:
    """
    Check the status of an advisory lock without trying to acquire it

    Args:
        user: User instance
        client_id: Client ID (defaults to user.client.id if available)
        lock_type: Type of operation being checked

    Returns:
        Dict with lock status information
    """
    if client_id is None:
        if hasattr(user, 'client') and user.client:
            client_id = user.client.id
        else:
            raise ValueError("client_id must be provided or user must have associated client")

    lock_id = _generate_lock_id(user.id, client_id, lock_type)

    try:
        with connection.cursor() as cursor:
            # Check if lock exists (PostgreSQL 9.6+)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_locks
                    WHERE locktype = 'advisory'
                    AND objid = %s
                    AND granted = true
                )
            """, [lock_id])

            is_locked = cursor.fetchone()[0]

            return {
                'lock_id': lock_id,
                'is_locked': is_locked,
                'user_id': user.id,
                'client_id': client_id,
                'lock_type': lock_type
            }

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Error checking lock status: {str(e)}")
        return {
            'lock_id': lock_id,
            'is_locked': None,
            'error': str(e),
            'user_id': user.id,
            'client_id': client_id,
            'lock_type': lock_type
        }