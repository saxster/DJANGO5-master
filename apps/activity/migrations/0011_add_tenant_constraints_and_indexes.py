"""
Migration to add tenant-aware constraints and indexes to activity models.

This migration updates Job, Jobneed, JobneedDetails, Asset, and AssetLog models to:
1. Include tenant in unique constraints for proper multi-tenant isolation
2. Add performance indexes on tenant+field combinations

Phase 1: Multi-Tenant Security Hardening (Sprint 1)
Date: 2025-10-27
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0010_add_comprehensive_indexes'),
        ('tenants', '0001_initial'),  # Ensure tenant model exists
    ]

    operations = [
        # =====================================================================
        # JOB MODEL
        # =====================================================================

        # Remove old constraint without tenant
        migrations.RemoveConstraint(
            model_name='job',
            name='jobname_asset_qset_id_parent_identifier_client_uk',
        ),

        # Add new constraint with tenant
        migrations.AddConstraint(
            model_name='job',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'jobname', 'asset', 'qset', 'parent', 'identifier', 'client'],
                name='tenant_jobname_asset_qset_parent_identifier_client_uk',
            ),
        ),

        # Add tenant indexes
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['tenant', 'cdtz'], name='job_tenant_cdtz_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['tenant', 'identifier'], name='job_tenant_identifier_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['tenant', 'enable'], name='job_tenant_enable_idx'),
        ),

        # =====================================================================
        # JOBNEED MODEL
        # =====================================================================

        # Add tenant indexes for Jobneed
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(fields=['tenant', 'cdtz'], name='jobneed_tenant_cdtz_idx'),
        ),
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(fields=['tenant', 'jobstatus'], name='jobneed_tenant_jobstatus_idx'),
        ),
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(fields=['tenant', 'people'], name='jobneed_tenant_people_idx'),
        ),

        # =====================================================================
        # JOBNEEDDETAILS MODEL
        # =====================================================================

        # Remove old constraints
        migrations.RemoveConstraint(
            model_name='jobneeddetails',
            name='jobneeddetails_jobneed_question_uk',
        ),
        migrations.RemoveConstraint(
            model_name='jobneeddetails',
            name='jobneeddetails_jobneed_seqno_uk',
        ),

        # Add new constraints with tenant
        migrations.AddConstraint(
            model_name='jobneeddetails',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'jobneed', 'question'],
                name='tenant_jobneeddetails_jobneed_question_uk',
                violation_error_message=(
                    "Duplicate question not allowed for the same jobneed. "
                    "Each question can only appear once per jobneed."
                )
            ),
        ),
        migrations.AddConstraint(
            model_name='jobneeddetails',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'jobneed', 'seqno'],
                name='tenant_jobneeddetails_jobneed_seqno_uk',
                violation_error_message=(
                    "Duplicate sequence number not allowed for the same jobneed. "
                    "Each seqno must be unique within a jobneed."
                )
            ),
        ),

        # Add tenant indexes
        migrations.AddIndex(
            model_name='jobneeddetails',
            index=models.Index(fields=['tenant', 'jobneed'], name='jnd_tenant_jobneed_idx'),
        ),
        migrations.AddIndex(
            model_name='jobneeddetails',
            index=models.Index(fields=['tenant', 'question'], name='jnd_tenant_question_idx'),
        ),

        # =====================================================================
        # ASSET MODEL
        # =====================================================================

        # Remove old constraint
        migrations.RemoveConstraint(
            model_name='asset',
            name='assetcode_client_uk',
        ),

        # Add new constraint with tenant
        migrations.AddConstraint(
            model_name='asset',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'assetcode', 'bu', 'client'],
                name='tenant_assetcode_client_uk'
            ),
        ),

        # Add tenant indexes
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'cdtz'], name='asset_tenant_cdtz_idx'),
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'identifier'], name='asset_tenant_identifier_idx'),
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'enable'], name='asset_tenant_enable_idx'),
        ),

        # =====================================================================
        # ASSETLOG MODEL
        # =====================================================================

        # Add tenant indexes for AssetLog
        migrations.AddIndex(
            model_name='assetlog',
            index=models.Index(fields=['tenant', 'asset'], name='assetlog_tenant_asset_idx'),
        ),
        migrations.AddIndex(
            model_name='assetlog',
            index=models.Index(fields=['tenant', 'cdtz'], name='assetlog_tenant_cdtz_idx'),
        ),
    ]
