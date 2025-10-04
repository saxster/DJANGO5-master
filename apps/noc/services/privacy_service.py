"""
NOC Privacy Service for PII Masking.

Implements PII masking for NOC data based on user capabilities.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #15 (no PII in logs).
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger('noc.privacy')

__all__ = ['NOCPrivacyService']


class NOCPrivacyService:
    """Service for PII masking in NOC data."""

    PII_FIELDS = [
        'phone',
        'mobile',
        'mobno',
        'email',
        'address',
        'full_address',
        'peoplename',
        'person_name',
        'assigned_to_name',
        'resolved_by_name',
    ]

    @staticmethod
    def mask_pii(data: Dict[str, Any], user) -> Dict[str, Any]:
        """
        Mask PII unless user has special permission.

        Args:
            data: Dictionary containing potentially sensitive data
            user: People instance

        Returns:
            dict: Data with masked PII fields
        """
        if NOCPrivacyService.can_view_pii(user):
            return data

        masked_data = data.copy()

        for field in NOCPrivacyService.PII_FIELDS:
            if field in masked_data:
                masked_data[field] = NOCPrivacyService._mask_value(
                    masked_data[field]
                )

        return masked_data

    @staticmethod
    def mask_list(data_list: List[Dict], user) -> List[Dict]:
        """
        Mask PII in a list of dictionaries.

        Args:
            data_list: List of dictionaries
            user: People instance

        Returns:
            list: List with masked PII
        """
        if NOCPrivacyService.can_view_pii(user):
            return data_list

        return [
            NOCPrivacyService.mask_pii(item, user)
            for item in data_list
        ]

    @staticmethod
    def mask_alert_metadata(alert, user):
        """
        Mask PII in alert metadata.

        Args:
            alert: NOCAlertEvent instance
            user: People instance

        Returns:
            dict: Masked metadata
        """
        if NOCPrivacyService.can_view_pii(user):
            return alert.metadata

        metadata = alert.metadata.copy()

        pii_keys = [
            'assigned_to',
            'person_name',
            'device_owner',
            'contact_info',
        ]

        for key in pii_keys:
            if key in metadata:
                metadata[key] = '***MASKED***'

        return metadata

    @staticmethod
    def can_view_pii(user) -> bool:
        """
        Check if user can view PII data.

        Args:
            user: People instance

        Returns:
            bool: True if user can view PII
        """
        return (
            user.isadmin or
            user.has_capability('noc:view_pii') or
            user.has_capability('noc:view_all_clients')
        )

    @staticmethod
    def _mask_value(value: Any) -> str:
        """
        Mask a sensitive value.

        Args:
            value: Value to mask

        Returns:
            str: Masked value
        """
        if value is None:
            return None

        value_str = str(value)

        if len(value_str) <= 4:
            return '****'

        if '@' in value_str:
            return NOCPrivacyService._mask_email(value_str)

        if len(value_str) >= 10 and value_str.replace('-', '').replace('+', '').isdigit():
            return NOCPrivacyService._mask_phone(value_str)

        return value_str[:2] + '*' * (len(value_str) - 4) + value_str[-2:]

    @staticmethod
    def _mask_email(email: str) -> str:
        """
        Mask email address.

        Args:
            email: Email address

        Returns:
            str: Masked email (e.g., j***@example.com)
        """
        if '@' not in email:
            return '***@***.***'

        local, domain = email.split('@', 1)

        if len(local) <= 1:
            masked_local = '*'
        elif len(local) <= 3:
            masked_local = local[0] + '*' * (len(local) - 1)
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]

        return f"{masked_local}@{domain}"

    @staticmethod
    def _mask_phone(phone: str) -> str:
        """
        Mask phone number.

        Args:
            phone: Phone number

        Returns:
            str: Masked phone (e.g., +1-***-***-1234)
        """
        digits_only = ''.join(c for c in phone if c.isdigit())

        if len(digits_only) < 4:
            return '***-****'

        masked_digits = '*' * (len(digits_only) - 4) + digits_only[-4:]

        if '+' in phone[:3]:
            return f"+{phone[1:3]}-***-{masked_digits[-4:]}"

        return f"***-{masked_digits[-4:]}"