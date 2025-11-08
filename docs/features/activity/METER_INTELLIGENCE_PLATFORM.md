# Meter Intelligence & Insights Platform
## Transforming Meter Readings into Actionable Intelligence

**Date**: November 6, 2025  
**Purpose**: High-impact analytics and insights from existing meter/tank data  
**Scope**: Electricity, Water, Diesel, UPS, Gas, Temperature, Pressure  
**Business Value**: Energy optimization, cost savings, predictive maintenance, environmental compliance

---

## 🎯 Executive Summary

### Current State
YOUTILITY5 **already collects comprehensive meter data**:
- ✅ **Meter readings**: Electricity, Water, Diesel, Gas, UPS, Temperature, Pressure
- ✅ **AI/ML processing**: OCR from photos, confidence scoring
- ✅ **Anomaly detection**: Basic anomaly alerts
- ✅ **Data models**: MeterReading, MeterPoint, AssetUtilizationMetric

### Opportunity
**Transform raw readings into high-value intelligence**:
- 💰 **Cost optimization**: Identify wastage, peak vs off-peak usage
- 🔮 **Predictive insights**: When tank needs refilling, consumption forecasts
- 🚨 **Theft/leak detection**: Sudden drops, unusual patterns
- 📊 **Benchmarking**: Site vs site, period vs period comparisons
- 🌱 **Environmental impact**: Carbon footprint, sustainability metrics
- 💡 **Actionable alerts**: Auto-create work orders, budget warnings

### Business Impact
- **30-40% cost savings** on utilities (identify wastage)
- **Prevent stockouts** (diesel tank empty → generator fails)
- **Detect theft early** (fuel pilferage common in facilities)
- **Regulatory compliance** (environmental reporting)
- **Executive dashboards** (CFO-ready cost analytics)
- **Revenue potential**: $100-200/month per site premium feature

---

## 🔍 Current Capabilities Assessment

### ✅ What's Already Built

**Data Collection**:
```python
# apps/activity/models/meter_reading_model.py
class MeterReading:
    meter_type: ELECTRICITY, WATER, DIESEL, GAS, etc.
    reading_value: Decimal
    unit: KWH, LITERS, M3, etc.
    timestamp: datetime
    confidence_score: AI accuracy
    consumption: Change since last reading
    cost_estimate: Calculated cost
    anomaly_score: 0-100
    validation_status: PENDING, APPROVED, REJECTED
```

**Basic Analytics**:
```python
# apps/activity/services/meter_reading_service.py
MeterReadingService:
    - get_consumption_analytics()  # Basic consumption trends
    - detect_anomalies_batch()  # Anomaly detection
    - validate_reading()  # Reading validation
```

**AI/ML Features**:
```python
# apps/core_onboarding/services/ocr_service.py
OCRService:
    - extract_meter_reading_from_image()  # OCR extraction
    - Supports electricity, water, diesel meters
```

### ❌ What's Missing (High-Impact Opportunities)

1. **Predictive Tank Level Forecasting** ⭐⭐⭐⭐⭐
   - When will diesel tank be empty?
   - Optimal refill scheduling
   - Prevent generator failures

2. **Cost Optimization Intelligence** ⭐⭐⭐⭐⭐
   - Peak vs off-peak usage analysis
   - Budget vs actual tracking
   - Cost-saving recommendations

3. **Theft & Leak Detection** ⭐⭐⭐⭐⭐
   - Sudden drops in fuel (pilferage)
   - Gradual leaks (water, diesel)
   - Unauthorized consumption

4. **Comparative Benchmarking** ⭐⭐⭐⭐
   - Site vs site efficiency
   - Industry benchmarks
   - Best/worst performers

5. **Environmental Impact Tracking** ⭐⭐⭐⭐
   - Carbon footprint calculation
   - Sustainability scoring
   - ESG reporting

6. **UPS Health Degradation** ⭐⭐⭐⭐
   - Runtime capacity trending
   - Battery replacement prediction
   - Load management alerts

7. **Executive Cost Dashboards** ⭐⭐⭐⭐⭐
   - CFO-ready utility cost breakdowns
   - Trend analysis and forecasts
   - Budget variance alerts

8. **Auto-Action Recommendations** ⭐⭐⭐⭐
   - Auto-create work orders (refill tank)
   - Schedule off-peak operations
   - Alert procurement for fuel orders

---

## 💡 High-Impact Features to Implement

## Feature 1: Predictive Tank Level Forecasting ⭐⭐⭐⭐⭐

### Business Problem
**Diesel tanks run empty → Generators fail → Site blackout → SLA breach + revenue loss**

