"""
Test configuration settings for AI features
Environment-specific test configurations and thresholds
"""

import os
from typing import Dict, Any

# Test environment configuration
TEST_ENVIRONMENTS = {
    'local': {
        'database_url': 'sqlite:///test.db',
        'redis_url': 'redis://localhost:6379/1',
        'mock_external_apis': True,
        'verbose_logging': True
    },
    'ci': {
        'database_url': os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/test_youtility'),
        'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        'mock_external_apis': True,
        'verbose_logging': False
    },
    'docker': {
        'database_url': 'postgresql://postgres:postgres@db:5432/test_youtility',
        'redis_url': 'redis://redis:6379/0',
        'mock_external_apis': True,
        'verbose_logging': False
    }
}

# AI Model test configurations
AI_MODEL_TEST_CONFIG = {
    'face_recognition': {
        'embedding_dimensions': 512,
        'confidence_threshold': 0.7,
        'similarity_threshold': 0.3,
        'anti_spoofing_threshold': 0.5,
        'max_embeddings_per_user': 100,
        'mock_model_path': '/tmp/test_models/facenet.pkl'
    },
    'anomaly_detection': {
        'contamination_rate': 0.1,
        'n_estimators': 10,  # Reduced for testing
        'max_samples': 1000,
        'ensemble_size': 3,
        'mock_model_path': '/tmp/test_models/isolation_forest.pkl'
    },
    'behavioral_analytics': {
        'fraud_threshold': 0.7,
        'risk_score_threshold': 0.5,
        'pattern_history_days': 30,
        'min_samples_for_analysis': 5,
        'mock_model_path': '/tmp/test_models/fraud_detector.pkl'
    }
}

# Performance test thresholds
PERFORMANCE_THRESHOLDS = {
    'response_times': {
        'face_verification': 2.0,  # seconds
        'anomaly_detection': 1.0,  # seconds
        'fraud_analysis': 0.5,     # seconds
        'batch_processing': 5.0    # seconds per 100 items
    },
    'throughput': {
        'min_requests_per_second': 10,
        'max_concurrent_users': 100,
        'bulk_processing_rate': 1000  # items per minute
    },
    'resource_usage': {
        'max_memory_mb': 500,
        'max_cpu_percent': 80,
        'max_database_connections': 20
    }
}

# Security test configuration
SECURITY_TEST_CONFIG = {
    'authentication': {
        'max_login_attempts': 5,
        'lockout_duration': 300,  # seconds
        'password_strength_min': 8,
        'token_expiry': 3600      # seconds
    },
    'rate_limiting': {
        'requests_per_minute': 60,
        'requests_per_hour': 1000,
        'api_burst_limit': 10
    },
    'data_protection': {
        'encrypt_embeddings': True,
        'mask_pii_in_logs': True,
        'secure_deletion': True,
        'audit_trail': True
    },
    'vulnerability_scanning': {
        'bandit_severity_threshold': 'MEDIUM',
        'safety_ignore_ids': [],  # Known false positives
        'dependency_check_timeout': 300
    }
}

# Mock service configurations
MOCK_SERVICES = {
    'ml_models': {
        'sklearn_models': True,
        'face_recognition_lib': True,
        'opencv': True,
        'numpy_random_seed': 42
    },
    'external_apis': {
        'fraud_detection_api': {
            'enabled': True,
            'response_delay': 0.1,
            'success_rate': 0.95
        },
        'image_processing_api': {
            'enabled': True,
            'response_delay': 0.2,
            'success_rate': 0.98
        }
    },
    'storage': {
        'use_temp_directories': True,
        'cleanup_after_tests': True,
        'max_file_size_mb': 10
    }
}

# Test data generation settings
TEST_DATA_CONFIG = {
    'users': {
        'default_count': 10,
        'with_embeddings_ratio': 0.8,
        'with_profiles_ratio': 0.6,
        'active_ratio': 0.9
    },
    'embeddings': {
        'dimensions': 512,
        'confidence_range': (0.6, 0.95),
        'variations_per_user': 3,
        'quality_distribution': 'normal'
    },
    'attendance': {
        'records_per_user': 30,
        'time_range_days': 90,
        'fraud_ratio': 0.05,
        'anomaly_ratio': 0.1
    },
    'behavioral_data': {
        'pattern_consistency': 0.8,
        'seasonal_variation': True,
        'outlier_percentage': 5
    }
}

# Coverage requirements
COVERAGE_REQUIREMENTS = {
    'minimum_coverage': 80,  # percent
    'critical_modules': {
        'face_recognition.models': 95,
        'behavioral_analytics.fraud_detector': 90,
        'anomaly_detection.engines': 85
    },
    'exclude_patterns': [
        '*/migrations/*',
        '*/tests/*',
        '*/venv/*',
        '*/node_modules/*'
    ],
    'fail_under': 80
}

