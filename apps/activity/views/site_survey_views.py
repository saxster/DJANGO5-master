import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Prefetch
from django.http import response as rp
from django.shortcuts import render, get_object_or_404
from django.views.generic.base import View
from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.activity.models.attachment_model import Attachment

logger = logging.getLogger("django")


class SiteSurveyListView(LoginRequiredMixin, View):
    """List view for Site Survey jobneeds with filtering and search capabilities."""

    def get(self, request, *args, **kwargs):
        R = request.GET

        # Load the list template
        if R.get("template"):
            context = {
                "status_options": [
                    ("ASSIGNED", "Assigned"),
                    ("INPROGRESS", "In Progress"),
                    ("COMPLETED", "Completed"),
                    ("PARTIALLYCOMPLETED", "Partially Completed"),
                ]
            }
            return render(request, "activity/site_survey/site_survey_list.html", context)

        # Return JSON data for DataTables
        if R.get("action") == "site_survey_list":
            # Get site survey jobneeds with related data
            site_surveys = Jobneed.objects.select_related(
                'performedby', 'asset', 'bu', 'client', 'qset'
            ).filter(
                identifier='SITESURVEY'
            )

            # Apply search filter if provided
            search_value = R.get("search", "").strip()
            if search_value:
                site_surveys = site_surveys.filter(
                    Q(jobdesc__icontains=search_value) |
                    Q(performedby__peoplename__icontains=search_value) |
                    Q(bu__buname__icontains=search_value) |
                    Q(asset__assetname__icontains=search_value)
                )

            # Apply status filter if provided
            status_filter = R.get("status")
            if status_filter and status_filter != "ALL":
                site_surveys = site_surveys.filter(jobstatus=status_filter)

            # Apply date range filter if provided
            from_date = R.get("from_date")
            to_date = R.get("to_date")
            if from_date:
                site_surveys = site_surveys.filter(plandatetime__isnull=False, plandatetime__date__gte=from_date)
            if to_date:
                site_surveys = site_surveys.filter(plandatetime__isnull=False, plandatetime__date__lte=to_date)

            # Prepare data for DataTables
            data = []
            for survey in site_surveys:
                data.append({
                    "id": survey.id,
                    "uuid": str(survey.uuid),
                    "jobdesc": survey.jobdesc,
                    "plandatetime": survey.plandatetime.strftime("%Y-%m-%d %H:%M") if survey.plandatetime else "",
                    "expirydatetime": survey.expirydatetime.strftime("%Y-%m-%d %H:%M") if survey.expirydatetime else "",
                    "performedby": survey.performedby.peoplename if survey.performedby else "Not Assigned",
                    "jobstatus": survey.get_jobstatus_display() if survey.jobstatus else "Unknown",
                    "bu_name": survey.bu.buname if survey.bu else "",
                    "asset_name": survey.asset.assetname if survey.asset else "",
                    "priority": survey.get_priority_display() if survey.priority else "",
                    "attachment_count": survey.attachmentcount,
                    "actions": f'<button class="btn btn-sm btn-primary view-detail" data-id="{survey.id}">View Details</button>'
                })

            return rp.JsonResponse({"data": data})

        # Handle delete action
        if R.get("action") == "delete" and R.get("id"):
            try:
                survey = get_object_or_404(Jobneed, id=R["id"], identifier='SITESURVEY')
                survey.delete()
                return rp.JsonResponse({"success": True, "message": "Site survey deleted successfully."})
            except (ValueError, TypeError) as e:
                logger.error(f"Error deleting site survey: {e}")
                return rp.JsonResponse({"success": False, "message": "Error deleting site survey."})


