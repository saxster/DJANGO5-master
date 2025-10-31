"""
Data migration to populate tenant field for existing work order records.

Assigns all existing records without a tenant to the default tenant.

Phase 1: Multi-Tenant Security Hardening (Sprint 1)
Date: 2025-10-27
"""

from django.db import migrations


def populate_tenant_field(apps, schema_editor):
    """Populate tenant field for all existing records."""
    Tenant = apps.get_model('tenants', 'Tenant')
    Wom = apps.get_model('work_order_management', 'Wom')
    Vendor = apps.get_model('work_order_management', 'Vendor')
    WomDetails = apps.get_model('work_order_management', 'WomDetails')
    Approver = apps.get_model('work_order_management', 'Approver')

    # Get or create default tenant
    default_tenant, created = Tenant.objects.using('default').get_or_create(
        subdomain_prefix='default',
        defaults={'tenantname': 'Default Tenant'}
    )

    if created:
        print(f"Created default tenant: {default_tenant.tenantname}")

    # Populate tenant for each model
    models_to_update = [
        ('Wom', Wom),
        ('Vendor', Vendor),
        ('WomDetails', WomDetails),
        ('Approver', Approver),
    ]

    for model_name, Model in models_to_update:
        updated_count = Model.objects.filter(tenant__isnull=True).update(
            tenant=default_tenant
        )
        print(f"Updated {updated_count} {model_name} records with default tenant")


def reverse_populate_tenant(apps, schema_editor):
    """Reverse migration: Set tenant back to NULL."""
    Tenant = apps.get_model('tenants', 'Tenant')
    Wom = apps.get_model('work_order_management', 'Wom')
    Vendor = apps.get_model('work_order_management', 'Vendor')
    WomDetails = apps.get_model('work_order_management', 'WomDetails')
    Approver = apps.get_model('work_order_management', 'Approver')

    try:
        default_tenant = Tenant.objects.using('default').get(subdomain_prefix='default')

        models_to_revert = [
            ('Wom', Wom),
            ('Vendor', Vendor),
            ('WomDetails', WomDetails),
            ('Approver', Approver),
        ]

        for model_name, Model in models_to_revert:
            reverted_count = Model.objects.filter(tenant=default_tenant).update(tenant=None)
            print(f"Reverted {reverted_count} {model_name} records to NULL tenant")

    except Tenant.DoesNotExist:
        print("Default tenant not found, skipping reversal")


class Migration(migrations.Migration):

    dependencies = [
        ('work_order_management', '0002_add_tenant_constraints_and_indexes'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            populate_tenant_field,
            reverse_code=reverse_populate_tenant
        ),
    ]
