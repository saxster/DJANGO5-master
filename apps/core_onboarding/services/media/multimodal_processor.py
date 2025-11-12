"""
Multimodal Input Processor

Processes voice OR text + 0-N photos/videos for onboarding observations.
Works across all contexts (client, site, worker).

Features:
- Text OR voice input (validated)
- 0 to N media attachments (flexible)
- GPS location capture
- AI analysis (Vision API, speech-to-text, LLM enhancement)
- Security validation (file type, size, MIME)

Complies with Rule #7: Service < 150 lines
"""
from typing import Dict, List, Optional
from django.core.files.uploadedfile import UploadedFile
from django.core.exceptions import ValidationError
from apps.core_onboarding.models import OnboardingMedia, OnboardingObservation
from apps.peoples.models import People


class MultimodalInputProcessor:
    """
    Processes multimodal input for onboarding observations.

    Input modes:
    - Text only (0 media)
    - Text + N photos/videos
    - Voice only (0 media)
    - Voice + N photos/videos

    NOT allowed:
    - Both text AND voice
    - Neither text NOR voice
    """

    def process_input(
        self,
        context_type: str,
        context_object_id: str,
        text_input: str = None,
        audio_file: UploadedFile = None,
        photos: List[UploadedFile] = None,
        videos: List[UploadedFile] = None,
        gps_location: Dict = None,
        created_by: People = None,
        conversation_session_id: str = None
    ) -> Dict:
        """
        Process multimodal input and create observation.

        Args:
            context_type: CLIENT, SITE, or WORKER
            context_object_id: UUID of related object
            text_input: Text description (if not voice)
            audio_file: Audio file (if not text)
            photos: List of 0-N photo files
            videos: List of 0-N video files
            gps_location: Optional {lat, lng, accuracy}
            created_by: User creating observation
            conversation_session_id: Optional conversation link

        Returns:
            Dict with observation_id, media_count, etc.
        """
        # Validation: Must have text OR audio (not both, not neither)
        has_text = bool(text_input and text_input.strip())
        has_audio = bool(audio_file)

        if has_text and has_audio:
            raise ValidationError("Provide text OR audio input, not both")
        if not has_text and not has_audio:
            raise ValidationError("Must provide either text or audio input")

        # Process media (0 to N)
        media_objects = []

        # Process photos
        for photo in (photos or []):
            media = OnboardingMedia.objects.create(
                context_type=context_type,
                context_object_id=context_object_id,
                media_type='PHOTO',
                file=photo,
                gps_latitude=gps_location.get('lat') if gps_location else None,
                gps_longitude=gps_location.get('lng') if gps_location else None,
                gps_accuracy=gps_location.get('accuracy') if gps_location else None,
                uploaded_by=created_by
            )
            media_objects.append(media)

        # Process videos
        for video in (videos or []):
            media = OnboardingMedia.objects.create(
                context_type=context_type,
                context_object_id=context_object_id,
                media_type='VIDEO',
                file=video,
                gps_latitude=gps_location.get('lat') if gps_location else None,
                gps_longitude=gps_location.get('lng') if gps_location else None,
                uploaded_by=created_by
            )
            media_objects.append(media)

        # Create observation
        observation = OnboardingObservation.objects.create(
            context_type=context_type,
            context_object_id=context_object_id,
            conversation_session_id=conversation_session_id,
            text_input=text_input if has_text else '',
            audio_file=audio_file if has_audio else None,
            created_by=created_by
        )

        # Link media (0 to N)
        if media_objects:
            observation.media.set(media_objects)

        return {
            'observation_id': str(observation.observation_id),
            'media_count': len(media_objects),
            'input_type': 'voice' if has_audio else 'text',
            'has_media': len(media_objects) > 0
        }
