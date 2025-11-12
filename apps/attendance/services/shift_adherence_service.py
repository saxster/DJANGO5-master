"""
Shift Adherence Service - Track who's on time, late, or missing.

Compares scheduled shifts against actual attendance records to calculate
adherence metrics and identify staffing issues in real-time.
"""
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from apps.client_onboarding.models import Shift
from apps.attendance.models import PeopleEventlog
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE
import logging

logger = logging.getLogger(__name__)


class ShiftAdherenceService:
    """Check who's on time, late, or missing from scheduled shifts"""
    
    GRACE_PERIOD_MINUTES = 15
    
    @staticmethod
    def calculate_adherence(date, site=None):
        """
        Compare scheduled shifts vs actual attendance for a date.
        
        Returns list of:
        - ✅ On Time (clocked in within 15 min of shift start)
        - ⚠️ Late (clocked in after 15 min grace period)
        - 🔴 No Show (no clock-in at all)
        - 🟠 Early Exit (left before shift end)
        """
        scheduled_shifts = Shift.objects.filter(
            enable=True
        ).select_related('bu', 'client', 'designation')
        
        if site:
            scheduled_shifts = scheduled_shifts.filter(bu=site)
        
        results = []
        
        for shift in scheduled_shifts:
            # Find attendance records for employees assigned to this shift
            # Using PeopleEventlog as main attendance model
            attendance = PeopleEventlog.objects.filter(
                pdate=date,
                post__shift=shift
            ).select_related('people', 'post').order_by('pstarttime')
            
            status = {
                'shift': shift,
                'scheduled_start': shift.starttime,
                'scheduled_end': shift.endtime,
                'actual_start': None,
                'actual_end': None,
                'status': 'UNKNOWN',
                'color': 'gray',
                'icon': '❓',
                'minutes_late': 0,
                'minutes_early_exit': 0,
                'issues': [],
                'attendance_records': []
            }
            
            if not attendance.exists():
                status.update({
                    'status': 'NO_SHOW',
                    'color': 'red',
                    'icon': '🔴',
                    'issues': ['No clock-in records']
                })
            else:
                first_record = attendance.first()
                last_record = attendance.last()
                
                status['attendance_records'] = list(attendance)
                
                if first_record.pstarttime:
                    status['actual_start'] = first_record.pstarttime
                    
                    # Calculate if late
                    scheduled_dt = datetime.combine(date, shift.starttime)
                    actual_dt = datetime.combine(date, first_record.pstarttime)
                    grace_period = timedelta(minutes=ShiftAdherenceService.GRACE_PERIOD_MINUTES)
                    
                    if actual_dt > scheduled_dt + grace_period:
                        minutes_late = int((actual_dt - scheduled_dt).total_seconds() / SECONDS_IN_MINUTE)
                        status.update({
                            'status': 'LATE',
                            'color': 'orange',
                            'icon': '⚠️',
                            'minutes_late': minutes_late,
                            'issues': [f'Arrived {minutes_late} minutes late']
                        })
                    else:
                        status.update({
                            'status': 'ON_TIME',
                            'color': 'green',
                            'icon': '✅'
                        })
                
                if last_record.pendtime:
                    status['actual_end'] = last_record.pendtime
                    
                    # Check for early exit
                    scheduled_end = datetime.combine(date, shift.endtime)
                    actual_end = datetime.combine(date, last_record.pendtime)
                    
                    if actual_end < scheduled_end - timedelta(minutes=ShiftAdherenceService.GRACE_PERIOD_MINUTES):
                        minutes_early = int((scheduled_end - actual_end).total_seconds() / SECONDS_IN_MINUTE)
                        status['minutes_early_exit'] = minutes_early
                        status['issues'].append(f'Left {minutes_early} minutes early')
                        
                        if status['status'] == 'ON_TIME':
                            status.update({
                                'status': 'EARLY_EXIT',
                                'color': 'orange',
                                'icon': '🟠'
                            })
            
            results.append(status)
        
        return results
    
    @staticmethod
    def get_coverage_stats(adherence_results):
        """Calculate coverage percentages"""
        total = len(adherence_results)
        if total == 0:
            return {
                'total_shifts': 0,
                'coverage_pct': 0,
                'on_time_pct': 0,
                'late_pct': 0,
                'absent_pct': 0,
                'on_time_count': 0,
                'late_count': 0,
                'absent_count': 0
            }
        
        on_time = sum(1 for r in adherence_results if r['status'] == 'ON_TIME')
        late = sum(1 for r in adherence_results if r['status'] == 'LATE')
        absent = sum(1 for r in adherence_results if r['status'] == 'NO_SHOW')
        
        return {
            'total_shifts': total,
            'coverage_pct': round((total - absent) / total * 100, 1) if total else 0,
            'on_time_pct': round(on_time / total * 100, 1) if total else 0,
            'late_pct': round(late / total * 100, 1) if total else 0,
            'absent_pct': round(absent / total * 100, 1) if total else 0,
            'on_time_count': on_time,
            'late_count': late,
            'absent_count': absent
        }
    
    @staticmethod
    def auto_create_exceptions(adherence_results):
        """Create alert records for late/absent/early-exit"""
        from apps.attendance.models import AttendanceAlert
        
        created = 0
        for result in adherence_results:
            if result['status'] in ['NO_SHOW', 'LATE', 'EARLY_EXIT']:
                for record in result.get('attendance_records', []):
                    alert, is_created = AttendanceAlert.objects.get_or_create(
                        people=record.people,
                        post=record.post,
                        pdate=record.pdate,
                        alert_type=result['status'],
                        defaults={
                            'severity': 'HIGH' if result['status'] == 'NO_SHOW' else 'MEDIUM',
                            'message': ', '.join(result['issues']),
                            'auto_generated': True,
                            'resolved': False
                        }
                    )
                    if is_created:
                        created += 1
                        logger.info(
                            f"Auto-created alert for {record.people.get_full_name()}: "
                            f"{result['status']}"
                        )
        
        return created
