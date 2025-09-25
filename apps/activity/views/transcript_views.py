"""
Transcript Views

API endpoints for speech-to-text transcript management:
- Check transcript status
- Retrieve transcript content
- Manage transcription requests
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import response as rp
from django.views.generic.base import View
from apps.activity.models.job_model import JobneedDetails
from apps.core.services.speech_to_text_service import SpeechToTextService

logger = logging.getLogger("django")


class TranscriptStatusView(LoginRequiredMixin, View):
    """
    API endpoint to check transcript status for JobneedDetails

    GET parameters:
    - jobneed_detail_id: ID of the JobneedDetails instance
    - uuid: UUID of the JobneedDetails instance (alternative to ID)

    Returns JSON with transcript status and content
    """

    def get(self, request, *args, **kwargs):
        R = request.GET

        try:
            # Get JobneedDetails by ID or UUID
            jobneed_detail = None

            if R.get("jobneed_detail_id"):
                try:
                    jobneed_detail = JobneedDetails.objects.get(id=R["jobneed_detail_id"])
                except JobneedDetails.DoesNotExist:
                    return rp.JsonResponse({"error": "JobneedDetails not found"}, status=404)

            elif R.get("uuid"):
                try:
                    jobneed_detail = JobneedDetails.objects.get(uuid=R["uuid"])
                except JobneedDetails.DoesNotExist:
                    return rp.JsonResponse({"error": "JobneedDetails not found"}, status=404)
            else:
                return rp.JsonResponse({
                    "error": "Missing required parameter: jobneed_detail_id or uuid"
                }, status=400)

            # Build response data
            response_data = {
                "jobneed_detail_id": jobneed_detail.id,
                "uuid": str(jobneed_detail.uuid),
                "transcript_status": jobneed_detail.transcript_status,
                "transcript_language": jobneed_detail.transcript_language,
                "transcript_processed_at": jobneed_detail.transcript_processed_at.isoformat() if jobneed_detail.transcript_processed_at else None,
                "has_transcript": bool(jobneed_detail.transcript),
            }

            # Include transcript content if completed
            if jobneed_detail.transcript_status == 'COMPLETED' and jobneed_detail.transcript:
                response_data["transcript"] = jobneed_detail.transcript
                response_data["transcript_length"] = len(jobneed_detail.transcript)

            # Include error info if failed
            elif jobneed_detail.transcript_status == 'FAILED':
                response_data["error_message"] = "Transcription failed. Please try re-uploading the audio."

            return rp.JsonResponse(response_data, status=200)

        except Exception as e:
            logger.error(f"Error in TranscriptStatusView: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Internal server error"}, status=500)


class TranscriptManagementView(LoginRequiredMixin, View):
    """
    API endpoint for transcript management operations

    POST actions:
    - retry_transcription: Retry failed transcription
    - clear_transcript: Clear existing transcript
    """

    def post(self, request, *args, **kwargs):
        R = request.POST

        try:
            action = R.get("action")
            if not action:
                return rp.JsonResponse({"error": "Missing action parameter"}, status=400)

            # Get JobneedDetails
            jobneed_detail = None
            if R.get("jobneed_detail_id"):
                try:
                    jobneed_detail = JobneedDetails.objects.get(id=R["jobneed_detail_id"])
                except JobneedDetails.DoesNotExist:
                    return rp.JsonResponse({"error": "JobneedDetails not found"}, status=404)
            else:
                return rp.JsonResponse({"error": "Missing jobneed_detail_id"}, status=400)

            if action == "retry_transcription":
                return self._retry_transcription(jobneed_detail)
            elif action == "clear_transcript":
                return self._clear_transcript(jobneed_detail)
            else:
                return rp.JsonResponse({"error": f"Unknown action: {action}"}, status=400)

        except Exception as e:
            logger.error(f"Error in TranscriptManagementView: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Internal server error"}, status=500)

    def _retry_transcription(self, jobneed_detail):
        """Retry transcription for a JobneedDetails instance"""
        try:
            from background_tasks.tasks import process_audio_transcript

            # Reset transcript fields
            jobneed_detail.transcript = None
            jobneed_detail.transcript_status = 'PENDING'
            jobneed_detail.transcript_processed_at = None
            jobneed_detail.save()

            # Queue new transcription task
            process_audio_transcript.delay(jobneed_detail.id)

            logger.info(f"Transcription retry queued for JobneedDetails {jobneed_detail.id}")

            return rp.JsonResponse({
                "status": "success",
                "message": "Transcription retry queued",
                "transcript_status": "PENDING"
            }, status=200)

        except Exception as e:
            logger.error(f"Error retrying transcription: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Failed to retry transcription"}, status=500)

    def _clear_transcript(self, jobneed_detail):
        """Clear existing transcript data"""
        try:
            jobneed_detail.transcript = None
            jobneed_detail.transcript_status = None
            jobneed_detail.transcript_language = None
            jobneed_detail.transcript_processed_at = None
            jobneed_detail.save()

            logger.info(f"Transcript cleared for JobneedDetails {jobneed_detail.id}")

            return rp.JsonResponse({
                "status": "success",
                "message": "Transcript cleared",
                "transcript_status": None
            }, status=200)

        except Exception as e:
            logger.error(f"Error clearing transcript: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Failed to clear transcript"}, status=500)


class SpeechServiceStatusView(LoginRequiredMixin, View):
    """
    API endpoint to check speech-to-text service status and configuration
    """

    def get(self, request, *args, **kwargs):
        try:
            # Initialize service to check status
            service = SpeechToTextService()

            response_data = {
                "service_available": service.is_service_available(),
                "supported_languages": service.get_supported_languages(),
                "default_language": service.DEFAULT_LANGUAGE,
                "max_file_size_mb": service.MAX_FILE_SIZE / (1024 * 1024),
                "chunk_duration_seconds": service.CHUNK_DURATION,
            }

            # Add configuration status
            from django.conf import settings
            credentials_configured = hasattr(settings, 'GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_configured:
                import os
                credentials_exist = os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS)
                response_data["credentials_configured"] = credentials_exist
            else:
                response_data["credentials_configured"] = False

            return rp.JsonResponse(response_data, status=200)

        except Exception as e:
            logger.error(f"Error in SpeechServiceStatusView: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Internal server error"}, status=500)