"""
Data migration to populate tenant field for existing records.

Assigns all existing records without a tenant to the default tenant.
This ensures backward compatibility while enabling multi-tenant isolation.

Phase 1: Multi-Tenant Security Hardening (Sprint 1)
Date: 2025-10-27
"""

from django.db import migrations


def populate_tenant_field(apps, schema_editor):
    """
    Populate tenant field for all existing records.

    Strategy:
    1. Get or create a default tenant
    2. Assign all records with NULL tenant to default tenant
    3. Log the number of records updated
    """
    Tenant = apps.get_model('tenants', 'Tenant')
    Job = apps.get_model('activity', 'Job')
    Jobneed = apps.get_model('activity', 'Jobneed')
    JobneedDetails = apps.get_model('activity', 'JobneedDetails')
    Asset = apps.get_model('activity', 'Asset')
    AssetLog = apps.get_model('activity', 'AssetLog')

    # Get or create default tenant
    default_tenant, created = Tenant.objects.using('default').get_or_create(
        subdomain_prefix='default',
        defaults={
            'tenantname': 'Default Tenant',
        }
    )

    if created:
        print(f"Created default tenant: {default_tenant.tenantname}")
    else:
        print(f"Using existing default tenant: {default_tenant.tenantname}")

    # Populate tenant for each model
    models_to_update = [
        ('Job', Job),
        ('Jobneed', Jobneed),
        ('JobneedDetails', JobneedDetails),
        ('Asset', Asset'),
        ('AssetLog', AssetLog),
    ]

    for model_name, Model in models_to_update:
        updated_count = Model.objects.filter(tenant__isnull=True).update(
            tenant=default_tenant
        )
        print(f"Updated {updated_count} {model_name} records with default tenant")


def reverse_populate_tenant(apps, schema_editor):
    """
    Reverse migration: Set tenant back to NULL for default tenant records.

    This allows rolling back the migration if needed.
    """
    Tenant = apps.get_model('tenants', 'Tenant')
    Job = apps.get_model('activity', 'Job')
    Jobneed = apps.get_model('activity', 'Jobneed')
    JobneedDetails = apps.get_model('activity', 'JobneedDetails')
    Asset = apps.get_model('activity', 'Asset')
    AssetLog = apps.get_model('activity', 'AssetLog')

    try:
        default_tenant = Tenant.objects.using('default').get(subdomain_prefix='default')

        models_to_revert = [
            ('Job', Job),
            ('Jobneed', Jobneed),
            ('JobneedDetails', JobneedDetails),
            ('Asset', Asset),
            ('AssetLog', AssetLog),
        ]

        for model_name, Model in models_to_revert:
            reverted_count = Model.objects.filter(tenant=default_tenant).update(
                tenant=None
            )
            print(f"Reverted {reverted_count} {model_name} records to NULL tenant")

    except Tenant.DoesNotExist:
        print("Default tenant not found, skipping reversal")


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0011_add_tenant_constraints_and_indexes'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            populate_tenant_field,
            reverse_code=reverse_populate_tenant
        ),
    ]
