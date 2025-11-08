"""
Tank Level Forecasting Service.

Predicts when tanks will reach critical levels based on:
- Historical consumption patterns
- Day-of-week variations  
- Seasonal factors
- Site activity levels

Generates proactive refill alerts to prevent stockouts.

Following CLAUDE.md:
- Rule #7: Service methods <50 lines
- Rule #11: Specific exception handling
- Rule #14: Query optimization
"""

import logging
from datetime import timedelta
from typing import Dict, List
import statistics
from django.db.models import Avg
from django.utils import timezone
from apps.activity.models import MeterReading, Asset, MeterReadingAlert
from apps.core.constants.datetime_constants import SECONDS_IN_DAY
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)

# Forecast parameters
HISTORY_DAYS = 30
REFILL_BUFFER_DAYS = 3
CRITICAL_LEVEL_PERCENTAGE = 0.20


class TankForecastingService:
    """Predict tank levels and generate proactive refill alerts."""

    @classmethod
    def predict_empty_date(
        cls,
        asset_id: int,
        current_level: float
    ) -> Dict:
        """
        Predict when tank will be empty based on consumption trends.

        Args:
            asset_id: Tank/meter asset ID
            current_level: Current tank level (liters, kWh, etc.)

        Returns:
            Dictionary with predictions and recommendations

        Raises:
            ValueError: If asset not found or invalid data
        """
        try:
            asset = Asset.objects.select_related('location').get(id=asset_id)
            
            # Get consumption history
            consumption_history = cls._get_consumption_history(asset_id, days=HISTORY_DAYS)
            
            if len(consumption_history) < 3:
                return {
                    'predicted_empty_date': None,
                    'days_remaining': None,
                    'recommended_refill_date': None,
                    'error': 'Insufficient historical data (need 3+ readings)',
                    'confidence': 0.0
                }
            
            # Calculate average daily consumption
            avg_daily = statistics.mean(consumption_history)
            
            # Calculate trend
            trend = cls._calculate_consumption_trend(consumption_history)
            
            # Adjust for trend
            if trend['slope'] > 0.1:
                adjusted_avg = avg_daily * 1.2
                trend_label = 'INCREASING'
            elif trend['slope'] < -0.1:
                adjusted_avg = avg_daily * 0.9
                trend_label = 'DECREASING'
            else:
                adjusted_avg = avg_daily
                trend_label = 'STABLE'
            
            # Predict empty date
            if adjusted_avg == 0:
                days_remaining = float('inf')
            else:
                days_remaining = current_level / adjusted_avg
            
            predicted_empty = timezone.now() + timedelta(days=days_remaining)
            
            # Recommended refill date
            refill_buffer = max(REFILL_BUFFER_DAYS, days_remaining * CRITICAL_LEVEL_PERCENTAGE)
            recommended_refill = timezone.now() + timedelta(days=(days_remaining - refill_buffer))
            
            # Calculate confidence
            std_dev = statistics.stdev(consumption_history) if len(consumption_history) > 1 else 0
            coefficient_of_variation = std_dev / avg_daily if avg_daily > 0 else 1
            confidence = max(0, min(1, 1 - coefficient_of_variation))
            
            result = {
                'asset_id': asset_id,
                'asset_name': asset.name,
                'current_level': round(current_level, 2),
                'unit': asset.other_data.get('unit', 'LITERS') if asset.other_data else 'LITERS',
                'predicted_empty_date': predicted_empty.isoformat(),
                'days_remaining': round(days_remaining, 1),
                'recommended_refill_date': recommended_refill.isoformat(),
                'average_daily_consumption': round(avg_daily, 2),
                'adjusted_daily_consumption': round(adjusted_avg, 2),
                'confidence': round(confidence, 2),
                'consumption_trend': trend_label,
                'trend_slope': round(trend['slope'], 4),
                'r_squared': round(trend['r_squared'], 3),
                'data_points': len(consumption_history),
                'forecasted_at': timezone.now().isoformat()
            }
            
            logger.info(
                "tank_forecast_computed",
                extra={
                    'asset_id': asset_id,
                    'days_remaining': days_remaining,
                    'confidence': confidence,
                    'trend': trend_label
                }
            )
            
            return result
            
        except Asset.DoesNotExist as e:
            raise ValueError(f"Asset {asset_id} not found") from e
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                "tank_forecast_failed",
                extra={'asset_id': asset_id, 'error': str(e)},
                exc_info=True
            )
            raise

    @classmethod
    def _get_consumption_history(cls, asset_id: int, days: int = 30) -> List[float]:
        """
        Get daily consumption for last N days.

        Returns only positive consumption values (actual usage).
        """
        cutoff = timezone.now() - timedelta(days=days)
        
        readings = MeterReading.objects.filter(
            asset_id=asset_id,
            timestamp__gte=cutoff,
            consumption__isnull=False,
            consumption__gt=0
        ).order_by('timestamp')
        
        return [float(r.consumption) for r in readings]

    @classmethod
    def _calculate_consumption_trend(cls, history: List[float]) -> Dict:
        """
        Simple linear regression to determine consumption trend.

        Returns:
            {
                'slope': float,  # >0 = increasing, <0 = decreasing
                'r_squared': float  # Goodness of fit (0-1)
            }
        """
        if len(history) < 2:
            return {'slope': 0, 'r_squared': 0}
        
        n = len(history)
        x = list(range(n))
        y = history
        
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        
        # R-squared
        y_pred = [slope * (xi - x_mean) + y_mean for xi in x]
        ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        return {
            'slope': slope,
            'r_squared': max(0, r_squared)
        }

    @classmethod
    def create_refill_alert(cls, asset_id: int, forecast: Dict) -> Optional[int]:
        """
        Create proactive alert for tank refill.

        Creates alert when:
        - days_remaining <= 3, OR
        - current_level < 20% of capacity

        Args:
            asset_id: Tank asset ID
            forecast: Forecast dictionary from predict_empty_date

        Returns:
            Alert ID if created, None otherwise
        """
        days_remaining = forecast.get('days_remaining')
        
        if not days_remaining or days_remaining > REFILL_BUFFER_DAYS:
            return None
        
        try:
            # Determine severity
            if days_remaining <= 1:
                severity = 'CRITICAL'
            elif days_remaining <= 2:
                severity = 'HIGH'
            else:
                severity = 'MEDIUM'
            
            # Build message
            message = (
                f"🚨 Tank refill required! Predicted empty in {days_remaining:.1f} days "
                f"({forecast['predicted_empty_date'][:10]}). "
                f"Recommended refill by: {forecast['recommended_refill_date'][:10]}."
            )
            
            alert = MeterReadingAlert.objects.create(
                asset_id=asset_id,
                alert_type='REFILL_REQUIRED',
                severity=severity,
                message=message,
                metadata={
                    'forecast': forecast,
                    'auto_generated': True,
                    'forecast_confidence': forecast['confidence']
                }
            )
            
            logger.warning(
                "tank_refill_alert_created",
                extra={
                    'asset_id': asset_id,
                    'alert_id': alert.id,
                    'days_remaining': days_remaining,
                    'severity': severity,
                    'confidence': forecast['confidence']
                }
            )
            
            return alert.id
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                "refill_alert_creation_failed",
                extra={'asset_id': asset_id, 'error': str(e)},
                exc_info=True
            )
            raise

    @classmethod
    def get_all_tank_forecasts(cls, tenant_id: int) -> List[Dict]:
        """
        Get forecasts for all tanks in tenant.

        Returns:
            List of forecast dictionaries sorted by days_remaining
        """
        try:
            # Get all tank/fuel assets
            tanks = Asset.objects.filter(
                tenant_id=tenant_id,
                meter_type__in=['DIESEL', 'FUEL', 'GAS', 'WATER']
            ).select_related('location')
            
            forecasts = []
            
            for tank in tanks:
                # Get latest reading
                latest = tank.meter_readings.order_by('-timestamp').first()
                
                if not latest:
                    continue
                
                forecast = cls.predict_empty_date(
                    asset_id=tank.id,
                    current_level=float(latest.reading_value)
                )
                
                if forecast.get('days_remaining'):
                    forecast['site_name'] = tank.location.name if tank.location else 'Unknown'
                    forecasts.append(forecast)
            
            # Sort by days_remaining (most urgent first)
            forecasts.sort(key=lambda x: x['days_remaining'])
            
            return forecasts
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                "get_all_forecasts_failed",
                extra={'tenant_id': tenant_id, 'error': str(e)},
                exc_info=True
            )
            return []
