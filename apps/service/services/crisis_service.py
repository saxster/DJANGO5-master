"""
Crisis Service Module

Handles site crisis detection and ticket generation with escalation workflows.
Extracted from apps/service/utils.py for improved organization and maintainability.

Migration Date: 2025-09-30
Original File: apps/service/utils.py (lines 1191-1260)

Functions:
- check_for_sitecrisis: Detect crisis events and trigger tickets
- raise_ticket: Create crisis ticket with proper escalation
- create_escalation_matrix_for_sitecrisis: Auto-create escalation if missing

Features:
- Automatic crisis detection from PeopleEventlog
- Ticket auto-generation with escalation routing
- Site manager/emergency contact assignment
"""
from logging import getLogger
from django.apps import apps

log = getLogger("message_q")


def check_for_sitecrisis(obj, tablename, user):
    """
    Check for site crisis events and automatically raise tickets.

    Detects if a PeopleEventlog entry represents a site crisis (e.g., security
    incident, emergency) and automatically creates a helpdesk ticket with
    proper escalation routing.

    Args:
        obj: Model instance being inserted
        tablename: Name of the table ('peopleeventlog' for crisis detection)
        user: User instance who created the record

    Side Effects:
        - Creates Ticket instance if crisis detected
        - Creates EscalationMatrix if not configured
    """
    if tablename == "peopleeventlog":
        model = apps.get_model("attendance", "PeopleEventlog")
        if obj.peventtype.tacode in model.objects.get_sitecrisis_types():
            log.info("Site Crisis found raising a ticket")
            Ticket = apps.get_model("y_helpdesk", "Ticket")
            ESM = apps.get_model("y_helpdesk", "EscalationMatrix")
            # generate ticket sitecrisis appeared
            esc = (
                ESM.objects.select_related("escalationtemplate")
                .filter(
                    escalationtemplate__tacode="TC_SITECRISIS",
                    escalationtemplate__tatype__tacode="TICKETCATEGORY",
                    bu_id=user.bu_id,
                )
                .order_by("level")
                .first()
            )
            if esc:
                raise_ticket(Ticket, user, esc, obj)
                log.info("Ticket raised")
            else:
                esc = create_escalation_matrix_for_sitecrisis(ESM, user)
                log.info("Escalation was not set, so created one")
                raise_ticket(Ticket, user, esc, obj)
                log.info("Ticket raised")


def raise_ticket(Ticket, user, esc, obj):
    """
    Create crisis ticket with escalation routing.

    Args:
        Ticket: Ticket model class
        user: User instance creating the ticket
        esc: EscalationMatrix instance defining routing
        obj: Source object (PeopleEventlog) with crisis details

    Side Effects:
        - Creates Ticket instance in database
    """
    Ticket.objects.create(
        ticketdesc=f"{obj.remarks}",
        assignedtopeople=esc.assignedperson,
        assignedtogroup_id=1,
        identifier=Ticket.Identifier.TICKET,
        client=user.client,
        bu=user.bu,
        priority=Ticket.Priority.HIGH,
        ticketcategory_id=esc.escalationtemplate_id,
        level=1,
        status=Ticket.Status.NEW,
        isescalated=False,
        ticketsource=Ticket.TicketSource.SYSTEMGENERATED,
        ctzoffset=obj.ctzoffset,
    )


def create_escalation_matrix_for_sitecrisis(ESM, user):
    """
    Auto-create escalation matrix for site crisis if not configured.

    Finds the appropriate person to assign (site manager or emergency contact)
    and creates a default escalation configuration for crisis tickets.

    Args:
        ESM: EscalationMatrix model class
        user: User instance with bu context

    Returns:
        EscalationMatrix: Newly created escalation configuration

    Note:
        Assigns to site manager or emergency contact if available,
        otherwise falls back to the BU's creator.
    """
    People = apps.get_model("peoples", "People")
    assigneduser = (
        People.objects.get_sitemanager_or_emergencycontact(user.bu) or user.bu.cuser
    )
    if assigneduser:
        TypeAssist = apps.get_model("onboarding", "TypeAssist")
        site_crisis_obj = TypeAssist.objects.filter(
            tacode="TC_SITECRISIS", tatype__tacode="TICKETCATEGORY"
        ).first()
        return ESM.objects.create(
            cuser=user,
            muser=user,
            level=1,
            job_id=1,
            frequency="MINUTE",
            frequencyvalue=30,
            assignedfor="PEOPLE",
            bu=user.bu,
            client=user.client,
            escalationtemplate=site_crisis_obj,
            assignedperson=assigneduser,
            assignedgroup_id=1,
        )
