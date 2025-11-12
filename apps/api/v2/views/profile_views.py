"""
Profile management endpoints for mobile onboarding.

Provides REST API endpoints for:
- Current user profile retrieval and update
- Profile image upload with validation
- Profile completion status tracking
- Onboarding workflow completion
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
from django.utils import timezone
from PIL import Image
from io import BytesIO

from apps.peoples.models import People, PeopleProfile, PeopleOrganizational
from apps.peoples.permissions import HasOnboardingAccess
from apps.api.v2.serializers.profile_serializers import (
    ProfileRetrieveSerializer,
    ProfileUpdateSerializer,
    ProfileCompletionStatusSerializer,
    MarkOnboardingCompleteSerializer,
    MarkOnboardingCompleteResponseSerializer,
    ProfileImageResponseSerializer,
)


class CurrentUserProfileView(APIView):
    """
    GET /api/v2/people/profile/me/
    PATCH /api/v2/people/profile/me/

    Retrieve or update current authenticated user's profile.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        """Get current user's complete profile."""
        user = request.user

        # Prefetch related data to avoid N+1 queries
        user = People.objects.select_related(
            'peopleprofile',
            'peopleorganizational',
            'peopleorganizational__location',
            'peopleorganizational__department',
            'peopleorganizational__designation',
            'peopleorganizational__client',
            'peopleorganizational__bu',
        ).get(pk=user.pk)

        # Calculate profile completion before serializing
        if hasattr(user, 'peopleprofile'):
            user.peopleprofile.calculate_completion_percentage()

        serializer = ProfileRetrieveSerializer(user)
        return Response(serializer.data)

    @transaction.atomic
    def patch(self, request):
        """Update current user's profile (partial update)."""
        user = request.user

        serializer = ProfileUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Recalculate completion percentage
        if hasattr(user, 'peopleprofile'):
            user.peopleprofile.calculate_completion_percentage()

        # Return updated profile (avoid second GET request)
        return self.get(request)


class ProfileImageUploadView(APIView):
    """
    POST /api/v2/people/profile/me/image/

    Upload profile image with validation.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF'}
    MIN_DIMENSIONS = (200, 200)
    MAX_DIMENSIONS = (2048, 2048)

    def post(self, request):
        """Upload and validate profile image."""
        if 'image' not in request.FILES:
            return Response(
                {'error': 'No image file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        image_file = request.FILES['image']

        # Validate file size
        if image_file.size > self.MAX_IMAGE_SIZE:
            return Response(
                {'error': 'Image file too large. Maximum size is 5MB'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate format and dimensions
        try:
            img = Image.open(image_file)

            if img.format not in self.ALLOWED_FORMATS:
                allowed = ', '.join(f'image/{fmt.lower()}' for fmt in self.ALLOWED_FORMATS)
                return Response(
                    {'error': f'Invalid file type. Allowed: {allowed}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            width, height = img.size
            if width < self.MIN_DIMENSIONS[0] or height < self.MIN_DIMENSIONS[1]:
                return Response(
                    {'error': f'Image dimensions too small. Minimum: {self.MIN_DIMENSIONS[0]}x{self.MIN_DIMENSIONS[1]} pixels'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if width > self.MAX_DIMENSIONS[0] or height > self.MAX_DIMENSIONS[1]:
                return Response(
                    {'error': f'Image dimensions too large. Maximum: {self.MAX_DIMENSIONS[0]}x{self.MAX_DIMENSIONS[1]} pixels'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            return Response(
                {'error': 'Invalid image file'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save to profile
        user = request.user
        profile, created = PeopleProfile.objects.get_or_create(
            people=user,
            defaults={'dateofbirth': timezone.now().date()}  # Required field
        )

        # Use secure upload path
        profile.peopleimg = image_file
        profile.save()

        # Recalculate completion
        new_percentage = profile.calculate_completion_percentage()

        # Build image URL (handle both S3 and local storage)
        image_url = request.build_absolute_uri(profile.peopleimg.url) if profile.peopleimg else None

        return Response({
            'image_url': image_url,
            'profile_completion_percentage': new_percentage
        })


class ProfileCompletionStatusView(APIView):
    """
    GET /api/v2/people/profile/completion-status/

    Get profile completion status (requires onboarding capability).
    """
    permission_classes = [IsAuthenticated, HasOnboardingAccess]

    def get(self, request):
        """Get detailed completion status."""
        user = request.user

        # Ensure profile exists
        profile, created = PeopleProfile.objects.get_or_create(
            people=user,
            defaults={'dateofbirth': timezone.now().date()}  # Required field
        )

        # Calculate current completion
        completion_percentage = profile.calculate_completion_percentage()
        missing_fields = profile.get_missing_profile_fields()

        data = {
            'is_complete': completion_percentage == 100,
            'completion_percentage': completion_percentage,
            'missing_fields': missing_fields,
            'has_completed_onboarding': user.has_completed_onboarding(),
            'onboarding_completed_at': user.onboarding_completed_at.isoformat() if user.onboarding_completed_at else None,
            'onboarding_skipped': user.onboarding_skipped,
            'first_login_completed': user.first_login_completed,
            'can_skip_onboarding': completion_percentage >= 50,
            'required_documents': [],  # Placeholder for future document requirements
            'onboarding_workflow_state': user.people_extras.get('onboarding', {}).get('workflow_state', None),
        }

        return Response(data)


class MarkOnboardingCompleteView(APIView):
    """
    POST /api/v2/people/profile/mark-onboarding-complete/

    Mark onboarding as complete or skipped (requires onboarding capability).
    """
    permission_classes = [IsAuthenticated, HasOnboardingAccess]
    parser_classes = [JSONParser]

    VALID_STEPS = {'welcome', 'permissions', 'profile_setup', 'safety_briefing', 'feature_tour', 'voice_enrollment'}

    @transaction.atomic
    def post(self, request):
        """Mark onboarding complete."""
        serializer = MarkOnboardingCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        skipped = serializer.validated_data['skipped']
        completed_steps = serializer.validated_data.get('completed_steps', [])

        # Validate steps
        invalid_steps = set(completed_steps) - self.VALID_STEPS
        if invalid_steps:
            return Response(
                {'errors': {'completed_steps': [f'Invalid step: {step}' for step in invalid_steps]}},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        # Update onboarding status
        user.first_login_completed = True

        if skipped:
            user.onboarding_skipped = True
            user.onboarding_completed_at = None
        else:
            user.onboarding_skipped = False
            user.onboarding_completed_at = timezone.now()

        # Store metadata in people_extras
        user.people_extras = user.people_extras or {}
        user.people_extras['onboarding'] = {
            'completed_steps': completed_steps,
            'completed_at': user.onboarding_completed_at.isoformat() if user.onboarding_completed_at else None,
            'skipped': skipped,
            'version': '1.0',
        }

        user.save(update_fields=['first_login_completed', 'onboarding_completed_at', 'onboarding_skipped', 'people_extras'])

        response_data = {
            'success': True,
            'onboarding_completed_at': user.onboarding_completed_at.isoformat() if user.onboarding_completed_at else None,
            'onboarding_skipped': user.onboarding_skipped,
            'first_login_completed': user.first_login_completed,
        }

        return Response(response_data)
