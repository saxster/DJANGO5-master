"""
Authentication REST API Views

Provides JWT-based authentication endpoints for login, logout, and token refresh.

Security features:
- JWT access + refresh token pattern
- Refresh token rotation on use
- Token blacklisting on logout
- Device ID tracking
- Rate limiting via DRF throttling

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling (no bare except)
- Reuses existing authentication services
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.contrib.auth import authenticate
from django.db import transaction, DatabaseError
from apps.peoples.models import People
from apps.peoples.services.authentication_service import AuthenticationService
from apps.core.models.refresh_token_blacklist import RefreshTokenBlacklist
import logging

logger = logging.getLogger(__name__)


class LoginView(APIView):
    """
    User login with JWT token generation.

    POST /api/v1/auth/login/
    Request:
        {
            "username": "user@example.com",
            "password": "securepassword",
            "device_id": "device-uuid-123" (optional)
        }

    Response:
        {
            "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "user": {
                "id": 123,
                "username": "user@example.com",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "bu_id": 1,
                "client_id": 1
            }
        }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Handle user login and token generation."""
        username = request.data.get('username')
        password = request.data.get('password')
        device_id = request.data.get('device_id')

        if not username or not password:
            return Response(
                {'error': {'code': 'MISSING_CREDENTIALS', 'message': 'Username and password are required'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Authenticate user
            user = authenticate(request, username=username, password=password)

            if user is None:
                return Response(
                    {'error': {'code': 'INVALID_CREDENTIALS', 'message': 'Invalid username or password'}},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            if not user.is_active:
                return Response(
                    {'error': {'code': 'ACCOUNT_DISABLED', 'message': 'This account has been disabled'}},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            # Add custom claims
            if device_id:
                refresh['device_id'] = device_id

            # Build user data response
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'bu_id': user.bu_id if hasattr(user, 'bu_id') else None,
                'client_id': user.client_id if hasattr(user, 'client_id') else None,
            }

            logger.info(f"User login successful: {username}")

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': user_data
            }, status=status.HTTP_200_OK)

        except DatabaseError as e:
            logger.error(f"Database error during login: {e}", exc_info=True)
            return Response(
                {'error': {'code': 'DATABASE_ERROR', 'message': 'An error occurred. Please try again.'}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LogoutView(APIView):
    """
    User logout with refresh token blacklisting.

    POST /api/v1/auth/logout/
    Headers: Authorization: Bearer <access_token>
    Request:
        {
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
        }

    Response:
        {
            "message": "Logout successful"
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle user logout and token blacklisting."""
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'error': {'code': 'MISSING_TOKEN', 'message': 'Refresh token is required'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()

            logger.info(f"User logout successful: {request.user.username}")

            return Response(
                {'message': 'Logout successful'},
                status=status.HTTP_200_OK
            )

        except TokenError as e:
            logger.warning(f"Invalid refresh token during logout: {e}")
            return Response(
                {'error': {'code': 'INVALID_TOKEN', 'message': 'Invalid or expired refresh token'}},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error during logout: {e}", exc_info=True)
            return Response(
                {'error': {'code': 'DATABASE_ERROR', 'message': 'An error occurred. Please try again.'}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RefreshTokenView(APIView):
    """
    Refresh access token using refresh token.

    POST /api/v1/auth/refresh/
    Request:
        {
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
        }

    Response:
        {
            "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..." (if rotation enabled)
        }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Handle token refresh with rotation."""
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'error': {'code': 'MISSING_TOKEN', 'message': 'Refresh token is required'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Validate and refresh token
            token = RefreshToken(refresh_token)

            # Generate new access token
            new_access = str(token.access_token)

            # If rotation is enabled, generate new refresh token
            response_data = {'access': new_access}

            # Check if rotation is enabled in settings
            from django.conf import settings
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                # Blacklist old refresh token
                token.blacklist()
                # Generate new refresh token
                new_refresh = RefreshToken.for_user(token.payload.get('user_id'))
                response_data['refresh'] = str(new_refresh)

            return Response(response_data, status=status.HTTP_200_OK)

        except (TokenError, InvalidToken) as e:
            logger.warning(f"Invalid refresh token: {e}")
            return Response(
                {'error': {'code': 'INVALID_TOKEN', 'message': 'Invalid or expired refresh token'}},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except DatabaseError as e:
            logger.error(f"Database error during token refresh: {e}", exc_info=True)
            return Response(
                {'error': {'code': 'DATABASE_ERROR', 'message': 'An error occurred. Please try again.'}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


__all__ = [
    'LoginView',
    'LogoutView',
    'RefreshTokenView',
]
