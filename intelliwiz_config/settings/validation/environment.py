"""
Environment validation and readiness checks.

Handles:
- Environment variable validation
- Environment-specific configuration checks
- Readiness verification before startup
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger('settings.environment')


def validate_environment_variables(required_vars: List[str]) -> Dict[str, str]:
    """
    Validate that required environment variables are set.

    Args:
        required_vars: List of environment variable names to check

    Returns:
        Dictionary of validated environment variables

    Raises:
        ValueError: If any required variable is missing
    """
    import os

    missing_vars = []
    validated_vars = {}

    for var_name in required_vars:
        value = os.environ.get(var_name)
        if not value:
            missing_vars.append(var_name)
        else:
            validated_vars[var_name] = value

    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"✅ All {len(required_vars)} required environment variables are set")
    return validated_vars


def check_environment_readiness(environment: str) -> Dict[str, Any]:
    """
    Check if the environment is ready for application startup.

    Args:
        environment: 'development', 'production', or 'test'

    Returns:
        Dictionary containing readiness status and issues

    Raises:
        RuntimeError: If critical environment checks fail
    """
    import os
    from pathlib import Path

    readiness = {
        'environment': environment,
        'ready': True,
        'issues': [],
        'warnings': [],
    }

    # Check database connectivity requirements
    db_host = os.environ.get('DBHOST')
    if not db_host and environment == 'production':
        readiness['issues'].append("DBHOST not set for production database")
        readiness['ready'] = False

    # Check required directories
    if environment == 'production':
        log_dir = '/var/log/youtility4'
        if not Path(log_dir).exists():
            readiness['warnings'].append(f"Log directory {log_dir} does not exist - will be created")

    # Check Redis availability for production
    if environment == 'production':
        redis_host = os.environ.get('REDIS_HOST')
        if not redis_host:
            readiness['warnings'].append("REDIS_HOST not set - Redis caching unavailable")

    # Check email configuration
    if environment == 'production':
        email_host = os.environ.get('AWS_SES_SMTP_USER')
        if not email_host:
            readiness['warnings'].append("AWS_SES_SMTP_USER not set - Email notifications disabled")

    # Report findings
    if readiness['ready']:
        logger.info(
            f"✅ Environment '{environment}' is ready",
            extra={'environment': environment}
        )
    else:
        msg = f"Environment '{environment}' not ready: {readiness['issues']}"
        logger.error(msg)
        raise RuntimeError(msg)

    if readiness['warnings']:
        logger.warning(
            f"⚠️  Environment warnings: {readiness['warnings']}",
            extra={'environment': environment}
        )

    return readiness


def get_environment_config(environment: str) -> Dict[str, Any]:
    """
    Get environment-specific configuration.

    Args:
        environment: 'development', 'production', or 'test'

    Returns:
        Dictionary of environment-specific settings
    """
    configs = {
        'development': {
            'DEBUG': True,
            'LOG_LEVEL': 'DEBUG',
            'DATABASE_TIMEOUT': 30,
            'CACHE_TIMEOUT': 300,
            'ENABLE_PROFILING': True,
        },
        'production': {
            'DEBUG': False,
            'LOG_LEVEL': 'INFO',
            'DATABASE_TIMEOUT': 10,
            'CACHE_TIMEOUT': 3600,
            'ENABLE_PROFILING': False,
        },
        'test': {
            'DEBUG': True,
            'LOG_LEVEL': 'ERROR',
            'DATABASE_TIMEOUT': 5,
            'CACHE_TIMEOUT': 0,
            'ENABLE_PROFILING': False,
        }
    }

    return configs.get(environment, configs['development'])


__all__ = [
    'validate_environment_variables',
    'check_environment_readiness',
    'get_environment_config',
]
