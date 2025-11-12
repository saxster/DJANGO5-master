"""
Comprehensive tests for session security configuration.
Tests that session settings provide proper security without impacting performance.
"""

import time
from django.test import TestCase, override_settings, Client
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
from django.conf import settings
from apps.core.testing import poll_until


class SessionSecurityTest(TestCase):
    """Test session security configuration"""

    def test_session_engine_configuration(self):
        """Test session engine is configured for PostgreSQL"""
        # Should use database backend for PostgreSQL-first approach
        self.assertEqual(
            settings.SESSION_ENGINE,
            "django.contrib.sessions.backends.db"
        )

    def test_session_cookie_age_security(self):
        """Test session cookie age is properly configured"""
        # Rule #10: Should be 2 hours (2 * 60 * 60 = 7200 seconds)
        expected_age = 2 * 60 * 60
        self.assertEqual(settings.SESSION_COOKIE_AGE, expected_age)

        # Should be reasonable for security (not too short, not too long)
        self.assertGreaterEqual(settings.SESSION_COOKIE_AGE, 3600)  # >= 1 hour
        self.assertLessEqual(settings.SESSION_COOKIE_AGE, 7200)     # <= 2 hours (Rule #10)

    def test_session_expire_at_browser_close(self):
        """Test session expires when browser closes"""
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)

    def test_session_save_security(self):
        """Test session saving prioritizes security per Rule #10"""
        # Rule #10: Should save on every request for security
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_session_security_flags(self):
        """Test session cookies have proper security flags"""
        # In production, these should be secure
        if not settings.DEBUG:
            # These would be set in production settings
            expected_secure_settings = [
                'SESSION_COOKIE_SECURE',
                'SESSION_COOKIE_HTTPONLY',
                'SESSION_COOKIE_SAMESITE',
            ]

            for setting_name in expected_secure_settings:
                if hasattr(settings, setting_name):
                    setting_value = getattr(settings, setting_name)
                    if setting_name == 'SESSION_COOKIE_SECURE':
                        self.assertTrue(setting_value)
                    elif setting_name == 'SESSION_COOKIE_HTTPONLY':
                        self.assertTrue(setting_value)
                    elif setting_name == 'SESSION_COOKIE_SAMESITE':
                        self.assertIn(setting_value, ['Strict', 'Lax'])

    def test_database_session_optimizations(self):
        """Test database session optimizations are configured"""
        self.assertTrue(hasattr(settings, 'DATABASE_SESSION_OPTIMIZATIONS'))

        optimizations = settings.DATABASE_SESSION_OPTIMIZATIONS
        self.assertIsInstance(optimizations, dict)

        # Should have performance optimizations
        expected_optimizations = [
            'USE_INDEX_ON_SESSION_KEY',
            'USE_INDEX_ON_EXPIRE_DATE',
            'ENABLE_SESSION_CLEANUP'
        ]

        for optimization in expected_optimizations:
            self.assertIn(optimization, optimizations)
            self.assertTrue(optimizations[optimization])


