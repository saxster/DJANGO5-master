"""
Management command to audit attachment ownership and permissions.

Identifies:
- Orphaned attachments (no owner, no tenant, no creator)
- Cross-tenant inconsistencies (owner tenant != attachment tenant)
- Attachments without business unit assignments
- Attachments with missing permission metadata

Usage:
    python manage.py audit_attachment_permissions --verbose
    python manage.py audit_attachment_permissions --fix-orphaned
    python manage.py audit_attachment_permissions --tenant=TenantA
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, Count, F
from django.db.models.functions import Length
from django.contrib.auth import get_user_model

from apps.activity.models import Attachment
from apps.tenants.models import Tenant

People = get_user_model()


class Command(BaseCommand):
    help = 'Audit attachment ownership and permission metadata for security compliance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each finding'
        )
        parser.add_argument(
            '--tenant',
            type=str,
            help='Filter audit to specific tenant (tenantname)'
        )
        parser.add_argument(
            '--fix-orphaned',
            action='store_true',
            help='Attempt to fix orphaned attachments by assigning default values'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export findings to CSV file'
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        tenant_filter = options.get('tenant')
        fix_orphaned = options['fix-orphaned']
        export_path = options.get('export')

        self.stdout.write(self.style.SUCCESS('\n=== Attachment Permission Audit ===\n'))

        # Filter by tenant if specified
        queryset = Attachment.objects.all()
        if tenant_filter:
            try:
                tenant = Tenant.objects.get(tenantname=tenant_filter)
                queryset = queryset.filter(tenant=tenant)
                self.stdout.write(f'Filtering to tenant: {tenant.tenantname}\n')
            except Tenant.DoesNotExist:
                raise CommandError(f'Tenant "{tenant_filter}" not found')

        total_attachments = queryset.count()
        self.stdout.write(f'Total attachments: {total_attachments}\n')

        # Track findings
        findings = []

        # 1. Orphaned Attachments (no owner, tenant, or creator)
        self.stdout.write(self.style.WARNING('\n--- Orphaned Attachments ---'))
        orphaned = queryset.filter(
            Q(owner__isnull=True) | Q(owner='')
        ).filter(
            Q(cuser__isnull=True)
        )
        orphaned_count = orphaned.count()
        self.stdout.write(f'Found: {orphaned_count}')

        if orphaned_count > 0:
            if verbose:
                for att in orphaned[:10]:  # Show first 10
                    self.stdout.write(
                        f'  ID {att.id}: {att.filename} '
                        f'(owner={att.owner}, cuser={att.cuser_id}, tenant={att.tenant_id})'
                    )
                if orphaned_count > 10:
                    self.stdout.write(f'  ... and {orphaned_count - 10} more')

            findings.append({
                'type': 'orphaned',
                'count': orphaned_count,
                'severity': 'HIGH',
                'description': 'Attachments with no owner or creator'
            })

            if fix_orphaned:
                self.stdout.write(self.style.WARNING('\nAttempting to fix orphaned attachments...'))
                fixed_count = self._fix_orphaned_attachments(orphaned)
                self.stdout.write(self.style.SUCCESS(f'Fixed {fixed_count} orphaned attachments'))

        # 2. No Tenant Assignment
        self.stdout.write(self.style.WARNING('\n--- Attachments Without Tenant ---'))
        no_tenant = queryset.filter(tenant__isnull=True)
        no_tenant_count = no_tenant.count()
        self.stdout.write(f'Found: {no_tenant_count}')

        if no_tenant_count > 0:
            if verbose:
                for att in no_tenant[:10]:
                    self.stdout.write(
                        f'  ID {att.id}: {att.filename} '
                        f'(cuser={att.cuser_id}, owner={att.owner})'
                    )
                if no_tenant_count > 10:
                    self.stdout.write(f'  ... and {no_tenant_count - 10} more')

            findings.append({
                'type': 'no_tenant',
                'count': no_tenant_count,
                'severity': 'CRITICAL',
                'description': 'Multi-tenant isolation cannot be enforced'
            })

        # 3. Cross-Tenant Inconsistencies (cuser tenant != attachment tenant)
        self.stdout.write(self.style.WARNING('\n--- Cross-Tenant Inconsistencies ---'))
        cross_tenant = queryset.filter(
            cuser__isnull=False,
            tenant__isnull=False
        ).exclude(
            cuser__tenant=F('tenant')
        )
        cross_tenant_count = cross_tenant.count()
        self.stdout.write(f'Found: {cross_tenant_count}')

        if cross_tenant_count > 0:
            if verbose:
                for att in cross_tenant[:10]:
                    cuser_tenant = att.cuser.tenant.tenantname if att.cuser and att.cuser.tenant else 'None'
                    att_tenant = att.tenant.tenantname if att.tenant else 'None'
                    self.stdout.write(
                        f'  ID {att.id}: {att.filename} '
                        f'(creator tenant: {cuser_tenant}, attachment tenant: {att_tenant})'
                    )
                if cross_tenant_count > 10:
                    self.stdout.write(f'  ... and {cross_tenant_count - 10} more')

            findings.append({
                'type': 'cross_tenant_inconsistency',
                'count': cross_tenant_count,
                'severity': 'HIGH',
                'description': 'Creator tenant differs from attachment tenant'
            })

        # 4. No Business Unit Assignment
        self.stdout.write(self.style.WARNING('\n--- Attachments Without Business Unit ---'))
        no_bu = queryset.filter(bu__isnull=True)
        no_bu_count = no_bu.count()
        self.stdout.write(f'Found: {no_bu_count}')

        if no_bu_count > 0:
            if verbose:
                for att in no_bu[:10]:
                    self.stdout.write(
                        f'  ID {att.id}: {att.filename} '
                        f'(tenant={att.tenant.tenantname if att.tenant else "None"})'
                    )
                if no_bu_count > 10:
                    self.stdout.write(f'  ... and {no_bu_count - 10} more')

            findings.append({
                'type': 'no_bu',
                'count': no_bu_count,
                'severity': 'MEDIUM',
                'description': 'Business unit access control cannot be enforced'
            })

        # 5. Invalid Owner UUIDs (not matching any attachment pattern)
        self.stdout.write(self.style.WARNING('\n--- Invalid Owner References ---'))
        invalid_owner = queryset.filter(
            owner__isnull=False
        ).exclude(
            owner=''
        ).annotate(
            owner_length=Length('owner')
        ).filter(
            # UUID should be 36 characters (with hyphens) or at least 32
            owner_length__lt=10
        )
        invalid_owner_count = invalid_owner.count()
        self.stdout.write(f'Found: {invalid_owner_count}')

        if invalid_owner_count > 0:
            if verbose:
                for att in invalid_owner[:10]:
                    self.stdout.write(
                        f'  ID {att.id}: {att.filename} '
                        f'(owner="{att.owner}" - length {len(att.owner)})'
                    )

            findings.append({
                'type': 'invalid_owner',
                'count': invalid_owner_count,
                'severity': 'MEDIUM',
                'description': 'Owner field contains invalid UUID format'
            })

        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Audit Summary ==='))
        total_issues = sum(f['count'] for f in findings)

        if total_issues == 0:
            self.stdout.write(self.style.SUCCESS('✅ No permission issues found! All attachments properly configured.'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ Found {total_issues} total permission issues'))

            for finding in findings:
                severity_style = {
                    'CRITICAL': self.style.ERROR,
                    'HIGH': self.style.WARNING,
                    'MEDIUM': self.style.WARNING,
                    'LOW': self.style.NOTICE
                }.get(finding['severity'], self.style.NOTICE)

                self.stdout.write(
                    severity_style(
                        f'  [{finding["severity"]}] {finding["type"]}: '
                        f'{finding["count"]} - {finding["description"]}'
                    )
                )

        # Export to CSV if requested
        if export_path and findings:
            self._export_to_csv(export_path, findings, queryset)
            self.stdout.write(self.style.SUCCESS(f'\n✅ Findings exported to: {export_path}'))

        self.stdout.write('\n')

    def _fix_orphaned_attachments(self, orphaned_queryset):
        """
        Attempt to fix orphaned attachments by assigning sensible defaults.

        Strategy:
        1. If attachment has a tenant but no cuser, try to find the tenant's admin
        2. If no tenant, cannot fix (requires manual intervention)
        3. Generate owner UUID if missing
        """
        import uuid
        from django.db import models

        fixed_count = 0

        for attachment in orphaned_queryset:
            try:
                # Generate owner UUID if completely missing
                if not attachment.owner or attachment.owner == '':
                    attachment.owner = str(uuid.uuid4())

                # Try to assign a creator if tenant exists
                if attachment.tenant and not attachment.cuser:
                    # Find first staff user in tenant
                    default_user = People.objects.filter(
                        tenant=attachment.tenant,
                        is_staff=True
                    ).first()

                    if default_user:
                        attachment.cuser = default_user
                        attachment.muser = default_user
                        attachment.save()
                        fixed_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  Fixed ID {attachment.id}: Assigned to {default_user.loginid}'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Cannot fix ID {attachment.id}: No staff user in tenant'
                            )
                        )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'  Error fixing ID {attachment.id}: {str(e)}'
                    )
                )

        return fixed_count

    def _export_to_csv(self, export_path, findings, queryset):
        """Export audit findings to CSV file."""
        import csv

        with open(export_path, 'w', newline='') as csvfile:
            fieldnames = [
                'attachment_id', 'filename', 'owner', 'cuser_id',
                'tenant_id', 'tenant_name', 'bu_id', 'bu_name',
                'created_date', 'issue_type'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # Write rows for each finding type
            for finding in findings:
                issue_type = finding['type']

                # Get attachments matching this issue type
                if issue_type == 'orphaned':
                    issue_attachments = queryset.filter(
                        Q(owner__isnull=True) | Q(owner='')
                    ).filter(Q(cuser__isnull=True))
                elif issue_type == 'no_tenant':
                    issue_attachments = queryset.filter(tenant__isnull=True)
                elif issue_type == 'no_bu':
                    issue_attachments = queryset.filter(bu__isnull=True)
                else:
                    continue

                for att in issue_attachments:
                    writer.writerow({
                        'attachment_id': att.id,
                        'filename': att.filename,
                        'owner': att.owner,
                        'cuser_id': att.cuser_id,
                        'tenant_id': att.tenant_id,
                        'tenant_name': att.tenant.tenantname if att.tenant else '',
                        'bu_id': att.bu_id,
                        'bu_name': att.bu.buname if att.bu else '',
                        'created_date': att.created_date.isoformat() if hasattr(att, 'created_date') else '',
                        'issue_type': issue_type
                    })
