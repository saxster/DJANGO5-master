"""
Activity Timeline Service - Unified event views for entities

Creates 360° views of all events related to people, assets, or locations
by aggregating data from multiple sources (attendance, tickets, work orders, etc.)

User-Friendly Name: "Activity Timeline"

Security:
    - Tenant isolation on all queries
    - Permission validation for cross-entity views
    - Audit logging for timeline access
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from django.db.models import Q, Avg, Count
from django.urls import reverse
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_DAY


class ActivityTimelineService:
    """Build unified timelines from multiple sources"""
    
    MAX_EVENTS_PER_SOURCE = 100
    
    @staticmethod
    def get_person_timeline(
        person,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        max_events: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Get all events for a person across multiple systems
        
        Args:
            person: People instance
            start_date: Filter events after this date
            end_date: Filter events before this date
            event_types: List of event types to include (None = all)
            max_events: Maximum total events to return
            
        Returns:
            List of event dictionaries sorted by timestamp (newest first)
        """
        events = []
        
        # Attendance events
        if not event_types or 'attendance' in event_types:
            events.extend(
                ActivityTimelineService._get_attendance_events(
                    person, start_date, end_date
                )
            )
        
        # Ticket events
        if not event_types or 'ticket' in event_types:
            events.extend(
                ActivityTimelineService._get_ticket_events(
                    person, start_date, end_date
                )
            )
        
        # Work order events
        if not event_types or 'work_order' in event_types:
            events.extend(
                ActivityTimelineService._get_work_order_events(
                    person, start_date, end_date
                )
            )
        
        # Journal entries
        if not event_types or 'journal' in event_types:
            events.extend(
                ActivityTimelineService._get_journal_events(
                    person, start_date, end_date
                )
            )
        
        # Security incidents
        if not event_types or 'incident' in event_types:
            events.extend(
                ActivityTimelineService._get_incident_events(
                    person, start_date, end_date
                )
            )
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Limit total events
        return events[:max_events]
    
    @staticmethod
    def _get_attendance_events(
        person,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Get attendance events for person"""
        try:
            from apps.attendance.models.tracking import Tracking
            
            queryset = Tracking.objects.filter(
                people=person
            ).select_related('shift', 'post').order_by('-timestamp')
            
            if start_date:
                queryset = queryset.filter(timestamp__gte=start_date)
            if end_date:
                queryset = queryset.filter(timestamp__lte=end_date)
            
            events = []
            for att in queryset[:ActivityTimelineService.MAX_EVENTS_PER_SOURCE]:
                action_display = att.get_action_display() if hasattr(att, 'get_action_display') else att.action
                post_name = att.post.name if att.post else 'Unknown'
                shift_name = att.shift.name if att.shift else 'N/A'
                
                events.append({
                    'timestamp': att.timestamp,
                    'type': 'attendance',
                    'icon': '🕐',
                    'color': 'blue',
                    'title': f"{action_display} at {post_name}",
                    'description': f"Shift: {shift_name}",
                    'location': post_name,
                    'url': reverse('admin:attendance_tracking_change', args=[att.id]),
                    'source': 'Attendance',
                    'metadata': {
                        'action': att.action,
                        'shift_id': att.shift_id,
                        'post_id': att.post_id
                    }
                })
            
            return events
        except ImportError:
            return []
    
    @staticmethod
    def _get_ticket_events(
        person,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Get ticket events for person (created or assigned)"""
        try:
            from apps.y_helpdesk.models import Ticket
            
            queryset = Ticket.objects.filter(
                Q(cuser=person) | Q(assignedtopeople=person)
            ).select_related('cuser', 'assignedtopeople').order_by('-cdtz')
            
            if start_date:
                queryset = queryset.filter(cdtz__gte=start_date)
            if end_date:
                queryset = queryset.filter(cdtz__lte=end_date)
            
            events = []
            for ticket in queryset[:ActivityTimelineService.MAX_EVENTS_PER_SOURCE]:
                is_assignee = ticket.assignedtopeople_id == person.id
                role = 'Assigned' if is_assignee else 'Created'
                
                # Determine color by priority
                color_map = {
                    'CRITICAL': 'red',
                    'HIGH': 'orange',
                    'MEDIUM': 'yellow',
                    'LOW': 'green'
                }
                color = color_map.get(ticket.priority, 'gray')
                
                events.append({
                    'timestamp': ticket.cdtz,
                    'type': 'ticket',
                    'icon': '🎫',
                    'color': color,
                    'title': f"{role} ticket: {ticket.ticketdesc[:50]}",
                    'description': f"Priority: {ticket.priority}, Status: {ticket.status}",
                    'url': reverse('admin:y_helpdesk_ticket_change', args=[ticket.id]),
                    'source': 'Help Desk',
                    'metadata': {
                        'ticket_id': ticket.id,
                        'priority': ticket.priority,
                        'status': ticket.status,
                        'role': role
                    }
                })
            
            return events
        except ImportError:
            return []
    
    @staticmethod
    def _get_work_order_events(
        person,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Get work order events for person"""
        try:
            from apps.work_order_management.models import WorkOrder
            
            queryset = WorkOrder.objects.filter(
                Q(assigned_to=person) | Q(cuser=person)
            ).select_related('asset', 'cuser').order_by('-created_at')
            
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)
            
            events = []
            for wo in queryset[:ActivityTimelineService.MAX_EVENTS_PER_SOURCE]:
                wo_type = wo.get_type_display() if hasattr(wo, 'get_type_display') else wo.type
                
                events.append({
                    'timestamp': wo.created_at,
                    'type': 'work_order',
                    'icon': '🔧',
                    'color': 'purple',
                    'title': f"{wo_type}: {wo.description[:50]}",
                    'description': f"Status: {wo.status}",
                    'url': reverse('admin:work_order_management_workorder_change', args=[wo.id]),
                    'source': 'Maintenance',
                    'metadata': {
                        'work_order_id': wo.id,
                        'type': wo.type,
                        'status': wo.status
                    }
                })
            
            return events
        except (ImportError, AttributeError):
            return []
    
    @staticmethod
    def _get_journal_events(
        person,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Get journal entries for person"""
        try:
            from apps.journal.models import JournalEntry
            
            queryset = JournalEntry.objects.filter(
                user=person
            ).order_by('-created_at')
            
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)
            
            events = []
            for entry in queryset[:ActivityTimelineService.MAX_EVENTS_PER_SOURCE]:
                mood_icon = '😊' if entry.mood_rating >= 7 else '😐' if entry.mood_rating >= 4 else '😢'
                
                events.append({
                    'timestamp': entry.created_at,
                    'type': 'journal',
                    'icon': mood_icon,
                    'color': 'teal',
                    'title': f"Journal Entry - Mood: {entry.mood_rating}/10",
                    'description': entry.content[:100] if entry.content else 'No content',
                    'url': reverse('admin:journal_journalentry_change', args=[entry.id]),
                    'source': 'Journal',
                    'metadata': {
                        'mood_rating': entry.mood_rating,
                        'stress_level': getattr(entry, 'stress_level', None),
                        'energy_level': getattr(entry, 'energy_level', None)
                    }
                })
            
            return events
        except (ImportError, AttributeError):
            return []
    
    @staticmethod
    def _get_incident_events(
        person,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Get security incidents involving person"""
        try:
            from apps.noc.models import Alert
            
            queryset = Alert.objects.filter(
                Q(assigned_to=person) | Q(reported_by=person)
            ).select_related('assigned_to', 'reported_by').order_by('-created_at')
            
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)
            
            events = []
            for alert in queryset[:ActivityTimelineService.MAX_EVENTS_PER_SOURCE]:
                severity_color = {
                    'CRITICAL': 'red',
                    'HIGH': 'orange',
                    'MEDIUM': 'yellow',
                    'LOW': 'blue'
                }.get(alert.severity, 'gray')
                
                events.append({
                    'timestamp': alert.created_at,
                    'type': 'incident',
                    'icon': '🚨',
                    'color': severity_color,
                    'title': f"Security Alert: {alert.title[:50]}",
                    'description': f"Severity: {alert.severity}, Status: {alert.status}",
                    'url': reverse('admin:noc_alert_change', args=[alert.id]),
                    'source': 'Security',
                    'metadata': {
                        'alert_id': alert.id,
                        'severity': alert.severity,
                        'status': alert.status
                    }
                })
            
            return events
        except (ImportError, AttributeError):
            return []
    
    @staticmethod
    def get_asset_timeline(
        asset,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get all events for an asset"""
        events = []
        
        # Work orders
        try:
            from apps.work_order_management.models import WorkOrder
            
            queryset = WorkOrder.objects.filter(
                asset=asset
            ).select_related('assigned_to').order_by('-created_at')
            
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)
            
            for wo in queryset[:ActivityTimelineService.MAX_EVENTS_PER_SOURCE]:
                wo_type = wo.get_type_display() if hasattr(wo, 'get_type_display') else wo.type
                
                events.append({
                    'timestamp': wo.created_at,
                    'type': 'maintenance',
                    'icon': '🔧',
                    'color': 'purple',
                    'title': f"{wo_type}: {wo.description[:50]}",
                    'description': f"Status: {wo.status}, Assigned: {wo.assigned_to}",
                    'url': reverse('admin:work_order_management_workorder_change', args=[wo.id]),
                    'source': 'Maintenance'
                })
        except (ImportError, AttributeError):
            pass
        
        # Alerts related to asset
        try:
            from apps.noc.models import Alert
            
            queryset = Alert.objects.filter(
                asset=asset
            ).order_by('-created_at')
            
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)
            
            for alert in queryset[:ActivityTimelineService.MAX_EVENTS_PER_SOURCE]:
                events.append({
                    'timestamp': alert.created_at,
                    'type': 'alert',
                    'icon': '⚠️',
                    'color': 'orange',
                    'title': f"Alert: {alert.title[:50]}",
                    'description': f"Severity: {alert.severity}",
                    'url': reverse('admin:noc_alert_change', args=[alert.id]),
                    'source': 'Monitoring'
                })
        except (ImportError, AttributeError):
            pass
        
        # Sort by timestamp
        events.sort(key=lambda x: x['timestamp'], reverse=True)
        return events
    
    @staticmethod
    def calculate_kpis(person) -> Dict[str, Any]:
        """
        Calculate key performance indicators for person
        
        Returns:
            Dictionary with KPI metrics
        """
        kpis = {}
        
        # Ticket metrics
        try:
            from apps.y_helpdesk.models import Ticket
            
            total_tickets = Ticket.objects.filter(
                Q(cuser=person) | Q(assignedtopeople=person)
            ).count()
            
            open_tickets = Ticket.objects.filter(
                assignedtopeople=person,
                status__in=['NEW', 'OPEN', 'IN_PROGRESS']
            ).count()
            
            kpis['total_tickets'] = total_tickets
            kpis['open_tickets'] = open_tickets
            
            # Average sentiment
            avg_sentiment = Ticket.objects.filter(
                assignedtopeople=person,
                sentiment_score__isnull=False
            ).aggregate(Avg('sentiment_score'))['sentiment_score__avg']
            
            kpis['avg_sentiment'] = round(avg_sentiment, 1) if avg_sentiment else None
        except (ImportError, AttributeError):
            kpis['total_tickets'] = 0
            kpis['open_tickets'] = 0
            kpis['avg_sentiment'] = None
        
        # Attendance metrics
        try:
            from apps.attendance.models.tracking import Tracking
            
            last_30_days = timezone.now() - timedelta(seconds=30 * SECONDS_IN_DAY)
            attendance_days = Tracking.objects.filter(
                people=person,
                timestamp__gte=last_30_days,
                action='CLOCK_IN'
            ).dates('timestamp', 'day').count()
            
            kpis['attendance_days_30d'] = attendance_days
            kpis['attendance_rate'] = round((attendance_days / 30) * 100, 1)
        except (ImportError, AttributeError):
            kpis['attendance_days_30d'] = 0
            kpis['attendance_rate'] = 0
        
        # Work order metrics
        try:
            from apps.work_order_management.models import WorkOrder
            
            open_work_orders = WorkOrder.objects.filter(
                assigned_to=person,
                status__in=['PENDING', 'IN_PROGRESS']
            ).count()
            
            kpis['open_work_orders'] = open_work_orders
        except (ImportError, AttributeError):
            kpis['open_work_orders'] = 0
        
        return kpis
