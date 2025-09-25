"""
Test configuration for recommendation system
Provides configuration settings and utilities for recommendation system tests
"""

import os
import tempfile
from django.conf import settings
from django.test.utils import override_settings

# Test database configuration
TEST_DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'OPTIONS': {
            'timeout': 20,
        },
        'TEST': {
            'MIGRATE': True,
        }
    }
}

# Test cache configuration
TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    }
}

# Test logging configuration
TEST_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'DEBUG',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'test_logs/recommendation_tests.log',
            'formatter': 'verbose',
            'level': 'DEBUG',
        },
    },
    'loggers': {
        'apps.core.recommendation_engine': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.core.models.recommendation': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.core.middleware.recommendation_middleware': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.core.views.recommendation_views': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}

# Celery configuration for tests
TEST_CELERY_SETTINGS = {
    'CELERY_TASK_ALWAYS_EAGER': True,
    'CELERY_TASK_EAGER_PROPAGATES': True,
    'CELERY_BROKER_URL': 'memory://',
    'CELERY_RESULT_BACKEND': 'cache+memory://',
}

# Email configuration for tests
TEST_EMAIL_SETTINGS = {
    'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
}

# Media and static files for tests
TEST_MEDIA_ROOT = os.path.join(tempfile.gettempdir(), 'test_media')
TEST_STATIC_ROOT = os.path.join(tempfile.gettempdir(), 'test_static')

# Performance test thresholds
PERFORMANCE_THRESHOLDS = {
    'recommendation_generation': {
        'single_user_max_time': 1.0,  # seconds
        'batch_users_max_time': 30.0,  # seconds for 50 users
        'max_memory_per_user': 2.5 * 1024 * 1024,  # 2.5MB
    },
    'similarity_calculation': {
        'max_time': 5.0,  # seconds for 100 users
        'time_per_comparison': 0.1,  # seconds
    },
    'api_response': {
        'recommendation_api_max': 0.5,  # seconds
        'interaction_api_max': 0.2,  # seconds
    },
    'websocket': {
        'throughput_min': 50,  # messages per second
        'connection_time_max': 10.0,  # seconds for 20 connections
    },
    'database': {
        'max_queries_per_recommendation': 20,
        'avg_query_time_max': 0.1,  # seconds
        'max_query_time': 0.5,  # seconds
    }
}

# Edge case test data
EDGE_CASE_DATA = {
    'large_similarity_vector_size': 10000,
    'max_concurrent_connections': 20,
    'max_test_users': 200,
    'extreme_relevance_scores': [float('inf'), float('-inf'), float('nan'), -10.0, 10.0],
    'invalid_similarity_scores': [2.0, -2.0, float('nan'), float('inf')],
    'large_json_field_entries': 10000,
    'massive_string_length': 100000,
}

# Mock data configurations
MOCK_DATA_CONFIG = {
    'default_user_count': 10,
    'default_recommendations_per_user': 5,
    'default_similarity_count': 3,
    'heatmap_sessions_per_user': 8,
    'clicks_per_session': 3,
    'time_range_days': 30,
}

# Test environment settings
TEST_ENVIRONMENT = {
    'DEBUG': True,
    'TESTING': True,
    'USE_TZ': True,
    'TIME_ZONE': 'UTC',
    'LANGUAGE_CODE': 'en-us',
    'SECRET_KEY': 'test-secret-key-for-recommendation-tests-only',
}

# Django apps required for recommendation tests
RECOMMENDATION_TEST_APPS = [
    'apps.core',
    'apps.ab_testing',
    'tests',
]

# Middleware for recommendation tests
RECOMMENDATION_TEST_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.core.middleware.recommendation_middleware.RecommendationMiddleware',
]

# URL configuration for tests
TEST_ROOT_URLCONF = 'intelliwiz_config.urls'

