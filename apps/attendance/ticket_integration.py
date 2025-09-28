"""
Attendance Ticket Integration Service

This module provides functionality to automatically create and manage
tickets for attendance-related issues like mismatches, missing IN/OUT records, etc.
"""

from django.apps import apps
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class AttendanceTicketService:
    """Service for managing attendance-related tickets"""

    # Define attendance-specific ticket categories
    ATTENDANCE_CATEGORIES = {
        'ATTENDANCE_MISMATCH': 'Attendance Data Mismatch',
        'ATTENDANCE_MISSING_IN': 'Missing Check-In Record',
        'ATTENDANCE_MISSING_OUT': 'Missing Check-Out Record',
        'ATTENDANCE_INVALID_SCAN': 'Invalid Attendance Scan',
        'ATTENDANCE_DUPLICATE': 'Duplicate Attendance Record',
    }

    @classmethod
    def ensure_attendance_categories_exist(cls, client_id, bu_id):
        """
        Ensure attendance ticket categories exist in TypeAssist

        Args:
            client_id: Client ID for multi-tenancy
            bu_id: Business unit ID

        Returns:
            dict: Created category ID mapping
        """
        try:
            TypeAssist = apps.get_model('onboarding', 'TypeAssist')
            category_ids = {}

            # Get or create ticket category type
            try:
                ticket_category_type = TypeAssist.objects.get(tacode="TICKETCATEGORY")
            except TypeAssist.DoesNotExist:
                logger.warning("TICKETCATEGORY type not found, attendance categories may not work properly")
                return category_ids

            with transaction.atomic():
                for code, name in cls.ATTENDANCE_CATEGORIES.items():
                    category, created = TypeAssist.objects.get_or_create(
                        tacode=code,
                        client_id=client_id,
                        bu_id=bu_id,
                        defaults={
                            'taname': name,
                            'tatype': ticket_category_type,
                            'enable': True,
                        }
                    )
                    category_ids[code] = category.id
                    if created:
                        logger.info(f"Created attendance ticket category: {code} - {name}")

            return category_ids

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to ensure attendance categories exist: {e}", exc_info=True)
            return {}

    @classmethod
    def create_attendance_ticket(cls, category_code, description, people_id, client_id, bu_id,
                                location_id=None, priority='MEDIUM', additional_data=None):
        """
        Create an attendance-related ticket

        Args:
            category_code: One of ATTENDANCE_CATEGORIES keys
            description: Ticket description
            people_id: ID of person with attendance issue
            client_id: Client ID
            bu_id: Business unit ID
            location_id: Optional location ID
            priority: Ticket priority (LOW, MEDIUM, HIGH)
            additional_data: Optional dict with additional ticket data

        Returns:
            Ticket instance or None if creation failed
        """
        try:
            Ticket = apps.get_model('y_helpdesk', 'Ticket')
            TypeAssist = apps.get_model('onboarding', 'TypeAssist')

            # Ensure categories exist and get the category ID
            categories = cls.ensure_attendance_categories_exist(client_id, bu_id)
            category_id = categories.get(category_code)

            if not category_id:
                logger.warning(f"Could not find/create attendance category: {category_code}")
                return None

            # Get site incharge as assignee (fallback to NONE user)
            from apps.core.utils_new.db_utils import get_or_create_none_people
            try:
                Bt = apps.get_model('onboarding', 'Bt')
                site = Bt.objects.get(id=bu_id)
                assignee_id = site.siteincharge_id if site.siteincharge_id else 1
            except:
                assignee_id = get_or_create_none_people().id

            ticket_data = {
                'ticketdesc': description,
                'ticketcategory_id': category_id,
                'assignedtopeople_id': assignee_id,
                'client_id': client_id,
                'bu_id': bu_id,
                'priority': priority,
                'status': Ticket.Status.NEW.value,
                'ticketsource': Ticket.TicketSource.SYSTEMGENERATED.value,
            }

            # Add optional fields
            if location_id:
                ticket_data['location_id'] = location_id

            if additional_data:
                ticket_data.update(additional_data)

            with transaction.atomic():
                ticket = Ticket.objects.create(**ticket_data)

                # Add initial history entry
                from apps.core.utils_new.db_utils import get_or_create_none_people
                system_user = get_or_create_none_people()
                from apps.core import utils
                utils.store_ticket_history(ticket, user=system_user)

                logger.info(f"Created attendance ticket {ticket.id}: {description}")
                return ticket

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to create attendance ticket: {e}", exc_info=True)
            return None

    @classmethod
    def resolve_attendance_tickets(cls, people_id, category_codes=None, resolution_comment="Issue resolved automatically"):
        """
        Auto-resolve attendance tickets for a person when issues are corrected

        Args:
            people_id: ID of person whose tickets should be resolved
            category_codes: List of category codes to resolve (None = all attendance tickets)
            resolution_comment: Comment for resolution

        Returns:
            int: Number of tickets resolved
        """
        try:
            Ticket = apps.get_model('y_helpdesk', 'Ticket')
            TypeAssist = apps.get_model('onboarding', 'TypeAssist')

            # Build query for attendance tickets
            query_filters = {
                'assignedtopeople_id': people_id,
                'status__in': [Ticket.Status.NEW.value, Ticket.Status.OPEN.value, Ticket.Status.ONHOLD.value],
                'ticketsource': Ticket.TicketSource.SYSTEMGENERATED.value,
            }

            if category_codes:
                # Filter by specific category codes
                categories = TypeAssist.objects.filter(tacode__in=category_codes)
                query_filters['ticketcategory__in'] = categories
            else:
                # All attendance categories
                categories = TypeAssist.objects.filter(tacode__in=cls.ATTENDANCE_CATEGORIES.keys())
                query_filters['ticketcategory__in'] = categories

            tickets_to_resolve = Ticket.objects.filter(**query_filters)
            resolved_count = 0

            with transaction.atomic():
                for ticket in tickets_to_resolve:
                    ticket.status = Ticket.Status.RESOLVED.value
                    ticket.comments = resolution_comment
                    ticket.save()

                    # Add history entry for resolution
                    from apps.core.utils_new.db_utils import get_or_create_none_people
                    system_user = get_or_create_none_people()
                    from apps.core import utils
                    utils.store_ticket_history(ticket, user=system_user)

                    resolved_count += 1
                    logger.info(f"Auto-resolved attendance ticket {ticket.id}")

            return resolved_count

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to resolve attendance tickets: {e}", exc_info=True)
            return 0

    @classmethod
    def get_open_attendance_tickets(cls, people_id=None, client_id=None, bu_id=None):
        """
        Get open attendance tickets with optional filtering

        Args:
            people_id: Filter by person ID
            client_id: Filter by client ID
            bu_id: Filter by business unit ID

        Returns:
            QuerySet of open attendance tickets
        """
        try:
            Ticket = apps.get_model('y_helpdesk', 'Ticket')
            TypeAssist = apps.get_model('onboarding', 'TypeAssist')

            # Get attendance categories
            attendance_categories = TypeAssist.objects.filter(
                tacode__in=cls.ATTENDANCE_CATEGORIES.keys()
            )

            query_filters = {
                'ticketcategory__in': attendance_categories,
                'status__in': [Ticket.Status.NEW.value, Ticket.Status.OPEN.value, Ticket.Status.ONHOLD.value],
            }

            if people_id:
                query_filters['assignedtopeople_id'] = people_id
            if client_id:
                query_filters['client_id'] = client_id
            if bu_id:
                query_filters['bu_id'] = bu_id

            return Ticket.objects.filter(**query_filters).select_related(
                'assignedtopeople', 'ticketcategory', 'bu'
            )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to get open attendance tickets: {e}", exc_info=True)
            return Ticket.objects.none()


# Convenience functions for common attendance ticket operations

def create_attendance_mismatch_ticket(people_id, expected_time, actual_time, client_id, bu_id, location_id=None):
    """Create ticket for attendance time mismatch"""
    description = f"Attendance mismatch detected - Expected: {expected_time}, Actual: {actual_time}"
    return AttendanceTicketService.create_attendance_ticket(
        'ATTENDANCE_MISMATCH', description, people_id, client_id, bu_id, location_id
    )

def create_missing_checkin_ticket(people_id, expected_date, client_id, bu_id, location_id=None):
    """Create ticket for missing check-in"""
    description = f"Missing check-in record for {expected_date}"
    return AttendanceTicketService.create_attendance_ticket(
        'ATTENDANCE_MISSING_IN', description, people_id, client_id, bu_id, location_id
    )

def create_missing_checkout_ticket(people_id, expected_date, client_id, bu_id, location_id=None):
    """Create ticket for missing check-out"""
    description = f"Missing check-out record for {expected_date}"
    return AttendanceTicketService.create_attendance_ticket(
        'ATTENDANCE_MISSING_OUT', description, people_id, client_id, bu_id, location_id
    )

def resolve_attendance_issues_for_person(people_id, comment="Attendance records corrected"):
    """Resolve all open attendance tickets for a person"""
    return AttendanceTicketService.resolve_attendance_tickets(people_id, resolution_comment=comment)