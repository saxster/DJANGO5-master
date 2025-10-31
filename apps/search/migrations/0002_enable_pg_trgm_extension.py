"""
Enable PostgreSQL pg_trgm Extension for Fuzzy Matching

This migration enables the pg_trgm (trigram) extension which provides:
- Fuzzy text matching with similarity() function
- Typo tolerance in searches
- GiST/GIN index support for performance
- Distance-based ranking

Requires PostgreSQL 9.1+ with contrib modules installed.
"""

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0001_enable_fts_extensions'),
    ]

    operations = [
        # Enable pg_trgm extension
        TrigramExtension(),
    ]
