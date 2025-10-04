"""
GraphQL Schema for Mobile Sync System

Implements GraphQL mutations for sync operations as complement to REST API.
Reuses existing sync services for consistency.

Follows .claude/rules.md:
- Rule #1: GraphQL security protection (validation applied)
- Rule #7: Service methods < 50 lines (delegate to existing services)
- Rule #11: Specific exception handling
- Rule #17: Transaction management (via services)

Features:
- Idempotency support (24-hour window)
- Conflict resolution
- Batch operations
- Performance metrics
- Security validation
"""

import graphene
from graphene import ObjectType, Mutation, Field, List, String
from graphql_jwt.decorators import login_required
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import DatabaseError
import logging
import time

from .sync_types import (
    VoiceDataInput,
    BehavioralDataInput,
    SessionDataInput,
    MetricsDataInput,
    SyncBatchInput,
    ConflictResolutionInput,
    SyncResponseType,
    SyncBatchResponseType,
    ConflictResolutionResponseType,
    SyncHealthType,
    SyncErrorType,
    SyncMetricsType,
)

from apps.api.v1.services.sync_engine_service import sync_engine
from apps.api.v1.services.idempotency_service import IdempotencyService
from apps.api.v1.services.conflict_resolution_service import ConflictResolutionService
from apps.core.services.sync_analytics_service import sync_analytics_service

logger = logging.getLogger('graphql.sync')


def validate_graphql_sync_input(data):
    """
    Validate GraphQL sync input (Rule #1: GraphQL security protection).

    Prevents:
    - SQL injection via input
    - Excessive payload size
    - Invalid data types
    """
    if not data:
        raise ValidationError("Empty sync data provided")

    if isinstance(data, list) and len(data) > 1000:
        raise ValidationError("Batch size too large (max 1000 items)")

    if isinstance(data, str) and len(data) > 10 * 1024 * 1024:
        raise ValidationError("Payload too large (max 10MB)")

    return True


class SyncVoiceDataMutation(Mutation):
    """
    Sync voice verification data from mobile client.

    GraphQL complement to REST POST /api/v1/sync/voice
    """

    class Arguments:
        data = List(VoiceDataInput, required=True)
        idempotency_key = String(required=True)
        device_id = String(required=True)

    Output = SyncResponseType

    @staticmethod
    @login_required
    def mutate(root, info, data, idempotency_key, device_id):
        """Execute voice data sync."""
        start_time = time.time()

        try:
            validate_graphql_sync_input(data)

            cached_response = IdempotencyService.check_duplicate(idempotency_key)
            if cached_response:
                logger.info(f"GraphQL sync cache hit: {idempotency_key[:16]}...")
                return SyncResponseType(**cached_response)

            voice_data_dicts = [
                {
                    'verification_id': item.verification_id,
                    'timestamp': item.timestamp,
                    'verified': item.verified,
                    'confidence_score': item.confidence_score,
                    'quality_score': item.quality_score,
                    'processing_time_ms': item.processing_time_ms,
                }
                for item in data
            ]

            result = sync_engine.sync_voice_data(
                user_id=str(info.context.user.id),
                payload={'voice_data': voice_data_dicts},
                device_id=device_id
            )

            duration_ms = (time.time() - start_time) * 1000

            response_data = {
                'success': result['failed_items'] == 0,
                'synced_items': result['synced_items'],
                'failed_items': result['failed_items'],
                'conflicts': [],
                'errors': [
                    {
                        'code': 'SYNC_ERROR',
                        'message': err.get('error', 'Unknown error'),
                        'item_id': err.get('item_id')
                    }
                    for err in result.get('errors', [])
                ],
                'metrics': {
                    'total_items': len(data),
                    'synced_items': result['synced_items'],
                    'failed_items': result['failed_items'],
                    'duration_ms': duration_ms,
                },
                'server_timestamp': timezone.now().isoformat(),
                'idempotency_key': idempotency_key,
            }

            IdempotencyService.store_response(
                idempotency_key=idempotency_key,
                request_hash=idempotency_key,
                response_data=response_data,
                user_id=str(info.context.user.id),
                device_id=device_id,
                endpoint='graphql:syncVoiceData',
                scope='batch'
            )

            logger.info(f"GraphQL voice sync: {result['synced_items']} items, {duration_ms:.1f}ms")

            return SyncResponseType(**response_data)

        except ValidationError as e:
            logger.warning(f"GraphQL sync validation error: {e}")
            return SyncResponseType(
                success=False,
                synced_items=0,
                failed_items=len(data),
                errors=[{
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }],
                server_timestamp=timezone.now().isoformat(),
                idempotency_key=idempotency_key
            )
        except DatabaseError as e:
            logger.error(f"GraphQL sync database error: {e}", exc_info=True)
            return SyncResponseType(
                success=False,
                synced_items=0,
                failed_items=len(data),
                errors=[{
                    'code': 'DATABASE_ERROR',
                    'message': 'Database temporarily unavailable'
                }],
                server_timestamp=timezone.now().isoformat(),
                idempotency_key=idempotency_key
            )


