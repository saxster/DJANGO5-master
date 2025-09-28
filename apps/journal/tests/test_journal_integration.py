"""
Comprehensive Journal & Wellness Integration Tests

Tests the complete integration of journal and wellness systems to ensure:
- Error-free operation across all components
- Privacy controls and consent management work correctly
- Pattern recognition triggers wellness content appropriately
- ML analytics generate accurate insights
- Mobile sync handles conflicts properly
- Multi-tenant isolation is maintained
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta
import uuid

from apps.wellness.models import WellnessContent, WellnessUserProgress, WellnessContentInteraction
from apps.tenants.models import Tenant
from ..services.pattern_analyzer import JournalPatternAnalyzer
from ..ml.analytics_engine import WellbeingAnalyticsEngine

User = get_user_model()


class JournalWellnessIntegrationTestCase(TransactionTestCase):
    """
    Integration tests for complete journal and wellness system
    Tests end-to-end functionality to ensure ERROR FREE operation
    """

    def setUp(self):
        """Set up test data for integration testing"""
        # Create test tenant
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

        # Create test users
        self.user1 = User.objects.create_user(
            loginid="testuser1",
            peoplename="Test User 1",
            email="test1@example.com",
            tenant=self.tenant
        )

        self.user2 = User.objects.create_user(
            loginid="testuser2",
            peoplename="Test User 2",
            email="test2@example.com",
            tenant=self.tenant
        )

        # Create wellness content
        self.wellness_content = WellnessContent.objects.create(
            title="Test Stress Management Tip",
            summary="Test content for stress management",
            content="Practice deep breathing when stressed.",
            category="stress_management",
            delivery_context="stress_response",
            content_level="quick_tip",
            evidence_level="peer_reviewed",
            source_name="Test Source",
            estimated_reading_time=2,
            tenant=self.tenant,
            created_by=self.user1
        )

    def test_journal_entry_creation_triggers_pattern_analysis(self):
        """Test that creating journal entry triggers pattern analysis"""
        # Create high-stress journal entry
        journal_entry = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            title="Stressful Day at Work",
            content="Feeling overwhelmed with equipment failures and deadlines",
            entry_type="STRESS_LOG",
            timestamp=timezone.now(),
            mood_rating=2,
            stress_level=5,
            energy_level=3,
            stress_triggers=["equipment failure", "deadline pressure"],
            privacy_scope="private",
            consent_given=True,
            consent_timestamp=timezone.now()
        )

        # Test pattern analysis
        analyzer = JournalPatternAnalyzer()
        analysis = analyzer.analyze_entry_for_immediate_action(journal_entry)

        # Validate analysis results
        self.assertGreaterEqual(analysis['urgency_score'], 5)  # Should trigger immediate intervention
        self.assertEqual(analysis['urgency_level'], 'high')
        self.assertIn('stress_management', analysis['intervention_categories'])
        self.assertTrue(analysis['crisis_detected'])

        # Verify wellness content would be triggered
        self.assertGreater(analysis['recommended_content_count'], 0)

    def test_privacy_controls_enforce_access_restrictions(self):
        """Test that privacy controls correctly restrict access to journal entries"""
        # Create private entry
        private_entry = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            title="Private Mood Entry",
            entry_type="MOOD_CHECK_IN",
            mood_rating=3,
            privacy_scope="private",
            timestamp=timezone.now()
        )

        # Create shared entry
        shared_entry = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            title="Shared Work Update",
            entry_type="PROJECT_MILESTONE",
            privacy_scope="shared",
            sharing_permissions=[str(self.user2.id)],
            timestamp=timezone.now(),
            consent_given=True,
            consent_timestamp=timezone.now()
        )

        # Test access controls
        self.assertTrue(private_entry.can_user_access(self.user1))  # Owner can access
        self.assertFalse(private_entry.can_user_access(self.user2))  # Other user cannot access

        self.assertTrue(shared_entry.can_user_access(self.user1))  # Owner can access
        self.assertTrue(shared_entry.can_user_access(self.user2))  # Shared user can access

        # Test wellbeing entries are always private
        wellbeing_entry = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            title="Mood Check",
            entry_type="MOOD_CHECK_IN",
            mood_rating=4,
            privacy_scope="shared",  # Attempted to share
            timestamp=timezone.now()
        )

        effective_scope = wellbeing_entry.get_effective_privacy_scope(self.user2)
        self.assertEqual(effective_scope, "private")  # Should be forced to private

    def test_ml_analytics_generate_accurate_insights(self):
        """Test ML analytics engine generates accurate wellbeing insights"""
        # Create test journal entries with wellbeing data
        test_entries = []
        base_date = timezone.now() - timedelta(days=30)

        for i in range(30):
            entry_date = base_date + timedelta(days=i)
            # Create varying mood/stress patterns
            mood = 8 - (i % 7)  # Weekly mood cycle
            stress = 2 + (i % 5)  # Stress pattern

            entry = JournalEntry.objects.create(
                user=self.user1,
                tenant=self.tenant,
                title=f"Day {i+1} Entry",
                entry_type="MOOD_CHECK_IN",
                timestamp=entry_date,
                mood_rating=mood,
                stress_level=stress,
                energy_level=7 - (i % 6),
                gratitude_items=[f"Grateful for item {i}"] if i % 3 == 0 else []
            )
            test_entries.append(entry)

        # Test analytics engine
        analytics_engine = WellbeingAnalyticsEngine()

        # Test mood trends
        mood_trends = analytics_engine.calculate_mood_trends(test_entries)
        self.assertIsNotNone(mood_trends['average_mood'])
        self.assertIn(mood_trends['trend_direction'], ['improving', 'declining', 'stable'])
        self.assertGreater(len(mood_trends['daily_moods']), 0)

        # Test stress analysis
        stress_analysis = analytics_engine.calculate_stress_trends(test_entries)
        self.assertIsNotNone(stress_analysis['average_stress'])
        self.assertGreater(len(stress_analysis['daily_stress']), 0)

        # Test overall wellbeing score
        energy_trends = analytics_engine.calculate_energy_trends(test_entries)
        wellbeing_score = analytics_engine.calculate_overall_wellbeing_score(
            mood_trends, stress_analysis, energy_trends, test_entries
        )

        self.assertIsInstance(wellbeing_score['overall_score'], (int, float))
        self.assertGreaterEqual(wellbeing_score['overall_score'], 0)
        self.assertLessEqual(wellbeing_score['overall_score'], 10)
        self.assertGreater(wellbeing_score['confidence'], 0)

    def test_wellness_content_personalization_works(self):
        """Test that wellness content personalization delivers appropriate content"""
        # Create user with wellness progress
        progress = WellnessUserProgress.objects.create(
            user=self.user1,
            tenant=self.tenant,
            enabled_categories=['stress_management', 'mental_health'],
            preferred_content_level='short_read',
            contextual_delivery_enabled=True
        )

        # Create stressed journal entry
        stressed_entry = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            title="High Stress Day",
            entry_type="STRESS_LOG",
            timestamp=timezone.now(),
            stress_level=5,
            mood_rating=2,
            stress_triggers=["equipment failure", "time pressure"]
        )

        # Test pattern analysis triggers appropriate content
        analyzer = JournalPatternAnalyzer()
        analysis = analyzer.analyze_entry_for_immediate_action(stressed_entry)

        # Verify high urgency is detected
        self.assertGreaterEqual(analysis['urgency_score'], 5)
        self.assertIn('stress_management', analysis['intervention_categories'])

        # Test content delivery system would select appropriate content
        from apps.wellness.services.content_delivery import WellnessContentDeliveryService

        delivery_service = WellnessContentDeliveryService()
        contextual_content = delivery_service.get_contextual_content(
            self.user1, stressed_entry, analysis
        )

        # Verify appropriate content is selected
        self.assertGreater(len(contextual_content), 0)

        # Check that stress management content is prioritized
        stress_content = [c for c in contextual_content if c.category == 'stress_management']
        self.assertGreater(len(stress_content), 0)

    def test_multi_tenant_isolation_maintained(self):
        """Test that multi-tenant isolation is properly maintained"""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            tenantname="Second Tenant",
            subdomain_prefix="tenant2"
        )

        user_tenant2 = User.objects.create_user(
            loginid="tenant2user",
            peoplename="Tenant 2 User",
            email="tenant2@example.com",
            tenant=tenant2
        )

        # Create journal entries for both tenants
        entry_tenant1 = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            title="Tenant 1 Entry",
            entry_type="PERSONAL_REFLECTION",
            timestamp=timezone.now()
        )

        entry_tenant2 = JournalEntry.objects.create(
            user=user_tenant2,
            tenant=tenant2,
            title="Tenant 2 Entry",
            entry_type="PERSONAL_REFLECTION",
            timestamp=timezone.now()
        )

        # Create wellness content for both tenants
        content_tenant1 = WellnessContent.objects.create(
            title="Tenant 1 Content",
            summary="Content for tenant 1",
            content="Test content",
            category="mental_health",
            delivery_context="daily_tip",
            content_level="quick_tip",
            evidence_level="educational",
            source_name="Test",
            estimated_reading_time=1,
            tenant=self.tenant
        )

        content_tenant2 = WellnessContent.objects.create(
            title="Tenant 2 Content",
            summary="Content for tenant 2",
            content="Test content",
            category="mental_health",
            delivery_context="daily_tip",
            content_level="quick_tip",
            evidence_level="educational",
            source_name="Test",
            estimated_reading_time=1,
            tenant=tenant2
        )

        # Test tenant isolation for journal entries
        tenant1_entries = JournalEntry.objects.filter(tenant=self.tenant)
        tenant2_entries = JournalEntry.objects.filter(tenant=tenant2)

        self.assertIn(entry_tenant1, tenant1_entries)
        self.assertNotIn(entry_tenant2, tenant1_entries)
        self.assertIn(entry_tenant2, tenant2_entries)
        self.assertNotIn(entry_tenant1, tenant2_entries)

        # Test tenant isolation for wellness content
        tenant1_content = WellnessContent.objects.filter(tenant=self.tenant)
        tenant2_content = WellnessContent.objects.filter(tenant=tenant2)

        self.assertIn(content_tenant1, tenant1_content)
        self.assertNotIn(content_tenant2, tenant1_content)
        self.assertIn(content_tenant2, tenant2_content)
        self.assertNotIn(content_tenant1, tenant2_content)

    def test_mobile_sync_handles_conflicts_correctly(self):
        """Test mobile sync conflict resolution works correctly"""
        # Create journal entry on server
        server_entry = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            title="Original Title",
            content="Original content",
            entry_type="PERSONAL_REFLECTION",
            timestamp=timezone.now(),
            mobile_id=uuid.uuid4(),
            version=1,
            sync_status="synced"
        )

        # Simulate client update with higher version
        client_data = {
            'mobile_id': str(server_entry.mobile_id),
            'title': 'Updated Title',
            'content': 'Updated content from mobile',
            'version': 2,
            'timestamp': timezone.now().isoformat()
        }

        # Test sync view logic would handle this correctly
        from apps.journal.views import JournalSyncView

        sync_view = JournalSyncView()

        # Simulate update handling
        result = sync_view._handle_entry_update(server_entry, client_data)

        # Verify server accepts client update
        self.assertEqual(result['status'], 'updated')

        # Refresh entry from database
        server_entry.refresh_from_db()
        self.assertEqual(server_entry.title, 'Updated Title')
        self.assertEqual(server_entry.version, 2)

        # Test conflict scenario (client behind server)
        client_data_old = {
            'mobile_id': str(server_entry.mobile_id),
            'title': 'Old Title',
            'version': 1,  # Behind server
            'timestamp': timezone.now().isoformat()
        }

        conflict_result = sync_view._handle_entry_update(server_entry, client_data_old)
        self.assertEqual(conflict_result['status'], 'conflict')
        self.assertEqual(conflict_result['server_version'], 2)
        self.assertEqual(conflict_result['client_version'], 1)

    def test_crisis_detection_and_intervention_workflow(self):
        """Test crisis detection triggers appropriate interventions"""
        # Create crisis-indicating journal entry
        crisis_entry = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            title="Struggling Today",
            content="Feeling hopeless and overwhelmed. Can't cope with everything.",
            entry_type="PERSONAL_REFLECTION",
            timestamp=timezone.now(),
            mood_rating=1,
            stress_level=5,
            energy_level=2
        )

        # Set up user privacy settings for crisis intervention
        privacy_settings = JournalPrivacySettings.objects.create(
            user=self.user1,
            crisis_intervention_consent=True,
            consent_timestamp=timezone.now()
        )

        # Test pattern analysis detects crisis
        analyzer = JournalPatternAnalyzer()
        analysis = analyzer.analyze_entry_for_immediate_action(crisis_entry)

        # Verify crisis detection
        self.assertTrue(analysis['crisis_detected'])
        self.assertGreaterEqual(analysis['urgency_score'], 6)
        self.assertIn('crisis_intervention', analysis['intervention_categories'])
        self.assertGreater(len(analysis['crisis_indicators']), 0)

        # Test that appropriate wellness content would be delivered
        self.assertEqual(analysis['delivery_timing'], 'immediate')
        self.assertTrue(analysis['follow_up_required'])

    def test_privacy_settings_auto_creation(self):
        """Test that privacy settings are automatically created for new users"""
        # Create new user
        new_user = User.objects.create_user(
            loginid="newuser",
            peoplename="New User",
            email="new@example.com",
            tenant=self.tenant
        )

        # Check that privacy settings were auto-created by signal
        self.assertTrue(hasattr(new_user, 'journal_privacy_settings'))

        privacy_settings = new_user.journal_privacy_settings
        self.assertEqual(privacy_settings.default_privacy_scope, 'private')
        self.assertFalse(privacy_settings.wellbeing_sharing_consent)
        self.assertIsNotNone(privacy_settings.consent_timestamp)

    def test_wellness_progress_tracks_correctly(self):
        """Test wellness progress tracking and gamification"""
        # Create wellness progress
        progress = WellnessUserProgress.objects.create(
            user=self.user1,
            tenant=self.tenant
        )

        # Create wellness interaction
        interaction = WellnessContentInteraction.objects.create(
            user=self.user1,
            content=self.wellness_content,
            interaction_type='completed',
            delivery_context='daily_tip',
            completion_percentage=100,
            user_rating=5,
            action_taken=True
        )

        # Refresh progress to see updates from signals
        progress.refresh_from_db()

        # Verify progress tracking
        self.assertEqual(progress.total_content_completed, 1)
        self.assertGreater(progress.total_score, 0)
        self.assertGreater(progress.current_streak, 0)

        # Test achievement checking
        new_achievements = progress.check_and_award_achievements()
        if progress.total_content_viewed >= 10:
            self.assertIn('content_explorer', progress.achievements_earned)

    def test_long_term_pattern_detection_works(self):
        """Test long-term pattern detection with sufficient data"""
        # Create 60 days of journal entries with patterns
        test_entries = []
        base_date = timezone.now() - timedelta(days=60)

        for i in range(60):
            entry_date = base_date + timedelta(days=i)
            day_of_week = entry_date.weekday()

            # Create pattern: Monday stress, Friday happiness
            if day_of_week == 0:  # Monday
                mood, stress = 4, 4
            elif day_of_week == 4:  # Friday
                mood, stress = 8, 2
            else:
                mood, stress = 6, 3

            entry = JournalEntry.objects.create(
                user=self.user1,
                tenant=self.tenant,
                title=f"Day {i+1}",
                entry_type="MOOD_CHECK_IN",
                timestamp=entry_date,
                mood_rating=mood,
                stress_level=stress,
                energy_level=6 + (i % 3)
            )
            test_entries.append(entry)

        # Test long-term pattern detection
        analyzer = JournalPatternAnalyzer()
        patterns = analyzer.detect_long_term_patterns(test_entries)

        # Verify patterns are detected
        self.assertFalse(patterns.get('insufficient_data', False))
        self.assertIn('stress_cycles', patterns['detected_patterns'])
        self.assertIn('mood_seasonality', patterns['detected_patterns'])

        # Check stress cycle detection
        stress_cycles = patterns['detected_patterns']['stress_cycles']
        if not stress_cycles.get('insufficient_data'):
            self.assertIn('Monday', stress_cycles.get('high_stress_days', []))

    def test_complete_api_workflow_end_to_end(self):
        """Test complete API workflow from journal creation to wellness delivery"""
        # This test simulates the complete user journey

        # 1. User creates journal entry via API
        journal_data = {
            'title': 'Challenging Work Day',
            'content': 'Equipment broke down and deadline pressure is high',
            'entry_type': 'STRESS_LOG',
            'timestamp': timezone.now().isoformat(),
            'mood_rating': 3,
            'stress_level': 4,
            'energy_level': 4,
            'stress_triggers': ['equipment failure', 'deadline pressure'],
            'privacy_scope': 'private',
            'consent_given': True
        }

        # Create entry
        entry = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            **{k: v for k, v in journal_data.items() if k != 'timestamp'},
            timestamp=timezone.now()
        )

        # 2. Pattern analysis should be triggered
        analyzer = JournalPatternAnalyzer()
        analysis = analyzer.analyze_entry_for_immediate_action(entry)

        # 3. Wellness content should be recommended
        self.assertGreater(analysis['urgency_score'], 0)

        # 4. Test analytics can be generated
        analytics_engine = WellbeingAnalyticsEngine()
        mood_trends = analytics_engine.calculate_mood_trends([entry])

        # 5. Test recommendations are generated
        stress_analysis = analytics_engine.calculate_stress_trends([entry])
        energy_trends = analytics_engine.calculate_energy_trends([entry])
        recommendations = analytics_engine.generate_recommendations(
            mood_trends, stress_analysis, energy_trends, [entry]
        )

        # Verify end-to-end workflow works
        self.assertIsNotNone(analysis)
        self.assertIsNotNone(mood_trends)
        self.assertIsInstance(recommendations, list)

    def test_data_integrity_and_validation(self):
        """Test data integrity and validation across the system"""
        # Test journal entry validation
        with self.assertRaises(Exception):
            # Invalid mood rating should fail
            JournalEntry.objects.create(
                user=self.user1,
                tenant=self.tenant,
                title="Invalid Entry",
                mood_rating=15,  # Invalid - should be 1-10
                timestamp=timezone.now()
            )

        # Test wellness content validation
        with self.assertRaises(Exception):
            # Invalid priority score should fail
            WellnessContent.objects.create(
                title="Invalid Content",
                summary="Test",
                content="Test content",
                category="mental_health",
                delivery_context="daily_tip",
                content_level="quick_tip",
                evidence_level="educational",
                source_name="Test",
                priority_score=150,  # Invalid - should be 1-100
                estimated_reading_time=1,
                tenant=self.tenant
            )

        # Test valid entries work correctly
        valid_entry = JournalEntry.objects.create(
            user=self.user1,
            tenant=self.tenant,
            title="Valid Entry",
            mood_rating=5,
            stress_level=3,
            energy_level=7,
            timestamp=timezone.now()
        )

        valid_content = WellnessContent.objects.create(
            title="Valid Content",
            summary="Test summary",
            content="Test content",
            category="mental_health",
            delivery_context="daily_tip",
            content_level="quick_tip",
            evidence_level="educational",
            source_name="Test Source",
            priority_score=50,
            estimated_reading_time=1,
            tenant=self.tenant
        )

        # Verify valid objects were created
        self.assertEqual(valid_entry.mood_rating, 5)
        self.assertEqual(valid_content.priority_score, 50)

    def test_signal_handlers_work_correctly(self):
        """Test that signal handlers properly process events"""
        # Test user creation signals
        signal_user = User.objects.create_user(
            loginid="signaluser",
            peoplename="Signal Test User",
            email="signal@example.com",
            tenant=self.tenant
        )

        # Verify signals created required objects
        self.assertTrue(hasattr(signal_user, 'journal_privacy_settings'))
        self.assertTrue(hasattr(signal_user, 'wellness_progress'))

        # Test journal entry creation signals
        signal_entry = JournalEntry.objects.create(
            user=signal_user,
            tenant=self.tenant,
            title="Signal Test Entry",
            entry_type="MOOD_CHECK_IN",
            mood_rating=2,  # Low mood should trigger analysis
            timestamp=timezone.now()
        )

        # Verify entry was processed (would trigger pattern analysis in real system)
        self.assertIsNotNone(signal_entry.id)
        self.assertEqual(signal_entry.version, 1)

    def test_wellness_content_seeding_command_works(self):
        """Test that wellness content seeding works correctly"""
        # Import and test the seeding command
        from apps.wellness.management.commands.seed_wellness_content import Command

        command = Command()

        # Test content data generation
        mental_health_content = command._get_content_data_for_category('mental_health')
        self.assertGreater(len(mental_health_content), 0)

        stress_content = command._get_content_data_for_category('stress_management')
        self.assertGreater(len(stress_content), 0)

        # Verify content structure is correct
        for content_item in mental_health_content:
            self.assertIn('title', content_item)
            self.assertIn('category', content_item)
            self.assertIn('evidence_level', content_item)
            self.assertIn('source_name', content_item)
            self.assertIn('action_tips', content_item)

    def tearDown(self):
        """Clean up test data"""
        # Clean up is handled automatically by TransactionTestCase
        pass


class JournalAPIEndpointTestCase(APITestCase):
    """Test journal API endpoints work correctly"""

    def setUp(self):
        """Set up API test data"""
        self.tenant = Tenant.objects.create(
            tenantname="API Test Tenant",
            subdomain_prefix="apitest"
        )

        self.user = User.objects.create_user(
            loginid="apiuser",
            peoplename="API Test User",
            email="api@example.com",
            tenant=self.tenant
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_journal_entry_crud_operations(self):
        """Test CRUD operations for journal entries"""
        # Test CREATE
        create_data = {
            'title': 'API Test Entry',
            'content': 'Testing API creation',
            'entry_type': 'PERSONAL_REFLECTION',
            'mood_rating': 7,
            'stress_level': 2,
            'privacy_scope': 'private',
            'consent_given': True
        }

        response = self.client.post('/api/v1/journal/entries/', create_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        entry_id = response.data['id']

        # Test READ
        response = self.client.get(f'/api/v1/journal/entries/{entry_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'API Test Entry')

        # Test UPDATE
        update_data = {'title': 'Updated API Entry'}
        response = self.client.patch(f'/api/v1/journal/entries/{entry_id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated API Entry')

        # Test LIST with filtering
        response = self.client.get('/api/v1/journal/entries/?entry_types=PERSONAL_REFLECTION')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)

        # Test DELETE (soft delete)
        response = self.client.delete(f'/api/v1/journal/entries/{entry_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_wellness_content_api_endpoints(self):
        """Test wellness content API endpoints"""
        # Create test wellness content
        content = WellnessContent.objects.create(
            title="API Test Content",
            summary="Test content summary",
            content="Test wellness content",
            category="mental_health",
            delivery_context="daily_tip",
            content_level="quick_tip",
            evidence_level="educational",
            source_name="Test Source",
            estimated_reading_time=1,
            tenant=self.tenant
        )

        # Test content listing
        response = self.client.get('/api/v1/wellness/content/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test daily tip endpoint
        response = self.client.get('/api/v1/wellness/daily-tip/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test personalized content endpoint
        response = self.client.get('/api/v1/wellness/personalized/?limit=3')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_and_analytics_endpoints(self):
        """Test search and analytics endpoints"""
        # Create test entries for analytics
        for i in range(5):
            JournalEntry.objects.create(
                user=self.user,
                tenant=self.tenant,
                title=f"Analytics Test {i}",
                entry_type="MOOD_CHECK_IN",
                mood_rating=5 + i,
                stress_level=2 + (i % 3),
                timestamp=timezone.now() - timedelta(days=i)
            )

        # Test analytics endpoint
        response = self.client.get('/api/v1/journal/analytics/?days=30')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify analytics structure
        self.assertIn('wellbeing_trends', response.data)
        self.assertIn('overall_wellbeing_score', response.data)

        # Test search endpoint
        search_data = {
            'query': 'Analytics Test',
            'mood_min': 5,
            'mood_max': 10
        }

        response = self.client.post('/api/v1/journal/search/', search_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def tearDown(self):
        """Clean up API test data"""
        pass