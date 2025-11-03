"""
NOC Module Constants and Capability Definitions.

This module defines NOC-specific capabilities, alert types, and configuration constants
following .claude/rules.md code quality standards.
"""

__all__ = [
    'NOC_CAPABILITIES',
    'ALERT_TYPES',
    'ALERT_SEVERITIES',
    'ALERT_STATUSES',
    'INCIDENT_STATES',
    'DEFAULT_METRIC_WINDOW_MINUTES',
    'DEFAULT_ALERT_THRESHOLDS',
]


NOC_CAPABILITIES = {
    'noc:view': {
        'name': 'View NOC Dashboard',
        'description': 'View NOC dashboard with own scope (assigned sites/clients)',
        'level': 'basic',
    },
    'noc:view_all_clients': {
        'name': 'View All Clients',
        'description': 'View all clients in tenant (admin-level access)',
        'level': 'admin',
    },
    'noc:view_client': {
        'name': 'View Assigned Client',
        'description': 'View specific assigned client only',
        'level': 'basic',
    },
    'noc:view_assigned_sites': {
        'name': 'View Assigned Sites',
        'description': 'View only sites explicitly assigned to user',
        'level': 'basic',
    },
    'noc:ack_alerts': {
        'name': 'Acknowledge Alerts',
        'description': 'Acknowledge and comment on alerts',
        'level': 'operator',
    },
    'noc:escalate': {
        'name': 'Escalate Incidents',
        'description': 'Escalate alerts and incidents to higher level',
        'level': 'operator',
    },
    'noc:configure': {
        'name': 'Configure NOC Settings',
        'description': 'Configure NOC thresholds, alert rules, and settings',
        'level': 'admin',
    },
    'noc:export': {
        'name': 'Export NOC Data',
        'description': 'Export NOC metrics, alerts, and reports',
        'level': 'operator',
    },
    'noc:manage_maintenance': {
        'name': 'Manage Maintenance Windows',
        'description': 'Create and manage maintenance windows for alert suppression',
        'level': 'operator',
    },
    'noc:audit_view': {
        'name': 'View Audit Logs',
        'description': 'View NOC audit logs and compliance reports',
        'level': 'admin',
    },
    'noc:assign_incidents': {
        'name': 'Assign Incidents',
        'description': 'Assign incidents to other users or groups',
        'level': 'operator',
    },
}


