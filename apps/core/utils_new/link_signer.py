"""
Time-bound Secure Link Signer.

Generates and validates signed, expiring links for client portal access.
Prevents tampering and ensures time-limited access.

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #12: Security first - cryptographic signing

@ontology(
    domain="security",
    purpose="Generate time-bound signed URLs for client portal",
    business_value="Secure temporary access without password sharing",
    criticality="high",
    tags=["security", "authentication", "tokens", "portal"]
)
"""

import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple
from django.conf import settings
from django.core.exceptions import ValidationError

__all__ = ['LinkSigner']


class LinkSigner:
    """Generate and verify signed time-bound access tokens."""
    
    @classmethod
    def generate_token(
        cls,
        client_id: int,
        scope: str = 'read_only',
        expires_in_hours: int = 24
    ) -> str:
        """
        Generate signed access token.
        
        Args:
            client_id: Client/BusinessUnit ID
            scope: Permission scope (read_only, reports, dashboards)
            expires_in_hours: Token validity period
            
        Returns:
            Signed token string
        """
        expiry = int(time.time()) + (expires_in_hours * 3600)
        
        payload = f"{client_id}:{scope}:{expiry}"
        signature = cls._sign_payload(payload)
        
        return f"{payload}:{signature}"
    
    @classmethod
    def verify_token(cls, token: str) -> Tuple[int, str]:
        """
        Verify token validity and extract claims.
        
        Args:
            token: Signed token string
            
        Returns:
            Tuple of (client_id, scope)
            
        Raises:
            ValidationError: If token invalid, expired, or tampered
        """
        try:
            parts = token.split(':')
            if len(parts) != 4:
                raise ValidationError("Invalid token format")
            
            client_id_str, scope, expiry_str, signature = parts
            
            payload = f"{client_id_str}:{scope}:{expiry_str}"
            expected_signature = cls._sign_payload(payload)
            
            if not hmac.compare_digest(signature, expected_signature):
                raise ValidationError("Token signature invalid")
            
            expiry = int(expiry_str)
            if time.time() > expiry:
                raise ValidationError("Token expired")
            
            return int(client_id_str), scope
            
        except (ValueError, IndexError) as e:
            raise ValidationError(f"Token verification failed: {e}")
    
    @classmethod
    def _sign_payload(cls, payload: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        secret = settings.SECRET_KEY.encode('utf-8')
        message = payload.encode('utf-8')
        
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return signature[:32]
    
    @classmethod
    def generate_portal_url(
        cls,
        client_id: int,
        base_url: str,
        scope: str = 'read_only',
        expires_in_hours: int = 24
    ) -> str:
        """
        Generate complete portal access URL.
        
        Args:
            client_id: Client/BusinessUnit ID
            base_url: Base portal URL (e.g., https://app.example.com/portal)
            scope: Permission scope
            expires_in_hours: Token validity period
            
        Returns:
            Complete signed URL
        """
        token = cls.generate_token(client_id, scope, expires_in_hours)
        return f"{base_url}?token={token}"
