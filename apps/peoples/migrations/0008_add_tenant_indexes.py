"""
Migration to add tenant-aware indexes to peoples models.

This migration updates People model to add performance indexes
on tenant+field combinations for efficient multi-tenant user queries.

Phase 1: Multi-Tenant Security Hardening (Sprint 1)
Date: 2025-10-27
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peoples', '0007_deviceregistration_deviceriskevent_and_more'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # =====================================================================
        # PEOPLE MODEL
        # =====================================================================

        # Add tenant indexes
        migrations.AddIndex(
            model_name='people',
            index=models.Index(fields=['tenant', 'cdtz'], name='people_tenant_cdtz_idx'),
        ),
        migrations.AddIndex(
            model_name='people',
            index=models.Index(fields=['tenant', 'enable'], name='people_tenant_enable_idx'),
        ),
    ]
