"""
Enhanced test fixtures and infrastructure for Information Architecture testing
Provides comprehensive fixtures, factories, and utilities for IA test suite
"""
import pytest
from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.core.cache import cache
from django.utils import timezone
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import factory
import tempfile
import os
import json

User = get_user_model()


# ============================================================================
# USER FACTORIES AND FIXTURES
# ============================================================================

class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating test users with different permission levels"""
    
    class Meta:
        model = User
        django_get_or_create = ('username',)
    
    username = factory.Sequence(lambda n: f'testuser{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    is_superuser = False


@pytest.fixture
def user_factory():
    """Factory for creating users"""
    return UserFactory


@pytest.fixture
def regular_user():
    """Regular user with basic permissions"""
    return UserFactory(
        username='regular_user',
        password='regularpass123'
    )


@pytest.fixture
def staff_user():
    """Staff user with elevated permissions"""
    return UserFactory(
        username='staff_user',
        password='staffpass123',
        is_staff=True
    )


@pytest.fixture
def admin_user():
    """Admin user with full permissions"""
    return UserFactory(
        username='admin_user',
        password='adminpass123',
        is_staff=True,
        is_superuser=True
    )


@pytest.fixture
def users_all_types():
    """Fixture providing all user types"""
    return {
        'regular': UserFactory(username='regular_test'),
        'staff': UserFactory(username='staff_test', is_staff=True),
        'admin': UserFactory(username='admin_test', is_staff=True, is_superuser=True)
    }


# ============================================================================
# REQUEST AND CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def rf():
    """Request factory for creating mock requests"""
    return RequestFactory()


@pytest.fixture
def client():
    """Django test client"""
    return Client()


@pytest.fixture
def authenticated_client(client, regular_user):
    """Client authenticated with regular user"""
    client.force_login(regular_user)
    return client


@pytest.fixture
def staff_client(client, staff_user):
    """Client authenticated with staff user"""
    client.force_login(staff_user)
    return client


@pytest.fixture
def admin_client(client, admin_user):
    """Client authenticated with admin user"""
    client.force_login(admin_user)
    return client


@pytest.fixture
def mock_request(rf, regular_user):
    """Mock request with authenticated user and session"""
    request = rf.get('/')
    request.user = regular_user
    
    # Add session middleware
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    
    # Add session data
    request.session['user_id'] = regular_user.id
    request.session['session_key'] = 'test_session_key'
    
    return request


@pytest.fixture
def mock_request_with_meta(mock_request):
    """Mock request with META data for testing"""
    mock_request.META = {
        'QUERY_STRING': 'param1=value1&param2=value2',
        'HTTP_USER_AGENT': 'Mozilla/5.0 Test Browser',
        'REMOTE_ADDR': '127.0.0.1',
        'HTTP_HOST': 'testserver'
    }
    return mock_request


# ============================================================================
# URL MAPPING TEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def url_mapping_test_cases():
    """Complete URL mapping test cases for parametrized testing"""
    from apps.core.url_router_optimized import OptimizedURLRouter
    
    # Convert URL mappings to test cases with metadata
    test_cases = []
    
    for old_url, new_url in OptimizedURLRouter.URL_MAPPINGS.items():
        # Determine domain
        domain = 'unknown'
        if new_url.startswith('operations/'):
            domain = 'operations'
        elif new_url.startswith('assets/'):
            domain = 'assets'
        elif new_url.startswith('people/'):
            domain = 'people'
        elif new_url.startswith('help-desk/'):
            domain = 'help-desk'
        elif new_url.startswith('reports/'):
            domain = 'reports'
        elif new_url.startswith('admin/'):
            domain = 'admin'
        elif new_url.startswith('api/'):
            domain = 'api'
        elif new_url.startswith('auth/'):
            domain = 'auth'
        elif new_url.startswith('monitoring/'):
            domain = 'monitoring'
        
        # Determine if URL has parameters
        has_params = '<str:' in old_url or '<int:' in old_url
        
        test_cases.append({
            'old_url': old_url,
            'new_url': new_url,
            'domain': domain,
            'has_params': has_params,
            'is_critical': domain in ['operations', 'assets', 'people'],
            'test_id': f"{domain}_{old_url.replace('/', '_').replace('<', '').replace('>', '').replace(':', '_')}"
        })
    
    return test_cases


@pytest.fixture
def critical_url_mappings(url_mapping_test_cases):
    """Only critical URL mappings for focused testing"""
    return [case for case in url_mapping_test_cases if case['is_critical']]


@pytest.fixture
def domain_grouped_urls(url_mapping_test_cases):
    """URL mappings grouped by domain"""
    grouped = {}
    for case in url_mapping_test_cases:
        domain = case['domain']
        if domain not in grouped:
            grouped[domain] = []
        grouped[domain].append(case)
    return grouped


# ============================================================================
# NAVIGATION AND ANALYTICS FIXTURES
# ============================================================================

@pytest.fixture
def navigation_analytics_data():
    """Mock navigation analytics data for testing"""
    return {
        'popular_paths': {
            '/operations/tasks/': {
                'count': 150,
                'avg_response_time': 0.8,
                'users': {'user1', 'user2', 'user3'},
                'last_accessed': datetime.now()
            },
            '/assets/': {
                'count': 120,
                'avg_response_time': 1.2,
                'users': {'user1', 'user4'},
                'last_accessed': datetime.now() - timedelta(hours=2)
            },
            '/people/': {
                'count': 80,
                'avg_response_time': 0.6,
                'users': {'user2', 'user3'},
                'last_accessed': datetime.now() - timedelta(hours=1)
            }
        },
        'dead_urls': {
            '/broken/link/': {
                'count': 25,
                'users': {'user1'},
                'last_accessed': datetime.now() - timedelta(days=1)
            },
            '/old/path/': {
                'count': 10,
                'users': {'user2'},
                'last_accessed': datetime.now() - timedelta(days=3)
            }
        },
        'deprecated_usage': {
            'schedhuler/jobneedtasks/': {
                'count': 45,
                'users': {'user1', 'user2'},
                'last_accessed': datetime.now() - timedelta(hours=6),
                'new_url': 'operations/tasks/'
            },
            'activity/asset/': {
                'count': 30,
                'users': {'user3'},
                'last_accessed': datetime.now() - timedelta(hours=12),
                'new_url': 'assets/'
            }
        },
        'user_flows': {
            'session_123': {
                'paths': ['/dashboard/', '/operations/tasks/', '/operations/tours/'],
                'timestamps': [
                    datetime.now() - timedelta(minutes=30),
                    datetime.now() - timedelta(minutes=25),
                    datetime.now() - timedelta(minutes=20)
                ]
            },
            'session_456': {
                'paths': ['/dashboard/', '/assets/', '/assets/maintenance/'],
                'timestamps': [
                    datetime.now() - timedelta(minutes=45),
                    datetime.now() - timedelta(minutes=40),
                    datetime.now() - timedelta(minutes=35)
                ]
            }
        }
    }


@pytest.fixture
def url_usage_analytics():
    """URL usage analytics for migration tracking"""
    return {
        'schedhuler/jobneedtasks/': {
            'count': 75,
            'users': {'user1', 'user2', 'user3'},
            'last_accessed': datetime.now() - timedelta(hours=2),
            'new_url': 'operations/tasks/'
        },
        'activity/asset/': {
            'count': 50,
            'users': {'user1', 'user4'},
            'last_accessed': datetime.now() - timedelta(hours=1),
            'new_url': 'assets/'
        },
        'peoples/people/': {
            'count': 35,
            'users': {'user2', 'user3'},
            'last_accessed': datetime.now() - timedelta(minutes=30),
            'new_url': 'people/'
        },
        'helpdesk/ticket/': {
            'count': 20,
            'users': {'user1'},
            'last_accessed': datetime.now() - timedelta(hours=4),
            'new_url': 'help-desk/tickets/'
        }
    }


@pytest.fixture
def navigation_menu_test_data():
    """Test data for navigation menu testing"""
    return {
        'main_menu': [
            {
                'name': 'Dashboard',
                'url': '/dashboard/',
                'icon': 'dashboard',
                'capability': 'view_dashboard'
            },
            {
                'name': 'Operations',
                'url': '/operations/',
                'icon': 'settings',
                'capability': 'view_operations',
                'children': [
                    {'name': 'Tasks', 'url': '/operations/tasks/'},
                    {'name': 'Tours', 'url': '/operations/tours/'},
                    {'name': 'Work Orders', 'url': '/operations/work-orders/'}
                ]
            },
            {
                'name': 'Assets',
                'url': '/assets/',
                'icon': 'business',
                'capability': 'view_assets',
                'children': [
                    {'name': 'Inventory', 'url': '/assets/'},
                    {'name': 'Maintenance', 'url': '/assets/maintenance/'},
                    {'name': 'Locations', 'url': '/assets/locations/'}
                ]
            }
        ],
        'admin_menu': [
            {
                'name': 'Administration',
                'url': '/admin/',
                'icon': 'admin_panel_settings',
                'capability': 'view_admin',
                'children': [
                    {'name': 'Business Units', 'url': '/admin/business-units/'},
                    {'name': 'Clients', 'url': '/admin/clients/'},
                    {'name': 'Configuration', 'url': '/admin/config/'}
                ]
            }
        ]
    }


# ============================================================================
# CACHE AND PERFORMANCE FIXTURES
# ============================================================================

@pytest.fixture
def clean_cache():
    """Ensure cache is clean before and after tests"""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def mock_cache():
    """Mock cache for testing without affecting real cache"""
    with patch('django.core.cache.cache') as mock_cache_obj:
        mock_cache_obj.get.return_value = None
        mock_cache_obj.set.return_value = True
        mock_cache_obj.delete.return_value = True
        mock_cache_obj.clear.return_value = True
        yield mock_cache_obj


@pytest.fixture
def performance_test_data():
    """Data for performance testing"""
    return {
        'target_times': {
            'redirect': 0.05,  # 50ms
            'page_load': 2.0,  # 2 seconds
            'menu_render': 0.5,  # 500ms
            'analytics_query': 0.1  # 100ms
        },
        'load_test_urls': [
            '/operations/tasks/',
            '/assets/',
            '/people/',
            '/help-desk/tickets/',
            '/reports/download/'
        ],
        'concurrent_users': [5, 10, 20],
        'test_duration': 30  # seconds
    }


# ============================================================================
# MIDDLEWARE TESTING FIXTURES
# ============================================================================

@pytest.fixture
def mock_middleware_response():
    """Mock middleware response for testing"""
    response = Mock()
    response.status_code = 200
    response.content = b'Mock response content'
    response.headers = {'Content-Type': 'text/html'}
    return response


@pytest.fixture
def navigation_tracking_data():
    """Test data for navigation tracking middleware"""
    return {
        'tracking_patterns': [
            '/operations/tasks/*',
            '/assets/*',
            '/people/attendance/*'
        ],
        'excluded_patterns': [
            '/static/*',
            '/media/*',
            '/__debug__/*',
            '/admin/jsi18n/*'
        ],
        'sample_requests': [
            {'path': '/operations/tasks/', 'user': 'user1', 'response_time': 0.8},
            {'path': '/assets/123/', 'user': 'user2', 'response_time': 1.2},
            {'path': '/people/attendance/', 'user': 'user1', 'response_time': 0.6}
        ]
    }


# ============================================================================
# TEMPLATE TESTING FIXTURES
# ============================================================================

@pytest.fixture
def template_test_contexts():
    """Test contexts for template rendering"""
    return {
        'basic_context': {
            'user': UserFactory(),
            'request': Mock(),
            'title': 'Test Page'
        },
        'sidebar_context': {
            'user': UserFactory(is_staff=True),
            'request': Mock(),
            'navigation_menu': [],
            'current_url': '/operations/tasks/'
        },
        'dashboard_context': {
            'user': UserFactory(is_superuser=True),
            'request': Mock(),
            'analytics_data': {},
            'recent_activities': []
        }
    }


@pytest.fixture
def template_directories():
    """Template directories for testing"""
    return [
        'frontend/templates/globals/',
        'frontend/templates/schedhuler/',
        'frontend/templates/activity/',
        'frontend/templates/attendance/',
        'frontend/templates/core/',
        'frontend/templates/base/'
    ]


# ============================================================================
# E2E TESTING FIXTURES
# ============================================================================

@pytest.fixture
def selenium_driver():
    """Selenium WebDriver for E2E testing"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        yield driver
        driver.quit()
    except Exception:
        pytest.skip("WebDriver not available")


