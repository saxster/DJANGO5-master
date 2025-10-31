"""
API Views for the Mentor system with streaming support.
"""

import json
import time
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, status
from django.http import StreamingHttpResponse, JsonResponse
from .permissions import (
    CanUsePlanGenerator, CanUsePatchGenerator, CanApplyPatches,
    CanUseTestRunner, CanViewSensitiveCode, CanAdminMentor
)
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from apps.core.utils_new.sse_cors_utils import get_secure_sse_cors_headers
from .serializers import PlanRequestSerializer


class BaseMentorViewSet(viewsets.ViewSet):
    """Base viewset for all Mentor API endpoints."""

    permission_classes = [IsAuthenticated]  # Will be overridden in subclasses

    def get_streaming_response(self, generator_func, *args, **kwargs):
        """Create a streaming response for long-running operations."""
        def event_stream():
            try:
                for event in generator_func(*args, **kwargs):
                    yield f"data: {json.dumps(event)}\n\n"
            except (TypeError, ValueError, json.JSONDecodeError) as e:
                error_event = {
                    'type': 'error',
                    'message': str(e),
                    'timestamp': time.time()
                }
                yield f"data: {json.dumps(error_event)}\n\n"
            finally:
                # Send completion event
                completion_event = {
                    'type': 'complete',
                    'timestamp': time.time()
                }
                yield f"data: {json.dumps(completion_event)}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['Connection'] = 'keep-alive'

        # SECURITY FIX: Use secure CORS validation instead of wildcard (CVSS 8.1 vulnerability)
        # Wildcard CORS with credentials allows any origin to access SSE stream, enabling CSRF attacks
        # Note: get_streaming_response is called from viewset methods, so we need to access request
        request = kwargs.get('request') or args[0] if args else None
        if request is None:
            # Fallback to self.request if available (in ViewSet context)
            request = getattr(self, 'request', None)

        if request:
            cors_headers = get_secure_sse_cors_headers(request)
            if cors_headers:
                for key, value in cors_headers.items():
                    response[key] = value
            else:
                # Origin blocked - return error response instead
                return JsonResponse({'error': 'Unauthorized origin'}, status=403)
        else:
            # No request context available - log warning and deny
            import logging
            logger = logging.getLogger('security.cors')
            logger.error("No request context available for SSE CORS validation")
            return JsonResponse({'error': 'Internal server error'}, status=500)

        return response


class PlanViewSet(BaseMentorViewSet):
    """ViewSet for plan generation operations."""

    permission_classes = [CanUsePlanGenerator]

    def create(self, request):
        """Generate a structured change plan from natural language request."""
        serializer = PlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            # Import here to avoid circular imports
            from apps.mentor.management.commands.mentor_plan import PlanGenerator

            generator = PlanGenerator()
            plan = generator.generate_plan(
                request=data['request'],
                scope=data.get('scope')
            )

            response_data = {
                'plan_id': plan.plan_id,
                'request': plan.request,
                'steps': [step.to_dict() for step in plan.steps],
                'impacted_files': list(plan.impacted_files),
                'required_tests': plan.required_tests,
                'migration_needed': plan.migration_needed,
                'overall_risk': plan.overall_risk,
                'estimated_total_time': plan.estimated_total_time,
                'prerequisites': plan.prerequisites,
                'rollback_plan': plan.rollback_plan,
                'created_at': time.time()
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except (TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def stream(self, request):
        """Stream plan generation progress."""
        serializer = PlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        def plan_generator():
            # Yield progress events during plan generation
            yield {'type': 'progress', 'stage': 'analyzing', 'progress': 0.1}

            time.sleep(0.5)  # Simulate work
            yield {'type': 'progress', 'stage': 'planning', 'progress': 0.5}

            # Generate actual plan
            from apps.mentor.management.commands.mentor_plan import PlanGenerator
            generator = PlanGenerator()
            plan = generator.generate_plan(
                request=serializer.validated_data['request'],
                scope=serializer.validated_data.get('scope')
            )

            yield {'type': 'progress', 'stage': 'finalizing', 'progress': 0.9}

            # Yield final result
            yield {
                'type': 'result',
                'plan': {
                    'plan_id': plan.plan_id,
                    'request': plan.request,
                    'steps': [step.to_dict() for step in plan.steps],
                    'overall_risk': plan.overall_risk,
                    'estimated_total_time': plan.estimated_total_time
                }
            }

        return self.get_streaming_response(plan_generator)


class PatchViewSet(BaseMentorViewSet):
    """ViewSet for patch generation and application."""

    permission_classes = [CanUsePatchGenerator]

    def create(self, request):
        """Generate and optionally apply code patches."""
        serializer = PatchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            from apps.mentor.management.commands.mentor_patch import PatchOrchestrator

            orchestrator = PatchOrchestrator()

            # Create patch request
            from apps.mentor.management.commands.mentor_patch import PatchRequest
            patch_request = PatchRequest(
                request=data.get('request', 'General code improvements'),
                scope=data.get('scope'),
                patch_type=data['type'],
                target_files=data.get('files'),
                dry_run=data['dry_run'],
                create_branch=bool(data.get('branch')),
                auto_test=data.get('auto_test', True)
            )

            # Generate patches
            patches = orchestrator.generate_patches(patch_request)

            if not patches:
                return Response(
                    {'message': 'No patches generated', 'patches': []},
                    status=status.HTTP_200_OK
                )

            # Apply patches if not dry run
            results = {'applied': [], 'failed': [], 'patches': []}
            if not data['dry_run']:
                apply_results = orchestrator.apply_patches(
                    patches,
                    dry_run=False,
                    create_branch=bool(data.get('branch'))
                )
                results.update(apply_results)

            # Add patch details to response
            results['patches'] = [{
                'type': patch.type.value,
                'priority': patch.priority.value,
                'description': patch.description,
                'file_path': patch.file_path,
                'original_code': patch.original_code[:500],  # Truncate for API
                'modified_code': patch.modified_code[:500],
                'line_start': patch.line_start,
                'line_end': patch.line_end,
                'confidence': patch.confidence
            } for patch in patches]

            return Response(results, status=status.HTTP_201_CREATED)

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def preview(self, request):
        """Preview patches without applying them."""
        data = request.data.copy()
        data['dry_run'] = True

        # Create new request with dry_run forced
        new_request = request.__class__(data, **{
            k: v for k, v in request.__dict__.items()
            if k not in ['_request', '_data', '_files']
        })
        new_request._full_data = data

        return self.create(new_request)


class TestViewSet(BaseMentorViewSet):
    """ViewSet for test execution and management."""

    permission_classes = [CanUseTestRunner]

    def create(self, request):
        """Execute tests based on criteria."""
        serializer = TestRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            from apps.mentor.management.commands.mentor_test import TestSelector, TestRunner

            selector = TestSelector()
            runner = TestRunner()

            # Select tests based on criteria
            selected_tests = set()

            if data.get('targets'):
                # Check if targets are files or symbols
                file_targets = [t for t in data['targets'] if '/' in t]
                symbol_targets = [t for t in data['targets'] if t not in file_targets]

                if file_targets:
                    selected_tests.update(
                        selector.select_tests_for_changes(file_targets)
                    )

                if symbol_targets:
                    selected_tests.update(
                        selector.select_tests_for_symbols(symbol_targets)
                    )

            if data.get('changed'):
                import subprocess
                try:
                    result = subprocess.run(
                        ['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'],
                        capture_output=True, text=True, check=True
                    )
                    changed_files = [line.strip() for line in result.stdout.split('\n')
                                   if line.strip().endswith('.py')]
                    selected_tests.update(
                        selector.select_tests_for_changes(changed_files)
                    )
                except subprocess.CalledProcessError:
                    pass

            if data.get('flaky'):
                selected_tests.update(selector.select_flaky_tests())

            if data.get('slow'):
                selected_tests.update(selector.select_slow_tests())

            if not selected_tests:
                return Response(
                    {'message': 'No tests selected'},
                    status=status.HTTP_200_OK
                )

            # Run selected tests
            session = runner.run_tests(
                selected_tests,
                collect_coverage=data.get('coverage', False),
                parallel=data.get('parallel', True),
                timeout=data.get('timeout', 600)
            )

            response_data = {
                'session_id': session.session_id,
                'total_tests': session.total_tests,
                'passed': session.passed,
                'failed': session.failed,
                'skipped': session.skipped,
                'errors': session.errors,
                'total_duration': session.total_duration,
                'coverage_percentage': session.coverage_percentage,
                'results': [{
                    'node_id': result.node_id,
                    'status': result.status,
                    'duration': result.duration,
                    'output': result.output[:500],  # Truncate for API
                    'error_message': result.error_message
                } for result in session.results[:50]]  # Limit results
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GuardViewSet(BaseMentorViewSet):
    """ViewSet for safety validation and guards."""

    permission_classes = [CanViewSensitiveCode]

    def create(self, request):
        """Run safety validation checks."""
        serializer = GuardRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            from apps.mentor.management.commands.mentor_guard import PreCommitGuard

            guard = PreCommitGuard()

            if data.get('validate') or data.get('pre_commit'):
                report = guard.run_all_checks(data.get('files'))
            elif data.get('check'):
                report = guard._parent.run_specific_check(
                    guard, data['check'], data.get('files')
                )
            else:
                return Response(
                    {'error': 'No action specified'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            response_data = {
                'overall_status': report.overall_status,
                'total_checks': report.total_checks,
                'passed_checks': report.passed_checks,
                'failed_checks': report.failed_checks,
                'blocking_issues': len(report.blocking_issues),
                'results': [{
                    'check_name': result.check_name,
                    'level': result.level.value,
                    'message': result.message,
                    'file_path': result.file_path,
                    'line_number': result.line_number,
                    'recommendation': result.recommendation,
                    'auto_fixable': result.auto_fixable
                } for result in report.results]
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExplainViewSet(BaseMentorViewSet):
    """ViewSet for code explanations."""

    permission_classes = [IsAuthenticated]  # Basic permission for explanations

    def create(self, request):
        """Explain code symbols, files, URLs, models, etc."""
        serializer = ExplainRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            from apps.mentor.management.commands.mentor_explain import CodeExplainer

            explainer = CodeExplainer()
            explainer.context_depth = data.get('depth', 2)

            target = data['target']
            target_type = data.get('type')

            # Auto-detect type if not specified
            if not target_type:
                if ':' in target:
                    target_type = 'symbol'
                elif target.endswith('.py'):
                    target_type = 'file'
                elif '/' in target or target.startswith('^'):
                    target_type = 'url'
                elif target[0].isupper():
                    target_type = 'model'
                else:
                    target_type = 'query'

            # Generate explanation
            explanation = None
            if target_type == 'symbol':
                explanation = explainer.explain_symbol(target, data.get('include_usage', True))
            elif target_type == 'file':
                explanation = explainer.explain_file(target)
            elif target_type == 'url':
                explanation = explainer.explain_url(target)
            elif target_type == 'model':
                explanation = explainer.explain_model(target)
            elif target_type == 'query':
                explanation = explainer.explain_query(target)
            else:
                return Response(
                    {'error': f"Unsupported explanation type: {target_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if 'error' in explanation:
                return Response(explanation, status=status.HTTP_404_NOT_FOUND)

            response_data = {
                'target': target,
                'type': target_type,
                'explanation': explanation,
                'formatted_output': None
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MentorStatusView(APIView):
    """API view for mentor system status."""

    permission_classes = [CanViewSensitiveCode]

    @method_decorator(cache_page(60))  # Cache for 1 minute
    def get(self, request):
        """Get mentor system status."""
        try:
            from apps.mentor.monitoring.dashboard import MentorMetrics

            metrics = MentorMetrics()
            dashboard_data = metrics.generate_dashboard_data()

            response_data = {
                'status': 'healthy' if dashboard_data.index_health['is_healthy'] else 'degraded',
                'index_health': dashboard_data.index_health,
                'usage_statistics': dashboard_data.usage_statistics,
                'quality_metrics': dashboard_data.quality_metrics,
                'last_update': dashboard_data.index_health.get('last_update')
            }

            return Response(response_data)

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MentorHealthView(APIView):
    """API view for mentor system health check."""

    permission_classes = [CanAdminMentor]

    def get(self, request):
        """Perform comprehensive health check."""
        checks = []
        overall_health = 'healthy'

        try:
            # Database connectivity check
            from apps.mentor.models import IndexMetadata
            IndexMetadata.objects.count()
            checks.append({
                'component': 'Database',
                'status': 'healthy',
                'message': 'Connected successfully'
            })
        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            checks.append({
                'component': 'Database',
                'status': 'unhealthy',
                'message': f'Connection failed: {str(e)}'
            })
            overall_health = 'unhealthy'

        # Index health check
        try:
            from apps.mentor.monitoring.dashboard import MentorMetrics
            metrics = MentorMetrics()
            health = metrics.get_index_health()

            if health['is_healthy']:
                checks.append({
                    'component': 'Index',
                    'status': 'healthy',
                    'message': f"{health['indexed_files']} files indexed"
                })
            else:
                checks.append({
                    'component': 'Index',
                    'status': 'degraded',
                    'message': f"{health['commits_behind']} commits behind"
                })
                if overall_health == 'healthy':
                    overall_health = 'degraded'
        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            checks.append({
                'component': 'Index',
                'status': 'unhealthy',
                'message': f'Health check failed: {str(e)}'
            })
            overall_health = 'unhealthy'

        # Dependencies check
        try:
            checks.append({
                'component': 'LibCST',
                'status': 'healthy',
                'message': 'Available for advanced codemods'
            })
        except ImportError:
            checks.append({
                'component': 'LibCST',
                'status': 'degraded',
                'message': 'Not available - reduced functionality'
            })
            if overall_health == 'healthy':
                overall_health = 'degraded'

        issues_found = len([c for c in checks if c['status'] != 'healthy'])

        recommendations = []
        if issues_found > 0:
            recommendations.append("Address unhealthy components")
            if any(c['component'] == 'Index' and c['status'] != 'healthy' for c in checks):
                recommendations.append("Run 'python manage.py mentor index --full' to refresh index")

        response_data = {
            'overall_health': overall_health,
            'component_checks': checks,
            'issues_found': issues_found,
            'recommendations': recommendations
        }

        return Response(response_data)
