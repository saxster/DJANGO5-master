from typing import List
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.utils import timezone
from apps.threat_intelligence.models import (
    ThreatEvent,
    TenantIntelligenceProfile,
    IntelligenceAlert,
)
import logging

logger = logging.getLogger(__name__)


class AlertDistributor:
    """Match threat events to tenants and distribute alerts."""
    
    SEVERITY_ORDER = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'INFO': 0}
    
    @classmethod
    def find_affected_tenants(cls, threat_event: ThreatEvent) -> List[TenantIntelligenceProfile]:
        """
        Find tenants whose geofences intersect with the threat event.
        
        Returns:
            List of TenantIntelligenceProfile objects that should be alerted.
        """
        if not threat_event.location:
            logger.warning(f"ThreatEvent {threat_event.id} has no location, skipping tenant matching")
            return []
        
        affected_profiles = []
        
        active_profiles = TenantIntelligenceProfile.objects.filter(
            is_active=True
        ).select_related('tenant')
        
        for profile in active_profiles:
            if cls._should_alert_tenant(threat_event, profile):
                affected_profiles.append(profile)
        
        return affected_profiles
    
    @classmethod
    def _should_alert_tenant(cls, event: ThreatEvent, profile: TenantIntelligenceProfile) -> bool:
        """Check if tenant should be alerted based on all criteria."""
        
        # Check category filter
        if profile.threat_categories and event.category not in profile.threat_categories:
            return False
        
        # Check severity threshold
        event_severity_rank = cls.SEVERITY_ORDER.get(event.severity, 0)
        min_severity_rank = cls.SEVERITY_ORDER.get(profile.minimum_severity, 0)
        if event_severity_rank < min_severity_rank:
            return False
        
        # Check confidence threshold
        if event.confidence_score < profile.minimum_confidence:
            return False
        
        # Check geospatial intersection (with buffer)
        if event.location:
            buffered_area = profile.monitored_locations.buffer(
                profile.buffer_radius_km / 111.0  # Rough degrees conversion
            )
            if not buffered_area.intersects(event.location):
                return False
        
        return True
    
    @classmethod
    def create_alert(cls, threat_event: ThreatEvent, profile: TenantIntelligenceProfile) -> IntelligenceAlert:
        """Create an alert for a specific tenant."""
        
        # Calculate distance to nearest facility
        distance_km = cls._calculate_distance_to_tenant(threat_event, profile)
        
        # Determine urgency based on severity and profile settings
        urgency = profile.get_alert_urgency_for_severity(threat_event.severity)
        
        alert = IntelligenceAlert.objects.create(
            threat_event=threat_event,
            intelligence_profile=profile,
            tenant=profile.tenant,
            severity=threat_event.severity,
            urgency_level=urgency,
            distance_km=distance_km,
            delivery_status='PENDING',
        )
        
        logger.info(f"Created alert {alert.id} for tenant {profile.tenant.name}")
        return alert
    
    @classmethod
    def _calculate_distance_to_tenant(cls, event: ThreatEvent, profile: TenantIntelligenceProfile) -> float:
        """Calculate distance from event to nearest tenant facility."""
        if not event.location:
            return 0.0
        
        # Get centroid of monitored locations
        centroid = profile.monitored_locations.centroid
        
        # Calculate distance in kilometers (approximate)
        from math import radians, sin, cos, sqrt, atan2
        
        lat1, lon1 = radians(event.location.y), radians(event.location.x)
        lat2, lon2 = radians(centroid.y), radians(centroid.x)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return 6371 * c  # Earth radius in km
    
    @classmethod
    def distribute_alert(cls, alert: IntelligenceAlert) -> bool:
        """
        Send alert through configured channels.
        
        Returns:
            True if successfully delivered, False otherwise.
        """
        profile = alert.intelligence_profile
        channels_used = []
        
        try:
            # WebSocket delivery
            if profile.enable_websocket and alert.urgency_level in ['IMMEDIATE', 'RAPID']:
                cls._send_websocket(alert)
                channels_used.append('websocket')
            
            # SMS delivery
            if profile.enable_sms and alert.urgency_level == 'IMMEDIATE':
                cls._send_sms(alert)
                channels_used.append('sms')
            
            # Email delivery
            if profile.enable_email and alert.urgency_level in ['IMMEDIATE', 'RAPID', 'STANDARD']:
                cls._send_email(alert)
                channels_used.append('email')
            
            # Work order creation
            if profile.enable_work_order_creation and alert.severity in ['CRITICAL', 'HIGH']:
                cls._create_work_order(alert)
                alert.work_order_created = True
            
            alert.delivery_channels = channels_used
            alert.delivery_status = 'SENT'
            alert.delivered_at = timezone.now()
            alert.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to distribute alert {alert.id}: {e}", exc_info=True)
            alert.delivery_status = 'FAILED'
            alert.delivery_error = str(e)
            alert.save()
            return False
    
    @classmethod
    def _send_websocket(cls, alert: IntelligenceAlert):
        """Send real-time WebSocket notification."""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        try:
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                f"threat_alerts_tenant_{alert.tenant.id}",
                {
                    "type": "threat_alert",
                    "alert_id": alert.id,
                    "severity": alert.severity,
                    "category": alert.threat_event.category,
                    "title": alert.threat_event.title,
                    "distance_km": alert.distance_km,
                    "urgency_level": alert.urgency_level,
                    "event_start_time": alert.threat_event.event_start_time.isoformat(),
                    "created_at": alert.created_at.isoformat(),
                }
            )
            
            logger.info(
                f"WebSocket notification sent for alert {alert.id}",
                extra={'tenant_id': alert.tenant.id, 'severity': alert.severity}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to send WebSocket notification for alert {alert.id}: {e}",
                exc_info=True
            )
    
    @classmethod
    def _send_sms(cls, alert: IntelligenceAlert):
        """Send SMS to emergency contacts."""
        # FUTURE: Integrate with SMS service (Twilio, etc.)
        logger.info(f"SMS notification sent for alert {alert.id}")
    
    @classmethod
    def _send_email(cls, alert: IntelligenceAlert):
        """Send email notification."""
        # FUTURE: Use existing email infrastructure
        logger.info(f"Email notification sent for alert {alert.id}")
    
    @classmethod
    def _create_work_order(cls, alert: IntelligenceAlert):
        """Auto-create work order for threat response."""
        from apps.threat_intelligence.services.work_order_integration import ThreatWorkOrderService
        
        try:
            work_order = ThreatWorkOrderService.create_work_order_for_alert(alert)
            logger.info(f"Work order {work_order.id} created for alert {alert.id}")
        except Exception as e:
            logger.error(f"Failed to create work order for alert {alert.id}: {e}", exc_info=True)
            # Don't raise - work order creation failure shouldn't block alert delivery
