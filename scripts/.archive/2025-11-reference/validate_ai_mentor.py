#!/usr/bin/env python
"""
AI Mentor System Validation Script

Validates that all AI Mentor components are properly installed and configured.

Usage:
    python scripts/validate_ai_mentor.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()


def print_header(title):
    """Print section header"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_success(message):
    """Print success message"""
    print(f"✅ {message}")


def print_error(message):
    """Print error message"""
    print(f"❌ {message}")


def print_info(message):
    """Print info message"""
    print(f"ℹ️  {message}")


def validate_models():
    """Validate models are importable and have correct fields"""
    print_header("Validating Models")
    
    try:
        from apps.core.models import AdminMentorSession, AdminMentorTip
        print_success("Models imported successfully")
        
        # Check AdminMentorSession fields
        session_fields = [f.name for f in AdminMentorSession._meta.get_fields()]
        required_session_fields = [
            'admin_user', 'session_start', 'session_end', 'page_context',
            'features_used', 'features_shown', 'skill_level', 'questions_asked',
            'suggestions_shown', 'suggestions_followed', 'time_saved_estimate',
            'tasks_completed', 'shortcuts_used'
        ]
        
        for field in required_session_fields:
            if field in session_fields:
                print_success(f"AdminMentorSession.{field} exists")
            else:
                print_error(f"AdminMentorSession.{field} MISSING")
        
        # Check AdminMentorTip fields
        tip_fields = [f.name for f in AdminMentorTip._meta.get_fields()]
        required_tip_fields = [
            'trigger_context', 'condition', 'tip_title', 'tip_content',
            'tip_type', 'action_button_text', 'action_url', 'priority',
            'show_frequency', 'active'
        ]
        
        for field in required_tip_fields:
            if field in tip_fields:
                print_success(f"AdminMentorTip.{field} exists")
            else:
                print_error(f"AdminMentorTip.{field} MISSING")
        
    except ImportError as e:
        print_error(f"Failed to import models: {e}")
        return False
    
    return True


def validate_services():
    """Validate services are importable and have required methods"""
    print_header("Validating Services")
    
    try:
        from apps.core.services.admin_mentor_service import AdminMentorService
        print_success("AdminMentorService imported successfully")
        
        # Check required methods
        required_methods = [
            'get_contextual_suggestions',
            'analyze_efficiency',
            'answer_question',
            'track_suggestion_followed'
        ]
        
        for method in required_methods:
            if hasattr(AdminMentorService, method):
                print_success(f"AdminMentorService.{method}() exists")
            else:
                print_error(f"AdminMentorService.{method}() MISSING")
        
    except ImportError as e:
        print_error(f"Failed to import AdminMentorService: {e}")
        return False
    
    try:
        from apps.core.services.admin_tutorial_service import AdminTutorialService
        print_success("AdminTutorialService imported successfully")
        
        # Check tutorials
        tutorials = AdminTutorialService.TUTORIALS
        print_info(f"Found {len(tutorials)} tutorials")
        
        expected_tutorials = [
            'welcome',
            'quick_actions_deep_dive',
            'smart_assignment_tutorial',
            'saved_views_tutorial',
            'keyboard_shortcuts_tutorial'
        ]
        
        for tutorial_id in expected_tutorials:
            if tutorial_id in tutorials:
                tutorial = tutorials[tutorial_id]
                print_success(f"Tutorial '{tutorial.title}' ({len(tutorial.steps)} steps)")
            else:
                print_error(f"Tutorial '{tutorial_id}' MISSING")
        
    except ImportError as e:
        print_error(f"Failed to import AdminTutorialService: {e}")
        return False
    
    return True


def validate_api_views():
    """Validate API views are importable"""
    print_header("Validating API Views")
    
    try:
        from apps.core.api.mentor_views import (
            MentorSuggestionsAPI,
            MentorAskAPI,
            MentorTrackSuggestionAPI,
            MentorEfficiencyAPI,
            TutorialListAPI,
            TutorialDetailAPI
        )
        
        views = [
            'MentorSuggestionsAPI',
            'MentorAskAPI',
            'MentorTrackSuggestionAPI',
            'MentorEfficiencyAPI',
            'TutorialListAPI',
            'TutorialDetailAPI'
        ]
        
        for view in views:
            print_success(f"{view} imported successfully")
        
    except ImportError as e:
        print_error(f"Failed to import API views: {e}")
        return False
    
    return True


