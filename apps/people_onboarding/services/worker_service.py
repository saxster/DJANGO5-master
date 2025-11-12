"""
Worker Onboarding Service - Public API

Manages worker intake, document verification, provisioning.
"""
from typing import Dict, List
from django.db import transaction
from apps.people_onboarding.models import OnboardingRequest, OnboardingTask, WorkerDocument


class WorkerService:
    """Public API for worker onboarding context"""

    def create_onboarding_request(
        self,
        person_type: str,
        client_id: str,
        site_id: str = None,
        conversation_session_id: str = None
    ) -> str:
        """
        Create worker onboarding request.

        Args:
            person_type: EMPLOYEE_FULLTIME, CONTRACTOR, etc.
            client_id: Client UUID (employer)
            site_id: Optional site UUID (assignment)
            conversation_session_id: Optional conversation UUID

        Returns:
            request_id (UUID string)
        """
        from apps.core_onboarding.models import ConversationSession

        with transaction.atomic():
            request = OnboardingRequest.objects.create(
                person_type=person_type,
                current_state='DRAFT'
            )

            # Store context
            request.context_data = {
                'client_id': client_id,
                'site_id': site_id
            }
            request.save()

            # Link conversation
            if conversation_session_id:
                session = ConversationSession.objects.get(session_id=conversation_session_id)
                request.conversation_session = session
                session.context_object_id = str(request.uuid)
                session.save()
                request.save()

            return str(request.uuid)

    def upload_document(
        self,
        request_id: str,
        document_type: str,
        media_id: str
    ) -> Dict:
        """
        Attach document to worker onboarding.

        Args:
            request_id: OnboardingRequest UUID
            document_type: PHOTO_ID, CERTIFICATE, etc.
            media_id: OnboardingMedia UUID

        Returns:
            Dict with document details
        """
        doc = WorkerDocument.objects.create(
            onboarding_request_id=request_id,
            document_type=document_type,
            media_id=media_id,
            verification_status='PENDING'
        )

        return {
            'document_id': str(doc.document_id),
            'type': document_type,
            'status': 'uploaded'
        }
