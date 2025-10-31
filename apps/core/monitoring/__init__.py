"""
Core Monitoring Package

Contains specialized monitoring and telemetry modules:
- sql_security_telemetry: SQL injection detection and monitoring
- google_maps_monitor: Google Maps API monitoring

NOTE: This package coexists with apps/core/monitoring.py module.
- monitoring.py: Production monitoring, logging config, performance timers
- monitoring/: Specialized security monitoring modules

MIGRATION NOTE (Oct 2025): Legacy query layer removed - use REST API monitoring
"""

__all__ = []