@pytest.fixture
def e2e_test_urls():
    """URLs for E2E navigation testing"""
    return {
        'critical_paths': [
            '/',
            '/operations/tasks/',
            '/assets/',
            '/people/',
            '/help-desk/tickets/'
        ],
        'user_journeys': [
            # Task management journey
            ['/', '/operations/', '/operations/tasks/', '/operations/tasks/create/'],
            # Asset management journey
            ['/', '/assets/', '/assets/maintenance/', '/assets/maintenance/schedule/'],
            # People management journey
            ['/', '/people/', '/people/attendance/', '/people/groups/']
        ],
        'legacy_redirects': [
            ('schedhuler/jobneedtasks/', '/operations/tasks/'),
            ('activity/asset/', '/assets/'),
            ('peoples/people/', '/people/')
        ]
    }


# ============================================================================
# TEST CONFIGURATION FIXTURES
# ============================================================================

@pytest.fixture
def test_settings():
    """Test-specific Django settings"""
    return {
        'DEBUG': True,
        'USE_OPTIMIZED_URLS': True,
        'CACHES': {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            }
        },
        'LOGGING': {
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                },
            },
            'loggers': {
                'apps.core.url_router_optimized': {
                    'handlers': ['console'],
                    'level': 'DEBUG',
                },
            },
        }
    }


