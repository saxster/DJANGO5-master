"""
Management command to load initial consent policies.

Loads default consent policies for GPS tracking and biometric data collection.

Usage:
    python manage.py load_consent_policies [--state=CA] [--update-existing]
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.attendance.models.consent import ConsentPolicy
from pathlib import Path
import logging
from apps.core.exceptions.patterns import BUSINESS_LOGIC_EXCEPTIONS, DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load initial consent policies for GPS and biometric data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--state',
            type=str,
            help='Load policies for specific state only (CA, LA, IL, TX, etc.)'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing policies if they exist'
        )
        parser.add_argument(
            '--tenant',
            type=str,
            default='default',
            help='Tenant ID for policies'
        )

    def handle(self, *args, **options):
        state_filter = options.get('state')
        update_existing = options['update_existing']
        tenant = options['tenant']

        self.stdout.write(self.style.SUCCESS('Loading Consent Policies'))
        self.stdout.write(f"Tenant: {tenant}")
        self.stdout.write(f"Update existing: {update_existing}\n")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        # Define policies to load
        policies = self._get_policy_definitions(tenant)

        # Filter by state if specified
        if state_filter:
            policies = [p for p in policies if p['state'] == state_filter]

        for policy_data in policies:
            try:
                # Check if exists
                existing = ConsentPolicy.objects.filter(
                    policy_type=policy_data['policy_type'],
                    state=policy_data['state'],
                    version=policy_data['version'],
                    tenant=tenant
                ).first()

                if existing:
                    if update_existing:
                        # Update existing policy
                        for key, value in policy_data.items():
                            setattr(existing, key, value)
                        existing.save()
                        updated_count += 1
                        self.stdout.write(self.style.WARNING(f"  ↻ Updated: {existing}"))
                    else:
                        skipped_count += 1
                        self.stdout.write(f"  - Skipped: {existing} (already exists)")
                else:
                    # Create new policy
                    policy = ConsentPolicy.objects.create(**policy_data)
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Created: {policy}"))

            except DATABASE_EXCEPTIONS as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Failed to load policy: {e}"))
                logger.error(f"Failed to load policy: {e}", exc_info=True)

        # Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS(f"Consent Policy Loading Complete"))
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        self.stdout.write('=' * 70)

    def _get_policy_definitions(self, tenant: str) -> list:
        """Get policy definitions to load"""
        base_path = Path('apps/attendance/templates/consent/policies/')

        return [
            # NOTE: GPS consent policies REMOVED
            # GPS tracking is CORE APP FUNCTIONALITY - no consent required
            # By using the attendance app, users implicitly accept GPS tracking
            # Users who don't want GPS can choose not to use the app

            # Biometric Data Collection (Multi-state)
            {
                'policy_type': ConsentPolicy.PolicyType.BIOMETRIC_DATA,
                'state': ConsentPolicy.State.FEDERAL,
                'version': '1.0',
                'title': 'Biometric Data Collection and Use Consent',
                'summary': 'Consent for collection and use of facial recognition templates for identity verification. Complies with Illinois BIPA, Texas CUBI, and Washington biometric privacy laws.',
                'policy_text': self._load_template(base_path / 'biometric_data.html'),
                'effective_date': timezone.now().date(),
                'is_active': True,
                'requires_signature': True,
                'requires_written_consent': False,  # Electronic OK for federal
                'tenant': tenant,
            },

            # Illinois BIPA (Biometric)
            {
                'policy_type': ConsentPolicy.PolicyType.BIOMETRIC_DATA,
                'state': ConsentPolicy.State.ILLINOIS,
                'version': '1.0',
                'title': 'Biometric Information Privacy Act (BIPA) Consent',
                'summary': 'Written consent for biometric information collection as required by Illinois BIPA.',
                'policy_text': self._load_template(base_path / 'biometric_data.html'),
                'effective_date': timezone.now().date(),
                'is_active': True,
                'requires_signature': True,
                'requires_written_consent': True,  # BIPA requires written
                'tenant': tenant,
            },

            # Photo Capture
            {
                'policy_type': ConsentPolicy.PolicyType.PHOTO_CAPTURE,
                'state': ConsentPolicy.State.FEDERAL,
                'version': '1.0',
                'title': 'Photo Capture During Clock-In/Out',
                'summary': 'Consent for capturing your photo during attendance clock-in and clock-out for identity verification and security.',
                'policy_text': '<p>We capture photos during clock-in/out to verify your identity and prevent time fraud. Photos are retained for 90 days and then automatically deleted.</p>',
                'effective_date': timezone.now().date(),
                'is_active': True,
                'requires_signature': True,
                'requires_written_consent': False,
                'tenant': tenant,
            },
        ]

    def _load_template(self, template_path: Path) -> str:
        """Load policy template from file"""
        try:
            if template_path.exists():
                return template_path.read_text()
            else:
                return f'<p>Policy template not found: {template_path}</p>'
        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Failed to load template {template_path}: {e}", exc_info=True)
            return f'<p>Error loading policy template</p>'
