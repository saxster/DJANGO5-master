"""
Central Dashboard Registry

Unified registry for all dashboard views across the application.
Provides role-based access control, category organization, and
a single source of truth for dashboard management.

Usage:
    from apps.core.registry.dashboard_registry import dashboard_registry

    # Register a dashboard
    dashboard_registry.register(
        id='core_overview',
        title='System Overview',
        url='/dashboard/',
        permission='core.view_dashboard',
        category='core',
        icon='dashboard'
    )

    # Get dashboards for user
    dashboards = dashboard_registry.get_dashboards_for_user(request.user)

    # Get by category
    security_dashboards = dashboard_registry.get_by_category('security')

Architecture Compliance:
- Centralized configuration (prevents scattered dashboard definitions)
- Permission-based access control
- Category-based organization
- Lazy loading support for performance

Author: Dashboard Infrastructure Team
Date: 2025-10-04
"""

import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from django.contrib.auth import get_user_model
from django.urls import reverse, NoReverseMatch

logger = logging.getLogger(__name__)
User = get_user_model()


@dataclass
class Dashboard:
    """
    Dashboard definition with metadata.

    Attributes:
        id: Unique dashboard identifier
        title: Human-readable dashboard title
        url: Dashboard URL (can be path or named URL)
        permission: Required permission (e.g., 'core.view_dashboard')
        category: Dashboard category for organization
        description: Optional description
        icon: Optional icon class (e.g., 'fa-dashboard')
        tags: Optional tags for filtering
        priority: Display priority (lower = higher priority)
        refresh_interval: Auto-refresh interval in seconds (0 = no refresh)
        real_time: Whether dashboard supports WebSocket real-time updates
    """
    id: str
    title: str
    url: str
    permission: str
    category: str
    description: str = ''
    icon: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    priority: int = 100
    refresh_interval: int = 0
    real_time: bool = False

    def __post_init__(self):
        """Validate dashboard definition."""
        if not self.id:
            raise ValueError("Dashboard ID is required")
        if not self.title:
            raise ValueError("Dashboard title is required")
        if not self.url:
            raise ValueError("Dashboard URL is required")
        if not self.permission:
            raise ValueError("Dashboard permission is required")
        if not self.category:
            raise ValueError("Dashboard category is required")

    def has_access(self, user: User) -> bool:
        """
        Check if user has access to this dashboard.

        Args:
            user: User instance

        Returns:
            True if user has required permission
        """
        if user.is_superuser:
            return True

        # Parse permission string (e.g., 'core.view_dashboard')
        if '.' in self.permission:
            app_label, codename = self.permission.rsplit('.', 1)
            return user.has_perm(self.permission)
        else:
            # Simple permission checks
            if self.permission == 'staff':
                return user.is_staff
            elif self.permission == 'authenticated':
                return user.is_authenticated
            elif self.permission == 'superuser':
                return user.is_superuser
            else:
                # Custom permission check
                return user.has_perm(self.permission)

    def get_absolute_url(self) -> str:
        """
        Get absolute URL for dashboard.

        Returns:
            Resolved URL string
        """
        # Check if URL is already a path
        if self.url.startswith('/'):
            return self.url

        # Try to reverse URL name
        try:
            return reverse(self.url)
        except NoReverseMatch:
            logger.warning(f"Could not reverse URL '{self.url}' for dashboard '{self.id}'")
            return self.url

    def to_dict(self) -> Dict:
        """
        Convert dashboard to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            'id': self.id,
            'title': self.title,
            'url': self.get_absolute_url(),
            'permission': self.permission,
            'category': self.category,
            'description': self.description,
            'icon': self.icon,
            'tags': self.tags,
            'priority': self.priority,
            'refresh_interval': self.refresh_interval,
            'real_time': self.real_time
        }


class DashboardRegistry:
    """
    Central registry for all application dashboards.

    Provides unified dashboard management with:
    - Registration and discovery
    - Permission-based filtering
    - Category organization
    - Role-aware access control
    """

    def __init__(self):
        """Initialize empty registry."""
        self._dashboards: Dict[str, Dashboard] = {}
        self._categories: Dict[str, List[str]] = {}
        self._initialized = False
        logger.info("Dashboard registry initialized")

    def register(self,
                 id: str,
                 title: str,
                 url: str,
                 permission: str,
                 category: str,
                 description: str = '',
                 icon: Optional[str] = None,
                 tags: Optional[List[str]] = None,
                 priority: int = 100,
                 refresh_interval: int = 0,
                 real_time: bool = False) -> Dashboard:
        """
        Register a dashboard in the registry.

        Args:
            id: Unique dashboard identifier
            title: Dashboard title
            url: Dashboard URL (path or named URL)
            permission: Required permission
            category: Dashboard category
            description: Optional description
            icon: Optional icon class
            tags: Optional tags list
            priority: Display priority (lower = higher)
            refresh_interval: Auto-refresh interval (seconds)
            real_time: WebSocket support flag

        Returns:
            Registered Dashboard instance

        Raises:
            ValueError: If dashboard with same ID already exists
        """
        if id in self._dashboards:
            raise ValueError(f"Dashboard with ID '{id}' already registered")

        dashboard = Dashboard(
            id=id,
            title=title,
            url=url,
            permission=permission,
            category=category,
            description=description,
            icon=icon,
            tags=tags or [],
            priority=priority,
            refresh_interval=refresh_interval,
            real_time=real_time
        )

        self._dashboards[id] = dashboard

        # Add to category index
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(id)

        logger.info(f"Registered dashboard: {id} ({title}) in category '{category}'")
        return dashboard

    def unregister(self, id: str) -> bool:
        """
        Unregister a dashboard.

        Args:
            id: Dashboard ID to unregister

        Returns:
            True if dashboard was unregistered, False if not found
        """
        if id not in self._dashboards:
            return False

        dashboard = self._dashboards[id]

        # Remove from category index
        if dashboard.category in self._categories:
            self._categories[dashboard.category].remove(id)
            if not self._categories[dashboard.category]:
                del self._categories[dashboard.category]

        del self._dashboards[id]
        logger.info(f"Unregistered dashboard: {id}")
        return True

    def get(self, id: str) -> Optional[Dashboard]:
        """
        Get dashboard by ID.

        Args:
            id: Dashboard ID

        Returns:
            Dashboard instance or None if not found
        """
        return self._dashboards.get(id)

    def all(self) -> List[Dashboard]:
        """
        Get all registered dashboards.

        Returns:
            List of all dashboards sorted by priority
        """
        return sorted(self._dashboards.values(), key=lambda d: d.priority)

    def get_dashboards_for_user(self, user: User) -> List[Dashboard]:
        """
        Get all dashboards accessible to user.

        Args:
            user: User instance

        Returns:
            List of dashboards user can access, sorted by priority
        """
        accessible = [
            dashboard for dashboard in self._dashboards.values()
            if dashboard.has_access(user)
        ]
        return sorted(accessible, key=lambda d: d.priority)

    def get_by_category(self, category: str) -> List[Dashboard]:
        """
        Get all dashboards in a category.

        Args:
            category: Category name

        Returns:
            List of dashboards in category, sorted by priority
        """
        dashboard_ids = self._categories.get(category, [])
        dashboards = [self._dashboards[id] for id in dashboard_ids]
        return sorted(dashboards, key=lambda d: d.priority)

    def get_categories(self) -> List[str]:
        """
        Get all registered categories.

        Returns:
            List of category names
        """
        return sorted(self._categories.keys())

    def get_by_tag(self, tag: str) -> List[Dashboard]:
        """
        Get all dashboards with a specific tag.

        Args:
            tag: Tag to filter by

        Returns:
            List of matching dashboards, sorted by priority
        """
        matching = [
            dashboard for dashboard in self._dashboards.values()
            if tag in dashboard.tags
        ]
        return sorted(matching, key=lambda d: d.priority)

    def search(self, query: str) -> List[Dashboard]:
        """
        Search dashboards by title or description.

        Args:
            query: Search query

        Returns:
            List of matching dashboards, sorted by relevance
        """
        query_lower = query.lower()
        matching = []

        for dashboard in self._dashboards.values():
            # Calculate relevance score
            score = 0

            if query_lower in dashboard.title.lower():
                score += 10
            if query_lower in dashboard.description.lower():
                score += 5
            if query_lower in dashboard.category.lower():
                score += 3
            if any(query_lower in tag.lower() for tag in dashboard.tags):
                score += 2

            if score > 0:
                matching.append((score, dashboard))

        # Sort by score (descending) then priority (ascending)
        matching.sort(key=lambda x: (-x[0], x[1].priority))
        return [dashboard for score, dashboard in matching]

    def get_dashboard_count(self) -> int:
        """
        Get total number of registered dashboards.

        Returns:
            Count of dashboards
        """
        return len(self._dashboards)

    def get_category_count(self) -> int:
        """
        Get total number of categories.

        Returns:
            Count of categories
        """
        return len(self._categories)

    def to_dict(self) -> Dict:
        """
        Convert entire registry to dictionary.

        Returns:
            Dictionary with registry metadata and all dashboards
        """
        return {
            'total_dashboards': self.get_dashboard_count(),
            'total_categories': self.get_category_count(),
            'categories': self.get_categories(),
            'dashboards': [dashboard.to_dict() for dashboard in self.all()]
        }


# Global registry instance
dashboard_registry = DashboardRegistry()


# Auto-registration function for apps to call during initialization
def register_core_dashboards():
    """
    Register core application dashboards.

    Called automatically during app initialization.
    Individual apps should define their own registration functions.
    """
    # Core dashboards
    dashboard_registry.register(
        id='core_main',
        title='Main Dashboard',
        url='/dashboard/',
        permission='authenticated',
        category='core',
        description='System overview and key metrics',
        icon='fa-dashboard',
        priority=1,
        refresh_interval=30
    )

    dashboard_registry.register(
        id='core_database',
        title='Database Performance',
        url='/admin/database/',
        permission='staff',
        category='admin_infra',
        description='Database performance monitoring and analytics',
        icon='fa-database',
        tags=['performance', 'monitoring'],
        priority=20
    )

    dashboard_registry.register(
        id='core_redis',
        title='Redis Performance',
        url='/admin/redis/dashboard/',
        permission='staff',
        category='admin_infra',
        description='Redis performance metrics and health',
        icon='fa-server',
        tags=['performance', 'cache', 'monitoring'],
        priority=21
    )

    dashboard_registry.register(
        id='core_tasks',
        title='Task Monitoring',
        url='/admin/tasks/dashboard',
        permission='staff',
        category='admin_infra',
        description='Background task monitoring and idempotency analysis',
        icon='fa-tasks',
        tags=['monitoring', 'celery', 'background'],
        priority=22
    )

    dashboard_registry.register(
        id='core_state_transitions',
        title='State Transitions',
        url='/admin/state-transitions/dashboard/',
        permission='staff',
        category='admin_infra',
        description='State machine transition monitoring and failure analysis',
        icon='fa-exchange',
        tags=['monitoring', 'state-machines'],
        priority=23
    )

    # Security dashboards
    dashboard_registry.register(
        id='security_csrf',
        title='CSRF Violations',
        url='/admin/security/csrf-violations/',
        permission='staff',
        category='security',
        description='CSRF violation monitoring and threat detection',
        icon='fa-shield',
        tags=['security', 'csrf', 'threats'],
        priority=30,
        refresh_interval=15
    )

    dashboard_registry.register(
        id='security_rate_limiting',
        title='Rate Limiting',
        url='/security/rate-limiting/dashboard/',
        permission='staff',
        category='security',
        description='Rate limiting analytics and blocked requests',
        icon='fa-ban',
        tags=['security', 'rate-limiting'],
        priority=32
    )

    logger.info("Core dashboards registered successfully")


# Export public API
__all__ = [
    'Dashboard',
    'DashboardRegistry',
    'dashboard_registry',
    'register_core_dashboards'
]
