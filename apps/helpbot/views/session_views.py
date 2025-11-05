"""
HelpBot Session Views

Handles session management and security scorecard generation.
"""

import logging
from datetime import datetime

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.helpbot.models import HelpBotSession
from apps.helpbot.services import HelpBotConversationService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class SecurityScorecardView(APIView):
    """
    Security & Facility Mentor Scorecard API.
    Generates and returns non-negotiables scorecard for current user's client.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.conversation_service = HelpBotConversationService()

    def get(self, request):
        """Get scorecard for current user's client."""
        try:
            session = self._get_or_create_session(request.user)
            check_date = self._parse_check_date(request.query_params.get('check_date'))
            scorecard_data = self._generate_scorecard(session, check_date)

            if not scorecard_data['success']:
                return self._error_response(
                    scorecard_data.get('error', 'Failed to generate scorecard'),
                    status.HTTP_400_BAD_REQUEST
                )

            return Response(scorecard_data['scorecard'])

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return self._error_response(
                'Invalid date format. Use YYYY-MM-DD',
                status.HTTP_400_BAD_REQUEST
            )
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error generating scorecard: {e}", exc_info=True)
            return self._error_response(
                'Internal server error',
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Refresh scorecard (same as GET but with optional parameters in body)."""
        try:
            session = self._get_or_create_session(request.user)
            check_date = self._parse_check_date(request.data.get('check_date'))
            scorecard_data = self._generate_scorecard(session, check_date)

            if not scorecard_data['success']:
                return self._error_response(
                    scorecard_data.get('error', 'Failed to generate scorecard'),
                    status.HTTP_400_BAD_REQUEST
                )

            return Response(scorecard_data['scorecard'])

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return self._error_response(
                'Invalid date format. Use YYYY-MM-DD',
                status.HTTP_400_BAD_REQUEST
            )
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error generating scorecard: {e}", exc_info=True)
            return self._error_response(
                'Internal server error',
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_or_create_session(self, user):
        """Get or create a security facility session with optimized query."""
        session = HelpBotSession.objects.select_related(
            'user',
            'user__profile',
            'tenant',
            'client'
        ).filter(
            user=user,
            session_type=HelpBotSession.SessionTypeChoices.SECURITY_FACILITY
        ).first()

        if not session:
            session = HelpBotSession.objects.create(
                user=user,
                session_type=HelpBotSession.SessionTypeChoices.SECURITY_FACILITY,
                tenant=user.tenant if hasattr(user, 'tenant') else None,
                client=user.bu if hasattr(user, 'bu') else None,
            )

        return session

    def _parse_check_date(self, check_date_str):
        """Parse check date string to date object."""
        if not check_date_str:
            return None

        return datetime.strptime(check_date_str, '%Y-%m-%d').date()

    def _generate_scorecard(self, session, check_date):
        """Generate scorecard using conversation service."""
        return self.conversation_service.generate_security_scorecard(
            session=session,
            check_date=check_date
        )

    def _error_response(self, error_message, status_code):
        """Create standardized error response."""
        return Response({'error': error_message}, status=status_code)