Current: Reactive (tank empty, scramble for fuel)  
Future: **Predictive (auto-alert 3 days before empty, schedule refill)**

### Solution

**File**: `apps/activity/services/tank_forecasting_service.py`

```python
"""
Tank Level Forecasting Service.

Predicts when tanks will reach critical levels based on:
- Historical consumption patterns
- Day-of-week variations
- Seasonal factors
- Site activity levels

Following CLAUDE.md standards.
"""

import logging
from datetime import timedelta
from typing import Dict, List, Tuple
import statistics
from django.db.models import Avg, Sum
from django.utils import timezone
from apps.activity.models import MeterReading, Asset
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

logger = logging.getLogger(__name__)


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
            {
                'predicted_empty_date': datetime,
                'days_remaining': int,
                'recommended_refill_date': datetime,
                'average_daily_consumption': float,
                'confidence': float,  # 0-1
                'consumption_trend': 'INCREASING|STABLE|DECREASING'
            }
        """
        try:
            # Get consumption history (last 30 days)
            consumption_history = cls._get_consumption_history(asset_id, days=30)
            
            if not consumption_history:
                return {
                    'predicted_empty_date': None,
                    'days_remaining': None,
                    'recommended_refill_date': None,
                    'error': 'Insufficient historical data'
                }
            
            # Calculate average daily consumption
            avg_daily = statistics.mean(consumption_history)
            
            # Calculate trend (increasing/decreasing consumption)
            trend = cls._calculate_consumption_trend(consumption_history)
            
            # Adjust for trend
            if trend['slope'] > 0.1:  # Increasing consumption
                adjusted_avg = avg_daily * 1.2  # 20% buffer
                trend_label = 'INCREASING'
            elif trend['slope'] < -0.1:  # Decreasing consumption
                adjusted_avg = avg_daily * 0.9
                trend_label = 'DECREASING'
            else:
                adjusted_avg = avg_daily
                trend_label = 'STABLE'
            
            # Predict empty date
            days_remaining = current_level / adjusted_avg if adjusted_avg > 0 else float('inf')
            predicted_empty = timezone.now() + timedelta(days=days_remaining)
            
            # Recommended refill date (3 days before empty, or when 20% remaining)
            refill_threshold = max(3, days_remaining * 0.2)
            recommended_refill = timezone.now() + timedelta(days=(days_remaining - refill_threshold))
            
            # Confidence based on data consistency
            std_dev = statistics.stdev(consumption_history) if len(consumption_history) > 1 else 0
            coefficient_of_variation = std_dev / avg_daily if avg_daily > 0 else 1
            confidence = max(0, min(1, 1 - coefficient_of_variation))
            
            result = {
                'predicted_empty_date': predicted_empty,
                'days_remaining': round(days_remaining, 1),
                'recommended_refill_date': recommended_refill,
                'average_daily_consumption': round(avg_daily, 2),
                'confidence': round(confidence, 2),
                'consumption_trend': trend_label,
                'trend_slope': trend['slope'],
                'data_points': len(consumption_history)
            }
            
            logger.info(
                "tank_forecast_computed",
                extra={
                    'asset_id': asset_id,
                    'days_remaining': days_remaining,
                    'confidence': confidence
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "tank_forecast_failed",
                extra={'asset_id': asset_id, 'error': str(e)},
                exc_info=True
            )
            raise

    @classmethod
    def _get_consumption_history(cls, asset_id: int, days: int = 30) -> List[float]:
        """Get daily consumption for last N days."""
        cutoff = timezone.now() - timedelta(days=days)
        
        readings = MeterReading.objects.filter(
            asset_id=asset_id,
            timestamp__gte=cutoff,
            consumption__isnull=False,
            consumption__gt=0
        ).order_by('timestamp')
        
        return [float(r.consumption) for r in readings if r.consumption > 0]

    @classmethod
    def _calculate_consumption_trend(cls, history: List[float]) -> Dict:
        """
        Simple linear regression to determine trend.
        
        Returns:
            {
                'slope': float,  # Positive = increasing, negative = decreasing
                'r_squared': float
            }
        """
        if len(history) < 2:
            return {'slope': 0, 'r_squared': 0}
        
        n = len(history)
        x = list(range(n))
        y = history
        
        # Simple linear regression
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        
        # R-squared calculation
        y_pred = [slope * (xi - x_mean) + y_mean for xi in x]
        ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        return {
            'slope': slope,
            'r_squared': r_squared
        }

    @classmethod
    def create_refill_alert(cls, asset_id: int, forecast: Dict) -> None:
        """
        Create proactive alert for tank refill.
        
        Creates alert when days_remaining <= 3 or level < 20%.
        """
        if forecast['days_remaining'] and forecast['days_remaining'] <= 3:
            from apps.activity.models import MeterReadingAlert
            
            severity = 'CRITICAL' if forecast['days_remaining'] <= 1 else 'HIGH'
            
            MeterReadingAlert.objects.create(
                meter_reading=None,  # Forecast, not specific reading
                asset_id=asset_id,
                alert_type='REFILL_REQUIRED',
                severity=severity,
                message=f"Tank predicted empty in {forecast['days_remaining']} days. Refill recommended by {forecast['recommended_refill_date'].strftime('%Y-%m-%d')}.",
                metadata={
                    'forecast': forecast,
                    'auto_generated': True
                }
            )
            
            logger.warning(
                "tank_refill_alert_created",
                extra={
                    'asset_id': asset_id,
                    'days_remaining': forecast['days_remaining'],
                    'severity': severity
                }
            )
```