# Test execution settings
TEST_EXECUTION_CONFIG = {
    'parallel_workers': 4,
    'timeout_per_test': 30,  # seconds
    'max_test_duration': 1800,  # 30 minutes total
    'retry_flaky_tests': 2,
    'collect_performance_data': True,
    'generate_html_report': True
}

# Integration with external tools
EXTERNAL_TOOLS_CONFIG = {
    'codecov': {
        'enabled': True,
        'threshold': 80,
        'fail_on_decrease': True
    },
    'sonarqube': {
        'enabled': False,
        'quality_gate': 'Sonar way',
        'exclude_duplications': ['*/tests/*']
    },
    'docker': {
        'test_image': 'python:3.11-slim',
        'services': ['postgres:15', 'redis:7'],
        'network': 'test-network'
    }
}

# Notification settings
NOTIFICATION_CONFIG = {
    'slack': {
        'enabled': False,
        'webhook_url': os.getenv('SLACK_WEBHOOK_URL'),
        'channels': {
            'test_results': '#ai-test-results',
            'security_alerts': '#security-alerts',
            'performance_alerts': '#performance'
        }
    },
    'email': {
        'enabled': False,
        'recipients': ['ai-team@company.com'],
        'on_failure_only': True
    },
    'github': {
        'pr_comments': True,
        'status_checks': True,
        'deployment_protection': True
    }
}

# Environment-specific overrides
ENVIRONMENT_OVERRIDES = {
    'github_actions': {
        'parallel_workers': 2,  # Limited by CI resources
        'timeout_per_test': 60,
        'mock_services.external_apis.enabled': True
    },
    'local_development': {
        'verbose_logging': True,
        'parallel_workers': 1,
        'generate_html_report': True
    }
}

def get_test_config(environment: str = None) -> Dict[str, Any]:
    """
    Get test configuration for specified environment
    
    Args:
        environment: Test environment ('local', 'ci', 'docker')
        
    Returns:
        Complete test configuration dictionary
    """
    if environment is None:
        environment = os.getenv('TEST_ENVIRONMENT', 'local')
    
    # Start with base configuration
    config = {
        'environment': environment,
        'ai_models': AI_MODEL_TEST_CONFIG,
        'performance': PERFORMANCE_THRESHOLDS,
        'security': SECURITY_TEST_CONFIG,
        'mocks': MOCK_SERVICES,
        'test_data': TEST_DATA_CONFIG,
        'coverage': COVERAGE_REQUIREMENTS,
        'execution': TEST_EXECUTION_CONFIG,
        'external_tools': EXTERNAL_TOOLS_CONFIG,
        'notifications': NOTIFICATION_CONFIG
    }
    
    # Apply environment-specific settings
    if environment in TEST_ENVIRONMENTS:
        config['database'] = TEST_ENVIRONMENTS[environment]
    
    # Apply environment overrides
    current_env = os.getenv('CI') and 'github_actions' or 'local_development'
    if current_env in ENVIRONMENT_OVERRIDES:
        overrides = ENVIRONMENT_OVERRIDES[current_env]
        for key, value in overrides.items():
            if '.' in key:
                # Handle nested keys like 'mock_services.external_apis.enabled'
                keys = key.split('.')
                target = config
                for k in keys[:-1]:
                    target = target[k]
                target[keys[-1]] = value
            else:
                config[key] = value
    
    return config

def validate_test_environment():
    """
    Validate that the test environment is properly configured
    
    Returns:
        Dict with validation results
    """
    issues = []
    warnings = []
    
    # Check required environment variables
    required_vars = [
        'DJANGO_SETTINGS_MODULE',
        'DATABASE_URL'
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            issues.append(f"Missing required environment variable: {var}")
    
    # Check optional but recommended variables
    recommended_vars = [
        'REDIS_URL',
        'CELERY_BROKER_URL'
    ]
    
    for var in recommended_vars:
        if not os.getenv(var):
            warnings.append(f"Missing recommended environment variable: {var}")
    
    # Check if mock services should be enabled
    if os.getenv('CI'):
        if not os.getenv('MOCK_ML_MODELS'):
            warnings.append("MOCK_ML_MODELS not set in CI environment")
    
    # Check test data directories
    temp_dir = '/tmp/test_models'
    if not os.path.exists(temp_dir):
        try:
            os.makedirs(temp_dir, exist_ok=True)
        except OSError:
            issues.append(f"Cannot create test model directory: {temp_dir}")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'environment': os.getenv('TEST_ENVIRONMENT', 'unknown')
    }

# Export commonly used configurations
def get_mock_config():
    """Get mock service configuration"""
    return get_test_config()['mocks']

def get_performance_thresholds():
    """Get performance test thresholds"""
    return get_test_config()['performance']

def get_security_config():
    """Get security test configuration"""
    return get_test_config()['security']

def get_ai_model_config():
    """Get AI model test configuration"""
    return get_test_config()['ai_models']