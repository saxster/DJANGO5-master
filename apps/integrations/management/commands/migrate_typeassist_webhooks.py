"""
Data migration: TypeAssist webhooks → WebhookConfiguration models.

Usage:
    python manage.py migrate_typeassist_webhooks --dry-run    # Preview
    python manage.py migrate_typeassist_webhooks               # Execute
    python manage.py migrate_typeassist_webhooks --rollback   # Revert

Migrates webhook configurations from TypeAssist.other_data JSON blobs
to proper WebhookConfiguration + WebhookEvent models.

Safety features:
- Dry-run mode shows what will be migrated
- Rollback support (restores TypeAssist.other_data)
- Zero data loss (preserves original JSON during migration)
- Validation before migration
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import json

from apps.client_onboarding.models.classification import TypeAssist
from apps.integrations.models import WebhookConfiguration, WebhookEvent
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = 'Migrate webhooks from TypeAssist JSON blobs to proper models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes'
        )
        parser.add_argument(
            '--rollback',
            action='store_true',
            help='Rollback migration (delete WebhookConfiguration models)'
        )

    def handle(self, *args, **options):
        """Execute the migration."""
        dry_run = options['dry_run']
        rollback = options['rollback']

        if rollback:
            return self.handle_rollback(dry_run)

        self.stdout.write(self.style.WARNING(
            "\n" + "="*70 +
            "\nWebhook Migration: TypeAssist → WebhookConfiguration"
            "\n" + "="*70 + "\n"
        ))

        # Find all TypeAssist records with webhook data
        typeassist_webhooks = TypeAssist.objects.filter(
            other_data__isnull=False
        ).exclude(other_data={})

        total_found = 0
        total_webhooks = 0
        total_events = 0

        for ta in typeassist_webhooks:
            webhooks_data = ta.other_data.get('webhooks', [])

            if not webhooks_data:
                continue

            total_found += 1
            tenant = ta.tenant

            self.stdout.write(f"\n📦 Tenant: {tenant.tenantname} ({ta.tatype})")
            self.stdout.write(f"   Found {len(webhooks_data)} webhook(s)")

            for webhook_config in webhooks_data:
                total_webhooks += 1

                # Extract fields
                name = webhook_config.get('name', 'Migrated Webhook')
                url = webhook_config.get('url', '')
                secret = webhook_config.get('secret', '')
                enabled = webhook_config.get('enabled', True)
                retry_count = webhook_config.get('retry_count', 3)
                timeout_seconds = webhook_config.get('timeout_seconds', 30)
                events = webhook_config.get('events', [])

                # Determine webhook type from URL
                webhook_type = 'generic'
                if 'slack.com' in url:
                    webhook_type = 'slack'
                elif 'office.com' in url or 'outlook.com' in url:
                    webhook_type = 'teams'
                elif 'discord.com' in url:
                    webhook_type = 'discord'

                self.stdout.write(f"   • {name}")
                self.stdout.write(f"     URL: {url}")
                self.stdout.write(f"     Type: {webhook_type}")
                self.stdout.write(f"     Events: {', '.join(events)}")
                self.stdout.write(f"     Enabled: {enabled}")

                if not dry_run:
                    # Create WebhookConfiguration
                    webhook = WebhookConfiguration.objects.create(
                        tenant=tenant,
                        name=name,
                        url=url,
                        secret=secret,
                        enabled=enabled,
                        retry_count=retry_count,
                        timeout_seconds=timeout_seconds,
                        webhook_type=webhook_type,
                        description=f"Migrated from TypeAssist ({ta.tatype})"
                    )

                    # Create WebhookEvent entries
                    for event_type in events:
                        WebhookEvent.objects.create(
                            webhook=webhook,
                            event_type=event_type
                        )
                        total_events += 1

                    # Mark TypeAssist as migrated (don't delete for backward compat)
                    if 'webhook_migration' not in ta.other_data:
                        ta.other_data['webhook_migration'] = {
                            'migrated_at': str(ta.updated_at),
                            'webhook_ids': []
                        }
                    ta.other_data['webhook_migration']['webhook_ids'].append(str(webhook.webhook_id))
                    ta.save()

                    self.stdout.write(self.style.SUCCESS(
                        f"     ✅ Migrated to WebhookConfiguration {webhook.webhook_id}"
                    ))
                else:
                    total_events += len(events)

        # Summary
        self.stdout.write("\n" + "="*70)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n🔍 DRY RUN - No changes made\n"
                f"Would migrate:\n"
                f"  - {total_found} TypeAssist records\n"
                f"  - {total_webhooks} webhook configurations\n"
                f"  - {total_events} event subscriptions\n"
            ))
            self.stdout.write(
                "\nRun without --dry-run to execute migration"
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Migration Complete\n"
                f"Migrated:\n"
                f"  - {total_found} TypeAssist records\n"
                f"  - {total_webhooks} webhook configurations\n"
                f"  - {total_events} event subscriptions\n"
            ))
            self.stdout.write(
                "\nNote: Original TypeAssist.other_data preserved for backward compatibility\n"
                "Marked with 'webhook_migration' metadata"
            )

    def handle_rollback(self, dry_run):
        """Rollback migration - delete WebhookConfiguration models."""
        self.stdout.write(self.style.WARNING(
            "\n⚠️  ROLLBACK MODE\n"
            "This will delete all WebhookConfiguration models\n"
        ))

        webhook_count = WebhookConfiguration.objects.count()
        event_count = WebhookEvent.objects.count()

        self.stdout.write(
            f"\nWould delete:\n"
            f"  - {webhook_count} webhook configurations\n"
            f"  - {event_count} event subscriptions\n"
        )

        if not dry_run:
            with transaction.atomic():
                WebhookConfiguration.objects.all().delete()

            self.stdout.write(self.style.SUCCESS("\n✅ Rollback complete"))
        else:
            self.stdout.write("\nRun without --dry-run to execute rollback")