**Background Task**: `background_tasks/tank_forecasting_tasks.py`

```python
"""Tank forecasting background tasks."""

import logging
from celery import shared_task
from django.utils import timezone
from apps.activity.models import Asset
from apps.activity.services.tank_forecasting_service import TankForecastingService

logger = logging.getLogger(__name__)


@shared_task(name='apps.activity.forecast_tank_levels')
def forecast_all_tanks_task(tenant_id: int):
    """
    Run tank level forecasting for all diesel/fuel tanks.
    
    Creates proactive refill alerts.
    Runs daily via Celery beat.
    """
    try:
        # Get all tank assets (diesel, fuel)
        tanks = Asset.objects.filter(
            tenant_id=tenant_id,
            meter_type__in=['DIESEL', 'FUEL', 'GAS']
        )
        
        forecasts_created = 0
        alerts_created = 0
        
        for tank in tanks:
            # Get latest reading
            latest_reading = tank.meter_readings.order_by('-timestamp').first()
            
            if not latest_reading:
                continue
            
            # Predict empty date
            forecast = TankForecastingService.predict_empty_date(
                asset_id=tank.id,
                current_level=float(latest_reading.reading_value)
            )
            
            forecasts_created += 1
            
            # Store forecast in asset.other_data
            if not tank.other_data:
                tank.other_data = {}
            
            tank.other_data['tank_forecast'] = forecast
            tank.other_data['forecast_updated_at'] = timezone.now().isoformat()
            tank.save()
            
            # Create alert if needed
            if forecast.get('days_remaining') and forecast['days_remaining'] <= 3:
                TankForecastingService.create_refill_alert(tank.id, forecast)
                alerts_created += 1
        
        logger.info(
            "tank_forecasting_complete",
            extra={
                'tenant_id': tenant_id,
                'tanks_processed': len(tanks),
                'forecasts_created': forecasts_created,
                'alerts_created': alerts_created
            }
        )
        
        return {
            'status': 'success',
            'tanks_processed': len(tanks),
            'forecasts_created': forecasts_created,
            'alerts_created': alerts_created
        }
        
    except Exception as e:
        logger.error(
            "tank_forecasting_failed",
            extra={'tenant_id': tenant_id, 'error': str(e)},
            exc_info=True
        )
        return {'status': 'error', 'error': str(e)}
```

**Celery Beat Schedule**:
```python
'daily_tank_forecasting': {
    'task': 'apps.activity.forecast_tank_levels',
    'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
    'args': (1,),  # Tenant ID
},
```

**UI Widget**: Display on asset detail page

```html
<!-- apps/activity/templates/assets/tank_forecast_widget.html -->
{% if asset.other_data.tank_forecast %}
<div class="tank-forecast-widget">
    <h4>🔮 Tank Level Forecast</h4>
    
    {% with forecast=asset.other_data.tank_forecast %}
    
    <div class="forecast-summary">
        <div class="metric {% if forecast.days_remaining <= 3 %}critical{% endif %}">
            <span class="label">Days Until Empty:</span>
            <span class="value">{{ forecast.days_remaining|floatformat:1 }}</span>
        </div>
        
        <div class="metric">
            <span class="label">Recommended Refill Date:</span>
            <span class="value">{{ forecast.recommended_refill_date|date:"M d, Y" }}</span>
        </div>
        
        <div class="metric">
            <span class="label">Avg Daily Consumption:</span>
            <span class="value">{{ forecast.average_daily_consumption|floatformat:2 }} {{ asset.unit }}</span>
        </div>
        
        <div class="metric">
            <span class="label">Consumption Trend:</span>
            <span class="value trend-{{ forecast.consumption_trend|lower }}">
                {% if forecast.consumption_trend == 'INCREASING' %}📈{% elif forecast.consumption_trend == 'DECREASING' %}📉{% else %}➡️{% endif %}
                {{ forecast.consumption_trend }}
            </span>
        </div>
        
        <div class="metric">
            <span class="label">Forecast Confidence:</span>
            <span class="value">{{ forecast.confidence|floatformat:0 }}%</span>
        </div>
    </div>
    
    {% if forecast.days_remaining <= 3 %}
    <div class="alert alert-danger">
        <strong>⚠️ Action Required:</strong> Tank refill needed within {{ forecast.days_remaining|floatformat:1 }} days.
        <a href="#" class="btn btn-primary btn-sm">Create Refill Work Order</a>
    </div>
    {% endif %}
    
    {% endwith %}
</div>
{% endif %}
```

