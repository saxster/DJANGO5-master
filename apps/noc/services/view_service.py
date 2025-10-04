"""
NOC View Service Layer.

Service for managing saved dashboard views and user preferences.
Follows .claude/rules.md Rule #8 (methods <30 lines), Rule #11 (specific exceptions).
"""

import logging
from typing import List, Optional
from django.db.models import QuerySet
from django.db import transaction
from apps.noc.models import NOCSavedView
from apps.core.utils_new.db_utils import get_current_db_name

__all__ = ['NOCViewService']

logger = logging.getLogger('noc.services.view')


class NOCViewService:
    """
    Service for NOC saved view management.

    Handles view CRUD operations, default view management, and sharing.
    """

    @staticmethod
    def get_user_views(user) -> QuerySet:
        """
        Get all views accessible to user.

        Args:
            user: People instance

        Returns:
            QuerySet of NOCSavedView instances
        """
        own_views = NOCSavedView.objects.filter(
            tenant=user.tenant,
            user=user
        )

        shared_views = NOCSavedView.objects.filter(
            tenant=user.tenant,
            is_shared=True,
            shared_with=user
        )

        return (own_views | shared_views).distinct()

    @staticmethod
    def get_default_view(user) -> Optional[NOCSavedView]:
        """
        Get user's default view.

        Args:
            user: People instance

        Returns:
            NOCSavedView instance or None
        """
        try:
            return NOCSavedView.objects.get(
                tenant=user.tenant,
                user=user,
                is_default=True
            )
        except NOCSavedView.DoesNotExist:
            return None

    @staticmethod
    def set_default_view(user, view_id: int) -> NOCSavedView:
        """
        Set a view as user's default.

        Args:
            user: People instance
            view_id: ID of view to set as default

        Returns:
            Updated NOCSavedView instance
        """
        with transaction.atomic(using=get_current_db_name()):
            NOCSavedView.objects.filter(
                tenant=user.tenant,
                user=user,
                is_default=True
            ).update(is_default=False)

            view = NOCSavedView.objects.get(
                id=view_id,
                tenant=user.tenant,
                user=user
            )
            view.is_default = True
            view.save(update_fields=['is_default'])

            logger.info(
                f"Set default view",
                extra={'user_id': user.id, 'view_id': view_id}
            )

            return view

    @staticmethod
    def share_view(view: NOCSavedView, user_ids: List[int]) -> bool:
        """
        Share view with specified users.

        Args:
            view: NOCSavedView instance
            user_ids: List of People IDs to share with

        Returns:
            Success status
        """
        try:
            from apps.peoples.models import People

            users = People.objects.filter(
                id__in=user_ids,
                tenant=view.tenant
            )

            with transaction.atomic(using=get_current_db_name()):
                view.is_shared = True
                view.save(update_fields=['is_shared'])
                view.shared_with.add(*users)

            logger.info(
                f"Shared view",
                extra={'view_id': view.id, 'user_count': len(user_ids)}
            )

            return True

        except (ValueError, AttributeError) as e:
            logger.error(
                f"Failed to share view: {e}",
                extra={'view_id': view.id}
            )
            return False

    @staticmethod
    def unshare_view(view: NOCSavedView, user_ids: Optional[List[int]] = None) -> bool:
        """
        Unshare view (remove specific users or all).

        Args:
            view: NOCSavedView instance
            user_ids: Optional list of People IDs to remove (None = remove all)

        Returns:
            Success status
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                if user_ids:
                    view.shared_with.remove(*user_ids)

                    if not view.shared_with.exists():
                        view.is_shared = False
                        view.save(update_fields=['is_shared'])
                else:
                    view.shared_with.clear()
                    view.is_shared = False
                    view.save(update_fields=['is_shared'])

            logger.info(
                f"Unshared view",
                extra={'view_id': view.id}
            )

            return True

        except (ValueError, AttributeError) as e:
            logger.error(
                f"Failed to unshare view: {e}",
                extra={'view_id': view.id}
            )
            return False

    @staticmethod
    def clone_view(view: NOCSavedView, new_name: str, user) -> NOCSavedView:
        """
        Clone an existing view for the user.

        Args:
            view: NOCSavedView instance to clone
            new_name: Name for the cloned view
            user: People instance (owner of clone)

        Returns:
            New NOCSavedView instance
        """
        cloned_view = NOCSavedView.objects.create(
            tenant=user.tenant,
            user=user,
            name=new_name,
            description=f"Cloned from: {view.name}",
            filters=view.filters.copy(),
            widget_layout=view.widget_layout.copy(),
            time_range_hours=view.time_range_hours,
            refresh_interval_seconds=view.refresh_interval_seconds,
            is_default=False,
            is_shared=False,
            version=1
        )

        logger.info(
            f"Cloned view",
            extra={
                'source_view_id': view.id,
                'new_view_id': cloned_view.id,
                'user_id': user.id
            }
        )

        return cloned_view

    @staticmethod
    def validate_widget_layout(layout: list) -> bool:
        """
        Validate widget layout structure.

        Args:
            layout: Widget layout configuration

        Returns:
            True if valid
        """
        if not isinstance(layout, list):
            return False

        required_fields = {'widget_id', 'x', 'y', 'width', 'height'}

        for widget in layout:
            if not isinstance(widget, dict):
                return False

            if not required_fields.issubset(widget.keys()):
                return False

            if not all(isinstance(widget.get(f), int) for f in ['x', 'y', 'width', 'height']):
                return False

        return True

    @staticmethod
    def validate_filters(filters: dict) -> bool:
        """
        Validate filter structure.

        Args:
            filters: Filter configuration

        Returns:
            True if valid
        """
        if not isinstance(filters, dict):
            return False

        valid_keys = {
            'client_ids',
            'severities',
            'statuses',
            'time_range_hours',
            'alert_types'
        }

        if not set(filters.keys()).issubset(valid_keys):
            return False

        if 'client_ids' in filters and not isinstance(filters['client_ids'], list):
            return False

        if 'severities' in filters and not isinstance(filters['severities'], list):
            return False

        if 'statuses' in filters and not isinstance(filters['statuses'], list):
            return False

        return True