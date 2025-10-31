"""
Data migration to populate tenant field for existing user records.

Assigns all existing records without a tenant to the default tenant.

Phase 1: Multi-Tenant Security Hardening (Sprint 1)
Date: 2025-10-27
"""

from django.db import migrations


def populate_tenant_field(apps, schema_editor):
    """Populate tenant field for all existing user records."""
    Tenant = apps.get_model('tenants', 'Tenant')
    People = apps.get_model('peoples', 'People')

    # Get or create default tenant
    default_tenant, created = Tenant.objects.using('default').get_or_create(
        subdomain_prefix='default',
        defaults={'tenantname': 'Default Tenant'}
    )

    if created:
        print(f"Created default tenant: {default_tenant.tenantname}")

    # Populate tenant
    updated_count = People.objects.filter(tenant__isnull=True).update(
        tenant=default_tenant
    )
    print(f"Updated {updated_count} People records with default tenant")


def reverse_populate_tenant(apps, schema_editor):
    """Reverse migration: Set tenant back to NULL."""
    Tenant = apps.get_model('tenants', 'Tenant')
    People = apps.get_model('peoples', 'People')

    try:
        default_tenant = Tenant.objects.using('default').get(subdomain_prefix='default')
        reverted_count = People.objects.filter(tenant=default_tenant).update(tenant=None)
        print(f"Reverted {reverted_count} People records to NULL tenant")
    except Tenant.DoesNotExist:
        print("Default tenant not found, skipping reversal")


class Migration(migrations.Migration):

    dependencies = [
        ('peoples', '0008_add_tenant_indexes'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            populate_tenant_field,
            reverse_code=reverse_populate_tenant
        ),
    ]
