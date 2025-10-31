"""
People Management REST API ViewSets

Provides CRUD operations for user management with tenant isolation.

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
- Uses permission classes
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from apps.peoples.models import People
from apps.ontology.decorators import ontology
from apps.peoples.api.serializers import (
    PeopleListSerializer,
    PeopleDetailSerializer,
    PeopleCreateSerializer,
    PeopleUpdateSerializer,
    PeopleCapabilitiesSerializer
)
from apps.api.permissions import TenantIsolationPermission, IsOwnerOrAdmin
from apps.api.pagination import MobileSyncCursorPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
import logging

logger = logging.getLogger(__name__)


@ontology(
    domain="people",
    purpose="REST API for People (user) CRUD operations with tenant isolation and multi-tenant security",
    api_endpoint=True,
    http_methods=["GET", "POST", "PATCH", "DELETE"],
    authentication_required=True,
    permissions=["IsAuthenticated", "TenantIsolationPermission"],
    rate_limit="100/minute",
    request_schema="PeopleCreateSerializer|PeopleUpdateSerializer",
    response_schema="PeopleListSerializer|PeopleDetailSerializer",
    error_codes=[400, 401, 403, 404, 500],
    pagination="MobileSyncCursorPagination",
    filtering=["bu_id", "client_id", "department", "is_active"],
    search_fields=["username", "email", "first_name", "last_name"],
    ordering_fields=["date_joined", "last_login", "first_name"],
    criticality="high",
    tags=["api", "rest", "people", "users", "multi-tenant", "mobile"],
    security_notes="Automatic tenant isolation via client_id/bu_id filtering. Owner/admin permissions for profile access. Soft delete preserves audit trail",
    endpoints={
        "list": "GET /api/v1/people/ - List all users (paginated, tenant-filtered)",
        "create": "POST /api/v1/people/ - Create new user",
        "retrieve": "GET /api/v1/people/{id}/ - Get user details",
        "update": "PATCH /api/v1/people/{id}/ - Update user (partial)",
        "delete": "DELETE /api/v1/people/{id}/ - Soft delete user",
        "profile": "GET /api/v1/people/{id}/profile/ - Get detailed profile",
        "capabilities": "PATCH /api/v1/people/{id}/capabilities/ - Update capabilities (admin only)"
    },
    examples=[
        "curl -X GET https://api.example.com/api/v1/people/ -H 'Authorization: Bearer <token>'",
        "curl -X POST https://api.example.com/api/v1/people/ -H 'Authorization: Bearer <token>' -d '{\"username\":\"john.doe\",\"email\":\"john@example.com\"}'",
        "curl -X PATCH https://api.example.com/api/v1/people/123/capabilities/ -H 'Authorization: Bearer <token>' -d '{\"capabilities\":{\"view_reports\":true}}'"
    ]
)
class PeopleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for People (user) management.

    Endpoints:
    - GET    /api/v1/people/              List all users (paginated)
    - POST   /api/v1/people/              Create new user
    - GET    /api/v1/people/{id}/         Retrieve specific user
    - PATCH  /api/v1/people/{id}/         Update user (partial)
    - DELETE /api/v1/people/{id}/         Delete user (soft delete)
    - GET    /api/v1/people/{id}/profile/ Get user profile
    - PATCH  /api/v1/people/{id}/capabilities/ Update capabilities (admin only)

    Features:
    - Tenant isolation (automatic filtering)
    - Search by name, email, username
    - Filter by bu_id, client_id, department, is_active
    - Order by date_joined, last_login, name
    - Cursor pagination for mobile sync
    """
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class = MobileSyncCursorPagination
    schema = None  # Exclude outdated people API until serializers align with refactored models

    # Filtering
    filterset_fields = ['bu_id', 'client_id', 'department', 'is_active']

    # Search
    search_fields = ['username', 'email', 'first_name', 'last_name']

    # Ordering
    ordering_fields = ['date_joined', 'last_login', 'first_name']
    ordering = ['-date_joined']  # Default ordering

    def get_queryset(self):
        """
        Get queryset with tenant filtering.

        Automatically filters by user's client_id and bu_id.
        Admins see all users.
        """
        queryset = People.objects.all()

        # Apply tenant filtering
        if not self.request.user.is_superuser:
            queryset = queryset.filter(client_id=self.request.user.client_id)

            # Optional BU filtering
            if hasattr(self.request.user, 'bu_id') and self.request.user.bu_id:
                queryset = queryset.filter(bu_id=self.request.user.bu_id)

        # Optimize queries
        queryset = queryset.select_related('bu', 'client')

        return queryset

    def get_serializer_class(self):
        """
        Return appropriate serializer based on action.

        Actions:
        - list: Lightweight serializer
        - retrieve: Full detail serializer
        - create: Create serializer with validation
        - update/partial_update: Update serializer
        - capabilities: Capabilities serializer
        """
        if self.action == 'list':
            return PeopleListSerializer
        elif self.action == 'create':
            return PeopleCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return PeopleUpdateSerializer
        elif self.action == 'capabilities':
            return PeopleCapabilitiesSerializer
        return PeopleDetailSerializer

    def perform_create(self, serializer):
        """
        Create new user with tenant assignment.

        Automatically assigns user to creator's tenant.
        """
        # Assign tenant from current user
        serializer.save(
            client_id=self.request.user.client_id,
            bu_id=self.request.user.bu_id if hasattr(self.request.user, 'bu_id') else None
        )

        logger.info(f"User created: {serializer.instance.username} by {self.request.user.username}")

    def perform_destroy(self, instance):
        """
        Soft delete user (set is_active=False).

        Preserves data for audit trail.
        """
        instance.is_active = False
        instance.save()

        logger.info(f"User deactivated: {instance.username} by {self.request.user.username}")

    @action(detail=True, methods=['get'], permission_classes=[IsOwnerOrAdmin])
    def profile(self, request, pk=None):
        """
        Get detailed user profile.

        GET /api/v1/people/{id}/profile/

        Returns complete user information including profile and organizational data.
        """
        user = self.get_object()
        serializer = PeopleDetailSerializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def capabilities(self, request, pk=None):
        """
        Update user capabilities (admin only).

        PATCH /api/v1/people/{id}/capabilities/
        Request:
            {
                "capabilities": {
                    "view_reports": true,
                    "create_reports": true,
                    "edit_reports": false
                }
            }

        Validates JSON structure and updates capabilities field.
        """
        user = self.get_object()
        serializer = PeopleCapabilitiesSerializer(
            user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"Capabilities updated for {user.username} by {request.user.username}")

        return Response(serializer.data)


__all__ = [
    'PeopleViewSet',
]
