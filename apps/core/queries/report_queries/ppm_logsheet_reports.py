"""
PPM and Logsheet report queries.

Handles PPM summary and detailed logsheet reports.
"""

from typing import List, Dict
from django.db.models import Q, F, Count, Case, When, Value
from django.db import models
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PPMLogsheetReports:
    """Report queries for PPM and logsheets."""

    @staticmethod
    def ppmsummary_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """PPM (Preventive Maintenance) summary report."""
        from apps.activity.models.job_model import Jobneed

        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]

        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()

        ppm_data = (
            Jobneed.objects
            .filter(
                identifier='PPM',
                parent_id=1,
                bu_id__in=site_id_list,
                plandatetime__date__range=[from_date, upto_date]
            )
            .select_related('people', 'asset', 'asset__type', 'bu')
            .values(
                'bu__buname',
                asset_type_name=F('asset__type__taname')
            )
            .annotate(
                total_ppm_scheduled=Count('id'),
                completed_on_time=Count(
                    'id',
                    filter=Q(
                        endtime__lte=F('expirydatetime'),
                        jobstatus='COMPLETED'
                    )
                ),
                completed_after_schedule=Count(
                    'id',
                    filter=Q(
                        endtime__gt=F('expirydatetime'),
                        jobstatus='COMPLETED'
                    )
                ),
                ppm_missed=Count('id', filter=Q(jobstatus='AUTOCLOSED'))
            )
            .annotate(
                percentage=Case(
                    When(total_ppm_scheduled=0, then=Value(0.0)),
                    default=models.ExpressionWrapper(
                        F('completed_on_time') * 100.0 / F('total_ppm_scheduled'),
                        output_field=models.FloatField()
                    )
                )
            )
            .order_by('bu__buname', 'asset_type_name')
        )

        result = []
        for item in ppm_data:
            result.append({
                'Asset Type': item['asset_type_name'],
                'Total PPM Scheduled': item['total_ppm_scheduled'],
                'Completed On Time': item['completed_on_time'],
                'Completed After Schedule': item['completed_after_schedule'],
                'PPM Missed': item['ppm_missed'],
                'Percentage': round(item['percentage'], 2),
                'Site Name': item['bu__buname']
            })

        return result

    @staticmethod
    def logsheet_report(timezone_str: str, buid: int, qsetid: int, assetid: int) -> List[Dict]:
        """Complex logsheet report with detailed question/answer handling."""
        from apps.activity.models.job_model import Jobneed, JobneedDetails

        jobs = (
            Jobneed.objects
            .filter(
                identifier='TASK',
                jobstatus='COMPLETED',
                bu_id=buid,
                qset_id=qsetid,
                asset_id=assetid
            )
            .select_related(
                'asset', 'people', 'pgroup', 'qset', 'bu', 'performedby'
            )
            .prefetch_related('details')
        )

        result = []
        for job in jobs:
            job_details = (
                JobneedDetails.objects
                .filter(jobneed_id=job.id)
                .select_related('question')
                .exclude(answer__isnull=True, answer__exact='')
                .order_by('seqno')
            )

            for detail in job_details:
                answer = detail.answer
                if detail.answertype == 'NUMERIC' and answer:
                    try:
                        answer = f"{float(answer):.2f}"
                    except (ValueError, TypeError):
                        answer = answer
                elif not answer or answer.strip() == '':
                    answer = 'X0X'
                else:
                    answer = answer or '0'

                result.append({
                    'id': job.id,
                    'Plan Datetime': job.plandatetime,
                    'jobdesc': job.jobdesc,
                    'Assigned To': (
                        job.people.peoplename if job.people_id != 1
                        else job.pgroup.groupname if job.pgroup_id != 1
                        else 'NONE'
                    ),
                    'Asset': job.asset.assetname,
                    'Performed By': job.performedby.peoplename if job.performedby else '',
                    'qsetname': job.qset.qsetname,
                    'expirydatetime': job.expirydatetime,
                    'gracetime': job.gracetime,
                    'site': job.bu.buname,
                    'scantype': job.scantype,
                    'receivedonserver': job.receivedonserver,
                    'priority': job.priority,
                    'Start Time': job.starttime,
                    'End Time': job.endtime,
                    'gpslocation': job.gpslocation,
                    'remarks': job.remarks,
                    'seqno': detail.seqno,
                    'quesname': detail.question.quesname,
                    'answer': answer
                })

        return result