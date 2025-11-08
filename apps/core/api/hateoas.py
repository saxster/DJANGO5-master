"""
HATEOAS (Hypermedia as the Engine of Application State) Implementation

Adds hypermedia links to API responses for self-documenting, discoverable APIs.

Usage:
    from apps.core.api.hateoas import HATEOASMixin

    class TaskSerializer(HATEOASMixin, serializers.ModelSerializer):
        class Meta:
            model = Task
            fields = '__all__'

        def get_hateoas_links(self, obj):
            return {
                'checkpoints': self.build_url('scheduler:task-checkpoints', task_id=obj.id),
                'assign': self.build_url('scheduler:task-assign', task_id=obj.id),
            }

Example Response:
    {
        "id": 123,
        "name": "Security Patrol",
        "status": "active",
        "_links": {
            "self": "/api/v1/tasks/123/",
            "checkpoints": "/api/v1/tasks/123/checkpoints/",
            "assign": "/api/v1/tasks/123/assign/",
            "collection": "/api/v1/tasks/"
        }
    }
"""

import logging
from typing import Dict, Optional, Any
from django.urls import reverse, NoReverseMatch
from django.conf import settings
from rest_framework import serializers

logger = logging.getLogger(__name__)


class HATEOASMixin:
    """
    Mixin to add HATEOAS links to serializer responses.

    Automatically adds:
    - self: Link to the resource itself
    - collection: Link to the collection (list view)
    - Custom links via get_hateoas_links()

    Usage:
        class MySerializer(HATEOASMixin, serializers.ModelSerializer):
            def get_hateoas_links(self, obj):
                return {
                    'related_resource': self.build_url('app:view-name', id=obj.id)
                }
    """

    def to_representation(self, instance):
        """
        Add _links field to serialized data.
        """
        data = super().to_representation(instance)

        # Add HATEOAS links if enabled
        if self._should_add_links():
            links = self._build_links(instance)
            if links:
                data['_links'] = links

        return data

    def _should_add_links(self) -> bool:
        """
        Check if HATEOAS links should be added.
        """
        # Check global setting
        if not getattr(settings, 'API_HATEOAS_ENABLED', True):
            return False

        # Check if we're in a list view (don't add links to every item by default)
        view = self.context.get('view')
        if view and hasattr(view, 'action') and view.action == 'list':
            # Only add links in list view if explicitly enabled
            return getattr(settings, 'API_HATEOAS_IN_LISTS', False)

        return True

    def _build_links(self, instance) -> Dict[str, str]:
        """
        Build all HATEOAS links for the instance.
        """
        links = {}

        # Add 'self' link
        self_link = self._get_self_link(instance)
        if self_link:
            links['self'] = self_link

        # Add 'collection' link
        collection_link = self._get_collection_link()
        if collection_link:
            links['collection'] = collection_link

        # Add custom links from subclass
        custom_links = self.get_hateoas_links(instance)
        if custom_links:
            links.update(custom_links)

        return links

    def _get_self_link(self, instance) -> Optional[str]:
        """
        Get the 'self' link for this resource.

        Tries to determine the detail URL from:
        1. view context
        2. Model get_absolute_url()
        3. Convention-based URL pattern
        """
        # Try from view context
        view = self.context.get('view')
        request = self.context.get('request')

        if view and request:
            try:
                # If view has get_url method
                if hasattr(view, 'get_url'):
                    return view.get_url(instance)

                # Try to build from view name
                if hasattr(view, 'basename'):
                    url_name = f"{view.basename}-detail"
                    return self.build_url(url_name, pk=instance.pk)

            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"Could not build self link from view: {e}")

        # Try model's get_absolute_url()
        if hasattr(instance, 'get_absolute_url'):
            try:
                return instance.get_absolute_url()
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"Could not get absolute URL from model: {e}")

        return None

    def _get_collection_link(self) -> Optional[str]:
        """
        Get the 'collection' link (list view).
        """
        view = self.context.get('view')
        if view and hasattr(view, 'basename'):
            try:
                url_name = f"{view.basename}-list"
                return self.build_url(url_name)
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"Could not build collection link: {e}")

        return None

    def get_hateoas_links(self, instance) -> Dict[str, str]:
        """
        Override this method to add custom HATEOAS links.

        Args:
            instance: The model instance being serialized

        Returns:
            Dictionary of link_name → URL

        Example:
            def get_hateoas_links(self, obj):
                return {
                    'checkpoints': self.build_url('scheduler:task-checkpoints', task_id=obj.id),
                    'assign': self.build_url('scheduler:task-assign', task_id=obj.id),
                    'complete': self.build_url('scheduler:task-complete', task_id=obj.id),
                }
        """
        return {}

    def build_url(self, view_name: str, **kwargs) -> str:
        """
        Build a full URL from view name and parameters.

        Args:
            view_name: Django URL name (can include namespace)
            **kwargs: URL parameters

        Returns:
            Full URL string

        Example:
            url = self.build_url('scheduler:task-detail', task_id=123)
            # Returns: 'http://example.com/api/v1/tasks/123/'
        """
        try:
            # Build relative URL
            relative_url = reverse(view_name, kwargs=kwargs)

            # Get request from context
            request = self.context.get('request')
            if request:
                # Build absolute URL
                return request.build_absolute_uri(relative_url)

            # Fallback to relative URL
            return relative_url

        except NoReverseMatch as e:
            logger.warning(f"Could not reverse URL '{view_name}' with kwargs {kwargs}: {e}")
            return None