---

## Feature 2: Theft & Leak Detection ⭐⭐⭐⭐⭐

### Business Problem
**Fuel pilferage costs facilities $10K-50K/year. Water leaks waste 20-30% of consumption.**

### Solution

**File**: `apps/activity/services/theft_leak_detection_service.py`

```python
"""
Theft and Leak Detection Service.

Detects:
- Sudden drops (theft/pilferage)
- Gradual leaks (water, diesel)
- Abnormal consumption patterns
- Off-hours usage (when site closed)

Following CLAUDE.md standards.
"""

import logging
from datetime import timedelta
from typing import Dict, List
import statistics
from django.db.models import Q
from django.utils import timezone
from apps.activity.models import MeterReading, Asset

logger = logging.getLogger(__name__)


class TheftLeakDetectionService:
    """Detect theft, pilferage, and leaks from meter readings."""

    # Detection thresholds
    SUDDEN_DROP_THRESHOLD = 0.15  # 15% drop in single reading
    LEAK_RATE_THRESHOLD = 0.05  # 5% gradual loss per week
    OFF_HOURS_THRESHOLD = 0.1  # 10% consumption outside business hours

    @classmethod
    def detect_sudden_drop(
        cls,
        asset_id: int,
        current_reading: float,
        previous_reading: float
    ) -> Dict:
        """
        Detect sudden drops indicating theft/pilferage.
        
        Returns:
            {
                'is_theft': bool,
                'drop_percentage': float,
                'drop_amount': float,
                'confidence': float,
                'estimated_loss_value': float
            }
        """
        if previous_reading == 0:
            return {'is_theft': False, 'drop_percentage': 0}
        
        drop_amount = previous_reading - current_reading
        drop_percentage = drop_amount / previous_reading
        
        # Negative drops are normal consumption
        if drop_amount <= 0:
            return {'is_theft': False, 'drop_percentage': 0}
        
        # Check against threshold
        is_theft = drop_percentage >= cls.SUDDEN_DROP_THRESHOLD
        
        # Estimate value of loss
        asset = Asset.objects.get(id=asset_id)
        unit_cost = asset.other_data.get('unit_cost', 0) if asset.other_data else 0
        estimated_loss = drop_amount * unit_cost
        
        # Confidence based on magnitude
        if drop_percentage >= 0.30:  # 30%+ drop
            confidence = 0.95
        elif drop_percentage >= 0.20:
            confidence = 0.85
        elif drop_percentage >= 0.15:
            confidence = 0.70
        else:
            confidence = 0.50
        
        result = {
            'is_theft': is_theft,
            'drop_percentage': round(drop_percentage * 100, 2),
            'drop_amount': round(drop_amount, 2),
            'confidence': confidence,
            'estimated_loss_value': round(estimated_loss, 2)
        }
        
        if is_theft:
            logger.warning(
                "potential_theft_detected",
                extra={
                    'asset_id': asset_id,
                    'drop_percentage': result['drop_percentage'],
                    'estimated_loss': estimated_loss
                }
            )
        
        return result

    @classmethod
    def detect_gradual_leak(
        cls,
        asset_id: int,
        days: int = 7
    ) -> Dict:
        """
        Detect gradual leaks from consumption pattern.
        
        Looks for:
        - Consistent small losses
        - Night-time consumption (when site closed)
        - Consumption without corresponding activity
        """
        cutoff = timezone.now() - timedelta(days=days)
        
        readings = MeterReading.objects.filter(
            asset_id=asset_id,
            timestamp__gte=cutoff
        ).order_by('timestamp')
        
        if len(readings) < 2:
            return {'is_leak': False, 'message': 'Insufficient data'}
        
        # Calculate total loss
        total_loss = sum(
            float(r.consumption) for r in readings 
            if r.consumption and r.consumption > 0
        )
        
        # Get expected consumption (from site activity, occupancy, etc.)
        # For now, use historical baseline
        expected = cls._get_expected_consumption(asset_id, days)
        
        if expected == 0:
            return {'is_leak': False, 'message': 'No baseline data'}
        
        loss_rate = (total_loss - expected) / expected
        
        is_leak = loss_rate >= cls.LEAK_RATE_THRESHOLD
        
        # Estimate leak cost
        asset = Asset.objects.get(id=asset_id)
        unit_cost = asset.other_data.get('unit_cost', 0) if asset.other_data else 0
        leak_amount = total_loss - expected
        estimated_cost = leak_amount * unit_cost
        
        result = {
            'is_leak': is_leak,
            'leak_rate_percentage': round(loss_rate * 100, 2),
            'leak_amount_per_day': round(leak_amount / days, 2),
            'estimated_monthly_cost': round(estimated_cost * 30 / days, 2),
            'confidence': 0.75 if is_leak else 0.5
        }
        
        if is_leak:
            logger.warning(
                "potential_leak_detected",
                extra={
                    'asset_id': asset_id,
                    'leak_rate': result['leak_rate_percentage'],
                    'monthly_cost': result['estimated_monthly_cost']
                }
            )
        
        return result

    @classmethod
    def _get_expected_consumption(cls, asset_id: int, days: int) -> float:
        """Get baseline expected consumption."""
        # Get same period from previous month
        month_ago = timezone.now() - timedelta(days=30)
        comparison_start = month_ago - timedelta(days=days)
        
        baseline_readings = MeterReading.objects.filter(
            asset_id=asset_id,
            timestamp__gte=comparison_start,
            timestamp__lt=month_ago
        )
        
        if not baseline_readings.exists():
            return 0
        
        return sum(
            float(r.consumption) for r in baseline_readings 
            if r.consumption and r.consumption > 0
        )

    @classmethod
    def create_theft_leak_alert(
        cls,
        asset_id: int,
        detection_type: str,
        details: Dict
    ) -> None:
        """Create alert for detected theft or leak."""
        from apps.activity.models import MeterReadingAlert
        
        if detection_type == 'THEFT':
            severity = 'CRITICAL'
            message = f"Potential fuel theft detected: {details['drop_percentage']}% sudden drop. Estimated loss: ${details['estimated_loss_value']}"
        elif detection_type == 'LEAK':
            severity = 'HIGH'
            message = f"Potential leak detected: {details['leak_rate_percentage']}% excess consumption. Estimated monthly cost: ${details['estimated_monthly_cost']}"
        else:
            return
        
        MeterReadingAlert.objects.create(
            asset_id=asset_id,
            alert_type=detection_type,
            severity=severity,
            message=message,
            metadata=details
        )
        
        logger.warning(
            f"{detection_type.lower()}_alert_created",
            extra={
                'asset_id': asset_id,
                'details': details
            }
        )
```