class SiteSurveyDetailView(LoginRequiredMixin, View):
    """Detail view for individual Site Survey with all related information and attachments."""

    def get(self, request, *args, **kwargs):
        R = request.GET

        # Load the detail template
        if R.get("template"):
            return render(request, "activity/site_survey/site_survey_detail.html")

        # Get site survey details
        if R.get("action") == "get_detail" and R.get("id"):
            try:
                # Get the main site survey record
                survey = Jobneed.objects.select_related(
                    'performedby', 'asset', 'bu', 'client', 'qset', 'job'
                ).prefetch_related(
                    Prefetch(
                        'jobneeddetails_set',
                        queryset=JobneedDetails.objects.select_related('question').order_by('seqno'),
                        to_attr='details'
                    )
                ).get(
                    id=R["id"],
                    identifier='SITESURVEY'
                )

                # Prepare survey basic info
                survey_data = {
                    "id": survey.id,
                    "uuid": str(survey.uuid),
                    "jobdesc": survey.jobdesc,
                    "plandatetime": survey.plandatetime.strftime("%Y-%m-%d %H:%M:%S") if survey.plandatetime else "",
                    "expirydatetime": survey.expirydatetime.strftime("%Y-%m-%d %H:%M:%S") if survey.expirydatetime else "",
                    "starttime": survey.starttime.strftime("%Y-%m-%d %H:%M:%S") if survey.starttime else "",
                    "endtime": survey.endtime.strftime("%Y-%m-%d %H:%M:%S") if survey.endtime else "",
                    "performedby": survey.performedby.peoplename if survey.performedby else "Not Assigned",
                    "jobstatus": survey.get_jobstatus_display() if survey.jobstatus else "Unknown",
                    "jobtype": survey.get_jobtype_display() if survey.jobtype else "Unknown",
                    "priority": survey.get_priority_display() if survey.priority else "",
                    "frequency": survey.get_frequency_display() if survey.frequency else "",
                    "bu_name": survey.bu.buname if survey.bu else "",
                    "bu_code": survey.bu.bucode if survey.bu else "",
                    "client_name": survey.client.buname if survey.client else "",
                    "asset_name": survey.asset.assetname if survey.asset else "",
                    "qset_name": survey.qset.qsetname if survey.qset else "",
                    "gracetime": survey.gracetime,
                    "seqno": survey.seqno,
                    "remarks": survey.remarks,
                    "attachment_count": survey.attachmentcount,
                    "gpslocation": {
                        "lat": survey.gpslocation.y if survey.gpslocation else None,
                        "lng": survey.gpslocation.x if survey.gpslocation else None
                    } if survey.gpslocation else None,
                }

                # Get survey details (questions and answers)
                details_data = []
                attachment_uuids = []

                for detail in survey.details:
                    detail_info = {
                        "id": detail.id,
                        "uuid": str(detail.uuid),
                        "seqno": detail.seqno,
                        "question": detail.question.quesname if detail.question else "No Question",
                        "answertype": detail.get_answertype_display() if detail.answertype else "",
                        "answer": detail.answer,
                        "ismandatory": detail.ismandatory,
                        "isavpt": detail.isavpt,
                        "avpttype": detail.get_avpttype_display() if detail.avpttype else "",
                        "options": detail.options,
                        "min": float(detail.min) if detail.min else None,
                        "max": float(detail.max) if detail.max else None,
                        "alerton": detail.alerton,
                        "alerts": detail.alerts,
                        "attachment_count": detail.attachmentcount
                    }
                    details_data.append(detail_info)

                    # Collect UUIDs for attachment filtering
                    if detail.uuid:
                        attachment_uuids.append(str(detail.uuid))

                # Get attachments using the collected UUIDs
                attachments_data = []
                if attachment_uuids:
                    attachments = Attachment.objects.filter(
                        owner__in=attachment_uuids
                    ).select_related('bu', 'ownername')

                    for attachment in attachments:
                        attachment_info = {
                            "id": attachment.id,
                            "uuid": str(attachment.uuid),
                            "filename": attachment.filename.name if attachment.filename else "",
                            "filepath": attachment.filepath,
                            "attachmenttype": attachment.get_attachmenttype_display(),
                            "datetime": attachment.datetime.strftime("%Y-%m-%d %H:%M:%S") if attachment.datetime else "",
                            "size": attachment.size,
                            "owner": attachment.owner,
                            "ownername": attachment.ownername.taname if attachment.ownername else "",
                            "bu_name": attachment.bu.buname if attachment.bu else "",
                            "gpslocation": {
                                "lat": attachment.gpslocation.y if attachment.gpslocation else None,
                                "lng": attachment.gpslocation.x if attachment.gpslocation else None
                            } if attachment.gpslocation else None,
                        }
                        attachments_data.append(attachment_info)

                return rp.JsonResponse({
                    "success": True,
                    "survey": survey_data,
                    "details": details_data,
                    "attachments": attachments_data
                })

            except Jobneed.DoesNotExist:
                return rp.JsonResponse({
                    "success": False,
                    "message": "Site survey not found."
                })
            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Error getting site survey detail: {e}")
                return rp.JsonResponse({
                    "success": False,
                    "message": "Error retrieving site survey details."
                })

        return rp.JsonResponse({"success": False, "message": "Invalid request."})