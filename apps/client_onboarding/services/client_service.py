"""
Client Onboarding Service - Public API

Provides bounded context interface for client operations.
Returns DTOs (dicts), not model instances.

Complies with Rule #7: Service methods < 150 lines
"""
from typing import Dict, List, Optional
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import ConversationSession


class ClientService:
    """
    Public service API for Client Onboarding context.

    All external access to client context goes through this service.
    Returns DTOs (dicts/strings), NOT Django model instances.
    """

    def create_client(
        self,
        name: str,
        client_type: str,
        preferences: dict,
        conversation_session_id: str = None,
        initial_media: List[str] = None
    ) -> str:
        """
        Create new client from conversation or direct API.

        Args:
            name: Client name
            client_type: Type of client
            preferences: Client preferences dict
            conversation_session_id: Optional conversation session UUID
            initial_media: List of OnboardingMedia UUIDs

        Returns:
            client_id (UUID string)
        """
        with transaction.atomic():
            # Create business unit
            bt = Bt.objects.create(
                buname=name,
                bucode=self._generate_bucode(name),
                bupreferences=preferences
            )

            # Link to conversation if provided
            if conversation_session_id:
                session = ConversationSession.objects.get(session_id=conversation_session_id)
                session.context_object_id = str(bt.id)
                session.save()

            return str(bt.id)

    def get_client_details(self, client_id: str) -> Dict:
        """
        Get client details as DTO.

        Args:
            client_id: Client UUID string

        Returns:
            Dict with client details
        """
        try:
            bt = Bt.objects.get(id=client_id)
        except ObjectDoesNotExist:
            raise ValidationError(f"Client not found: {client_id}")

        return {
            'id': str(bt.id),
            'code': bt.bucode,
            'name': bt.buname,
            'type': bt.butype.name if bt.butype else None,
            'preferences': bt.bupreferences or {},
            'created_at': bt.cdtz.isoformat() if bt.cdtz else None,
        }

    def update_client_preferences(
        self,
        client_id: str,
        preferences: dict
    ) -> Dict:
        """Update client preferences"""
        with transaction.atomic():
            bt = Bt.objects.select_for_update().get(id=client_id)
            bt.bupreferences = {**(bt.bupreferences or {}), **preferences}
            bt.save()

        return {'id': client_id, 'preferences': bt.bupreferences}

    def get_client_sites(self, client_id: str) -> List[str]:
        """
        Get list of site IDs for this client.

        Returns:
            List of site UUID strings (not model instances)
        """
        from apps.site_onboarding.models import OnboardingSite

        sites = OnboardingSite.objects.filter(
            business_unit_id=client_id
        ).values_list('site_id', flat=True)

        return [str(site_id) for site_id in sites]

    def _generate_bucode(self, name: str) -> str:
        """Generate unique business unit code from name"""
        import re
        # Take first 3 letters, uppercase, add counter
        code_base = re.sub(r'[^A-Z]', '', name.upper())[:3]
        counter = Bt.objects.filter(bucode__startswith=code_base).count() + 1
        return f"{code_base}{counter:03d}"
