"""
Issue Tracker Enums
Centralized choice definitions for status, severity, and type fields
"""

# Severity levels for anomaly classification
SEVERITY_CHOICES = [
    ('info', 'Info'),
    ('warning', 'Warning'),
    ('error', 'Error'),
    ('critical', 'Critical')
]

# Status choices for anomaly signatures
SIGNATURE_STATUS_CHOICES = [
    ('active', 'Active'),
    ('resolved', 'Resolved'),
    ('ignored', 'Ignored'),
    ('monitoring', 'Monitoring')
]

# Status choices for anomaly occurrences
OCCURRENCE_STATUS_CHOICES = [
    ('new', 'New'),
    ('investigating', 'Investigating'),
    ('resolved', 'Resolved'),
    ('false_positive', 'False Positive')
]

# Fix types for suggested fixes
FIX_TYPES = [
    ('index', 'Database Index'),
    ('serializer', 'Serializer Update'),
    ('rate_limit', 'Rate Limiting'),
    ('connection_pool', 'Connection Pool'),
    ('caching', 'Caching Strategy'),
    ('retry_policy', 'Retry Policy'),
    ('schema_update', 'Schema Update'),
    ('configuration', 'Configuration Change'),
    ('code_fix', 'Code Fix'),
    ('infrastructure', 'Infrastructure Change')
]

# Status choices for fix suggestions
FIX_STATUS_CHOICES = [
    ('suggested', 'Suggested'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('applied', 'Applied'),
    ('verified', 'Verified')
]

# Risk levels for fix suggestions
RISK_LEVEL_CHOICES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High')
]

# Action types for fix actions
FIX_ACTION_TYPES = [
    ('applied', 'Applied'),
    ('tested', 'Tested'),
    ('rolled_back', 'Rolled Back'),
    ('verified', 'Verified')
]

# Result choices for fix actions
FIX_ACTION_RESULT_CHOICES = [
    ('success', 'Success'),
    ('partial', 'Partial Success'),
    ('failed', 'Failed'),
    ('pending', 'Pending')
]

# Severity trend choices
SEVERITY_TREND_CHOICES = [
    ('improving', 'Improving'),
    ('stable', 'Stable'),
    ('worsening', 'Worsening')
]
