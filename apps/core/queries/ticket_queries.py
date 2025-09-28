"""
Ticket and escalation query operations.

Handles help desk ticket queries, escalation processing, and email notifications.
"""

from typing import List, Dict, Optional
from django.db.models import Q, F, Count, Case, When, Value
from django.db import models
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class TicketQueries:
    """Query repository for ticket and escalation operations."""

    @staticmethod
    def get_ticketlist_for_escalation() -> List[Dict]:
        """Get tickets needing escalation."""
        from apps.y_helpdesk.models import Ticket, EscalationMatrix

        now = timezone.now()

        open_tickets = (
            Ticket.objects
            .exclude(status__in=['CLOSED', 'CANCELLED'])
            .select_related('assignedtopeople', 'assignedtogroup', 'cuser', 'ticketcategory')
        )

        escalations = (
            EscalationMatrix.objects
            .select_related('assignedperson', 'assignedgroup', 'escalationtemplate')
            .annotate(
                calcminute=Case(
                    When(frequency='MINUTE', then=F('frequencyvalue')),
                    When(frequency='HOUR', then=F('frequencyvalue') * 60),
                    When(frequency='DAY', then=F('frequencyvalue') * 24 * 60),
                    When(frequency='WEEK', then=F('frequencyvalue') * 7 * 24 * 60),
                    default=Value(None),
                    output_field=models.IntegerField()
                )
            )
        )

        escalation_dict = {}
        for esc in escalations:
            key = (esc.escalationtemplate_id, esc.level)
            escalation_dict[key] = esc

        escalation_tickets = []
        for ticket in open_tickets:
            next_level = ticket.level + 1
            key = (ticket.ticketcategory_id, next_level)
            escalation = escalation_dict.get(key)

            if escalation and escalation.calcminute:
                exp_time = ticket.cdtz + timedelta(minutes=escalation.calcminute)
                if exp_time < now:
                    ticket_dict = {
                        'id': ticket.id,
                        'ticketno': ticket.ticketno,
                        'ticketdesc': ticket.ticketdesc,
                        'comments': ticket.comments,
                        'cdtz': ticket.cdtz,
                        'mdtz': ticket.modifieddatetime,
                        'tescalationtemplate': ticket.ticketcategory_id,
                        'status': ticket.status,
                        'tbu': ticket.bu_id,
                        'peoplename': ticket.assignedtopeople.peoplename if ticket.assignedtopeople else None,
                        'groupname': ticket.assignedtogroup.groupname if ticket.assignedtogroup else None,
                        'assignedtopeople': ticket.assignedtopeople_id,
                        'assignedtogroup': ticket.assignedtogroup_id,
                        'ticketlog': ticket.ticketlog,
                        'level': ticket.level,
                        'cuser_id': ticket.cuser_id,
                        'who': ticket.cuser.peoplename if ticket.cuser else None,
                        'exp_time': exp_time,
                        'esid': escalation.id,
                        'eslevel': escalation.level,
                        'frequency': escalation.frequency,
                        'frequencyvalue': escalation.frequencyvalue,
                        'calcminute': escalation.calcminute,
                        'escpeoplename': escalation.assignedperson.peoplename if escalation.assignedperson else None,
                        'escgroupname': escalation.assignedgroup.groupname if escalation.assignedgroup else None,
                        'escpersonid': escalation.assignedperson_id,
                        'escgrpid': escalation.assignedgroup_id,
                    }
                    escalation_tickets.append(ticket_dict)

        return escalation_tickets

    @staticmethod
    def ticketmail(ticket_id: int) -> Optional[Dict]:
        """Get ticket details for email notifications."""
        from apps.y_helpdesk.models import Ticket, EscalationMatrix
        from apps.peoples.models import People

        try:
            ticket = (
                Ticket.objects
                .select_related(
                    'assignedtopeople', 'assignedtogroup', 'cuser',
                    'muser', 'ticketcategory'
                )
                .get(id=ticket_id)
            )
        except Ticket.DoesNotExist:
            return None

        ticket_dict = {
            'id': ticket.id,
            'ticketno': ticket.ticketno,
            'ticketlog': ticket.ticketlog,
            'comments': ticket.comments,
            'ticketdesc': ticket.ticketdesc,
            'cdtz': ticket.cdtz,
            'status': ticket.status,
            'tescalationtemplate': ticket.ticketcategory.taname if ticket.ticketcategory else None,
            'peoplename': ticket.assignedtopeople.peoplename if ticket.assignedtopeople else None,
            'peopleemail': ticket.assignedtopeople.email if ticket.assignedtopeople else None,
            'creatorid': ticket.cuser_id,
            'creatoremail': ticket.cuser.email if ticket.cuser else None,
            'groupname': ticket.assignedtogroup.groupname if ticket.assignedtogroup else None,
            'modifierid': ticket.muser_id if ticket.muser else None,
            'modifiername': ticket.muser.peoplename if ticket.muser else None,
            'modifiermail': ticket.muser.email if ticket.muser else None,
            'assignedtopeople_id': ticket.assignedtopeople_id,
            'assignedtogroup_id': ticket.assignedtogroup_id,
            'ticketcategory_id': ticket.ticketcategory_id,
            'priority': ticket.priority,
            'mdtz': ticket.modifieddatetime,
        }

        try:
            current_esc = EscalationMatrix.objects.get(
                escalationtemplate_id=ticket.ticketcategory_id,
                level=ticket.level
            )

            if current_esc.frequency == 'MINUTE':
                exp_time = ticket.cdtz + timedelta(minutes=current_esc.frequencyvalue)
            elif current_esc.frequency == 'HOUR':
                exp_time = ticket.cdtz + timedelta(hours=current_esc.frequencyvalue)
            elif current_esc.frequency == 'DAY':
                exp_time = ticket.cdtz + timedelta(days=current_esc.frequencyvalue)
            elif current_esc.frequency == 'WEEK':
                exp_time = ticket.cdtz + timedelta(weeks=current_esc.frequencyvalue)
            else:
                exp_time = None

            ticket_dict.update({
                'exptime': exp_time,
                'level': current_esc.level,
                'frequency': current_esc.frequency,
                'frequencyvalue': current_esc.frequencyvalue,
                'body': current_esc.body,
                'notify': current_esc.notify,
                'escperson': current_esc.assignedperson_id,
                'escgrp': current_esc.assignedgroup_id,
            })

            if current_esc.notify:
                ticket_dict['notifyemail'] = current_esc.notify

        except EscalationMatrix.DoesNotExist:
            pass

        if ticket.assignedtogroup:
            group_emails = list(
                People.objects
                .filter(pgbelonging__pgroup=ticket.assignedtogroup)
                .values_list('email', flat=True)
            )
            ticket_dict['pgroupemail'] = ','.join(group_emails)

        try:
            next_esc = EscalationMatrix.objects.get(
                escalationtemplate_id=ticket.ticketcategory_id,
                level=ticket.level + 1
            )
            ticket_dict['next_escalation'] = f"{next_esc.frequencyvalue} {next_esc.frequency}"
        except EscalationMatrix.DoesNotExist:
            pass

        return ticket_dict