class RecommendationTestSettings:
    """
    Context manager for recommendation system test settings
    """
    
    def __init__(self, **overrides):
        self.overrides = overrides
        self.original_settings = {}
    
    def __enter__(self):
        # Create log directory
        log_dir = 'test_logs'
        os.makedirs(log_dir, exist_ok=True)
        
        # Prepare test settings
        test_settings = {
            **TEST_ENVIRONMENT,
            'DATABASES': TEST_DATABASES,
            'CACHES': TEST_CACHES,
            'LOGGING': TEST_LOGGING,
            'MEDIA_ROOT': TEST_MEDIA_ROOT,
            'STATIC_ROOT': TEST_STATIC_ROOT,
            'ROOT_URLCONF': TEST_ROOT_URLCONF,
            'MIDDLEWARE': RECOMMENDATION_TEST_MIDDLEWARE,
            **TEST_CELERY_SETTINGS,
            **TEST_EMAIL_SETTINGS,
            **self.overrides
        }
        
        # Store original settings
        for key, value in test_settings.items():
            if hasattr(settings, key):
                self.original_settings[key] = getattr(settings, key)
            setattr(settings, key, value)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original settings
        for key, value in self.original_settings.items():
            setattr(settings, key, value)
        
        # Clean up temporary files
        import shutil
        for temp_dir in [TEST_MEDIA_ROOT, TEST_STATIC_ROOT]:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)


def get_test_settings_override(**overrides):
    """
    Get Django settings override for recommendation tests
    """
    return override_settings(
        DATABASES=TEST_DATABASES,
        CACHES=TEST_CACHES,
        LOGGING=TEST_LOGGING,
        MEDIA_ROOT=TEST_MEDIA_ROOT,
        STATIC_ROOT=TEST_STATIC_ROOT,
        **TEST_CELERY_SETTINGS,
        **TEST_EMAIL_SETTINGS,
        **overrides
    )


def setup_test_environment():
    """
    Set up test environment for recommendation system tests
    """
    # Create necessary directories
    os.makedirs('test_logs', exist_ok=True)
    os.makedirs(TEST_MEDIA_ROOT, exist_ok=True)
    os.makedirs(TEST_STATIC_ROOT, exist_ok=True)
    
    # Set environment variables for testing
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
    os.environ['TESTING'] = '1'


def cleanup_test_environment():
    """
    Clean up test environment after recommendation system tests
    """
    import shutil
    
    # Remove temporary directories
    for temp_dir in [TEST_MEDIA_ROOT, TEST_STATIC_ROOT]:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    # Clear environment variables
    if 'TESTING' in os.environ:
        del os.environ['TESTING']


# Test data generators
class TestDataGenerator:
    """
    Generate test data for recommendation system tests
    """
    
    @staticmethod
    def generate_user_behavior_data(num_users=10):
        """Generate user behavior data for testing"""
        from tests.factories.heatmap_factories import UserFactory
        from tests.factories.recommendation_factories import UserBehaviorProfileFactory
        
        users_data = []
        for i in range(num_users):
            user = UserFactory.build()
            profile = UserBehaviorProfileFactory.build(
                user=user,
                preferred_pages={f'/page{j}/': 10 - j for j in range(5)},
                similarity_vector=[float(j + i * 0.1) for j in range(10)]
            )
            users_data.append({'user': user, 'profile': profile})
        
        return users_data
    
    @staticmethod
    def generate_recommendation_scenario(num_users=10, recs_per_user=5):
        """Generate complete recommendation test scenario"""
        from tests.factories.recommendation_factories import create_recommendation_scenario
        return create_recommendation_scenario(
            num_users=num_users, 
            recommendations_per_user=recs_per_user
        )
    
    @staticmethod
    def generate_edge_case_data():
        """Generate edge case test data"""
        return {
            'extreme_vectors': [
                [float('inf')] * 10,
                [float('nan')] * 10,
                [0.0] * 10,
                list(range(10000)),  # Very large vector
            ],
            'invalid_scores': EDGE_CASE_DATA['invalid_similarity_scores'],
            'large_json_data': {f'key{i}': f'value{i}' for i in range(10000)},
            'empty_data': {
                'preferred_pages': {},
                'similarity_vector': [],
                'content_metadata': {}
            }
        }


# Export commonly used configurations
__all__ = [
    'TEST_DATABASES',
    'TEST_CACHES',
    'PERFORMANCE_THRESHOLDS',
    'EDGE_CASE_DATA',
    'MOCK_DATA_CONFIG',
    'RecommendationTestSettings',
    'get_test_settings_override',
    'setup_test_environment',
    'cleanup_test_environment',
    'TestDataGenerator',
]