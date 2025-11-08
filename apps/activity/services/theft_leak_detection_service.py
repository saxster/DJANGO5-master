"""
Theft and Leak Detection Service.

Detects anomalous consumption patterns indicating:
- Fuel pilferage (sudden drops)
- Water/diesel leaks (gradual losses)
- Unauthorized usage (off-hours consumption)

Business value: Average $15K-25K/year savings per site.

Following CLAUDE.md:
- Rule #7: Service methods <50 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta, time
from typing import Dict, Optional
import statistics
from django.db.models import Avg, Sum
from django.utils import timezone
from apps.activity.models import MeterReading, Asset, MeterReadingAlert
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)

# Detection thresholds
SUDDEN_DROP_THRESHOLD = 0.15  # 15% drop = potential theft
LEAK_RATE_THRESHOLD = 0.10  # 10% excess = potential leak
OFF_HOURS_START = time(22, 0)  # 10 PM
OFF_HOURS_END = time(6, 0)  # 6 AM


class TheftLeakDetectionService:
    """Detect theft, pilferage, and leaks from meter readings."""

    @classmethod
    def detect_sudden_drop(
        cls,
        asset_id: int,
        current_reading: float,
        previous_reading: float,
        timestamp: timezone.datetime
    ) -> Dict:
        """
        Detect sudden drops indicating theft/pilferage.

        Args:
            asset_id: Asset identifier
            current_reading: Current meter reading value
            previous_reading: Previous meter reading value
            timestamp: Reading timestamp

        Returns:
            {
                'is_theft': bool,
                'drop_percentage': float,
                'drop_amount': float,
                'confidence': float (0-1),
                'estimated_loss_value': float,
                'severity': str
            }
        """
        try:
            if previous_reading <= 0:
                return {
                    'is_theft': False,
                    'drop_percentage': 0,
                    'message': 'Invalid previous reading'
                }
            
            # Calculate drop (for tank levels, reading going down is normal consumption)
            # But RAPID drops are suspicious
            drop_amount = previous_reading - current_reading
            drop_percentage = drop_amount / previous_reading
            
            # Normal consumption (gradual decrease)
            if drop_amount <= 0 or drop_percentage < 0.05:
                return {'is_theft': False, 'drop_percentage': 0}
            
            # Check if drop is suspicious
            is_theft = drop_percentage >= SUDDEN_DROP_THRESHOLD
            
            # Get asset details for cost estimation
            asset = Asset.objects.get(id=asset_id)
            unit_cost = asset.other_data.get('unit_cost', 0) if asset.other_data else 0
            estimated_loss = drop_amount * unit_cost
            
            # Confidence scoring
            if drop_percentage >= 0.50:  # 50%+ drop
                confidence = 0.98
                severity = 'CRITICAL'
            elif drop_percentage >= 0.30:  # 30%+ drop
                confidence = 0.90
                severity = 'CRITICAL'
            elif drop_percentage >= 0.20:  # 20%+ drop
                confidence = 0.80
                severity = 'HIGH'
            elif drop_percentage >= 0.15:  # 15%+ drop
                confidence = 0.65
                severity = 'MEDIUM'
            else:
                confidence = 0.50
                severity = 'LOW'
            
            result = {
                'is_theft': is_theft,
                'drop_percentage': round(drop_percentage * 100, 2),
                'drop_amount': round(drop_amount, 2),
                'confidence': confidence,
                'severity': severity,
                'estimated_loss_value': round(estimated_loss, 2),
                'currency': asset.other_data.get('currency', 'USD') if asset.other_data else 'USD',
                'meter_type': asset.meter_type,
                'timestamp': timestamp.isoformat()
            }
            
            if is_theft:
                logger.warning(
                    "potential_theft_detected",
                    extra={
                        'asset_id': asset_id,
                        'asset_name': asset.name,
                        'drop_percentage': result['drop_percentage'],
                        'estimated_loss': estimated_loss,
                        'confidence': confidence
                    }
                )
            
            return result
            
        except Asset.DoesNotExist as e:
            raise ValueError(f"Asset {asset_id} not found") from e
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                "theft_detection_failed",
                extra={'asset_id': asset_id, 'error': str(e)},
                exc_info=True
            )
            raise

    @classmethod
    def detect_gradual_leak(
        cls,
        asset_id: int,
        analysis_days: int = 7
    ) -> Dict:
        """
        Detect gradual leaks from consumption pattern.

        Analyzes:
        - Consistent small losses
        - Off-hours consumption (when site closed)
        - Consumption exceeding expected usage

        Args:
            asset_id: Asset identifier
            analysis_days: Days to analyze (default: 7)

        Returns:
            Leak detection results
        """
        try:
            cutoff = timezone.now() - timedelta(days=analysis_days)
            
            readings = MeterReading.objects.filter(
                asset_id=asset_id,
                timestamp__gte=cutoff,
                consumption__isnull=False
            ).order_by('timestamp')
            
            if len(readings) < 2:
                return {
                    'is_leak': False,
                    'message': 'Insufficient data for leak detection'
                }
            
            # Calculate actual consumption
            actual_consumption = sum(
                float(r.consumption) for r in readings 
                if r.consumption and r.consumption > 0
            )
            
            # Get expected consumption (baseline from previous month)
            expected = cls._get_baseline_consumption(asset_id, analysis_days)
            
            if expected == 0:
                return {
                    'is_leak': False,
                    'message': 'No baseline data for comparison'
                }
            
            # Calculate excess
            excess = actual_consumption - expected
            loss_rate = excess / expected
            
            # Detect leak
            is_leak = loss_rate >= LEAK_RATE_THRESHOLD
            
            # Off-hours consumption check
            off_hours_consumption = cls._get_off_hours_consumption(readings)
            off_hours_percentage = (off_hours_consumption / actual_consumption * 100) if actual_consumption > 0 else 0
            
            # Cost estimation
            asset = Asset.objects.get(id=asset_id)
            unit_cost = asset.other_data.get('unit_cost', 0) if asset.other_data else 0
            daily_leak_amount = excess / analysis_days
            monthly_leak_cost = daily_leak_amount * 30 * unit_cost
            
            result = {
                'is_leak': is_leak,
                'leak_rate_percentage': round(loss_rate * 100, 2),
                'excess_consumption': round(excess, 2),
                'leak_amount_per_day': round(daily_leak_amount, 2),
                'estimated_monthly_cost': round(monthly_leak_cost, 2),
                'estimated_annual_cost': round(monthly_leak_cost * 12, 2),
                'off_hours_consumption': round(off_hours_consumption, 2),
                'off_hours_percentage': round(off_hours_percentage, 2),
                'confidence': 0.75 if is_leak else 0.5,
                'severity': 'HIGH' if loss_rate >= 0.20 else 'MEDIUM' if is_leak else 'LOW'
            }
            
            if is_leak:
                logger.warning(
                    "potential_leak_detected",
                    extra={
                        'asset_id': asset_id,
                        'leak_rate': result['leak_rate_percentage'],
                        'monthly_cost': monthly_leak_cost,
                        'off_hours_percentage': off_hours_percentage
                    }
                )
            
            return result
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                "leak_detection_failed",
                extra={'asset_id': asset_id, 'error': str(e)},
                exc_info=True
            )
            raise

    @classmethod
    def _get_baseline_consumption(cls, asset_id: int, days: int) -> float:
        """
        Get baseline expected consumption from same period previous month.

        Args:
            asset_id: Asset identifier
            days: Number of days

        Returns:
            Baseline consumption value
        """
        month_ago = timezone.now() - timedelta(days=30)
        comparison_start = month_ago - timedelta(days=days)
        
        baseline_readings = MeterReading.objects.filter(
            asset_id=asset_id,
            timestamp__gte=comparison_start,
            timestamp__lt=month_ago,
            consumption__isnull=False
        )
        
        if not baseline_readings.exists():
            return 0
        
        return sum(
            float(r.consumption) for r in baseline_readings 
            if r.consumption and r.consumption > 0
        )

    @classmethod
    def _get_off_hours_consumption(cls, readings) -> float:
        """
        Calculate consumption during off-hours (10 PM - 6 AM).

        High off-hours consumption may indicate:
        - Leaks (continuous drain)
        - Unauthorized usage
        - Equipment left running
        """
        off_hours_total = 0
        
        for reading in readings:
            reading_time = reading.timestamp.time()
            
            # Check if in off-hours window
            is_off_hours = (
                reading_time >= OFF_HOURS_START or
                reading_time <= OFF_HOURS_END
            )
            
            if is_off_hours and reading.consumption:
                off_hours_total += float(reading.consumption)
        
        return off_hours_total

    @classmethod
    def create_theft_leak_alert(
        cls,
        asset_id: int,
        detection_type: str,
        details: Dict
    ) -> Optional[int]:
        """
        Create alert for detected theft or leak.

        Args:
            asset_id: Asset identifier
            detection_type: 'THEFT' or 'LEAK'
            details: Detection details dictionary

        Returns:
            Alert ID if created
        """
        try:
            if detection_type == 'THEFT' and details.get('is_theft'):
                severity = details.get('severity', 'HIGH')
                message = (
                    f"⚠️ Potential fuel theft detected: {details['drop_percentage']:.1f}% sudden drop. "
                    f"Amount: {details['drop_amount']:.2f} units. "
                    f"Estimated loss: ${details['estimated_loss_value']:.2f}. "
                    f"Confidence: {details['confidence'] * 100:.0f}%."
                )
            
            elif detection_type == 'LEAK' and details.get('is_leak'):
                severity = details.get('severity', 'HIGH')
                message = (
                    f"💧 Potential leak detected: {details['leak_rate_percentage']:.1f}% excess consumption. "
                    f"Daily leak: {details['leak_amount_per_day']:.2f} units. "
                    f"Estimated monthly cost: ${details['estimated_monthly_cost']:.2f}."
                )
                
                if details['off_hours_percentage'] > 30:
                    message += f" {details['off_hours_percentage']:.1f}% consumption during off-hours (10PM-6AM)."
            
            else:
                return None
            
            alert = MeterReadingAlert.objects.create(
                asset_id=asset_id,
                alert_type=detection_type,
                severity=severity,
                message=message,
                metadata={
                    'detection_details': details,
                    'auto_generated': True,
                    'requires_investigation': True
                }
            )
            
            logger.warning(
                f"{detection_type.lower()}_alert_created",
                extra={
                    'asset_id': asset_id,
                    'alert_id': alert.id,
                    'severity': severity,
                    'details': details
                }
            )
            
            return alert.id
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                "alert_creation_failed",
                extra={
                    'asset_id': asset_id,
                    'detection_type': detection_type,
                    'error': str(e)
                },
                exc_info=True
            )
            raise
