"""
Shift Compliance Tasks.

Zero no-show enforcement and shift validation.
Part of HIGH_IMPACT_FEATURE_OPPORTUNITIES.md implementation.

Revenue Impact: +$100-200/month per site
ROI: Prevent 5 no-shows/month = $1,000-2,500 saved

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #15: No blocking I/O

@ontology(
    domain="noc",
    purpose="Enforce shift compliance and detect no-shows",
    business_value="Zero no-shows, 100% shift compliance",
    criticality="high",
    tags=["shift-compliance", "attendance", "no-show-detection", "celery"]
)
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import DatabaseError
from datetime import timedelta
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS

logger = logging.getLogger('shift_compliance')

__all__ = ['rebuild_shift_schedule_cache_task', 'detect_shift_no_shows_task']


@shared_task(
    name='apps.noc.rebuild_shift_schedule_cache',
    bind=True,
    max_retries=2,
    time_limit=600
)
def rebuild_shift_schedule_cache_task(self):
    """
    Rebuild shift schedule cache for next 14 days.
    
    Runs daily at 2 AM via Celery beat.
    
    Returns:
        Dict with cache build statistics
    """
    from apps.noc.security_intelligence.services.shift_compliance_service import ShiftComplianceService
    from apps.noc.security_intelligence.models import SecurityAnomalyConfig
    from apps.tenants.models import Tenant
    
    try:
        total_cache_entries = 0
        tenants_processed = 0
        
        # Get all active tenants
        tenants = Tenant.objects.filter(is_active=True)
        
        start_date = timezone.now()
        end_date = start_date + timedelta(days=14)  # 14 days ahead
        
        logger.info(f"Rebuilding shift cache for {tenants.count()} tenants")
        
        for tenant in tenants:
            try:
                # Get or create config for tenant
                config, _ = SecurityAnomalyConfig.objects.get_or_create(
                    tenant=tenant,
                    defaults={'is_active': True}
                )
                
                # Create service instance
                service = ShiftComplianceService(config)
                
                # Build cache
                count = service.build_schedule_cache(tenant, start_date, end_date)
                total_cache_entries += count
                tenants_processed += 1
                
                logger.info(
                    f"Built {count} cache entries for tenant {tenant.name}",
                    extra={'tenant_id': tenant.id, 'cache_entries': count}
                )

            except DATABASE_EXCEPTIONS as e:
                logger.error(
                    f"Database error building cache for tenant {tenant.id}: {e}",
                    exc_info=True
                )
                continue
            except (ValueError, TypeError, KeyError, AttributeError) as e:
                logger.error(
                    f"Error building cache for tenant {tenant.id}: {e}",
                    exc_info=True
                )
                continue
        
        result = {
            'tenants_processed': tenants_processed,
            'total_cache_entries': total_cache_entries,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(
            f"Shift cache rebuild complete",
            extra=result
        )
        
        return result

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error rebuilding shift cache: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=300)


@shared_task(
    name='apps.noc.detect_shift_no_shows',
    bind=True,
    max_retries=3,
    time_limit=300
)
def detect_shift_no_shows_task(self):
    """
    Detect no-shows and late arrivals for current shifts.
    
    Runs every 30 minutes via Celery beat.
    
    Returns:
        Dict with no-show and anomaly counts
    """
    from apps.noc.security_intelligence.models import ShiftScheduleCache
    from apps.attendance.models import Attendance
    from apps.noc.models import NOCAlertEvent
    
    try:
        now = timezone.now()
        today = now.date()
        
        no_shows_detected = 0
        late_arrivals = 0
        wrong_site_incidents = 0
        
        # Get shifts that should have started in last 2 hours but have no attendance
        two_hours_ago = now - timedelta(hours=2)
        
        scheduled_shifts = ShiftScheduleCache.objects.filter(
            shift_date=today,
            scheduled_start__lte=now,
            scheduled_start__gte=two_hours_ago,
            cache_valid_until__gt=now
        ).select_related('person', 'site', 'tenant')
        
        logger.info(f"Checking {scheduled_shifts.count()} shifts for compliance")
        
        for shift in scheduled_shifts:
            try:
                # Check if person has punched in
                attendance = Attendance.objects.filter(
                    people=shift.person,
                    punchin__date=today,
                    bu=shift.site
                ).first()
                
                if not attendance:
                    # NO SHOW DETECTED
                    no_shows_detected += 1
                    
                    # Create critical alert
                    NOCAlertEvent.objects.create(
                        tenant=shift.tenant,
                        bu=shift.site,
                        alert_type='NO_SHOW_DETECTED',
                        severity='HIGH',
                        title=f"No-Show: {shift.person.get_full_name()}",
                        description=f"Guard {shift.person.get_full_name()} scheduled for "
                                   f"{shift.site.name} at {shift.scheduled_start.strftime('%H:%M')} "
                                   f"has not checked in. Immediate replacement needed.",
                        source='SHIFT_COMPLIANCE_MONITOR',
                        status='NEW',
                        other_data={
                            'person_id': shift.person.id,
                            'site_id': shift.site.id,
                            'scheduled_start': shift.scheduled_start.isoformat(),
                            'anomaly_type': 'NO_SHOW'
                        }
                    )
                    
                    logger.warning(
                        f"No-show detected: {shift.person.get_full_name()} at {shift.site.name}",
                        extra={
                            'person_id': shift.person.id,
                            'site_id': shift.site.id,
                            'scheduled_start': shift.scheduled_start
                        }
                    )
                
                else:
                    # Check for late arrival
                    time_diff_minutes = (attendance.punchin - shift.scheduled_start).total_seconds() / 60
                    
                    if time_diff_minutes > 15:  # More than 15 minutes late
                        late_arrivals += 1
                        
                        NOCAlertEvent.objects.create(
                            tenant=shift.tenant,
                            bu=shift.site,
                            alert_type='LATE_ARRIVAL',
                            severity='MEDIUM',
                            title=f"Late Arrival: {shift.person.get_full_name()}",
                            description=f"Guard {shift.person.get_full_name()} arrived "
                                       f"{int(time_diff_minutes)} minutes late at {shift.site.name}.",
                            source='SHIFT_COMPLIANCE_MONITOR',
                            status='NEW',
                            other_data={
                                'person_id': shift.person.id,
                                'site_id': shift.site.id,
                                'minutes_late': int(time_diff_minutes),
                                'anomaly_type': 'LATE'
                            }
                        )
                    
                    # Check if attendance is at wrong site
                    attendances_today = Attendance.objects.filter(
                        people=shift.person,
                        punchin__date=today
                    ).exclude(bu=shift.site)
                    
                    if attendances_today.exists():
                        wrong_site_incidents += 1
                        
                        wrong_attendance = attendances_today.first()
                        NOCAlertEvent.objects.create(
                            tenant=shift.tenant,
                            bu=shift.site,
                            alert_type='WRONG_SITE',
                            severity='HIGH',
                            title=f"Wrong Site: {shift.person.get_full_name()}",
                            description=f"Guard {shift.person.get_full_name()} checked in at "
                                       f"{wrong_attendance.bu.name} but scheduled for {shift.site.name}.",
                            source='SHIFT_COMPLIANCE_MONITOR',
                            status='NEW',
                            other_data={
                                'person_id': shift.person.id,
                                'expected_site_id': shift.site.id,
                                'actual_site_id': wrong_attendance.bu.id,
                                'anomaly_type': 'WRONG_SITE'
                            }
                        )

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error checking shift {shift.id}: {e}", exc_info=True)
                continue
            except (ValueError, TypeError, KeyError, AttributeError) as e:
                logger.error(f"Error checking shift {shift.id}: {e}", exc_info=True)
                continue
        
        result = {
            'shifts_checked': scheduled_shifts.count(),
            'no_shows_detected': no_shows_detected,
            'late_arrivals': late_arrivals,
            'wrong_site_incidents': wrong_site_incidents,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(
            f"Shift compliance check complete",
            extra=result
        )
        
        return result

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error detecting no-shows: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120)
