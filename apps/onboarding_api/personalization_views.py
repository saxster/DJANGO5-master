"""
API views for personalization and experiment management

Provides REST API endpoints for:
- User preference profile management
- Experiment CRUD operations (staff-only)
- Experiment arm assignments
- Learning signal collection
- Real-time personalization metrics
"""

import logging
from django.utils import timezone
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser

    ExperimentAssignment,
    RecommendationInteraction,
    ConversationSession,
    LLMRecommendation,
    Bt
)
from apps.peoples.models import People
from apps.onboarding_api.services.learning import get_learning_service
from apps.onboarding_api.services.experiments import get_experiment_manager
from apps.onboarding_api.services.personalization import get_assignment_service
from apps.onboarding_api.serializers import *  # Assuming serializers exist

logger = logging.getLogger(__name__)


class InteractionThrottle(UserRateThrottle):
    """Custom throttle for interaction collection endpoints"""
    scope = 'interactions'
    rate = getattr(settings, 'INTERACTION_THROTTLE_RATE', '100/hour')


class ExperimentThrottle(UserRateThrottle):
    """Custom throttle for experiment management endpoints"""
    scope = 'experiments'
    rate = getattr(settings, 'EXPERIMENT_THROTTLE_RATE', '50/hour')


class PreferencesAPIView(APIView):
    """
    API for user preference management (staff-only)
    GET /api/v1/onboarding/preferences/{user_or_client}/
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, user_or_client):
        """Get preference summary and recent metrics"""
        try:
            # Parse user_or_client identifier
            user, client = self._resolve_user_client(user_or_client, request)

            if not user and not client:
                return Response(
                    {'error': 'Invalid user_or_client identifier'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get preference profile
            profile = None
            if user and client:
                profile = PreferenceProfile.objects.filter(user=user, client=client).first()
            elif client:
                # Client-wide preferences (user=null)
                profile = PreferenceProfile.objects.filter(user__isnull=True, client=client).first()

            # Get learning service for metrics
            learning_service = get_learning_service()

            if user and client:
                summary = learning_service.get_user_learning_summary(user, client, days=30)
            else:
                summary = {'status': 'no_user_specified', 'message': 'Client-wide preferences not implemented'}

            response_data = {
                'user_id': user.id if user else None,
                'client_id': client.id if client else None,
                'has_preference_profile': profile is not None,
                'preference_weights': profile.weights if profile else {},
                'learning_stats': profile.stats if profile else {},
                'last_updated': profile.last_updated.isoformat() if profile else None,
                'learning_summary': summary,
                'acceptance_rate': profile.calculate_acceptance_rate() if profile else 0.0
            }

            return Response(response_data)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error retrieving preferences for {user_or_client}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _resolve_user_client(self, identifier: str, request) -> tuple:
        """Resolve user_or_client identifier to user and client objects"""
        try:
            # Try parsing as "user_id:client_id"
            if ':' in identifier:
                user_id, client_id = identifier.split(':', 1)
                try:
                    user = People.objects.get(id=int(user_id))
                    client = Bt.objects.get(id=int(client_id))
                    return user, client
                except (ValueError, People.DoesNotExist, Bt.DoesNotExist):
                    pass

            # Try parsing as user ID only (use current user's client)
            try:
                user_id = int(identifier)
                user = People.objects.get(id=user_id)
                # Get user's client from current context or first available
                client = getattr(request.user, 'current_client', None)
                if not client:
                    # Fallback: get first client the user has preferences for
                    profile = PreferenceProfile.objects.filter(user=user).first()
                    client = profile.client if profile else None
                return user, client
            except (ValueError, People.DoesNotExist):
                pass

            # Try parsing as client code
            try:
                client = Bt.objects.get(bucode=identifier)
                return None, client
            except Bt.DoesNotExist:
                pass

            return None, None

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error resolving identifier {identifier}: {str(e)}")
            return None, None


class ExperimentsAPIView(APIView):
    """
    API for experiment management (staff-only)
    GET/POST /api/v1/onboarding/experiments/
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes = [ExperimentThrottle]

    def get(self, request):
        """List experiments with filtering"""
        try:
            # Filter parameters
            status_filter = request.query_params.get('status')
            scope_filter = request.query_params.get('scope')
            owner_filter = request.query_params.get('owner')

            queryset = Experiment.objects.all().select_related('owner').order_by('-started_at', '-cdtz')

            # Apply filters
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            if scope_filter:
                queryset = queryset.filter(scope=scope_filter)
            if owner_filter:
                try:
                    owner_id = int(owner_filter)
                    queryset = queryset.filter(owner_id=owner_id)
                except ValueError:
                    pass

            # Pagination
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            page = int(request.query_params.get('page', 1))
            offset = (page - 1) * page_size

            total_count = queryset.count()
            experiments = queryset[offset:offset + page_size]

            # Serialize experiments
            experiments_data = []
            for exp in experiments:
                exp_data = {
                    'experiment_id': str(exp.experiment_id),
                    'name': exp.name,
                    'description': exp.description,
                    'status': exp.status,
                    'scope': exp.scope,
                    'owner': {
                        'id': exp.owner.id,
                        'email': exp.owner.email
                    },
                    'arms': exp.arms,
                    'primary_metric': exp.primary_metric,
                    'secondary_metrics': exp.secondary_metrics,
                    'holdback_pct': exp.holdback_pct,
                    'started_at': exp.started_at.isoformat() if exp.started_at else None,
                    'ended_at': exp.ended_at.isoformat() if exp.ended_at else None,
                    'created_at': exp.cdtz.isoformat(),
                    'arm_count': exp.get_arm_count(),
                    'is_active': exp.is_active()
                }
                experiments_data.append(exp_data)

            return Response({
                'experiments': experiments_data,
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size
                }
            })

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error listing experiments: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Create new experiment"""
        try:
            data = request.data

            # Validate required fields
            required_fields = ['name', 'description', 'arms']
            for field in required_fields:
                if field not in data:
                    return Response(
                        {'error': f'Missing required field: {field}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Validate arms
            arms = data['arms']
            if not isinstance(arms, list) or len(arms) < 2:
                return Response(
                    {'error': 'Must provide at least 2 experiment arms'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create experiment using manager
            experiment_manager = get_experiment_manager()
            experiment = experiment_manager.create_experiment(
                name=data['name'],
                description=data['description'],
                arms=arms,
                owner=request.user,
                scope=data.get('scope', 'tenant'),
                primary_metric=data.get('primary_metric', 'acceptance_rate'),
                secondary_metrics=data.get('secondary_metrics', []),
                holdback_pct=data.get('holdback_pct', 10.0),
                safety_constraints=data.get('safety_constraints', {})
            )

            return Response({
                'experiment_id': str(experiment.experiment_id),
                'name': experiment.name,
                'status': experiment.status,
                'created_at': experiment.cdtz.isoformat(),
                'message': 'Experiment created successfully'
            }, status=status.HTTP_201_CREATED)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error creating experiment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ExperimentDetailAPIView(APIView):
    """
    API for individual experiment management
    GET/PUT/DELETE /api/v1/onboarding/experiments/{experiment_id}/
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, experiment_id):
        """Get experiment details with analysis"""
        try:
            experiment = Experiment.objects.select_related('owner').get(
                experiment_id=experiment_id
            )

            # Get experiment analysis if active or completed
            analysis = {}
            if experiment.status in ['running', 'completed']:
                experiment_manager = get_experiment_manager()
                analysis = experiment_manager.analyzer.analyze_experiment(experiment)

            # Get assignment counts
            assignments = ExperimentAssignment.objects.filter(experiment=experiment)
            assignment_counts = {}
            for assignment in assignments:
                arm = assignment.arm
                assignment_counts[arm] = assignment_counts.get(arm, 0) + 1

            experiment_data = {
                'experiment_id': str(experiment.experiment_id),
                'name': experiment.name,
                'description': experiment.description,
                'status': experiment.status,
                'scope': experiment.scope,
                'owner': {
                    'id': experiment.owner.id,
                    'email': experiment.owner.email
                },
                'arms': experiment.arms,
                'primary_metric': experiment.primary_metric,
                'secondary_metrics': experiment.secondary_metrics,
                'holdback_pct': experiment.holdback_pct,
                'safety_constraints': experiment.safety_constraints,
                'started_at': experiment.started_at.isoformat() if experiment.started_at else None,
                'ended_at': experiment.ended_at.isoformat() if experiment.ended_at else None,
                'created_at': experiment.cdtz.isoformat(),
                'updated_at': experiment.mdtz.isoformat(),
                'results': experiment.results,
                'assignment_counts': assignment_counts,
                'analysis': analysis
            }

            return Response(experiment_data)

        except Experiment.DoesNotExist:
            return Response(
                {'error': 'Experiment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error retrieving experiment {experiment_id}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, experiment_id):
        """Update experiment (limited operations)"""
        try:
            experiment = Experiment.objects.get(experiment_id=experiment_id)
            data = request.data

            # Only allow certain updates based on experiment status
            if experiment.status == 'draft':
                # Can update most fields when in draft
                allowed_fields = ['name', 'description', 'arms', 'primary_metric',
                                'secondary_metrics', 'holdback_pct', 'safety_constraints']
            elif experiment.status == 'running':
                # Limited updates when running
                allowed_fields = ['description', 'safety_constraints']
            else:
                return Response(
                    {'error': f'Cannot update experiment in {experiment.status} status'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update allowed fields
            for field in allowed_fields:
                if field in data:
                    setattr(experiment, field, data[field])

            experiment.save()

            return Response({
                'experiment_id': str(experiment.experiment_id),
                'message': 'Experiment updated successfully'
            })

        except Experiment.DoesNotExist:
            return Response(
                {'error': 'Experiment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error updating experiment {experiment_id}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ExperimentActionAPIView(APIView):
    """
    API for experiment actions (start, pause, complete, analyze)
    POST /api/v1/onboarding/experiments/{experiment_id}/actions/
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, experiment_id):
        """Perform experiment actions"""
        try:
            experiment = Experiment.objects.get(experiment_id=experiment_id)
            action = request.data.get('action')

            if not action:
                return Response(
                    {'error': 'Missing required field: action'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            experiment_manager = get_experiment_manager()

            if action == 'start':
                experiment_manager.start_experiment(experiment)
                message = 'Experiment started successfully'

            elif action == 'pause':
                reason = request.data.get('reason', 'Manual pause')
                experiment_manager.pause_experiment(experiment, reason)
                message = 'Experiment paused successfully'

            elif action == 'complete':
                final_analysis = request.data.get('final_analysis', True)
                result = experiment_manager.complete_experiment(experiment, final_analysis)
                return Response({
                    'experiment_id': str(experiment.experiment_id),
                    'message': 'Experiment completed successfully',
                    'analysis': result
                })

            elif action == 'analyze':
                analysis = experiment_manager.analyzer.analyze_experiment(experiment)
                return Response({
                    'experiment_id': str(experiment.experiment_id),
                    'analysis': analysis
                })

            elif action == 'check_safety':
                violations = experiment_manager.check_safety_constraints(experiment)
                return Response({
                    'experiment_id': str(experiment.experiment_id),
                    'safety_violations': violations,
                    'safe': len(violations) == 0
                })

            elif action == 'promote':
                arm_name = request.data.get('arm_name')
                if not arm_name:
                    return Response(
                        {'error': 'Missing required field: arm_name'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                promotion_result = experiment_manager.promote_winning_arm(experiment, arm_name)
                return Response({
                    'experiment_id': str(experiment.experiment_id),
                    'message': 'Arm promoted successfully',
                    'promotion': promotion_result
                })

            else:
                return Response(
                    {'error': f'Unknown action: {action}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response({
                'experiment_id': str(experiment.experiment_id),
                'action': action,
                'message': message
            })

        except Experiment.DoesNotExist:
            return Response(
                {'error': 'Experiment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error performing action {action} on experiment {experiment_id}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ExperimentAssignmentAPIView(APIView):
    """
    API for experiment arm assignment (idempotent)
    GET /api/v1/onboarding/experiments/{experiment_id}/assign/
    """
    permission_classes = [IsAuthenticated]

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    @method_decorator(vary_on_headers('Authorization'))
    def get(self, request, experiment_id):
        """Get experiment arm assignment for current user"""
        try:
            experiment = Experiment.objects.get(
                experiment_id=experiment_id,
                status='running'
            )

            user = request.user
            client = getattr(user, 'current_client', None)

            if not client:
                # Try to get client from request or user profile
                client_id = request.query_params.get('client_id')
                if client_id:
                    try:
                        client = Bt.objects.get(id=client_id)
                    except Bt.DoesNotExist:
                        pass

            if not client:
                return Response(
                    {'error': 'No client context available'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get or create assignment
            assignment_service = get_assignment_service()
            assignment = assignment_service.get_assignment(experiment, user, client)

            return Response({
                'experiment_id': str(experiment.experiment_id),
                'experiment_name': experiment.name,
                'user_id': user.id,
                'client_id': client.id,
                'assigned_arm': assignment.arm,
                'assigned_at': assignment.assigned_at.isoformat(),
                'assignment_context': assignment.assignment_context
            })

        except Experiment.DoesNotExist:
            return Response(
                {'error': 'Active experiment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error getting assignment for experiment {experiment_id}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([InteractionThrottle])
def record_interaction(request):
    """
    Record user interaction with recommendations
    POST /api/v1/onboarding/interactions/
    """
    try:
        data = request.data

        # Validate required fields
        required_fields = ['session_id', 'event_type']
        for field in required_fields:
            if field not in data:
                return Response(
                    {'error': f'Missing required field: {field}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        session_id = data['session_id']
        recommendation_id = data.get('recommendation_id')
        event_type = data['event_type']
        metadata = data.get('metadata', {})

        # Get learning service
        learning_service = get_learning_service()

        # Record appropriate signal type
        if event_type in ['approved', 'rejected', 'modified', 'escalated']:
            # Explicit signal
            if not recommendation_id:
                return Response(
                    {'error': 'recommendation_id required for explicit signals'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            success = learning_service.collect_explicit_signal(
                session_id, recommendation_id, event_type, metadata
            )
        else:
            # Implicit signal
            success = learning_service.collect_implicit_signal(
                session_id, recommendation_id, metadata
            )

        if success:
            return Response({
                'status': 'recorded',
                'session_id': session_id,
                'event_type': event_type,
                'timestamp': timezone.now().isoformat()
            })
        else:
            return Response(
                {'error': 'Failed to record interaction'},
                status=status.HTTP_400_BAD_REQUEST
            )

    except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error recording interaction: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([InteractionThrottle])
def record_cost_signal(request):
    """
    Record cost and performance metrics for recommendations
    POST /api/v1/onboarding/cost-signals/
    """
    try:
        data = request.data

        # Validate required fields
        if 'recommendation_id' not in data:
            return Response(
                {'error': 'Missing required field: recommendation_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        recommendation_id = data['recommendation_id']
        cost_data = {
            'provider_cost_cents': data.get('provider_cost_cents'),
            'token_usage': data.get('token_usage'),
            'latency_ms': data.get('latency_ms'),
            'provider_name': data.get('provider_name')
        }

        # Get learning service
        learning_service = get_learning_service()

        success = learning_service.collect_cost_signal(recommendation_id, cost_data)

        if success:
            return Response({
                'status': 'recorded',
                'recommendation_id': recommendation_id,
                'timestamp': timezone.now().isoformat()
            })
        else:
            return Response(
                {'error': 'Failed to record cost signal'},
                status=status.HTTP_400_BAD_REQUEST
            )

    except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error recording cost signal: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def experiment_metrics(request, experiment_id):
    """
    Get real-time experiment metrics
    GET /api/v1/onboarding/experiments/{experiment_id}/metrics/
    """
    try:
        experiment = Experiment.objects.get(experiment_id=experiment_id)

        # Get cached metrics first
        cache_key = f"experiment_metrics_{experiment_id}"
        cached_metrics = cache.get(cache_key)

        if cached_metrics:
            return Response(cached_metrics)

        # Calculate metrics
        experiment_manager = get_experiment_manager()

        # Safety check
        violations = experiment_manager.check_safety_constraints(experiment)

        # Performance metrics
        assignments = ExperimentAssignment.objects.filter(experiment=experiment)
        assignment_counts = {}
        for assignment in assignments:
            arm = assignment.arm
            assignment_counts[arm] = assignment_counts.get(arm, 0) + 1

        metrics = {
            'experiment_id': str(experiment.experiment_id),
            'status': experiment.status,
            'total_assignments': assignments.count(),
            'assignment_distribution': assignment_counts,
            'safety_violations': violations,
            'is_safe': len(violations) == 0,
            'uptime_hours': None,
            'last_updated': timezone.now().isoformat()
        }

        # Calculate uptime
        if experiment.started_at:
            uptime = timezone.now() - experiment.started_at
            metrics['uptime_hours'] = round(uptime.total_seconds() / 3600, 2)

        # Cache metrics for 5 minutes
        cache.set(cache_key, metrics, 300)

        return Response(metrics)

    except Experiment.DoesNotExist:
        return Response(
            {'error': 'Experiment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error getting experiment metrics: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )