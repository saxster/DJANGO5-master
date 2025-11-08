"""
Template Management Views

Handles configuration templates for faster onboarding.

Migrated from: apps/onboarding_api/views.py (lines 1354-2189)
Date: 2025-09-30
"""
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils.security import require_tenant_scope, with_idempotency
import logging
from apps.core.exceptions.patterns import TEMPLATE_EXCEPTIONS


logger = logging.getLogger(__name__)


class ConfigurationTemplatesView(APIView):
    """Manage and apply configuration templates"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all available configuration templates"""
        from ..services.config_templates import get_template_service

        template_service = get_template_service()
        templates = template_service.get_all_templates()

        template_data = []
        for template in templates:
            template_dict = template.to_dict()
            template_dict['preview'] = {
                'business_units_count': len(template.config.get('business_units', [])),
                'shifts_count': len(template.config.get('shifts', [])),
                'type_assists_count': len(template.config.get('type_assists', [])),
                'complexity': template.metadata.get('complexity', 'medium'),
                'setup_time_minutes': template.metadata.get('setup_time_minutes', 30)
            }
            del template_dict['config']
            template_data.append(template_dict)

        return Response({
            'templates': template_data,
            'total_count': len(template_data)
        })

    def post(self, request):
        """Get template recommendations based on context"""
        if not hasattr(request.user, 'client') or not request.user.client:
            return Response(
                {"error": "User must be associated with a client"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from ..services.config_templates import get_template_service
        template_service = get_template_service()

        context = {
            'site_type': request.data.get('site_type', ''),
            'operating_hours': request.data.get('operating_hours', ''),
            'staff_count': request.data.get('staff_count', 0),
            'security_level': request.data.get('security_level', 'medium')
        }

        recommendations = template_service.recommend_templates(context)

        return Response({
            'context': context,
            'recommendations': recommendations
        })


class ConfigurationTemplateDetailView(APIView):
    """Get details and apply specific template"""
    permission_classes = [IsAuthenticated]

    def get(self, request, template_id):
        """Get detailed template information"""
        from ..services.config_templates import get_template_service

        template_service = get_template_service()
        template = template_service.get_template(template_id)

        if not template:
            return Response(
                {'error': f'Template {template_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(template.to_dict())

    def post(self, request, template_id):
        """Apply configuration template"""
        if not hasattr(request.user, 'client') or not request.user.client:
            return Response(
                {"error": "User must be associated with a client"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from ..services.config_templates import get_template_service
        template_service = get_template_service()

        try:
            customizations = request.data.get('customizations', {})
            dry_run = request.data.get('dry_run', True)

            applied_config = template_service.apply_template(template_id, customizations)

            if not dry_run:
                logger.info(
                    f"User {request.user.id} applied template {template_id}"
                )

                return Response({
                    'template_applied': True,
                    'template_id': template_id,
                    'applied_config': applied_config,
                    'message': 'Template configuration ready for application'
                })
            else:
                return Response({
                    'template_applied': False,
                    'preview': applied_config,
                    'dry_run': True,
                    'message': 'Template preview generated'
                })

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except TEMPLATE_EXCEPTIONS as e:
            logger.error(f"Template application error: {str(e)}")
            return Response(
                {'error': 'Template application failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class QuickStartRecommendationsView(APIView):
    """Get intelligent quick-start recommendations"""
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('read_templates')
    def post(self, request):
        """Generate quick-start recommendations"""
        if not hasattr(request.user, 'client') or not request.user.client:
            return Response(
                {"error": "User must be associated with a client"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            site_info = {
                'industry': request.data.get('industry', ''),
                'size': request.data.get('size', 'medium'),
                'operating_hours': request.data.get('operating_hours', 'business_hours'),
                'security_level': request.data.get('security_level', 'medium'),
                'staff_count': request.data.get('staff_count', 25),
                'special_requirements': request.data.get('special_requirements', [])
            }

            from ..services.config_templates import get_template_service
            template_service = get_template_service()

            recommendations = template_service.get_quick_start_recommendations(site_info)

            recommendations['client_info'] = {
                'id': request.user.client.id,
                'name': request.user.client.buname,
                'code': request.user.client.bucode
            }

            return Response(recommendations)

        except TEMPLATE_EXCEPTIONS as e:
            logger.error(f"Quick-start recommendations error: {str(e)}")
            return Response(
                {"error": "Failed to generate recommendations"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OneClickDeploymentView(APIView):
    """Deploy template configuration with one click"""
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('create_configuration')
    @with_idempotency('deploy_template')
    def post(self, request, template_id):
        """Deploy template to client database"""
        if not hasattr(request.user, 'client') or not request.user.client:
            return Response(
                {"error": "User must be associated with a client"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from ..services.config_templates import get_template_service
            template_service = get_template_service()

            customizations = request.data.get('customizations', {})
            dry_run = request.data.get('dry_run', True)

            template = template_service.get_template(template_id)
            if not template:
                return Response(
                    {"error": f"Template {template_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            deployment_result = template_service.apply_template_to_tenant(
                template_id=template_id,
                client=request.user.client,
                user=request.user,
                customizations=customizations,
                dry_run=dry_run
            )

            response_data = {
                'deployment_result': deployment_result,
                'template_info': {
                    'template_id': template_id,
                    'template_name': template.name,
                    'estimated_setup_time': template.metadata.get('setup_time_minutes', 30)
                }
            }

            if dry_run:
                response_data['message'] = 'Template deployment preview completed'
            else:
                response_data['message'] = 'Template deployed successfully'

            return Response(response_data)

        except TEMPLATE_EXCEPTIONS as e:
            logger.error(f"Template deployment error: {str(e)}")
            return Response(
                {"error": "Template deployment failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TemplateAnalyticsView(APIView):
    """Get template analytics and usage statistics"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retrieve template analytics (staff only)"""
        if not request.user.is_staff:
            return Response(
                {"error": "Staff access required for analytics"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            from ..services.config_templates import get_template_service
            template_service = get_template_service()

            analytics = template_service.get_template_analytics()
            usage_stats = template_service.get_template_usage_stats()

            return Response({
                'template_analytics': analytics,
                'usage_statistics': usage_stats,
                'system_info': {
                    'total_templates_available': len(template_service.get_all_templates()),
                    'last_updated': timezone.now().isoformat()
                }
            })

        except TEMPLATE_EXCEPTIONS as e:
            logger.error(f"Template analytics error: {str(e)}")
            return Response(
                {"error": "Failed to retrieve analytics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