**Integration**: Add to meter reading processing

```python
# In apps/activity/services/meter_reading_service.py
# Add to process_meter_reading method

from apps.activity.services.theft_leak_detection_service import TheftLeakDetectionService

def process_meter_reading(reading_id):
    reading = MeterReading.objects.get(id=reading_id)
    
    # Get previous reading
    previous = MeterReading.objects.filter(
        asset_id=reading.asset_id,
        timestamp__lt=reading.timestamp
    ).order_by('-timestamp').first()
    
    if previous:
        # Check for sudden drop (theft)
        theft_check = TheftLeakDetectionService.detect_sudden_drop(
            asset_id=reading.asset_id,
            current_reading=float(reading.reading_value),
            previous_reading=float(previous.reading_value)
        )
        
        if theft_check['is_theft']:
            TheftLeakDetectionService.create_theft_leak_alert(
                asset_id=reading.asset_id,
                detection_type='THEFT',
                details=theft_check
            )
```

---

## Feature 3: Cost Optimization Intelligence ⭐⭐⭐⭐⭐

### Business Problem
**Facilities run high-power equipment during peak hours → 2-3x electricity cost**

### Solution

**File**: `apps/activity/services/cost_optimization_service.py`

```python
"""
Cost Optimization Service.

Analyzes utility costs and provides optimization recommendations:
- Peak vs off-peak usage analysis
- Budget tracking and variance alerts
- Cost-saving opportunities
- Executive dashboards

Following CLAUDE.md standards.
"""

import logging
from datetime import timedelta, time
from typing import Dict, List
import statistics
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from apps.activity.models import MeterReading, Asset

logger = logging.getLogger(__name__)


class CostOptimizationService:
    """Optimize utility costs through intelligent analytics."""

    # Peak hours definition (can be configured per site/region)
    PEAK_HOURS_START = time(9, 0)  # 9 AM
    PEAK_HOURS_END = time(21, 0)   # 9 PM
    
    # Cost multipliers (typical)
    PEAK_MULTIPLIER = 2.5
    OFF_PEAK_MULTIPLIER = 1.0

    @classmethod
    def analyze_peak_usage(
        cls,
        asset_id: int,
        period_days: int = 30
    ) -> Dict:
        """
        Analyze peak vs off-peak consumption.
        
        Returns:
            {
                'peak_consumption': float,
                'off_peak_consumption': float,
                'peak_percentage': float,
                'potential_savings': float,
                'recommendations': List[str]
            }
        """
        cutoff = timezone.now() - timedelta(days=period_days)
        
        readings = MeterReading.objects.filter(
            asset_id=asset_id,
            timestamp__gte=cutoff,
            consumption__isnull=False
        )
        
        peak_consumption = 0
        off_peak_consumption = 0
        
        for reading in readings:
            reading_time = reading.timestamp.time()
            consumption = float(reading.consumption) if reading.consumption else 0
            
            if cls.PEAK_HOURS_START <= reading_time <= cls.PEAK_HOURS_END:
                peak_consumption += consumption
            else:
                off_peak_consumption += consumption
        
        total_consumption = peak_consumption + off_peak_consumption
        peak_percentage = (peak_consumption / total_consumption * 100) if total_consumption > 0 else 0
        
        # Get unit cost
        asset = Asset.objects.get(id=asset_id)
        unit_cost = asset.other_data.get('unit_cost', 0) if asset.other_data else 0
        
        # Calculate potential savings if shifted to off-peak
        current_cost = (
            peak_consumption * unit_cost * cls.PEAK_MULTIPLIER +
            off_peak_consumption * unit_cost * cls.OFF_PEAK_MULTIPLIER
        )
        
        # If 50% of peak usage shifted to off-peak
        optimized_peak = peak_consumption * 0.5
        optimized_off_peak = off_peak_consumption + (peak_consumption * 0.5)
        
        optimized_cost = (
            optimized_peak * unit_cost * cls.PEAK_MULTIPLIER +
            optimized_off_peak * unit_cost * cls.OFF_PEAK_MULTIPLIER
        )
        
        potential_savings = current_cost - optimized_cost
        
        # Generate recommendations
        recommendations = []
        
        if peak_percentage > 60:
            recommendations.append(
                f"High peak usage ({peak_percentage:.1f}%). Consider scheduling non-essential operations during off-peak hours (9PM-9AM)."
            )
        
        if potential_savings > 1000:  # $1000/month potential
            recommendations.append(
                f"Potential savings: ${potential_savings:.2f}/month by shifting 50% of peak usage to off-peak hours."
            )
        
        if peak_percentage > 70:
            recommendations.append(
                "Consider installing timer switches for non-critical equipment to auto-shift to off-peak."
            )
        
        result = {
            'peak_consumption': round(peak_consumption, 2),
            'off_peak_consumption': round(off_peak_consumption, 2),
            'peak_percentage': round(peak_percentage, 2),
            'current_monthly_cost': round(current_cost, 2),
            'optimized_monthly_cost': round(optimized_cost, 2),
            'potential_monthly_savings': round(potential_savings, 2),
            'annual_savings_potential': round(potential_savings * 12, 2),
            'recommendations': recommendations
        }
        
        logger.info(
            "cost_optimization_analyzed",
            extra={
                'asset_id': asset_id,
                'potential_savings': potential_savings
            }
        )
        
        return result

    @classmethod
    def generate_cost_dashboard(
        cls,
        tenant_id: int,
        site_id: int = None,
        period_days: int = 30
    ) -> Dict:
        """
        Generate executive cost dashboard data.
        
        CFO-ready utility cost breakdown and trends.
        """
        cutoff = timezone.now() - timedelta(days=period_days)
        
        # Filter assets
        assets_filter = {'tenant_id': tenant_id}
        if site_id:
            assets_filter['location_id'] = site_id
        
        assets = Asset.objects.filter(
            **assets_filter,
            meter_type__in=['ELECTRICITY', 'WATER', 'DIESEL', 'GAS']
        )
        
        total_cost = 0
        cost_by_type = {}
        
        for asset in assets:
            readings = MeterReading.objects.filter(
                asset_id=asset.id,
                timestamp__gte=cutoff,
                cost_estimate__isnull=False
            )
            
            asset_cost = sum(
                float(r.cost_estimate) for r in readings 
                if r.cost_estimate
            )
            
            total_cost += asset_cost
            
            meter_type = asset.meter_type
            cost_by_type[meter_type] = cost_by_type.get(meter_type, 0) + asset_cost
        
        # Calculate trend (compare to previous period)
        previous_period_start = cutoff - timedelta(days=period_days)
        
        previous_readings = MeterReading.objects.filter(
            asset__in=assets,
            timestamp__gte=previous_period_start,
            timestamp__lt=cutoff,
            cost_estimate__isnull=False
        )
        
        previous_cost = sum(
            float(r.cost_estimate) for r in previous_readings 
            if r.cost_estimate
        )
        
        cost_change = total_cost - previous_cost
        cost_change_percentage = (cost_change / previous_cost * 100) if previous_cost > 0 else 0
        
        dashboard = {
            'period_days': period_days,
            'total_cost': round(total_cost, 2),
            'previous_period_cost': round(previous_cost, 2),
            'cost_change': round(cost_change, 2),
            'cost_change_percentage': round(cost_change_percentage, 2),
            'trend': 'INCREASING' if cost_change > 0 else 'DECREASING',
            'cost_breakdown': {
                meter_type: round(cost, 2) 
                for meter_type, cost in cost_by_type.items()
            },
            'top_consumers': cls._get_top_consumers(tenant_id, cutoff, limit=5),
            'optimization_opportunities': cls._get_optimization_opportunities(tenant_id)
        }
        
        return dashboard

    @classmethod
    def _get_top_consumers(cls, tenant_id: int, cutoff: datetime, limit: int = 5) -> List[Dict]:
        """Get top consuming assets."""
        assets = Asset.objects.filter(tenant_id=tenant_id)
        
        consumption_data = []
        
        for asset in assets:
            readings = MeterReading.objects.filter(
                asset_id=asset.id,
                timestamp__gte=cutoff,
                cost_estimate__isnull=False
            )
            
            total_cost = sum(
                float(r.cost_estimate) for r in readings 
                if r.cost_estimate
            )
            
            if total_cost > 0:
                consumption_data.append({
                    'asset_name': asset.name,
                    'asset_id': asset.id,
                    'meter_type': asset.meter_type,
                    'total_cost': round(total_cost, 2)
                })
        
        # Sort by cost descending
        consumption_data.sort(key=lambda x: x['total_cost'], reverse=True)
        
        return consumption_data[:limit]

    @classmethod
    def _get_optimization_opportunities(cls, tenant_id: int) -> List[Dict]:
        """Identify cost-saving opportunities."""
        opportunities = []
        
        # Check all electricity meters for peak usage
        electricity_assets = Asset.objects.filter(
            tenant_id=tenant_id,
            meter_type='ELECTRICITY'
        )
        
        for asset in electricity_assets:
            peak_analysis = cls.analyze_peak_usage(asset.id, period_days=30)
            
            if peak_analysis['potential_monthly_savings'] > 500:  # $500+/month opportunity
                opportunities.append({
                    'asset_name': asset.name,
                    'opportunity_type': 'PEAK_SHIFT',
                    'potential_monthly_savings': peak_analysis['potential_monthly_savings'],
                    'annual_savings': peak_analysis['annual_savings_potential'],
                    'recommendation': peak_analysis['recommendations'][0] if peak_analysis['recommendations'] else ''
                })
        
        # Sort by savings potential
        opportunities.sort(key=lambda x: x['potential_monthly_savings'], reverse=True)
        
        return opportunities[:10]  # Top 10 opportunities
```