ALERT_TYPES = {
    # Predictive Alert Types (Enhancement #5)
    'PREDICTIVE_SLA_BREACH': {
        'code': 'PREDICTIVE_SLA_BREACH',
        'name': 'Predictive SLA Breach',
        'description': 'ML prediction: Ticket/WO likely to breach SLA in next 2 hours',
        'default_severity': 'HIGH',
    },
    'PREDICTIVE_DEVICE_FAILURE': {
        'code': 'PREDICTIVE_DEVICE_FAILURE',
        'name': 'Predictive Device Failure',
        'description': 'ML prediction: Device likely to go offline in next 1 hour',
        'default_severity': 'HIGH',
    },
    'PREDICTIVE_STAFFING_GAP': {
        'code': 'PREDICTIVE_STAFFING_GAP',
        'name': 'Predictive Staffing Gap',
        'description': 'ML prediction: Site likely understaffed in next 4 hours',
        'default_severity': 'MEDIUM',
    },
    # Reactive Alert Types
    'SLA_BREACH': {
        'code': 'SLA_BREACH',
        'name': 'SLA Breach',
        'description': 'Ticket or work order has breached SLA target time',
        'default_severity': 'HIGH',
    },
    'TICKET_ESCALATED': {
        'code': 'TICKET_ESCALATED',
        'name': 'Ticket Escalated',
        'description': 'Ticket has been escalated to higher priority or management',
        'default_severity': 'MEDIUM',
    },
    'DEVICE_OFFLINE': {
        'code': 'DEVICE_OFFLINE',
        'name': 'Device Offline',
        'description': 'IoT device or monitoring endpoint is unreachable',
        'default_severity': 'HIGH',
    },
    'DEVICE_SPOOF': {
        'code': 'DEVICE_SPOOF',
        'name': 'Device Spoofing Detected',
        'description': 'Potential device spoofing or unauthorized access detected',
        'default_severity': 'CRITICAL',
    },
    'GEOFENCE_BREACH': {
        'code': 'GEOFENCE_BREACH',
        'name': 'Geofence Violation',
        'description': 'Personnel or asset detected outside authorized geofence',
        'default_severity': 'MEDIUM',
    },
    'ATTENDANCE_MISSING': {
        'code': 'ATTENDANCE_MISSING',
        'name': 'Attendance Missing',
        'description': 'Expected attendance event not recorded',
        'default_severity': 'LOW',
    },
    'SYNC_DEGRADED': {
        'code': 'SYNC_DEGRADED',
        'name': 'Sync Health Degraded',
        'description': 'Mobile sync health score has degraded below threshold',
        'default_severity': 'MEDIUM',
    },
    'SECURITY_ANOMALY': {
        'code': 'SECURITY_ANOMALY',
        'name': 'Security Anomaly',
        'description': 'Unusual security pattern or potential breach detected',
        'default_severity': 'CRITICAL',
    },
    'WORK_ORDER_OVERDUE': {
        'code': 'WORK_ORDER_OVERDUE',
        'name': 'Work Order Overdue',
        'description': 'Work order has exceeded expected completion time',
        'default_severity': 'MEDIUM',
    },
    'ATTENDANCE_ANOMALY': {
        'code': 'ATTENDANCE_ANOMALY',
        'name': 'Attendance Anomaly',
        'description': 'Statistical anomaly in attendance patterns detected',
        'default_severity': 'MEDIUM',
    },
    'WRONG_PERSON_AT_SITE': {
        'code': 'WRONG_PERSON_AT_SITE',
        'name': 'Wrong Person at Site',
        'description': 'Person marked attendance but different person was scheduled',
        'default_severity': 'HIGH',
    },
    'UNAUTHORIZED_SITE_ACCESS': {
        'code': 'UNAUTHORIZED_SITE_ACCESS',
        'name': 'Unauthorized Site Access',
        'description': 'Person accessed site they are not authorized for',
        'default_severity': 'CRITICAL',
    },
    'IMPOSSIBLE_SHIFTS': {
        'code': 'IMPOSSIBLE_SHIFTS',
        'name': 'Impossible Consecutive Shifts',
        'description': 'Physically impossible travel time between consecutive shifts',
        'default_severity': 'CRITICAL',
    },
    'OVERTIME_VIOLATION': {
        'code': 'OVERTIME_VIOLATION',
        'name': 'Overtime Violation',
        'description': 'Continuous work hours exceeded legal/policy limits',
        'default_severity': 'HIGH',
    },
    'BUDDY_PUNCHING': {
        'code': 'BUDDY_PUNCHING',
        'name': 'Buddy Punching Detected',
        'description': 'Concurrent biometric usage or attendance fraud detected',
        'default_severity': 'CRITICAL',
    },
    'GPS_SPOOFING': {
        'code': 'GPS_SPOOFING',
        'name': 'GPS Spoofing Suspected',
        'description': 'GPS location appears to be manipulated or spoofed',
        'default_severity': 'HIGH',
    },
    'BIOMETRIC_PATTERN_ANOMALY': {
        'code': 'BIOMETRIC_PATTERN_ANOMALY',
        'name': 'Biometric Pattern Anomaly',
        'description': 'Unusual biometric attendance patterns detected',
        'default_severity': 'MEDIUM',
    },
    'SCHEDULE_MISMATCH': {
        'code': 'SCHEDULE_MISMATCH',
        'name': 'Schedule Mismatch',
        'description': 'Attendance does not match scheduled shift',
        'default_severity': 'MEDIUM',
    },
    'GUARD_INACTIVITY': {
        'code': 'GUARD_INACTIVITY',
        'name': 'Guard Inactivity Detected',
        'description': 'Guard showing no activity during shift (likely sleeping)',
        'default_severity': 'HIGH',
    },
    'GPS_LOW_ACCURACY': {
        'code': 'GPS_LOW_ACCURACY',
        'name': 'GPS Low Accuracy',
        'description': 'GPS accuracy below acceptable threshold',
        'default_severity': 'MEDIUM',
    },
    'TOUR_OVERDUE': {
        'code': 'TOUR_OVERDUE',
        'name': 'Tour Overdue',
        'description': 'Mandatory tour not completed within SLA',
        'default_severity': 'HIGH',
    },
    'TOUR_INCOMPLETE': {
        'code': 'TOUR_INCOMPLETE',
        'name': 'Tour Incomplete',
        'description': 'Tour completed with insufficient checkpoint coverage',
        'default_severity': 'MEDIUM',
    },
}


ALERT_SEVERITIES = [
    ('INFO', 'Informational'),
    ('LOW', 'Low'),
    ('MEDIUM', 'Medium'),
    ('HIGH', 'High'),
    ('CRITICAL', 'Critical'),
]


ALERT_STATUSES = [
    ('NEW', 'New'),
    ('ACKNOWLEDGED', 'Acknowledged'),
    ('ASSIGNED', 'Assigned'),
    ('ESCALATED', 'Escalated'),
    ('RESOLVED', 'Resolved'),
    ('SUPPRESSED', 'Suppressed'),
]


INCIDENT_STATES = [
    ('NEW', 'New'),
    ('ACKNOWLEDGED', 'Acknowledged'),
    ('ASSIGNED', 'Assigned'),
    ('IN_PROGRESS', 'In Progress'),
    ('RESOLVED', 'Resolved'),
    ('CLOSED', 'Closed'),
]


DEFAULT_METRIC_WINDOW_MINUTES = {
    'realtime': 5,
    'short': 15,
    'medium': 60,
    'long': 240,
}


DEFAULT_ALERT_THRESHOLDS = {
    'tickets_overdue_count': 5,
    'attendance_missing_percent': 20,
    'device_offline_count': 3,
    'sync_health_score_min': 70.0,
    'work_orders_overdue_count': 10,
    'geofence_breach_count_per_hour': 5,
}


DEFAULT_ESCALATION_DELAYS = {
    'CRITICAL': 15,  # minutes
    'HIGH': 30,
    'MEDIUM': 60,
    'LOW': 120,
    'INFO': None,  # Never auto-escalate
}


DEFAULT_ALERT_SUPPRESSION_WINDOW = 60  # minutes