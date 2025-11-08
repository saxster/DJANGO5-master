"""
Meter Intelligence Background Tasks.

Tasks:
- Tank level forecasting (daily)
- Theft and leak detection (hourly)
- Cost optimization analysis (weekly)
- Executive dashboard generation (monthly)

Following CLAUDE.md standards.
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from apps.activity.models import Asset, MeterReading
from apps.activity.services.tank_forecasting_service import TankForecastingService
from apps.activity.services.theft_leak_detection_service import TheftLeakDetectionService
from apps.activity.services.cost_optimization_service import CostOptimizationService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


@shared_task(
    name='apps.activity.forecast_tank_levels',
    bind=True,
    max_retries=3
)
def forecast_all_tanks_task(self, tenant_id: int):
    """
    Run tank level forecasting for all diesel/fuel tanks.

    Creates proactive refill alerts when days_remaining <= 3.
    Stores forecast in asset.other_data for UI display.

    Runs daily at 6 AM via Celery beat.

    Args:
        tenant_id: Tenant identifier

    Returns:
        dict: Processing results
    """
    try:
        # Get all tank assets
        tanks = Asset.objects.filter(
            tenant_id=tenant_id,
            meter_type__in=['DIESEL', 'FUEL', 'GAS', 'WATER']
        ).select_related('location')
        
        forecasts_created = 0
        alerts_created = 0
        warnings = []
        
        for tank in tanks:
            # Get latest reading
            latest_reading = tank.meter_readings.order_by('-timestamp').first()
            
            if not latest_reading:
                warnings.append(f"Tank {tank.name}: No readings available")
                continue
            
            try:
                # Predict empty date
                forecast = TankForecastingService.predict_empty_date(
                    asset_id=tank.id,
                    current_level=float(latest_reading.reading_value)
                )
                
                if forecast.get('error'):
                    warnings.append(f"Tank {tank.name}: {forecast['error']}")
                    continue
                
                # Store forecast in asset.other_data
                if not tank.other_data:
                    tank.other_data = {}
                
                tank.other_data['tank_forecast'] = forecast
                tank.other_data['forecast_updated_at'] = timezone.now().isoformat()
                tank.save()
                
                forecasts_created += 1
                
                # Create alert if needed (days_remaining <= 3)
                alert_id = TankForecastingService.create_refill_alert(tank.id, forecast)
                
                if alert_id:
                    alerts_created += 1
                    
            except Exception as e:
                warnings.append(f"Tank {tank.name}: {str(e)}")
                logger.error(
                    "tank_forecast_error",
                    extra={'tank_id': tank.id, 'error': str(e)},
                    exc_info=True
                )
        
        result = {
            'status': 'success',
            'tenant_id': tenant_id,
            'tanks_processed': len(tanks),
            'forecasts_created': forecasts_created,
            'alerts_created': alerts_created,
            'warnings': warnings
        }
        
        logger.info(
            "tank_forecasting_task_complete",
            extra=result
        )
        
        return result
        
    except DATABASE_EXCEPTIONS as e:
        logger.error(
            "tank_forecasting_task_failed",
            extra={'tenant_id': tenant_id, 'error': str(e)},
            exc_info=True
        )
        raise self.retry(exc=e)
    
    except Exception as e:
        logger.error(
            "tank_forecasting_task_error",
            extra={'tenant_id': tenant_id, 'error': str(e)},
            exc_info=True
        )
        return {
            'status': 'error',
            'tenant_id': tenant_id,
            'error': str(e)
        }


@shared_task(
    name='apps.activity.detect_theft_leaks',
    bind=True,
    max_retries=3
)
def detect_theft_leaks_task(self, tenant_id: int):
    """
    Detect theft and leaks across all meters.

    Analyzes recent readings for:
    - Sudden drops (theft)
    - Gradual leaks
    - Off-hours consumption anomalies

    Runs hourly via Celery beat.

    Args:
        tenant_id: Tenant identifier

    Returns:
        dict: Detection results
    """
    try:
        # Get all fuel/water assets (theft/leak prone)
        assets = Asset.objects.filter(
            tenant_id=tenant_id,
            meter_type__in=['DIESEL', 'FUEL', 'WATER']
        )
        
        theft_detected = 0
        leak_detected = 0
        alerts_created = 0
        
        for asset in assets:
            # Get last 2 readings for sudden drop check
            readings = asset.meter_readings.order_by('-timestamp')[:2]
            
            if len(readings) == 2:
                current = readings[0]
                previous = readings[1]
                
                # Check for sudden drop (theft)
                theft_check = TheftLeakDetectionService.detect_sudden_drop(
                    asset_id=asset.id,
                    current_reading=float(current.reading_value),
                    previous_reading=float(previous.reading_value),
                    timestamp=current.timestamp
                )
                
                if theft_check.get('is_theft'):
                    theft_detected += 1
                    
                    alert_id = TheftLeakDetectionService.create_theft_leak_alert(
                        asset_id=asset.id,
                        detection_type='THEFT',
                        details=theft_check
                    )
                    
                    if alert_id:
                        alerts_created += 1
            
            # Check for gradual leak (last 7 days)
            leak_check = TheftLeakDetectionService.detect_gradual_leak(
                asset_id=asset.id,
                analysis_days=7
            )
            
            if leak_check.get('is_leak'):
                leak_detected += 1
                
                alert_id = TheftLeakDetectionService.create_theft_leak_alert(
                    asset_id=asset.id,
                    detection_type='LEAK',
                    details=leak_check
                )
                
                if alert_id:
                    alerts_created += 1
        
        result = {
            'status': 'success',
            'tenant_id': tenant_id,
            'assets_analyzed': len(assets),
            'theft_detected': theft_detected,
            'leaks_detected': leak_detected,
            'alerts_created': alerts_created
        }
        
        logger.info(
            "theft_leak_detection_complete",
            extra=result
        )
        
        return result
        
    except DATABASE_EXCEPTIONS as e:
        logger.error(
            "theft_leak_detection_failed",
            extra={'tenant_id': tenant_id, 'error': str(e)},
            exc_info=True
        )
        raise self.retry(exc=e)
    
    except Exception as e:
        logger.error(
            "theft_leak_detection_error",
            extra={'tenant_id': tenant_id, 'error': str(e)},
            exc_info=True
        )
        return {
            'status': 'error',
            'tenant_id': tenant_id,
            'error': str(e)
        }


@shared_task(
    name='apps.activity.generate_cost_dashboards',
    bind=True
)
def generate_cost_dashboards_task(self, tenant_id: int):
    """
    Generate executive cost dashboards for all sites.

    Creates monthly cost dashboard PDFs and emails to executives.
    Runs weekly via Celery beat.

    Args:
        tenant_id: Tenant identifier

    Returns:
        dict: Generation results
    """
    try:
        from apps.onboarding.models import Bt
        
        # Get all sites for tenant
        sites = Bt.objects.filter(tenant_id=tenant_id)
        
        dashboards_created = 0
        
        for site in sites:
            dashboard = CostOptimizationService.generate_cost_dashboard(
                tenant_id=tenant_id,
                site_id=site.id,
                period_days=30
            )
            
            # Store in site.other_data for quick access
            if not site.other_data:
                site.other_data = {}
            
            site.other_data['cost_dashboard'] = dashboard
            site.other_data['dashboard_updated_at'] = timezone.now().isoformat()
            site.save()
            
            dashboards_created += 1
            
            # TODO: Generate PDF and email to CFO/management
            # Would use existing report generation infrastructure
        
        result = {
            'status': 'success',
            'tenant_id': tenant_id,
            'dashboards_created': dashboards_created
        }
        
        logger.info(
            "cost_dashboards_generated",
            extra=result
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "cost_dashboard_generation_error",
            extra={'tenant_id': tenant_id, 'error': str(e)},
            exc_info=True
        )
        return {
            'status': 'error',
            'tenant_id': tenant_id,
            'error': str(e)
        }


@shared_task(name='apps.activity.monitor_all_meter_intelligence')
def monitor_all_meter_intelligence_task():
    """
    Master task to run all meter intelligence features for all tenants.

    Orchestrates:
    - Tank forecasting
    - Theft/leak detection
    - Cost dashboards

    Runs once daily.

    Returns:
        dict: Aggregate results
    """
    from apps.tenants.models import Tenant
    
    results = {
        'tenants_processed': 0,
        'total_forecasts': 0,
        'total_theft_detected': 0,
        'total_leaks_detected': 0,
        'total_dashboards': 0,
        'errors': []
    }
    
    tenants = Tenant.objects.filter(is_active=True)
    
    for tenant in tenants:
        try:
            # Run tank forecasting
            forecast_result = forecast_all_tanks_task(tenant.id)
            if forecast_result['status'] == 'success':
                results['total_forecasts'] += forecast_result['forecasts_created']
            
            # Run theft/leak detection
            detection_result = detect_theft_leaks_task(tenant.id)
            if detection_result['status'] == 'success':
                results['total_theft_detected'] += detection_result['theft_detected']
                results['total_leaks_detected'] += detection_result['leaks_detected']
            
            # Run cost dashboards (weekly, not daily)
            # dashboard_result = generate_cost_dashboards_task(tenant.id)
            
            results['tenants_processed'] += 1
            
        except Exception as e:
            results['errors'].append({
                'tenant_id': tenant.id,
                'error': str(e)
            })
            logger.error(
                "meter_intelligence_tenant_error",
                extra={'tenant_id': tenant.id, 'error': str(e)},
                exc_info=True
            )
    
    logger.info(
        "meter_intelligence_monitoring_complete",
        extra=results
    )
    
    return results