**Executive Dashboard Template**: `apps/reports/report_designs/utility_cost_executive_dashboard.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>Utility Cost Executive Dashboard</title>
    <style>
        /* Similar styling to DAR template */
        .cost-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
        .cost-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white; }
        .breakdown-chart { margin: 20px 0; }
        .opportunity { background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>💰 Utility Cost Executive Dashboard</h1>
    <p>Period: {{ period_days }} days | Generated: {{ generated_at }}</p>
    
    <!-- Summary Cards -->
    <div class="cost-summary">
        <div class="cost-card">
            <h3>Total Cost</h3>
            <div class="value">${{ total_cost|floatformat:2 }}</div>
        </div>
        <div class="cost-card {% if cost_change > 0 %}warning{% else %}success{% endif %}">
            <h3>Change vs Previous Period</h3>
            <div class="value">{{ cost_change_percentage|floatformat:1 }}%</div>
            <div>{{ trend }}</div>
        </div>
        <div class="cost-card">
            <h3>Optimization Potential</h3>
            <div class="value">${{ optimization_total|floatformat:2 }}/mo</div>
        </div>
        <div class="cost-card">
            <h3>Annual Savings Potential</h3>
            <div class="value">${{ optimization_total|multiply:12|floatformat:2 }}</div>
        </div>
    </div>
    
    <!-- Cost Breakdown -->
    <div class="breakdown-section">
        <h2>💡 Cost Breakdown by Utility</h2>
        <table>
            <tr>
                <th>Utility Type</th>
                <th>Cost</th>
                <th>% of Total</th>
            </tr>
            {% for type, cost in cost_breakdown.items %}
            <tr>
                <td>{{ type }}</td>
                <td>${{ cost|floatformat:2 }}</td>
                <td>{{ cost|divide:total_cost|multiply:100|floatformat:1 }}%</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    
    <!-- Top Consumers -->
    <div class="top-consumers-section">
        <h2>📊 Top 5 Cost Drivers</h2>
        <table>
            <tr>
                <th>Asset</th>
                <th>Type</th>
                <th>Cost</th>
            </tr>
            {% for consumer in top_consumers %}
            <tr>
                <td>{{ consumer.asset_name }}</td>
                <td>{{ consumer.meter_type }}</td>
                <td>${{ consumer.total_cost|floatformat:2 }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    
    <!-- Optimization Opportunities -->
    <div class="opportunities-section">
        <h2>💰 Cost-Saving Opportunities</h2>
        {% for opp in optimization_opportunities %}
        <div class="opportunity">
            <h4>{{ opp.asset_name }} - {{ opp.opportunity_type }}</h4>
            <p><strong>Potential Savings:</strong> ${{ opp.potential_monthly_savings|floatformat:2 }}/month (${{ opp.annual_savings|floatformat:2 }}/year)</p>
            <p><strong>Recommendation:</strong> {{ opp.recommendation }}</p>
        </div>
        {% endfor %}
    </div>
</body>
</html>
```

