"""
Management command to set up AI capabilities for users
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from apps.peoples.models import People


class Command(BaseCommand):
    help = 'Set up AI capabilities for users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID to set capabilities for (optional, defaults to all staff/admin users)'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='User email to set capabilities for (optional)'
        )
        parser.add_argument(
            '--loginid',
            type=str,
            help='User loginid to set capabilities for (optional)'
        )
        parser.add_argument(
            '--can-approve',
            action='store_true',
            help='Grant AI recommendation approval capability'
        )
        parser.add_argument(
            '--can-manage-kb',
            action='store_true',
            help='Grant knowledge base management capability'
        )
        parser.add_argument(
            '--is-approver',
            action='store_true',
            help='Grant AI recommendation approver role'
        )
        parser.add_argument(
            '--auto-setup-admins',
            action='store_true',
            help='Automatically set up capabilities for all admin/staff users'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        users_to_update = []

        # Determine which users to update
        if options['user_id']:
            try:
                user = People.objects.get(pk=options['user_id'])
                users_to_update.append(user)
            except People.DoesNotExist:
                raise CommandError(f'User with ID {options["user_id"]} does not exist')

        elif options['email']:
            try:
                user = People.objects.get(email=options['email'])
                users_to_update.append(user)
            except People.DoesNotExist:
                raise CommandError(f'User with email {options["email"]} does not exist')

        elif options['loginid']:
            try:
                user = People.objects.get(loginid=options['loginid'])
                users_to_update.append(user)
            except People.DoesNotExist:
                raise CommandError(f'User with loginid {options["loginid"]} does not exist')

        elif options['auto_setup_admins']:
            # Get all admin/staff users
            users_to_update = People.objects.filter(
                models.Q(is_staff=True) | models.Q(isadmin=True) | models.Q(is_superuser=True)
            )
            self.stdout.write(f"Found {users_to_update.count()} admin/staff users")

        else:
            raise CommandError(
                'You must specify either --user-id, --email, --loginid, or --auto-setup-admins'
            )

        # Show what capabilities will be granted
        capabilities_to_grant = []
        if options['can_approve']:
            capabilities_to_grant.append('can_approve_ai_recommendations')
        if options['can_manage_kb']:
            capabilities_to_grant.append('can_manage_knowledge_base')
        if options['is_approver']:
            capabilities_to_grant.append('ai_recommendation_approver')

        if not capabilities_to_grant and not options['auto_setup_admins']:
            raise CommandError(
                'You must specify at least one capability: --can-approve, --can-manage-kb, or --is-approver'
            )

        # For auto-setup-admins, give full permissions
        if options['auto_setup_admins']:
            capabilities_to_grant = [
                'can_approve_ai_recommendations',
                'can_manage_knowledge_base',
                'ai_recommendation_approver',
                'system_administrator'
            ]

        self.stdout.write(f"Will grant capabilities: {', '.join(capabilities_to_grant)}")

        # Update users
        updated_count = 0
        with transaction.atomic():
            for user in users_to_update:
                if options['dry_run']:
                    self.stdout.write(
                        f"DRY RUN: Would update user {user.peoplename} ({user.loginid}) with capabilities: {capabilities_to_grant}"
                    )
                else:
                    # Initialize capabilities if not exists
                    if not user.capabilities:
                        user.capabilities = {}

                    # Add each capability
                    for capability in capabilities_to_grant:
                        user.capabilities[capability] = True

                    user.save()
                    updated_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Updated user {user.peoplename} ({user.loginid}) with AI capabilities"
                        )
                    )

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would have updated {len(users_to_update)} users")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully updated {updated_count} users with AI capabilities")
            )

    def get_user_capabilities_display(self, user):
        """Get a user's current capabilities for display"""
        if not user.capabilities:
            return "No capabilities set"

        capabilities = []
        if user.capabilities.get('can_approve_ai_recommendations'):
            capabilities.append('AI Approval')
        if user.capabilities.get('can_manage_knowledge_base'):
            capabilities.append('Knowledge Base Management')
        if user.capabilities.get('ai_recommendation_approver'):
            capabilities.append('AI Approver')
        if user.capabilities.get('system_administrator'):
            capabilities.append('System Admin')

        return ', '.join(capabilities) if capabilities else "No AI capabilities"