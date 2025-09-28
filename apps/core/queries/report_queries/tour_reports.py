"""
Tour report queries.

Handles tour summary and list reports (static and dynamic).
"""

from typing import List, Dict
from django.db.models import Q, F, Count, Case, When, Value, CharField
from django.db import models
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TourReports:
    """Report queries for tours."""

    @staticmethod
    def toursummary_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """Tour summary report."""
        from apps.activity.models.job_model import Jobneed

        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]

        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()

        summary = (
            Jobneed.objects
            .filter(
                identifier='INTERNALTOUR',
                bu_id__in=site_id_list,
                plandatetime__date__range=[from_date, upto_date]
            )
            .exclude(id=1, bu_id=1)
            .select_related('bu')
            .values('bu__id', 'bu__buname', 'plandatetime__date')
            .annotate(
                total_tours=Count('id'),
                total_scheduled=Count('id', filter=Q(jobtype='SCHEDULE')),
                total_adhoc=Count('id', filter=Q(jobtype='ADHOC')),
                total_pending=Count('id', filter=Q(jobstatus='ASSIGNED')),
                total_closed=Count('id', filter=Q(jobstatus='AUTOCLOSED')),
                total_completed=Count('id', filter=Q(jobstatus='COMPLETED'))
            )
            .annotate(
                percentage=Case(
                    When(total_tours=0, then=Value(0.0)),
                    default=models.ExpressionWrapper(
                        F('total_completed') * 100.0 / F('total_tours'),
                        output_field=models.FloatField()
                    )
                )
            )
            .order_by('bu__buname', '-plandatetime__date')
        )

        result = []
        for item in summary:
            result.append({
                'id': item['bu__id'],
                'Site': item['bu__buname'],
                'Date': item['plandatetime__date'],
                'Total Tours': item['total_tours'],
                'Total Scheduled': item['total_scheduled'],
                'Total Adhoc': item['total_adhoc'],
                'Total Pending': item['total_pending'],
                'Total Closed': item['total_closed'],
                'Total Completed': item['total_completed'],
                'Percentage': round(item['percentage'], 2)
            })

        return result

    @staticmethod
    def listoftours_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """List of tours report."""
        from apps.activity.models.job_model import Jobneed
        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]
        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()
        tours = (Jobneed.objects.filter(identifier='INTERNALTOUR', parent_id=1, bu_id__in=site_id_list,
            plandatetime__date__range=[from_date, upto_date]).exclude(id=1, bu_id=1)
            .select_related('bu', 'client', 'people', 'pgroup', 'performedby', 'asset', 'qset')
            .annotate(assigned_to=Case(When(~Q(people_id=1), then=F('people__peoplename')),
                When(~Q(pgroup_id=1), then=F('pgroup__groupname')), default=Value('NONE'), output_field=CharField()),
                is_time_bound=Case(When(other_info__istimebound='true', then=Value('Static')),
                default=Value('Dynamic'), output_field=CharField()))
            .values('client__buname', 'bu__buname', 'jobdesc', 'plandatetime', 'expirydatetime', 'assigned_to',
                'jobtype', 'jobstatus', 'endtime', 'performedby__peoplename', 'is_time_bound')
            .order_by('bu__buname', '-plandatetime'))
        result = []
        for tour in tours:
            result.append({'Client': tour['client__buname'], 'Site': tour['bu__buname'], 'Tour/Route': tour['jobdesc'],
                'Planned Datetime': tour['plandatetime'], 'Expiry Datetime': tour['expirydatetime'],
                'Assigned To': tour['assigned_to'], 'JobType': tour['jobtype'], 'Status': tour['jobstatus'],
                'Performed On': tour['endtime'], 'Performed By': tour['performedby__peoplename'],
                'Is Time Bound': tour['is_time_bound']})
        return result

    @staticmethod
    def statictourlist_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """Static tour list report."""
        from apps.activity.models.job_model import Jobneed
        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]
        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()
        tours = (Jobneed.objects.filter(identifier='INTERNALTOUR', parent_id=1, other_info__istimebound=True,
            bu_id__in=site_id_list, plandatetime__date__range=[from_date, upto_date]).exclude(id=1, bu_id=1)
            .select_related('bu', 'client', 'people', 'pgroup', 'performedby', 'asset', 'qset')
            .annotate(assigned_to=Case(When(~Q(people_id=1), then=F('people__peoplename')),
                When(~Q(pgroup_id=1), then=F('pgroup__groupname')), default=Value('NONE'), output_field=CharField()))
            .values('client__buname', 'bu__buname', 'jobdesc', 'plandatetime', 'expirydatetime', 'assigned_to',
                'jobtype', 'jobstatus', 'endtime', 'performedby__peoplename').order_by('bu__buname', '-plandatetime'))
        result = []
        for tour in tours:
            result.append({'Client': tour['client__buname'], 'Site': tour['bu__buname'], 'Tour/Route': tour['jobdesc'],
                'Planned Datetime': tour['plandatetime'], 'Expiry Datetime': tour['expirydatetime'],
                'Assigned To': tour['assigned_to'], 'JobType': tour['jobtype'], 'Status': tour['jobstatus'],
                'Performed On': tour['endtime'], 'Performed By': tour['performedby__peoplename']})
        return result

    @staticmethod
    def dynamictourlist_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """Dynamic tour list report."""
        return TourReports.statictourlist_report.__func__(TourReports, timezone_str, siteids, from_date, upto_date)

    @staticmethod
    def staticdetailedtoursummary_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """Static detailed tour summary report."""
        from apps.activity.models.job_model import Jobneed
        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]
        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()
        parent_tours = Jobneed.objects.filter(other_info__istimebound='true', parent_id=1, identifier='INTERNALTOUR',
            bu_id__in=site_id_list, plandatetime__date__range=[from_date, upto_date]).select_related('client', 'bu', 'remarkstype')
        result = []
        for tour in parent_tours:
            total_cp = Jobneed.objects.filter(parent_id=tour.id).count()
            completed_cp = Jobneed.objects.filter(parent_id=tour.id, jobstatus='COMPLETED').count()
            missed_cp = Jobneed.objects.filter(parent_id=tour.id, jobstatus__in=['AUTOCLOSED', 'ASSIGNED']).count()
            perc = round((completed_cp / total_cp) * 100) if total_cp > 0 else 0
            result.append({'Client Name': tour.client.buname if tour.client else '', 'Site Name': tour.bu.buname,
                'Description': tour.jobdesc, 'Start Time': tour.plandatetime.date(),
                'End Time': tour.expirydatetime.date() if tour.expirydatetime else None, 'Comments': tour.remarks,
                'Comments Type': tour.remarkstype.taname if tour.remarkstype else '', 'No of Checkpoints': total_cp,
                'Completed': completed_cp, 'Missed': missed_cp, 'Percentage': perc})
        return result

    @staticmethod
    def dynamicdetailedtoursummary_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """Dynamic detailed tour summary."""
        return TourReports.staticdetailedtoursummary_report.__func__(TourReports, timezone_str, siteids, from_date, upto_date)