"""
Ticket and Work Order report queries.

Handles ticket lists and work order reports.
"""

from typing import List, Dict
from django.db.models import Q, F, Case, When, Value, CharField
from django.db.models.functions import Cast, Concat
from django.utils import timezone
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TicketWorkorderReports:
    """Report queries for tickets and work orders."""

    @staticmethod
    def listoftickets_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """List of tickets report with TAT calculation."""
        from apps.y_helpdesk.models import Ticket

        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]

        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()

        now = timezone.now()

        tickets = (
            Ticket.objects
            .filter(
                bu_id__in=site_id_list,
                cdtz__date__range=[from_date, upto_date]
            )
            .exclude(
                Q(assignedtogroup_id__isnull=True, assignedtopeople_id__isnull=True) |
                Q(assignedtogroup_id=1, assignedtopeople_id=1) |
                Q(Q(cuser_id=1) | Q(cuser_id__isnull=True), Q(muser_id=1) | Q(muser_id__isnull=True))
            )
            .select_related(
                'assignedtopeople', 'assignedtogroup', 'cuser', 'muser', 'ticketcategory'
            )
            .annotate(
                tat=Case(
                    When(
                        status__in=['RESOLVED', 'CLOSED'],
                        then=Cast(F('modifieddatetime') - F('cdtz'), CharField())
                    ),
                    When(status='CANCELLED', then=Value('NA')),
                    default=Value('00:00:00'),
                    output_field=CharField()
                ),
                time_elapsed=Case(
                    When(
                        ~Q(status__in=['RESOLVED', 'CLOSED', 'CANCELLED']),
                        then=Cast(now - F('cdtz'), CharField())
                    ),
                    When(status='CANCELLED', then=Value('NA')),
                    default=Value('00:00:00'),
                    output_field=CharField()
                ),
                assigned_to=Case(
                    When(
                        Q(assignedtogroup_id__isnull=True) | Q(assignedtogroup_id=1),
                        then=F('assignedtopeople__peoplename')
                    ),
                    default=F('assignedtogroup__groupname'),
                    output_field=CharField()
                )
            )
            .values(
                'id', 'cdtz', 'modifieddatetime', 'status', 'ticketdesc', 'priority',
                'ticketcategory__taname', 'tat', 'time_elapsed', 'assigned_to',
                'cuser__peoplename', 'muser__peoplename'
            )
            .order_by('-cdtz')
        )

        result = []
        for ticket in tickets:
            result.append({
                'Ticket No': ticket['id'],
                'Created On': ticket['cdtz'],
                'Modied On': ticket['modifieddatetime'],
                'Status': ticket['status'],
                'Description': ticket['ticketdesc'],
                'Priority': ticket['priority'],
                'Ticket Category': ticket['ticketcategory__taname'],
                'TAT': ticket['tat'],
                'tl': ticket['time_elapsed'],
                'Assigned To': ticket['assigned_to'],
                'Created By': ticket['cuser__peoplename'],
                'modified_by': ticket['muser__peoplename']
            })

        return result

    @staticmethod
    def workorderlist_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """Work order list report."""
        from apps.work_order_management.models import Wom

        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]

        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()

        work_orders = (
            Wom.objects
            .filter(
                bu_id__in=site_id_list,
                cdtz__date__range=[from_date, upto_date]
            )
            .exclude(vendor_id__isnull=True, vendor_id=1, bu_id=1, qset_id=1)
            .select_related('cuser', 'vendor', 'bu')
            .annotate(
                categories_str=Case(
                    When(categories__isnull=False, then=Concat(*[
                        F('categories')
                    ])),
                    default=Value(''),
                    output_field=CharField()
                )
            )
            .values(
                'id', 'cdtz', 'description', 'plandatetime', 'endtime',
                'categories_str', 'cuser__peoplename', 'workstatus',
                'vendor__name', 'priority', 'bu__buname'
            )
            .order_by('bu__buname', '-plandatetime')
        )

        result = []
        for wo in work_orders:
            result.append({
                'wo_id': wo['id'],
                'Created On': wo['cdtz'],
                'Description': wo['description'],
                'Planned Date Time': wo['plandatetime'],
                'Completed On': wo['endtime'],
                'Categories': wo['categories_str'],
                'Created By': wo['cuser__peoplename'],
                'Status': wo['workstatus'],
                'Vendor Name': wo['vendor__name'],
                'Priority': wo['priority'].title() if wo['priority'] else '',
                'Site': wo['bu__buname']
            })

        return result