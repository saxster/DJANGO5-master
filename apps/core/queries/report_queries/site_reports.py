"""Site report queries - detailed site visit reports with attachments."""
from typing import List, Dict
from django.db.models import F
from django.db.models.functions import Cast
from django.db import models
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SiteReports:
    """Report queries for site visits."""

    @staticmethod
    def rp_sitevisitreport_report(timezone_str: str, sgroupids: str, from_date, upto_date) -> List[Dict]:
        """RP site visit report."""
        from apps.activity.models.job_model import Jobneed
        from django.db.models import Case, When, Value, CharField
        from django.db.models.functions import Extract

        sgroup_id_list = [int(id.strip()) for id in sgroupids.split(',') if id.strip()]

        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()

        reports = (
            Jobneed.objects
            .filter(
                identifier='EXTERNALTOUR',
                sgroup_id__in=sgroup_id_list,
                parent__other_info__tour_frequency='2',
                parent__plandatetime__date__range=[from_date, upto_date]
            )
            .exclude(parent_id=1)
            .select_related('bu', 'sgroup', 'parent')
            .annotate(
                state=F('bu__bupreferences__address2__state'),
                endtime_time=Case(
                    When(starttime__isnull=True, then=Value('Not Performed')),
                    default=Cast(F('starttime'), CharField()),
                    output_field=CharField()
                ),
                endtime_day=Extract('parent__plandatetime', 'day')
            )
            .values(
                'sgroup__groupname', 'state', 'bu__solid', 'bu__buname',
                'endtime_time', 'endtime_day', 'plandatetime', 'id'
            )
            .order_by('bu__buname', 'endtime_day')
        )

        result = []
        for report in reports:
            result.append({
                'Route Name/Cluster': report['sgroup__groupname'],
                'State': report['state'],
                'Sol Id': report['bu__solid'],
                'Site Name': report['bu__buname'],
                'endtime_time': report['endtime_time'],
                'endtime_day': report['endtime_day']
            })

        return result

    @staticmethod
    def sitereport_report(timezone_str: str, clientid: int, sgroupids: str, from_date, upto_date) -> List[Dict]:
        """Site report with dynamic question mapping."""
        from apps.activity.models.job_model import Jobneed, JobneedDetails

        sgroup_id_list = [int(id.strip()) for id in sgroupids.split(',') if id.strip()]
        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%d/%m/%Y %H:%M:%S').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%d/%m/%Y %H:%M:%S').date()

        parent_jobs = (Jobneed.objects.filter(parent_id=1, client_id=clientid, sgroup_id__in=sgroup_id_list,
            plandatetime__date__range=[from_date, upto_date]).select_related('bu', 'sgroup')
            .values('id', 'bu__id', 'bu__buname', 'bu__bucode', 'bu__solid', 'bu__bupreferences', 'sgroup__groupname', 'plandatetime'))

        child_jobs = (Jobneed.objects.filter(parent__in=[job['id'] for job in parent_jobs], starttime__isnull=False)
            .select_related('bu', 'performedby', 'qset').filter(qset__qsetname__iexact='SITE REPORT')
            .annotate(longitude=Cast(models.Func(F('gpslocation'), function='ST_X', template='ST_X(%(expressions)s::geometry)'), models.FloatField()),
                latitude=Cast(models.Func(F('gpslocation'), function='ST_Y', template='ST_Y(%(expressions)s::geometry)'), models.FloatField()))
            .values('id', 'parent_id', 'bu__solid', 'bu__bucode', 'bu__buname', 'bu__bupreferences', 'starttime', 'endtime',
                'longitude', 'latitude', 'performedby__peoplecode', 'performedby__peoplename', 'performedby__mobno', 'sgroup__groupname'))

        job_details = (JobneedDetails.objects.filter(jobneed__in=[job['id'] for job in child_jobs], answer__isnull=False)
            .select_related('question').exclude(answer='').values('jobneed_id', 'question__quesname', 'answer'))

        qa_mapping = {}
        for detail in job_details:
            job_id = detail['jobneed_id']
            if job_id not in qa_mapping:
                qa_mapping[job_id] = {}
            qa_mapping[job_id][detail['question__quesname'].upper()] = detail['answer']

        result = []
        for parent_job in parent_jobs:
            matching_child = next((job for job in child_jobs if job['parent_id'] == parent_job['id']), None)
            if not matching_child:
                continue
            qa_data = qa_mapping.get(matching_child['id'], {})
            address, state = '', ''
            if matching_child['bu__bupreferences']:
                address = matching_child['bu__bupreferences'].get('address', '')
                addr2 = matching_child['bu__bupreferences'].get('address2', {})
                if isinstance(addr2, dict):
                    state = addr2.get('state', '')

            result.append({
                'SOL ID': matching_child['bu__solid'], 'ROUTE NAME': matching_child['sgroup__groupname'],
                'SITE CODE': matching_child['bu__bucode'], 'SITE NAME': matching_child['bu__buname'],
                'DATE OF VISIT': matching_child['starttime'].date() if matching_child['starttime'] else None,
                'TIME OF VISIT': matching_child['starttime'].strftime('%H:%M:%S') if matching_child['starttime'] else None,
                'LONGITUDE': matching_child['longitude'], 'LATITUDE': matching_child['latitude'],
                'RP ID': matching_child['performedby__peoplecode'], 'RP OFFICER': matching_child['performedby__peoplename'],
                'CONTACT': matching_child['performedby__mobno'], 'SITE ADDRESS': address, 'STATE': state,
                'FASCIA WORKING': qa_data.get('FASCIA WORKING', ''), 'LOLLY POP WORKING': qa_data.get('LOLLY POP WORKING', ''),
                'ATM MACHINE COUNT': qa_data.get('ATM MACHINE COUNT', ''), 'AC IN ATM COOLING': qa_data.get('AC IN ATM COOLING', ''),
                'ATM BACK ROOM LOCKED': qa_data.get('ATM BACK ROOM LOCKED', ''), 'UPS ROOM BEHIND ATM LOBBY ALL SAFE': qa_data.get('UPS ROOM BEHIND ATM LOBBY ALL SAFE', ''),
                'BRANCH SHUTTER DAMAGED': qa_data.get('BRANCH SHUTTER DAMAGED', ''), 'BRANCH PERIPHERY ROUND TAKEN': qa_data.get('BRANCH PERIPHERY ROUND TAKEN', ''),
                'AC ODU AND COPPER PIPE INTACT': qa_data.get('AC ODU AND COPPER PIPE INTACT', ''), 'ANY WATER LOGGING OR FIRE IN VICINITY': qa_data.get('ANY WATER LOGGING OR FIRE IN VICINITY', ''),
                'FE AVAILABLE IN ATM LOBBY': qa_data.get('FE AVAILABLE IN ATM LOBBY', ''), 'DG DOOR LOCKED': qa_data.get('DG DOOR LOCKED', ''),
                'DAMAGE TO ATM LOBBY': qa_data.get('DAMAGE TO ATM LOBBY', ''), 'ANY OTHER OBSERVATION': qa_data.get('ANY OTHER OBSERVATION', '')})
        return result

    @staticmethod
    def sitevisitreport_report(timezone_str: str, siteids: str, date_filter) -> List[Dict]:
        """Site visit report with attachment handling."""
        from apps.activity.models.job_model import Jobneed, JobneedDetails
        from apps.activity.models.attachment_model import Attachment

        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]

        if isinstance(date_filter, str):
            date_filter = datetime.strptime(date_filter, '%Y-%m-%d').date()

        jobs = (
            Jobneed.objects
            .filter(
                identifier='SITEREPORT',
                bu_id__in=site_id_list,
                cdtz__date=date_filter
            )
            .select_related('qset')
            .values('id', 'uuid', 'plandatetime', 'jobdesc', 'identifier', 'seqno')
            .order_by('id')
        )

        job_details = (
            JobneedDetails.objects
            .filter(jobneed__in=[job['id'] for job in jobs])
            .select_related('question')
            .values('jobneed_id', 'question__quesname', 'answer', 'seqno')
            .order_by('jobneed_id', 'seqno')
        )

        job_uuids = [str(job['uuid']) for job in jobs]
        attachments = (
            Attachment.objects
            .filter(
                owner__in=job_uuids,
                attachmenttype__in=['ATTACHMENT', None]
            )
            .values('owner', 'filename')
        )

        attachment_mapping = {}
        for att in attachments:
            attachment_mapping[att['owner']] = att['filename']

        details_mapping = {}
        for detail in job_details:
            job_id = detail['jobneed_id']
            if job_id not in details_mapping:
                details_mapping[job_id] = []
            details_mapping[job_id].append(detail)

        result = []
        for job in jobs:
            job_details_list = details_mapping.get(job['id'], [])
            attachment_filename = attachment_mapping.get(str(job['uuid']), None)

            for detail in job_details_list:
                result.append({
                    'plandatetime': job['plandatetime'],
                    'section_name': job['jobdesc'],
                    'question': detail['question__quesname'],
                    'answers': detail['answer'],
                    'attachment': attachment_filename,
                    'identifier': job['identifier'],
                    'seqno': job['seqno']
                })

        return result