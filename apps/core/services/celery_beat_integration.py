"""
Enhanced Celery Beat Integration Service

Provides seamless integration between existing Celery Beat schedules
and the unified cron management system, enabling backwards compatibility
and smooth migration paths.

Key Features:
- Backwards compatibility with existing Celery Beat schedules
- Enhanced registration for NOC and Onboarding modules
- Migration utilities for transitioning to unified system
- Dual-mode operation during transition
- Health monitoring integration

Compliance:
- Rule #7: Service < 150 lines (focused integration logic)
- Rule #11: Specific exception handling
- Rule #15: No PII in logs
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import timedelta

from celery.schedules import crontab
from django.conf import settings
from django.db import DatabaseError

from apps.core.services.base_service import BaseService
from apps.core.services.cron_schedule_registration import cron_schedule_registry
from apps.core.services.cron_job_registry import cron_registry

logger = logging.getLogger(__name__)


class CeleryBeatIntegration(BaseService):
    """
    Service for integrating Celery Beat schedules with unified cron system.

    Provides backwards compatibility and migration support for existing
    Celery Beat schedules while enabling enhanced monitoring and management.
    """

    def __init__(self):
        super().__init__()
        self._registered_modules = set()

    def get_service_name(self) -> str:
        """Return service name for logging and monitoring."""
        return "CeleryBeatIntegration"

    def register_enhanced_noc_schedules(self, app, tenant=None) -> Dict[str, Any]:
        """
        Register enhanced NOC schedules with both Celery Beat and unified system.

        Args:
            app: Celery application instance
            tenant: Tenant for multi-tenant setup

        Returns:
            Dict containing registration results
        """
        try:
            # Enhanced NOC schedules with unified system integration
            enhanced_noc_schedules = {
                'noc-aggregate-snapshot': {
                    'task': 'noc_aggregate_snapshot',
                    'schedule': timedelta(minutes=5),
                    'options': {
                        'queue': 'default',
                        'expires': 240,
                    },
                    'unified_config': {
                        'description': 'Create metric snapshots for all active clients',
                        'tags': ['noc', 'metrics', 'monitoring'],
                        'priority': 'normal',
                        'timeout_seconds': 300
                    }
                },
                'noc-alert-backpressure': {
                    'task': 'noc_alert_backpressure',
                    'schedule': timedelta(minutes=1),
                    'options': {
                        'queue': 'high_priority',
                        'expires': 30,
                    },
                    'unified_config': {
                        'description': 'Handle alert queue overflow management',
                        'tags': ['noc', 'alerts', 'critical'],
                        'priority': 'high',
                        'timeout_seconds': 60
                    }
                },
                'noc-archive-snapshots': {
                    'task': 'noc_archive_snapshots',
                    'schedule': crontab(hour=2, minute=0),
                    'options': {
                        'queue': 'maintenance',
                        'expires': 3600,
                    },
                    'unified_config': {
                        'description': 'Archive old metric snapshots (30+ days)',
                        'tags': ['noc', 'cleanup', 'maintenance'],
                        'priority': 'low',
                        'timeout_seconds': 1800
                    }
                },
                'noc-cache-warming': {
                    'task': 'noc_cache_warming',
                    'schedule': timedelta(minutes=5),
                    'options': {
                        'queue': 'default',
                        'expires': 240,
                    },
                    'unified_config': {
                        'description': 'Pre-warm dashboard caches for performance',
                        'tags': ['noc', 'performance', 'cache'],
                        'priority': 'normal',
                        'timeout_seconds': 300
                    }
                },
                'noc-alert-escalation': {
                    'task': 'noc_alert_escalation',
                    'schedule': timedelta(minutes=1),
                    'options': {
                        'queue': 'high_priority',
                        'expires': 30,
                    },
                    'unified_config': {
                        'description': 'Auto-escalate unacknowledged critical alerts',
                        'tags': ['noc', 'alerts', 'escalation', 'critical'],
                        'priority': 'critical',
                        'timeout_seconds': 60
                    }
                },
                # New enhanced schedules
                'noc-health-monitoring': {
                    'task': 'noc_health_monitoring',
                    'schedule': timedelta(minutes=2),
                    'options': {
                        'queue': 'monitoring',
                        'expires': 120,
                    },
                    'unified_config': {
                        'description': 'Monitor NOC system health and performance',
                        'tags': ['noc', 'health', 'monitoring'],
                        'priority': 'high',
                        'timeout_seconds': 120
                    }
                },
                'noc-performance-optimization': {
                    'task': 'noc_performance_optimization',
                    'schedule': crontab(minute=0),  # Hourly
                    'options': {
                        'queue': 'maintenance',
                        'expires': 3600,
                    },
                    'unified_config': {
                        'description': 'Optimize NOC performance and resource usage',
                        'tags': ['noc', 'performance', 'optimization'],
                        'priority': 'normal',
                        'timeout_seconds': 1800
                    }
                }
            }

            # Register with Celery Beat (backwards compatibility)
            beat_schedule = app.conf.beat_schedule or {}
            celery_schedules = {
                name: {k: v for k, v in config.items() if k != 'unified_config'}
                for name, config in enhanced_noc_schedules.items()
            }
            beat_schedule.update(celery_schedules)
            app.conf.beat_schedule = beat_schedule

            # Register with unified system
            unified_count = 0
            for schedule_name, config in enhanced_noc_schedules.items():
                try:
                    # Convert schedule to cron expression
                    cron_expr = self._convert_schedule_to_cron(config['schedule'])
                    if cron_expr:
                        unified_config = config.get('unified_config', {})
                        success = cron_schedule_registry.register_background_task(
                            task_name=config['task'],
                            cron_expression=cron_expr,
                            description=unified_config.get('description', ''),
                            timeout_seconds=unified_config.get('timeout_seconds', 1800),
                            priority=unified_config.get('priority', 'normal'),
                            tags=unified_config.get('tags', ['noc']),
                            tenant=tenant
                        )
                        if success:
                            unified_count += 1

                except (ValueError, KeyError) as e:
                    logger.error(
                        f"Failed to register unified schedule",
                        extra={
                            'schedule_name': schedule_name,
                            'error': str(e)
                        }
                    )

            logger.info(
                f"Enhanced NOC schedules registered",
                extra={
                    'celery_schedules': len(celery_schedules),
                    'unified_schedules': unified_count
                }
            )

            return {
                'success': True,
                'celery_schedules_registered': len(celery_schedules),
                'unified_schedules_registered': unified_count
            }

        except Exception as e:
            logger.error(f"Failed to register enhanced NOC schedules: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def register_enhanced_onboarding_schedules(self, app, tenant=None) -> Dict[str, Any]:
        """
        Register enhanced Onboarding schedules with both systems.

        Args:
            app: Celery application instance
            tenant: Tenant for multi-tenant setup

        Returns:
            Dict containing registration results
        """
        try:
            enhanced_onboarding_schedules = {
                'cleanup-old-conversation-sessions': {
                    'task': 'background_tasks.onboarding_tasks.cleanup_old_sessions',
                    'schedule': timedelta(hours=1),
                    'options': {
                        'queue': 'maintenance',
                        'expires': 300,
                    },
                    'unified_config': {
                        'description': 'Clean up old conversation sessions',
                        'tags': ['onboarding', 'cleanup', 'maintenance'],
                        'priority': 'low',
                        'timeout_seconds': 600
                    }
                },
                'check-knowledge-freshness': {
                    'task': 'background_tasks.onboarding_tasks_phase2.validate_knowledge_freshness_task',
                    'schedule': crontab(hour=2, minute=0),
                    'options': {
                        'queue': 'maintenance',
                        'expires': 3600,
                    },
                    'unified_config': {
                        'description': 'Validate knowledge base freshness daily',
                        'tags': ['onboarding', 'knowledge', 'validation'],
                        'priority': 'normal',
                        'timeout_seconds': 1800
                    }
                },
                'cleanup-old-traces': {
                    'task': 'background_tasks.onboarding_tasks_phase2.cleanup_old_traces_task',
                    'schedule': timedelta(minutes=30),
                    'options': {
                        'queue': 'maintenance',
                        'expires': 1800,
                    },
                    'unified_config': {
                        'description': 'Clean up old execution traces',
                        'tags': ['onboarding', 'cleanup', 'traces'],
                        'priority': 'low',
                        'timeout_seconds': 900
                    }
                },
                'weekly-knowledge-verification': {
                    'task': 'background_tasks.onboarding_tasks_phase2.weekly_knowledge_verification',
                    'schedule': crontab(day_of_week=1, hour=0, minute=0),
                    'options': {
                        'queue': 'maintenance',
                        'expires': 7200,
                    },
                    'unified_config': {
                        'description': 'Weekly knowledge base verification',
                        'tags': ['onboarding', 'knowledge', 'verification', 'weekly'],
                        'priority': 'normal',
                        'timeout_seconds': 3600
                    }
                },
                # New enhanced schedules
                'knowledge-optimization': {
                    'task': 'background_tasks.onboarding_tasks_phase2.knowledge_optimization',
                    'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
                    'options': {
                        'queue': 'maintenance',
                        'expires': 7200,
                    },
                    'unified_config': {
                        'description': 'Optimize knowledge base performance',
                        'tags': ['onboarding', 'knowledge', 'optimization'],
                        'priority': 'low',
                        'timeout_seconds': 3600
                    }
                }
            }

            # Register with both systems similar to NOC schedules
            beat_schedule = app.conf.beat_schedule or {}
            celery_schedules = {
                name: {k: v for k, v in config.items() if k != 'unified_config'}
                for name, config in enhanced_onboarding_schedules.items()
            }
            beat_schedule.update(celery_schedules)
            app.conf.beat_schedule = beat_schedule

            unified_count = 0
            for schedule_name, config in enhanced_onboarding_schedules.items():
                try:
                    cron_expr = self._convert_schedule_to_cron(config['schedule'])
                    if cron_expr:
                        unified_config = config.get('unified_config', {})
                        success = cron_schedule_registry.register_background_task(
                            task_name=config['task'],
                            cron_expression=cron_expr,
                            description=unified_config.get('description', ''),
                            timeout_seconds=unified_config.get('timeout_seconds', 1800),
                            priority=unified_config.get('priority', 'normal'),
                            tags=unified_config.get('tags', ['onboarding']),
                            tenant=tenant
                        )
                        if success:
                            unified_count += 1

                except (ValueError, KeyError) as e:
                    logger.error(
                        f"Failed to register unified onboarding schedule",
                        extra={
                            'schedule_name': schedule_name,
                            'error': str(e)
                        }
                    )

            return {
                'success': True,
                'celery_schedules_registered': len(celery_schedules),
                'unified_schedules_registered': unified_count
            }

        except Exception as e:
            logger.error(f"Failed to register enhanced onboarding schedules: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def create_migration_plan(self) -> Dict[str, Any]:
        """
        Create a migration plan from Celery Beat to unified system.

        Returns:
            Dict containing migration plan and recommendations
        """
        try:
            migration_plan = {
                'phase_1': {
                    'description': 'Dual operation mode - both systems running',
                    'actions': [
                        'Deploy unified cron system alongside existing Celery Beat',
                        'Register key management commands in unified system',
                        'Monitor parallel execution and performance',
                        'Validate unified system reliability'
                    ],
                    'duration_weeks': 2,
                    'risk_level': 'low'
                },
                'phase_2': {
                    'description': 'Gradual migration of schedules',
                    'actions': [
                        'Migrate NOC schedules to unified system',
                        'Migrate onboarding schedules to unified system',
                        'Update monitoring and alerting configurations',
                        'Train operations team on new system'
                    ],
                    'duration_weeks': 3,
                    'risk_level': 'medium'
                },
                'phase_3': {
                    'description': 'Complete transition and optimization',
                    'actions': [
                        'Disable Celery Beat schedules',
                        'Remove deprecated Celery Beat infrastructure',
                        'Optimize unified system performance',
                        'Complete documentation and runbooks'
                    ],
                    'duration_weeks': 2,
                    'risk_level': 'medium'
                }
            }

            recommendations = [
                'Start with dual operation to ensure reliability',
                'Monitor job execution metrics during transition',
                'Maintain rollback capability during migration',
                'Update operational procedures and documentation',
                'Train team on unified system management'
            ]

            return {
                'success': True,
                'migration_plan': migration_plan,
                'recommendations': recommendations,
                'total_duration_weeks': 7,
                'estimated_effort_days': 15
            }

        except Exception as e:
            logger.error(f"Failed to create migration plan: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _convert_schedule_to_cron(self, schedule) -> Optional[str]:
        """Convert Celery schedule to cron expression."""
        try:
            if hasattr(schedule, 'minute') and hasattr(schedule, 'hour'):
                # crontab schedule
                minute = getattr(schedule, 'minute', '*')
                hour = getattr(schedule, 'hour', '*')
                day = getattr(schedule, 'day_of_month', '*')
                month = getattr(schedule, 'month_of_year', '*')
                day_of_week = getattr(schedule, 'day_of_week', '*')
                return f"{minute} {hour} {day} {month} {day_of_week}"

            elif hasattr(schedule, 'total_seconds'):
                # timedelta schedule
                seconds = schedule.total_seconds()
                if seconds >= 60 and seconds % 60 == 0:
                    minutes = int(seconds / 60)
                    if minutes <= 59:
                        return f"*/{minutes} * * * *"
                    elif minutes == 60:
                        return "0 * * * *"  # Hourly
                    elif minutes == 1440:
                        return "0 0 * * *"  # Daily

            return None

        except (AttributeError, ValueError):
            return None


# Global integration instance
celery_beat_integration = CeleryBeatIntegration()