@pytest.fixture
def temporary_file():
    """Temporary file for testing"""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        yield f
    os.unlink(f.name)


@pytest.fixture
def temporary_directory():
    """Temporary directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing"""
    mock_now = datetime(2024, 1, 1, 12, 0, 0)
    
    with patch('apps.core.url_router_optimized.datetime') as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield mock_dt


@pytest.fixture
def json_response_mock():
    """Mock JSON response for API testing"""
    def create_json_response(data, status_code=200):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = data
        response.content = json.dumps(data).encode()
        response.headers = {'Content-Type': 'application/json'}
        return response
    
    return create_json_response


@pytest.fixture
def assert_helpers():
    """Helper assertion functions for testing"""
    class AssertHelpers:
        @staticmethod
        def assert_url_redirect(response, expected_url, status_code=301):
            """Assert URL redirect with specific status code"""
            assert response.status_code == status_code
            assert response.url == expected_url
        
        @staticmethod
        def assert_performance_within_limit(elapsed_time, limit, operation=""):
            """Assert operation completed within time limit"""
            assert elapsed_time < limit, f"{operation} took {elapsed_time:.3f}s (limit: {limit}s)"
        
        @staticmethod
        def assert_contains_keywords(text, keywords, min_matches=1):
            """Assert text contains minimum number of keywords"""
            text_lower = text.lower()
            matches = sum(1 for keyword in keywords if keyword.lower() in text_lower)
            assert matches >= min_matches, f"Text should contain at least {min_matches} keywords from {keywords}"
        
        @staticmethod
        def assert_valid_url_structure(url):
            """Assert URL follows valid structure"""
            assert url.startswith('/'), "URL should start with '/'"
            assert not url.endswith('//'), "URL should not end with '//'"
            assert '__' not in url, "URL should not contain '__'"
    
    return AssertHelpers()


