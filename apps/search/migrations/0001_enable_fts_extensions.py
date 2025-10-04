"""
Enable PostgreSQL Full Text Search extensions

This migration enables:
- pg_trgm: Trigram matching for fuzzy search and typo tolerance
- unaccent: Accent-insensitive search (e.g., "cafe" matches "café")

These extensions are required for the global search functionality.
Performance impact: Negligible (extensions are lightweight)
"""

from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    """Enable FTS extensions for global search (Rule #7: < 150 lines)"""

    dependencies = []

    operations = [
        # Enable trigram extension for fuzzy matching
        TrigramExtension(),

        # Enable unaccent extension for accent-insensitive search
        UnaccentExtension(),
    ]