"""
Secure upload path utilities for site onboarding media.

Provides callable upload path generators for file uploads.
"""
import os
from datetime import datetime
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename


def upload_site_photo(instance, filename):
    """Secure upload path for site photos."""
    safe_filename = get_valid_filename(filename)
    date_path = datetime.now().strftime('%Y/%m/%d')
    return f"onboarding/photos/{date_path}/{safe_filename}"


def upload_site_photo_thumbnail(instance, filename):
    """Secure upload path for site photo thumbnails."""
    safe_filename = get_valid_filename(filename)
    date_path = datetime.now().strftime('%Y/%m/%d')
    return f"onboarding/thumbnails/{date_path}/{safe_filename}"


def upload_site_video(instance, filename):
    """Secure upload path for site videos."""
    safe_filename = get_valid_filename(filename)
    date_path = datetime.now().strftime('%Y/%m/%d')
    return f"onboarding/videos/{date_path}/{safe_filename}"


def upload_site_video_thumbnail(instance, filename):
    """Secure upload path for site video thumbnails."""
    safe_filename = get_valid_filename(filename)
    date_path = datetime.now().strftime('%Y/%m/%d')
    return f"onboarding/video_thumbnails/{date_path}/{safe_filename}"