# ============================================================================
# RECOMMENDATION SYSTEM FIXTURES
# ============================================================================

@pytest.fixture
def recommendation_test_user():
    """Create a test user for recommendation system tests"""
    from tests.factories.heatmap_factories import UserFactory as RecommendationUserFactory
    return RecommendationUserFactory()


@pytest.fixture
def recommendation_admin_user():
    """Create an admin user for recommendation system tests"""
    from tests.factories.heatmap_factories import UserFactory as RecommendationUserFactory
    return RecommendationUserFactory(is_staff=True, is_superuser=True)


@pytest.fixture
def multiple_recommendation_users():
    """Create multiple test users for recommendation system tests"""
    from tests.factories.heatmap_factories import UserFactory as RecommendationUserFactory
    return [RecommendationUserFactory() for _ in range(5)]


@pytest.fixture
def user_with_behavior_profile():
    """Create a user with behavior profile for testing"""
    from tests.factories.heatmap_factories import UserFactory as RecommendationUserFactory
    from tests.factories.recommendation_factories import UserBehaviorProfileFactory
    
    user = RecommendationUserFactory()
    profile = UserBehaviorProfileFactory(user=user)
    return user, profile


@pytest.fixture
def user_with_recommendations():
    """Create a user with sample recommendations"""
    from tests.factories.heatmap_factories import UserFactory as RecommendationUserFactory
    from tests.factories.recommendation_factories import (
        UserBehaviorProfileFactory, ContentRecommendationFactory
    )
    
    user = RecommendationUserFactory()
    profile = UserBehaviorProfileFactory(user=user)
    recommendations = [
        ContentRecommendationFactory(user=user) for _ in range(3)
    ]
    return user, profile, recommendations


@pytest.fixture
def recommendation_test_scenario():
    """Create a complete recommendation test scenario"""
    from tests.factories.recommendation_factories import create_recommendation_scenario
    return create_recommendation_scenario(num_users=10, recommendations_per_user=5)


