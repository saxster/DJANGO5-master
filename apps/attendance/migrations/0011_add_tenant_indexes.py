"""
Migration to add tenant-aware indexes to attendance models.

This migration updates PeopleEventlog model to add performance indexes
on tenant+field combinations for efficient multi-tenant queries.

Phase 1: Multi-Tenant Security Hardening (Sprint 1)
Date: 2025-10-27
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0010_add_performance_indexes'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # =====================================================================
        # PEOPLEEVENTLOG (Attendance) MODEL
        # =====================================================================

        # Add tenant indexes
        migrations.AddIndex(
            model_name='peopleeventlog',
            index=models.Index(fields=['tenant', 'cdtz'], name='pel_tenant_cdtz_idx'),
        ),
        migrations.AddIndex(
            model_name='peopleeventlog',
            index=models.Index(fields=['tenant', 'people'], name='pel_tenant_people_idx'),
        ),
        migrations.AddIndex(
            model_name='peopleeventlog',
            index=models.Index(fields=['tenant', 'datefor'], name='pel_tenant_datefor_idx'),
        ),
        migrations.AddIndex(
            model_name='peopleeventlog',
            index=models.Index(fields=['tenant', 'bu'], name='pel_tenant_bu_idx'),
        ),
    ]
