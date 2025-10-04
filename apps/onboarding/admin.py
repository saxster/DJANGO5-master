"""
Backward Compatibility Shim for apps.onboarding.admin

This file provides 100% backward compatibility for code importing from apps.onboarding.admin.
All admin classes are re-exported from the new domain-specific admin modules.

Migration Date: 2025-09-30
Original File: Archived to .archive/onboarding_admin.py_*

IMPORTANT: This is a compatibility layer only!
New code should import directly from apps.onboarding.admin package or domain-specific modules.

Usage:
    # OLD (still works via this file):
    from apps.onboarding.admin import TaAdmin
    from apps.onboarding import admin
    admin.TaAdmin

    # NEW (recommended):
    from apps.onboarding.admin.typeassist_admin import TaAdmin
    from apps.onboarding.admin import typeassist_admin
    typeassist_admin.TaAdmin
"""

# Import everything from the new admin package
from apps.onboarding.admin import *
