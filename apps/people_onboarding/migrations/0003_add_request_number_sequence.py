"""
Migration to add PostgreSQL sequence for atomic request number generation.

Fixes race condition in concurrent onboarding request creation where
count() + 1 generates duplicate request_number values.

Author: Ultrathink Phase 6 Remediation
Date: 2025-11-11
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('people_onboarding', '0002_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Create sequence starting at 1
            sql="""
                CREATE SEQUENCE IF NOT EXISTS onboarding_request_number_seq START 1;
            """,
            reverse_sql="""
                DROP SEQUENCE IF EXISTS onboarding_request_number_seq;
            """
        ),
    ]
