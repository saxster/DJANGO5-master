"""
Management command to migrate existing insecure encryption to secure encryption.

This command safely migrates email and mobile number data from the old insecure
zlib compression format to cryptographically secure Fernet encryption.

CRITICAL: This addresses the security vulnerability where sensitive data was
stored using only zlib compression instead of real encryption.
"""
import logging
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from apps.peoples.models import People
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger("secure_migration")


class Command(BaseCommand):
    help = """
    Migrate People model email and mobile data from insecure zlib compression
    to cryptographically secure Fernet encryption.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
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
            help='Force migration even if validation fails',
        )

    def handle(self, *args, **options):
        """Main migration handler."""
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        force = options['force']

        self.stdout.write(
            self.style.WARNING("🚨 CRITICAL SECURITY MIGRATION")
        )
        self.stdout.write(
            "Migrating from insecure zlib compression to secure encryption..."
        )

        if not force:
            # Validate encryption setup first
            try:
                if not SecureEncryptionService.validate_encryption_setup():
                    self.stdout.write(
                        self.style.ERROR("❌ Encryption setup validation failed!")
                    )
                    return
            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Encryption validation error: {e}")
                )
                return

        # Get migration statistics
        stats = self._analyze_data()
        self._print_statistics(stats)

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("✅ DRY RUN COMPLETE - No changes made")
            )
            return

        # Confirm before proceeding
        if not force:
            confirm = input("\nProceed with migration? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write("❌ Migration cancelled")
                return

        # Perform migration
        self._perform_migration(batch_size, stats)

    def _analyze_data(self):
        """Analyze current data to understand migration scope."""
        self.stdout.write("📊 Analyzing current encryption status...")

        stats = {
            'total_users': People.objects.count(),
            'users_with_email': People.objects.exclude(email__isnull=True).exclude(email='').count(),
            'users_with_mobile': People.objects.exclude(mobno__isnull=True).exclude(mobno='').count(),
            'secure_encrypted_emails': 0,
            'legacy_encrypted_emails': 0,
            'plaintext_emails': 0,
            'secure_encrypted_mobiles': 0,
            'legacy_encrypted_mobiles': 0,
            'plaintext_mobiles': 0,
            'migration_needed': 0,
        }

        # Analyze email encryption status
        for user in People.objects.exclude(email__isnull=True).exclude(email='').iterator():
            try:
                # This uses the raw database value
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT email FROM people WHERE id = %s", [user.id]
                    )
                    raw_email = cursor.fetchone()[0]

                    if raw_email:
                        if raw_email.startswith('FERNET_V1:'):
                            stats['secure_encrypted_emails'] += 1
                        elif raw_email.startswith('ENC_V1:'):
                            stats['legacy_encrypted_emails'] += 1
                        else:
                            stats['plaintext_emails'] += 1
            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
                logger.warning(f"Error analyzing email for user {user.id}: {e}")

        # Analyze mobile encryption status
        for user in People.objects.exclude(mobno__isnull=True).exclude(mobno='').iterator():
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT mobno FROM people WHERE id = %s", [user.id]
                    )
                    raw_mobile = cursor.fetchone()[0]

                    if raw_mobile:
                        if raw_mobile.startswith('FERNET_V1:'):
                            stats['secure_encrypted_mobiles'] += 1
                        elif raw_mobile.startswith('ENC_V1:'):
                            stats['legacy_encrypted_mobiles'] += 1
                        else:
                            stats['plaintext_mobiles'] += 1
            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
                logger.warning(f"Error analyzing mobile for user {user.id}: {e}")

        stats['migration_needed'] = (
            stats['legacy_encrypted_emails'] + stats['plaintext_emails'] +
            stats['legacy_encrypted_mobiles'] + stats['plaintext_mobiles']
        )

        return stats

    def _print_statistics(self, stats):
        """Print migration statistics."""
        self.stdout.write("\n📊 MIGRATION STATISTICS")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Total Users: {stats['total_users']}")
        self.stdout.write(f"Users with Email: {stats['users_with_email']}")
        self.stdout.write(f"Users with Mobile: {stats['users_with_mobile']}")

        self.stdout.write("\nEMAIL ENCRYPTION STATUS:")
        self.stdout.write(f"  ✅ Secure: {stats['secure_encrypted_emails']}")
        self.stdout.write(f"  ⚠️  Legacy: {stats['legacy_encrypted_emails']}")
        self.stdout.write(f"  🚨 Plaintext: {stats['plaintext_emails']}")

        self.stdout.write("\nMOBILE ENCRYPTION STATUS:")
        self.stdout.write(f"  ✅ Secure: {stats['secure_encrypted_mobiles']}")
        self.stdout.write(f"  ⚠️  Legacy: {stats['legacy_encrypted_mobiles']}")
        self.stdout.write(f"  🚨 Plaintext: {stats['plaintext_mobiles']}")

        self.stdout.write(f"\n🔄 TOTAL RECORDS NEEDING MIGRATION: {stats['migration_needed']}")

        if stats['migration_needed'] == 0:
            self.stdout.write(self.style.SUCCESS("✅ All data is already securely encrypted!"))

    def _perform_migration(self, batch_size, stats):
        """Perform the actual data migration."""
        if stats['migration_needed'] == 0:
            return

        self.stdout.write("\n🔄 Starting migration...")

        migrated_count = 0
        error_count = 0

        # Migrate in batches to avoid memory issues
        total_users = People.objects.exclude(email__isnull=True, mobno__isnull=True).count()

        for offset in range(0, total_users, batch_size):
            users = People.objects.exclude(
                email__isnull=True, mobno__isnull=True
            ).order_by('id')[offset:offset + batch_size]

            with transaction.atomic():
                for user in users:
                    try:
                        user_migrated = self._migrate_user_data(user)
                        if user_migrated:
                            migrated_count += 1

                        if migrated_count % 50 == 0:
                            self.stdout.write(f"📊 Migrated {migrated_count} records...")

                    except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                        error_count += 1
                        correlation_id = ErrorHandler.handle_exception(
                            e,
                            context={'user_id': user.id, 'operation': 'migrate_user_data'}
                        )
                        logger.error(f"Migration error for user {user.id} (ID: {correlation_id})")

        self.stdout.write("\n✅ MIGRATION COMPLETE")
        self.stdout.write(f"📊 Migrated: {migrated_count} records")
        self.stdout.write(f"❌ Errors: {error_count} records")

        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f"⚠️  {error_count} records had errors - check logs")
            )

    def _migrate_user_data(self, user):
        """
        Migrate a single user's data from insecure to secure encryption.

        Args:
            user: People instance to migrate

        Returns:
            bool: True if any data was migrated
        """
        migrated = False

        # Check email field
        if user.email:
            with connection.cursor() as cursor:
                cursor.execute("SELECT email FROM people WHERE id = %s", [user.id])
                raw_email = cursor.fetchone()[0]

                if raw_email and not raw_email.startswith('FERNET_V1:'):
                    # Need to migrate email
                    try:
                        if raw_email.startswith('ENC_V1:'):
                            # Legacy encrypted format
                            legacy_payload = raw_email[len('ENC_V1:'):]
                            migration_successful, result = SecureEncryptionService.migrate_legacy_data(legacy_payload)

                            if migration_successful:
                                # Update database directly with secure encryption
                                cursor.execute(
                                    "UPDATE people SET email = %s WHERE id = %s",
                                    [result, user.id]
                                )
                                migrated = True
                        else:
                            # Plaintext - encrypt directly
                            secure_email = SecureEncryptionService.encrypt(raw_email)
                            cursor.execute(
                                "UPDATE people SET email = %s WHERE id = %s",
                                [secure_email, user.id]
                            )
                            migrated = True
                    except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                        logger.error(f"Failed to migrate email for user {user.id}: {e}")

        # Check mobile field
        if user.mobno:
            with connection.cursor() as cursor:
                cursor.execute("SELECT mobno FROM people WHERE id = %s", [user.id])
                raw_mobile = cursor.fetchone()[0]

                if raw_mobile and not raw_mobile.startswith('FERNET_V1:'):
                    # Need to migrate mobile
                    try:
                        if raw_mobile.startswith('ENC_V1:'):
                            # Legacy encrypted format
                            legacy_payload = raw_mobile[len('ENC_V1:'):]
                            migration_successful, result = SecureEncryptionService.migrate_legacy_data(legacy_payload)

                            if migration_successful:
                                cursor.execute(
                                    "UPDATE people SET mobno = %s WHERE id = %s",
                                    [result, user.id]
                                )
                                migrated = True
                        else:
                            # Plaintext - encrypt directly
                            secure_mobile = SecureEncryptionService.encrypt(raw_mobile)
                            cursor.execute(
                                "UPDATE people SET mobno = %s WHERE id = %s",
                                [secure_mobile, user.id]
                            )
                            migrated = True
                    except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                        logger.error(f"Failed to migrate mobile for user {user.id}: {e}")

        return migrated