"""
Task report queries.

Handles task summary and list reports.
"""

from typing import List, Dict
from django.db.models import Q, F, Count, Case, When, Value, CharField
from django.db import models
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TaskReports:
    """Report queries for tasks."""

    @staticmethod
    def tasksummary_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """Task summary report with timezone handling."""
        from apps.activity.models.job_model import Jobneed

        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]

        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()

        summary = (
            Jobneed.objects
            .filter(
                identifier='TASK',
                bu_id__in=site_id_list,
                plandatetime__date__range=[from_date, upto_date]
            )
            .exclude(id=1, bu_id=1)
            .select_related('bu')
            .values('bu__buname', 'plandatetime__date')
            .annotate(
                total_tasks=Count('id'),
                total_scheduled=Count('id', filter=Q(jobtype='SCHEDULE')),
                total_adhoc=Count('id', filter=Q(jobtype='ADHOC')),
                total_pending=Count('id', filter=Q(jobtype='SCHEDULE', jobstatus='ASSIGNED')),
                total_closed=Count('id', filter=Q(jobtype='SCHEDULE', jobstatus='AUTOCLOSED')),
                total_completed=Count('id', filter=Q(jobtype='SCHEDULE', jobstatus='COMPLETED')),
                not_performed=models.ExpressionWrapper(
                    Count('id') - Count('id', filter=Q(jobtype='SCHEDULE', jobstatus='COMPLETED')),
                    output_field=models.IntegerField()
                )
            )
            .annotate(
                percentage=Case(
                    When(total_scheduled=0, then=Value(0.0)),
                    default=models.ExpressionWrapper(
                        F('total_completed') * 100.0 / F('total_scheduled'),
                        output_field=models.FloatField()
                    )
                )
            )
            .order_by('bu__buname', '-plandatetime__date')
        )

        result = []
        for item in summary:
            result.append({
                'Site': item['bu__buname'],
                'Planned Date': item['plandatetime__date'],
                'Total Tasks': item['total_tasks'],
                'Total Scheduled': item['total_scheduled'],
                'Total Adhoc': item['total_adhoc'],
                'Total Pending': item['total_pending'],
                'Total Closed': item['total_closed'],
                'Total Completed': item['total_completed'],
                'Not Performed': item['not_performed'],
                'Percentage': round(item['percentage'], 2)
            })

        return result

    @staticmethod
    def listoftasks_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """Detailed list of tasks report."""
        from apps.activity.models.job_model import Jobneed

        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]

        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()

        tasks = (
            Jobneed.objects
            .filter(
                identifier='TASK',
                parent_id=1,
                bu_id__in=site_id_list,
                plandatetime__date__range=[from_date, upto_date]
            )
            .exclude(id=1, bu_id=1)
            .select_related(
                'bu', 'people', 'pgroup', 'performedby',
                'asset', 'qset'
            )
            .annotate(
                site=F('bu__buname'),
                assigned_to=Case(
                    When(~Q(people_id=1), then=F('people__peoplename')),
                    When(~Q(pgroup_id=1), then=F('pgroup__groupname')),
                    default=Value('NONE'),
                    output_field=CharField()
                ),
                performed_by=F('performedby__peoplename'),
                asset_name=F('asset__assetname'),
                question_set=F('qset__qsetname')
            )
            .order_by('bu__buname', '-plandatetime')
        )

        result = []
        for task in tasks:
            result.append({
                'id': task.bu_id,
                'Site': task.site,
                'Planned Date Time': task.plandatetime,
                'jobneedid': task.id,
                'identifier': task.identifier,
                'Description': task.jobdesc,
                'Assigned To': task.assigned_to,
                'assignedto': task.people_id,
                'jobtype': task.jobtype,
                'Status': task.jobstatus,
                'asset_id': task.asset_id,
                'Performed By': task.performed_by,
                'qsetname': task.qset_id,
                'Expired Date Time': task.expirydatetime,
                'Gracetime': task.gracetime,
                'scantype': task.scantype,
                'receivedonserver': task.receivedonserver,
                'priority': task.priority,
                'starttime': task.starttime,
                'endtime': task.endtime,
                'gpslocation': task.gpslocation,
                'qset_id': task.qset_id,
                'remarks': task.remarks,
                'Asset': task.asset_name,
                'Question Set': task.question_set,
                'peoplename': task.people.peoplename if task.people_id != 1 else None
            })

        return result