import json
import logging
import mimetypes
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.http import response as rp
from django.views.generic.base import View
from apps.activity.models.attachment_model import Attachment
from apps.activity.models.job_model import Job
import apps.activity.utils as av_utils
import apps.onboarding.models as obm
from apps.core import utils
from apps.onboarding.utils import is_point_in_geofence, polygon_to_address
from apps.service.utils import get_model_or_form
import time
from requests.exceptions import RequestException

logger = logging.getLogger("django")


def get_address(lat, lon):
    if lat == 0.0 and lon == 0.0:
        return "Invalid coordinates"

    for attempt in range(3):  # Retry up to 3 times
        try:
            response = av_utils.get_address_from_coordinates(lat, lon)
            if response and response.get("full_address"):
                return response.get("full_address")
        except RequestException as e:
            logger.warning(f"Retrying due to error: {e}")
            time.sleep(2**attempt)  # Exponential backoff
    logger.error(
        f"Failed to retrieve address after retries for coordinates: {lat}, {lon}"
    )
    return "Address lookup failed"


class Attachments(LoginRequiredMixin, View):
    params = {"model": Attachment}

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        if R.get("action") == "delete_att" and R.get("id"):
            result = P["model"].objects.optimized_delete_by_id(R["id"])
            if not result:
                return rp.JsonResponse({"error": "Attachment not found"}, status=404)

            if R["ownername"].lower() in ["ticket", "jobneed", "jobneeddetails"]:
                model = get_model_or_form(R["ownername"].lower())
                model.objects.filter(uuid=R["ownerid"]).update(
                    attachmentcount=P["model"]
                    .objects.filter(owner=R["ownerid"])
                    .count()
                )
            return rp.JsonResponse({"result": result['deleted']}, status=200)

        if R.get("action") == "get_attachments_of_owner" and R.get("owner"):
            objs = P["model"].objects.get_att_given_owner(R["owner"])
            return rp.JsonResponse({"data": list(objs)}, status=200)

        if R.get("action") == "download" and R.get("filepath") and R.get("filename"):
            # SECURE FILE DOWNLOAD - prevent path traversal attacks
            from apps.core.services.secure_file_download_service import SecureFileDownloadService
            from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
            from django.http import Http404

            try:
                # Use SecureFileDownloadService for safe file retrieval
                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath=R.get("filepath"),
                    filename=R.get("filename"),
                    user=request.user,
                    owner_id=R.get("ownerid")  # Optional: for access control
                )
                return response

            except (PermissionDenied, SuspiciousFileOperation) as e:
                logger.error(
                    "Security violation during file download",
                    extra={
                        'user_id': request.user.id if request.user else None,
                        'filepath': R.get("filepath"),
                        'filename': R.get("filename"),
                        'error': str(e)
                    }
                )
                return rp.JsonResponse(
                    {"error": "Access denied"},
                    status=403
                )

            except Http404 as e:
                logger.warning(
                    "File not found during download request",
                    extra={
                        'user_id': request.user.id if request.user else None,
                        'filepath': R.get("filepath"),
                        'filename': R.get("filename")
                    }
                )
                return rp.JsonResponse(
                    {"error": "File not found"},
                    status=404
                )

            except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
                logger.error(
                    "Unexpected error during file download",
                    extra={
                        'user_id': request.user.id if request.user else None,
                        'filepath': R.get("filepath"),
                        'filename': R.get("filename"),
                        'error': str(e)
                    },
                    exc_info=True
                )
                return rp.JsonResponse(
                    {"error": "File download failed"},
                    status=500
                )

    def post(self, request, *args, **kwargs):
        R, P = request.POST, self.params
        if "img" in request.FILES:
            isUploaded, filename, filepath = utils.upload(request)
            filepath = filepath.replace(settings.MEDIA_ROOT, "")
            if isUploaded:
                if data := P["model"].objects.create_att_record(
                    request, filename, filepath
                ):
                    # update attachment count
                    if data["ownername"].lower() in [
                        "ticket",
                        "jobneed",
                        "jobneeddetails",
                        "wom",
                    ]:
                        model = get_model_or_form(data["ownername"].lower())
                        model.objects.filter(uuid=R["ownerid"]).update(
                            attachmentcount=data["attcount"]
                        )

                    # NEW: Auto-trigger transcription for audio attachments on jobneeddetails
                    if (data["ownername"].lower() == "jobneeddetails" and
                        self._is_audio_file(data["filename"])):
                        self._trigger_audio_transcription(R["ownerid"], data["filename"])
                        # Add transcript status to response
                        data["transcript_status"] = "PENDING"

                return rp.JsonResponse(data, status=200, safe=False)
        return rp.JsonResponse({"error": "Invalid Request"}, status=404)

    def _is_audio_file(self, filename: str) -> bool:
        """Check if uploaded file is an audio file based on extension"""
        audio_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma']
        return any(filename.lower().endswith(ext) for ext in audio_extensions)

    def _trigger_audio_transcription(self, jobneed_detail_uuid: str, filename: str):
        """Trigger background transcription task for audio attachment"""
        try:
            from apps.activity.models.job_model import JobneedDetails
            from background_tasks.tasks import process_audio_transcript

            # Get JobneedDetails ID from UUID
            jobneed_detail = JobneedDetails.objects.get(uuid=jobneed_detail_uuid)

            # Set initial transcript status
            jobneed_detail.transcript_status = 'PENDING'
            jobneed_detail.save()

            # Queue the background transcription task
            process_audio_transcript.delay(jobneed_detail.id)

            logger.info(f"Audio transcription queued for JobneedDetails {jobneed_detail.id}, file: {filename}")

        except JobneedDetails.DoesNotExist:
            logger.error(f"JobneedDetails not found for UUID: {jobneed_detail_uuid}")
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to trigger audio transcription: {str(e)}", exc_info=True)


