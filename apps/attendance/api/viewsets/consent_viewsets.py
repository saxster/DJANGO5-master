"""
Consent Management API ViewSets

REST API endpoints for employee consent management.

Endpoints:
- GET /api/v1/attendance/my-consents/ - Employee's consent list
- GET /api/v1/attendance/pending-consents/ - Pending consents for employee
- POST /api/v1/attendance/grant-consent/ - Grant consent
- POST /api/v1/attendance/revoke-consent/ - Revoke consent
- GET /api/v1/attendance/consent-policies/ - Available policies
- GET /api/v1/attendance/consent-status/ - Check consent status

Admin Endpoints:
- GET /api/v1/attendance/admin/consents/ - All consents (admin)
- POST /api/v1/attendance/admin/request-consent/ - Request consent from employee
- GET /api/v1/attendance/admin/consent-compliance/ - Compliance report
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from apps.attendance.models.consent import (
    ConsentPolicy,
    EmployeeConsentLog,
    ConsentRequirement
)
from apps.attendance.api.serializers.consent_serializers import (
    ConsentPolicySerializer,
    EmployeeConsentLogSerializer,
    ConsentGrantSerializer,
    ConsentRevokeSerializer,
    ConsentRequestSerializer,
    ConsentStatusSerializer,
)
from apps.attendance.services.consent_service import (
    ConsentValidationService,
    ConsentManagementService,
    StateSpecificConsentService,
)
from apps.core.permissions import TenantIsolationPermission
from apps.attendance.exceptions import AttendanceValidationError, AttendancePermissionError
import logging

logger = logging.getLogger(__name__)


class EmployeeConsentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for employee to manage their own consents.

    Permissions:
    - Authenticated employees only
    - Can only view/manage their own consents
    """

    queryset = EmployeeConsentLog.objects.all()
    serializer_class = EmployeeConsentLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter to current user's consents only"""
        return EmployeeConsentLog.objects.filter(
            employee=self.request.user
        ).select_related('policy').order_by('-granted_at')

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """
        Get pending consents for current user.

        Returns:
            List of policies requiring consent
        """
        try:
            pending = ConsentValidationService.get_pending_consents(request.user)

            # Serialize pending consents
            response_data = []
            for item in pending:
                response_data.append({
                    'policy': ConsentPolicySerializer(item['policy']).data,
                    'is_mandatory': item['is_mandatory'],
                    'blocks_clock_in': item['blocks_clock_in'],
                })

            return Response({'pending_consents': response_data})

        except Exception as e:
            logger.error(f"Failed to get pending consents: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve pending consents'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def grant(self, request):
        """
        Grant consent for a policy.

        Request Body:
        {
            "policy_id": 123,
            "signature_data": "base64_signature_or_typed_name",
            "signature_type": "ELECTRONIC|TYPED|DRAWN"
        }

        Returns:
            Updated consent log
        """
        serializer = ConsentGrantSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            policy_id = serializer.validated_data['policy_id']
            signature_data = serializer.validated_data.get('signature_data')
            signature_type = serializer.validated_data.get('signature_type', 'ELECTRONIC')

            # Get or create consent log
            policy = ConsentPolicy.objects.get(id=policy_id)

            consent_log, created = EmployeeConsentLog.objects.get_or_create(
                employee=request.user,
                policy=policy,
                status=EmployeeConsentLog.ConsentStatus.PENDING,
                defaults={
                    'tenant': request.user.client_id if hasattr(request.user, 'client_id') else 'default'
                }
            )

            # Grant consent
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')

            ConsentManagementService.grant_consent(
                consent_log=consent_log,
                ip_address=ip_address,
                user_agent=user_agent,
                signature_data=signature_data,
                signature_type=signature_type
            )

            # Return updated consent
            return Response(
                EmployeeConsentLogSerializer(consent_log).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )

        except ConsentPolicy.DoesNotExist:
            return Response(
                {'error': 'Policy not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to grant consent: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to grant consent'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def revoke(self, request):
        """
        Revoke consent.

        Request Body:
        {
            "consent_id": 123,
            "reason": "No longer wish to share location data"
        }

        Returns:
            Updated consent log
        """
        serializer = ConsentRevokeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            consent_id = serializer.validated_data['consent_id']
            reason = serializer.validated_data['reason']

            # Get consent log (must belong to current user)
            consent_log = EmployeeConsentLog.objects.get(
                id=consent_id,
                employee=request.user
            )

            # Revoke consent
            ip_address = self._get_client_ip(request)
            ConsentManagementService.revoke_consent(
                consent_log=consent_log,
                reason=reason,
                ip_address=ip_address
            )

            return Response(EmployeeConsentLogSerializer(consent_log).data)

        except EmployeeConsentLog.DoesNotExist:
            return Response(
                {'error': 'Consent not found or does not belong to you'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to revoke consent: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to revoke consent'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def status(self, request):
        """
        Check if user can clock in (has all required consents).

        Returns:
            Consent status and missing consents
        """
        try:
            can_clock_in, missing_consents = ConsentValidationService.can_user_clock_in(
                request.user
            )

            return Response({
                'can_clock_in': can_clock_in,
                'missing_consents': missing_consents,
                'has_all_required_consents': can_clock_in,
            })

        except Exception as e:
            logger.error(f"Failed to check consent status: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to check consent status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @staticmethod
    def _get_client_ip(request) -> str:
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class ConsentPolicyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing available consent policies.

    Permissions:
    - Authenticated employees can view policies
    """

    queryset = ConsentPolicy.objects.filter(is_active=True)
    serializer_class = ConsentPolicySerializer
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['policy_type', 'state']

    def get_queryset(self):
        """Filter to active policies for user's tenant"""
        queryset = super().get_queryset()

        # Filter by tenant
        if hasattr(self.request.user, 'client_id'):
            queryset = queryset.filter(tenant=self.request.user.client_id)

        # Only show active policies within effective date range
        queryset = queryset.filter(
            effective_date__lte=timezone.now().date()
        ).filter(
            models.Q(expiration_date__isnull=True) |
            models.Q(expiration_date__gte=timezone.now().date())
        )

        return queryset


class ConsentAdminViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet for managing employee consents.

    Permissions:
    - Admin users only
    - Automatic tenant isolation
    """

    queryset = EmployeeConsentLog.objects.all()
    serializer_class = EmployeeConsentLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser, TenantIsolationPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'employee': ['exact'],
        'status': ['exact', 'in'],
        'policy__policy_type': ['exact'],
        'granted_at': ['gte', 'lte'],
    }

    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()

        if not self.request.user.is_superuser:
            queryset = queryset.filter(tenant=self.request.user.client_id)

        return queryset.select_related('employee', 'policy', 'impersonated_by')

    @action(detail=False, methods=['post'])
    def request_consent(self, request):
        """
        Request consent from an employee (admin action).

        Request Body:
        {
            "employee_id": 123,
            "policy_id": 456,
            "send_notification": true
        }

        Returns:
            Created consent log
        """
        serializer = ConsentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            employee_id = serializer.validated_data['employee_id']
            policy_id = serializer.validated_data['policy_id']
            send_notification = serializer.validated_data.get('send_notification', True)

            employee = User.objects.get(id=employee_id)
            policy = ConsentPolicy.objects.get(id=policy_id)

            # Request consent
            consent = ConsentManagementService.request_consent(
                user=employee,
                policy=policy,
                send_notification=send_notification
            )

            return Response(
                EmployeeConsentLogSerializer(consent).data,
                status=status.HTTP_201_CREATED
            )

        except (User.DoesNotExist, ConsentPolicy.DoesNotExist) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to request consent: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to request consent'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def compliance_report(self, request):
        """
        Generate consent compliance report.

        Query Parameters:
        - state: Filter by state (optional)
        - policy_type: Filter by policy type (optional)

        Returns:
            Compliance statistics
        """
        try:
            state_filter = request.query_params.get('state')
            policy_type_filter = request.query_params.get('policy_type')

            queryset = EmployeeConsentLog.objects.filter(
                tenant=request.user.client_id if hasattr(request.user, 'client_id') else 'default'
            )

            if state_filter:
                queryset = queryset.filter(policy__state=state_filter)
            if policy_type_filter:
                queryset = queryset.filter(policy__policy_type=policy_type_filter)

            # Calculate statistics
            total_employees = queryset.values('employee').distinct().count()
            granted_count = queryset.filter(status=EmployeeConsentLog.ConsentStatus.GRANTED).count()
            pending_count = queryset.filter(status=EmployeeConsentLog.ConsentStatus.PENDING).count()
            revoked_count = queryset.filter(status=EmployeeConsentLog.ConsentStatus.REVOKED).count()
            expired_count = queryset.filter(status=EmployeeConsentLog.ConsentStatus.EXPIRED).count()

            # By policy type
            from django.db.models import Count
            by_policy = dict(
                queryset.values('policy__policy_type')
                .annotate(count=Count('id'))
                .values_list('policy__policy_type', 'count')
            )

            # Expiring soon
            expiring_soon = queryset.filter(
                status=EmployeeConsentLog.ConsentStatus.GRANTED,
                expires_at__lte=timezone.now() + timezone.timedelta(days=30)
            ).count()

            return Response({
                'total_employees': total_employees,
                'granted': granted_count,
                'pending': pending_count,
                'revoked': revoked_count,
                'expired': expired_count,
                'expiring_soon_30_days': expiring_soon,
                'by_policy_type': by_policy,
                'compliance_rate': (granted_count / total_employees * 100) if total_employees > 0 else 0,
            })

        except Exception as e:
            logger.error(f"Failed to generate compliance report: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to generate compliance report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """
        Get consents expiring soon.

        Query Parameters:
        - days: Number of days to look ahead (default: 30)

        Returns:
            List of expiring consents
        """
        try:
            days = int(request.query_params.get('days', 30))
            expiring = ConsentManagementService.check_expiring_consents(days_before=days)

            return Response(
                EmployeeConsentLogSerializer(expiring, many=True).data
            )

        except Exception as e:
            logger.error(f"Failed to get expiring consents: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve expiring consents'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def send_reminders(self, request):
        """
        Send reminders for expiring consents (admin action).

        Returns:
            Number of reminders sent
        """
        try:
            sent = ConsentManagementService.send_expiration_reminders()
            return Response({'reminders_sent': sent})

        except Exception as e:
            logger.error(f"Failed to send reminders: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to send reminders'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConsentCheckMixin:
    """
    Mixin to add consent checking to attendance viewsets.

    Add this to attendance clock-in/out viewsets to enforce consent requirements.
    """

    def check_consent_before_action(self, request):
        """
        Check if user has required consents before allowing action.

        Raises:
            AttendancePermissionError: If required consents missing
        """
        can_proceed, missing_consents = ConsentValidationService.can_user_clock_in(
            request.user
        )

        if not can_proceed:
            # Format error message
            policy_names = [c['policy_title'] for c in missing_consents]
            error_message = (
                f"Cannot proceed: Missing required consent(s): {', '.join(policy_names)}. "
                f"Please review and accept consent policies at /attendance/consent/"
            )

            raise AttendancePermissionError(
                error_message,
                context={'missing_consents': missing_consents}
            )
