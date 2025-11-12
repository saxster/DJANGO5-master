"""
Secure upload path utilities for site onboarding media.

Provides callable upload path generators for file uploads.
"""
import os
import uuid
from typing import Optional

from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.text import get_valid_filename


def upload_site_photo(instance, filename):
    """Secure upload path for site photos."""
    return _build_secure_upload_path(instance, filename, category='photos')


def upload_site_photo_thumbnail(instance, filename):
    """Secure upload path for site photo thumbnails."""
    return _build_secure_upload_path(instance, filename, category='photo_thumbnails')


def upload_site_video(instance, filename):
    """Secure upload path for site videos."""
    return _build_secure_upload_path(instance, filename, category='videos')


def upload_site_video_thumbnail(instance, filename):
    """Secure upload path for site video thumbnails."""
    return _build_secure_upload_path(instance, filename, category='video_thumbnails')


def _build_secure_upload_path(instance, filename: str, category: str) -> str:
    """
    Build a tenant/site scoped upload path with a random suffix to prevent collisions.
    """
    safe_filename = get_valid_filename(filename or 'upload')
    name, ext = os.path.splitext(safe_filename)
    # Limit base name to avoid exploding path lengths
    base_name = name[:80] or 'file'

    tenant_id = _extract_identifier(instance, 'tenant_id') or _extract_identifier(
        getattr(instance, 'tenant', None), 'id'
    )
    site_id = _extract_identifier(instance, 'site_id') or _extract_identifier(
        getattr(instance, 'site', None), 'id'
    )

    tenant_segment = f"tenant_{tenant_id}" if tenant_id else "tenant_unknown"
    site_segment = f"site_{site_id}" if site_id else "site_unknown"
    date_path = timezone.now().strftime('%Y/%m/%d')
    random_suffix = uuid.uuid4().hex[:8]

    relative_path = os.path.join(
        'onboarding',
        category,
        tenant_segment,
        site_segment,
        date_path,
        f"{base_name}-{random_suffix}{ext.lower()}"
    )

    return default_storage.generate_filename(relative_path)


def _extract_identifier(value: Optional[object], attr: str) -> Optional[int]:
    """Safely extract an integer identifier from nested objects."""
    if not value:
        return None
    return getattr(value, attr, None)