---

## Implementation Priority & Timeline

### Phase 1 (Week 1): Immediate Value
1. ✅ **Tank Forecasting** - Prevent stockouts (2 days)
2. ✅ **Theft/Leak Detection** - Catch pilferage early (2 days)
3. ✅ **Basic Cost Dashboard** - Executive visibility (1 day)

### Phase 2 (Week 2): Advanced Analytics
4. **Peak Usage Optimization** - Cost savings (2 days)
5. **UPS Health Degradation** - Battery replacement prediction (2 days)
6. **Environmental Impact** - Carbon footprint (1 day)

### Phase 3 (Week 3): Benchmarking & Reporting
7. **Site Comparisons** - Best/worst performers (2 days)
8. **Budget Tracking** - Variance alerts (1 day)
9. **Monthly Executive Reports** - Automated delivery (2 days)

---

## Revenue Model

**Premium Feature**: "Utility Intelligence Pack"

**Pricing**: $150-300/month per site

**Value Proposition**:
- "Prevent fuel theft - average $15K/year savings"
- "Optimize electricity costs - save 20-30%"
- "Never run out of diesel again - automated forecasting"
- "Executive dashboards - CFO-ready cost analytics"

**Client ROI**:
- Fuel theft prevention: $15K/year saved
- Electricity optimization: 25% of $50K = $12.5K/year
- Water leak detection: $5K/year saved
- **Total Savings**: $32.5K/year
- **Cost**: $3,600/year ($300/month)
- **ROI**: 9x

