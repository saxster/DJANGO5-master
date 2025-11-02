"""
Contract ViewSet for Admin Configuration API

Provides REST endpoints for contract management:
- GET /api/v1/admin/config/contracts/ → List all contracts
- GET /api/v1/admin/config/contracts/{id}/ → Get specific contract

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError
from django.core.exceptions import ObjectDoesNotExist
import logging

from apps.onboarding.models import Contract
from apps.api.permissions import TenantIsolationPermission
from apps.api.pagination import MobileSyncCursorPagination

logger = logging.getLogger('onboarding_api')


class ContractViewSet(viewsets.ReadOnlyModelViewSet):
    """
    REST API for contract configuration.

    Endpoints:
    - GET  /api/v1/admin/config/contracts/           List contracts
    - GET  /api/v1/admin/config/contracts/{id}/      Get specific contract
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    pagination_class = MobileSyncCursorPagination
    queryset = Contract.objects.all()

    def list(self, request):
        """
        List all contracts.

        Query Params:
            active (bool): Filter by active status
            client_id (int): Filter by client

        Returns:
            {
                "count": 10,
                "results": [...],
                "message": "Success"
            }
        """
        try:
            queryset = self.get_queryset()

            # Apply filters
            if request.query_params.get('active'):
                queryset = queryset.filter(isactive=True)

            if request.query_params.get('client_id'):
                queryset = queryset.filter(client_id=request.query_params['client_id'])

            contracts = queryset.select_related('client').values(
                'id',
                'contract_name',
                'contract_code',
                'client_id',
                'client__client_name',
                'start_date',
                'end_date',
                'isactive',
                'created_at',
            )

            return Response({
                'count': len(contracts),
                'results': list(contracts),
                'message': 'Success'
            })

        except DatabaseError as e:
            logger.error(f"Database error listing contracts: {e}", exc_info=True)
            return Response(
                {'error': 'Database error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, pk=None):
        """Get specific contract by ID"""
        try:
            contract = self.get_object()
            data = {
                'id': contract.id,
                'contract_name': contract.contract_name,
                'contract_code': contract.contract_code,
                'client_id': contract.client_id,
                'client_name': contract.client.client_name if contract.client else None,
                'start_date': contract.start_date,
                'end_date': contract.end_date,
                'isactive': contract.isactive,
                'created_at': contract.created_at,
            }

            return Response({
                'result': data,
                'message': 'Success'
            })

        except ObjectDoesNotExist:
            return Response(
                {'error': 'Contract not found'},
                status=status.HTTP_404_NOT_FOUND
            )
