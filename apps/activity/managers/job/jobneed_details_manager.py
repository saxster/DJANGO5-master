"""
JobneedDetailsManager - Custom Manager for JobneedDetails Model.

Provides specialized query methods for JobneedDetails (checklist answers) including:
- Mobile sync queries (modifiedafter)
- Checklist detail retrieval
- Attachment queries
- Asset comparison analytics
- Optimized N+1 prevention

Extracted from: apps/activity/managers/job_manager.py (lines 1578-1783)
Date: 2025-10-10
"""

from .base import (
    models, transaction, Q, F, Concat, Cast, AsGeoJSON,
    V, DatabaseError, OperationalError, ValidationError,
    logger, json, utils, settings,
    distributed_lock, LockAcquisitionError,
    ActivityManagementException, DatabaseIntegrityException,
    ErrorHandler,
    TenantAwareManager
)
from datetime import datetime


class JobneedDetailsManager(TenantAwareManager):
    """
    Custom manager for JobneedDetails model (checklist question answers).

    Extends TenantAwareManager to provide automatic tenant filtering while
    maintaining JobneedDetails-specific business logic methods.

    Provides optimized queries for:
    - Mobile sync operations (modifiedafter queries)
    - Checklist detail retrieval with attachments
    - Asset/parameter comparison analytics
    - N+1 query prevention via select_related

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    - Inherited from TenantAwareManager (apps/tenants/managers.py)
    """

    use_in_migrations = True
    related = ['question', 'jobneed', 'cuser', 'muser']
    fields = [
        'id', 'uuid', 'seqno', 'answertype', 'answer', 'isavpt', 'options',
        'ctzoffset', 'ismandatory', 'cdtz', 'mdtz', 'avpttype', 'min', 'max',
        'alerton', 'question_id', 'jobneed_id', 'alerts', 'cuser_id', 'muser_id',
        'tenant_id'
    ]

    def get_jndmodifiedafter(self, jobneedid):
        """
        Get JobneedDetails for specified jobneed IDs (mobile sync).

        Args:
            jobneedid: Comma-separated jobneed IDs

        Returns:
            QuerySet of JobneedDetails with related objects
        """
        if jobneedid:
            jobneedids = jobneedid.split(',')
            qset = self.select_related(
                *self.related
            ).filter(
                jobneed_id__in=jobneedids,
            ).values(
                *self.fields
            )
            return qset or self.none()
        return self.none()

    def update_ans_muser(self, answer, peopleid, mdtz, jnid):
        """
        Update answer and modification metadata for a jobneed.

        Args:
            answer: New answer value
            peopleid: ID of person making the update
            mdtz: Modification datetime string (YYYY-MM-DD HH:MM:SS)
            jnid: Jobneed ID

        Returns:
            Number of rows updated
        """
        _mdtz = datetime.strptime(mdtz, "%Y-%m-%d %H:%M:%S")
        return self.filter(jobneed_id=jnid).update(
            muser_id=peopleid,
            answer=answer,
            mdtz=_mdtz
        )

    def get_jnd_observation(self, id):
        """
        Get JobneedDetails observations for a jobneed (ordered by sequence).

        Args:
            id: Jobneed ID

        Returns:
            QuerySet ordered by seqno with jobneed and question preloaded
        """
        qset = self.select_related(
            'jobneed', 'question'
        ).filter(
            jobneed_id=id
        ).order_by('seqno')
        return qset or self.none()

    def get_jndofjobneed(self, R):
        """
        Get JobneedDetails for a jobneed with attachment counts.

        Args:
            R: Request dict with 'jobneedid' key

        Returns:
            List of dicts with checklist details and attachment counts
        """
        from apps.activity.models.attachment_model import Attachment

        # Get base queryset with all fields
        qset = self.filter(
            jobneed_id=R['jobneedid']
        ).select_related(
            'jobneed', 'question'
        ).annotate(
            quesname=F('question__quesname')
        ).values(
            'quesname', 'answertype', 'answer', 'min', 'max',
            'alerton', 'ismandatory', 'options', 'question_id', 'pk',
            'ctzoffset', 'seqno', 'uuid'
        ).order_by('seqno')

        # Convert to list and add attachment counts
        result_list = list(qset)
        for item in result_list:
            # Count attachments for this JobneedDetails UUID
            attachment_count = Attachment.objects.filter(
                owner=str(item['uuid']),
                attachmenttype__in=['ATTACHMENT', 'SIGN', 'IMAGE', 'VIDEO', 'AUDIO', 'OTHER']
            ).count()
            item['attachmentcount'] = attachment_count

        return result_list

    def get_e_tour_checklist_details(self, jobneedid):
        """
        Get external tour checklist details for a jobneed.

        Args:
            jobneedid: Jobneed ID

        Returns:
            QuerySet with checklist question details ordered by seqno
        """
        qset = self.filter(
            jobneed_id=jobneedid
        ).select_related('question').values(
            'question__quesname', 'answertype', 'min', 'max', 'id', 'ctzoffset',
            'options', 'alerton', 'ismandatory', 'seqno', 'answer', 'alerts'
        ).order_by('seqno')
        return qset or self.none()

    def getAttachmentJND(self, id):
        """
        Get attachments for a JobneedDetails record.

        Args:
            id: JobneedDetails ID

        Returns:
            QuerySet of attachments with file URLs and GPS locations
        """
        if qset := self.filter(id=id).values('uuid'):
            if atts := self.get_atts(qset[0]['uuid']):
                return atts or self.none()
        return self.none()

    def get_atts(self, uuid):
        """
        Get attachments for a UUID owner.

        Args:
            uuid: Owner UUID

        Returns:
            QuerySet of attachments with generated file URLs
        """
        from apps.activity.models import Attachment
        if atts := Attachment.objects.annotate(
            file=Concat(
                V(settings.MEDIA_URL, output_field=models.CharField()),
                F('filepath'),
                Cast('filename', output_field=models.CharField())
            ),
            location=AsGeoJSON('gpslocation')
        ).filter(owner=uuid).values(
            'filepath', 'filename', 'location', 'attachmenttype',
            'datetime', 'id', 'file', 'ctzoffset'
        ):
            return atts
        return self.none()

    def get_task_details(self, taskid):
        """
        Get task checklist details with attachment counts.

        Args:
            taskid: Task (jobneed) ID

        Returns:
            List of dicts with checklist details and attachment counts
        """
        from apps.activity.models.attachment_model import Attachment

        # Get base queryset with all fields except attachmentcount
        qset = self.filter(
            jobneed_id=taskid
        ).select_related('question').values(
            'question__quesname', 'answertype', 'min', 'max', 'id',
            'options', 'alerton', 'ismandatory', 'seqno', 'answer',
            'alerts', 'uuid'
        ).order_by('seqno')

        # Convert to list and add attachment counts
        result_list = list(qset)
        for item in result_list:
            # Count attachments for this JobneedDetails UUID
            attachment_count = Attachment.objects.filter(
                owner=str(item['uuid']),
                attachmenttype__in=['ATTACHMENT', 'SIGN', 'IMAGE', 'VIDEO', 'AUDIO', 'OTHER']
            ).count()
            item['attachmentcount'] = attachment_count

        return result_list

    def get_ppm_details(self, request):
        """
        Get PPM (Preventive Maintenance) task details from request.

        Args:
            request: HTTP request with 'taskid' in GET params

        Returns:
            List of dicts with checklist details (delegates to get_task_details)
        """
        return self.get_task_details(request.GET.get('taskid'))

    def get_asset_comparision(self, request, formData):
        """
        Get asset parameter comparison data for analytics.

        Compares numeric answers across multiple assets for a specific question
        over a date range.

        Args:
            request: HTTP request with session data (bu_id, client_id)
            formData: Form data with fromdate, uptodate, question, asset list

        Returns:
            List of series dicts with asset names and (time, value) tuples
        """
        S = request.session
        qset = self.filter(
            jobneed__identifier='TASK',
            jobneed__jobstatus='COMPLETED',
            jobneed__plandatetime__date__gte=formData.get('fromdate'),
            jobneed__plandatetime__date__lte=formData.get('uptodate'),
            jobneed__bu_id=S['bu_id'],
            answertype='NUMERIC',
            question_id=formData.get('question'),
            jobneed__client_id=S['client_id']
        ).annotate(
            plandatetime=F('jobneed__plandatetime'),
            starttime=F('jobneed__starttime'),
            jobdesc=F('jobneed__jobdesc'),
            asset_id=F('jobneed__asset_id'),
            assetcode=F('jobneed__asset__assetcode'),
            assetname=F('jobneed__asset__assetname'),
            questionname=F('question__quesname'),
            bu_id=F('jobneed__bu_id'),
            buname=F('jobneed__bu__buname'),
            answer_as_float=Cast('answer', models.FloatField())
        ).select_related('jobneed').values(
            "plandatetime", 'starttime', 'jobdesc',
            'asset_id', 'assetcode', 'questionname',
            'bu_id', 'buname', 'answer_as_float'
        )

        series = []
        from django.apps import apps
        Asset = apps.get_model('activity', 'Asset')
        for asset_id in formData.getlist('asset'):
            series.append(
                {
                    'name': Asset.objects.get(id=asset_id).assetname,
                    'data': list(qset.filter(jobneed__asset_id=asset_id).values_list('starttime', 'answer_as_float'))
                }
            )
        return series

    def get_parameter_comparision(self, request, formData):
        """
        Get parameter comparison data for a specific asset.

        Compares multiple numeric questions (parameters) for a single asset
        over a date range.

        Args:
            request: HTTP request with session data (bu_id, client_id)
            formData: Form data with fromdate, uptodate, asset, question list

        Returns:
            List of series dicts with question names and (time, value) tuples
        """
        S = request.session
        qset = self.filter(
            jobneed__identifier='TASK',
            jobneed__jobstatus='COMPLETED',
            jobneed__plandatetime__date__gte=formData.get('fromdate'),
            jobneed__plandatetime__date__lte=formData.get('uptodate'),
            jobneed__bu_id=S['bu_id'],
            answertype='NUMERIC',
            jobneed__asset_id=formData.get('asset'),
            jobneed__client_id=S['client_id']
        ).annotate(
            plandatetime=F('jobneed__plandatetime'),
            starttime=F('jobneed__starttime'),
            jobdesc=F('jobneed__jobdesc'),
            asset_id=F('jobneed__asset_id'),
            assetcode=F('jobneed__asset__assetcode'),
            assetname=F('jobneed__asset__assetname'),
            questionname=F('question__quesname'),
            bu_id=F('jobneed__bu_id'),
            buname=F('jobneed__bu__buname'),
            answer_as_float=Cast('answer', models.FloatField())
        ).select_related('jobneed').values(
            "plandatetime", 'starttime', 'jobdesc',
            'asset_id', 'assetcode', 'questionname',
            'bu_id', 'buname', 'answer_as_float'
        )

        series = []
        from django.apps import apps
        Question = apps.get_model('activity', 'Question')
        for question_id in formData.getlist('question'):
            series.append(
                {
                    'name': Question.objects.get(id=question_id).quesname,
                    'data': list(qset.filter(question_id=question_id).values_list('starttime', 'answer_as_float'))
                }
            )
        return series

    def optimized_get_with_relations(self, jobneed_detail_id):
        """
        Get JobneedDetails with all commonly accessed relationships preloaded.
        Prevents N+1 queries when accessing question, jobneed, etc.

        Args:
            jobneed_detail_id: JobneedDetails ID

        Returns:
            Single JobneedDetails instance with preloaded relations
        """
        return self.select_related(
            'question', 'jobneed', 'cuser', 'muser',
            'jobneed__performedby', 'jobneed__asset'
        ).get(id=jobneed_detail_id)