def validate_urls():
    """Validate URL configuration"""
    print_header("Validating URL Configuration")
    
    try:
        from django.urls import reverse, NoReverseMatch
        
        url_names = [
            'core_api:mentor_suggestions',
            'core_api:mentor_ask',
            'core_api:mentor_track_suggestion',
            'core_api:mentor_efficiency',
            'core_api:tutorial_list'
        ]
        
        for url_name in url_names:
            try:
                url = reverse(url_name)
                print_success(f"{url_name} → {url}")
            except NoReverseMatch:
                print_error(f"{url_name} NOT FOUND in URL configuration")
        
    except Exception as e:
        print_error(f"Failed to validate URLs: {e}")
        return False
    
    return True


def validate_admin():
    """Validate admin classes are registered"""
    print_header("Validating Admin Classes")
    
    try:
        from django.contrib import admin
        from apps.core.models import AdminMentorSession, AdminMentorTip
        
        if AdminMentorSession in admin.site._registry:
            print_success("AdminMentorSession registered in admin")
        else:
            print_error("AdminMentorSession NOT registered in admin")
        
        if AdminMentorTip in admin.site._registry:
            print_success("AdminMentorTip registered in admin")
        else:
            print_error("AdminMentorTip NOT registered in admin")
        
    except Exception as e:
        print_error(f"Failed to validate admin: {e}")
        return False
    
    return True


def validate_template():
    """Validate template file exists"""
    print_header("Validating Template")
    
    template_path = 'templates/admin/includes/ai_mentor_widget.html'
    
    if os.path.exists(template_path):
        print_success(f"Template file exists: {template_path}")
        
        # Check file size
        size = os.path.getsize(template_path)
        print_info(f"Template size: {size} bytes")
        
        # Check for key components
        with open(template_path, 'r') as f:
            content = f.read()
            
            checks = [
                ('mentor-avatar', 'Floating avatar'),
                ('mentor-panel', 'Mentor panel'),
                ('mentor-suggestions', 'Suggestions container'),
                ('toggleMentor', 'Toggle function'),
                ('loadMentorSuggestions', 'Load suggestions function'),
                ('askMentor', 'Ask question function')
            ]
            
            for check_id, check_name in checks:
                if check_id in content:
                    print_success(f"{check_name} found in template")
                else:
                    print_error(f"{check_name} MISSING from template")
    else:
        print_error(f"Template file NOT FOUND: {template_path}")
        return False
    
    return True


def validate_database():
    """Validate database tables exist"""
    print_header("Validating Database")
    
    try:
        from apps.core.models import AdminMentorSession, AdminMentorTip
        
        # Try to query models (will fail if tables don't exist)
        try:
            AdminMentorSession.objects.count()
            print_success("AdminMentorSession table exists")
        except Exception as e:
            print_error(f"AdminMentorSession table NOT FOUND: {e}")
            print_info("Run: python manage.py migrate")
        
        try:
            AdminMentorTip.objects.count()
            tip_count = AdminMentorTip.objects.filter(active=True).count()
            print_success(f"AdminMentorTip table exists ({tip_count} active tips)")
        except Exception as e:
            print_error(f"AdminMentorTip table NOT FOUND: {e}")
            print_info("Run: python manage.py migrate")
        
    except Exception as e:
        print_error(f"Database validation failed: {e}")
        return False
    
    return True


def main():
    """Run all validations"""
    print("\n" + "=" * 60)
    print("  AI MENTOR SYSTEM VALIDATION")
    print("=" * 60)
    
    results = {
        'Models': validate_models(),
        'Services': validate_services(),
        'API Views': validate_api_views(),
        'URLs': validate_urls(),
        'Admin': validate_admin(),
        'Template': validate_template(),
        'Database': validate_database()
    }
    
    # Summary
    print_header("VALIDATION SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for component, status in results.items():
        if status:
            print_success(f"{component}: PASSED")
        else:
            print_error(f"{component}: FAILED")
    
    print(f"\n{'=' * 60}")
    print(f"  OVERALL: {passed}/{total} components validated")
    print('=' * 60)
    
    if passed == total:
        print("\n🎉 All validations passed! AI Mentor system is ready to use!")
        print("\nNext steps:")
        print("1. Create sample tips in Django Admin")
        print("2. Add widget to admin templates")
        print("3. Test the API endpoints")
        print("4. See AI_MENTOR_QUICK_START.md for details")
        return 0
    else:
        print("\n⚠️  Some validations failed. Please fix the issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