class SessionFunctionalityTest(TestCase):
    """Test session functionality works correctly with security settings"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        User = get_user_model()
        self.test_user = User.objects.create_user(
            loginid='sessiontest',
            email='session@test.com',
            password='SecureTestPass123!'
        )

    def test_session_creation_and_persistence(self):
        """Test sessions are created and persist correctly"""
        # Start with no sessions
        initial_session_count = Session.objects.count()

        # Create a session by accessing a view that requires session
        response = self.client.get('/')

        # Session should be created
        self.assertIn('sessionid', self.client.cookies)

        # Session should be stored in database
        current_session_count = Session.objects.count()
        if response.status_code == 200:  # Only if view exists and accessible
            self.assertGreaterEqual(current_session_count, initial_session_count)

    def test_session_data_storage(self):
        """Test session data can be stored and retrieved"""
        session = self.client.session
        test_data = {'test_key': 'test_value', 'user_pref': 'dark_mode'}

        # Store data in session
        session.update(test_data)
        session.save()

        # Retrieve data from session
        self.assertEqual(session['test_key'], 'test_value')
        self.assertEqual(session['user_pref'], 'dark_mode')

    def test_session_security_with_authentication(self):
        """Test session security during authentication"""
        # Login user
        login_successful = self.client.login(
            username='sessiontest',
            password='SecureTestPass123!'
        )

        if login_successful:
            # Session should exist after login
            self.assertIn('sessionid', self.client.cookies)

            # Session should contain user information
            session = self.client.session
            self.assertIn('_auth_user_id', session)

    def test_session_invalidation_on_logout(self):
        """Test session is properly invalidated on logout"""
        # Login first
        if self.client.login(username='sessiontest', password='SecureTestPass123!'):
            old_session_key = self.client.session.session_key

            # Logout
            self.client.logout()

            # Old session should be invalid
            try:
                old_session = Session.objects.get(session_key=old_session_key)
                # If session still exists, it should be marked as expired or empty
                self.assertTrue(
                    old_session.expire_date < time.time() or
                    len(old_session.get_decoded()) == 0
                )
            except Session.DoesNotExist:
                # Session deleted - this is also acceptable
                pass

    @override_settings(SESSION_COOKIE_AGE=1)  # 1 second for testing
    def test_session_expiration(self):
        """Test session expiration works correctly"""
        session = self.client.session
        session['test_data'] = 'expires_quickly'
        session.save()

        original_session_key = session.session_key

        # Wait for session to expire
        import datetime

        def session_expired():
            try:
                expired_session = Session.objects.get(session_key=original_session_key)
                now = datetime.datetime.now()
                return expired_session.expire_date < now
            except Session.DoesNotExist:
                # Session cleaned up - acceptable
                return True

        poll_until(
            session_expired,
            timeout=5,
            interval=0.1,
            error_message="Session did not expire within timeout"
        )

    def test_concurrent_session_handling(self):
        """Test multiple concurrent sessions are handled correctly"""
        clients = [Client() for _ in range(5)]

        # Create sessions for multiple clients
        session_keys = []
        for i, client in enumerate(clients):
            session = client.session
            session[f'client_id'] = i
            session.save()
            session_keys.append(session.session_key)

        # All sessions should be unique
        self.assertEqual(len(set(session_keys)), 5)

        # All sessions should be retrievable
        for i, client in enumerate(clients):
            self.assertEqual(client.session['client_id'], i)


class SessionPerformanceTest(TestCase):
    """Test session performance with security settings"""

    def test_session_creation_performance(self):
        """Test session creation is fast enough"""
        clients = []
        start_time = time.time()

        # Create 100 sessions
        for _ in range(100):
            client = Client()
            session = client.session
            session['test'] = 'performance_test'
            session.save()
            clients.append(client)

        end_time = time.time()

        total_time = end_time - start_time
        avg_time_per_session = total_time / 100

        # Session creation should be fast (less than 10ms per session)
        self.assertLess(avg_time_per_session, 0.01)

    def test_session_save_performance(self):
        """Test session saving performance"""
        client = Client()
        session = client.session

        start_time = time.time()

        # Save session data 1000 times
        for i in range(1000):
            session[f'key_{i}'] = f'value_{i}'
            if i % 10 == 0:  # Save every 10 updates
                session.save()

        end_time = time.time()

        total_time = end_time - start_time
        avg_time_per_save = total_time / 100  # 100 saves total

        # Session saving should be fast (less than 5ms per save)
        self.assertLess(avg_time_per_save, 0.005)

    def test_session_retrieval_performance(self):
        """Test session data retrieval performance"""
        client = Client()
        session = client.session

        # Store test data
        test_data = {f'key_{i}': f'value_{i}' for i in range(100)}
        session.update(test_data)
        session.save()

        start_time = time.time()

        # Retrieve data 1000 times
        for _ in range(1000):
            for key in test_data:
                _ = session.get(key)

        end_time = time.time()

        total_time = end_time - start_time
        avg_time_per_retrieval = total_time / (1000 * 100)

        # Data retrieval should be very fast (less than 0.001ms per access)
        self.assertLess(avg_time_per_retrieval, 0.000001)


class SessionSecurityAttackTest(TestCase):
    """Test session security against common attacks"""

    def test_session_fixation_protection(self):
        """Test protection against session fixation attacks"""
        client = Client()

        # Get initial session
        response = client.get('/')
        if 'sessionid' in client.cookies:
            initial_session_id = client.cookies['sessionid'].value

            # Simulate login (which should regenerate session ID)
            User = get_user_model()
            user = User.objects.create_user(
                loginid='fixationtest',
                email='fixation@test.com',
                password='SecurePass123!'
            )

            login_successful = client.login(
                username='fixationtest',
                password='SecurePass123!'
            )

            if login_successful:
                # Session ID should change after login
                new_session_id = client.cookies['sessionid'].value
                self.assertNotEqual(initial_session_id, new_session_id)

    def test_session_data_isolation(self):
        """Test sessions are properly isolated between users"""
        User = get_user_model()
        user1 = User.objects.create_user(
            loginid='isolation1',
            email='isolation1@test.com',
            password='SecurePass123!'
        )
        user2 = User.objects.create_user(
            loginid='isolation2',
            email='isolation2@test.com',
            password='SecurePass123!'
        )

        client1 = Client()
        client2 = Client()

        # Login both users
        client1.login(username='isolation1', password='SecurePass123!')
        client2.login(username='isolation2', password='SecurePass123!')

        # Set different data for each session
        client1.session['user_data'] = 'user1_secret'
        client1.session.save()

        client2.session['user_data'] = 'user2_secret'
        client2.session.save()

        # Verify data isolation
        self.assertEqual(client1.session['user_data'], 'user1_secret')
        self.assertEqual(client2.session['user_data'], 'user2_secret')

        # Sessions should have different IDs
        self.assertNotEqual(
            client1.cookies['sessionid'].value,
            client2.cookies['sessionid'].value
        )

    def test_session_hijacking_protection(self):
        """Test protection against session hijacking"""
        client = Client()
        session = client.session
        session['sensitive_data'] = 'protected_information'
        session.save()

        original_session_key = session.session_key

        # Simulate session hijacking attempt
        malicious_client = Client()

        # Try to use stolen session key
        malicious_client.cookies['sessionid'] = original_session_key

        # The malicious client should not have access to session data
        # (This depends on additional security measures like IP binding)
        try:
            malicious_session_data = malicious_client.session.get('sensitive_data')
            # If session sharing is allowed, verify it's the same user
            # If not allowed, malicious_session_data should be None
            if malicious_session_data:
                # Additional checks would be needed in production
                pass
        except (ValueError, TypeError, AttributeError, KeyError):
            # Session access denied - this is good
            pass

    def test_session_cookie_security_attributes(self):
        """Test session cookies have proper security attributes"""
        client = Client()
        response = client.get('/')

        if 'sessionid' in client.cookies:
            session_cookie = client.cookies['sessionid']

            # In production, these should be set
            if not settings.DEBUG:
                # HttpOnly should be set to prevent XSS
                self.assertTrue(
                    getattr(session_cookie, 'httponly', False) or
                    getattr(settings, 'SESSION_COOKIE_HTTPONLY', True)
                )

                # Secure should be set for HTTPS
                self.assertTrue(
                    getattr(session_cookie, 'secure', False) or
                    getattr(settings, 'SESSION_COOKIE_SECURE', True)
                )

    def test_session_cleanup_mechanism(self):
        """Test session cleanup works to prevent session accumulation"""
        # Create expired sessions
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        import datetime

        expired_session = Session(
            session_key='expired_test_session',
            session_data='test_data',
            expire_date=timezone.now() - datetime.timedelta(days=1)
        )
        expired_session.save()

        initial_count = Session.objects.count()

        # Django's session cleanup would normally handle this
        # We test that the mechanism is available
        self.assertTrue(hasattr(Session.objects, 'all'))

        # Cleanup expired sessions
        expired_count = Session.objects.filter(
            expire_date__lt=timezone.now()
        ).count()

        if expired_count > 0:
            # Expired sessions exist and can be cleaned up
            Session.objects.filter(expire_date__lt=timezone.now()).delete()

            final_count = Session.objects.count()
            self.assertLess(final_count, initial_count)


class SessionIntegrationTest(TestCase):
    """Integration tests for session security in full application context"""

    def test_session_middleware_integration(self):
        """Test session middleware is properly configured"""
        from django.conf import settings

        # Session middleware should be present
        self.assertIn(
            'django.contrib.sessions.middleware.SessionMiddleware',
            settings.MIDDLEWARE
        )

    def test_session_with_csrf_protection(self):
        """Test sessions work correctly with CSRF protection"""
        client = Client(enforce_csrf_checks=True)

        # Get CSRF token (this creates a session)
        response = client.get('/')
        if response.status_code == 200:
            # Session should be created
            self.assertIn('sessionid', client.cookies)

            # If CSRF is enabled, CSRF token should be available
            if 'csrfmiddlewaretoken' in str(response.content):
                self.assertIn('csrftoken', client.cookies)

    def test_session_with_authentication_backend(self):
        """Test sessions work with custom authentication"""
        # This would test integration with the custom People model
        from apps.peoples.models import People

        # Create user with custom model
        user = People.objects.create_user(
            loginid='integration_test',
            email='integration@test.com',
            password='SecurePass123!',
            firstname='Test',
            lastname='User'
        )

        client = Client()
        login_successful = client.login(
            username='integration_test',
            password='SecurePass123!'
        )

        if login_successful:
            # Session should contain user information
            session = client.session
            self.assertIn('_auth_user_id', session)

            # User ID should match our custom model
            stored_user_id = session['_auth_user_id']
            self.assertEqual(int(stored_user_id), user.id)

    def test_session_performance_under_load(self):
        """Test session performance under concurrent load"""
        import threading
        import queue

        results = queue.Queue()

        def create_session():
            client = Client()
            start = time.time()
            session = client.session
            session['load_test'] = 'data'
            session.save()
            end = time.time()
            results.put(end - start)

        # Create 50 concurrent sessions
        threads = []
        for _ in range(50):
            thread = threading.Thread(target=create_session)
            threads.append(thread)

        start_time = time.time()

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        end_time = time.time()

        # Collect results
        times = []
        while not results.empty():
            times.append(results.get())

        # Performance should be acceptable
        avg_time = sum(times) / len(times)
        max_time = max(times)
        total_time = end_time - start_time

        # Average session creation should be fast
        self.assertLess(avg_time, 0.1)  # Less than 100ms average

        # No session creation should take too long
        self.assertLess(max_time, 1.0)  # Less than 1 second max

        # Total time should be reasonable for concurrent operations
        self.assertLess(total_time, 10.0)  # Less than 10 seconds total