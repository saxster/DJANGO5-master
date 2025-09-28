"""
Logging configuration validation utilities for Conversational Onboarding API

This module provides functions to validate that all required loggers are properly
configured for production use, with appropriate handlers, formatters, and retention policies.
"""
import logging
from pathlib import Path
from django.conf import settings


def validate_logger_configuration() -> Dict[str, Any]:
    """
    Validate that all required loggers for the onboarding API are properly configured

    Returns:
        Dict with validation results and recommendations
    """
    validation_result = {
        'is_valid': True,
        'logger_status': {},
        'warnings': [],
        'recommendations': [],
        'missing_loggers': [],
        'handler_issues': [],
        'file_path_issues': []
    }

    # Required loggers for onboarding API
    required_loggers = {
        'audit': {
            'description': 'Audit trail for security and compliance events',
            'required_handlers': ['security_file', 'app_file'],
            'min_level': logging.INFO,
            'retention_days': 90
        },
        'metrics': {
            'description': 'Performance and usage metrics',
            'required_handlers': ['app_file'],
            'min_level': logging.INFO,
            'retention_days': 30
        },
        'django': {
            'description': 'General Django framework logs',
            'required_handlers': ['app_file'],
            'min_level': logging.INFO,
            'retention_days': 30
        },
        'security': {
            'description': 'Security-related events and violations',
            'required_handlers': ['security_file'],
            'min_level': logging.INFO,
            'retention_days': 90
        }
    }

    # Check if logging configuration exists
    logging_config = getattr(settings, 'LOGGING_CONFIG_', None)
    if not logging_config:
        validation_result['is_valid'] = False
        validation_result['warnings'].append('LOGGING_CONFIG_ not found in settings')
        validation_result['recommendations'].append('Configure LOGGING_CONFIG_ with required loggers')
        return validation_result

    configured_loggers = logging_config.get('loggers', {})
    configured_handlers = logging_config.get('handlers', {})

    # Validate each required logger
    for logger_name, logger_config in required_loggers.items():
        logger_status = {
            'exists': logger_name in configured_loggers,
            'handlers_configured': [],
            'missing_handlers': [],
            'level_appropriate': False,
            'issues': []
        }

        if logger_name not in configured_loggers:
            validation_result['missing_loggers'].append(logger_name)
            logger_status['issues'].append(f'Logger {logger_name} not configured')
            validation_result['is_valid'] = False
        else:
            logger_def = configured_loggers[logger_name]
            configured_handler_names = logger_def.get('handlers', [])

            # Check required handlers
            for required_handler in logger_config['required_handlers']:
                if required_handler in configured_handler_names:
                    logger_status['handlers_configured'].append(required_handler)
                else:
                    logger_status['missing_handlers'].append(required_handler)
                    logger_status['issues'].append(f'Missing required handler: {required_handler}')

            # Check logging level
            logger_level = getattr(logging, logger_def.get('level', 'INFO').upper(), logging.INFO)
            if logger_level <= logger_config['min_level']:
                logger_status['level_appropriate'] = True
            else:
                logger_status['issues'].append(
                    f'Log level {logger_def.get("level", "INFO")} is higher than recommended minimum'
                )

        validation_result['logger_status'][logger_name] = logger_status

    # Validate handler configurations
    critical_handlers = ['security_file', 'app_file', 'error_file']
    for handler_name in critical_handlers:
        if handler_name not in configured_handlers:
            validation_result['handler_issues'].append(f'Critical handler {handler_name} not configured')
            validation_result['is_valid'] = False
        else:
            handler_def = configured_handlers[handler_name]

            # Check if file handlers have valid file paths
            if 'File' in handler_def.get('class', ''):
                filename = handler_def.get('filename')
                if filename:
                    log_path = Path(filename).parent
                    if not log_path.exists():
                        validation_result['file_path_issues'].append(
                            f'Log directory for {handler_name} does not exist: {log_path}'
                        )
                        validation_result['warnings'].append(
                            f'Log directory {log_path} should be created before logging starts'
                        )

    # Generate recommendations based on validation results
    if validation_result['missing_loggers']:
        validation_result['recommendations'].append(
            f'Add missing loggers: {", ".join(validation_result["missing_loggers"])}'
        )

    if validation_result['handler_issues']:
        validation_result['recommendations'].append(
            'Configure missing handlers for critical logging functionality'
        )

    if validation_result['file_path_issues']:
        validation_result['recommendations'].append(
            'Create log directories before starting the application'
        )

    # Production-specific recommendations
    if not settings.DEBUG:
        if 'console' in [h for logger_config in configured_loggers.values()
                        for h in logger_config.get('handlers', [])]:
            validation_result['warnings'].append(
                'Console handlers detected in production - consider removing for performance'
            )

    return validation_result


def check_logger_accessibility() -> Dict[str, Any]:
    """
    Check that all onboarding API loggers can be accessed and used

    Returns:
        Dict with accessibility test results
    """
    test_results = {
        'accessible_loggers': [],
        'inaccessible_loggers': [],
        'test_errors': []
    }

    required_loggers = ['audit', 'metrics', 'django', 'security']

    for logger_name in required_loggers:
        try:
            logger = logging.getLogger(logger_name)

            # Test that logger is configured (has handlers)
            if logger.handlers or logger.parent.handlers:
                test_results['accessible_loggers'].append(logger_name)

                # Test a debug log message (won't appear in production but tests the pipeline)
                logger.debug(f'Logger accessibility test for {logger_name}')
            else:
                test_results['inaccessible_loggers'].append(logger_name)

        except (TypeError, ValidationError, ValueError) as e:
            test_results['test_errors'].append(f'Error testing logger {logger_name}: {str(e)}')

    return test_results


