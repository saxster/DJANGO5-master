"""
Job list query operations - site reports, incident reports, work permits.

Extracted from job_queries.py to maintain <200 line limit per file.
"""

from typing import List, Dict
from django.db.models import Q, F, Case, When, Value
from django.db.models.functions import Concat, Cast
from django.db import models
from django.utils import timezone
from datetime import timedelta
from .base import AttachmentHelper
import logging

logger = logging.getLogger(__name__)


class JobListQueries:
    """Query repository for job list operations."""

    @staticmethod
    def sitereportlist(bu_ids: List[int], start_date, end_date) -> List[Dict]:
        """Get site report list with optimized Django ORM."""
        from apps.activity.models.job_model import Jobneed

        queryset = (
            Jobneed.objects
            .exclude(id__in=[-1, 1])
            .filter(
                identifier='SITEREPORT',
                parent_id=1,
                bu_id__in=bu_ids,
                plandatetime__gte=start_date,
                plandatetime__lte=end_date
            )
            .select_related('people', 'bu')
            .annotate(
                peoplename=F('people__peoplename'),
                jobstatusname=F('jobstatus'),
                buname=Case(
                    When(
                        Q(othersite='') | Q(othersite__iexact='NONE'),
                        then=F('bu__buname')
                    ),
                    default=Concat(
                        Value('other location [ '),
                        F('othersite'),
                        Value(' ]')
                    ),
                ),
                gpslocation_text=Cast('gpslocation', models.TextField()),
                pdist=F('bu__pdist')
            )
            .order_by('-plandatetime')[:250]
        )

        job_list = list(queryset)
        uuids = [str(job.uuid) for job in job_list if job.uuid]
        att_counts = AttachmentHelper.get_attachment_counts(uuids)

        result = []
        for job in job_list:
            job_dict = {
                'id': job.id,
                'plandatetime': job.plandatetime,
                'jobdesc': job.jobdesc,
                'peoplename': job.peoplename,
                'buname': job.buname,
                'qset_id': job.qset_id,
                'jobstatusname': job.jobstatusname,
                'gpslocation': job.gpslocation_text,
                'pdist': job.pdist,
                'att': att_counts.get(str(job.uuid), 0) if job.uuid else 0,
                'bu_id': job.bu_id,
                'remarks': job.remarks
            }
            result.append(job_dict)

        return result

    @staticmethod
    def incidentreportlist(bu_ids: List[int], start_date, end_date) -> List[Dict]:
        """Get incident report list."""
        from apps.activity.models.job_model import Jobneed
        from apps.activity.models.attachment_model import Attachment

        uuids_with_attachments = set(
            Attachment.objects
            .filter(attachmenttype='ATTACHMENT')
            .values_list('owner', flat=True)
        )

        queryset = (
            Jobneed.objects
            .exclude(id__in=[-1, 1])
            .filter(
                identifier='INCIDENTREPORT',
                parent_id=1,
                bu_id__in=bu_ids,
                plandatetime__gte=start_date,
                plandatetime__lte=end_date,
                uuid__in=uuids_with_attachments
            )
            .select_related('people', 'bu')
            .annotate(
                peoplename=F('people__peoplename'),
                jobstatusname=F('jobstatus'),
                buname=Case(
                    When(
                        Q(othersite='') | Q(othersite__iexact='NONE'),
                        then=F('bu__buname')
                    ),
                    default=Concat(
                        Value('other location [ '),
                        F('othersite'),
                        Value(' ]')
                    ),
                ),
                gpslocation_text=Cast('gpslocation', models.TextField())
            )
            .order_by('-plandatetime')[:250]
        )

        job_list = list(queryset)
        uuids = [str(job.uuid) for job in job_list if job.uuid]
        att_counts = AttachmentHelper.get_attachment_counts(uuids)

        result = []
        for job in job_list:
            job_dict = {
                'id': job.id,
                'plandatetime': job.plandatetime,
                'jobdesc': job.jobdesc,
                'bu_id': job.bu_id,
                'buname': job.buname,
                'peoplename': job.peoplename,
                'jobstatusname': job.jobstatusname,
                'att': att_counts.get(str(job.uuid), 0) if job.uuid else 0,
                'gpslocation': job.gpslocation_text
            }
            result.append(job_dict)

        return result

    @staticmethod
    def workpermitlist(bu_id: int) -> List[Dict]:
        """Get work permit list."""
        from apps.work_order_management.models import Wom
        from apps.activity.models.attachment_model import Attachment

        date_filter = timezone.now() - timedelta(days=100)

        uuids_with_attachments = set(
            Attachment.objects
            .filter(attachmenttype='ATTACHMENT')
            .values_list('owner', flat=True)
        )

        queryset = (
            Wom.objects
            .exclude(id=1)
            .filter(
                parent_id=1,
                bu_id=bu_id,
                cdtz__gte=date_filter,
                uuid__in=uuids_with_attachments
            )
            .select_related('qset', 'bu', 'cuser')
            .annotate(
                wptype_name=F('qset__qsetname'),
                buname=F('bu__buname'),
                user=F('cuser__peoplename')
            )
            .order_by('-cdtz')
        )

        permit_list = list(queryset)
        uuids = [str(permit.uuid) for permit in permit_list if permit.uuid]
        att_counts = AttachmentHelper.get_attachment_counts(uuids)

        result = []
        for permit in permit_list:
            permit_dict = {
                'id': permit.id,
                'cdtz': permit.cdtz,
                'seqno': permit.seqno,
                'wptype': permit.wptype_name,
                'wpstatus': permit.workpermit,
                'workstatus': permit.workstatus,
                'bu_id': permit.bu_id,
                'buname': permit.buname,
                'peoplename': permit.performedby,
                'user': permit.user,
                'att': att_counts.get(str(permit.uuid), 0) if permit.uuid else 0
            }
            result.append(permit_dict)

        return result