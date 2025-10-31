"""
API authentication and access logging models.

This module contains models for API key management and access auditing:
- APIKey: Secure API key storage with HMAC signing support
- APIAccessLog: API access attempts for audit and analytics

Migration Date: 2025-10-10
Migrated from: apps/core/models.py (lines 154-409)
"""

import hashlib
import secrets
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from datetime import timedelta


class APIKey(models.Model):
    """
    Model for storing API keys with secure hashing.
    """

    name = models.CharField(
        max_length=100,
        help_text="Descriptive name for this API key"
    )

    key_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 hash of the API key"
    )

    secret = models.CharField(
        max_length=64,
        help_text="Secret for request signing (HMAC)"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys',
        null=True,
        blank=True,
        help_text="User associated with this API key"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this API key is active"
    )

    require_signing = models.BooleanField(
        default=False,
        help_text="Whether requests must be signed with HMAC"
    )

    allowed_ips = ArrayField(
        models.GenericIPAddressField(),
        blank=True,
        null=True,
        help_text="List of allowed IP addresses (null = all allowed)"
    )

    permissions = models.JSONField(
        default=dict,
        help_text="Permissions granted to this API key"
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this API key expires (null = never)"
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this API key was used"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this API key was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this API key was last updated"
    )

    class Meta:
        db_table = 'api_keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key_hash']),
            models.Index(fields=['is_active', 'expires_at']),
        ]

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    @classmethod
    def generate_key(cls):
        """
        Generate a new API key.

        Returns:
            tuple: (api_key, key_hash)
        """
        # Generate a secure random API key
        api_key = secrets.token_urlsafe(32)

        # Hash the key for storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        return api_key, key_hash

    @classmethod
    def generate_secret(cls):
        """
        Generate a secret for request signing.

        Returns:
            str: Secret string
        """
        return secrets.token_urlsafe(32)

    @classmethod
    def create_api_key(cls, name, user=None, **kwargs):
        """
        Create a new API key.

        Args:
            name: Name for the API key
            user: Optional user to associate with
            **kwargs: Additional fields

        Returns:
            tuple: (api_key_instance, raw_api_key)
        """
        api_key, key_hash = cls.generate_key()
        secret = cls.generate_secret()

        instance = cls.objects.create(
            name=name,
            key_hash=key_hash,
            secret=secret,
            user=user,
            **kwargs
        )

        # Return both instance and raw key (raw key is only available now)
        return instance, api_key

    def update_last_used(self):
        """Update the last_used_at timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])

    def is_expired(self):
        """Check if the API key has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    def has_permission(self, permission):
        """
        Check if this API key has a specific permission.

        Args:
            permission: Permission string to check

        Returns:
            bool: True if permission is granted
        """
        if not self.permissions:
            return False

        # Check for wildcard permission
        if self.permissions.get('*'):
            return True

        # Check specific permission
        return self.permissions.get(permission, False)


class APIAccessLog(models.Model):
    """
    Log of API access attempts for audit and analytics.
    """

    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.SET_NULL,
        null=True,
        related_name='access_logs',
        help_text="API key used for this request"
    )

    ip_address = models.GenericIPAddressField(
        help_text="IP address of the request"
    )

    method = models.CharField(
        max_length=10,
        help_text="HTTP method used"
    )

    path = models.CharField(
        max_length=500,
        help_text="Request path"
    )

    query_params = models.TextField(
        blank=True,
        help_text="Query parameters"
    )

    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )

    response_status = models.IntegerField(
        null=True,
        help_text="HTTP response status code"
    )

    response_time = models.IntegerField(
        help_text="Response time in milliseconds"
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if request failed"
    )

    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="When the request was made"
    )

    class Meta:
        db_table = 'api_access_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['api_key', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['response_status']),
        ]

    def __str__(self):
        return f"{self.method} {self.path} - {self.timestamp}"

    @classmethod
    def cleanup_old_logs(cls, days=90):
        """
        Clean up old access logs.

        Args:
            days: Number of days to keep

        Returns:
            int: Number of deleted records
        """
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = cls.objects.filter(timestamp__lt=cutoff).delete()

        return deleted
