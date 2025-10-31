"""
Unfold Admin Theme Configuration

Minimal configuration for Unfold admin theme.
Simplified to ensure compatibility and eliminate Error 500.

Author: Claude Code
Date: 2025-10-12
CLAUDE.md Compliance: Settings file (<200 lines)
"""
from django.utils.translation import gettext_lazy as _

# Unfold Admin Theme Configuration (Simplified for compatibility)
UNFOLD = {
    # Branding
    "SITE_TITLE": "IntelliWiz",
    "SITE_HEADER": "IntelliWiz Operations Center",
    "SITE_URL": "/",

    # Theme Colors (Purple)
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "192 132 252",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
        },
    },

}
