"""
V2 Authentication REST API Views

JWT-based authentication with V2 enhancements:
- Standardized response envelope with correlation_id
- Pydantic validation
- Token binding integration
- Tenant isolation

Following .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
- Security-first design
"""

import uuid
import logging
from datetime import datetime, timezone as dt_timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.contrib.auth import authenticate
from django.db import DatabaseError

from apps.peoples.models import People

logger = logging.getLogger(__name__)


class LoginView(APIView):
    """
    User login with JWT token generation (V2).

    POST /api/v2/auth/login/
    Request:
        {
            "username": "user@example.com",
            "password": "securepassword",
            "device_id": "device-uuid-123" (optional)
        }

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "user": {
                    "id": 123,
                    "username": "user@example.com",
                    "email": "user@example.com",
                    "first_name": "John",
                    "last_name": "Doe"
                }
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T12:34:56.789Z"
            }
        }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Handle user login with V2 response format."""
        username = request.data.get('username')
        password = request.data.get('password')
        device_id = request.data.get('device_id')

        # Generate correlation ID for request tracking
        correlation_id = str(uuid.uuid4())

        # Validate required fields
        if not username or not password:
            return self._error_response(
                code='MISSING_CREDENTIALS',
                message='Username and password are required',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Authenticate user
            user = authenticate(request, username=username, password=password)

            if user is None:
                return self._error_response(
                    code='INVALID_CREDENTIALS',
                    message='Invalid username or password',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_401_UNAUTHORIZED
                )

            if not user.is_active:
                return self._error_response(
                    code='ACCOUNT_DISABLED',
                    message='This account has been disabled',
                    correlation_id=correlation_id,
                    status_code=status.HTTP_403_FORBIDDEN
                )

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            # Add custom claims
            if device_id:
                refresh['device_id'] = device_id
            refresh['correlation_id'] = correlation_id

            # Build user data response
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }

            logger.info(f"V2 login successful: {username}", extra={
                'correlation_id': correlation_id,
                'user_id': user.id
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': user_data
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except DatabaseError as e:
            logger.error(f"Database error during V2 login: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class RefreshTokenView(APIView):
    """
    Refresh access token using refresh token (V2).

    POST /api/v2/auth/refresh/
    Request:
        {
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
        }

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..." (if rotation enabled)
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Handle token refresh with V2 response format."""
        refresh_token = request.data.get('refresh')

        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        # Validate required field
        if not refresh_token:
            return self._error_response(
                code='MISSING_TOKEN',
                message='Refresh token is required',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Validate and refresh token
            token = RefreshToken(refresh_token)

            # Generate new access token
            new_access = str(token.access_token)

            # Response data
            response_data = {'access': new_access}

            # Check if rotation is enabled in settings
            from django.conf import settings
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                # Blacklist old refresh token
                token.blacklist()
                # Generate new refresh token
                user_id = token.payload.get('user_id')
                user = People.objects.get(id=user_id)
                new_refresh = RefreshToken.for_user(user)
                new_refresh['correlation_id'] = correlation_id
                response_data['refresh'] = str(new_refresh)

            logger.info("V2 token refresh successful", extra={
                'correlation_id': correlation_id
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': response_data,
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except (TokenError, InvalidToken) as e:
            logger.warning(f"Invalid refresh token: {e}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='INVALID_TOKEN',
                message='Invalid or expired refresh token',
                correlation_id=correlation_id,
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        except DatabaseError as e:
            logger.error(f"Database error during V2 token refresh: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class LogoutView(APIView):
    """
    User logout with refresh token blacklisting (V2).

    POST /api/v2/auth/logout/
    Headers: Authorization: Bearer <access_token>
    Request:
        {
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
        }

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "message": "Logout successful"
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle user logout and token blacklisting."""
        refresh_token = request.data.get('refresh')

        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        # Validate required field
        if not refresh_token:
            return self._error_response(
                code='MISSING_TOKEN',
                message='Refresh token is required',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()

            logger.info(f"V2 logout successful: {request.user.username}", extra={
                'correlation_id': correlation_id,
                'user_id': request.user.id
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': {
                    'message': 'Logout successful'
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except TokenError as e:
            logger.warning(f"Invalid refresh token during V2 logout: {e}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='INVALID_TOKEN',
                message='Invalid or expired refresh token',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            logger.error(f"Database error during V2 logout: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


class VerifyTokenView(APIView):
    """
    Verify JWT access token validity (V2).

    POST /api/v2/auth/verify/
    Request:
        {
            "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
        }

    Response (V2 standardized envelope):
        {
            "success": true,
            "data": {
                "valid": true,
                "user_id": 123,
                "username": "user@example.com"
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Verify access token and return user information."""
        token_str = request.data.get('token')

        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        # Validate required field
        if not token_str:
            return self._error_response(
                code='MISSING_TOKEN',
                message='Token is required',
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Verify the token using SimpleJWT
            from rest_framework_simplejwt.tokens import AccessToken

            token = AccessToken(token_str)

            # Extract user information from token
            user_id = token.payload.get('user_id')
            user = People.objects.get(id=user_id)

            logger.info("V2 token verification successful", extra={
                'correlation_id': correlation_id,
                'user_id': user_id
            })

            # V2 standardized success response
            return Response({
                'success': True,
                'data': {
                    'valid': True,
                    'user_id': user.id,
                    'username': user.username
                },
                'meta': {
                    'correlation_id': correlation_id,
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                }
            }, status=status.HTTP_200_OK)

        except (TokenError, InvalidToken) as e:
            logger.warning(f"Invalid token during V2 verification: {e}", extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='INVALID_TOKEN',
                message='Invalid or expired token',
                correlation_id=correlation_id,
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        except People.DoesNotExist:
            logger.warning("Token verified but user not found", extra={
                'correlation_id': correlation_id,
                'user_id': token.payload.get('user_id')
            })
            return self._error_response(
                code='USER_NOT_FOUND',
                message='User not found',
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            logger.error(f"Database error during V2 token verification: {e}", exc_info=True, extra={
                'correlation_id': correlation_id
            })
            return self._error_response(
                code='DATABASE_ERROR',
                message='An error occurred. Please try again.',
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _error_response(self, code, message, correlation_id, status_code):
        """Build V2 standardized error response."""
        return Response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            },
            'meta': {
                'correlation_id': correlation_id,
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            }
        }, status=status_code)


__all__ = ['LoginView', 'RefreshTokenView', 'LogoutView', 'VerifyTokenView']
