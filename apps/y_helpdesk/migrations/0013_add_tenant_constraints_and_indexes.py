"""
Migration to add tenant-aware constraints and indexes to y_helpdesk models.

This migration updates Ticket and EscalationMatrix models to:
1. Include tenant in unique constraints for proper multi-tenant isolation
2. Add performance indexes on tenant+field combinations

Phase 1: Multi-Tenant Security Hardening (Sprint 1)
Date: 2025-10-27
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('y_helpdesk', '0012_extract_ticket_workflow'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # =====================================================================
        # TICKET MODEL
        # =====================================================================

        # Remove old constraint
        migrations.RemoveConstraint(
            model_name='ticket',
            name='bu_id_uk',
        ),

        # Add new constraint with tenant
        migrations.AddConstraint(
            model_name='ticket',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'bu', 'id', 'client'],
                name='tenant_bu_id_uk'
            ),
        ),

        # Add tenant indexes
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['tenant', 'cdtz'], name='ticket_tenant_cdtz_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['tenant', 'status'], name='ticket_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['tenant', 'priority'], name='ticket_tenant_priority_idx'),
        ),

        # =====================================================================
        # ESCALATIONMATRIX MODEL
        # =====================================================================

        # Add tenant indexes
        migrations.AddIndex(
            model_name='escalationmatrix',
            index=models.Index(fields=['tenant', 'job'], name='escmatrix_tenant_job_idx'),
        ),
        migrations.AddIndex(
            model_name='escalationmatrix',
            index=models.Index(fields=['tenant', 'level'], name='escmatrix_tenant_level_idx'),
        ),
    ]