class PaginatedHATEOASMixin:
    """
    Adds HATEOAS links to paginated responses.

    Usage:
        from rest_framework.pagination import PageNumberPagination
        from apps.core.api.hateoas import PaginatedHATEOASMixin

        class TaskPagination(PaginatedHATEOASMixin, PageNumberPagination):
            page_size = 50
    """

    def get_paginated_response(self, data):
        """
        Add HATEOAS links to paginated response.
        """
        response = super().get_paginated_response(data)

        # Add pagination links
        links = {
            'self': self.request.build_absolute_uri(),
        }

        if self.get_next_link():
            links['next'] = self.get_next_link()

        if self.get_previous_link():
            links['previous'] = self.get_previous_link()

        # Add first and last page links
        if hasattr(self, 'page'):
            page = self.page
            if page.has_previous():
                links['first'] = self._get_page_link(1)

            if page.has_next():
                links['last'] = self._get_page_link(page.paginator.num_pages)

        response.data['_links'] = links
        return response

    def _get_page_link(self, page_number: int) -> str:
        """
        Build link for specific page number.
        """
        url = self.request.build_absolute_uri()
        # Replace or add page parameter
        # This is a simplified implementation
        if '?' in url:
            base_url = url.split('?')[0]
            return f"{base_url}?page={page_number}"
        return f"{url}?page={page_number}"


def add_action_links(data: Dict, actions: Dict[str, str]) -> Dict:
    """
    Utility function to add action links to response data.

    Usage:
        data = {'id': 123, 'name': 'Task'}
        data = add_action_links(data, {
            'approve': '/api/v1/tasks/123/approve/',
            'reject': '/api/v1/tasks/123/reject/',
        })

    Args:
        data: Response data dictionary
        actions: Dictionary of action_name → URL

    Returns:
        Updated data dictionary with _actions field
    """
    if '_actions' not in data:
        data['_actions'] = {}

    data['_actions'].update(actions)
    return data


def add_related_links(data: Dict, related: Dict[str, str]) -> Dict:
    """
    Utility function to add related resource links.

    Usage:
        data = add_related_links(data, {
            'asset': '/api/v1/assets/456/',
            'location': '/api/v1/locations/789/',
        })

    Args:
        data: Response data dictionary
        related: Dictionary of resource_name → URL

    Returns:
        Updated data dictionary with _related field
    """
    if '_related' not in data:
        data['_related'] = {}

    data['_related'].update(related)
    return data


# Example Serializers

class ExampleTaskSerializer(HATEOASMixin, serializers.Serializer):
    """
    Example serializer showing HATEOAS implementation.
    """
    id = serializers.IntegerField()
    name = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()

    def get_hateoas_links(self, obj):
        """
        Add custom links for task resource.
        """
        return {
            'checkpoints': self.build_url('scheduler:task-checkpoints', task_id=obj.id),
            'assign': self.build_url('scheduler:task-assign', task_id=obj.id),
            'complete': self.build_url('scheduler:task-complete', task_id=obj.id),
            'asset': self.build_url('api_v1:asset-detail', pk=obj.asset_id) if hasattr(obj, 'asset_id') else None,
        }


# Configuration Guide
"""
=== CONFIGURATION ===

1. Enable HATEOAS globally:
    # settings.py
    API_HATEOAS_ENABLED = True
    API_HATEOAS_IN_LISTS = False  # Don't add links to list items by default

2. Add to serializers:
    from apps.core.api.hateoas import HATEOASMixin

    class MySerializer(HATEOASMixin, serializers.ModelSerializer):
        class Meta:
            model = MyModel
            fields = '__all__'

        def get_hateoas_links(self, obj):
            return {
                'related': self.build_url('app:view', id=obj.id)
            }

3. Use with pagination:
    from apps.core.api.hateoas import PaginatedHATEOASMixin

    class MyPagination(PaginatedHATEOASMixin, PageNumberPagination):
        page_size = 50

4. Manual link addition:
    from apps.core.api.hateoas import add_action_links

    data = serializer.data
    data = add_action_links(data, {
        'approve': reverse('tasks:approve', kwargs={'pk': obj.id}),
        'reject': reverse('tasks:reject', kwargs={'pk': obj.id}),
    })

=== BENEFITS ===

1. Self-Documenting APIs:
   - Clients can discover available actions
   - No need to hardcode URLs in clients

2. Loose Coupling:
   - URL changes don't break clients
   - Server controls navigation

3. Better Developer Experience:
   - Clear navigation paths
   - Reduced documentation burden

4. Mobile App Support:
   - Generate client SDKs with automatic navigation
   - Deep linking support

=== RESPONSE EXAMPLES ===

Single Resource:
    {
        "id": 123,
        "name": "Security Patrol",
        "status": "active",
        "_links": {
            "self": "/api/v1/tasks/123/",
            "collection": "/api/v1/tasks/",
            "checkpoints": "/api/v1/tasks/123/checkpoints/",
            "assign": "/api/v1/tasks/123/assign/"
        }
    }

Paginated List:
    {
        "count": 250,
        "results": [ ... ],
        "_links": {
            "self": "/api/v1/tasks/?page=2",
            "next": "/api/v1/tasks/?page=3",
            "previous": "/api/v1/tasks/?page=1",
            "first": "/api/v1/tasks/?page=1",
            "last": "/api/v1/tasks/?page=10"
        }
    }

With Actions:
    {
        "id": 123,
        "name": "Security Patrol",
        "status": "pending_approval",
        "_links": { ... },
        "_actions": {
            "approve": "/api/v1/tasks/123/approve/",
            "reject": "/api/v1/tasks/123/reject/",
            "reassign": "/api/v1/tasks/123/reassign/"
        }
    }
"""
