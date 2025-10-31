"""
Data migration to add initial deprecation entries.
Marks upload_attachment legacy mutation as deprecated.
"""

from django.db import migrations
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone


def add_initial_deprecations(apps, schema_editor):
    """Add initial deprecation entries for known deprecated endpoints."""
    APIDeprecation = apps.get_model('core', 'APIDeprecation')

    deprecated_date = timezone.now()
    sunset_date = datetime(2026, 6, 30, 23, 59, 59, tzinfo=dt_timezone.utc)

    APIDeprecation.objects.create(
        endpoint_pattern='Mutation.upload_attachment',
        api_type='legacy_mutation',
        version_deprecated='v1.0',
        version_removed='v2.0',
        deprecated_date=deprecated_date,
        sunset_date=sunset_date,
        status='deprecated',
        replacement_endpoint='Mutation.secure_file_upload',
        migration_url='/docs/api-migrations/file-upload-v2/',
        deprecation_reason='Security vulnerabilities in Base64 upload method. Migrating to secure multipart upload.',
        notify_on_usage=True,
    )


def remove_initial_deprecations(apps, schema_editor):
    """Reverse migration: remove deprecation entries."""
    APIDeprecation = apps.get_model('core', 'APIDeprecation')
    APIDeprecation.objects.filter(endpoint_pattern='Mutation.upload_attachment').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_add_api_deprecation_models'),
    ]

    operations = [
        migrations.RunPython(add_initial_deprecations, remove_initial_deprecations),
    ]
