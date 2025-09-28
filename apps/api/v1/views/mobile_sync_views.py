"""
Mobile Sync Views - WebSocket Integration

Exposes sync_engine for import by mobile_consumers.py.
This module serves as the integration point between WebSocket consumers
and the sync engine service.

Usage in mobile_consumers.py:
    from .v1.views.mobile_sync_views import sync_engine
"""

from ..services.sync_engine_service import sync_engine

__all__ = ['sync_engine']