"""
API Version Negotiation
Handles version selection and compatibility checking.

Compliance with .claude/rules.md:
- Rule #6: File < 200 lines
- Rule #11: Specific exception handling
"""

import re
import logging
from typing import Optional, Tuple
from django.conf import settings

logger = logging.getLogger('api.versioning')


class APIVersionNegotiator:
    """
    Handles API version negotiation between clients and server.
    Supports URL path versioning and Accept header versioning.
    """

    @staticmethod
    def negotiate_version(request) -> Tuple[str, str]:
        """
        Negotiate API version from request.

        Returns:
            Tuple of (version, source) where source is 'url', 'header', or 'default'
        """
        version, source = APIVersionNegotiator._extract_from_url(request)
        if version:
            return version, source

        version, source = APIVersionNegotiator._extract_from_header(request)
        if version:
            return version, source

        default_version = getattr(settings, 'API_VERSION_CONFIG', {}).get('CURRENT_VERSION', 'v1')
        return default_version, 'default'

    @staticmethod
    def _extract_from_url(request) -> Tuple[Optional[str], str]:
        """Extract version from URL path (/api/v1/, /api/v2/)."""
        match = re.search(r'/api/(v\d+)/', request.path)
        if match:
            version = match.group(1)
            if APIVersionNegotiator._is_supported_version(version):
                return version, 'url'
        return None, ''

    @staticmethod
    def _extract_from_header(request) -> Tuple[Optional[str], str]:
        """Extract version from Accept-Version or Accept header."""
        version_header = request.META.get('HTTP_ACCEPT_VERSION')
        if version_header and APIVersionNegotiator._is_supported_version(version_header):
            return version_header, 'header'

        accept_header = request.META.get('HTTP_ACCEPT', '')
        match = re.search(r'version=(v?\d+\.?\d*)', accept_header)
        if match:
            version = match.group(1)
            if not version.startswith('v'):
                version = f'v{version}'
            if APIVersionNegotiator._is_supported_version(version):
                return version, 'header'

        return None, ''

    @staticmethod
    def _is_supported_version(version: str) -> bool:
        """Check if version is supported."""
        supported = getattr(settings, 'API_VERSION_CONFIG', {}).get('SUPPORTED_VERSIONS', ['v1'])
        return version in supported

    @staticmethod
    def is_deprecated_version(version: str) -> bool:
        """Check if version is deprecated."""
        deprecated = getattr(settings, 'API_VERSION_CONFIG', {}).get('DEPRECATED_VERSIONS', [])
        return version in deprecated

    @staticmethod
    def is_sunset_version(version: str) -> bool:
        """Check if version is in sunset period."""
        sunset = getattr(settings, 'API_VERSION_CONFIG', {}).get('SUNSET_VERSIONS', [])
        return version in sunset

    @staticmethod
    def get_compatible_version(client_version: str) -> str:
        """
        Get compatible API version for given client SDK version.

        Maps client versions to API versions for backward compatibility.
        """
        version_map = {
            '1.0.0': 'v1',
            '1.1.0': 'v1',
            '1.2.0': 'v1',
            '2.0.0': 'v2',
        }

        for client_ver, api_ver in sorted(version_map.items(), reverse=True):
            if client_version >= client_ver:
                return api_ver

        return 'v1'


__all__ = ['APIVersionNegotiator']