---

## Integration Points

### Existing Services to Enhance
```python
# apps/activity/services/meter_reading_service.py
# Add theft/leak detection to processing pipeline

# apps/activity/services/asset_analytics_service.py  
# Add cost optimization analytics

# apps/dashboard/services/command_center_service.py
# Add meter intelligence panel
```

### New Background Tasks
```python
# background_tasks/meter_intelligence_tasks.py
- forecast_all_tanks_task()  # Daily
- detect_theft_leaks_task()  # Hourly
- generate_cost_dashboards_task()  # Weekly
```

### New API Endpoints
```python
# apps/activity/api/meter_intelligence_endpoints.py
GET /api/v1/meters/tank-forecast/{asset_id}/
GET /api/v1/meters/theft-check/{asset_id}/
GET /api/v1/meters/cost-dashboard/{site_id}/
GET /api/v1/meters/optimization-opportunities/{tenant_id}/
```

---

## Success Metrics

### Technical
- Forecast accuracy: >85%
- Theft detection precision: >80%
- Alert false positive rate: <10%

### Business
- Fuel stockouts prevented: 100%
- Theft/leak incidents detected: >90%
- Cost savings realized: 20-30%
- Client satisfaction: >90%

---

**Next Steps**:
1. Review this proposal
2. Prioritize features (recommend Phase 1 first)
3. Implement tank forecasting (highest immediate impact)
4. Deploy to pilot sites
5. Measure savings and iterate

**This transforms YOUTILITY5 from a data collection tool into an intelligent cost-saving platform.**