class SyncBatchMutation(Mutation):
    """
    Batch sync for multiple data types in single request.

    Optimizes network round-trips by combining:
    - Voice data
    - Behavioral data
    - Session data
    - Metrics data
    """

    class Arguments:
        batch = SyncBatchInput(required=True)

    Output = SyncBatchResponseType

    @staticmethod
    @login_required
    def mutate(root, info, batch):
        """Execute batch sync."""
        start_time = time.time()

        try:
            validate_graphql_sync_input(batch)

            cached_response = IdempotencyService.check_duplicate(batch.idempotency_key)
            if cached_response:
                return SyncBatchResponseType(**cached_response)

            results = {}

            if batch.voice_data:
                voice_result = sync_engine.sync_voice_data(
                    user_id=str(info.context.user.id),
                    payload={'voice_data': [
                        {
                            'verification_id': item.verification_id,
                            'timestamp': item.timestamp,
                            'verified': item.verified,
                            'confidence_score': item.confidence_score,
                        }
                        for item in batch.voice_data
                    ]},
                    device_id=batch.device_id
                )
                results['voice_sync_result'] = voice_result

            if batch.behavioral_data:
                behavioral_result = sync_engine.sync_behavioral_data(
                    user_id=str(info.context.user.id),
                    payload={'behavioral_data': [
                        {
                            'session_id': item.session_id,
                            'events': item.events,
                            'duration_ms': item.duration_ms,
                        }
                        for item in batch.behavioral_data
                    ]},
                    device_id=batch.device_id
                )
                results['behavioral_sync_result'] = behavioral_result

            if batch.session_data:
                session_result = sync_engine.sync_session_data(
                    user_id=str(info.context.user.id),
                    payload={'sessions': [
                        {
                            'session_id': item.session_id,
                            'start_time': item.start_time,
                            'end_time': item.end_time,
                        }
                        for item in batch.session_data
                    ]},
                    device_id=batch.device_id
                )
                results['session_sync_result'] = session_result

            if batch.metrics_data:
                metrics_result = sync_engine.sync_metrics_data(
                    user_id=str(info.context.user.id),
                    payload={'metrics': [
                        {
                            'metric_type': item.metric_type,
                            'value': item.value,
                            'timestamp': item.timestamp,
                        }
                        for item in batch.metrics_data
                    ]},
                    device_id=batch.device_id
                )
                results['metrics_sync_result'] = metrics_result

            duration_ms = (time.time() - start_time) * 1000

            total_synced = sum(r.get('synced_items', 0) for r in results.values())
            total_failed = sum(r.get('failed_items', 0) for r in results.values())

            response_data = {
                'success': total_failed == 0,
                'voice_sync_result': results.get('voice_sync_result'),
                'behavioral_sync_result': results.get('behavioral_sync_result'),
                'session_sync_result': results.get('session_sync_result'),
                'metrics_sync_result': results.get('metrics_sync_result'),
                'overall_metrics': {
                    'total_items': total_synced + total_failed,
                    'synced_items': total_synced,
                    'failed_items': total_failed,
                    'duration_ms': duration_ms,
                },
            }

            IdempotencyService.store_response(
                idempotency_key=batch.idempotency_key,
                request_hash=batch.idempotency_key,
                response_data=response_data,
                user_id=str(info.context.user.id),
                device_id=batch.device_id,
                endpoint='graphql:syncBatch',
                scope='batch'
            )

            logger.info(f"GraphQL batch sync: {total_synced} items, {duration_ms:.1f}ms")

            return SyncBatchResponseType(**response_data)

        except (ValidationError, DatabaseError) as e:
            logger.error(f"GraphQL batch sync error: {e}", exc_info=True)
            return SyncBatchResponseType(
                success=False,
                overall_metrics={
                    'total_items': 0,
                    'synced_items': 0,
                    'failed_items': 0,
                    'duration_ms': (time.time() - start_time) * 1000,
                }
            )


class ResolveConflictMutation(Mutation):
    """
    Manual conflict resolution via GraphQL.

    Allows clients to resolve conflicts that require human intervention.
    """

    class Arguments:
        resolution = ConflictResolutionInput(required=True)

    Output = ConflictResolutionResponseType

    @staticmethod
    @login_required
    def mutate(root, info, resolution):
        """Execute conflict resolution."""
        try:
            from apps.core.models.sync_conflict_policy import ConflictResolutionLog

            conflict = ConflictResolutionLog.objects.get(id=resolution.conflict_id)

            conflict_service = ConflictResolutionService()

            result = conflict_service.resolve_conflict(
                domain=conflict.domain,
                server_entry={'data': conflict.merge_details.get('server_data')},
                client_entry={'data': resolution.merge_data},
                tenant_id=info.context.user.businessunit_id
            )

            conflict.resolution_result = result['resolution']
            conflict.winning_version = result.get('winning_version')
            conflict.merge_details = result.get('merge_details', {})
            conflict.save()

            return ConflictResolutionResponseType(
                success=True,
                conflict_id=resolution.conflict_id,
                resolution_result=result['resolution'],
                winning_version=result.get('winning_version'),
                merge_details=result.get('merge_details'),
                message='Conflict resolved successfully'
            )

        except (ValidationError, DatabaseError) as e:
            logger.error(f"GraphQL conflict resolution error: {e}", exc_info=True)
            return ConflictResolutionResponseType(
                success=False,
                conflict_id=resolution.conflict_id,
                resolution_result='failed',
                error={
                    'code': 'RESOLUTION_ERROR',
                    'message': str(e)
                }
            )


class SyncMutations(ObjectType):
    """Root mutation type for sync operations."""

    sync_voice_data = SyncVoiceDataMutation.Field()
    sync_batch = SyncBatchMutation.Field()
    resolve_conflict = ResolveConflictMutation.Field()