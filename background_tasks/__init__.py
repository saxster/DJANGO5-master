"""
Background Tasks Package

All task implementations are in domain-specific modules:
- email_tasks.py - Email operations
- media_tasks.py - Media processing
- report_tasks.py - Report generation
- job_tasks.py - Job/tour management
- ticket_tasks.py - Ticketing operations
- integration_tasks.py - External API integrations
- maintenance_tasks.py - Cleanup and maintenance

Import directly from specific modules:
    from background_tasks.email_tasks import send_reminder_email
    from background_tasks.job_tasks import create_ppm_job

Or from the aggregator (for backward compatibility):
    from background_tasks.tasks import send_reminder_email

Note: __init__.py intentionally left empty to avoid circular import issues.
Refactored: 2025-10-10
"""

# Intentionally empty to prevent circular imports
# Import from specific task modules or from tasks.py aggregator
