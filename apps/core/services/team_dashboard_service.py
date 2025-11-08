"""
Team Dashboard Service

Provides business logic for the unified team operations dashboard.
Aggregates tickets, incidents, jobs across tenants with security and permissions.

Following CLAUDE.md:
- Rule #7: Service layer for business logic (ADR 003)
- Rule #11: Specific exception handling
- Rule #17: Multi-tenant isolation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.db import connection
from django.utils import timezone
from django.core.cache import cache
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class TeamDashboardService:
    """
    Service for Team Dashboard operations.
    
    Handles:
    - Item retrieval with filters
    - Stats calculations
    - Real-time updates
    - Permission checks
    """
    
    CACHE_TIMEOUT = 60  # 1 minute for dashboard data
    
    @staticmethod
    def get_dashboard_items(
        tenant_id: int,
        user_id: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get dashboard items with filters applied.
        
        Args:
            tenant_id: Tenant identifier
            user_id: Current user ID
            filters: Optional filters (status, priority, assigned_to, item_type)
            
        Returns:
            List of dashboard items sorted by priority
        """
        filters = filters or {}
        cache_key = f"team_dashboard:{tenant_id}:{user_id}:{hash(str(filters))}"
        
        # Try cache first
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            query = """
            SELECT 
                item_type,
                item_id,
                item_number,
                title,
                priority,
                status,
                assignee_id,
                created_at,
                updated_at,
                priority_score,
                sla_due_at,
                severity,
                url_namespace,
                client_id,
                site_id,
                -- Calculate urgency badge
                CASE 
                    WHEN sla_due_at IS NOT NULL AND sla_due_at <= NOW() THEN 'OVERDUE'
                    WHEN sla_due_at IS NOT NULL AND sla_due_at <= NOW() + INTERVAL '2 hours' THEN 'URGENT'
                    WHEN sla_due_at IS NOT NULL AND sla_due_at <= NOW() + INTERVAL '24 hours' THEN 'SOON'
                    ELSE 'ON_TRACK'
                END as urgency_badge,
                -- Time since creation
                EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600 as age_hours
            FROM v_team_dashboard
            WHERE tenant_id = %s
            """
            params = [tenant_id]
            
            # Apply filters
            if filters.get('status') == 'mine':
                query += " AND assignee_id = %s"
                params.append(user_id)
            elif filters.get('status') == 'unassigned':
                query += " AND assignee_id IS NULL"
            elif filters.get('status') == 'team':
                # All items for this tenant
                pass
            
            if filters.get('priority'):
                query += " AND priority = %s"
                params.append(filters['priority'])
            
            if filters.get('assigned_to'):
                query += " AND assignee_id = %s"
                params.append(filters['assigned_to'])
            
            if filters.get('item_type'):
                query += " AND item_type = %s"
                params.append(filters['item_type'].upper())
            
            if filters.get('search'):
                query += " AND (title ILIKE %s OR item_number ILIKE %s)"
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term])
            
            # Sort by priority and deadline
            query += """
            ORDER BY 
                urgency_badge DESC,
                priority_score DESC, 
                sla_due_at ASC NULLS LAST,
                created_at DESC
            LIMIT 50
            """
            
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                items = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]
            
            # Cache results
            cache.set(cache_key, items, TeamDashboardService.CACHE_TIMEOUT)
            
            return items
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error fetching dashboard items for tenant {tenant_id}: {e}",
                exc_info=True,
                extra={'tenant_id': tenant_id, 'user_id': user_id}
            )
            raise
    
    @staticmethod
    def get_dashboard_stats(tenant_id: int, user_id: int) -> Dict[str, Any]:
        """
        Calculate dashboard statistics.
        
        Args:
            tenant_id: Tenant identifier
            user_id: Current user ID
            
        Returns:
            Dictionary with stats (total, mine, urgent, overdue, etc.)
        """
        cache_key = f"team_dashboard_stats:{tenant_id}:{user_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            query = """
            SELECT 
                COUNT(*) as total_items,
                COUNT(*) FILTER (WHERE assignee_id = %s) as my_items,
                COUNT(*) FILTER (WHERE assignee_id IS NULL) as unassigned_items,
                COUNT(*) FILTER (WHERE sla_due_at <= NOW() + INTERVAL '2 hours') as urgent_items,
                COUNT(*) FILTER (WHERE sla_due_at <= NOW()) as overdue_items,
                COUNT(*) FILTER (WHERE item_type = 'TICKET') as ticket_count,
                COUNT(*) FILTER (WHERE item_type = 'INCIDENT') as incident_count,
                COUNT(*) FILTER (WHERE item_type = 'JOB') as job_count,
                COUNT(*) FILTER (WHERE priority IN ('HIGH', 'CRITICAL')) as high_priority_count
            FROM v_team_dashboard
            WHERE tenant_id = %s
            """
            
            with connection.cursor() as cursor:
                cursor.execute(query, [user_id, tenant_id])
                row = cursor.fetchone()
                
                stats = {
                    'total_items': row[0] or 0,
                    'my_items': row[1] or 0,
                    'unassigned_items': row[2] or 0,
                    'urgent_items': row[3] or 0,
                    'overdue_items': row[4] or 0,
                    'ticket_count': row[5] or 0,
                    'incident_count': row[6] or 0,
                    'job_count': row[7] or 0,
                    'high_priority_count': row[8] or 0,
                }
            
            # Cache for 30 seconds
            cache.set(cache_key, stats, 30)
            
            return stats
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error calculating dashboard stats for tenant {tenant_id}: {e}",
                exc_info=True,
                extra={'tenant_id': tenant_id, 'user_id': user_id}
            )
            return {
                'total_items': 0,
                'my_items': 0,
                'unassigned_items': 0,
                'urgent_items': 0,
                'overdue_items': 0,
                'ticket_count': 0,
                'incident_count': 0,
                'job_count': 0,
                'high_priority_count': 0,
            }
    
    @staticmethod
    def invalidate_cache(tenant_id: int, user_id: Optional[int] = None):
        """
        Invalidate dashboard cache after updates.
        
        Args:
            tenant_id: Tenant identifier
            user_id: Optional user ID to invalidate specific user cache
        """
        if user_id:
            cache.delete_pattern(f"team_dashboard:{tenant_id}:{user_id}:*")
            cache.delete(f"team_dashboard_stats:{tenant_id}:{user_id}")
        else:
            # Invalidate all caches for this tenant
            cache.delete_pattern(f"team_dashboard:{tenant_id}:*")
            cache.delete_pattern(f"team_dashboard_stats:{tenant_id}:*")
