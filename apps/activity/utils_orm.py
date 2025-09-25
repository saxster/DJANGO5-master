"""
Django ORM implementations for activity utils.
Replaces raw SQL queries with Django ORM equivalents.

NOTE: The get_ticket_events_orm function uses raw SQL as a necessary compromise
because the Event model is not accessible from this module. However, it:
- Eliminates PostgreSQL-specific array functions (string_to_array, unnest)
- Uses parameterized queries to prevent SQL injection
- Is well-documented and isolated to this single function
"""
from django.db.models import Count, Q, F, Value
from django.db import models, connection
from apps.y_helpdesk.models import Ticket
import logging

logger = logging.getLogger("django")


def get_ticket_events_orm(ticketno, columnsort='asc', columnname='id'):
    """
    Get ticket events using a hybrid approach.
    
    This replaces the PostgreSQL-specific array operations (string_to_array, unnest)
    with Python string processing and a simpler SQL query.
    
    Since the Event model is not accessible, we use raw SQL but without
    PostgreSQL-specific array functions.
    """
    try:
        # Get the ticket and its events
        ticket = Ticket.objects.filter(ticketno=ticketno).values('events').first()
        if not ticket or not ticket['events']:
            return []
        
        # Split the comma-separated event IDs in Python
        event_ids = []
        events_str = ticket['events'].strip()
        if events_str:
            try:
                event_ids = [int(eid.strip()) for eid in events_str.split(',') if eid.strip().isdigit()]
            except (ValueError, AttributeError):
                logger.error(f"Invalid event IDs in ticket {ticketno}: {ticket['events']}")
                return []
        
        if not event_ids:
            return []
        
        # Validate column names for SQL injection prevention
        valid_columns = {
            "e.id": "e.id",
            "d.devicename": "d.devicename",
            "d.ipaddress": "d.ipaddress",
            "ta.taname": "ta.taname",
            "e.source": "e.source",
            "e.cdtz": "e.cdtz",
            "attachment__count": "attachment__count",
        }
        
        order_column = valid_columns.get(columnname, "e.id")
        order_direction = "DESC" if columnsort.lower() == "desc" else "ASC"
        
        # Build a simpler query without PostgreSQL array functions
        # Using parameterized IN clause for event IDs
        placeholders = ','.join(['%s'] * len(event_ids))
        
        sql = f"""
            SELECT 
                e.id as eid, 
                d.devicename, 
                d.ipaddress, 
                ta.taname as type, 
                e.source, 
                e.cdtz, 
                COUNT(att.id) AS attachment__count
            FROM event e
            INNER JOIN typeassist ta ON e.eventtype_id = ta.id
            INNER JOIN device d ON e.device_id = d.id
            LEFT JOIN attachment att ON e.id = att.event_id
            WHERE e.id IN ({placeholders})
            GROUP BY e.id, d.devicename, d.ipaddress, ta.taname, e.source, e.cdtz
            ORDER BY {order_column} {order_direction}
        """
        
        # Execute query with event IDs as parameters
        with connection.cursor() as cursor:
            cursor.execute(sql, event_ids)
            columns = [col[0] for col in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting ticket events for {ticketno}: {str(e)}")
        return []


def ticketevents_query_orm(ticketno, columnsort, columnname):
    """
    Django ORM replacement for ticketevents_query function.
    Returns the results directly instead of SQL query string.
    """
    # Validate inputs
    valid_columns = {
        "e.id",
        "d.devicename",
        "d.ipaddress",
        "ta.taname",
        "e.source",
        "e.cdtz",
        "attachment__count",
    }
    if columnname not in valid_columns:
        columnname = "e.id"  # Default to safe column if invalid
    
    if columnsort.lower() not in ("asc", "desc"):
        columnsort = "asc"  # Default to safe direction if invalid
    
    # Get the results using Django ORM
    return get_ticket_events_orm(ticketno, columnsort, columnname)