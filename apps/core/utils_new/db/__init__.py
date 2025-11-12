"""
Database Utilities Package

Provides utilities for database operations including:
- Connection management and tenant routing
- Raw SQL query execution with parameterization
- Transaction handling and state management
- NONE object factory functions for sentinel records
- Administrative utilities
"""

from .connection import (
    THREAD_LOCAL,
    get_current_db_name,
    set_db_for_router,
    hostname_from_request,
    get_tenants_map,
    tenant_db_from_request,
    create_tenant_with_alias,
)

from .queries import (
    dictfetchall,
    namedtuplefetchall,
    runrawsql,
    get_record_from_input,
)

from .transactions import (
    save_common_stuff,
    get_action_on_ticket_states,
    store_ticket_history,
)

from .none_objects import (
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

from .admin import (
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
