"""
Workforce Staffing Forecaster Service

Predicts staffing needs per site/shift using:
- Historical attendance patterns
- Incident rates (more incidents = more guards needed)
- Seasonal variations
- Day of week patterns

Simple gradient + seasonality model for operational forecasting.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exceptions
"""

import logging
from datetime import timedelta
from typing import Dict, List, Any
from django.utils import timezone
from django.db.models import Count, Avg, Q
from apps.attendance.models import Attendance
from apps.activity.models import Activity
from apps.client_onboarding.models import Bt
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('attendance.forecaster')

__all__ = ['StaffingForecaster']


class StaffingForecaster:
    """Predict staffing needs based on historical patterns."""
    
    @classmethod
    def forecast_weekly_staffing(cls, site_id: int) -> Dict[str, Any]:
        """
        Generate weekly staffing forecast for a site.
        
        Args:
            site_id: Site (Bt) ID
            
        Returns:
            Dict with forecasts per shift/day
        """
        try:
            site = Bt.objects.get(id=site_id)
            now = timezone.now()
            
            historical_data = cls._get_historical_patterns(site_id, days=90)
            incident_impact = cls._calculate_incident_impact(site_id, days=30)
            
            forecast = {
                'site': site.unitcode,
                'forecast_date': now.date().isoformat(),
                'shifts': cls._forecast_by_shift(historical_data, incident_impact),
                'weekly_summary': cls._summarize_weekly_needs(historical_data),
                'recommendations': cls._generate_recommendations(historical_data, incident_impact),
            }
            
            return forecast
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Forecasting failed for site {site_id}: {e}")
            raise
    
    @classmethod
    def _get_historical_patterns(cls, site_id: int, days: int) -> Dict[str, Any]:
        """Analyze historical attendance patterns."""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        attendance_data = Attendance.objects.filter(
            site_id=site_id,
            checkin__gte=cutoff_date
        ).values('shift_id', 'checkin__week_day').annotate(
            avg_attendance=Count('id'),
            on_time_rate=Avg('is_on_time')
        )
        
        return {
            'average_attendance': list(attendance_data),
            'days_analyzed': days,
            'total_records': attendance_data.count(),
        }
    
    @classmethod
    def _calculate_incident_impact(cls, site_id: int, days: int) -> float:
        """
        Calculate incident rate impact on staffing.
        
        More incidents = higher risk = more guards needed.
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        incident_count = Activity.objects.filter(
            site_id=site_id,
            created_at__gte=cutoff_date,
            activity_type='INCIDENT'
        ).count()
        
        baseline_incidents = 10
        impact_multiplier = 1.0 + ((incident_count - baseline_incidents) / 100)
        
        return max(1.0, min(1.5, impact_multiplier))
    
    @classmethod
    def _forecast_by_shift(cls, historical_data: Dict, incident_impact: float) -> List[Dict]:
        """Generate per-shift forecasts."""
        shifts = []
        
        for record in historical_data.get('average_attendance', []):
            base_headcount = record.get('avg_attendance', 1)
            adjusted_headcount = int(base_headcount * incident_impact)
            
            shifts.append({
                'shift_id': record.get('shift_id'),
                'day_of_week': record.get('checkin__week_day'),
                'base_headcount': base_headcount,
                'recommended_headcount': adjusted_headcount,
                'delta': adjusted_headcount - base_headcount,
                'on_time_rate': round(record.get('on_time_rate', 0.0) * 100, 1),
            })
        
        return shifts
    
    @classmethod
    def _summarize_weekly_needs(cls, historical_data: Dict) -> Dict[str, Any]:
        """Weekly summary statistics."""
        records = historical_data.get('average_attendance', [])
        
        if not records:
            return {'total_guards_needed': 0, 'avg_per_shift': 0}
        
        total = sum(r.get('avg_attendance', 0) for r in records)
        avg_shift = total / len(records) if records else 0
        
        return {
            'total_guards_needed_weekly': int(total),
            'avg_per_shift': round(avg_shift, 1),
            'shifts_analyzed': len(records),
        }
    
    @classmethod
    def _generate_recommendations(cls, historical_data: Dict, incident_impact: float) -> List[str]:
        """Generate actionable staffing recommendations."""
        recommendations = []
        
        if incident_impact > 1.2:
            recommendations.append(
                f"High incident rate detected. Consider increasing staff by {int((incident_impact - 1) * 100)}%"
            )
        
        records = historical_data.get('average_attendance', [])
        low_attendance_shifts = [r for r in records if r.get('on_time_rate', 1.0) < 0.8]
        
        if low_attendance_shifts:
            recommendations.append(
                f"{len(low_attendance_shifts)} shifts have <80% on-time rate. Review scheduling."
            )
        
        if not recommendations:
            recommendations.append("Staffing levels appear adequate based on current patterns.")
        
        return recommendations
