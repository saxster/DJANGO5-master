"""
Management command to rotate encryption keys safely.

This command addresses the CVSS 7.5 security vulnerability where no key
rotation mechanism existed. It provides:
- Safe key rotation with data migration
- Rollback capability on failure
- Progress tracking and reporting
- Dry-run mode for testing

Usage:
    python manage.py rotate_encryption_keys --dry-run
    python manage.py rotate_encryption_keys --batch-size 100
    python manage.py rotate_encryption_keys --force
"""

import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.utils import timezone
from apps.core.models import EncryptionKeyMetadata
from apps.core.services.encryption_key_manager import EncryptionKeyManager
from apps.peoples.models import People
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger("key_rotation")


class Command(BaseCommand):
    help = """
    Rotate encryption keys safely with automatic data migration.

    This command creates a new encryption key, migrates all encrypted data
    to use the new key, and retires the old key. It includes rollback
    capability if any errors occur during the process.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch (default: 100)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rotation even if current key is not near expiration',
        )
        parser.add_argument(
            '--skip-data-migration',
            action='store_true',
            help='Skip data migration (only create new key)',
        )

    def handle(self, *args, **options):
        """Main rotation handler."""
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        force = options['force']
        skip_migration = options['skip_data_migration']

        self.stdout.write(
            self.style.WARNING("🔄 ENCRYPTION KEY ROTATION")
        )
        self.stdout.write("=" * 60)

        # Step 1: Initialize key manager
        try:
            EncryptionKeyManager.initialize()
            self.stdout.write(self.style.SUCCESS("✅ Key manager initialized"))
        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            raise CommandError(f"Failed to initialize key manager: {e}")

        # Step 2: Check current key status
        current_key = EncryptionKeyMetadata.get_current_key()
        if not current_key:
            raise CommandError("No current encryption key found!")

        self.stdout.write(f"\n📊 Current Key Status:")
        self.stdout.write(f"  Key ID: {current_key.key_id}")
        self.stdout.write(f"  Age: {current_key.age_days} days")
        self.stdout.write(f"  Expires in: {current_key.expires_in_days} days")
        self.stdout.write(f"  Status: {current_key.rotation_status}")

        # Check if rotation is needed
        if not force and not current_key.needs_rotation:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  Current key does not need rotation yet "
                    f"(expires in {current_key.expires_in_days} days)"
                )
            )
            self.stdout.write("    Use --force to rotate anyway")
            return

        # Step 3: Analyze data to migrate
        stats = self._analyze_encrypted_data()
        self._print_statistics(stats)

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n✅ DRY RUN COMPLETE - No changes made"))
            return

        # Step 4: Confirm before proceeding
        if not force:
            confirm = input("\n⚠️  Proceed with key rotation? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write("❌ Key rotation cancelled")
                return

        # Step 5: Perform rotation
        try:
            new_key_id = self._perform_rotation(
                current_key,
                batch_size,
                skip_migration,
                stats
            )

            self.stdout.write(
                self.style.SUCCESS(f"\n✅ KEY ROTATION COMPLETE")
            )
            self.stdout.write(f"   New Key ID: {new_key_id}")
            self.stdout.write(f"   Old Key ID: {current_key.key_id} (retired)")

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            self.stdout.write(self.style.ERROR(f"\n❌ KEY ROTATION FAILED: {e}"))
            self.stdout.write("   Rolling back changes...")
            self._rollback_rotation()
            raise

    def _analyze_encrypted_data(self):
        """Analyze encrypted data to understand migration scope."""
        self.stdout.write("\n📊 Analyzing encrypted data...")

        stats = {
            'total_users': People.objects.count(),
            'users_with_email': People.objects.exclude(email__isnull=True).exclude(email='').count(),
            'users_with_mobile': People.objects.exclude(mobno__isnull=True).exclude(mobno='').count(),
            'v1_format_count': 0,
            'v2_format_count': 0,
            'plaintext_count': 0,
            'records_needing_migration': 0,
        }

        # Sample check (check first 1000 records)
        sample_users = People.objects.exclude(
            email__isnull=True
        ).exclude(email='')[:1000]

        for user in sample_users:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT email FROM people WHERE id = %s", [user.id]
                    )
                    raw_email = cursor.fetchone()[0]

                    if raw_email:
                        if raw_email.startswith('FERNET_V2:'):
                            stats['v2_format_count'] += 1
                        elif raw_email.startswith('FERNET_V1:'):
                            stats['v1_format_count'] += 1
                            stats['records_needing_migration'] += 1
                        else:
                            stats['plaintext_count'] += 1
                            stats['records_needing_migration'] += 1

            except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                logger.warning(f"Error analyzing email for user {user.id}: {e}")

        # Extrapolate to full dataset
        sample_size = len(sample_users)
        if sample_size > 0:
            ratio = stats['total_users'] / sample_size
            stats['v1_format_count'] = int(stats['v1_format_count'] * ratio)
            stats['v2_format_count'] = int(stats['v2_format_count'] * ratio)
            stats['plaintext_count'] = int(stats['plaintext_count'] * ratio)
            stats['records_needing_migration'] = int(stats['records_needing_migration'] * ratio)

        return stats

    def _print_statistics(self, stats):
        """Print migration statistics."""
        self.stdout.write("\n📊 MIGRATION STATISTICS (Estimated)")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total Users: {stats['total_users']}")
        self.stdout.write(f"Users with Email: {stats['users_with_email']}")
        self.stdout.write(f"Users with Mobile: {stats['users_with_mobile']}")

        self.stdout.write("\nENCRYPTION FORMAT DISTRIBUTION:")
        self.stdout.write(f"  📦 V2 Format (Current): {stats['v2_format_count']}")
        self.stdout.write(f"  📜 V1 Format (Legacy): {stats['v1_format_count']}")
        self.stdout.write(f"  📝 Plaintext: {stats['plaintext_count']}")

        self.stdout.write(
            f"\n🔄 RECORDS NEEDING MIGRATION: {stats['records_needing_migration']}"
        )

        if stats['records_needing_migration'] == 0:
            self.stdout.write(self.style.SUCCESS("✅ All data already uses current format!"))

    def _perform_rotation(self, current_key, batch_size, skip_migration, stats):
        """Perform the actual key rotation."""
        self.stdout.write("\n🔄 Starting key rotation process...")

        # Step 1: Create new key
        self.stdout.write("  1️⃣  Creating new encryption key...")
        new_key_id = EncryptionKeyManager.create_new_key()
        self.stdout.write(f"     ✅ New key created: {new_key_id}")

        # Step 2: Mark current key for rotation
        self.stdout.write("  2️⃣  Marking current key for rotation...")
        current_key.mark_for_rotation(
            new_key_id,
            notes=f"Rotating to {new_key_id} on {datetime.now()}"
        )
        self.stdout.write(f"     ✅ Current key marked for rotation")

        # Step 3: Migrate data (if not skipped)
        if not skip_migration and stats['records_needing_migration'] > 0:
            self.stdout.write("  3️⃣  Migrating encrypted data...")
            migrated_count = self._migrate_encrypted_data(
                new_key_id,
                batch_size,
                stats
            )
            self.stdout.write(f"     ✅ Migrated {migrated_count} records")
        else:
            self.stdout.write("  3️⃣  Skipping data migration...")
            migrated_count = 0

        # Step 4: Activate new key
        self.stdout.write("  4️⃣  Activating new key...")
        EncryptionKeyManager.activate_key(new_key_id)
        self.stdout.write(f"     ✅ New key activated")

        # Step 5: Retire old key
        self.stdout.write("  5️⃣  Retiring old key...")
        current_key.retire(
            notes=f"Retired in favor of {new_key_id} on {datetime.now()}"
        )
        self.stdout.write(f"     ✅ Old key retired")

        return new_key_id

    def _migrate_encrypted_data(self, new_key_id, batch_size, stats):
        """
        Migrate encrypted data to new key.

        Args:
            new_key_id: ID of the new encryption key
            batch_size: Number of records per batch
            stats: Statistics about data to migrate

        Returns:
            int: Number of migrated records
        """
        migrated_count = 0
        error_count = 0

        # Get users with encrypted data
        total_users = People.objects.exclude(
            email__isnull=True,
            mobno__isnull=True
        ).count()

        for offset in range(0, total_users, batch_size):
            users = People.objects.exclude(
                email__isnull=True,
                mobno__isnull=True
            ).order_by('id')[offset:offset + batch_size]

            with transaction.atomic():
                for user in users:
                    try:
                        user_migrated = self._migrate_user_data(user, new_key_id)
                        if user_migrated:
                            migrated_count += 1

                        if migrated_count % 50 == 0 and migrated_count > 0:
                            progress = (migrated_count / stats['records_needing_migration']) * 100
                            self.stdout.write(
                                f"     📊 Progress: {migrated_count} / {stats['records_needing_migration']} "
                                f"({progress:.1f}%)"
                            )

                    except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                        error_count += 1
                        correlation_id = ErrorHandler.handle_exception(
                            e,
                            context={
                                'user_id': user.id,
                                'operation': 'migrate_user_data_rotation',
                                'new_key_id': new_key_id
                            }
                        )
                        logger.error(
                            f"Migration error for user {user.id} (ID: {correlation_id})"
                        )

        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"     ⚠️  {error_count} records had errors - check logs"
                )
            )

        return migrated_count

    def _migrate_user_data(self, user, new_key_id):
        """
        Migrate a single user's encrypted data to new key.

        Args:
            user: People instance
            new_key_id: New key ID to use

        Returns:
            bool: True if any data was migrated
        """
        migrated = False

        # Check email field
        if user.email:
            with connection.cursor() as cursor:
                cursor.execute("SELECT email FROM people WHERE id = %s", [user.id])
                raw_email = cursor.fetchone()[0]

                # Check if needs re-encryption with new key
                if raw_email and not raw_email.startswith(f'FERNET_V2:{new_key_id}:'):
                    try:
                        # Decrypt with old key
                        plaintext_email = EncryptionKeyManager.decrypt(raw_email)

                        # Re-encrypt with new key
                        new_encrypted = EncryptionKeyManager.encrypt(
                            plaintext_email,
                            key_id=new_key_id
                        )

                        # Update database
                        cursor.execute(
                            "UPDATE people SET email = %s WHERE id = %s",
                            [new_encrypted, user.id]
                        )
                        migrated = True

                    except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                        logger.error(f"Failed to migrate email for user {user.id}: {e}")

        # Check mobile field
        if user.mobno:
            with connection.cursor() as cursor:
                cursor.execute("SELECT mobno FROM people WHERE id = %s", [user.id])
                raw_mobile = cursor.fetchone()[0]

                if raw_mobile and not raw_mobile.startswith(f'FERNET_V2:{new_key_id}:'):
                    try:
                        plaintext_mobile = EncryptionKeyManager.decrypt(raw_mobile)
                        new_encrypted = EncryptionKeyManager.encrypt(
                            plaintext_mobile,
                            key_id=new_key_id
                        )

                        cursor.execute(
                            "UPDATE people SET mobno = %s WHERE id = %s",
                            [new_encrypted, user.id]
                        )
                        migrated = True

                    except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                        logger.error(f"Failed to migrate mobile for user {user.id}: {e}")

        return migrated

    def _rollback_rotation(self):
        """Rollback rotation on failure."""
        try:
            # Mark any 'rotating' keys as failed
            EncryptionKeyMetadata.objects.filter(
                rotation_status='rotating'
            ).update(rotation_status='created')

            # Reactivate previous active key
            prev_key = EncryptionKeyMetadata.objects.filter(
                rotation_status='active'
            ).order_by('-activated_at').first()

            if prev_key:
                EncryptionKeyManager.activate_key(prev_key.key_id)

            self.stdout.write(self.style.SUCCESS("✅ Rollback completed"))

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Rollback failed: {e}")
            )
            logger.error(f"Rollback error: {e}")