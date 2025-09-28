"""
Job, Task, and Tour query operations - core functionality.

Handles core jobneed queries. List operations moved to job_list_queries.py
to maintain <200 line limit per file.
"""

from typing import List, Dict
from django.db.models import Q, F, Count, Case, When, Value
from django.db import models
import logging

from .job_list_queries import JobListQueries

logger = logging.getLogger(__name__)


class JobQueries:
    """Query repository for job/task/tour operations."""

    sitereportlist = staticmethod(JobListQueries.sitereportlist)
    incidentreportlist = staticmethod(JobListQueries.incidentreportlist)
    workpermitlist = staticmethod(JobListQueries.workpermitlist)

    @staticmethod
    def tsitereportdetails(site_report_id: int = 1) -> List[Dict]:
        """Get site report details with parent-child traversal."""
        from apps.activity.models.job_model import Jobneed, JobneedDetails

        all_reports = list(
            Jobneed.objects
            .filter(identifier='SITEREPORT')
            .exclude(id=-1)
            .values('id', 'parent_id')
        )

        if not all_reports:
            return []

        children_map = {}
        for report in all_reports:
            parent_id = report['parent_id']
            if parent_id not in [-1, None]:
                children_map.setdefault(parent_id, []).append(report['id'])

        def get_descendants(parent_id: int) -> List[int]:
            descendants = []
            for child_id in children_map.get(parent_id, []):
                descendants.append(child_id)
                descendants.extend(get_descendants(child_id))
            return descendants

        child_ids = get_descendants(site_report_id)

        if not child_ids:
            return []

        return list(
            JobneedDetails.objects
            .filter(
                jobneed_id__in=child_ids,
                answertype='Question Type'
            )
            .select_related('jobneed', 'question')
            .annotate(
                jobdesc=F('jobneed__jobdesc'),
                pseqno=F('jobneed__seqno'),
                cseqno=F('seqno'),
                quesname=F('question__quesname'),
                question_answertype=F('question__answertype')
            )
            .order_by('jobneed__seqno', 'jobneed__jobdesc', 'seqno')
            .values(
                'jobdesc', 'pseqno', 'cseqno', 'question_id',
                'answertype', 'min', 'max', 'options', 'answer',
                'alerton', 'ismandatory', 'quesname', 'question_answertype'
            )
        )

    @staticmethod
    def tasksummary(timezone_str: str, bu_ids: str, start_date, end_date) -> List[Dict]:
        """Get task summary statistics."""
        from apps.activity.models.job_model import Jobneed

        bu_id_list = [int(id.strip()) for id in bu_ids.split(',') if id.strip()]

        summary = (
            Jobneed.objects
            .exclude(id__in=[-1, 1])
            .filter(
                identifier='TASK',
                bu_id__in=bu_id_list,
                plandatetime__date__range=[start_date, end_date]
            )
            .exclude(bu_id=1)
            .select_related('bu')
            .values('bu__id', 'bu__buname', 'plandatetime__date')
            .annotate(
                tot_task=Count('id'),
                tot_scheduled=Count('id', filter=Q(jobtype='SCHEDULE')),
                tot_adhoc=Count('id', filter=Q(jobtype='ADHOC')),
                tot_pending=Count('id', filter=Q(jobtype='SCHEDULE', jobstatus='ASSIGNED')),
                tot_closed=Count('id', filter=Q(jobtype='SCHEDULE', jobstatus='AUTOCLOSED')),
                tot_completed=Count('id', filter=Q(jobtype='SCHEDULE', jobstatus='COMPLETED'))
            )
            .annotate(
                perc=Case(
                    When(tot_scheduled=0, then=Value(0.0)),
                    default=models.ExpressionWrapper(
                        F('tot_completed') * 100.0 / F('tot_scheduled'),
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
                'site': item['bu__buname'],
                'planneddate': item['plandatetime__date'],
                'tot_task': item['tot_task'],
                'tot_scheduled': item['tot_scheduled'],
                'tot_adhoc': item['tot_adhoc'],
                'tot_pending': item['tot_pending'],
                'tot_closed': item['tot_closed'],
                'tot_completed': item['tot_completed'],
                'perc': round(item['perc'], 2)
            })

        return result