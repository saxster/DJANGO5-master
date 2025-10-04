"""
Monitoring API Views

REST API endpoints for monitoring system access.
Provides comprehensive access to monitoring data and operations.
"""

import logging
from datetime import timedelta
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.viewsets import ReadOnlyModelViewSet, ModelViewSet
from django.utils import timezone
from django.db.models import Q, Count, Avg

from apps.monitoring.models import (
    Alert, OperationalTicket, MonitoringMetric, DeviceHealthSnapshot,
    AlertRule, TicketCategory
)
from apps.monitoring.services.monitoring_service import monitoring_service
from apps.monitoring.api.serializers import (
    AlertSerializer, TicketSerializer, MonitoringMetricSerializer,
    DeviceHealthSnapshotSerializer, AlertRuleSerializer
)

logger = logging.getLogger(__name__)


class MonitoringAPIView(APIView):
    """
    Main monitoring API endpoint.

    Provides access to comprehensive monitoring functionality.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get monitoring overview"""
        try:
            # Get query parameters
            user_id = request.query_params.get('user_id')
            device_id = request.query_params.get('device_id')
            site_id = request.query_params.get('site_id')

            if user_id and device_id:
                # Get specific device monitoring
                monitoring_result = monitoring_service.monitor_device(int(user_id), device_id)
                return Response(monitoring_result)

            # Get system overview
            system_health = monitoring_service.get_system_health()

            # Get active alerts with filtering
            alerts = monitoring_service.alert_service.get_active_alerts(
                user_id=int(user_id) if user_id else None,
                site_id=int(site_id) if site_id else None
            )

            return Response({
                'system_health': system_health,
                'active_alerts': alerts,
                'timestamp': timezone.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Error in monitoring API: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Force monitoring update"""
        try:
            user_id = request.data.get('user_id')
            device_id = request.data.get('device_id')

            if not user_id or not device_id:
                return Response(
                    {'error': 'user_id and device_id are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Force monitoring update
            result = monitoring_service.force_monitoring_update(int(user_id), device_id)

            return Response(result)

        except Exception as e:
            logger.error(f"Error forcing monitoring update: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AlertAPIViewSet(ModelViewSet):
    """
    Alert management API endpoints.

    Provides CRUD operations for alerts and alert management.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = AlertSerializer

    def get_queryset(self):
        """Get alerts with optional filtering"""
        queryset = Alert.objects.select_related('user', 'site', 'rule')

        # Apply filters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        severity_filter = self.request.query_params.get('severity')
        if severity_filter:
            queryset = queryset.filter(severity=severity_filter)

        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        site_id = self.request.query_params.get('site_id')
        if site_id:
            queryset = queryset.filter(site_id=site_id)

        # Date range filtering
        days = self.request.query_params.get('days', 7)
        cutoff_date = timezone.now() - timedelta(days=int(days))
        queryset = queryset.filter(triggered_at__gte=cutoff_date)

        return queryset.order_by('-triggered_at')

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge an alert"""
        try:
            alert = self.get_object()
            notes = request.data.get('notes', '')

            success = monitoring_service.alert_service.acknowledge_alert(
                str(alert.alert_id), request.user.id, 'API', notes
            )

            if success:
                return Response({'status': 'acknowledged'})
            else:
                return Response(
                    {'error': 'Failed to acknowledge alert'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error(f"Error acknowledging alert: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve an alert"""
        try:
            alert = self.get_object()
            notes = request.data.get('notes', '')

            success = monitoring_service.alert_service.resolve_alert(
                str(alert.alert_id), request.user.id, notes
            )

            if success:
                return Response({'status': 'resolved'})
            else:
                return Response(
                    {'error': 'Failed to resolve alert'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error(f"Error resolving alert: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get alert statistics"""
        try:
            days = int(request.query_params.get('days', 7))
            stats = monitoring_service.alert_service.get_alert_statistics(days)

            return Response(stats)

        except Exception as e:
            logger.error(f"Error getting alert statistics: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TicketAPIViewSet(ModelViewSet):
    """
    Operational ticket management API endpoints.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TicketSerializer

    def get_queryset(self):
        """Get tickets with filtering"""
        queryset = OperationalTicket.objects.select_related(
            'category', 'user', 'site', 'assigned_to', 'alert'
        )

        # Apply filters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)

        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign ticket to user"""
        try:
            ticket = self.get_object()
            assigned_to_id = request.data.get('assigned_to_id')
            notes = request.data.get('notes', '')

            if not assigned_to_id:
                return Response(
                    {'error': 'assigned_to_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Assign ticket
            from apps.peoples.models import People
            assigned_user = People.objects.get(id=assigned_to_id)
            ticket.assign_to_user(assigned_user, notes)

            return Response({'status': 'assigned', 'assigned_to': assigned_user.peoplename})

        except Exception as e:
            logger.error(f"Error assigning ticket: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve ticket"""
        try:
            ticket = self.get_object()
            resolution_type = request.data.get('resolution_type', 'MANUAL')
            notes = request.data.get('notes', '')

            ticket.resolve(request.user, resolution_type, notes)

            return Response({'status': 'resolved'})

        except Exception as e:
            logger.error(f"Error resolving ticket: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeviceStatusAPIView(APIView):
    """
    Device status and health API endpoints.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get device status information"""
        try:
            user_id = request.query_params.get('user_id')
            device_id = request.query_params.get('device_id')

            if user_id and device_id:
                # Get specific device status
                device_status = monitoring_service.monitor_device(int(user_id), device_id)
                return Response(device_status)

            # Get all device statuses (limited)
            recent_cutoff = timezone.now() - timedelta(hours=1)
            recent_snapshots = DeviceHealthSnapshot.objects.filter(
                snapshot_taken_at__gte=recent_cutoff
            ).select_related('user')[:100]

            device_statuses = [{
                'user_id': snapshot.user.id,
                'user_name': snapshot.user.peoplename,
                'device_id': snapshot.device_id,
                'overall_health': snapshot.overall_health,
                'health_score': snapshot.health_score,
                'battery_level': snapshot.battery_level,
                'risk_score': snapshot.risk_score,
                'last_updated': snapshot.snapshot_taken_at.isoformat()
            } for snapshot in recent_snapshots]

            return Response({
                'device_statuses': device_statuses,
                'total_devices': len(device_statuses),
                'timestamp': timezone.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Error getting device status: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SystemHealthAPIView(APIView):
    """
    System health and metrics API endpoints.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get system health information"""
        try:
            system_health = monitoring_service.get_system_health()
            return Response(system_health)

        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MonitoringMetricsAPIView(APIView):
    """
    Monitoring metrics API for analytics and charting.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get monitoring metrics with filtering"""
        try:
            # Get query parameters
            metric_type = request.query_params.get('metric_type')
            user_id = request.query_params.get('user_id')
            device_id = request.query_params.get('device_id')
            hours = int(request.query_params.get('hours', 24))

            # Build query
            cutoff_time = timezone.now() - timedelta(hours=hours)
            queryset = MonitoringMetric.objects.filter(recorded_at__gte=cutoff_time)

            if metric_type:
                queryset = queryset.filter(metric_type=metric_type)
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            if device_id:
                queryset = queryset.filter(device_id=device_id)

            # Serialize results
            metrics = queryset.order_by('-recorded_at')[:1000]  # Limit to 1000 records
            serializer = MonitoringMetricSerializer(metrics, many=True)

            return Response({
                'metrics': serializer.data,
                'total_count': queryset.count(),
                'time_range_hours': hours,
                'timestamp': timezone.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AlertRuleAPIViewSet(ModelViewSet):
    """
    Alert rule management API endpoints.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = AlertRuleSerializer
    queryset = AlertRule.objects.all()

    def get_queryset(self):
        """Get alert rules with filtering"""
        queryset = super().get_queryset()

        # Apply filters
        alert_type = self.request.query_params.get('alert_type')
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('name')

    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test an alert rule with sample data"""
        try:
            rule = self.get_object()
            test_data = request.data.get('test_data', {})

            # This would test the rule against sample data
            # Implementation depends on rule engine design

            return Response({
                'rule_id': str(rule.rule_id),
                'test_result': 'passed',  # Placeholder
                'would_trigger': False    # Placeholder
            })

        except Exception as e:
            logger.error(f"Error testing alert rule: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DashboardAPIView(APIView):
    """
    Dashboard data API for real-time monitoring interface.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get comprehensive dashboard data"""
        try:
            # Get dashboard overview data
            dashboard_data = {
                'system_health': monitoring_service.get_system_health(),
                'alert_summary': self._get_alert_summary(),
                'device_summary': self._get_device_summary(),
                'recent_incidents': self._get_recent_incidents(),
                'performance_metrics': self._get_performance_metrics(),
                'timestamp': timezone.now().isoformat()
            }

            return Response(dashboard_data)

        except Exception as e:
            logger.error(f"Error getting dashboard data: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_alert_summary(self) -> Dict:
        """Get alert summary for dashboard"""
        try:
            active_alerts = Alert.objects.filter(status='ACTIVE')

            severity_counts = active_alerts.values('severity').annotate(
                count=Count('id')
            )

            type_counts = active_alerts.values('rule__alert_type').annotate(
                count=Count('id')
            ).order_by('-count')[:5]  # Top 5 alert types

            return {
                'total_active': active_alerts.count(),
                'severity_breakdown': {item['severity']: item['count'] for item in severity_counts},
                'top_alert_types': {item['rule__alert_type']: item['count'] for item in type_counts}
            }

        except Exception as e:
            logger.error(f"Error getting alert summary: {str(e)}")
            return {}

    def _get_device_summary(self) -> Dict:
        """Get device summary for dashboard"""
        try:
            # Get recent device health snapshots
            recent_cutoff = timezone.now() - timedelta(minutes=30)
            recent_snapshots = DeviceHealthSnapshot.objects.filter(
                snapshot_taken_at__gte=recent_cutoff
            )

            health_counts = recent_snapshots.values('overall_health').annotate(
                count=Count('id')
            )

            avg_battery = recent_snapshots.aggregate(
                avg=Avg('battery_level')
            )['avg'] or 0

            devices_at_risk = recent_snapshots.filter(risk_score__gt=0.7).count()

            return {
                'total_active': recent_snapshots.count(),
                'health_breakdown': {item['overall_health']: item['count'] for item in health_counts},
                'avg_battery_level': round(avg_battery, 1),
                'devices_at_risk': devices_at_risk
            }

        except Exception as e:
            logger.error(f"Error getting device summary: {str(e)}")
            return {}

    def _get_recent_incidents(self) -> List[Dict]:
        """Get recent incidents for dashboard"""
        try:
            # Get recent high-severity alerts
            recent_cutoff = timezone.now() - timedelta(hours=24)
            incidents = Alert.objects.filter(
                triggered_at__gte=recent_cutoff,
                severity__in=['HIGH', 'CRITICAL', 'EMERGENCY']
            ).select_related('user', 'site').order_by('-triggered_at')[:10]

            return [{
                'alert_id': str(incident.alert_id),
                'title': incident.title,
                'severity': incident.severity,
                'user_name': incident.user.peoplename,
                'site_name': incident.site.buname if incident.site else 'Unknown',
                'triggered_at': incident.triggered_at.isoformat(),
                'status': incident.status
            } for incident in incidents]

        except Exception as e:
            logger.error(f"Error getting recent incidents: {str(e)}")
            return []

    def _get_performance_metrics(self) -> Dict:
        """Get system performance metrics"""
        try:
            # Get recent system metrics
            recent_cutoff = timezone.now() - timedelta(hours=1)
            recent_metrics = MonitoringMetric.objects.filter(
                recorded_at__gte=recent_cutoff
            )

            # Calculate metrics by type
            metric_summaries = {}
            for metric_type in ['BATTERY_LEVEL', 'SIGNAL_STRENGTH', 'STEP_COUNT']:
                type_metrics = recent_metrics.filter(metric_type=metric_type)
                if type_metrics.exists():
                    avg_value = type_metrics.aggregate(avg=Avg('value'))['avg']
                    metric_summaries[metric_type] = {
                        'average': round(avg_value, 2),
                        'count': type_metrics.count()
                    }

            return metric_summaries

        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            return {}


class BulkMonitoringAPIView(APIView):
    """
    Bulk monitoring operations API.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Trigger bulk monitoring for multiple devices"""
        try:
            device_list = request.data.get('devices', [])

            if not device_list:
                return Response(
                    {'error': 'devices list is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Queue bulk monitoring task
            from apps.monitoring.tasks.monitoring_tasks import bulk_device_monitoring_task
            task = bulk_device_monitoring_task.delay(device_list)

            return Response({
                'status': 'queued',
                'task_id': task.id,
                'devices_count': len(device_list)
            })

        except Exception as e:
            logger.error(f"Error in bulk monitoring: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )