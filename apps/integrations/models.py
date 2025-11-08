"""
Integration models - Configuration for external integrations.

Uses TypeAssist for tenant-specific webhook configurations.
No new models needed - configuration stored in TypeAssist.other_data.

Webhook Configuration Structure (in TypeAssist.other_data):
{
    "webhooks": [
        {
            "id": "uuid",
            "name": "Primary Webhook",
            "url": "https://api.example.com/webhook",
            "events": ["ticket.created", "alert.escalated"],
            "secret": "hmac_secret",
            "enabled": true,
            "retry_count": 3,
            "timeout_seconds": 30
        }
    ],
    "teams": {
        "enabled": true,
        "webhook_url": "https://outlook.office.com/webhook/...",
        "events": ["sos.triggered", "sla.at_risk"]
    },
    "slack": {
        "enabled": true,
        "webhook_url": "https://hooks.slack.com/services/...",
        "channel": "#operations",
        "events": ["alert.escalated", "device.low_health"]
    }
}
"""

from django.db import models

# This module intentionally minimal - configurations stored in TypeAssist
