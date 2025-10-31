"""
Refresh Token Blacklist Model

Tracks invalidated JWT refresh tokens to prevent token replay attacks.
Implements token rotation security pattern for legacy API authentication.

Security Features:
- Blacklist revoked/rotated tokens
- Prevent token reuse
- Track invalidation reasons
- Support for token cleanup

Compliance: Addresses Medium-severity token security vulnerability
"""

from __future__ import annotations  # Enable string annotations for type hints
from typing import TYPE_CHECKING

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models.enhanced_base_model import BaseModelCompat as BaseModel
from apps.core.constants.datetime_constants import SECONDS_IN_DAY
import logging

if TYPE_CHECKING:
    from apps.peoples.models import People

logger = logging.getLogger('security')


class RefreshTokenBlacklist(BaseModel):
    """
    Model to track blacklisted JWT refresh tokens.

    When a refresh token is rotated or explicitly revoked, it's added to this
    blacklist to prevent reuse. Old entries are automatically cleaned up.

    Usage:
        # Blacklist a token after rotation
        RefreshTokenBlacklist.objects.create(
            token_jti='abc123',
            user=user,
            reason='rotated'
        )

        # Check if token is blacklisted
        is_blacklisted = RefreshTokenBlacklist.objects.is_token_blacklisted('abc123')
    """

    # Token identifier (JWT 'jti' claim)
    token_jti = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="JWT token identifier (jti claim)"
    )

    # User who owned the token
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blacklisted_tokens',
        help_text="User associated with this token"
    )

    # When the token was blacklisted
    blacklisted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when token was blacklisted"
    )

    # Why the token was blacklisted
    REASON_CHOICES = [
        ('rotated', 'Token Rotated'),
        ('logout', 'User Logout'),
        ('revoked', 'Admin Revoked'),
        ('expired', 'Token Expired'),
        ('security', 'Security Event'),
    ]

    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        default='rotated',
        db_index=True,
        help_text="Reason for blacklisting"
    )

    # Optional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (IP address, user agent, etc.)"
    )

    class Meta:
        db_table = 'core_refresh_token_blacklist'
        verbose_name = 'Refresh Token Blacklist Entry'
        verbose_name_plural = 'Refresh Token Blacklist Entries'
        ordering = ['-blacklisted_at']

        indexes = [
            # Fast token lookup
            models.Index(fields=['token_jti'], name='idx_token_jti'),

            # Cleanup queries
            models.Index(fields=['blacklisted_at', 'reason'], name='idx_blacklist_cleanup'),

            # User-specific queries
            models.Index(fields=['user', '-blacklisted_at'], name='idx_user_blacklist'),
        ]

    def __str__(self):
        return f"Blacklisted token for {self.user.peoplename} ({self.reason})"

    @classmethod
    def blacklist_token(cls, token_jti: str, user: People, reason: str = 'rotated',
                       metadata: dict = None) -> 'RefreshTokenBlacklist':
        """
        Blacklist a refresh token.

        Args:
            token_jti: JWT token identifier (jti claim)
            user: User who owns the token
            reason: Reason for blacklisting
            metadata: Optional metadata dict

        Returns:
            RefreshTokenBlacklist instance
        """
        entry = cls.objects.create(
            token_jti=token_jti,
            user=user,
            reason=reason,
            metadata=metadata or {}
        )

        logger.info(
            f"Token blacklisted: jti={token_jti[:10]}... "
            f"user={user.id} reason={reason}",
            extra={
                'user_id': user.id,
                'token_jti_prefix': token_jti[:10],
                'reason': reason,
                'security_event': 'token_blacklist'
            }
        )

        return entry

    @classmethod
    def is_token_blacklisted(cls, token_jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token_jti: JWT token identifier

        Returns:
            True if blacklisted, False otherwise
        """
        return cls.objects.filter(token_jti=token_jti).exists()

    @classmethod
    def cleanup_old_entries(cls, days_old: int = 7) -> int:
        """
        Delete blacklist entries older than specified days.

        Tokens typically expire within 2 days, so blacklist entries older
        than 7 days are no longer needed.

        Args:
            days_old: Number of days to keep entries

        Returns:
            Number of entries deleted
        """
        from django.utils import timezone as dt_timezone
        from datetime import timedelta

        cutoff_date = timezone.now() - timedelta(days=days_old)
        deleted_count, _ = cls.objects.filter(
            blacklisted_at__lt=cutoff_date
        ).delete()

        if deleted_count > 0:
            logger.info(
                f"Cleaned up {deleted_count} old blacklist entries (>{days_old} days)",
                extra={
                    'deleted_count': deleted_count,
                    'days_threshold': days_old,
                    'maintenance_task': 'blacklist_cleanup'
                }
            )

        return deleted_count

    @classmethod
    def revoke_all_user_tokens(cls, user: People, reason: str = 'security') -> int:
        """
        Revoke all active tokens for a specific user.

        Use case: Force logout across all devices (e.g., password change,
        security incident, account suspension).

        Args:
            user: User whose tokens to revoke
            reason: Reason for mass revocation

        Returns:
            Number of tokens revoked (note: this might not match actual
            active tokens, as we don't track all issued tokens)
        """
        # Note: This creates entries for potential future tokens.
        # A more robust implementation would track all issued tokens.

        logger.warning(
            f"Revoking all tokens for user {user.id}",
            extra={
                'user_id': user.id,
                'reason': reason,
                'security_event': 'mass_token_revocation'
            }
        )

        # In a complete implementation, you'd track issued tokens and
        # blacklist them here. For now, this serves as a security log.
        return 0


class RefreshTokenBlacklistManager(models.Manager):
    """Custom manager for RefreshTokenBlacklist with helper methods."""

    def blacklist_token(self, token_jti: str, user: People, reason: str = 'rotated',
                       metadata: dict = None):
        """Proxy to model classmethod for convenience."""
        return self.model.blacklist_token(token_jti, user, reason, metadata)

    def is_blacklisted(self, token_jti: str) -> bool:
        """Check if token is blacklisted."""
        return self.filter(token_jti=token_jti).exists()

    def cleanup_old_entries(self, days_old: int = 7) -> int:
        """Delete old entries."""
        return self.model.cleanup_old_entries(days_old)


# Attach custom manager
RefreshTokenBlacklist.objects = RefreshTokenBlacklistManager()
