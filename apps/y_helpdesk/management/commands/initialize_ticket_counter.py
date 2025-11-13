"""
Management command to initialize Redis ticket counter based on existing max ticket ID.

Usage:
    python manage.py initialize_ticket_counter

This command should be run once when deploying the Redis-based ticket number generation
to ensure the counter starts from the correct value (current max ticket number + 1).

Purpose:
    - Prevents ticket number collisions
    - Ensures sequential ticket numbering continues
    - Initializes Redis counter based on database state
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
from apps.y_helpdesk.models import Ticket


class Command(BaseCommand):
    help = 'Initialize Redis ticket counter based on existing max ticket number'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Force reset counter even if already initialized'
        )

    def handle(self, *args, **options):
        reset = options.get('reset', False)

        # Check if counter already exists
        current_value = cache.get('ticket_counter')

        if current_value is not None and not reset:
            self.stdout.write(
                self.style.WARNING(
                    f'Ticket counter already initialized with value: {current_value}'
                )
            )
            self.stdout.write('Use --reset to force reinitialize')
            return

        # Get max ticket ID from database
        max_ticket = Ticket.objects.order_by('-id').first()

        if max_ticket:
            # Parse ticket number to get the counter value
            # Format: TKT-00123 -> 123
            try:
                # Try extracting number from ticketno field
                if max_ticket.ticketno and 'TKT-' in max_ticket.ticketno:
                    counter_value = int(max_ticket.ticketno.split('-')[1])
                else:
                    # Fallback to using the database ID
                    counter_value = max_ticket.id

                # Initialize Redis counter
                cache.set('ticket_counter', counter_value)

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Ticket counter initialized to: {counter_value}'
                    )
                )
                self.stdout.write(
                    f'   Next ticket will be: TKT-{counter_value + 1:05d}'
                )

            except (ValueError, IndexError) as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Failed to parse ticket number: {e}'
                    )
                )
                self.stdout.write(
                    f'   Max ticket: {max_ticket.ticketno}'
                )
                # Fallback to using count
                count = Ticket.objects.count()
                cache.set('ticket_counter', count)
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Using fallback: counter set to {count}'
                    )
                )
        else:
            # No tickets in database yet
            cache.set('ticket_counter', 0)
            self.stdout.write(
                self.style.SUCCESS(
                    '✅ Ticket counter initialized to: 0 (no tickets in database)'
                )
            )
            self.stdout.write(
                '   First ticket will be: TKT-00001'
            )
