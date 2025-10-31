"""
Migration to add tenant-aware constraints and indexes to work_order_management models.

This migration updates Wom, Vendor, WomDetails, and Approver models to:
1. Include tenant in unique constraints for proper multi-tenant isolation
2. Add performance indexes on tenant+field combinations

Phase 1: Multi-Tenant Security Hardening (Sprint 1)
Date: 2025-10-27
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('work_order_management', '0001_initial'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # =====================================================================
        # WOM MODEL
        # =====================================================================

        # Remove old constraint
        migrations.RemoveConstraint(
            model_name='wom',
            name='qset_client',
        ),

        # Add new constraint with tenant
        migrations.AddConstraint(
            model_name='wom',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'qset', 'client', 'id'],
                name='tenant_qset_client'
            ),
        ),

        # Add tenant indexes
        migrations.AddIndex(
            model_name='wom',
            index=models.Index(fields=['tenant', 'cdtz'], name='wom_tenant_cdtz_idx'),
        ),
        migrations.AddIndex(
            model_name='wom',
            index=models.Index(fields=['tenant', 'workstatus'], name='wom_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='wom',
            index=models.Index(fields=['tenant', 'workpermit'], name='wom_tenant_permit_idx'),
        ),

        # =====================================================================
        # VENDOR MODEL
        # =====================================================================

        # Remove old constraint
        migrations.RemoveConstraint(
            model_name='vendor',
            name='code_client',
        ),

        # Add new constraint with tenant
        migrations.AddConstraint(
            model_name='vendor',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'code', 'client'],
                name='tenant_code_client'
            ),
        ),

        # Add tenant indexes
        migrations.AddIndex(
            model_name='vendor',
            index=models.Index(fields=['tenant', 'cdtz'], name='vendor_tenant_cdtz_idx'),
        ),
        migrations.AddIndex(
            model_name='vendor',
            index=models.Index(fields=['tenant', 'enable'], name='vendor_tenant_enable_idx'),
        ),

        # =====================================================================
        # WOMDETAILS MODEL
        # =====================================================================

        # Remove old constraint
        migrations.RemoveConstraint(
            model_name='womdetails',
            name='question_client',
        ),

        # Add new constraint with tenant
        migrations.AddConstraint(
            model_name='womdetails',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'question', 'wom'],
                name='tenant_question_client'
            ),
        ),

        # Add tenant indexes
        migrations.AddIndex(
            model_name='womdetails',
            index=models.Index(fields=['tenant', 'wom'], name='womdetails_tenant_wom_idx'),
        ),
        migrations.AddIndex(
            model_name='womdetails',
            index=models.Index(fields=['tenant', 'question'], name='womdetails_tenant_question_idx'),
        ),

        # =====================================================================
        # APPROVER MODEL
        # =====================================================================

        # Remove old constraint
        migrations.RemoveConstraint(
            model_name='approver',
            name='people_approverfor_forallsites_sites_uk',
        ),

        # Add new constraint with tenant
        migrations.AddConstraint(
            model_name='approver',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'people', 'approverfor', 'sites'],
                name='tenant_people_approverfor_sites_uk'
            ),
        ),

        # Add tenant indexes
        migrations.AddIndex(
            model_name='approver',
            index=models.Index(fields=['tenant', 'people'], name='approver_tenant_people_idx'),
        ),
        migrations.AddIndex(
            model_name='approver',
            index=models.Index(fields=['tenant', 'identifier'], name='approver_tenant_identifier_idx'),
        ),
    ]
