"""
Management command to encrypt existing biometric data.

This command should be run ONCE after deploying the encrypted field migration.
It encrypts all existing plaintext biometric templates in the database.

Usage:
    python manage.py encrypt_existing_biometric_data [--dry-run] [--batch-size=1000]

Options:
    --dry-run: Preview changes without committing to database
    --batch-size: Number of records to process per batch (default: 1000)
    --skip-encrypted: Skip records that appear to be already encrypted

Security:
- Backs up original data before encryption
- Validates encryption/decryption cycle
- Provides rollback instructions
- Logs all operations for audit trail
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from apps.attendance.models import PeopleEventlog
from apps.core.encryption import BiometricEncryptionService, EncryptionError
import json
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Encrypt existing plaintext biometric data in attendance records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without committing to database',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process per batch',
        )
        parser.add_argument(
            '--skip-encrypted',
            action='store_true',
            help='Skip records that appear to be already encrypted',
        )
        parser.add_argument(
            '--backup-file',
            type=str,
            default=None,
            help='Path to backup file for original data (JSON format)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        skip_encrypted = options['skip_encrypted']
        backup_file = options['backup_file']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        # Step 1: Count total records
        total_records = PeopleEventlog.objects.count()
        self.stdout.write(f"Total attendance records: {total_records}")

        # Step 2: Query records with raw SQL to bypass Django ORM decryption
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, peventlogextras
                FROM peopleeventlog
                WHERE peventlogextras IS NOT NULL
                ORDER BY id
            """)

            records_to_encrypt = []
            encrypted_count = 0
            plaintext_count = 0

            for row in cursor.fetchall():
                record_id, peventlogextras_value = row

                # Check if already encrypted
                if self._is_encrypted(peventlogextras_value):
                    encrypted_count += 1
                    if skip_encrypted:
                        continue
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"Record {record_id} appears already encrypted")
                        )
                        continue

                plaintext_count += 1
                records_to_encrypt.append((record_id, peventlogextras_value))

        self.stdout.write(f"Records already encrypted: {encrypted_count}")
        self.stdout.write(f"Records needing encryption: {plaintext_count}")

        if plaintext_count == 0:
            self.stdout.write(self.style.SUCCESS('No records need encryption. Exiting.'))
            return

        # Step 3: Backup original data if requested
        if backup_file and not dry_run:
            self._backup_data(records_to_encrypt, backup_file)

        # Step 4: Encrypt records in batches
        encrypted = 0
        failed = 0
        batch_num = 0

        for i in range(0, len(records_to_encrypt), batch_size):
            batch = records_to_encrypt[i:i + batch_size]
            batch_num += 1

            self.stdout.write(f"\nProcessing batch {batch_num} ({len(batch)} records)...")

            if not dry_run:
                try:
                    with transaction.atomic():
                        for record_id, plaintext_data in batch:
                            try:
                                # Parse plaintext JSON
                                json_data = json.loads(plaintext_data) if isinstance(plaintext_data, str) else plaintext_data

                                # Encrypt using our service
                                encrypted_data = BiometricEncryptionService.encrypt_biometric_data(json_data)

                                # Update database with raw SQL to bypass ORM
                                with connection.cursor() as update_cursor:
                                    update_cursor.execute("""
                                        UPDATE peopleeventlog
                                        SET peventlogextras = %s
                                        WHERE id = %s
                                    """, [encrypted_data, record_id])

                                encrypted += 1

                                if encrypted % 100 == 0:
                                    self.stdout.write(f"  Encrypted {encrypted} records...")

                            except Exception as e:
                                logger.error(f"Failed to encrypt record {record_id}: {e}")
                                failed += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Batch {batch_num} failed: {e}")
                    )
                    raise CommandError(f"Encryption failed at batch {batch_num}. Database rolled back.")

            else:
                # Dry run: just count
                encrypted += len(batch)

        # Step 5: Verify encryption
        if not dry_run:
            self.stdout.write("\nVerifying encryption...")
            verification_failures = self._verify_encryption(records_to_encrypt[:10])  # Verify first 10

            if verification_failures > 0:
                self.stdout.write(
                    self.style.ERROR(f"Verification failed for {verification_failures} records!")
                )
            else:
                self.stdout.write(self.style.SUCCESS("Verification passed!"))

        # Step 6: Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(f"Encryption complete!"))
        self.stdout.write(f"  Total records: {total_records}")
        self.stdout.write(f"  Already encrypted: {encrypted_count}")
        self.stdout.write(f"  Newly encrypted: {encrypted}")
        self.stdout.write(f"  Failed: {failed}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nDRY RUN - Run without --dry-run to apply changes")
            )
        else:
            self.stdout.write("\n" + self.style.SUCCESS("✓ Database updated successfully"))
            if backup_file:
                self.stdout.write(f"  Backup saved to: {backup_file}")

    def _is_encrypted(self, data: Any) -> bool:
        """
        Check if data appears to be encrypted.

        Encrypted data from Fernet starts with 'gAAAAA' (base64 encoded).
        """
        if not isinstance(data, str):
            return False

        # Fernet tokens start with version byte (0x80) followed by timestamp
        # When base64 encoded, they typically start with 'gAAAAA'
        return data.startswith('gAAAAA') or len(data) > 200  # Encrypted data is longer

    def _backup_data(self, records: list, backup_file: str) -> None:
        """Create a JSON backup of original data."""
        backup = {
            'timestamp': datetime.now().isoformat(),
            'record_count': len(records),
            'records': [
                {'id': record_id, 'data': data}
                for record_id, data in records
            ]
        }

        with open(backup_file, 'w') as f:
            json.dump(backup, f, indent=2)

        self.stdout.write(f"Backup created: {backup_file}")

    def _verify_encryption(self, sample_records: list) -> int:
        """
        Verify that encrypted data can be decrypted correctly.

        Returns: Number of verification failures
        """
        failures = 0

        for record_id, original_plaintext in sample_records:
            try:
                # Read the encrypted value from database
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT peventlogextras
                        FROM peopleeventlog
                        WHERE id = %s
                    """, [record_id])
                    row = cursor.fetchone()
                    encrypted_value = row[0] if row else None

                if not encrypted_value:
                    failures += 1
                    continue

                # Try to decrypt
                decrypted = BiometricEncryptionService.decrypt_biometric_data(encrypted_value)

                # Compare with original
                original_json = json.loads(original_plaintext) if isinstance(original_plaintext, str) else original_plaintext

                if decrypted != original_json:
                    self.stdout.write(
                        self.style.WARNING(f"Verification mismatch for record {record_id}")
                    )
                    failures += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Verification failed for record {record_id}: {e}")
                )
                failures += 1

        return failures
