"""Feature flags controlling REST API rollout phases."""

from __future__ import annotations

import os
from typing import Dict


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


API_MIGRATION_FEATURE_FLAGS: Dict[str, bool] = {
    # Phase 1 – REST authentication endpoints
    "rest_auth_enabled": _env_flag("REST_AUTH_ENABLED", default=False),
    # Phase 2 – Mobile sync read endpoints (tickets, questions, type assist)
    "rest_sync_read_enabled": _env_flag("REST_SYNC_READ_ENABLED", default=False),
    # Phase 3 – Job, people, and attendance sync endpoints
    "rest_sync_jobs_enabled": _env_flag("REST_SYNC_JOBS_ENABLED", default=False),
    # Phase 4 – Work permit workflow and secure file uploads
    "rest_workpermit_enabled": _env_flag("REST_WORKPERMIT_ENABLED", default=False),
    # Phase 5 – HelpBot and wellness REST surfaces
    "rest_helpbot_enabled": _env_flag("REST_HELPBOT_ENABLED", default=False),
}


__all__ = ["API_MIGRATION_FEATURE_FLAGS"]