class PreviewImage(LoginRequiredMixin, View):
    P = {"model": Attachment}

    def get(self, request, *args, **kwargs):
        R = request.GET
        S = request.session

        if R.get("action") == "getFRStatus" and R.get("uuid"):
            try:
                # Fetch data
                resp = self.P["model"].objects.get_fr_status(R["uuid"])

                # Validate eventlog_in_out
                if not resp.get("eventlog_in_out") or not resp["eventlog_in_out"][0]:
                    return rp.JsonResponse(
                        {"error": "Invalid eventlog_in_out data"}, status=400
                    )

                eventlog_entry = resp["eventlog_in_out"][0]
                get_people = Job.objects.filter(
                    people_id=eventlog_entry["people_id"], identifier="GEOFENCE"
                ).values()
                base_address = ""

                if get_people:
                    get_geofence_data = (
                        obm.GeofenceMaster.objects.filter(
                            id=get_people[0]["geofence_id"], enable=True
                        )
                        .exclude(id=1)
                        .values()
                    )
                    if get_geofence_data:
                        base_address = polygon_to_address(
                            get_geofence_data[0]["geofence"]
                        )

                # Handle startgps
                start_address = ""
                startgps = eventlog_entry.get("startgps")
                if startgps:
                    try:
                        start_coordinates = json.loads(startgps).get("coordinates")
                        if start_coordinates and len(start_coordinates) >= 2:
                            start_address = get_address(
                                start_coordinates[1], start_coordinates[0]
                            )
                    except (ValueError, KeyError, TypeError) as e:
                        logger.error(
                            f"Error parsing startgps: {e}, startgps: {startgps}"
                        )
                        start_address = "Error parsing startgps"

                # Handle endgps
                end_address = ""
                endgps = eventlog_entry.get("endgps")
                if endgps:
                    try:
                        end_coordinates = json.loads(endgps).get("coordinates")
                        if end_coordinates and len(end_coordinates) >= 2:
                            end_address = get_address(
                                end_coordinates[1], end_coordinates[0]
                            )
                    except (ValueError, KeyError, TypeError) as e:
                        logger.error(f"Error parsing endgps: {e}, endgps: {endgps}")
                        end_address = "Error parsing endgps"

                # Determine in_address and out_address
                if start_address and get_people and get_geofence_data:
                    eventlog_entry["in_address"] = (
                        f"{start_address} (Inside Geofence)"
                        if is_point_in_geofence(
                            start_coordinates[1],
                            start_coordinates[0],
                            get_geofence_data[0]["geofence"],
                        )
                        else f"{start_address} (Outside Geofence)"
                    )
                else:
                    eventlog_entry["in_address"] = start_address or "Unknown address"

                if end_address and get_people and get_geofence_data:
                    eventlog_entry["out_address"] = (
                        f"{end_address} (Inside Geofence)"
                        if is_point_in_geofence(
                            end_coordinates[1],
                            end_coordinates[0],
                            get_geofence_data[0]["geofence"],
                        )
                        else f"{end_address} (Outside Geofence)"
                    )
                else:
                    eventlog_entry["out_address"] = end_address or "Unknown address"

                eventlog_entry["base_address"] = base_address
                return rp.JsonResponse(resp, status=200)

            except self.P["model"].objects.model.DoesNotExist:
                logger.error(f"Model not found for uuid: {R.get('uuid')}")
                return rp.JsonResponse({"error": "Data not found"}, status=404)

            except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
                logger.error(f"Unexpected error: {e}")
                return rp.JsonResponse({"error": "Internal server error"}, status=500)

        # Handle general attachment preview by ID
        if R.get("id"):
            from apps.core.services.secure_file_download_service import SecureFileDownloadService
            from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
            from django.http import Http404

            try:
                # Validate attachment access using secure service
                attachment = SecureFileDownloadService.validate_attachment_access(
                    attachment_id=R["id"],
                    user=request.user
                )

                # Get file path components from attachment
                filepath = str(attachment.filepath) if attachment.filepath else ""
                filename = str(attachment.filename.name if hasattr(attachment.filename, 'name') else attachment.filename)

                # Use SecureFileDownloadService for safe file retrieval
                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath=filepath,
                    filename=filename,
                    user=request.user,
                    owner_id=attachment.owner if hasattr(attachment, 'owner') else None
                )

                return response

            except (PermissionDenied, SuspiciousFileOperation) as e:
                logger.error(
                    "Security violation during attachment preview",
                    extra={
                        'user_id': request.user.id if request.user else None,
                        'attachment_id': R.get("id"),
                        'error': str(e)
                    }
                )
                return rp.JsonResponse({"error": "Access denied"}, status=403)

            except Http404:
                logger.warning(
                    "Attachment not found",
                    extra={
                        'user_id': request.user.id if request.user else None,
                        'attachment_id': R.get("id")
                    }
                )
                return rp.JsonResponse({"error": "Attachment not found"}, status=404)

            except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
                logger.error(
                    "Error retrieving attachment",
                    extra={
                        'user_id': request.user.id if request.user else None,
                        'attachment_id': R.get("id"),
                        'error': str(e)
                    },
                    exc_info=True
                )
                return rp.JsonResponse({"error": "Error retrieving attachment"}, status=500)

        return rp.JsonResponse({"error": "Invalid request"}, status=400)