def get_logging_health_status() -> Dict[str, Any]:
    """
    Comprehensive logging health check for monitoring systems

    Returns:
        Complete health status for logging subsystem
    """
    config_validation = validate_logger_configuration()
    accessibility_test = check_logger_accessibility()

    health_status = {
        'overall_health': 'healthy' if config_validation['is_valid'] else 'degraded',
        'configuration_valid': config_validation['is_valid'],
        'configuration_details': config_validation,
        'logger_accessibility': accessibility_test,
        'recommendations': config_validation['recommendations'],
        'critical_issues': [],
        'warnings': config_validation['warnings']
    }

    # Identify critical issues
    if config_validation['missing_loggers']:
        health_status['critical_issues'].append(
            f'Missing critical loggers: {", ".join(config_validation["missing_loggers"])}'
        )

    if accessibility_test['inaccessible_loggers']:
        health_status['critical_issues'].append(
            f'Inaccessible loggers: {", ".join(accessibility_test["inaccessible_loggers"])}'
        )

    if health_status['critical_issues']:
        health_status['overall_health'] = 'critical'

    return health_status


def create_logger_setup_documentation() -> str:
    """
    Generate documentation for logger setup and configuration

    Returns:
        Markdown documentation string
    """
    return """
# Conversational Onboarding API - Logging Configuration Guide

## Overview

The Conversational Onboarding API uses a comprehensive logging system to track:
- Security events and audit trails
- Performance metrics and usage statistics
- Error conditions and debugging information
- User interactions and system behavior

## Required Loggers

### 1. Audit Logger (`audit`)
**Purpose**: Security and compliance audit trail
- **Level**: INFO and above
- **Handlers**: `security_file`, `app_file`
- **Retention**: 90 days minimum
- **Use Cases**:
  - User authentication events
  - Permission changes
  - Data access logging
  - Security violations

### 2. Metrics Logger (`metrics`)
**Purpose**: Performance and usage metrics
- **Level**: INFO and above
- **Handlers**: `app_file`
- **Retention**: 30 days minimum
- **Use Cases**:
  - API response times
  - Request volumes
  - Error rates
  - Resource utilization

### 3. Security Logger (`security`)
**Purpose**: Security-specific events
- **Level**: INFO and above
- **Handlers**: `security_file`, `console` (dev), `mail_admins` (critical)
- **Retention**: 90 days minimum
- **Use Cases**:
  - CSP violations
  - Rate limiting triggers
  - Suspicious activity detection
  - Access control violations

### 4. Django Logger (`django`)
**Purpose**: General application events
- **Level**: INFO and above
- **Handlers**: `app_file`, `console` (dev)
- **Retention**: 30 days minimum
- **Use Cases**:
  - General application flow
  - Configuration issues
  - Framework-level events

## Handler Configuration

### Security File Handler
```python
"security_file": {
    "class": "logging.handlers.TimedRotatingFileHandler",
    "filename": "/path/to/logs/security.log",
    "when": "midnight",
    "interval": 1,
    "backupCount": 90,
    "formatter": "detailed",
    "level": "INFO"
}
```

### Application File Handler
```python
"app_file": {
    "class": "logging.handlers.TimedRotatingFileHandler",
    "filename": "/path/to/logs/application.log",
    "when": "midnight",
    "interval": 1,
    "backupCount": 30,
    "formatter": "detailed"
}
```

## Production Recommendations

1. **File Permissions**: Ensure log files are writable by application user
2. **Disk Space**: Monitor disk usage for log directories
3. **Log Rotation**: Configure appropriate retention policies
4. **Performance**: Avoid console handlers in production
5. **Security**: Protect log files from unauthorized access
6. **Monitoring**: Set up alerts for critical log events

## Health Check Endpoint

Monitor logging health via: `GET /api/v1/onboarding/health/logging/`

This endpoint validates:
- Logger configuration completeness
- Handler accessibility
- File path validity
- Production readiness

## Troubleshooting

### Common Issues

1. **Logger Not Found**: Check LOGGING_CONFIG_ in settings.py
2. **No Log Output**: Verify handler configuration and file permissions
3. **Performance Issues**: Review log levels and disable verbose loggers
4. **Disk Full**: Implement log rotation and monitoring

### Debug Commands

```python
# Test logger accessibility
from apps.onboarding_api.utils.logging_validation import check_logger_accessibility
status = check_logger_accessibility()

# Validate configuration
from apps.onboarding_api.utils.logging_validation import validate_logger_configuration
validation = validate_logger_configuration()

# Full health check
from apps.onboarding_api.utils.logging_validation import get_logging_health_status
health = get_logging_health_status()
```

## Integration with External Systems

### ELK Stack Integration
Configure JSON formatters for structured logging:

```python
"json": {
    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
    "format": "%(asctime)s %(name)s %(levelname)s %(funcName)s %(message)s"
}
```

### Monitoring Systems
- **Audit logs** → SIEM systems
- **Metrics logs** → Time-series databases
- **Error logs** → Alert management systems
- **Security logs** → Security operations center

## Compliance Considerations

- **GDPR**: Ensure PII is not logged inappropriately
- **SOX**: Maintain audit trail integrity and retention
- **HIPAA**: Protect any healthcare-related information in logs
- **Industry Standards**: Follow organization-specific requirements
"""


if __name__ == '__main__':
    # Command-line validation
    import json

    print("Validating logging configuration...")
    health = get_logging_health_status()
    print(json.dumps(health, indent=2, default=str))