"""
Device Monitoring Tasks.

Predictive device failure detection and health monitoring.
Part of HIGH_IMPACT_FEATURE_OPPORTUNITIES.md implementation.

Revenue Impact: +$2-5/device/month
ROI: Prevent emergency service calls, reduce downtime 40%

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #15: No blocking I/O
- Rule #16: Network timeouts required

@ontology(
    domain="monitoring",
    purpose="Monitor device health and predict failures 1 hour in advance",
    business_value="40% less downtime, proactive maintenance",
    criticality="high",
    tags=["device-monitoring", "predictive-maintenance", "iot", "celery"]
)
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import DatabaseError
from datetime import timedelta

logger = logging.getLogger('monitoring.device_tasks')

__all__ = ['predict_device_failures_task', 'compute_device_health_scores_task']


@shared_task(
    name='apps.monitoring.predict_device_failures',
    bind=True,
    max_retries=3,
    time_limit=600
)
def predict_device_failures_task(self):
    """
    Predict device failures 1 hour in advance.
    Create proactive maintenance alerts.
    
    Runs every hour via Celery beat.
    
    Returns:
        Dict with prediction counts and alerts created
    """
    from apps.mqtt.models import DeviceTelemetry
    from apps.noc.ml.predictive_models.device_failure_predictor import DeviceFailurePredictor
    from apps.noc.models import NOCAlertEvent
    
    try:
        devices_analyzed = 0
        alerts_created = 0
        high_risk_devices = []
        
        # Get devices with recent telemetry (last hour)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        
        devices = DeviceTelemetry.objects.filter(
            timestamp__gte=one_hour_ago
        ).values('device_id', 'tenant_id').distinct()[:500]
        
        logger.info(f"Analyzing {devices.count()} devices for failure prediction")
        
        for device_data in devices:
            device_id = device_data['device_id']
            tenant_id = device_data['tenant_id']
            devices_analyzed += 1
            
            try:
                # Get latest telemetry
                device = DeviceTelemetry.objects.filter(
                    device_id=device_id
                ).order_by('-timestamp').first()
                
                if not device:
                    continue
                
                # Predict failure
                probability, features = DeviceFailurePredictor.predict_failure(device)
                
                # High risk threshold: 65%
                if probability >= 0.65:
                    high_risk_devices.append({
                        'device_id': device_id,
                        'probability': probability,
                        'battery': features.get('battery_level'),
                        'offline_duration': features.get('offline_duration_last_7_days')
                    })
                    
                    # Determine alert severity and recommendation
                    if probability >= 0.80:
                        severity = 'HIGH'
                        recommendation = 'Immediate inspection required'
                    elif probability >= 0.70:
                        severity = 'MEDIUM'
                        recommendation = 'Schedule maintenance within 24 hours'
                    else:
                        severity = 'LOW'
                        recommendation = 'Monitor closely'
                    
                    # Determine failure type
                    battery_level = features.get('battery_level', -1)
                    offline_duration = features.get('offline_duration_last_7_days', 0)
                    
                    if battery_level > 0 and battery_level < 20:
                        failure_type = 'BATTERY_FAILURE'
                        recommendation = 'Battery replacement needed'
                    elif offline_duration > 500:
                        failure_type = 'CONNECTIVITY_FAILURE'
                        recommendation = 'Check network connectivity'
                    else:
                        failure_type = 'DEVICE_FAILURE'
                    
                    # Create DeviceAlert/NOCAlertEvent
                    NOCAlertEvent.objects.create(
                        tenant_id=tenant_id,
                        alert_type='PREDICTED_FAILURE',
                        severity=severity,
                        title=f"Device Failure Predicted: {device_id}",
                        description=f"Device {device_id} has {probability:.0%} probability of failure in next hour. "
                                   f"Type: {failure_type}. {recommendation}. "
                                   f"Battery: {battery_level}%, Offline duration: {offline_duration:.0f} mins/week",
                        source='DEVICE_FAILURE_PREDICTOR',
                        status='NEW',
                        other_data={
                            'device_id': device_id,
                            'failure_probability': probability,
                            'failure_type': failure_type,
                            'features': features,
                            'recommendation': recommendation
                        }
                    )
                    
                    alerts_created += 1
                    
                    logger.warning(
                        f"High failure risk detected for device {device_id}",
                        extra={
                            'device_id': device_id,
                            'probability': probability,
                            'failure_type': failure_type
                        }
                    )

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.error(
                    f"Data processing error predicting failure for device {device_id}: {e}",
                    exc_info=True
                )
                continue
            except DatabaseError as e:
                logger.error(
                    f"Database error predicting failure for device {device_id}: {e}",
                    exc_info=True
                )
                continue
        
        result = {
            'devices_analyzed': devices_analyzed,
            'high_risk_count': len(high_risk_devices),
            'alerts_created': alerts_created,
            'high_risk_devices': high_risk_devices[:10],  # Top 10
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(
            f"Device failure prediction complete",
            extra=result
        )
        
        return result
        
    except DatabaseError as e:
        logger.error(f"Database error in device failure prediction: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120)
    except (ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error(f"Data processing error in device failure prediction: {e}", exc_info=True)
        raise


@shared_task(
    name='apps.monitoring.compute_device_health_scores',
    bind=True,
    max_retries=2,
    time_limit=600
)
def compute_device_health_scores_task(self):
    """
    Compute health scores for all active devices.
    Create alerts for devices below threshold.
    
    Runs every hour via Celery beat.
    
    Returns:
        Dict with health score statistics
    """
    from apps.noc.services.device_health_service import DeviceHealthService
    from apps.mqtt.models import DeviceTelemetry
    
    try:
        # Get all tenants with active devices
        tenants = DeviceTelemetry.objects.filter(
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).values_list('tenant_id', flat=True).distinct()
        
        total_alerts = 0
        
        for tenant_id in tenants:
            try:
                # Create proactive alerts for this tenant
                alerts = DeviceHealthService.create_proactive_alerts(tenant_id)
                total_alerts += sum(alerts.values())
                
                logger.info(
                    f"Created {sum(alerts.values())} health alerts for tenant {tenant_id}",
                    extra={'tenant_id': tenant_id, 'alerts': alerts}
                )

            except DatabaseError as e:
                logger.error(
                    f"Database error processing tenant {tenant_id}: {e}",
                    exc_info=True
                )
                continue
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.error(
                    f"Data processing error for tenant {tenant_id}: {e}",
                    exc_info=True
                )
                continue
        
        return {
            'tenants_processed': len(tenants),
            'total_alerts_created': total_alerts,
            'timestamp': timezone.now().isoformat()
        }
        
    except DatabaseError as e:
        logger.error(f"Database error computing health scores: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120)
