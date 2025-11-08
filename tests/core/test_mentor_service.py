"""
Tests for AI Mentor Service

Tests all advanced mentor features including daily briefing,
next action suggestions, learning paths, and achievements.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from apps.core.services.admin_mentor_service import AdminMentorService
from apps.core.models.admin_mentor import AdminMentorSession


@pytest.mark.django_db
class TestAdminMentorService:
    """Test AI mentor service methods"""
    
    def test_generate_daily_briefing(self, admin_user):
        """Test daily briefing generation"""
        briefing = AdminMentorService.generate_daily_briefing(admin_user)
        
        assert 'greeting' in briefing
        assert admin_user.first_name in briefing['greeting'] or admin_user.username in briefing['greeting']
        assert 'date' in briefing
        assert 'summary' in briefing
        assert 'priorities' in briefing
        assert 'suggestions' in briefing
        assert 'tip_of_day' in briefing
        assert isinstance(briefing['summary'], dict)
        assert isinstance(briefing['priorities'], list)
    
    def test_suggest_next_best_action(self, admin_user):
        """Test next action suggestion"""
        next_action = AdminMentorService.suggest_next_best_action(admin_user)
        
        assert 'action' in next_action
        assert 'reason' in next_action
        assert 'url' in next_action
        assert 'priority' in next_action
        assert 'estimated_time' in next_action
        
        assert next_action['priority'] in ['HIGH', 'MEDIUM', 'LOW']
        assert len(next_action['action']) > 0
    
    def test_create_personalized_learning_path_new_user(self, admin_user):
        """Test learning path for new user"""
        learning_path = AdminMentorService.create_personalized_learning_path(admin_user)
        
        assert learning_path['current_level'] == 'NOVICE'
        assert learning_path['features_mastered'] == 0
        assert learning_path['features_remaining'] == 9
        assert len(learning_path['next_steps']) <= 3
        assert isinstance(learning_path['estimated_time'], int)
    
    def test_create_personalized_learning_path_intermediate_user(self, admin_user):
        """Test learning path for intermediate user"""
        AdminMentorSession.objects.create(
            admin_user=admin_user,
            page_context='/admin/',
            skill_level='INTERMEDIATE',
            features_used=['team_dashboard', 'quick_actions', 'priority_alerts']
        )
        
        learning_path = AdminMentorService.create_personalized_learning_path(admin_user)
        
        assert learning_path['current_level'] == 'INTERMEDIATE'
        assert learning_path['features_mastered'] == 3
        assert learning_path['features_remaining'] == 6
        
        for step in learning_path['next_steps']:
            assert step['feature'] not in ['team_dashboard', 'quick_actions', 'priority_alerts']
    
    def test_get_user_achievements_no_activity(self, admin_user):
        """Test achievements for user with no activity"""
        achievements = AdminMentorService.get_user_achievements(admin_user)
        
        assert achievements['total_points'] == 0
        assert achievements['achievements'] == []
        assert achievements['next_achievement'] is not None
    
    def test_get_user_achievements_first_feature(self, admin_user):
        """Test achievement unlock for first feature"""
        AdminMentorSession.objects.create(
            admin_user=admin_user,
            page_context='/admin/',
            features_used=['quick_actions']
        )
        
        achievements = AdminMentorService.get_user_achievements(admin_user)
        
        assert achievements['total_points'] >= 10
        assert len(achievements['achievements']) == 1
        assert achievements['achievements'][0]['id'] == 'first_feature'
        assert achievements['achievements'][0]['unlocked'] is True
    
    def test_get_user_achievements_keyboard_warrior(self, admin_user):
        """Test keyboard warrior achievement"""
        AdminMentorSession.objects.create(
            admin_user=admin_user,
            page_context='/admin/',
            features_used=['quick_actions'],
            shortcuts_used=15
        )
        
        achievements = AdminMentorService.get_user_achievements(admin_user)
        
        keyboard_achievement = next(
            (a for a in achievements['achievements'] if a['id'] == 'keyboard_warrior'),
            None
        )
        
        assert keyboard_achievement is not None
        assert keyboard_achievement['unlocked'] is True
        assert keyboard_achievement['points'] == 25
    
    def test_get_user_achievements_time_saver(self, admin_user):
        """Test time saver achievement"""
        AdminMentorSession.objects.create(
            admin_user=admin_user,
            page_context='/admin/',
            features_used=['quick_actions'],
            time_saved_estimate=3700
        )
        
        achievements = AdminMentorService.get_user_achievements(admin_user)
        
        time_saver = next(
            (a for a in achievements['achievements'] if a['id'] == 'time_saver'),
            None
        )
        
        assert time_saver is not None
        assert time_saver['unlocked'] is True
        assert time_saver['points'] == 50
    
    def test_get_user_achievements_power_user(self, admin_user):
        """Test power user achievement"""
        all_features = [
            'team_dashboard',
            'quick_actions',
            'priority_alerts',
            'approval_workflows',
            'activity_timelines',
            'smart_assignment',
            'saved_views',
            'shift_tracker',
            'keyboard_shortcuts'
        ]
        
        AdminMentorSession.objects.create(
            admin_user=admin_user,
            page_context='/admin/',
            features_used=all_features,
            time_saved_estimate=7200
        )
        
        achievements = AdminMentorService.get_user_achievements(admin_user)
        
        power_user = next(
            (a for a in achievements['achievements'] if a['id'] == 'power_user'),
            None
        )
        
        assert power_user is not None
        assert power_user['unlocked'] is True
        assert power_user['points'] == 100
        
        assert achievements['total_points'] >= 185
    
    def test_analyze_efficiency_no_data(self, admin_user):
        """Test efficiency analysis with no data"""
        analysis = AdminMentorService.analyze_efficiency(admin_user, days=30)
        
        assert analysis['total_time_saved'] == 0
        assert analysis['features_adopted'] == 0
        assert analysis['shortcuts_proficiency'] == 0
        assert analysis['efficiency_score'] == 0
        assert isinstance(analysis['recommendations'], list)
    
    def test_analyze_efficiency_with_data(self, admin_user):
        """Test efficiency analysis with session data"""
        AdminMentorSession.objects.create(
            admin_user=admin_user,
            page_context='/admin/',
            features_used=['quick_actions', 'team_dashboard', 'priority_alerts'],
            shortcuts_used=8,
            time_saved_estimate=3600
        )
        
        analysis = AdminMentorService.analyze_efficiency(admin_user, days=30)
        
        assert analysis['total_time_saved'] == 3600
        assert analysis['features_adopted'] == 3
        assert analysis['shortcuts_proficiency'] == 8
        assert analysis['efficiency_score'] > 0
        assert analysis['efficiency_score'] <= 100
    
    def test_answer_question(self, admin_user):
        """Test question answering"""
        answer = AdminMentorService.answer_question(
            "How do I use quick actions?",
            admin_user
        )
        
        assert 'title' in answer
        assert 'answer' in answer
        assert 'related_articles' in answer
        assert isinstance(answer['related_articles'], list)
    
    def test_track_suggestion_followed(self, admin_user):
        """Test tracking suggestion followed"""
        session = AdminMentorSession.objects.create(
            admin_user=admin_user,
            page_context='/admin/',
            suggestions_followed=[]
        )
        
        AdminMentorService.track_suggestion_followed(
            admin_user,
            'smart_assign_tickets'
        )
        
        session.refresh_from_db()
        assert 'smart_assign_tickets' in session.suggestions_followed
    
    def test_contextual_suggestions_ticket_list(self, admin_user):
        """Test contextual suggestions for ticket list"""
        suggestions = AdminMentorService.get_contextual_suggestions(
            user=admin_user,
            page_url='/admin/ticket/changelist/',
            context={'unassigned_count': 15}
        )
        
        assert isinstance(suggestions, list)
        assert len(suggestions) <= 3
        
        if suggestions:
            assert 'id' in suggestions[0]
            assert 'type' in suggestions[0]
            assert 'priority' in suggestions[0]
            assert 'title' in suggestions[0]
            assert 'message' in suggestions[0]


@pytest.fixture
def admin_user(db):
    """Create admin user for testing"""
    from apps.peoples.models import People
    from apps.tenants.models import Tenant
    
    tenant = Tenant.objects.create(
        name='Test Tenant',
        slug='test-tenant'
    )
    
    user = People.objects.create_user(
        username='testadmin',
        email='admin@test.com',
        password='testpass123',
        tenant=tenant
    )
    
    user.first_name = 'Test'
    user.last_name = 'Admin'
    user.save()
    
    return user
