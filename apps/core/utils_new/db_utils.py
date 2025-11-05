"""
Database Utilities Module - DEPRECATED

This module has been refactored into submodules for maintainability.
All imports are preserved for backward compatibility.

NEW STRUCTURE (Phase 4 Refactoring):
  apps/core/utils_new/db/
    ├── connection.py    - Database connection and routing (101 lines)
    ├── queries.py       - Raw SQL query utilities (76 lines)
    ├── transactions.py  - Transaction and state management (171 lines)
    ├── none_objects.py  - NONE object factories (349 lines)
    ├── admin.py         - Admin utilities (60 lines)
    └── __init__.py      - Package exports (101 lines)

MIGRATION GUIDE:
  OLD: from apps.core.utils_new.db_utils import get_current_db_name
  NEW: from apps.core.utils_new.db.connection import get_current_db_name
  OR:  from apps.core.utils_new.db import get_current_db_name

This file will be removed in Q1 2026. Update imports accordingly.
"""

# Re-export all functions from new modules for backward compatibility
from apps.core.utils_new.db.connection import (
    THREAD_LOCAL,
    get_current_db_name,
    set_db_for_router,
    hostname_from_request,
    get_tenants_map,
    tenant_db_from_request,
    create_tenant_with_alias,
)

from apps.core.utils_new.db.queries import (
    dictfetchall,
    namedtuplefetchall,
    runrawsql,
    get_record_from_input,
)

from apps.core.utils_new.db.transactions import (
    save_common_stuff,
    get_action_on_ticket_states,
    store_ticket_history,
)

from apps.core.utils_new.db.none_objects import (
    check_nones,
    get_or_create_none_people,
    get_or_create_none_pgroup,
    get_or_create_none_cap,
    get_or_create_none_typeassist,
    get_none_typeassist,
    get_or_create_none_bv,
    get_or_create_none_tenant,
    get_or_create_none_location,
    get_or_create_none_jobneed,
    get_or_create_none_wom,
    get_or_create_none_qset,
    get_or_create_none_question,
    get_or_create_none_qsetblng,
    get_or_create_none_asset,
    get_or_create_none_ticket,
    get_or_create_none_job,
    get_or_create_none_gf,
    create_none_entries,
)

from apps.core.utils_new.db.admin import (
    create_super_admin,
)

__all__ = [
    # connection
    'THREAD_LOCAL',
    'get_current_db_name',
    'set_db_for_router',
    'hostname_from_request',
    'get_tenants_map',
    'tenant_db_from_request',
    'create_tenant_with_alias',
    # queries
    'dictfetchall',
    'namedtuplefetchall',
    'runrawsql',
    'get_record_from_input',
    # transactions
    'save_common_stuff',
    'get_action_on_ticket_states',
    'store_ticket_history',
    # none_objects
    'check_nones',
    'get_or_create_none_people',
    'get_or_create_none_pgroup',
    'get_or_create_none_cap',
    'get_or_create_none_typeassist',
    'get_none_typeassist',
    'get_or_create_none_bv',
    'get_or_create_none_tenant',
    'get_or_create_none_location',
    'get_or_create_none_jobneed',
    'get_or_create_none_wom',
    'get_or_create_none_qset',
    'get_or_create_none_question',
    'get_or_create_none_qsetblng',
    'get_or_create_none_asset',
    'get_or_create_none_ticket',
    'get_or_create_none_job',
    'get_or_create_none_gf',
    'create_none_entries',
    # admin
    'create_super_admin',
]