@pytest.fixture
def mock_recommendation_engine():
    """Mock recommendation engine for testing"""
    with patch('apps.core.recommendation_engine.RecommendationEngine') as mock_engine_class:
        mock_engine = Mock()
        mock_engine.generate_user_recommendations.return_value = []
        mock_engine.generate_navigation_recommendations.return_value = []
        mock_engine_class.return_value = mock_engine
        yield mock_engine


@pytest.fixture
def performance_test_recommendation_data():
    """Create data for recommendation performance testing"""
    from tests.factories.heatmap_factories import UserFactory as RecommendationUserFactory
    from tests.factories.recommendation_factories import (
        UserBehaviorProfileFactory, ContentRecommendationFactory
    )
    
    users = [RecommendationUserFactory() for _ in range(20)]
    profiles = []
    recommendations = []
    
    for user in users:
        profile = UserBehaviorProfileFactory(user=user)
        profiles.append(profile)
        
        user_recs = [
            ContentRecommendationFactory(user=user) for _ in range(3)
        ]
        recommendations.extend(user_recs)
    
    return {
        'users': users,
        'profiles': profiles,
        'recommendations': recommendations
    }


@pytest.fixture
def mock_websocket_communicator():
    """Mock WebSocket communicator for testing"""
    class MockCommunicator:
        def __init__(self):
            self.connected = False
            self.messages = []
        
        async def connect(self):
            self.connected = True
            return True, None
        
        async def disconnect(self):
            self.connected = False
        
        async def send_json_to(self, message):
            self.messages.append(message)
        
        async def receive_json_from(self):
            if self.messages:
                return self.messages.pop(0)
            return {'type': 'test_response'}
    
    return MockCommunicator


@pytest.fixture
def fixed_recommendation_time():
    """Fix time for consistent recommendation testing"""
    from django.utils import timezone
    
    fixed_datetime = timezone.now().replace(
        year=2024, month=1, day=15, hour=12, minute=0, second=0, microsecond=0
    )
    
    with patch('django.utils.timezone.now', return_value=fixed_datetime):
        yield fixed_datetime


@pytest.fixture
def recommendation_time_travel():
    """Utility for time travel in recommendation tests"""
    from django.utils import timezone
    from datetime import timedelta
    
    class RecommendationTimeTraveler:
        def __init__(self):
            self.current_time = timezone.now()
        
        def travel_to(self, target_time):
            self.current_time = target_time
            return patch('django.utils.timezone.now', return_value=target_time)
        
        def travel_days(self, days):
            target_time = self.current_time + timedelta(days=days)
            return self.travel_to(target_time)
        
        def travel_hours(self, hours):
            target_time = self.current_time + timedelta(hours=hours)
            return self.travel_to(target_time)
    
    return RecommendationTimeTraveler()


@pytest.fixture
def recommendation_performance_monitor():
    """Monitor recommendation test performance"""
    import time
    import threading
    
    class RecommendationPerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.monitoring = False
            self._monitor_thread = None
        
        def start(self):
            self.start_time = time.time()
            self.monitoring = True
        
        def stop(self):
            self.monitoring = False
            self.end_time = time.time()
        
        @property
        def elapsed_time(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return RecommendationPerformanceMonitor()


@pytest.fixture
def simulate_recommendation_errors():
    """Simulate errors for recommendation error handling tests"""
    from django.db import DatabaseError
    from django.core.cache import CacheKeyWarning
    
    def _simulate_db_error(model_class, method_name='objects'):
        return patch.object(
            getattr(model_class, method_name),
            'get',
            side_effect=DatabaseError('Simulated database error')
        )
    
    def _simulate_cache_error(operation='get'):
        return patch('django.core.cache.cache.' + operation,
                    side_effect=Exception('Simulated cache error'))
    
    return {
        'db_error': _simulate_db_error,
        'cache_error': _simulate_cache_error
    }


# ============================================================================
# PYTEST MARKS AND CONFIGURATIONS
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom marks"""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "requires_selenium: mark test as requiring selenium")
    config.addinivalue_line("markers", "requires_db: mark test as requiring database")
    config.addinivalue_line("markers", "edge_case: mark test as edge case test")
    config.addinivalue_line("markers", "recommendation: mark test as recommendation system test")


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Enable database access for all tests.
    This fixture is automatically used for all tests.
    """
    pass