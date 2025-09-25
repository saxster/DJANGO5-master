"""
Management command to fix compressed email addresses in the database.

Usage:
    python manage.py fix_compressed_emails --dry-run  # Preview changes
    python manage.py fix_compressed_emails             # Apply fixes
"""
import base64
import zlib
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.peoples.models import People


class Command(BaseCommand):
    help = 'Fix compressed/corrupted email addresses in the People model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be applied')
            )

        # Find suspicious email addresses (base64-like patterns without @ symbol)
        # Look for emails that don't contain @ and are longer than 20 chars (likely compressed)
        suspicious_people = People.objects.filter(
            email__isnull=False,
        ).exclude(email__icontains='@').exclude(
            email__in=['', 'NONE', 'none', 'None']
        ).filter(email__regex=r'^.{20,}$')

        total_found = suspicious_people.count()
        self.stdout.write(f'Found {total_found} people with suspicious email addresses')

        if total_found == 0:
            self.stdout.write(self.style.SUCCESS('No compressed emails found!'))
            return

        fixed_count = 0
        failed_count = 0

        with transaction.atomic():
            for person in suspicious_people:
                original_email = person.email

                try:
                    # Try to decompress the email
                    decompressed_email = self.decompress_email(original_email)

                    # Validate the decompressed email
                    if self.is_valid_email(decompressed_email):
                        self.stdout.write(
                            f'Person ID {person.id} ({person.peoplename}):'
                        )
                        self.stdout.write(f'  FROM: {original_email[:50]}...')
                        self.stdout.write(f'  TO:   {decompressed_email}')

                        if not dry_run:
                            person.email = decompressed_email
                            person.save()

                        fixed_count += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f'Person ID {person.id}: Decompressed email is invalid: {decompressed_email}'
                            )
                        )
                        failed_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Person ID {person.id}: Failed to decompress - {e}'
                        )
                    )
                    failed_count += 1

        # Summary
        self.stdout.write(f'\n=== SUMMARY ===')
        self.stdout.write(f'Total suspicious emails found: {total_found}')
        self.stdout.write(f'Successfully fixed: {fixed_count}')
        self.stdout.write(f'Failed to fix: {failed_count}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN COMPLETE - Run without --dry-run to apply changes')
            )
        elif fixed_count > 0:
            self.stdout.write(
                self.style.SUCCESS('Email addresses have been fixed!')
            )

    def decompress_email(self, compressed_email):
        """Decompress a zlib-compressed base64 email address."""
        try:
            # Decode base64
            decoded = base64.b64decode(compressed_email)
            # Decompress with zlib
            decompressed = zlib.decompress(decoded)
            # Convert to string
            return decompressed.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decompress: {e}")

    def is_valid_email(self, email):
        """Validate email format."""
        if not email or not isinstance(email, str):
            return False

        # Basic email regex
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email.strip()))